"""Intake (M6 W4): one commit of a git repository becomes an input repository under fixtures/repos/<name>, with a
record of where it came from in fixtures/intake/<name>.json (outside the workspace: the agent never sees or changes
it).

The files are the commit's tree exactly: every blob is written from `git cat-file`, so no .gitattributes rule
(export-ignore, export-subst, eol conversion) changes them, as `git archive` would. Paths named in `exclude` are left
out (each must match something, so a typo cannot silently exclude nothing). Symlinks and submodules are refused unless
excluded: the workspace holds regular files only. Git runs without user or system config and without hooks.

A code task whose workspace has a record checks the snapshot against it in setup, before any model call: a file
changed, added, removed, or with a different executable bit since intake blocks the run (codetask/run.py).
"""
import hashlib
import json
import os
import re
import stat
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

from .contract import check_glob
from .workspace import digest, snapshot

NAME = re.compile(r"^[a-z][a-z0-9_]{0,39}$")
REPOS, RECORDS = Path("fixtures") / "repos", Path("fixtures") / "intake"
VERSION = 1


class IntakeError(Exception):
    pass


def git(repo, *args, data=None):
    env = {**os.environ, "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull, "GIT_TERMINAL_PROMPT": "0"}
    r = subprocess.run(["git", "-c", "core.hooksPath=" + os.devnull, "-C", str(repo), *args], input=data,
                       capture_output=True, env=env, timeout=300)
    if r.returncode != 0:
        raise IntakeError(f"git {' '.join(args[:2])} failed: {r.stderr.decode(errors='replace').strip()[:300]}")
    return r.stdout


# SPEC_PROTECTED_FILES P1: the repository's own list of files the agent never changes, read from the commit (never a
# working tree) and kept in the intake record, so every stage of a job uses the list of the commit it was taken from.
PROTECTED_FILE = ".argus/protected"
MAX_PROTECTED = 200


def parse_protected(data):
    """{"sha256", "globs"} of the bytes of a .argus/protected: one scope glob per line, blank lines and # comments left
    out; the file itself is always in the list. Anything else is an IntakeError naming the line."""
    try:
        text = data.decode("utf-8-sig")             # a byte order mark (Windows editors) is not part of the first glob
    except UnicodeDecodeError as e:
        raise IntakeError(f"{PROTECTED_FILE} is not UTF-8 text") from e
    globs = []
    for n, line in enumerate(text.splitlines(), 1):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if not check_glob(line) or not all(c.isprintable() and not c.isspace() for c in line):
            raise IntakeError(f"{PROTECTED_FILE} line {n}: {line[:80]!r} is not a scope glob (relative, '/'-separated, "
                              "no '..', no spaces or invisible characters)")
        if line not in globs:
            globs.append(line)
    if len(globs) > MAX_PROTECTED:
        raise IntakeError(f"{PROTECTED_FILE} has {len(globs)} globs, more than {MAX_PROTECTED}")
    if PROTECTED_FILE not in globs:
        globs.append(PROTECTED_FILE)
    return {"sha256": hashlib.sha256(data).hexdigest(), "globs": globs}


def read_protected(repo, commit):
    """The parsed .argus/protected of the commit, or None when the commit has none. Only a regular file counts: a link
    or a directory there is an IntakeError, never a list read from somewhere else."""
    out = git(repo, "ls-tree", "-z", commit, "--", PROTECTED_FILE)
    if not out:
        return None
    meta, _, _ = out.rstrip(b"\0").partition(b"\t")
    mode, kind, sha = meta.decode().split()
    if kind != "blob" or mode not in ("100644", "100755"):
        raise IntakeError(f"{PROTECTED_FILE} in commit {commit[:12]} is not a regular file (mode {mode})")
    parsed = parse_protected(git(repo, "cat-file", "blob", sha))
    # a glob names files, never a directory: 'public' would protect nothing below public/ (say so, never widen it)
    dirs = set(git(repo, "ls-tree", "-r", "-d", "-z", "--name-only", commit).decode("utf-8").split("\0")) - {""}
    for g in parsed["globs"]:
        if not any(c in g for c in "*?") and g in dirs:
            raise IntakeError(f"{PROTECTED_FILE}: {g!r} is a directory in commit {commit[:12]}; globs match files: "
                              f"write {g + '/**'!r}")
    return parsed


def _plain(path):
    return (isinstance(path, str) and path and "\\" not in path and not path.startswith("/")
            and all(p not in ("", ".", "..") for p in path.split("/")))


def tree_entries(repo, commit):
    """[(mode, type, blob sha, path)] of every entry in the commit's tree."""
    out = []
    for rec in git(repo, "ls-tree", "-r", "-z", "--full-tree", commit).split(b"\0"):
        if not rec:
            continue
        meta, path = rec.split(b"\t", 1)
        mode, kind, sha = meta.decode().split()
        out.append((mode, kind, sha, path.decode("utf-8")))
    return out


def excluded(path, exclude):
    return any(path == e or path.startswith(e + "/") for e in exclude)


def write_tree(repo, commit, dest, exclude):
    """Write the commit's files (minus exclude) below dest. Returns the sorted executable paths."""
    entries = tree_entries(repo, commit)
    unused = [e for e in exclude if not any(excluded(p, [e]) for _, _, _, p in entries)]
    if unused:
        raise IntakeError(f"exclude matches nothing in {commit[:12]}: {unused}")
    keep = [(m, k, s, p) for m, k, s, p in entries if not excluded(p, exclude)]
    odd = [p for m, k, s, p in keep if k != "blob" or m not in ("100644", "100755")]
    if odd:
        raise IntakeError(f"not regular files (symlink or submodule); exclude them or leave the repo: {odd[:10]}")
    if any(p.split("/")[-1] == "__pycache__" or "/__pycache__/" in f"/{p}/" for _, _, _, p in keep):
        raise IntakeError("the commit tracks __pycache__ files, which workspaces never contain")
    blobs = git(repo, "cat-file", "--batch", data="".join(f"{s}\n" for _, _, s, _ in keep).encode())
    pos, executable = 0, []
    for mode, _, sha, path in keep:
        header_end = blobs.index(b"\n", pos)
        got_sha, _, size = blobs[pos:header_end].decode().split()
        if got_sha != sha:
            raise IntakeError(f"git cat-file returned {got_sha} for {sha}")
        start = header_end + 1
        body, pos = blobs[start:start + int(size)], start + int(size) + 1
        target = dest / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(body)
        os.chmod(target, 0o755 if mode == "100755" else 0o644)
        if mode == "100755":
            executable.append(path)
    return sorted(executable)


def executables(root):
    root = Path(root)
    return sorted(p.relative_to(root).as_posix() for p in root.rglob("*")
                  if p.is_file() and not p.is_symlink() and "__pycache__" not in p.parts
                  and os.stat(p).st_mode & stat.S_IXUSR)


def remote_url(repo):
    """The origin URL without any user or password in it (a token must never land in a public record)."""
    try:
        url = git(repo, "remote", "get-url", "origin").decode().strip()
    except IntakeError:
        return None
    parts = urlsplit(url)
    if parts.scheme and parts.netloc:
        return urlunsplit((parts.scheme, parts.hostname + (f":{parts.port}" if parts.port else ""), parts.path, "", ""))
    return url.split("@", 1)[-1] if "@" in url.split(":", 1)[0] else url


_UNREAD = object()


def intake(repo, commit, name, *, exclude=(), root=".", protected=_UNREAD):
    """Create fixtures/repos/<name> from the commit and fixtures/intake/<name>.json. Refuses to overwrite. protected:
    read_protected() of this commit when the caller already read it (router), so one reading decides both."""
    root, repo = Path(root), Path(repo)
    if not NAME.match(name or ""):
        raise IntakeError(f"name {name!r} must be a lower-case name")
    exclude = list(exclude)
    bad = [e for e in exclude if not _plain(e)]
    if bad:
        raise IntakeError(f"exclude entries must be plain relative paths: {bad}")
    dest, record_path = root / REPOS / name, root / RECORDS / f"{name}.json"
    if dest.exists() or record_path.exists():
        raise IntakeError(f"{dest} or {record_path} already exists; intake never overwrites")
    full = git(repo, "rev-parse", "--verify", f"{commit}^{{commit}}").decode().strip()
    tree = git(repo, "rev-parse", "--verify", f"{full}^{{tree}}").decode().strip()
    (root / REPOS).mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=root / REPOS, prefix=".intake-") as tmp:   # same filesystem: atomic rename
        stage = Path(tmp) / name
        stage.mkdir()
        exec_paths = write_tree(repo, full, stage, exclude)
        snap = snapshot(stage)
        if not snap:
            raise IntakeError("the snapshot is empty")
        record = {"intake_version": VERSION, "name": name, "repo": remote_url(repo) or repo.resolve().name,
                  "commit": full, "tree": tree, "exclude": exclude, "files": len(snap),
                  "snapshot_sha256": digest(snap), "executable": exec_paths, "protected": read_protected(repo, full) if protected is _UNREAD else protected,
                  "created_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}
        # The record is published before the workspace, each by an atomic rename. A stop in between leaves a record
        # without its workspace, which check() reports and setup blocks; never a workspace without its record, which
        # would pass for a hand-written fixture and skip the check.
        record_path.parent.mkdir(parents=True, exist_ok=True)
        part = record_path.with_name(f".{name}.json.part")
        part.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
        os.replace(part, record_path)
        os.replace(stage, dest)
    return record


def record_for(workspace, root="."):
    """The intake record of a contract's workspace (fixtures/repos/<name>), or None if it has none."""
    parts = Path(workspace).parts
    if len(parts) != 3 or Path(*parts[:2]) != REPOS or not NAME.match(parts[2]):
        return None
    path = Path(root) / RECORDS / f"{parts[2]}.json"
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        raise IntakeError(f"intake record {path} is unreadable: {e}") from e


def check(record, workspace_dir):
    """Problems between a snapshot on disk and its intake record, or []."""
    if not Path(workspace_dir).is_dir():
        return [f"the workspace of intake {record.get('name')!r} is missing (an intake stopped before publishing it?)"]
    snap = snapshot(workspace_dir, skip_cache=True)
    problems = []
    if digest(snap) != record.get("snapshot_sha256") or len(snap) != record.get("files"):
        problems.append(f"files differ from the intake of {record.get('commit', '?')[:12]} "
                        f"({len(snap)} files now, {record.get('files')} at intake)")
    if os.name == "posix" and executables(workspace_dir) != record.get("executable"):
        problems.append("executable bits differ from the intake")
    return problems


def approved_tests(record):
    """{path: sha256} of the test files approval added or changed in a task's workspace ({} for other records)."""
    if record.get("kind") != "task":
        return {}
    out = {}
    for path, body in (record.get("added") or {}).items():
        if isinstance(body, str) and body:
            out[path] = body
    for path, info in (record.get("changed") or {}).items():
        after = info.get("after") if isinstance(info, dict) else info
        if isinstance(after, str) and after:
            out[path] = after
    return out


def check_against_repo(record, workspace_dir, repo):
    """Problems between the snapshot and the commit's tree rebuilt now from the repository (minus the exclusions).

    A task's workspace is that tree plus the approved tests the record lists (their `added` hash, or the `after` hash
    of a `changed` one); an intake record without a kind is checked against the tree alone."""
    with tempfile.TemporaryDirectory() as tmp:
        fresh = Path(tmp) / "fresh"
        fresh.mkdir()
        write_tree(repo, record["commit"], fresh, record["exclude"])
        tree = snapshot(fresh)
        expected = {**tree, **approved_tests(record)}
        if expected != snapshot(workspace_dir, skip_cache=True):
            return ["the snapshot is not the commit's tree minus the exclusions"]
        if os.name == "posix":
            got = executables(workspace_dir)
            if record.get("kind") == "task":
                got = [p for p in got if p in tree]   # an approved test brings its own bits; the record fixes content
            if executables(fresh) != got:
                return ["executable bits differ from the commit"]
    return []

