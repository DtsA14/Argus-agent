"""SPEC_STAGING_REAL_DATA: the staging snapshot of real jobs is a projection through a field allowlist, read
consistently, validated before it is published by an atomic symlink swap, never refreshed twice at once; the monitor
never touches a container or the active snapshot; the report is escaped and private."""
import json
import os
import stat
import subprocess
import sys
import threading
from contextlib import contextmanager
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from router import stage as sg  # noqa: E402
from router import stage_data as sd  # noqa: E402
from test_stage import Staging  # noqa: E402  (the tests' own container namespace)

pytestmark = pytest.mark.skipif(sys.platform == "win32", reason="symlinks, flock and modes on the VM")

T = "2026-10-30T01:02:03Z"


def started(call, worst=1000, **more):
    return {"event": "llm_call_started", "call_id": call, "worst_usd_nano": worst, "worst_tokens": 100,
            "model": "deepseek:deepseek-flash", "node": "agent", "role": "coder", "ts": 1.5, "prompt_hash": "ab12",
            "task": "task", **more}


def final(call, nano=400, **more):
    return {"event": "llm_call", "call_id": call, "status": "ok", "usd_nano": nano, "tokens": 10, "input_tokens": 8,
            "output_tokens": 2, "cache_read": 0, "est_input": 9, "model": "deepseek:deepseek-flash", "node": "agent",
            "role": "coder", "ts": 2.5, "latency_s": 0.3, "stop_reason": "stop", **more}


def make_job(root, job_id, *, job=None, events=None, extra_events=()):
    d = root / job_id
    (d / "runs" / f"{job_id}-a1").mkdir(parents=True)
    body = {"job": job_id, "kind": "code", "state": "APPLIED", "created_at": T, "max_usd": 0.5,
            "inputs": {"repo": "/home/ubuntu/secret-repo", "issue": "the issue text"},
            "approval": {"by": "atha"}, "intake": {"commit": "abc"}, "environment_image": "sha256:" + "1" * 64,
            "stages": {"a1": {"kind": "agent", "run_id": f"{job_id}-a1", "status": "DONE", "started_at": T,
                              "ended_at": T, "usd": 0.0000004, "cap_usd": 0.5, "draft_sha256": "f" * 64,
                              "review": "free text"}},
            "log": [{"at": T, "what": "state", "old": "NEW", "new": "DRAFTING", "stage": "a1",
                     "screen": "the limits screen", "reason": "free text", "path": "/home/ubuntu/x"}]}
    body.update(job or {})
    (d / "job.json").write_text(json.dumps(body))
    lines = events if events is not None else [started("c1"), final("c1"), *extra_events]
    (d / "runs" / f"{job_id}-a1" / "events.jsonl").write_text("".join(json.dumps(e) + "\n" for e in lines))
    return d


@pytest.fixture
def source(tmp_path):
    root = tmp_path / "jobs"
    root.mkdir()
    make_job(root, "jone")
    make_job(root, "jtwo", extra_events=[{"event": "tool_call", "role": "coder", "tool": "read_file", "ts": 1.0},
                                         {"event": "attempt_end", "reason": "finished", "steps": 3, "node": "agent",
                                          "ts": 3.0, "task": "task", "iteration": 0}])
    return root


def snapshot_bytes(data):
    return b"".join(p.read_bytes() for p in sorted((sd.pub(data) / "jobs").rglob("*")) if p.is_file())


# ---- A1: the allowlist -------------------------------------------------------------------------------------------------

def test_only_allowlisted_fields_are_published(tmp_path, source):
    data = tmp_path / "data"
    man = sd.refresh(source, data)
    assert man["jobs"] == ["jone", "jtwo"] and man["excluded"] == [] and man["cost_nano"] == 800
    job = json.loads((sd.pub(data) / "jobs" / "jone" / "job.json").read_text())
    assert set(job) == {"job", "kind", "state", "created_at", "max_usd", "stages", "log"}
    assert set(job["stages"]["a1"]) == {"kind", "run_id", "status", "started_at", "ended_at", "usd"}
    assert job["log"] == [{"at": T, "what": "state", "old": "NEW", "new": "DRAFTING", "stage": "a1"}]
    events = [json.loads(x) for x in (sd.pub(data) / "jobs" / "jtwo" / "runs" / "jtwo-a1" / "events.jsonl").read_text()
              .splitlines()]
    assert [e["event"] for e in events] == ["llm_call_started", "llm_call", "attempt_end"]
    assert all("prompt_hash" not in e and "latency_s" not in e and "task" not in e for e in events)
    published = snapshot_bytes(data)
    for secret in (b"secret-repo", b"the issue text", b"atha", b"limits screen", b"free text", b"/home/ubuntu"):
        assert secret not in published


@pytest.mark.parametrize("job, why", [
    ({"state": "applied; rm -rf"}, "job.state"),
    ({"created_at": "yesterday"}, "job.created_at"),
    ({"max_usd": -1}, "job.max_usd"),
    ({"job": "jother"}, "not its directory"),
    ({"stages": {"a1": {"run_id": "jother-a1"}}}, "run_id"),
    ({"stages": {"../x": {}}}, "stage name"),
    ({"log": [{"at": T, "what": "sk-ant-api03-abcdefgh"}]}, "log.what"),
    ({"log": "not a list"}, "job.log"),
])
def test_a_wrong_allowlisted_field_excludes_only_that_job_and_never_quotes_it(tmp_path, source, job, why):
    make_job(source, "jbad", job=job)
    man = sd.refresh(source, tmp_path / "data")
    assert man["jobs"] == ["jone", "jtwo"]
    assert [e["job"] for e in man["excluded"]] == ["jbad"] and why in man["excluded"][0]["why"]
    assert "rm -rf" not in json.dumps(man) and "sk-ant" not in json.dumps(man)


@pytest.mark.parametrize("event", [
    final("c1", nano=-5), final("c1", model="evil model"), started("c1", worst="lots"), final("c1", status="OK!"),
    {"event": "attempt_end", "reason": "<script>", "steps": 1},
])
def test_a_wrong_field_in_a_ledger_event_excludes_the_job(tmp_path, source, event):
    make_job(source, "jbad", events=[started("c9"), event])
    man = sd.refresh(source, tmp_path / "data")
    assert [e["job"] for e in man["excluded"]] == ["jbad"] and "jbad" not in man["jobs"]


def test_a_writers_cut_last_line_is_left_out(tmp_path, source):
    log = source / "jone" / "runs" / "jone-a1" / "events.jsonl"
    log.write_text(log.read_text() + '{"event": "llm_call_started", "call_id": "c2", "wor')
    man = sd.refresh(source, tmp_path / "data")
    assert man["per_job"]["jone"] == 400 and "jone" in man["jobs"]


def test_symlinks_other_files_and_other_runs_are_never_published(tmp_path, source):
    outside = tmp_path / "outside.json"
    outside.write_text(json.dumps({"job": "jlink", "state": "APPLIED"}))
    (source / "jlink").mkdir()
    (source / "jlink" / "job.json").symlink_to(outside)                   # job.json that is a link
    (source / "jone" / "root").mkdir()
    (source / "jone" / "root" / "secret.py").write_text("KEY = 1")      # a copied target repository
    (source / "jone" / "runs" / "jone-a1" / "result.json").write_text("{}")
    (source / "jone" / "runs" / "scratch").mkdir()
    (source / "jone" / "runs" / "scratch" / "events.jsonl").write_text(json.dumps(final("zz", nano=10 ** 9)))
    (source / "jtwo" / "runs" / "jtwo-d1").symlink_to(source / "jone" / "runs" / "jone-a1")
    (source / "jsym").symlink_to(source / "jone")                        # a job directory that is a link
    data = tmp_path / "data"
    man = sd.refresh(source, data)
    assert man["jobs"] == ["jone", "jtwo"] and man["cost_nano"] == 800
    assert [e["job"] for e in man["excluded"]] == ["jlink"]
    files = sorted(p.relative_to(sd.pub(data) / "jobs").as_posix() for p in (sd.pub(data) / "jobs").rglob("*") if p.is_file())
    assert files == ["jone/job.json", "jone/runs/jone-a1/events.jsonl", "jtwo/job.json",
                     "jtwo/runs/jtwo-a1/events.jsonl"]


# ---- A2: consistent, validated, atomic --------------------------------------------------------------------------------

def where(dir_fd):
    return Path(os.readlink(f"/proc/self/fd/{dir_fd}"))


def test_a_job_that_keeps_changing_while_it_is_read_is_excluded(tmp_path, source, monkeypatch):
    real, n = sd._read_at, [0]

    def changing(dir_fd, name):
        if name == "job.json" and where(dir_fd).name == "jone":
            n[0] += 1
            return real(dir_fd, name) + b" " * n[0]
        return real(dir_fd, name)
    monkeypatch.setattr(sd, "_read_at", changing)
    monkeypatch.setattr(sd.time, "sleep", lambda s: None)
    man = sd.refresh(source, tmp_path / "data")
    assert man["jobs"] == ["jtwo"] and "kept changing" in man["excluded"][0]["why"]


def test_a_ledger_that_shrinks_while_it_is_read_is_excluded(tmp_path, source, monkeypatch):
    real, seen = sd._read_at, {}

    def shrinking(dir_fd, name):
        b = real(dir_fd, name)
        path = where(dir_fd)
        if name == "events.jsonl" and "jone" in str(path):
            seen[path] = seen.get(path, 0) + 1
            return b if seen[path] % 2 else b[:10]
        return b
    monkeypatch.setattr(sd, "_read_at", shrinking)
    monkeypatch.setattr(sd.time, "sleep", lambda s: None)
    man = sd.refresh(source, tmp_path / "data")
    assert "jone" not in man["jobs"]


def test_a_projection_that_would_change_the_cost_excludes_the_job(tmp_path, source, monkeypatch):
    make_job(source, "jthree")
    (source / "jone" / "runs" / "jone-a1" / "events.jsonl").write_text(
        json.dumps(started("c7")) + "\n" + json.dumps(final("c7")) + "\n")
    real = sd.project_events                       # a projection that loses the final event of call c7
    monkeypatch.setattr(sd, "project_events", lambda text: [e for e in real(text)
                                                           if not (e["event"] == "llm_call" and e["call_id"] == "c7")])
    man = sd.refresh(source, tmp_path / "data")
    assert man["jobs"] == ["jthree", "jtwo"] and [e["job"] for e in man["excluded"]] == ["jone"]
    assert "cost" in man["excluded"][0]["why"]


def test_a_snapshot_with_more_than_half_of_the_jobs_excluded_is_not_published(tmp_path, source):
    data = tmp_path / "data"
    sd.refresh(source, data)
    snap = sd.current(data)
    for j in ("jx1", "jx2", "jx3"):
        make_job(source, j, job={"state": "lower"})
    with pytest.raises(sd.Refused, match="3 of 5 jobs excluded"):
        sd.refresh(source, data)
    assert sd.current(data) == snap and not list(data.glob(".tmp-*"))


@pytest.mark.parametrize("breaks", ["key", "extra file", "cost", "crash"])
def test_a_snapshot_that_fails_validation_is_never_published(tmp_path, source, monkeypatch, breaks):
    data = tmp_path / "data"
    first = sd.refresh(source, data, clock=lambda: (2026, 10, 30, 1, 0, 0, 0, 0, 0))
    before, snap = os.readlink(sd.pub(data) / "jobs"), sd.current(data)
    real = sd.build

    def bad(src, tmp):
        man = real(src, tmp)
        if breaks == "key":
            (tmp / "jobs" / "jone" / "job.json").write_text('{"note": "sk-ant-api03-AAAAAAAAAAAA"}')
        elif breaks == "extra file":
            (tmp / "jobs" / "jone" / "notes.txt").write_text("x")
        elif breaks == "cost":
            man["per_job"]["jone"] += 1
        else:
            raise RuntimeError("crashed in the middle")
        return man
    monkeypatch.setattr(sd, "build", bad)
    with pytest.raises((sd.Refused, RuntimeError)):
        sd.refresh(source, data, clock=lambda: (2026, 10, 30, 2, 0, 0, 0, 0, 0))
    assert os.readlink(sd.pub(data) / "jobs") == before and sd.current(data) == snap
    assert sd.manifest(data)["at"] == first["at"] and not list(data.glob(".tmp-*"))
    assert sorted(p.name for p in sd.pub(data).glob("snap-*")) == [snap.name]


def test_a_published_snapshot_is_read_only_and_the_two_newest_are_kept(tmp_path, source):
    data = tmp_path / "data"
    for hour in range(4):
        sd.refresh(source, data, clock=lambda h=hour: (2026, 10, 30, h, 0, 0, 0, 0, 0))
    snaps = sorted(p.name for p in sd.pub(data).glob("snap-*"))
    assert snaps == ["snap-20261030T020000Z", "snap-20261030T030000Z"]
    assert os.readlink(sd.pub(data) / "jobs") == "snap-20261030T030000Z/jobs" and (sd.pub(data) / "jobs").is_symlink()
    f = sd.pub(data) / "jobs" / "jone" / "job.json"
    assert not (f.stat().st_mode & (stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH))
    assert not (f.parent.stat().st_mode & stat.S_IWUSR)
    assert not (sd.current(data).stat().st_mode & stat.S_IWUSR)               # the snapshot directory itself


def test_a_crashed_refresh_leaves_only_a_temporary_directory_that_the_next_removes(tmp_path, source):
    data = tmp_path / "data"
    sd.refresh(source, data)
    (data / ".tmp-20261030T000000Z-1" / "jobs").mkdir(parents=True)
    sd.refresh(source, data)
    assert not list(data.glob(".tmp-*")) and sd.current(data)


def test_readers_always_see_a_whole_snapshot_while_refreshes_swap_it(tmp_path, source):
    data = tmp_path / "data"
    # Before the loop's names (a real clock's snap-<today>T<now> sorts after every snap-...T0000ss below: it was kept as
    # one of the two newest, so each refresh removed the snapshot that had just been live, and a reader within one
    # refresh could list it emptied; verify.sh saw that twice).
    sd.refresh(source, data, clock=lambda: (2026, 10, 29, 0, 0, 0, 0, 0, 0))
    stop, bad, started, done = threading.Event(), [], [0], [0]

    def read():
        while not stop.is_set():
            before, seen = done[0], len(bad)
            try:
                jobs = sorted(os.listdir(sd.pub(data) / "jobs"))
                for j in jobs:
                    json.loads((sd.pub(data) / "jobs" / j / "job.json").read_text())
                if jobs != ["jone", "jtwo"]:
                    bad.append(jobs)
            except FileNotFoundError as e:
                bad.append(repr(e))
            # A read that spanned two refreshes may have listed a snapshot the second one removed (two are kept): an
            # old path, never the link. Under load (verify.sh, 4 workers) that happened (an empty listing); a swap
            # that is not atomic fails within one refresh, so it is still caught.
            if started[0] - before >= 2:              # counted from its start: it removes before it returns
                del bad[seen:]
    t = threading.Thread(target=read)
    t.start()
    try:
        for i in range(30):
            started[0] += 1
            sd.refresh(source, data, clock=lambda i=i: (2026, 10, 30, 0, i // 60, i % 60, 0, 0, 0))
            done[0] += 1
    finally:
        stop.set()
        t.join()
    assert bad == []


# ---- A3: one refresh at a time ------------------------------------------------------------------------------------------

HOLD = ("import fcntl, os, sys\nfd = os.open(sys.argv[1], os.O_RDWR | os.O_CREAT, 0o600)\n"
        "fcntl.flock(fd, fcntl.LOCK_EX)\nprint('held', flush=True)\nsys.stdin.read()\n")


@contextmanager
def holding(lock):
    """Another process (a fresh interpreter, never a fork of this threaded one) holding `lock` until the block ends."""
    p = subprocess.Popen([sys.executable, "-c", HOLD, str(lock)], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                         text=True)
    try:
        assert p.stdout.readline().strip() == "held"
        yield
    finally:
        p.stdin.close()
        p.wait(10)


@pytest.fixture
def held_lock(tmp_path):
    """Another process holding the data lock, as a running refresh or monitor does."""
    data = tmp_path / "data"
    data.mkdir()
    with holding(data / ".refresh.lock"):
        yield data


def test_a_refresh_while_another_holds_the_lock_is_refused_and_changes_nothing(tmp_path, source, held_lock):
    with pytest.raises(sd.Refused, match="busy"):
        sd.refresh(source, held_lock)
    assert not os.path.lexists(sd.pub(held_lock) / "jobs") and not list(sd.pub(held_lock).glob("snap-*"))


REFRESH = ("import sys\nfrom pathlib import Path\nsys.path.insert(0, sys.argv[1])\n"
           "from router import stage_data as sd\ntry:\n    sd.refresh(Path(sys.argv[2]), Path(sys.argv[3]))\n"
           "    print('ok')\nexcept sd.Refused as e:\n    print('busy' if 'busy' in str(e) else repr(e))\n")


def test_two_refreshes_at_once_never_both_write(tmp_path, source):
    data = tmp_path / "data"
    ps = [subprocess.Popen([sys.executable, "-c", REFRESH, str(sg.ROOT), str(source), str(data)],
                           stdout=subprocess.PIPE, text=True, cwd=sg.ROOT) for _ in range(4)]
    got = sorted(p.communicate(timeout=60)[0].strip() for p in ps)
    assert set(got) <= {"ok", "busy"} and "ok" in got
    assert sd.current(data) and sd.manifest(data)["jobs"] == ["jone", "jtwo"] and not list(data.glob(".tmp-*"))


def test_a_smoke_test_waits_for_a_refresh_and_gives_up_when_it_never_ends(tmp_path, held_lock, monkeypatch):
    monkeypatch.setattr(sd, "LOCK_WAIT_S", 0.5)
    st = Staging(tmp_path)
    with pytest.raises(sd.Refused, match="busy"):
        st.smoke("jx-0123456789ab")


def test_the_monitor_unit_is_oneshot_with_a_timeout_every_15_minutes():
    unit = (sg.ROOT / "deploy" / "systemd" / "argus-stage-monitor.service").read_text()
    timer = (sg.ROOT / "deploy" / "systemd" / "argus-stage-monitor.timer").read_text()
    assert "Type=oneshot" in unit and "TimeoutStartSec=" in unit and "stage monitor" in unit
    assert "OnCalendar=*:0/15" in timer and "Unit=argus-stage-monitor.service" in timer


# ---- A5: the monitor never disturbs --------------------------------------------------------------------------------------

def no_docker(*a, **k):
    if a and a[0] in ("ps", "inspect", "logs"):
        return 0, "", ""
    pytest.fail(f"the monitor must not run docker {a[:1]}")


@pytest.fixture
def live(tmp_path, source, monkeypatch):
    st = Staging(tmp_path / "staging", run=no_docker)
    st.container_pid = lambda release: 4242
    st.base.mkdir(parents=True)
    st._save({"live": "jx-0123456789ab", "history": ["jx-0123456789ab"]})
    sd.refresh(source, st.data)
    smokes = []
    monkeypatch.setattr(st, "smoke", lambda release, held=False: smokes.append((release, held, sd.manifest(st.data)))
                        or [("all", True, "")])
    return st, smokes


def test_a_monitor_whose_refresh_fails_smokes_the_last_valid_snapshot_and_changes_nothing(live, source, monkeypatch):
    st, smokes = live
    snap, state = sd.current(st.data), st.state_path.read_bytes()
    monkeypatch.setattr(sd, "build", lambda src, tmp: (_ for _ in ()).throw(OSError("disk full")))
    rec = sd.monitor(st, source)
    assert rec["refresh"]["ok"] is False and "disk full" in rec["refresh"]["why"] and rec["ok"] is False
    assert smokes and smokes[0][1] is True and sd.current(st.data) == snap and st.state_path.read_bytes() == state
    assert sd.monitor_summary(st)[1] == 1


def test_a_failed_smoke_in_the_monitor_is_recorded_and_nothing_is_restarted(live, source, monkeypatch):
    st, smokes = live
    monkeypatch.setattr(st, "smoke", lambda release, held=False: [("staging.local /summary -> 200", False, "500")])
    state = st.state_path.read_bytes()
    for _ in range(3):
        assert sd.monitor(st, source)["ok"] is False
    assert st.state_path.read_bytes() == state and sd.monitor_summary(st)[1] == 3
    assert "last monitor: FAIL" in sg.status(staging=st) and "3 failed in a row" in sg.status(staging=st)
    monkeypatch.setattr(st, "smoke", lambda release, held=False: [("all", True, "")])
    assert sd.monitor(st, source)["ok"] is True and sd.monitor_summary(st)[1] == 0


def test_a_busy_monitor_is_skipped_and_touches_nothing(live, source, monkeypatch):
    st, smokes = live
    snap = sd.current(st.data)
    with holding(st.data / ".refresh.lock"):
        rec = sd.monitor(st, source)
    assert rec["ok"] is None and "busy" in rec["why"] and smokes == [] and sd.current(st.data) == snap
    assert sd.monitor_summary(st) == (rec, 1)                   # busy is not a pass: a held lock must show
    assert "last monitor: BUSY" in sg.status(staging=st) and "1 failed in a row" in sg.status(staging=st)


def test_a_monitor_with_an_unreadable_state_records_it_and_smokes_nothing(live, source):
    st, smokes = live
    st.state_path.write_text("{")
    rec = sd.monitor(st, source)
    assert rec["ok"] is False and "state.json" in rec["why"] and smokes == []


# ---- A4: the report ----------------------------------------------------------------------------------------------------

EVIL = '<script>alert(1)</script>"\'&'


def test_the_report_is_escaped_without_scripts_and_private(live, monkeypatch):
    st, smokes = live
    answers = {"/summary": {"jobs": 1, "cost_usd": EVIL, "skipped": 0},
               "/jobs": [{"job": EVIL, "state": EVIL, "created_at": T, "stages": 1, "cost_usd": "0.1",
                          "running": False}]}
    d = sd.report(st, lambda sock, host, url, peer=None: (200, json.dumps(answers[url]).encode()))
    page = (d / "report.html").read_text()
    assert "<script" not in page.lower() and "&lt;script&gt;" in page and "&quot;" in page and "&#x27;" in page
    assert "Content-Security-Policy" in page and "default-src 'none'" in page
    assert stat.S_IMODE(d.parent.stat().st_mode) == 0o700 and stat.S_IMODE(d.stat().st_mode) == 0o700
    assert all(stat.S_IMODE(f.stat().st_mode) == 0o600 for f in d.iterdir())


def test_only_the_last_ten_reports_are_kept(live):
    st, smokes = live
    answers = {"/summary": {"jobs": 0, "cost_usd": "0", "skipped": 0}, "/jobs": []}
    for i in range(12):
        sd.report(st, lambda sock, host, url, peer=None: (200, json.dumps(answers[url]).encode()),
                  clock=lambda i=i: (2026, 10, 30, 0, 0, i, 0, 0, 0))
    kept = sorted(p.name for p in (st.base / "reports").iterdir())
    assert len(kept) == 10 and kept[0] == "20261030T000002Z"


def test_a_report_of_an_answer_that_is_not_200_is_refused(live):
    st, smokes = live
    with pytest.raises(sd.Refused, match="answered 500"):
        sd.report(st, lambda sock, host, url, peer=None: (500, b""))


# ---- D3: the smoke test against the snapshot ------------------------------------------------------------------------

def test_the_smoke_numbers_are_the_harness_numbers_of_the_snapshot(tmp_path, source):
    data = tmp_path / "data"
    man = sd.refresh(source, data)
    checks = {url: ok for host, url, status, ok in sg.smoke_checks(man) if host == sg.HOST}
    good = json.dumps({"jobs": 2, "cost_nano": 800, "cost_usd": "0.0000", "skipped": 0}).encode()
    assert checks["/summary"](good)
    assert not checks["/summary"](json.dumps({"jobs": 2, "cost_nano": 801, "skipped": 0}).encode())
    assert not checks["/summary"](json.dumps({"jobs": 3, "cost_nano": 800, "skipped": 0}).encode())
    assert checks["/jobs"](json.dumps([{"job": "jtwo"}, {"job": "jone"}]).encode())
    assert not checks["/jobs"](json.dumps([{"job": "jone"}]).encode())
    none = {url: ok for host, url, status, ok in sg.smoke_checks(None) if host == sg.HOST}
    assert not none["/summary"](good) and not none["/jobs"](json.dumps([{"job": "jone"}, {"job": "jtwo"}]).encode())


def test_no_container_starts_without_a_published_snapshot(tmp_path):
    st = Staging(tmp_path, run=lambda *a, **k: pytest.fail("docker must not run"))
    st.dir("jx-0123456789ab").mkdir(parents=True)
    st.verify = lambda release: None
    with pytest.raises(sg.Refused, match="no published data snapshot"):
        st.start("jx-0123456789ab", "sha256:" + "a" * 64)


def test_the_active_snapshot_is_never_removed_even_when_the_clock_went_back(tmp_path, source):
    data = tmp_path / "data"
    for hour in (5, 4, 1):                                       # each new snapshot sorts before the last
        sd.refresh(source, data, clock=lambda h=hour: (2026, 10, 30, h, 0, 0, 0, 0, 0))
    assert sd.current(data).name == "snap-20261030T010000Z" and sd.manifest(data)["jobs"] == ["jone", "jtwo"]


def test_a_key_that_a_too_wide_allowlist_would_let_through_is_still_stopped(tmp_path, source, monkeypatch):
    data = tmp_path / "data"
    sd.refresh(source, data)
    snap = sd.current(data)
    monkeypatch.setitem(sd.JOB_FIELDS, "note", lambda v: isinstance(v, str))      # an allowlist mistake
    make_job(source, "jleak", job={"note": "sk-ant-api03-" + "A" * 40})
    with pytest.raises(sd.Refused, match="key pattern"):
        sd.refresh(source, data)
    assert sd.current(data) == snap and b"sk-ant" not in snapshot_bytes(data)



# ---- the security review (2026-10-30) ---------------------------------------------------------------------------------

def test_the_container_sees_only_published_snapshots_never_the_lock_or_a_build(tmp_path, source, monkeypatch):
    data = tmp_path / "data"
    sd.refresh(source, data)
    seen = []
    real = sd.validate

    def look(tmp, man):
        seen.extend(p.name for p in sd.pub(data).iterdir())        # what /data shows while a build is validated
        return real(tmp, man)
    monkeypatch.setattr(sd, "validate", look)
    sd.refresh(source, data)
    published = sorted(p.name for p in sd.pub(data).iterdir())
    assert all(n == "jobs" or n.startswith("snap-") for n in seen + published), (seen, published)
    assert (data / ".refresh.lock").exists() and not (sd.pub(data) / ".refresh.lock").exists()
    assert "source" not in sd.manifest(data) and str(source) not in json.dumps(sd.manifest(data))


def test_the_report_text_holds_only_numbers_from_the_app(live):
    st, smokes = live
    answers = {"/summary": {"jobs": "\x1b]0;pwned\x07", "cost_usd": "1.5\x1b[2J", "skipped": True}, "/jobs": []}
    d = sd.report(st, lambda sock, host, url, peer=None: (200, json.dumps(answers[url]).encode()))
    text = (d / "summary.txt").read_text()
    assert "\x1b" not in text and "jobs ?  cost $?  skipped ?" in text


def test_the_report_talks_only_to_the_releases_container(live):
    st, smokes = live
    peers = []
    answers = {"/summary": {"jobs": 0, "cost_usd": "0", "skipped": 0}, "/jobs": []}
    sd.report(st, lambda sock, host, url, peer=None: peers.append(peer) or (200, json.dumps(answers[url]).encode()))
    assert peers == [4242, 4242]
    st.container_pid = lambda release: None
    with pytest.raises(sd.Refused, match="not running"):
        sd.report(st, lambda sock, host, url, peer=None: pytest.fail("no request without the container"))
