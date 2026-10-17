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
import json
import os
import re
import stat
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

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


def intake(repo, commit, name, *, exclude=(), root="."):
    """Create fixtures/repos/<name> from the commit and fixtures/intake/<name>.json. Refuses to overwrite."""
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
        os.replace(stage, dest)
    record = {"intake_version": VERSION, "name": name, "repo": remote_url(repo) or repo.resolve().name,
              "commit": full, "tree": tree, "exclude": exclude, "files": len(snap),
              "snapshot_sha256": digest(snap), "executable": exec_paths,
              "created_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}
    record_path.parent.mkdir(parents=True, exist_ok=True)
    record_path.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
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
    snap = snapshot(workspace_dir, skip_cache=True)
    problems = []
    if digest(snap) != record.get("snapshot_sha256") or len(snap) != record.get("files"):
        problems.append(f"files differ from the intake of {record.get('commit', '?')[:12]} "
                        f"({len(snap)} files now, {record.get('files')} at intake)")
    if os.name == "posix" and executables(workspace_dir) != record.get("executable"):
        problems.append("executable bits differ from the intake")
    return problems


def check_against_repo(record, workspace_dir, repo):
    """Problems between the snapshot and the commit's tree rebuilt now from the repository (minus the exclusions)."""
    with tempfile.TemporaryDirectory() as tmp:
        fresh = Path(tmp) / "fresh"
        fresh.mkdir()
        write_tree(repo, record["commit"], fresh, record["exclude"])
        if snapshot(fresh) != snapshot(workspace_dir, skip_cache=True):
            return ["the snapshot is not the commit's tree minus the exclusions"]
        if os.name == "posix" and executables(fresh) != executables(workspace_dir):
            return ["executable bits differ from the commit"]
    return []

