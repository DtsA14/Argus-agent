"""SPEC_STAGING_V0: staging deploys only a reviewed, applied commit, in a container with no network and a read-only root
on a Unix socket; the smoke test runs from the host; a failed smoke test leaves the previous release live; rollback
starts the previous release and smoke-tests it. The docker tests need the checked ledger_staging image; without it they
are skipped with "SANDBOX NOT AVAILABLE", which scripts/verify.sh does not count as passing."""
import http.server
import json
import os
import socket
import socketserver
import subprocess
import sys
import threading
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from router import job as rj  # noqa: E402
from router import stage as sg  # noqa: E402
from router import stage_data as sd  # noqa: E402
from runner import load_config  # noqa: E402

pytestmark = pytest.mark.skipif(sys.platform == "win32", reason="Unix sockets and docker on the VM")

# Tests run containers in a namespace of their own (Atha 2026-10-30): even if the staging directory label were not
# checked, a test could not list or remove a container of the real staging.
TEST_PREFIX, TEST_LABEL = "argus-test-ledger-", "argus.test.release"


def Staging(base, **kw):  # noqa: N802  (stands for sg.Staging in every test)
    return sg.Staging(base, prefix=TEST_PREFIX, label=TEST_LABEL, **kw)


def owner(a, base, up):
    """A fake docker's answer to Staging.owner(): `base`'s label for a name in `up`, else no such container."""
    if a[-1] in up:
        return 0, str(Path(base).resolve()), ""
    return 1, "", f"Error: No such container: {a[-1]}"


def is_owner(a):
    return a[0] == "inspect" and any(sg.BASE_LABEL in str(x) for x in a)

SUMMARY = {"jobs": 2, "cost_nano": 2500000, "cost_usd": "0.0025", "skipped": 0}

# A small stand-in for argus-ledger (same create_app shape), good or broken; the real app is in its own repository.
APP = '''import json, os
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from starlette.middleware.trustedhost import TrustedHostMiddleware

BROKEN = {broken}


def _jobs(d):
    out = []
    for name in sorted(os.listdir(d)):
        job = json.load(open(os.path.join(d, name, "job.json")))
        nano = 0
        for run in os.listdir(os.path.join(d, name, "runs")):
            started, final = {{}}, {{}}
            for line in open(os.path.join(d, name, "runs", run, "events.jsonl")):
                e = json.loads(line)
                if e["event"] == "llm_call_started":
                    started[e["call_id"]] = e["worst_usd_nano"]
                elif e["event"] == "llm_call":
                    final[e["call_id"]] = e["usd_nano"]
            nano += sum(final.get(c, w) for c, w in started.items())
        out.append({{"job": job["job"], "nano": nano}})
    return out


def create_app(jobs_dir, allowed_hosts=None):
    app = FastAPI()

    @app.get("/summary")
    def summary():
        jobs = _jobs(jobs_dir)
        nano = sum(j["nano"] for j in jobs) + (1 if BROKEN else 0)
        return {{"jobs": len(jobs), "cost_nano": nano, "cost_usd": "%.4f" % (nano / 1e9), "skipped": 0}}

    @app.get("/jobs")
    def jobs():
        return [{{"job": j["job"]}} for j in _jobs(jobs_dir)]

    @app.get("/ui")
    def ui():
        return HTMLResponse("<!DOCTYPE html><html><body>jobs</body></html>")

    if allowed_hosts is not None:
        app.add_middleware(TrustedHostMiddleware, allowed_hosts=list(allowed_hosts), www_redirect=False)
    return app
'''


def git(cwd, *args):
    return subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t", *args], cwd=cwd, check=True,
                          capture_output=True, text=True).stdout.strip()


@pytest.fixture
def repo(tmp_path):
    """A target repository with two commits: a good app, then a broken one (its summary is off by one nano-dollar)."""
    r = tmp_path / "repo"
    (r / "ledger").mkdir(parents=True)
    (r / "ledger" / "__init__.py").write_text("")
    git(tmp_path, "init", "-q", str(r))
    commits = {}
    for name, broken in (("good", False), ("broken", True), ("good2", False)):
        (r / "ledger" / "api.py").write_text(APP.format(broken=broken) + f"# {name}\n")
        git(r, "add", "-A")
        git(r, "commit", "-qm", name)
        commits[name] = git(r, "rev-parse", "HEAD")
    return r, commits


def applied_job(jobs, job_id, repo, commit, *, state=rj.APPLIED, as_is=True):
    d = jobs / job_id
    d.mkdir(parents=True)
    log = [{"at": "2026-10-29T00:00:00Z", "what": "state", "old": rj.REVIEW_READY, "new": state, "commit": commit,
            "as_is": as_is, "patch_sha256": "0" * 64}]
    (d / "job.json").write_text(json.dumps({"job": job_id, "kind": "code", "state": state, "inputs": {"repo": str(repo)},
                                            "stages": {}, "log": log}))
    return job_id


class Said:
    def __init__(self):
        self.lines = []

    def __call__(self, text):
        self.lines.append(text)


def with_fixture(st):
    """The synthetic jobs published as the staging data snapshot, as `argus stage refresh` publishes the real ones."""
    sd.refresh(sg.FIXTURE, st.data)
    return st


def deps(yes=True):
    return rj.Deps(confirm=lambda text: False, assume_yes=yes, echo=Said(), clock=lambda: "2026-10-29T00:00:00Z")


# ---- without docker -------------------------------------------------------------------------------------------

@pytest.mark.parametrize("state, as_is, why", [
    (rj.REVIEW_READY, True, "only an APPLIED job"),
    (rj.APPLIED, False, "differ from the reviewed patch"),
    (rj.APPLIED, None, "differ from the reviewed patch"),
])
def test_only_an_applied_job_with_its_reviewed_patch_is_deployed(tmp_path, repo, state, as_is, why):
    r, c = repo
    jid = applied_job(tmp_path / "jobs", "jx", r, c["good"], state=state, as_is=as_is)
    st = Staging(tmp_path / "staging", run=lambda *a, **k: pytest.fail("docker must not run"))
    with pytest.raises(sg.Refused, match=why):
        st.build(rj.open_job(jid, tmp_path / "jobs"))
    assert not (tmp_path / "staging" / "releases").exists()


def test_a_release_whose_source_changed_after_the_build_is_refused(tmp_path, repo):
    r, c = repo
    jid = applied_job(tmp_path / "jobs", "jx", r, c["good"])
    st = Staging(tmp_path / "staging", run=lambda *a, **k: pytest.fail("docker must not run"))
    rec = st.build(rj.open_job(jid, tmp_path / "jobs"))
    assert rec["commit"] == c["good"] and "# good" in (st.dir(rec["release"]) / "src" / "ledger" / "api.py").read_text()
    api = st.dir(rec["release"]) / "src" / "ledger" / "api.py"
    api.chmod(0o644)
    api.write_text("changed")
    with pytest.raises(sg.Refused, match="differs from what was built"):
        st.build(rj.open_job(jid, tmp_path / "jobs"))
    with pytest.raises(sg.Refused, match="source or entry changed"):
        st.start(rec["release"], "sha256:x")


@pytest.mark.parametrize("name", ["athena-api", "argus-staging-ledger-", "argus-staging-ledger-x; rm -rf /",
                                  "argus-staging-ledgerj1-0123456789ab"])
def test_only_staging_containers_are_ever_removed(tmp_path, name):
    calls = []
    st = Staging(tmp_path, run=lambda *a, **k: calls.append(a) or (0, "", ""))
    with pytest.raises(sg.Refused, match="not a staging container"):
        st.remove(name)
    assert calls == []


def inspect(d, release, image, **over):
    h = {"NetworkMode": "none", "ReadonlyRootfs": True, "CapDrop": ["ALL"], "CapAdd": None,
         "SecurityOpt": ["no-new-privileges"], "Privileged": False, **sg.WANT_LIMITS}
    cfg = {"User": "1001:1001", "Labels": {TEST_LABEL: release, sg.BASE_LABEL: str(d.parent.parent.resolve())}}
    mounts = [{"Destination": "/app", "Source": str(d / "src"), "RW": False},
              {"Destination": "/entry", "Source": str(d / "entry"), "RW": False},
              {"Destination": "/data", "Source": str(d.parent.parent / "data" / "pub"), "RW": False},
              {"Destination": "/run/argus", "Source": str(d / "sock"), "RW": True}]
    c = {"HostConfig": h, "Config": cfg, "Image": image, "Mounts": mounts}
    for k, v in over.items():
        where, key = k.split("__")
        if where == "Mounts":
            c["Mounts"] = v
        else:
            {"h": h, "cfg": cfg}[where][key] = v
    return c


@pytest.mark.parametrize("over, problem", [
    ({}, None),
    ({"h__NetworkMode": "bridge"}, "network"),
    ({"h__ReadonlyRootfs": False}, "writable"),
    ({"h__CapDrop": []}, "capabilities"),
    ({"h__CapAdd": ["NET_ADMIN"]}, "capabilities"),
    ({"h__SecurityOpt": []}, "no-new-privileges"),
    ({"h__Privileged": True}, "privileged"),
    ({"cfg__User": "0"}, "root"),
    ({"cfg__User": ""}, "root"),
    ({"cfg__Labels": {}}, "label"),
    ({"cfg__Labels": {TEST_LABEL: "jx-0123456789ab"}}, "staging directory label"),
    ({"cfg__Labels": {TEST_LABEL: "jx-0123456789ab", sg.BASE_LABEL: "/home/ubuntu/argus-staging"}},
     "staging directory label"),
    ({"Mounts__": []}, "mounts"),
])
def test_a_container_without_the_required_isolation_is_refused(tmp_path, over, problem):
    release, image = "jx-0123456789ab", "sha256:" + "a" * 64
    d = tmp_path / "releases" / release
    c = inspect(d, release, image, **over)
    st = Staging(tmp_path, run=lambda *a, **k: (0, json.dumps([c]), ""))
    got = st.isolation_problems("n", release, image, d)
    assert (got == []) if problem is None else any(problem in p for p in got), got


def test_a_writable_source_mount_or_another_image_is_refused(tmp_path):
    release, image = "jx-0123456789ab", "sha256:" + "a" * 64
    d = tmp_path / "releases" / release
    c = inspect(d, release, image)
    c["Mounts"][0]["RW"] = True
    c["Image"] = "sha256:" + "b" * 64
    st = Staging(tmp_path, run=lambda *a, **k: (0, json.dumps([c]), ""))
    got = st.isolation_problems("n", release, image, d)
    assert any("/app" in p for p in got) and any("image" in p for p in got)


class UnixHTTP(socketserver.ThreadingMixIn, socketserver.UnixStreamServer):
    daemon_threads = True


def serve(path, answers):
    class H(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            status, body = answers(self.headers.get("Host"), self.path)
            self.send_response(status)
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *a):
            pass

        def address_string(self):
            return "unix"
    dfd = os.open(Path(path).parent, os.O_RDONLY | os.O_DIRECTORY)
    try:                                   # bound through the directory's fd: tmp paths pass the 107-byte limit
        srv = UnixHTTP(f"/proc/self/fd/{dfd}/{Path(path).name}", H)
    finally:
        os.close(dfd)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


def good(host, path):
    if host != sg.HOST:
        return 400, b"Invalid host header"
    return {"/summary": (200, json.dumps(SUMMARY).encode()),
            "/jobs": (200, json.dumps([{"job": "jstaging_done"}, {"job": "jstaging_failed"}]).encode()),
            "/ui": (200, b"<!DOCTYPE html><html></html>")}.get(path, (404, b""))


@pytest.mark.parametrize("answers, failed", [
    (good, []),
    (lambda h, p: (200, json.dumps({**SUMMARY, "cost_nano": 1}).encode()) if p == "/summary" and h == sg.HOST
     else good(h, p), ["staging.local /summary -> 200"]),
    (lambda h, p: (307, b"") if h != sg.HOST else good(h, p), ["evil.example /summary -> 400"]),
    (lambda h, p: (500, b"") if p == "/ui" else good(h, p), ["staging.local /ui -> 200"]),
])
def test_the_smoke_test_checks_every_answer(tmp_path, answers, failed):
    st = with_fixture(Staging(tmp_path, wait_s=1))
    st.container_pid = lambda release: os.getpid()                 # the test's own server is the peer
    d = st.dir("jx-0123456789ab") / "sock"
    d.mkdir(parents=True)
    srv = serve(d / "app.sock", answers)
    try:
        results = st.smoke("jx-0123456789ab")
    finally:
        srv.shutdown()
    assert [c for c, ok, _ in results if not ok] == failed


def test_a_smoke_test_without_a_socket_fails_every_check(tmp_path):
    st = Staging(tmp_path, wait_s=0.2)
    st.container_pid = lambda release: os.getpid()
    (st.dir("jx-0123456789ab") / "sock").mkdir(parents=True)
    assert not any(ok for _, ok, _ in st.smoke("jx-0123456789ab"))


def only_ps(*a, **k):
    """docker as a read-only `ps` with nothing running; any other command fails the test."""
    return (0, "", "") if a and a[0] == "ps" else pytest.fail(f"docker {a[:1]} must not run")


def test_rollback_without_an_earlier_release_is_refused(tmp_path, monkeypatch):
    monkeypatch.setattr(sg, "runtime_image", lambda cfg, runtime=sg.ENVIRONMENT: "sha256:" + "a" * 64)
    st = Staging(tmp_path, run=only_ps)
    with pytest.raises(sg.Refused, match="no earlier release"):
        sg.rollback(cfg=None, deps=deps(), staging=st)


def test_the_deploy_is_confirmed_before_anything_starts(tmp_path, repo, monkeypatch):
    r, c = repo
    jid = applied_job(tmp_path / "jobs", "jx", r, c["good"])
    monkeypatch.setattr(sg, "runtime_image", lambda cfg, runtime=sg.ENVIRONMENT: "sha256:" + "a" * 64)
    st = Staging(tmp_path / "staging", run=only_ps)
    with pytest.raises(sg.Refused, match="not confirmed"):
        sg.deploy(jid, cfg=None, deps=deps(yes=False), jobs_dir=tmp_path / "jobs", staging=st)
    assert st.state()["live"] is None and st.releases() == {} and not (tmp_path / "staging" / "releases").exists()


def test_no_role_has_a_staging_tool():
    from codetask import tools as tl
    cfg = load_config()
    names = set(tl.GATED) | {t for ts in (cfg.get("tools") or {}).values() for t in ts}
    assert not [n for n in names if "stage" in n.lower() or "deploy" in n.lower()]
    src = Path(sg.__file__).read_text()
    assert "LLMCaller" not in src and "build_chat_model" not in src


# ---- with docker: the real runtime image ------------------------------------------------------------------------

@pytest.fixture(scope="module")
def image():
    from approve_draft import sandbox_cfg
    cfg = load_config()
    cfg["sandbox"] = sandbox_cfg()
    try:
        return sg.runtime_image(cfg)
    except sg.Refused as e:
        pytest.skip(f"SANDBOX NOT AVAILABLE: {e}")


@pytest.fixture
def staging(tmp_path, image, monkeypatch):
    monkeypatch.setattr(sg, "runtime_image", lambda cfg, runtime=sg.ENVIRONMENT: image)
    st = with_fixture(Staging(tmp_path / "staging"))
    yield st
    for release in st.releases():
        st.run("rm", "-f", TEST_PREFIX + release)


def test_deploy_a_failed_smoke_test_and_rollback_in_the_real_container(tmp_path, repo, staging, image):
    r, c = repo
    jobs = tmp_path / "jobs"
    good, broken, good2 = (applied_job(jobs, f"j{n}", r, c[n]) for n in ("good", "broken", "good2"))
    d = deps()

    first = sg.deploy(good, cfg=None, deps=d, jobs_dir=jobs, staging=staging)
    assert staging.state() == {"live": first, "history": [first]}
    name = TEST_PREFIX + first
    h = json.loads(staging.run("inspect", name)[1])[0]["HostConfig"]
    assert h["NetworkMode"] == "none" and h["ReadonlyRootfs"] is True
    assert "staged" in [e["what"] for e in rj.open_job(good, jobs).data["log"]]

    # a release that fails its smoke test is stopped; the first stays live and still answers
    with pytest.raises(sg.Refused, match="failed its smoke test.*still live"):
        sg.deploy(broken, cfg=None, deps=d, jobs_dir=jobs, staging=staging)
    assert staging.state()["live"] == first and all(ok for _, ok, _ in staging.smoke(first))
    running = staging.run("ps", "--format", "{{.Names}}")[1].split()
    assert name in running and not [n for n in running if broken in n]

    second = sg.deploy(good2, cfg=None, deps=d, jobs_dir=jobs, staging=staging)
    running = staging.run("ps", "--format", "{{.Names}}")[1].split()
    assert TEST_PREFIX + second in running and name not in running
    assert staging.state()["history"] == [first, second]

    back = sg.rollback(cfg=None, deps=d, staging=staging)
    assert back == first and staging.state() == {"live": first, "history": [first]}
    running = staging.run("ps", "--format", "{{.Names}}")[1].split()
    assert name in running and TEST_PREFIX + second not in running
    assert all(ok for _, ok, _ in staging.smoke(first))
    assert list((staging.dir(first) / "logs").iterdir())
    with pytest.raises(sg.Refused, match="no earlier release"):
        sg.rollback(cfg=None, deps=d, staging=staging)
    assert "staging live: " + first in sg.status(staging=staging)


def test_the_container_cannot_reach_the_network_or_write_its_source(tmp_path, repo, staging, image):
    r, c = repo
    jid = applied_job(tmp_path / "jobs", "jg", r, c["good"])
    rel = sg.deploy(jid, cfg=None, deps=deps(), jobs_dir=tmp_path / "jobs", staging=staging)
    probe = ("import socket, pathlib\n"
             "try:\n    socket.create_connection(('1.1.1.1', 53), timeout=2); print('NET')\n"
             "except OSError: print('nonet')\n"
             "try:\n    pathlib.Path('/app/x').write_text('x'); print('WROTE')\n"
             "except OSError: print('ro')\n"
             "try:\n    pathlib.Path('/etc/x').write_text('x'); print('WROTE')\n"
             "except OSError: print('ro')\n")
    code, out, err = staging.run("exec", TEST_PREFIX + rel, "python3", "-c", probe)
    assert code == 0 and out.split() == ["nonet", "ro", "ro"], (out, err)


# ---- review fixes -------------------------------------------------------------------------------------------------

def test_the_fixture_jobs_are_tracked_by_git():
    out = subprocess.run(["git", "ls-files", "fixtures/staging/jobs"], cwd=sg.ROOT, capture_output=True, text=True).stdout
    assert len(out.split()) == 5 and "runs/jstaging_done-a1/events.jsonl" in out


def test_a_build_left_read_only_without_its_record_is_rebuilt(tmp_path, repo):
    r, c = repo
    jid = applied_job(tmp_path / "jobs", "jx", r, c["good"])
    st = Staging(tmp_path / "staging", run=only_ps)
    rec = st.build(rj.open_job(jid, tmp_path / "jobs"))
    st.log_path.unlink()                               # the record is lost; the read-only directory is left
    again = st.build(rj.open_job(jid, tmp_path / "jobs"))
    assert again["src_digest"] == rec["src_digest"]


def test_a_changed_entry_is_refused_also_on_rollback(tmp_path, repo):
    r, c = repo
    jid = applied_job(tmp_path / "jobs", "jx", r, c["good"])
    st = Staging(tmp_path / "staging", run=only_ps)
    rec = st.build(rj.open_job(jid, tmp_path / "jobs"))
    entry = st.dir(rec["release"]) / "entry" / "staging_app.py"
    entry.chmod(0o644)
    entry.write_text('from ledger.api import create_app\napp = create_app("/data/jobs")\n')
    with pytest.raises(sg.Refused, match="source or entry changed"):
        st.start(rec["release"], "sha256:x")


def test_an_archive_that_is_not_the_commits_tree_is_refused(tmp_path, repo):
    r, c = repo
    (r / ".gitattributes").write_text("ledger/api.py export-ignore\n")
    git(r, "add", "-A")
    git(r, "commit", "-qm", "ignore api in archives")
    jid = applied_job(tmp_path / "jobs", "jx", r, git(r, "rev-parse", "HEAD"))
    st = Staging(tmp_path / "staging", run=only_ps)
    with pytest.raises(sg.Refused, match="missing ledger/api.py"):
        st.build(rj.open_job(jid, tmp_path / "jobs"))
    assert st.releases() == {}


@pytest.mark.parametrize("opts", [["no-new-privileges:false"], ["no-new-privileges=false"],
                                  ["no-new-privileges", "no-new-privileges:false"], ["no-new-privileges:maybe"]])
def test_no_new_privileges_switched_off_is_refused(tmp_path, opts):
    release, image = "jx-0123456789ab", "sha256:" + "a" * 64
    d = tmp_path / "releases" / release
    c = inspect(d, release, image, h__SecurityOpt=opts)
    st = Staging(tmp_path, run=lambda *a, **k: (0, json.dumps([c]), ""))
    assert any("no-new-privileges" in p for p in st.isolation_problems("n", release, image, d))


@pytest.mark.parametrize("key, value", [("Memory", 0), ("PidsLimit", -1), ("NanoCpus", 0)])
def test_a_container_without_its_limits_is_refused(tmp_path, key, value):
    release, image = "jx-0123456789ab", "sha256:" + "a" * 64
    d = tmp_path / "releases" / release
    c = inspect(d, release, image, **{f"h__{key}": value})
    st = Staging(tmp_path, run=lambda *a, **k: (0, json.dumps([c]), ""))
    assert any(f"limit {key}" in p for p in st.isolation_problems("n", release, image, d))


def test_a_staging_container_that_is_not_live_is_stopped_before_a_deploy(tmp_path, repo, monkeypatch):
    r, c = repo
    jid = applied_job(tmp_path / "jobs", "jx", r, c["good"])
    monkeypatch.setattr(sg, "runtime_image", lambda cfg, runtime=sg.ENVIRONMENT: "sha256:" + "a" * 64)
    calls = []

    def run(*a, **k):
        calls.append(a)
        if a[0] == "ps":
            return 0, TEST_PREFIX + "jold-0123456789ab\nathena-api\n", ""
        if is_owner(a):
            return owner(a, tmp_path / "staging", {TEST_PREFIX + "jold-0123456789ab"})
        return 0, "", ""
    st = Staging(tmp_path / "staging", run=run)
    with pytest.raises(sg.Refused, match="not confirmed"):
        sg.deploy(jid, cfg=None, deps=deps(yes=False), jobs_dir=tmp_path / "jobs", staging=st)
    assert ("rm", "-f", TEST_PREFIX + "jold-0123456789ab") in calls
    assert not [a for a in calls if "athena-api" in a]


def test_status_reads_past_a_cut_line(tmp_path):
    st = Staging(tmp_path)
    st.base.mkdir(parents=True, exist_ok=True)
    st._save({"live": "jx-0123456789ab", "history": ["jx-0123456789ab"]})
    st.log_path.write_text('{"event": "smoke", "release": "jx-0123456789ab", "ok": false, "at": "t1"}\n{"event": "sm\n'
                           '{"event": "smoke", "release": "jx-0123456789ab", "ok": true, "at": "t2"}\n')
    assert "last smoke: pass at t2" in sg.status(staging=st)


def test_a_failure_to_record_the_new_release_stops_it_and_keeps_the_old_live(tmp_path, repo, staging, image, monkeypatch):
    r, c = repo
    jobs = tmp_path / "jobs"
    first = sg.deploy(applied_job(jobs, "ja", r, c["good"]), cfg=None, deps=deps(), jobs_dir=jobs, staging=staging)

    def broken_save(state):
        raise OSError("disk full")
    monkeypatch.setattr(staging, "_save", broken_save)
    with pytest.raises(OSError, match="disk full"):
        sg.deploy(applied_job(jobs, "jb", r, c["good2"]), cfg=None, deps=deps(), jobs_dir=jobs, staging=staging)
    assert staging.running() == [TEST_PREFIX + first] and staging.state()["live"] == first


# ---- SPEC_DEP_UPGRADE_V0: a release is a commit on one runtime; rollback restores the image; check before a new runtime --

IMAGES = {"ledger_staging": "sha256:" + "1" * 64, "ledger_staging_up1": "sha256:" + "2" * 64}
SANDBOX_UP1 = "sha256:" + "5" * 64


@pytest.fixture
def two_runtimes(tmp_path, monkeypatch):
    """Staging whose switch only records (release, image) and commits the state: no docker, no socket."""
    images = {**IMAGES, "ledger_py312_up1": SANDBOX_UP1}             # every name resolves; RUNTIMES decides
    monkeypatch.setattr(rj, "environment_pin", lambda cfg, name, root=None: (images.get(name), None)
                        if name in images else (None, f"no {name}"))
    st = Staging(tmp_path / "staging", run=only_ps)
    started = []

    def switch(release, image, deps_, why, commit_state):
        started.append((release, image))
        commit_state()
    monkeypatch.setattr(st, "switch", switch)
    return st, images, started


def passed_check(st, commit, ok=True, image=SANDBOX_UP1, environment="ledger_py312_up1",
                 runtime_image=IMAGES["ledger_staging_up1"]):
    st.record_check({"at": "t", "commit": commit, "environment": environment, "image": image, "ok": ok,
                     "runtime_image": runtime_image, "why": None if ok else "exit code 1", "tests_run": 3})


def test_rollback_starts_the_earlier_release_on_the_image_it_recorded(tmp_path, repo, two_runtimes):
    r, c = repo
    st, images, started = two_runtimes
    jobs = tmp_path / "jobs"
    first = sg.deploy(applied_job(jobs, "ja", r, c["good"]), cfg={}, deps=deps(), jobs_dir=jobs, staging=st)
    passed_check(st, c["good2"])
    second = sg.deploy(applied_job(jobs, "jb", r, c["good2"]), cfg={}, deps=deps(), jobs_dir=jobs, staging=st,
                       runtime="ledger_staging_up1")
    assert second.endswith(".up1") and sg.RELEASE.match(second)
    assert st.releases()[second]["image"] == IMAGES["ledger_staging_up1"]
    assert "on ledger_staging" in sg.status(staging=st) and "runtime ledger_staging_up1" in sg.status(staging=st)
    third = sg.deploy(applied_job(jobs, "jc", r, c["broken"]), cfg={}, deps=deps(), jobs_dir=jobs, staging=st)
    assert sg.rollback(cfg={}, deps=deps(), staging=st) == second      # back onto the upgraded runtime
    assert sg.rollback(cfg={}, deps=deps(), staging=st) == first       # and back again onto the old one
    one, two = IMAGES["ledger_staging"], IMAGES["ledger_staging_up1"]
    assert started == [(first, one), (second, two), (third, one), (second, two), (first, one)]


def test_a_release_whose_image_changed_since_its_build_is_refused(tmp_path, repo, two_runtimes):
    r, c = repo
    st, images, started = two_runtimes
    jobs = tmp_path / "jobs"
    first = sg.deploy(applied_job(jobs, "ja", r, c["good"]), cfg={}, deps=deps(), jobs_dir=jobs, staging=st)
    passed_check(st, c["good2"])
    sg.deploy(applied_job(jobs, "jb", r, c["good2"]), cfg={}, deps=deps(), jobs_dir=jobs, staging=st,
              runtime="ledger_staging_up1")
    images["ledger_staging"] = "sha256:" + "3" * 64                   # the default runtime was rebuilt
    with pytest.raises(sg.Refused, match="was built for image"):
        sg.rollback(cfg={}, deps=deps(), staging=st)
    assert len(started) == 2 and st.state()["history"][-1] != first
    with pytest.raises(sg.Refused, match="was built for image"):    # nor deployed again on the new image
        sg.deploy("ja", cfg={}, deps=deps(), jobs_dir=jobs, staging=st)
    assert len(started) == 2


@pytest.mark.parametrize("record", [None, {"ok": False}, {"image": "sha256:" + "9" * 64},
                                    {"environment": "ledger_py312"}, {"commit": "other"},
                                    {"runtime_image": "sha256:" + "8" * 64}])
def test_a_new_runtime_needs_a_passed_check_of_that_commit(tmp_path, repo, two_runtimes, record):
    r, c = repo
    st, images, started = two_runtimes
    jobs = tmp_path / "jobs"
    jid = applied_job(jobs, "jb", r, c["good2"])
    if record is not None:
        passed_check(st, **{"commit": c["good2"], **record})
    with pytest.raises(sg.Refused, match="no passed `argus stage check`"):
        sg.deploy(jid, cfg={}, deps=deps(), jobs_dir=jobs, staging=st, runtime="ledger_staging_up1")
    assert started == [] and st.releases() == {} and not (st.base / "releases").exists()
    passed_check(st, c["good2"])                                      # a later passed check is what counts
    sg.deploy(jid, cfg={}, deps=deps(), jobs_dir=jobs, staging=st, runtime="ledger_staging_up1")
    assert len(started) == 1


@pytest.mark.parametrize("runtime", ["ledger_py312_up1", "argus", "ledger_staging_up2"])
def test_only_a_staging_runtime_is_deployed_on(tmp_path, repo, two_runtimes, runtime):
    r, c = repo
    st, images, started = two_runtimes
    images[runtime] = "sha256:" + "4" * 64                             # it would resolve, but is not a runtime
    jid = applied_job(tmp_path / "jobs", "jb", r, c["good"])
    with pytest.raises(sg.Refused, match="not a staging runtime"):
        sg.deploy(jid, cfg={}, deps=deps(), jobs_dir=tmp_path / "jobs", staging=st, runtime=runtime)
    assert started == []


@pytest.mark.parametrize("runtime", ["ledger_py312_up1", "argus"])
def test_the_runtime_image_is_only_a_staging_runtimes(runtime):
    with pytest.raises(sg.Refused, match="not a staging runtime"):
        sg.runtime_image({}, runtime)


def test_a_check_runs_only_in_a_paired_environment_that_resolves(tmp_path, repo, monkeypatch):
    r, c = repo
    jid = applied_job(tmp_path / "jobs", "jx", r, c["good"])
    st = Staging(tmp_path / "staging")
    never = lambda *a, **k: pytest.fail("the sandbox must not run")      # noqa: E731
    with pytest.raises(sg.Refused, match="not the sandbox environment of a staging runtime"):
        sg.check(jid, "argus", cfg={}, jobs_dir=tmp_path / "jobs", staging=st, run=never)
    monkeypatch.setattr(rj, "environment_pin", lambda cfg, name, root=None:
                        (None, "no image") if name == "ledger_py312_up1" else ("sha256:" + "2" * 64, None))
    with pytest.raises(sg.Refused, match="sandbox environment ledger_py312_up1 cannot be used: no image"):
        sg.check(jid, "ledger_py312_up1", cfg={}, jobs_dir=tmp_path / "jobs", staging=st, run=never)
    assert st.checks() == []


# ---- with docker: the checked up1 images ----------------------------------------------------------------------------

TESTS = '''import sys
import warnings
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))   # as argus-ledger's tests do (python -I)

from fastapi.testclient import TestClient  # noqa: E402
from ledger.api import create_app  # noqa: E402


def test_ui():
    assert TestClient(create_app("/nonexistent")).get("/ui").status_code == 200
{extra}'''


@pytest.fixture(scope="module")
def real_cfg():
    from approve_draft import sandbox_cfg
    cfg = load_config()
    cfg["sandbox"] = sandbox_cfg()
    try:
        for runtime in sg.RUNTIMES:
            sg.runtime_image(cfg, runtime)
    except sg.Refused as e:
        pytest.skip(f"SANDBOX NOT AVAILABLE: {e}")
    image, problem = rj.environment_pin(cfg, "ledger_py312_up1")
    if problem:
        pytest.skip(f"SANDBOX NOT AVAILABLE: {problem}")
    return cfg


@pytest.fixture
def tested_repo(tmp_path):
    """good: the app and a passing test; deprecated: a test that warns DeprecationWarning; good2: passing again."""
    r = tmp_path / "trepo"
    (r / "ledger").mkdir(parents=True)
    (r / "tests").mkdir()
    (r / "ledger" / "__init__.py").write_text("")
    git(tmp_path, "init", "-q", str(r))
    commits = {}
    for name, extra in (("good", ""), ("deprecated", "\n\ndef test_old():\n    warnings.warn('old', "
                                                     "DeprecationWarning)\n"),
                        ("skipped", "\n\nimport pytest  # noqa: E402\n\n\n@pytest.mark.skip\ndef test_later():\n"
                                    "    pass\n"), ("good2", "")):
        (r / "ledger" / "api.py").write_text(APP.format(broken=False) + f"# {name}\n")
        (r / "tests" / "test_app.py").write_text(TESTS.format(extra=extra))
        git(r, "add", "-A")
        git(r, "commit", "-qm", name)
        commits[name] = git(r, "rev-parse", "HEAD")
    return r, commits


def test_a_check_passes_only_without_failures_or_deprecations(tmp_path, tested_repo, real_cfg):
    r, c = tested_repo
    jobs, st = tmp_path / "jobs", with_fixture(Staging(tmp_path / "staging"))
    ok = sg.check(applied_job(jobs, "jg", r, c["good"]), "ledger_py312_up1", cfg=real_cfg, jobs_dir=jobs, staging=st)
    assert ok["ok"] is True and ok["tests_run"] == 1, json.dumps(ok)
    bad = sg.check(applied_job(jobs, "jd", r, c["deprecated"]), "ledger_py312_up1", cfg=real_cfg, jobs_dir=jobs,
                   staging=st)
    assert bad["ok"] is False and bad["failed"] == ["tests/test_app.py::test_old"], bad
    skipped = sg.check(applied_job(jobs, "js", r, c["skipped"]), "ledger_py312_up1", cfg=real_cfg, jobs_dir=jobs,
                       staging=st)
    assert skipped["ok"] is False and "1 skipped" in skipped["why"], skipped
    assert [e["ok"] for e in st.checks()] == [True, False, False]
    assert not list((st.base / "checks").iterdir())


def test_rollback_across_an_upgrade_in_the_real_containers(tmp_path, tested_repo, real_cfg):
    r, c = tested_repo
    jobs, st = tmp_path / "jobs", with_fixture(Staging(tmp_path / "staging"))
    try:
        first = sg.deploy(applied_job(jobs, "ja", r, c["good"]), cfg=real_cfg, deps=deps(), jobs_dir=jobs, staging=st)
        jb = applied_job(jobs, "jb", r, c["good2"])
        assert sg.check(jb, "ledger_py312_up1", cfg=real_cfg, jobs_dir=jobs, staging=st)["ok"]
        second = sg.deploy(jb, cfg=real_cfg, deps=deps(), jobs_dir=jobs, staging=st, runtime="ledger_staging_up1")
        image = lambda rel: json.loads(st.run("inspect", TEST_PREFIX + rel)[1])[0]["Image"]   # noqa: E731
        assert image(second) == sg.runtime_image(real_cfg, "ledger_staging_up1") and st.running() == [TEST_PREFIX + second]
        assert sg.rollback(cfg=real_cfg, deps=deps(), staging=st) == first
        assert image(first) == sg.runtime_image(real_cfg) and st.running() == [TEST_PREFIX + first]
        assert all(ok for _, ok, _ in st.smoke(first))
    finally:
        for release in st.releases():
            st.run("rm", "-f", TEST_PREFIX + release)


def test_a_release_from_staging_v0_rolls_back_only_onto_the_v0_image(tmp_path, repo, two_runtimes):
    r, c = repo
    st, images, started = two_runtimes
    jobs = tmp_path / "jobs"
    images["ledger_staging"] = sg.V0_IMAGE
    first = sg.deploy(applied_job(jobs, "ja", r, c["good"]), cfg={}, deps=deps(), jobs_dir=jobs, staging=st)
    lines = st.log_path.read_text().splitlines()                # as staging v0 wrote it: no runtime, no image
    old = json.loads(lines[0])
    del old["runtime"], old["image"]
    st.log_path.write_text("\n".join([json.dumps(old)] + lines[1:]) + "\n")
    passed_check(st, c["good2"])
    sg.deploy(applied_job(jobs, "jb", r, c["good2"]), cfg={}, deps=deps(), jobs_dir=jobs, staging=st,
              runtime="ledger_staging_up1")
    images["ledger_staging"] = "sha256:" + "3" * 64              # ledger_staging rebuilt since
    with pytest.raises(sg.Refused, match="was built for image sha256:4ab2ff53"):
        sg.rollback(cfg={}, deps=deps(), staging=st)
    images["ledger_staging"] = sg.V0_IMAGE
    assert sg.rollback(cfg={}, deps=deps(), staging=st) == first and started[-1] == (first, sg.V0_IMAGE)


def pytest_output(tmp_path, body):
    """Real verbose pytest output (the validation's flags) of a one-file suite, as the sandbox would return it."""
    d = tmp_path / "suite"
    d.mkdir()
    (d / "test_x.py").write_text(body)
    flags = [f for f in sg.va.PYTEST_FIXED if f not in ("--rootdir", "/workspace")]
    r = subprocess.run([sys.executable, "-m", "pytest", *flags, str(d)], capture_output=True, text=True, cwd=d)
    return {"exit_code": r.returncode, "stdout": r.stdout, "stderr": r.stderr}


@pytest.fixture
def checkable(tmp_path, repo, two_runtimes):
    r, c = repo
    st, images, started = two_runtimes
    return st, applied_job(tmp_path / "jobs", "jx", r, c["good"]), c["good"]


def test_a_check_records_the_runtime_image_and_does_not_take_the_staging_lock(tmp_path, checkable):
    st, jid, commit = checkable
    out = pytest_output(tmp_path, "def test_a():\n    pass\n")
    with st.lock():                                             # a deploy or rollback running meanwhile
        rec = sg.check(jid, "ledger_py312_up1", cfg={}, jobs_dir=tmp_path / "jobs", staging=st,
                       run=lambda argv, workdir, cfg: out)
    assert rec["ok"] is True and rec["runtime_image"] == IMAGES["ledger_staging_up1"], rec
    assert st.checks() == [rec] and not list((st.base / "checks").iterdir())


def test_a_check_whose_container_was_not_removed_does_not_pass(tmp_path, checkable):
    st, jid, commit = checkable
    out = {**pytest_output(tmp_path, "def test_a():\n    pass\n"), "cleanup_failed": True}
    rec = sg.check(jid, "ledger_py312_up1", cfg={}, jobs_dir=tmp_path / "jobs", staging=st,
                   run=lambda argv, workdir, cfg: out)
    assert rec["ok"] is False and "removal not confirmed" in rec["why"]


def test_a_check_that_stops_is_recorded_and_outweighs_an_earlier_pass(tmp_path, checkable):
    st, jid, commit = checkable
    passed_check(st, commit)
    assert st.tested(commit, "ledger_staging_up1", {})

    def down(argv, workdir, cfg):
        raise sg.sb.SandboxUnavailable("docker is down")
    with pytest.raises(sg.sb.SandboxUnavailable):
        sg.check(jid, "ledger_py312_up1", cfg={}, jobs_dir=tmp_path / "jobs", staging=st, run=down)
    assert st.checks()[-1]["ok"] is False and "docker is down" in st.checks()[-1]["why"]
    with pytest.raises(sg.Refused, match="no passed"):
        st.tested(commit, "ledger_staging_up1", {})
    assert not list((st.base / "checks").iterdir())


def test_every_runtime_gives_valid_release_names():
    for runtime in sg.RUNTIMES:
        assert sg.RELEASE.match(sg.release_name(type("J", (), {"id": "jx"}), "0" * 40, runtime))


# ---- staging hardening (the /code-review findings on staging v0, Atha 2026-10-30) -------------------------------------

@pytest.fixture
def fake_docker(tmp_path, monkeypatch):
    """Staging whose containers are names in a set: start/smoke/logs faked, docker ps and rm answered from the set."""
    monkeypatch.setattr(sg, "runtime_image", lambda cfg, runtime=sg.ENVIRONMENT: "sha256:" + "a" * 64)
    up, calls = set(), []

    def run(*a, **k):
        calls.append(a)
        if a[0] == "ps":
            return 0, "\n".join(sorted(up)), ""
        if is_owner(a):
            return owner(a, tmp_path / "staging", up)
        if a[0] == "rm":
            up.discard(a[-1])
            return 0, "", ""
        return 0, "", ""
    st = Staging(tmp_path / "staging", run=run)

    def start(release, image):
        up.add(TEST_PREFIX + release)
        return TEST_PREFIX + release
    monkeypatch.setattr(st, "start", start)
    monkeypatch.setattr(st, "smoke", lambda release: [("all", True, "")])
    monkeypatch.setattr(st, "logs", lambda name, release, what: None)
    return st, up, calls


def test_a_failure_to_log_the_new_release_leaves_the_old_one_live_in_the_state_too(tmp_path, repo, fake_docker,
                                                                                    monkeypatch):
    r, c = repo
    st, up, calls = fake_docker
    jobs = tmp_path / "jobs"
    first = sg.deploy(applied_job(jobs, "ja", r, c["good"]), cfg=None, deps=deps(), jobs_dir=jobs, staging=st)
    note = st.note

    def broken(event, **detail):
        if event == "live":
            raise OSError("disk full")
        return note(event, **detail)
    monkeypatch.setattr(st, "note", broken)
    with pytest.raises(OSError, match="disk full"):
        sg.deploy(applied_job(jobs, "jb", r, c["good2"]), cfg=None, deps=deps(), jobs_dir=jobs, staging=st)
    assert st.state()["live"] == first and up == {TEST_PREFIX + first}


@pytest.mark.parametrize("content", ["{", "", "[]", '{"live": "x"}', '{"live": "x", "history": ["y"]}',
                                     '{"live": null, "history": [1]}', '{"live": "x", "history": ["x", "y"]}'])
def test_an_unreadable_state_refuses_deploy_and_rollback_and_stops_nothing(tmp_path, repo, fake_docker, content):
    r, c = repo
    st, up, calls = fake_docker
    jobs = tmp_path / "jobs"
    sg.deploy(applied_job(jobs, "ja", r, c["good"]), cfg=None, deps=deps(), jobs_dir=jobs, staging=st)
    before = set(up)
    st.state_path.write_text(content)
    calls.clear()
    with pytest.raises(sg.Refused, match="state.json"):
        sg.deploy(applied_job(jobs, "jb", r, c["good2"]), cfg=None, deps=deps(), jobs_dir=jobs, staging=st)
    with pytest.raises(sg.Refused, match="state.json"):
        sg.rollback(cfg=None, deps=deps(), staging=st)
    assert up == before and not [a for a in calls if a[0] == "rm"]
    assert "state.json" in sg.status(staging=st)


def test_a_fresh_staging_has_nothing_live(tmp_path):
    st = Staging(tmp_path / "none")
    assert st.state() == {"live": None, "history": []}


@pytest.mark.parametrize("still_there", [False, True])
def test_a_container_that_was_not_removed_is_not_reported_stopped(tmp_path, still_there):
    def run(*a, **k):
        if is_owner(a):
            return owner(a, tmp_path, {TEST_PREFIX + "jx-0123456789ab"})
        if a[0] == "rm":
            return 1, "", "some docker error"
        return (0 if still_there else 1), "", ""                  # docker inspect: is it still there?
    st = Staging(tmp_path, run=run)
    if still_there:
        with pytest.raises(sg.Refused, match="could not be removed"):
            st.remove(TEST_PREFIX + "jx-0123456789ab")
    else:
        st.remove(TEST_PREFIX + "jx-0123456789ab")


def test_a_hung_docker_logs_does_not_keep_the_old_release_running(tmp_path, repo, fake_docker, monkeypatch):
    r, c = repo
    st, up, calls = fake_docker
    jobs = tmp_path / "jobs"
    sg.deploy(applied_job(jobs, "ja", r, c["good"]), cfg=None, deps=deps(), jobs_dir=jobs, staging=st)

    def hung(name, release, what):
        if what == "stop":
            raise subprocess.TimeoutExpired(["docker", "logs"], 120)
    monkeypatch.setattr(st, "logs", hung)
    second = sg.deploy(applied_job(jobs, "jb", r, c["good2"]), cfg=None, deps=deps(), jobs_dir=jobs, staging=st)
    assert up == {TEST_PREFIX + second} and st.state()["live"] == second


def test_the_smoke_test_waits_until_the_socket_listens(tmp_path):
    st = with_fixture(Staging(tmp_path, wait_s=5))
    st.container_pid = lambda release: os.getpid()
    d = st.dir("jx-0123456789ab") / "sock"
    d.mkdir(parents=True)
    bound = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)    # uvicorn between bind() and listen()
    dfd = os.open(d, os.O_RDONLY | os.O_DIRECTORY)
    try:
        bound.bind(f"/proc/self/fd/{dfd}/app.sock")
    finally:
        os.close(dfd)
    servers = []

    def listen_later():
        bound.close()
        os.unlink(d / "app.sock")
        servers.append(serve(d / "app.sock", good))
    timer = threading.Timer(0.6, listen_later)
    timer.start()
    try:
        results = st.smoke("jx-0123456789ab")
    finally:
        timer.join()
        for s in servers:
            s.shutdown()
    assert all(ok for _, ok, _ in results), results


def test_a_failure_to_log_a_rollback_leaves_the_current_release_live(tmp_path, repo, fake_docker, monkeypatch):
    r, c = repo
    st, up, calls = fake_docker
    jobs = tmp_path / "jobs"
    sg.deploy(applied_job(jobs, "ja", r, c["good"]), cfg=None, deps=deps(), jobs_dir=jobs, staging=st)
    second = sg.deploy(applied_job(jobs, "jb", r, c["good2"]), cfg=None, deps=deps(), jobs_dir=jobs, staging=st)
    note = st.note
    monkeypatch.setattr(st, "note", lambda event, **d: (_ for _ in ()).throw(OSError("disk full")) if event == "live"
                        else note(event, **d))
    with pytest.raises(OSError, match="disk full"):
        sg.rollback(cfg=None, deps=deps(), staging=st)
    assert st.state()["live"] == second and up == {TEST_PREFIX + second}


def failing_rm(calls, up, base):
    """docker for fake_docker whose rm always fails and leaves the container running."""
    def run(*a, **k):
        calls.append(a)
        if a[0] == "ps":
            return 0, "\n".join(sorted(up)), ""
        if is_owner(a):
            return owner(a, base, up)
        if a[0] == "rm":
            return 1, "", "daemon hiccup"
        if a[0] == "inspect":
            return (0 if a[-1] in up else 1), "", ""
        return 0, "", ""
    return run


def test_a_record_failure_closes_the_live_event_it_left(tmp_path, repo, fake_docker, monkeypatch):
    r, c = repo
    st, up, calls = fake_docker
    jobs = tmp_path / "jobs"
    first = sg.deploy(applied_job(jobs, "ja", r, c["good"]), cfg=None, deps=deps(), jobs_dir=jobs, staging=st)
    monkeypatch.setattr(st, "_save", lambda state: (_ for _ in ()).throw(OSError("disk full")))
    with pytest.raises(OSError, match="disk full"):
        sg.deploy(applied_job(jobs, "jb", r, c["good2"]), cfg=None, deps=deps(), jobs_dir=jobs, staging=st)
    second = [e for e in sg._jsonl(st.log_path) if e.get("release", "").startswith("jb-")]
    assert [e["event"] for e in second][-2:] == ["live", "stopped"] and up == {TEST_PREFIX + first}


def test_an_old_release_that_cannot_be_stopped_does_not_fail_a_deploy_that_went_live(tmp_path, repo, fake_docker):
    r, c = repo
    st, up, calls = fake_docker
    jobs = tmp_path / "jobs"
    first = sg.deploy(applied_job(jobs, "ja", r, c["good"]), cfg=None, deps=deps(), jobs_dir=jobs, staging=st)
    st.run = failing_rm(calls, up, st.base)
    d = deps()
    second = sg.deploy(applied_job(jobs, "jb", r, c["good2"]), cfg=None, deps=d, jobs_dir=jobs, staging=st)
    assert st.state()["live"] == second and "staged" in [e["what"] for e in rj.open_job("jb", jobs).data["log"]]
    assert any(first in line and "could not be stopped" in line for line in d.echo.lines)
    assert [e["event"] for e in sg._jsonl(st.log_path)][-1] == "stop_failed"


def test_a_failed_cleanup_does_not_hide_why_the_deploy_failed(tmp_path, repo, fake_docker, monkeypatch):
    r, c = repo
    st, up, calls = fake_docker
    st.run = failing_rm(calls, up, st.base)
    monkeypatch.setattr(st, "smoke", lambda release: (_ for _ in ()).throw(RuntimeError("socket broke")))
    with pytest.raises(RuntimeError, match="socket broke"):
        sg.deploy(applied_job(tmp_path / "jobs", "ja", r, c["good"]), cfg=None, deps=deps(),
                  jobs_dir=tmp_path / "jobs", staging=st)


def test_a_hung_docker_logs_after_a_passed_smoke_does_not_fail_the_deploy(tmp_path, repo, fake_docker, monkeypatch):
    r, c = repo
    st, up, calls = fake_docker
    monkeypatch.setattr(st, "logs", lambda name, release, what: (_ for _ in ()).throw(
        subprocess.TimeoutExpired(["docker", "logs"], 15)))
    rel = sg.deploy(applied_job(tmp_path / "jobs", "ja", r, c["good"]), cfg=None, deps=deps(),
                    jobs_dir=tmp_path / "jobs", staging=st)
    assert st.state()["live"] == rel and up == {TEST_PREFIX + rel}


def test_copying_logs_waits_only_briefly(tmp_path):
    seen = []
    st = Staging(tmp_path, run=lambda *a, **k: seen.append(k) or (0, "", ""))
    st.dir("jx-0123456789ab").mkdir(parents=True)
    st.logs(TEST_PREFIX + "jx-0123456789ab", "jx-0123456789ab", "stop")
    assert seen and 0 < seen[0]["timeout"] <= 15


def test_a_dangling_state_link_is_not_a_fresh_staging(tmp_path):
    st = Staging(tmp_path)
    tmp_path.mkdir(exist_ok=True)
    st.state_path.symlink_to(tmp_path / "gone.json")
    with pytest.raises(sg.Refused, match="state.json"):
        st.state()


def test_status_exits_2_when_the_state_cannot_be_used(tmp_path, monkeypatch):
    import argus
    st = Staging(tmp_path)
    st.base.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(sg, "Staging", lambda: st)
    assert argus.main(["stage", "status"]) == 0
    st.state_path.write_text("{")
    assert argus.main(["stage", "status"]) == 2


def test_a_socket_that_never_listens_says_so(tmp_path):
    st = Staging(tmp_path, wait_s=0.5)
    st.container_pid = lambda release: os.getpid()
    (st.dir("jx-0123456789ab") / "sock").mkdir(parents=True)
    results = st.smoke("jx-0123456789ab")
    assert results and all(not ok and "did not accept a connection within" in d for _, ok, d in results)


# ---- SPEC_STAGING_REAL_DATA in the real container ---------------------------------------------------------------------

def test_a_refreshed_snapshot_is_served_without_a_restart_and_the_monitor_passes(tmp_path, repo, staging, image):
    import shutil
    r, c = repo
    rel = sg.deploy(applied_job(tmp_path / "jobs", "jg", r, c["good"]), cfg=None, deps=deps(),
                    jobs_dir=tmp_path / "jobs", staging=staging)
    container = json.loads(staging.run("inspect", TEST_PREFIX + rel)[1])[0]["Id"]
    more = tmp_path / "more"
    shutil.copytree(sg.FIXTURE, more)
    shutil.copytree(more / "jstaging_done", more / "jstaging_more")
    for f in (more / "jstaging_more").rglob("*"):
        if f.is_file():
            f.write_text(f.read_text().replace("jstaging_done", "jstaging_more"))
    (more / "jstaging_more" / "runs" / "jstaging_done-a1").rename(more / "jstaging_more" / "runs" / "jstaging_more-a1")
    (more / "jstaging_more" / "runs" / "jstaging_done-d1").rename(more / "jstaging_more" / "runs" / "jstaging_more-d1")
    rec = sd.monitor(staging, more)
    assert rec["ok"] is True and rec["refresh"]["jobs"] == 3, rec
    summary = json.loads(sg._get(staging.dir(rel) / "sock" / "app.sock", sg.HOST, "/summary")[1])
    assert summary["jobs"] == 3 and summary["cost_nano"] == sd.manifest(staging.data)["cost_nano"]
    assert json.loads(staging.run("inspect", TEST_PREFIX + rel)[1])[0]["Id"] == container   # the same container
    d = sd.report(staging, sg._get)
    assert "jstaging_more" in (d / "report.html").read_text()
    code, out, err = staging.run("exec", TEST_PREFIX + rel, "python3", "-c",
                                 "import pathlib\ntry:\n    pathlib.Path('/data/x').write_text('x'); print('WROTE')\n"
                                 "except OSError: print('ro')\n")
    assert out.split() == ["ro"], (out, err)
    code, out, err = staging.run("exec", TEST_PREFIX + rel, "python3", "-c", "import os; print(sorted(os.listdir('/data')))")
    names = json.loads(out.replace("'", '"'))
    assert names and all(n == "jobs" or n.startswith("snap-") for n in names), names    # no lock, no build



def test_a_socket_link_to_another_socket_is_never_followed(tmp_path):
    st = with_fixture(Staging(tmp_path / "s", wait_s=0.5))
    st.container_pid = lambda release: os.getpid()
    other = tmp_path / "other"
    other.mkdir()
    srv = serve(other / "x.sock", good)                         # another service of this host
    d = st.dir("jx-0123456789ab") / "sock"
    d.mkdir(parents=True)
    (d / "app.sock").symlink_to(other / "x.sock")
    try:
        results = st.smoke("jx-0123456789ab")
    finally:
        srv.shutdown()
    assert results and not any(ok for _, ok, _ in results)


def test_a_socket_whose_peer_is_not_the_container_is_refused(tmp_path):
    st = with_fixture(Staging(tmp_path, wait_s=0.5))
    st.container_pid = lambda release: os.getpid() + 1             # another process answers on the socket
    d = st.dir("jx-0123456789ab") / "sock"
    d.mkdir(parents=True)
    srv = serve(d / "app.sock", good)
    try:
        results = st.smoke("jx-0123456789ab")
    finally:
        srv.shutdown()
    assert results and not any(ok for _, ok, _ in results)
    with pytest.raises(OSError, match="peer is pid"):
        sg._get(d / "app.sock", sg.HOST, "/summary", peer=os.getpid() + 1)


def test_no_container_pid_means_no_smoke_request(tmp_path):
    st = with_fixture(Staging(tmp_path, run=lambda *a, **k: (1, "", "no such container")))
    results = st.smoke("jx-0123456789ab")
    assert results and all(not ok and "not running" in d for _, ok, d in results)


# ---- one staging directory never touches another's containers (Atha 2026-10-30) --------------------------------------

def labelled_docker(containers, calls=None):
    """docker over `containers` ({name: labels}) that applies ps's --filter label=K / label=K=V as docker does, and
    answers inspect of the staging directory label and rm."""
    def run(*a, **k):
        if calls is not None:
            calls.append(a)
        if a[0] == "ps":
            want = [f.split("=", 1)[1] for f, prev in zip(a[1:], a) if prev == "--filter"]
            names = [n for n, labels in containers.items()
                     if all((w.split("=", 1)[0] in labels) if "=" not in w else
                            labels.get(w.split("=", 1)[0]) == w.split("=", 1)[1] for w in want)]
            return 0, "\n".join(sorted(names)), ""
        if is_owner(a):
            labels = containers.get(a[-1])
            if labels is None:
                return 1, "", f"Error: No such container: {a[-1]}"
            return 0, labels.get(sg.BASE_LABEL, "<no value>"), ""
        if a[0] == "rm":
            containers.pop(a[-1], None)
        return 0, "", ""
    return run


def test_only_containers_of_this_staging_directory_are_listed(tmp_path):
    mine = Staging(tmp_path / "mine")
    containers = {
        TEST_PREFIX + "ja-0123456789ab": {TEST_LABEL: "ja-0123456789ab", sg.BASE_LABEL: mine.base_label},
        TEST_PREFIX + "jb-0123456789ab": {TEST_LABEL: "jb-0123456789ab", sg.BASE_LABEL: str(tmp_path / "other")},
        TEST_PREFIX + "jc-0123456789ab": {TEST_LABEL: "jc-0123456789ab"},
    }
    mine.run = labelled_docker(containers)
    assert mine.running() == [TEST_PREFIX + "ja-0123456789ab"]


def test_a_container_of_another_staging_directory_is_never_removed(tmp_path):
    calls = []
    other = {sg.BASE_LABEL: str(tmp_path / "other")}
    containers = {TEST_PREFIX + "jb-0123456789ab": other, TEST_PREFIX + "jc-0123456789ab": {}}
    st = Staging(tmp_path / "mine", run=labelled_docker(containers, calls))
    for name, why in ((TEST_PREFIX + "jb-0123456789ab", "belongs to staging " + other[sg.BASE_LABEL]),
                      (TEST_PREFIX + "jc-0123456789ab", "no directory label")):
        with pytest.raises(sg.Refused, match=why):
            st.remove(name)
    assert not [a for a in calls if a[0] == "rm"] and len(containers) == 2


def test_the_staging_directory_label_is_the_resolved_path(tmp_path):
    (tmp_path / "real").mkdir()
    os.symlink(tmp_path / "real", tmp_path / "link")
    assert Staging(tmp_path / "link").base_label == Staging(tmp_path / "real").base_label == str(tmp_path / "real")


def test_tests_use_a_container_namespace_of_their_own(tmp_path):
    st = Staging(tmp_path)
    assert (st.prefix, st.label) == (TEST_PREFIX, TEST_LABEL) != (sg.PREFIX, sg.LABEL)
    real = {sg.PREFIX + "ja-0123456789ab": {sg.LABEL: "ja-0123456789ab", sg.BASE_LABEL: st.base_label}}
    st.run = labelled_docker(real)
    assert st.running() == []                              # even with this directory's label
    with pytest.raises(sg.Refused, match="not a staging container"):
        st.remove(sg.PREFIX + "ja-0123456789ab")


def test_a_test_deploy_leaves_a_container_of_the_real_staging_running(tmp_path, repo, staging, image):
    """The regression of 2026-10-30: a container named and labelled as the real staging's (directory label included)
    is still running after a test's deploy and rollback."""
    r, c = repo
    name = sg.PREFIX + "jdummy-" + os.urandom(6).hex()
    code, _, err = staging.run("run", "-d", "--name", name, "--label", f"{sg.LABEL}={name[len(sg.PREFIX):]}",
                               "--label", f"{sg.BASE_LABEL}={sg.Staging().base_label}", "--network", "none", image,
                               "python3", "-c", "import time; time.sleep(600)")
    assert code == 0, err
    try:
        jobs = tmp_path / "jobs"
        sg.deploy(applied_job(jobs, "jg", r, c["good"]), cfg=None, deps=deps(), jobs_dir=jobs, staging=staging)
        sg.deploy(applied_job(jobs, "jh", r, c["good2"]), cfg=None, deps=deps(), jobs_dir=jobs, staging=staging)
        sg.rollback(cfg=None, deps=deps(), staging=staging)
        assert staging.run("inspect", "--format", "{{.State.Running}}", name)[1].strip() == "true"
        assert all(n.startswith(TEST_PREFIX) for n in staging.running())
    finally:
        staging.run("rm", "-f", name)


# ---- argus stage restart -----------------------------------------------------------------------------------------------

def restartable(tmp_path, live="jx-0123456789ab", image="sha256:" + "b" * 64, containers=None):
    calls, containers = [], ({} if containers is None else containers)
    st = Staging(tmp_path / "staging", run=labelled_docker(containers, calls))
    st.base.mkdir(parents=True)
    st._save({"live": live, "history": ["jw-0123456789ab", live]})
    st.note("built", release=live, job="jx", repo="r", commit="0" * 40, runtime="ledger_staging_up1", image=image)
    started = []

    def start(release, img):
        started.append((release, img))
        containers[st.prefix + release] = {sg.BASE_LABEL: st.base_label}
        return st.prefix + release
    st.start = start
    st.smoke = lambda release: [("all", True, "")]
    return st, calls, started, containers


def test_restart_starts_the_live_release_on_its_recorded_image_and_nothing_else(tmp_path, monkeypatch):
    monkeypatch.setattr(sg, "runtime_image", lambda *a, **k: pytest.fail("today's image is not asked for"))
    st, calls, started, _ = restartable(tmp_path)
    state = st.state_path.read_bytes()
    assert sg.restart(deps=deps(), staging=st) == "jx-0123456789ab"
    assert started == [("jx-0123456789ab", "sha256:" + "b" * 64)]
    assert not [a for a in calls if a[0] in ("ps", "rm")]           # no reconcile, nothing removed
    assert st.state_path.read_bytes() == state
    events = [e["event"] for e in sg._jsonl(st.log_path)]
    assert events[-2:] == ["smoke", "restarted"]


@pytest.mark.parametrize("running", [True, False])
def test_restart_is_refused_while_a_container_of_the_live_release_exists(tmp_path, running):
    st, calls, started, _ = restartable(tmp_path, containers={
        TEST_PREFIX + "jx-0123456789ab": {sg.BASE_LABEL: "x", "running": str(running)}})
    with pytest.raises(sg.Refused, match="exists"):
        sg.restart(deps=deps(), staging=st)
    assert started == [] and not [a for a in calls if a[0] == "rm"]


@pytest.mark.parametrize("make, why", [
    (lambda st: st._save({"live": None, "history": ["jx-0123456789ab"]}), "nothing is live"),
    (lambda st: st._save({"live": "jy-0123456789ab", "history": ["jy-0123456789ab"]}), "not one that was built"),
    (lambda st: st.note("built", release="jx-0123456789ab", job="jx", repo="r", commit="0" * 40,
                        runtime="ledger_staging_up1", image="argus-sandbox:latest"), "no image digest"),
])
def test_restart_without_a_recorded_live_release_and_image_is_refused(tmp_path, make, why):
    st, calls, started, _ = restartable(tmp_path)
    make(st)
    with pytest.raises(sg.Refused, match=why):
        sg.restart(deps=deps(), staging=st)
    assert started == []


def test_a_restart_whose_smoke_test_fails_is_stopped_and_not_recorded(tmp_path):
    st, calls, started, containers = restartable(tmp_path)
    st.smoke = lambda release: [("summary", False, "500")]
    with pytest.raises(sg.Refused, match="failed its smoke test"):
        sg.restart(deps=deps(), staging=st)
    assert containers == {} and "restarted" not in [e["event"] for e in sg._jsonl(st.log_path)]


def test_a_restart_is_confirmed_before_anything_starts(tmp_path):
    st, calls, started, _ = restartable(tmp_path)
    with pytest.raises(sg.Refused, match="not confirmed"):
        sg.restart(deps=deps(yes=False), staging=st)
    assert started == []


def test_restart_in_the_real_container_after_it_was_removed(tmp_path, repo, staging, image):
    r, c = repo
    jobs = tmp_path / "jobs"
    rel = sg.deploy(applied_job(jobs, "jg", r, c["good"]), cfg=None, deps=deps(), jobs_dir=jobs, staging=staging)
    staging.run("rm", "-f", TEST_PREFIX + rel)
    assert staging.running() == []
    assert sg.restart(deps=deps(), staging=staging) == rel
    assert staging.running() == [TEST_PREFIX + rel] and all(ok for _, ok, _ in staging.smoke(rel))
    with pytest.raises(sg.Refused, match="exists"):
        sg.restart(deps=deps(), staging=staging)


def test_a_container_whose_directory_cannot_be_read_is_not_removed(tmp_path):
    calls = []

    def run(*a, **k):
        calls.append(a)
        return (1, "", "Cannot connect to the Docker daemon") if a[0] == "inspect" else (0, "", "")
    with pytest.raises(sg.Refused, match="inspect"):
        Staging(tmp_path, run=run).remove(TEST_PREFIX + "jx-0123456789ab")
    assert not [a for a in calls if a[0] == "rm"]
