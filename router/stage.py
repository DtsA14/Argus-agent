"""Staging v0 (docs/reviews/SPEC_STAGING_V0.md): a reviewed, applied argus-ledger commit served by one container on this
VM, smoke-tested from the host, with a tested rollback. No model is called here, and no agent has a tool for it.

  argus stage deploy <job>   the commit `applied` recorded for the job (the review package applied as it was): a release
                             (git archive of that commit, read-only), a container with no network on a Unix socket, the
                             smoke test; only when it passes is the previous release stopped
  argus stage rollback       the release that was live before the current one, started and smoke-tested the same way
  argus stage status         what is live, its last smoke test, and what a rollback would start
  argus stage check <job> --env E   the job's commit's own tests in sandbox environment E (no model): the evidence a
                             deploy on that environment's staging runtime needs (SPEC_DEP_UPGRADE_V0 U2)

A release is a commit on one runtime (SPEC_DEP_UPGRADE_V0 U3): ledger_staging by default, or another staging runtime of
RUNTIMES once `stage check` passed for that commit in its paired sandbox environment. The release records the runtime's
image, and a rollback starts the earlier release on the image it recorded, never on today's default.

Every container runs from the checked runtime image of its release with --network none, a read-only root,
no capabilities, no-new-privileges, this user's uid (not root) and limits; the release's source, the harness's entry
module and the synthetic data (fixtures/staging/jobs) are mounted read-only, and only the socket directory is writable.
`docker inspect` must show exactly that before the smoke test runs. Only containers named argus-staging-ledger-* and
labelled with their release are ever stopped. Staging only: production needs its own approval (Atha, 2026-10-29).
"""
import fcntl
import hashlib
import http.client
import json
import os
import re
import shutil
import socket
import subprocess
import tempfile
import time
from contextlib import contextmanager
from pathlib import Path

from acceptance import intake
from acceptance.workspace import digest, snapshot

from acceptance import validation as va
from tools import sandbox as sb

from . import job as rj

ROOT = Path(__file__).resolve().parent.parent
STAGING = Path.home() / "argus-staging"
FIXTURE = ROOT / "fixtures" / "staging" / "jobs"
ENVIRONMENT = "ledger_staging"
# SPEC_DEP_UPGRADE_V0 U3: each staging runtime and the sandbox environment whose `stage check` a commit must have passed
# before it runs on that runtime. The default one needs none (its releases are those staging v0 deployed).
RUNTIMES = {"ledger_staging": None, "ledger_staging_up1": "ledger_py312_up1"}
# The one image staging v0 ever ran (SPEC_STAGING_V0 §6): its releases recorded no image, so this is theirs.
V0_IMAGE = "sha256:4ab2ff53a34f46ccecde0c8030298bcb37be41d7c565847590de4875a5578f5a"
CHECK_ARGV = ["python3", "-I", "-B", "-m", "pytest", *va.PYTEST_FIXED, "-W", "error::DeprecationWarning"]
CHECK_TIMEOUT_S = 600
PREFIX = "argus-staging-ledger-"
LABEL = "argus.staging.release"
HOST = "staging.local"
ENTRY = f'from ledger.api import create_app\n\napp = create_app("/data/jobs", allowed_hosts=["{HOST}"])\n'
RELEASE = re.compile(r"^j[0-9a-z_]{1,40}-[0-9a-f]{12}(\.[a-z0-9]{1,12})?$")   # .<runtime> unless the default
SUFFIX = re.compile(r"^[a-z0-9]{1,12}$")
LIMITS = ["--memory", "256m", "--pids-limit", "64", "--cpus", "1"]
WANT_LIMITS = {"Memory": 256 * 1024 * 1024, "PidsLimit": 64, "NanoCpus": 1_000_000_000}   # LIMITS as docker shows them
MOUNTS = {"/app": False, "/entry": False, "/data": False, "/run/argus": True}   # destination: writable
SOCKET_WAIT_S = 30
LOGS_TIMEOUT_S = 15                                        # copying logs is a convenience: never worth a long wait
STATE_PROBLEM = "staging state: "                          # how status() starts when state.json cannot be used
# SPEC_STAGING_V0 S4: what the synthetic jobs must give (fixtures/staging/README); a release that reads them wrongly fails
SMOKE = [(HOST, "/summary", 200, lambda b: json.loads(b) == {"jobs": 2, "cost_nano": 2500000, "cost_usd": "0.0025",
                                                               "skipped": 0}),
         (HOST, "/jobs", 200, lambda b: [j.get("job") or j.get("id") for j in json.loads(b)]
          == ["jstaging_done", "jstaging_failed"]),
         (HOST, "/ui", 200, lambda b: b.lstrip().lower().startswith(b"<!doctype html")),
         ("evil.example", "/summary", 400, lambda b: b"Invalid host header" in b)]


def docker(*args, timeout=120):
    """One docker command (argv only, never a shell) -> (returncode, stdout, stderr)."""
    r = subprocess.run(["docker", *args], capture_output=True, text=True, timeout=timeout)
    return r.returncode, r.stdout, r.stderr


class Refused(rj.Refused):
    pass


class Staging:
    """The staging area: <base>/releases/<release>/{src,entry,data,sock,logs}, state.json and releases.jsonl."""

    def __init__(self, base=STAGING, run=docker, fixture=FIXTURE, wait_s=SOCKET_WAIT_S):
        self.base, self.run, self.fixture, self.wait_s = Path(base), run, Path(fixture), wait_s
        self.state_path, self.log_path = self.base / "state.json", self.base / "releases.jsonl"
        self.checks_path = self.base / "env_checks.jsonl"

    # ---- records ----------------------------------------------------------------------------------------------

    def state(self):
        """{"live", "history"}; nothing live only when there is no state file yet. An unreadable or malformed one is
        Refused: read as "nothing live" it would make reconcile() stop the live release and lose the rollback history."""
        try:
            if not os.path.lexists(self.state_path):   # a dangling symlink is not "no state"
                return {"live": None, "history": []}
            s = json.loads(self.state_path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as e:
            s, why = None, f"{type(e).__name__}: {e}"
        else:
            why = "not a staging state"
        if isinstance(s, dict) and isinstance(s.get("history"), list) and \
                all(isinstance(r, str) for r in s["history"]) and \
                (s.get("live") is None or (s["history"] and s["live"] == s["history"][-1])):
            return s
        raise Refused(f"{self.state_path} is unreadable ({why}); nothing was changed: restore it by hand "
                      f"(releases.jsonl has every built, live and stopped event)")

    def _save(self, state):
        tmp = self.state_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
        tmp.replace(self.state_path)

    def note(self, event, **detail):
        with open(self.log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps({"at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "event": event, **detail})
                    + "\n")

    def releases(self):
        return {e["release"]: e for e in _jsonl(self.log_path)
                if e.get("event") == "built" and isinstance(e.get("release"), str)}

    @contextmanager
    def lock(self):
        self.base.mkdir(parents=True, exist_ok=True)
        fd = os.open(self.base / ".lock", os.O_RDWR | os.O_CREAT, 0o600)
        try:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                raise Refused("another staging command is running; nothing was changed") from None
            yield
        finally:
            os.close(fd)

    # ---- a release --------------------------------------------------------------------------------------------

    def dir(self, release):
        if not RELEASE.match(release):
            raise Refused(f"{release!r} is not a release name")
        return self.base / "releases" / release

    def build(self, job, runtime=ENVIRONMENT, image=None):
        """The release of an applied job on `runtime` (whose image is `image`): its applied commit, archived read-only.
        Built once; checked every time."""
        commit, repo = reviewed_commit(job)
        release = release_name(job, commit, runtime)
        d = self.dir(release)
        known = self.releases().get(release)
        if known is None:
            if d.exists():                             # left by a build that stopped before its record
                _writable(d)
                shutil.rmtree(d)
            archive = unpack(repo, commit, d / "src")
            (d / "entry").mkdir()
            (d / "entry" / "staging_app.py").write_text(ENTRY, encoding="utf-8")
            _read_only(d / "entry")
            known = {"release": release, "job": job.id, "repo": repo, "commit": commit,
                     "src_digest": digest(snapshot(d / "src")), "entry_sha256": _sha(ENTRY.encode()),
                     "archive_sha256": _sha(archive), "runtime": runtime, "image": image}
            self.note("built", **known)
        if known["commit"] != commit:
            raise Refused(f"release {release} differs from what was built (commit changed)")
        self.verify(release)
        return known

    def verify(self, release):
        """The built record of a release whose source and entry are still as they were built, or Refused."""
        d, rec = self.dir(release), self.releases().get(release)
        if rec is None:
            raise Refused(f"release {release} is not one that was built")
        try:
            same = digest(snapshot(d / "src")) == rec["src_digest"] and \
                _sha((d / "entry" / "staging_app.py").read_bytes()) == rec["entry_sha256"] == _sha(ENTRY.encode())
        except OSError:
            same = False
        if not same:
            raise Refused(f"release {release} differs from what was built (source or entry changed)")
        return rec

    def checks(self):
        return _jsonl(self.checks_path)

    def record_check(self, rec):
        """Append one check record; its own lock (not the staging lock), so a check never blocks a deploy."""
        self.base.mkdir(parents=True, exist_ok=True)
        with open(self.checks_path, "a", encoding="utf-8") as f:
            fcntl.flock(f, fcntl.LOCK_EX)
            f.write(json.dumps(rec) + "\n")

    def tested(self, commit, runtime, cfg):
        """The passed `stage check` a deploy of `commit` on `runtime` (one of RUNTIMES, as runtime_image ensured) needs
        (U3), or Refused; None for the default."""
        environment = RUNTIMES[runtime]
        if environment is None:
            return None
        image, problem = rj.environment_pin(cfg, environment)
        if problem:
            raise Refused(f"sandbox environment {environment} cannot be used: {problem}")
        runtime_now = runtime_image(cfg, runtime)
        last = [e for e in self.checks() if e.get("commit") == commit and e.get("environment") == environment
                and e.get("image") == image and e.get("runtime_image") == runtime_now]
        if not last or last[-1].get("ok") is not True:
            raise Refused(f"commit {commit[:12]} has no passed `argus stage check` in {environment} (image "
                          f"{image[:19]}, for {runtime} {runtime_now[:19]}): it does not run on {runtime}"
                          + (f" (last check: {last[-1].get('why')})" if last else ""))
        return last[-1]

    def _fresh_data(self, d):
        data = d / "data"
        if data.exists():
            _writable(data)
            shutil.rmtree(data)
        shutil.copytree(self.fixture, data / "jobs")
        _read_only(data)

    def start(self, release, image):
        """Start a release's container; it is refused (and removed) unless docker shows the isolation of S3."""
        d = self.dir(release)
        self.verify(release)
        self._fresh_data(d)
        sock = d / "sock"
        if sock.exists():
            shutil.rmtree(sock)
        sock.mkdir(mode=0o700)
        name = PREFIX + release
        self.remove(name)                               # a container of this release left by an earlier try
        code, out, err = self.run(
            "run", "-d", "--name", name, "--label", f"{LABEL}={release}", "--network", "none", "--read-only",
            "--cap-drop", "ALL", "--security-opt", "no-new-privileges", "--user", f"{os.getuid()}:{os.getgid()}",
            *LIMITS, "-e", "PYTHONDONTWRITEBYTECODE=1", "-e", "PYTHONPATH=/app",
            "-v", f"{d / 'src'}:/app:ro", "-v", f"{d / 'entry'}:/entry:ro", "-v", f"{d / 'data'}:/data:ro",
            "-v", f"{sock}:/run/argus", "-w", "/app", image,
            "python3", "-m", "uvicorn", "--app-dir", "/entry", "staging_app:app", "--uds", "/run/argus/app.sock",
            "--workers", "1")
        if code:
            raise Refused(f"the container did not start: {err.strip()[:300]}")
        problems = self.isolation_problems(name, release, image, d)
        if problems:
            self.discard(name, "not isolated")
            raise Refused(f"container {name} is not isolated as required: " + "; ".join(problems))
        return name

    def isolation_problems(self, name, release, image, d):
        code, out, _ = self.run("inspect", name)
        try:
            c = json.loads(out)[0] if code == 0 else None
        except (ValueError, IndexError):
            c = None
        if not isinstance(c, dict):
            return ["docker inspect failed"]
        h, cfg, problems = c.get("HostConfig") or {}, c.get("Config") or {}, []
        if h.get("NetworkMode") != "none":
            problems.append(f"network {h.get('NetworkMode')!r}")
        if h.get("ReadonlyRootfs") is not True:
            problems.append("root file system is writable")
        if "ALL" not in (h.get("CapDrop") or []) or h.get("CapAdd"):
            problems.append("capabilities not all dropped")
        if not any(str(o) in ("no-new-privileges", "no-new-privileges:true", "no-new-privileges=true")
                   for o in h.get("SecurityOpt") or []) or \
                any("no-new-privileges" in str(o) and "false" in str(o) for o in h.get("SecurityOpt") or []):
            problems.append("no-new-privileges missing")
        for key, want_v in WANT_LIMITS.items():
            if h.get(key) != want_v:
                problems.append(f"limit {key} is {h.get(key)!r}, not {want_v}")
        if h.get("Privileged"):
            problems.append("privileged")
        user = str(cfg.get("User") or "")
        if user.split(":")[0] in ("", "0", "root"):
            problems.append(f"user {user!r} is root")
        if c.get("Image") != image:
            problems.append(f"image {c.get('Image')} is not {image}")
        if (cfg.get("Labels") or {}).get(LABEL) != release:
            problems.append("release label missing")
        want = {"/app": d / "src", "/entry": d / "entry", "/data": d / "data", "/run/argus": d / "sock"}
        mounts = {m.get("Destination"): m for m in c.get("Mounts") or []}
        if set(mounts) != set(want):
            problems.append(f"mounts {sorted(mounts)}")
        for dest, m in mounts.items():
            if dest in want and (Path(m.get("Source", "")) != want[dest] or bool(m.get("RW")) != MOUNTS[dest]):
                problems.append(f"mount {dest} is not {want[dest]} ({'rw' if MOUNTS[dest] else 'ro'})")
        return problems

    def smoke(self, release):
        """[(check, ok, detail)] of S4, through the release's socket from this host."""
        path = self.dir(release) / "sock" / "app.sock"
        deadline = time.monotonic() + self.wait_s
        while True:                                    # until the app listens: the file exists from bind(), before
            left = deadline - time.monotonic()         # listen(), and a connect then is refused
            if left <= 0:
                return [(f"{host} {url} -> {status}", False, f"the socket did not accept a connection within "
                         f"{self.wait_s}s") for host, url, status, _ in SMOKE]
            try:
                _connect(path, timeout=min(left, 10)).close()
                break
            except OSError:
                time.sleep(min(0.2, max(left, 0)))
        out = []
        for host, url, status, body_ok in SMOKE:
            check = f"{host} {url} -> {status}"
            try:
                got, body = _get(path, host, url)
                ok = got == status and bool(body_ok(body))
                out.append((check, ok, f"{got} {body[:120]!r}"))
            except Exception as e:                      # noqa: BLE001  (any failure is a failed check, with its type)
                out.append((check, False, f"{type(e).__name__}: {str(e)[:120]}"))
        return out

    def logs(self, name, release, what):
        code, out, err = self.run("logs", "--tail", "200", name, timeout=LOGS_TIMEOUT_S)
        d = self.dir(release) / "logs"
        d.mkdir(exist_ok=True)
        (d / f"{time.strftime('%Y%m%dT%H%M%SZ', time.gmtime())}-{what}.txt").write_text(out + err, encoding="utf-8")

    def remove(self, name):
        """Stop and remove one staging container; never any other."""
        if not name.startswith(PREFIX) or not RELEASE.match(name[len(PREFIX):]):
            raise Refused(f"{name!r} is not a staging container")
        code, _, err = self.run("rm", "-f", name)
        if code and self.run("inspect", "--type", "container", name)[0] == 0:
            raise Refused(f"container {name} could not be removed ({err.strip()[:200]}); it may still be running")

    def discard(self, name, why):
        """remove() on a path that already has its answer (a failure being raised, or a release already live): a
        container that cannot be removed is noted, not raised; the next deploy or rollback reconciles it."""
        try:
            self.remove(name)
            return True
        except Refused as e:
            try:
                self.note("stop_failed", release=name[len(PREFIX):], why=why, error=str(e)[:300])
            except OSError:
                pass
            return False

    def running(self):
        """Names of the staging containers docker runs now (by label; only names this module would give)."""
        code, out, _ = self.run("ps", "--filter", f"label={LABEL}", "--format", "{{.Names}}")
        return [n for n in out.split() if n.startswith(PREFIX) and RELEASE.match(n[len(PREFIX):])] if code == 0 else []

    def reconcile(self):
        """Stop every staging container that is not the live release (left by a command that stopped half-way)."""
        live = self.state()["live"]
        for name in self.running():
            if name != PREFIX + str(live):
                self.remove(name)
                self.note("stopped", release=name[len(PREFIX):], why="not the live release (reconciled)")

    def switch(self, release, image, deps, why, commit_state):
        """Start `release` and smoke-test it; only when it passes, record it live (commit_state) and stop the one that
        was live. A failure before the record removes the new container: the live one is never left without a record."""
        live = self.state()["live"]
        name = self.start(release, image)
        try:
            results = self.smoke(release)
        except BaseException:
            self.discard(name, "smoke test stopped")
            raise
        try:
            self.logs(name, release, "smoke")
        except Exception:                              # noqa: BLE001  (the logs are a convenience, never a verdict)
            pass
        ok = all(r[1] for r in results)
        self.note("smoke", release=release, ok=ok, results=[list(r) for r in results], why=why)
        if not ok:
            stopped = self.discard(name, "smoke_failed")
            if stopped:
                self.note("stopped", release=release, why="smoke_failed")
            failed = "; ".join(f"{c}: {d}" for c, k, d in results if not k)
            raise Refused(f"release {release} failed its smoke test ({failed}); "
                          + ("it was stopped, " if stopped else "it could not be removed (the next command stops it), ")
                          + (f"{live} is still live" if live else "nothing is live"))
        try:
            commit_state()
        except BaseException:
            if self.discard(name, "record failed"):
                try:                                   # the live event may be in the log already: close it
                    self.note("stopped", release=release, why="record failed; not live")
                except OSError:
                    pass
            raise
        if live and live != release:
            try:
                self.logs(PREFIX + live, live, "stop")
            except Exception:                          # noqa: BLE001  (a hung `docker logs` too: the stop is not optional)
                pass                                   # the logs are a convenience; the stop is not
            if self.discard(PREFIX + live, f"{why}: {release} is live"):
                self.note("stopped", release=live, why=f"{why}: {release} is live")
            else:
                deps.echo(f"warning: {live} could not be stopped; {release} is live, and the next staging command "
                          f"stops {live}")
        return results


def _connect(sock_path, timeout=10):
    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    s.settimeout(timeout)
    try:
        dfd = os.open(Path(sock_path).parent, os.O_RDONLY | os.O_DIRECTORY)
        try:                               # a socket path is at most 107 bytes: connect through the directory's fd
            s.connect(f"/proc/self/fd/{dfd}/{Path(sock_path).name}")
        finally:
            os.close(dfd)
    except BaseException:
        s.close()
        raise
    return s


def _get(sock_path, host, url):
    conn = http.client.HTTPConnection("localhost", timeout=10)
    conn.sock = _connect(sock_path)
    try:
        conn.request("GET", url, headers={"Host": host})
        r = conn.getresponse()
        return r.status, r.read(1_000_000)
    finally:
        conn.close()


def _jsonl(path):
    """The objects of a JSONL file; a line cut by a crash, or one that is not an object, is skipped."""
    try:
        lines = Path(path).read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    out = []
    for line in lines:
        try:
            e = json.loads(line)
        except ValueError:
            continue
        if isinstance(e, dict):
            out.append(e)
    return out


def _sha(data):
    return hashlib.sha256(data).hexdigest()


def _read_only(path):
    for p in sorted(Path(path).rglob("*"), reverse=True):
        if not p.is_symlink():
            p.chmod(0o555 if p.is_dir() else 0o444)
    Path(path).chmod(0o555)


def _writable(path):
    Path(path).chmod(0o755)
    for p in Path(path).rglob("*"):
        if not p.is_symlink():
            p.chmod(0o755 if p.is_dir() else 0o644)


def release_name(job, commit, runtime=ENVIRONMENT):
    """<job>-<commit12>, plus .<suffix> on a runtime other than the default (ledger_staging_up1 -> .up1)."""
    base = f"{job.id}-{commit[:12]}"
    return base if runtime == ENVIRONMENT else f"{base}.{runtime.removeprefix(ENVIRONMENT + '_')}"


def unpack(repo, commit, src):
    """git archive of `commit` unpacked into `src` (made here, left read-only), checked against the commit's tree."""
    Path(src).mkdir(parents=True)
    archive = intake.git(repo, "archive", "--format=tar", commit)
    r = subprocess.run(["tar", "-x", "-C", str(src)], input=archive, capture_output=True, timeout=120)
    if r.returncode:
        raise Refused(f"the release could not be unpacked: {r.stderr[:200]!r}")
    diff = tree_differences(repo, commit, src)
    if diff:                                           # e.g. .gitattributes export-ignore or export-subst
        raise Refused(f"the archive of {commit[:12]} is not the commit's tree: " + "; ".join(diff[:5]))
    _read_only(src)
    return archive


def _git_blob_sha(data):
    return hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest()


def tree_differences(repo, commit, src):
    """What differs between the commit's tree (git ls-tree) and the unpacked archive: a missing or extra path, or a
    file whose content is not the commit's blob. Submodules (commits) are not part of an archive and not compared."""
    out = intake.git(repo, "ls-tree", "-r", "-z", "--full-tree", commit).decode("utf-8", "surrogateescape")
    want = {}
    for entry in filter(None, out.split("\0")):
        meta, path = entry.split("\t", 1)
        mode, kind, sha = meta.split()
        if kind == "blob":
            want[path] = (mode, sha)
    have = {}
    for p in Path(src).rglob("*"):
        rel = p.relative_to(src).as_posix()
        if p.is_symlink():
            have[rel] = ("120000", _git_blob_sha(os.readlink(p).encode("utf-8", "surrogateescape")))
        elif p.is_file():
            have[rel] = ("file", _git_blob_sha(p.read_bytes()))
    diff = [f"missing {p}" for p in sorted(set(want) - set(have))] + [f"extra {p}" for p in sorted(set(have) - set(want))]
    for p in sorted(set(want) & set(have)):
        mode, sha = want[p]
        if have[p][1] != sha or (mode == "120000") != (have[p][0] == "120000"):
            diff.append(f"content of {p}")
    return diff


def reviewed_commit(job):
    """(commit, repo) of an APPLIED job whose commit holds the review package's patch as it was (SPEC_STAGING_V0 3.1:
    only reviewed artefacts go to staging)."""
    if job.data["state"] != rj.APPLIED:
        raise Refused(f"job {job.id} is {job.data['state']}: only an APPLIED job is deployed to staging")
    why = rj._why(job)
    if why.get("as_is") is not True:
        raise Refused(f"job {job.id} was applied with changes that differ from the reviewed patch (as_is "
                      f"{why.get('as_is')!r}); only the reviewed patch is deployed")
    commit = why.get("commit")
    if not (isinstance(commit, str) and re.fullmatch(r"[0-9a-f]{40}", commit)):
        raise Refused(f"job {job.id} has no applied commit")
    return commit, job.data["inputs"]["repo"]


def runtime_image(cfg, runtime=ENVIRONMENT):
    if runtime not in RUNTIMES:
        raise Refused(f"{runtime!r} is not a staging runtime (known: {sorted(RUNTIMES)})")
    image, problem = rj.environment_pin(cfg, runtime)
    if problem:
        raise Refused(f"the staging runtime image cannot be used: {problem}")
    return image


def image_changed(rec, runtime, image):
    """Refused when a release was built for another image than its runtime resolves to now (the runtime itself is part
    of the release's name). A release from before SPEC_DEP_UPGRADE_V0 recorded no image: staging v0 ran V0_IMAGE."""
    built = rec.get("image") or (V0_IMAGE if runtime == ENVIRONMENT else None)
    if built != image:
        raise Refused(f"release {rec['release']} was built for image {str(built)[:19]} of {runtime}, which now "
                      f"resolves to {str(image)[:19]}; nothing was changed")


def release_image(cfg, rec):
    """(runtime, image) a built release starts on: its recorded runtime, still resolving to its recorded image."""
    runtime = rec.get("runtime", ENVIRONMENT)
    image = runtime_image(cfg, runtime)
    image_changed(rec, runtime, image)
    return runtime, image


def _confirm(deps, text):
    if deps.assume_yes:
        deps.echo(text + "\n(--yes: approved in chat; no [y/N] asked)")
        return
    if not deps.confirm(text):
        raise Refused("not confirmed; nothing was changed")


def deploy(job_id, *, cfg, deps, jobs_dir=rj.JOBS, staging=None, runtime=ENVIRONMENT):
    st = staging or Staging()
    job = rj.open_job(job_id, jobs_dir)
    image = runtime_image(cfg, runtime)
    with st.lock():
        st.reconcile()
        commit, repo = reviewed_commit(job)
        release = release_name(job, commit, runtime)
        state = st.state()
        if state["live"] == release:
            raise Refused(f"release {release} is already live")
        check = st.tested(commit, runtime, cfg)
        known = st.releases().get(release)
        if known is not None:
            image_changed(known, runtime, image)
        text = "\n".join([f"== staging deploy (job {job.id}) ==",
                          f"release {release}: {repo} at {commit[:12]} (applied as reviewed)",
                          f"image {runtime} {image[:19]}; no network, read-only, Unix socket; synthetic data",
                          *([f"tested: stage check passed in {check['environment']} at {check['at']} "
                             f"({check['tests_run']} tests)"] if check else []),
                          f"live now: {state['live'] or 'nothing'}; rollback after this: {state['live'] or 'none'}",
                          "staging only: no production, no users, no credentials"])
        _confirm(deps, text)
        rec = st.build(job, runtime, image)

        def record():
            state["history"] = [r for r in state["history"] if r != release] + [release]
            state["live"] = release
            st.note("live", release=release, by="deploy")
            st._save(state)                            # last: a failure before it leaves the old release live
        st.switch(release, image, deps, "deploy", record)
    with job.lock():
        job.note(deps, "staged", release=rec["release"])
    return rec["release"]


def rollback(*, cfg, deps, staging=None):
    st = staging or Staging()
    with st.lock():
        st.reconcile()
        state = st.state()
        if not state["live"] or len(state["history"]) < 2:
            raise Refused("there is no earlier release to roll back to")
        current, previous = state["history"][-1], state["history"][-2]
        rec = st.releases().get(previous)
        if rec is None:
            raise Refused(f"release {previous} is not one that was built")
        runtime, image = release_image(cfg, rec)       # the image it ran on, not today's default (U3)
        text = "\n".join(["== staging rollback ==", f"live now: {current}",
                          f"start again: {previous} on {runtime} {image[:19]}",
                          "staging only: no production, no users, no credentials"])
        _confirm(deps, text)

        def record():
            state["history"], state["live"] = state["history"][:-1], previous
            st.note("live", release=previous, by="rollback", replaced=current)
            st._save(state)                            # last: a failure before it leaves the current release live
        st.switch(previous, image, deps, "rollback", record)
    return previous


def status(*, staging=None):
    st = staging or Staging()
    try:
        state = st.state()
    except Refused as e:
        return f"{STATE_PROBLEM}{e}"
    rels = st.releases()
    live = state["live"]
    lines = [f"staging live: {live or 'nothing'}"]
    if live and live in rels:
        lines.append(f"  job {rels[live]['job']}, commit {rels[live]['commit'][:12]}, runtime "
                     f"{rels[live].get('runtime', ENVIRONMENT)}")
    smokes = [e for e in _jsonl(st.log_path) if e.get("event") == "smoke" and e.get("release") == live]
    if smokes:
        lines.append(f"  last smoke: {'pass' if smokes[-1]['ok'] else 'FAIL'} at {smokes[-1]['at']}")
    prev = state["history"][-2] if len(state["history"]) >= 2 else None
    lines.append(f"rollback would start: {prev or 'nothing (no earlier release)'}"
                 + (f" on {rels[prev].get('runtime', ENVIRONMENT)}" if prev in rels else ""))
    return "\n".join(lines)


def check(job_id, environment, *, cfg, jobs_dir=rj.JOBS, staging=None, run=sb.run_command):
    """SPEC_DEP_UPGRADE_V0 U2: the applied commit's own test suite in sandbox environment `environment` (the sandbox
    flags of a validation; workspace read-only), deprecation warnings as errors. Passed only with exit code 0, a
    consistent pytest summary, at least one test, none failed or skipped, and the run not cut short. Recorded in
    env_checks.jsonl, passed, failed or stopped, with the image of the paired runtime it covers. It trusts the reviewed
    test code: a conftest in the commit could report a pass (the same code runs in staging anyway). No model."""
    st = staging or Staging()
    if environment not in {e for e in RUNTIMES.values() if e}:
        raise Refused(f"{environment!r} is not the sandbox environment of a staging runtime "
                      f"({sorted(e for e in RUNTIMES.values() if e)})")
    job = rj.open_job(job_id, jobs_dir)
    commit, repo = reviewed_commit(job)
    image, problem = rj.environment_pin(cfg, environment)
    if problem:
        raise Refused(f"sandbox environment {environment} cannot be used: {problem}")
    runtime = next(r for r, e in RUNTIMES.items() if e == environment)
    runtime_now = runtime_image(cfg, runtime)              # the pair a passed check covers (U3)
    rec = {"at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "job": job.id, "commit": commit,
           "environment": environment, "image": image, "runtime": runtime, "runtime_image": runtime_now}
    (st.base / "checks").mkdir(parents=True, exist_ok=True)
    d = Path(tempfile.mkdtemp(prefix=f"{commit[:12]}.{environment}.", dir=st.base / "checks"))
    try:                                                   # no staging lock: a rollback never waits for a check
        unpack(repo, commit, d / "src")
        sandbox = {**(cfg.get("sandbox") or {}), "environment": environment, "timeout_s": CHECK_TIMEOUT_S}
        r = run(CHECK_ARGV, workdir=d / "src", cfg=sandbox)
    except BaseException as e:                             # stopped: recorded as not passed, then raised
        st.record_check({**rec, "ok": False, "why": f"stopped: {type(e).__name__}: {str(e)[:200]}", "tests_run": None,
                         "failed": [], "output_tail": ""})
        raise
    finally:
        _writable(d)
        shutil.rmtree(d)
    parsed = va.parse_pytest(r.get("stdout") or "")
    problems = [why for bad, why in (
        (r.get("timed_out"), "timed out"), (r.get("output_limit_exceeded"), "output limit exceeded"),
        (r.get("cleanup_failed"), "sandbox container removal not confirmed"),
        (r.get("truncated"), "output truncated"), (r.get("exit_code") != 0, f"exit code {r.get('exit_code')}"),
        (parsed["outcome"] != "OK", f"pytest outcome {parsed['outcome']}"),
        (not parsed["consistent"], "pytest output inconsistent"),
        (not parsed["tests_run"], "no test ran"), (parsed["skipped"], f"{parsed['skipped']} skipped")) if bad]
    rec.update(ok=not problems, why="; ".join(problems) or None, tests_run=parsed["tests_run"],
               failed=sorted(n for n, x in parsed["tests"].items() if x in ("FAIL", "ERROR"))[:20],
               output_tail=((r.get("stdout") or "") + (r.get("stderr") or ""))[-1500:])
    st.record_check(rec)
    return rec


for _runtime in RUNTIMES:                                  # every runtime gives valid release names (U3)
    assert _runtime == ENVIRONMENT or (_runtime.startswith(ENVIRONMENT + "_")
                                       and SUFFIX.match(_runtime.removeprefix(ENVIRONMENT + "_"))), _runtime
