"""Staging v0 (docs/reviews/SPEC_STAGING_V0.md): a reviewed, applied argus-ledger commit served by one container on this
VM, smoke-tested from the host, with a tested rollback. No model is called here, and no agent has a tool for it.

  argus stage deploy <job>   the commit `applied` recorded for the job (the review package applied as it was): a release
                             (git archive of that commit, read-only), a container with no network on a Unix socket, the
                             smoke test; only when it passes is the previous release stopped
  argus stage rollback       the release that was live before the current one, started and smoke-tested the same way
  argus stage status         what is live, its last smoke test, and what a rollback would start

Every container runs from the checked runtime image (environment ledger_staging) with --network none, a read-only root,
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
import time
from contextlib import contextmanager
from pathlib import Path

from acceptance import intake
from acceptance.workspace import digest, snapshot

from . import job as rj

ROOT = Path(__file__).resolve().parent.parent
STAGING = Path.home() / "argus-staging"
FIXTURE = ROOT / "fixtures" / "staging" / "jobs"
ENVIRONMENT = "ledger_staging"
PREFIX = "argus-staging-ledger-"
LABEL = "argus.staging.release"
HOST = "staging.local"
ENTRY = f'from ledger.api import create_app\n\napp = create_app("/data/jobs", allowed_hosts=["{HOST}"])\n'
RELEASE = re.compile(r"^j[0-9a-z_]{1,40}-[0-9a-f]{12}$")
LIMITS = ["--memory", "256m", "--pids-limit", "64", "--cpus", "1"]
MOUNTS = {"/app": False, "/entry": False, "/data": False, "/run/argus": True}   # destination: writable
SOCKET_WAIT_S = 30
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

    # ---- records ----------------------------------------------------------------------------------------------

    def state(self):
        try:
            s = json.loads(self.state_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {"live": None, "history": []}
        return s if isinstance(s, dict) and isinstance(s.get("history"), list) else {"live": None, "history": []}

    def _save(self, state):
        tmp = self.state_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
        tmp.replace(self.state_path)

    def note(self, event, **detail):
        with open(self.log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps({"at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "event": event, **detail})
                    + "\n")

    def releases(self):
        out = {}
        try:
            lines = self.log_path.read_text(encoding="utf-8").splitlines()
        except OSError:
            return out
        for line in lines:
            try:
                e = json.loads(line)
            except ValueError:
                continue
            if e.get("event") == "built" and isinstance(e.get("release"), str):
                out[e["release"]] = e
        return out

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

    def build(self, job):
        """The release of an applied job: its applied commit, archived read-only. Built once; checked every time."""
        commit, repo = reviewed_commit(job)
        release = f"{job.id}-{commit[:12]}"
        d = self.dir(release)
        known = self.releases().get(release)
        if known is None:
            if d.exists():
                shutil.rmtree(d)                       # left by a build that stopped before its record
            src = d / "src"
            src.mkdir(parents=True)
            archive = intake.git(repo, "archive", "--format=tar", commit)
            r = subprocess.run(["tar", "-x", "-C", str(src)], input=archive, capture_output=True, timeout=120)
            if r.returncode:
                raise Refused(f"the release could not be unpacked: {r.stderr[:200]!r}")
            (d / "entry").mkdir()
            (d / "entry" / "staging_app.py").write_text(ENTRY, encoding="utf-8")
            _read_only(d / "src")
            _read_only(d / "entry")
            known = {"release": release, "job": job.id, "repo": repo, "commit": commit,
                     "src_digest": digest(snapshot(d / "src")), "entry_sha256": _sha(ENTRY.encode()),
                     "archive_sha256": _sha(archive)}
            self.note("built", **known)
        if known["commit"] != commit or digest(snapshot(d / "src")) != known["src_digest"] or \
                _sha((d / "entry" / "staging_app.py").read_bytes()) != known["entry_sha256"]:
            raise Refused(f"release {release} differs from what was built (source, entry or commit changed)")
        return known

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
        rec = self.releases().get(release)
        if rec is None or digest(snapshot(d / "src")) != rec["src_digest"]:
            raise Refused(f"release {release} is not one that was built, or its source changed")
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
            self.remove(name)
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
        if not any(str(o).startswith("no-new-privileges") for o in h.get("SecurityOpt") or []):
            problems.append("no-new-privileges missing")
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
        while not path.exists() and time.monotonic() < deadline:
            time.sleep(0.2)
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
        code, out, err = self.run("logs", "--tail", "200", name)
        d = self.dir(release) / "logs"
        d.mkdir(exist_ok=True)
        (d / f"{time.strftime('%Y%m%dT%H%M%SZ', time.gmtime())}-{what}.txt").write_text(out + err, encoding="utf-8")

    def remove(self, name):
        """Stop and remove one staging container; never any other."""
        if not name.startswith(PREFIX) or not RELEASE.match(name[len(PREFIX):]):
            raise Refused(f"{name!r} is not a staging container")
        self.run("rm", "-f", name)

    def switch(self, release, image, deps, why):
        """Start `release`, smoke-test it, and only then stop the live one. Returns the smoke results."""
        live = self.state()["live"]
        name = self.start(release, image)
        results = self.smoke(release)
        self.logs(name, release, "smoke")
        ok = all(r[1] for r in results)
        self.note("smoke", release=release, ok=ok, results=[list(r) for r in results], why=why)
        if not ok:
            self.remove(name)
            self.note("stopped", release=release, why="smoke_failed")
            failed = "; ".join(f"{c}: {d}" for c, k, d in results if not k)
            raise Refused(f"release {release} failed its smoke test ({failed}); it was stopped, "
                          + (f"{live} is still live" if live else "nothing is live"))
        if live and live != release:
            self.logs(PREFIX + live, live, "stop")
            self.remove(PREFIX + live)
            self.note("stopped", release=live, why=f"{why}: {release} is live")
        return results


def _get(sock_path, host, url):
    conn = http.client.HTTPConnection("localhost", timeout=10)
    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    s.settimeout(10)
    dfd = os.open(Path(sock_path).parent, os.O_RDONLY | os.O_DIRECTORY)
    try:                                   # a socket path is at most 107 bytes: connect through the directory's fd
        s.connect(f"/proc/self/fd/{dfd}/{Path(sock_path).name}")
    finally:
        os.close(dfd)
    conn.sock = s
    try:
        conn.request("GET", url, headers={"Host": host})
        r = conn.getresponse()
        return r.status, r.read(1_000_000)
    finally:
        conn.close()


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


def runtime_image(cfg):
    image, problem = rj.environment_pin(cfg, ENVIRONMENT)
    if problem:
        raise Refused(f"the staging runtime image cannot be used: {problem}")
    return image


def _confirm(deps, text):
    if deps.assume_yes:
        deps.echo(text + "\n(--yes: approved in chat; no [y/N] asked)")
        return
    if not deps.confirm(text):
        raise Refused("not confirmed; nothing was changed")


def deploy(job_id, *, cfg, deps, jobs_dir=rj.JOBS, staging=None):
    st = staging or Staging()
    job = rj.open_job(job_id, jobs_dir)
    image = runtime_image(cfg)
    with st.lock():
        rec = st.build(job)
        state = st.state()
        if state["live"] == rec["release"]:
            raise Refused(f"release {rec['release']} is already live")
        text = "\n".join([f"== staging deploy (job {job.id}) ==",
                          f"release {rec['release']}: {rec['repo']} at {rec['commit'][:12]} (applied as reviewed)",
                          f"image {ENVIRONMENT} {image[:19]}; no network, read-only, Unix socket; synthetic data",
                          f"live now: {state['live'] or 'nothing'}; rollback after this: {state['live'] or 'none'}",
                          "staging only: no production, no users, no credentials"])
        _confirm(deps, text)
        st.switch(rec["release"], image, deps, "deploy")
        state["history"] = [r for r in state["history"] if r != rec["release"]] + [rec["release"]]
        state["live"] = rec["release"]
        st._save(state)
        st.note("live", release=rec["release"], by="deploy")
    with job.lock():
        job.note(deps, "staged", release=rec["release"])
    return rec["release"]


def rollback(*, cfg, deps, staging=None):
    st = staging or Staging()
    image = runtime_image(cfg)
    with st.lock():
        state = st.state()
        if not state["live"] or len(state["history"]) < 2:
            raise Refused("there is no earlier release to roll back to")
        current, previous = state["history"][-1], state["history"][-2]
        text = "\n".join(["== staging rollback ==", f"live now: {current}", f"start again: {previous}",
                          "staging only: no production, no users, no credentials"])
        _confirm(deps, text)
        st.switch(previous, image, deps, "rollback")
        state["history"], state["live"] = state["history"][:-1], previous
        st._save(state)
        st.note("live", release=previous, by="rollback", replaced=current)
    return previous


def status(*, staging=None):
    st = staging or Staging()
    state, rels = st.state(), st.releases()
    live = state["live"]
    lines = [f"staging live: {live or 'nothing'}"]
    if live and live in rels:
        lines.append(f"  job {rels[live]['job']}, commit {rels[live]['commit'][:12]}")
    smokes = []
    try:
        for line in st.log_path.read_text(encoding="utf-8").splitlines():
            e = json.loads(line)
            if e.get("event") == "smoke" and e.get("release") == live:
                smokes.append(e)
    except (OSError, ValueError):
        pass
    if smokes:
        lines.append(f"  last smoke: {'pass' if smokes[-1]['ok'] else 'FAIL'} at {smokes[-1]['at']}")
    prev = state["history"][-2] if len(state["history"]) >= 2 else None
    lines.append(f"rollback would start: {prev or 'nothing (no earlier release)'}")
    return "\n".join(lines)
