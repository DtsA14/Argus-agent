"""`argus apply <job> --read-sha <sha>` (docs/reviews/SPEC_ARGUS_APPLY.md PR 2): the review package's patch goes into the target repository and one commit is made,
then the job is recorded as applied. The mechanical steps of what a human did by hand; reading the patch is not one of them, `--read-sha` says someone looked at
the sha `status` prints (it does not prove the patch was read, as `approve --sha` does not).

Nothing here pushes, merges, deploys or calls a model. The target repository and its .git are trusted code and so is the git binary; everything else the
repository could make git run (hooks, filters, fsmonitor, gpg, diff drivers, includes, GIT_* of the caller) is switched off or refused. Every refusal before the
first change leaves the repository and the job untouched (git may write one unreachable blob object while it checks the patch in a temporary index); a failure after it is
undone and checked, unless the commit was already made."""
import fcntl
import hashlib
import json
import os
import re
import subprocess
import tempfile
from contextlib import contextmanager
from pathlib import Path

from acceptance.contract import matches
from router import job as rj
from router import examples_read as er
from router import patch_read as pr

ROOT = Path(__file__).resolve().parent.parent
LOCAL_OK = re.compile(r"^(core\.(repositoryformatversion|filemode|bare|logallrefupdates|ignorecase)|user\..+|remote\..+|branch\..+)$")
METADATA = {".git", ".gitattributes", ".gitmodules"}          # a path component of this name, at any depth (.gitignore and .github/ are fine)
BAD_MODES = {"120000", "160000"}                              # symlink, submodule
PINS = ("-c", "core.hooksPath=/dev/null", "-c", "core.fsmonitor=false", "-c", "commit.gpgsign=false", "-c", "gc.auto=0",
        "-c", "user.useConfigOnly=true")
DIFF_PINS = rj.SHOW_AS_PACKAGED[:rj.SHOW_AS_PACKAGED.index("show")]
TRAILER = re.compile(r"^(Argus-Job|Argus-Patch-Sha256): (\S+)$", re.M)


class GitFail(Exception):
    pass


def _env(*, global_config=False, index=None):
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_") and k != "EMAIL"}
    env.update(GIT_CONFIG_NOSYSTEM="1", GIT_TERMINAL_PROMPT="0")
    if not global_config:
        env["GIT_CONFIG_GLOBAL"] = os.devnull
    if index:
        env["GIT_INDEX_FILE"] = str(index)
    return env


def run_git(repo, *args, data=None, identity=None, index=None, ok=(0,), timeout=300):
    """One git call: no GIT_* of the caller, no system or global configuration, hooks, fsmonitor, gpg and gc off. Returns stdout bytes."""
    cmd = ["git", *PINS]
    if identity:
        cmd += ["-c", f"user.name={identity[0]}", "-c", f"user.email={identity[1]}"]
    cmd += ["-C", str(repo), *args]
    r = subprocess.run(cmd, input=data, capture_output=True, env=_env(index=index), timeout=timeout)
    if r.returncode not in ok:
        raise GitFail(f"git {' '.join(args[:3])}: {r.stderr.decode(errors='replace').strip()[:300] or 'exit ' + str(r.returncode)}")
    return r.stdout


def _identity(repo):
    """(name, email) as the user's own git configuration says, read once with the global configuration (the one place it is read)."""
    got = []
    for key in ("user.name", "user.email"):
        r = subprocess.run(["git", "-C", str(repo), "config", "--get", key], capture_output=True, text=True, timeout=60,
                           env=_env(global_config=True))
        got.append(r.stdout.strip())
    return tuple(got) if all(got) else None


@contextmanager
def lock_repo(jobs_dir, repo):
    """One apply at a time per repository (two jobs on one repository race the clean-tree and HEAD checks); the file lives with the jobs, never in the repository."""
    key = hashlib.sha256(os.path.realpath(repo).encode()).hexdigest()[:16]
    path = Path(jobs_dir) / f".repo-{key}.lock"
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(path, os.O_RDWR | os.O_CREAT, 0o644)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        os.close(fd)
        raise rj.Refused("another argus apply is running on this repository") from None
    try:
        yield
    finally:
        os.close(fd)


def raw_entries(out):
    """[(old mode, new mode, status, path)] from `git diff-index --raw -z --no-renames`."""
    parts, i, entries = out.split(b"\0"), 0, []
    while i + 1 < len(parts) and parts[i]:
        meta = parts[i].decode().split()
        entries.append((meta[0].lstrip(":"), meta[1], meta[4], parts[i + 1].decode("utf-8", "surrogateescape")))
        i += 2
    return entries


def apply(job_id, read_sha, *, deps, jobs_dir=rj.JOBS, note=None, allow_failed_examples=(), reader=None, queues_dir=None):
    job = rj.open_job(job_id, jobs_dir)
    with job.lock():
        repo = job.data["inputs"]["repo"]
        with lock_repo(jobs_dir, repo):
            return _apply(job, read_sha, deps=deps, note=note, allow=tuple(allow_failed_examples or ()), reader=reader, queues_dir=queues_dir)


def _title(review_dir, job_id):
    """The package's PR title for the commit message; any trouble reading it (no file, not UTF-8, a NUL) is the fallback, never an exception."""
    try:
        text = (Path(review_dir) / "PR.md").read_bytes().decode("utf-8", "replace").replace("\0", "")
        for line in text.splitlines():
            if line.startswith("# "):
                return line[2:].strip()[:120] or f"job {job_id}"
    except (OSError, ValueError):
        pass
    return f"job {job_id}"


def _apply(job, read_sha, *, deps, note, allow=(), reader=None, queues_dir=None):
    def refuse(why):
        raise rj.Refused(f"job {job.id}: {why}; nothing was changed")

    if job.data["state"] != rj.REVIEW_READY:
        raise rj.Refused(f"job {job.id} is {job.data['state']}: only a valid review package is applied")
    rv = rj.last_agent(job)[1]["review"]
    review_dir = Path(rv["dir"])
    # 1. the patch: the one that was reviewed, the one that was read
    try:
        patch = (review_dir / "changes.patch").read_bytes()
        prov = json.loads((review_dir / "provenance.json").read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        refuse(f"the review package cannot be read ({e})")
    sha = hashlib.sha256(patch).hexdigest()
    recorded = rv.get("patch_sha256")
    if not recorded:
        refuse("this job predates the recorded patch sha: apply by hand (status prints the steps)")
    if not (isinstance(read_sha, str) and len(read_sha) >= 12 and sha.startswith(read_sha.lower())):
        refuse(f"--read-sha is not the sha of the patch on disk ({sha[:12]}...): read that patch and give its sha")
    if recorded != sha or (prov.get("patch") or {}).get("sha256") != sha:
        refuse("the patch on disk is not the one the review recorded (job.json and provenance.json must both name it)")
    try:                                    # SPEC_KARTU_SETUJU 5: an `ok` note of a patch reader for these very bytes, before anything is touched
        pr.require_ok(job, rj.last_agent(job)[0], sha, reader)
    except rj.Refused as e:
        refuse(str(e).split(": ", 1)[1] if ": " in str(e) else str(e))
    extra = {"reader": reader} if reader else {}
    listed = sorted(f["path"] for f in (prov.get("patch") or {}).get("files") or [])
    globs = (job.data.get("protected_repo") or {}).get("globs") or []
    hit = [p for p in listed if matches(p, globs)]
    if hit:
        refuse(f"the patch changes files the repository protects (.argus/protected): {hit[:3]}")
    if not patch.strip() or not listed:
        refuse("the patch is empty")
    try:                                    # SPEC_EXAMPLE_GATE: before anything is touched, for the very bytes that will go in
        failed = rj.examples_decision(job, allow, sha=sha)
    except rj.Refused as e:
        refuse(str(e))
    # 2. the repository and git's environment
    repo = Path(job.data["inputs"]["repo"])
    if not (repo / ".git").is_dir():
        refuse(f"{repo} is not a repository with its own .git directory")
    real = repo.resolve()
    if real == ROOT.resolve():
        refuse("the target repository is the Argus checkout itself")
    try:
        top = Path(run_git(repo, "rev-parse", "--show-toplevel").decode().strip()).resolve()
        if top != real:
            refuse(f"git's top level is {top}, not {real}")
        # 3. the local configuration: only keys that cannot make git run something
        keys = [line.split("=", 1)[0] for line in run_git(repo, "config", "--local", "--list").decode().splitlines() if line]
        bad = sorted({k for k in keys if not LOCAL_OK.match(k)})
        if bad:
            refuse(f"the repository's local git configuration has keys this command does not accept ({', '.join(bad[:5])}); apply by hand")
        head = run_git(repo, "rev-parse", "HEAD").decode().strip()
        started = [e for e in job.data.get("log") or [] if e.get("what") == "apply_started"]
        if started and _recovered(job, repo, head, started[-1], sha, patch, deps, note, read_sha, allow, extra):
            return job                          # the commit is already in the repository: only the record was missing, nothing is asked again
        # SPEC_KARTU_SETUJU 5: an item of a PRD queue needs a fresh `ok` note on the numbers. Here, after the healing path and before anything is written
        # (only reads of git were made): an earlier attempt that did not commit gets no pass from its `apply_started` entry.
        res = er.chain(job, job.dir.parent, queues_dir)
        if res["applicable"] and not res["ok"]:
            how = f" (argus examples-read {res['prd_job']} --item {res['item']} --bundle, then --verdict ok ...)" if res["prd_job"] else ""
            how += f"; or a human's written acceptance of the concerns: argus examples-accept {res['prd_job']} --item {res['item']} --show" if res["prd_job"] and res["kind"] == "concerns" else ""
            refuse(f"{res['why']}; apply needs an ok note of the domain reader for an item of a PRD queue{how}")
        if res["applicable"] and res["kind"] == "accepted":          # the log says the numbers passed on a human's acceptance, and why (the acceptance file can be replaced later)
            extra = {**extra, "domain_gate": "accepted", "domain_accept_at": res["accepted"]["at"], "domain_accept_reason": res["accepted"]["reason"]}
        identity = _identity(repo)
        if identity is None:
            refuse("no git identity (user.name and user.email): set them in the repository or globally; none is made up")
        # 4. the repository: clean, on a branch nobody else holds, at the commit the job was taken in at
        dirty = run_git(repo, "status", "--porcelain=v1", "-z", "--untracked-files=all")
        if dirty:
            hint = f" (an earlier apply left changes: git -C {repo} apply -R --index {review_dir / 'changes.patch'})" if started else ""
            refuse(f"the working tree is not clean{hint}")
        ref = run_git(repo, "symbolic-ref", "-q", "HEAD", ok=(0, 1)).decode().strip()
        if not ref.startswith("refs/heads/"):
            refuse("HEAD is not on a branch (detached)")
        held = [ln for ln in run_git(repo, "worktree", "list", "--porcelain").decode().splitlines() if ln == f"branch {ref}"]
        if len(held) > 1:
            refuse(f"the branch {ref[11:]} is checked out in another worktree too")
        if head != job.data["intake"]["commit"]:
            refuse(f"HEAD is {head[:12]}, not the commit the job was taken in at ({job.data['intake']['commit'][:12]})")
        # 5. the patch in a temporary index: paths and modes as git reads them, nothing in the repository touched
        with tempfile.TemporaryDirectory() as tmp:
            index = Path(tmp) / "index"
            run_git(repo, "read-tree", "HEAD", index=index)
            run_git(repo, "apply", "--cached", "--whitespace=nowarn", data=patch, index=index)
            staged = run_git(repo, *DIFF_PINS, "diff", "--cached", "--binary", "--full-index", "--no-renames", "--no-textconv", "--no-color",
                             "--no-ext-diff", index=index)
            entries = raw_entries(run_git(repo, "diff-index", "--cached", "--raw", "-z", "--no-renames", "HEAD", index=index))
    except GitFail as e:
        refuse(str(e))
    except subprocess.TimeoutExpired:
        refuse("git took too long")
    if staged != patch:
        refuse("what git would stage is not the package's patch byte for byte (the patch is not as the package writes it, or a conversion changes it)")
    if not entries:
        refuse("the patch changes nothing")
    for old, new, status, path in entries:
        parts = [c.lower() for c in path.split("/")]
        if old in BAD_MODES or new in BAD_MODES:
            refuse(f"{path}: the patch makes or changes a symlink or a submodule (mode {old}/{new})")
        if METADATA & set(parts) or path.startswith("/") or ".." in parts:
            refuse(f"{path}: a git metadata path is not applied by this command")
    if sorted(p for _, _, _, p in entries) != listed:
        refuse("the files the patch changes are not the files the package lists")
    # 6. the change itself: logged first, applied to the tree and the index, committed
    title = _title(review_dir, job.id)
    job.note(deps, "apply_started", head_before=head, branch=ref[11:], read_sha=read_sha, **extra, **({"examples_failed": failed} if failed else {}))
    commit = None
    try:
        run_git(repo, "apply", "--index", "--whitespace=nowarn", data=patch)
        run_git(repo, "commit", "-q", "--no-verify", "--no-gpg-sign", "-m", title,
                "-m", f"Applied by `argus apply` from the review package of job {job.id}.",
                "-m", f"Argus-Job: {job.id}\nArgus-Patch-Sha256: {sha}", identity=identity)
        commit = run_git(repo, "rev-parse", "HEAD").decode().strip()
    except Exception as e:                                  # not BaseException: a kill is the crash the next call heals
        try:
            now = run_git(repo, "rev-parse", "HEAD").decode().strip()
        except Exception:
            now = None
        if now and now != head:                             # the commit exists (the failure came after it): it is not undone
            commit = now
        else:
            undone = _undo(repo, patch)
            raise rj.Refused(f"job {job.id}: {e}; the change was undone" + ("" if undone else f"; THE TREE IS NOT CLEAN: git -C {repo} status")) from None
    try:
        parent = run_git(repo, "rev-parse", f"{commit}^").decode().strip()
    except Exception:
        parent = None
    if parent != head:
        raise rj.Refused(f"job {job.id}: HEAD moved while the patch went in: the commit {commit[:12]} was made on {str(parent)[:12]}, not on {head[:12]}; "
                         "it stays and the job is not recorded: look at it, then `argus applied` if it is right")
    return _record(job, commit, deps, note, head, ref[11:], read_sha, allow=allow, **extra)


def _undo(repo, patch):
    """Back to a clean tree at HEAD: the patch reversed, and (the tree was clean before, so nothing else is in it) a hard reset if that was not enough."""
    for step in (lambda: run_git(repo, "apply", "-R", "--index", "--whitespace=nowarn", data=patch),
                 lambda: run_git(repo, "reset", "-q", "--hard", "HEAD")):
        try:
            step()
        except (GitFail, subprocess.TimeoutExpired):
            pass
        try:
            if not run_git(repo, "status", "--porcelain=v1", "-z", "--untracked-files=all"):
                return True
        except (GitFail, subprocess.TimeoutExpired):
            return False
    return False


def _record(job, commit, deps, note, head_before, branch, read_sha, allow=(), **extra):
    try:
        return rj._record_applied(job, commit, deps=deps, note=note, method="apply", head_before=head_before, branch=branch,
                                  read_sha=read_sha, require_as_is=True, allow_failed_examples=allow, **extra)
    except rj.Refused as e:
        raise rj.Refused(f"{e} (the commit {commit[:12]} was made and stays; record it by hand with `argus applied {job.id} --commit {commit[:12]}`)") from None


def _recovered(job, repo, head, started, sha, patch, deps, note, read_sha, allow=(), extra=None):
    """A crash after the commit and before the job moved: HEAD is a child of the HEAD before, made by this job from this patch. Records it, makes no second commit."""
    if head == started.get("head_before"):
        return False
    try:
        parent = run_git(repo, "rev-parse", "HEAD^").decode().strip()
        message = run_git(repo, "log", "-1", "--format=%B", "HEAD").decode()
    except (GitFail, subprocess.TimeoutExpired):
        return False
    trailers = dict(TRAILER.findall(message))
    if parent != started.get("head_before") or trailers.get("Argus-Job") != job.id or trailers.get("Argus-Patch-Sha256") != sha:
        return False
    _record(job, head, deps, note, started["head_before"], started.get("branch"), read_sha, allow=allow, recovered=True, **(extra or {}))
    return True
