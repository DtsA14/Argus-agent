"""SPEC_STAGING_REAL_DATA: the staging snapshot of real jobs is a projection through a field allowlist, read
consistently, validated before it is published by an atomic symlink swap, never refreshed twice at once; the monitor
never touches a container or the active snapshot; the report is escaped and private."""
import fcntl
import json
import multiprocessing
import os
import stat
import sys
import threading
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from router import stage as sg  # noqa: E402
from router import stage_data as sd  # noqa: E402

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
    return b"".join(p.read_bytes() for p in sorted((data / "jobs").rglob("*")) if p.is_file())


# ---- A1: the allowlist -------------------------------------------------------------------------------------------------

def test_only_allowlisted_fields_are_published(tmp_path, source):
    data = tmp_path / "data"
    man = sd.refresh(source, data)
    assert man["jobs"] == ["jone", "jtwo"] and man["excluded"] == [] and man["cost_nano"] == 800
    job = json.loads((data / "jobs" / "jone" / "job.json").read_text())
    assert set(job) == {"job", "kind", "state", "created_at", "max_usd", "stages", "log"}
    assert set(job["stages"]["a1"]) == {"kind", "run_id", "status", "started_at", "ended_at", "usd"}
    assert job["log"] == [{"at": T, "what": "state", "old": "NEW", "new": "DRAFTING", "stage": "a1"}]
    events = [json.loads(x) for x in (data / "jobs" / "jtwo" / "runs" / "jtwo-a1" / "events.jsonl").read_text()
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
    files = sorted(p.relative_to(data / "jobs").as_posix() for p in (data / "jobs").rglob("*") if p.is_file())
    assert files == ["jone/job.json", "jone/runs/jone-a1/events.jsonl", "jtwo/job.json",
                     "jtwo/runs/jtwo-a1/events.jsonl"]


# ---- A2: consistent, validated, atomic --------------------------------------------------------------------------------

def test_a_job_that_keeps_changing_while_it_is_read_is_excluded(tmp_path, source, monkeypatch):
    real, n = sd._regular, [0]

    def changing(path):
        if path.name == "job.json" and path.parent.name == "jone":
            n[0] += 1
            return real(path) + b" " * n[0]
        return real(path)
    monkeypatch.setattr(sd, "_regular", changing)
    monkeypatch.setattr(sd.time, "sleep", lambda s: None)
    man = sd.refresh(source, tmp_path / "data")
    assert man["jobs"] == ["jtwo"] and "kept changing" in man["excluded"][0]["why"]


def test_a_ledger_that_shrinks_while_it_is_read_is_excluded(tmp_path, source, monkeypatch):
    real, seen = sd._regular, {}

    def shrinking(path):
        b = real(path)
        if path.name == "events.jsonl" and "jone" in str(path):
            seen[path] = seen.get(path, 0) + 1
            return b if seen[path] % 2 else b[:10]
        return b
    monkeypatch.setattr(sd, "_regular", shrinking)
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
    before, snap = os.readlink(data / "jobs"), sd.current(data)
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
    assert os.readlink(data / "jobs") == before and sd.current(data) == snap
    assert sd.manifest(data)["at"] == first["at"] and not list(data.glob(".tmp-*"))
    assert sorted(p.name for p in data.glob("snap-*")) == [snap.name]


def test_a_published_snapshot_is_read_only_and_the_two_newest_are_kept(tmp_path, source):
    data = tmp_path / "data"
    for hour in range(4):
        sd.refresh(source, data, clock=lambda h=hour: (2026, 10, 30, h, 0, 0, 0, 0, 0))
    snaps = sorted(p.name for p in data.glob("snap-*"))
    assert snaps == ["snap-20261030T020000Z", "snap-20261030T030000Z"]
    assert os.readlink(data / "jobs") == "snap-20261030T030000Z/jobs" and (data / "jobs").is_symlink()
    f = data / "jobs" / "jone" / "job.json"
    assert not (f.stat().st_mode & (stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH))
    assert not (f.parent.stat().st_mode & stat.S_IWUSR)


def test_a_crashed_refresh_leaves_only_a_temporary_directory_that_the_next_removes(tmp_path, source):
    data = tmp_path / "data"
    sd.refresh(source, data)
    (data / ".tmp-20261030T000000Z-1" / "jobs").mkdir(parents=True)
    sd.refresh(source, data)
    assert not list(data.glob(".tmp-*")) and sd.current(data)


def test_readers_always_see_a_whole_snapshot_while_refreshes_swap_it(tmp_path, source):
    data = tmp_path / "data"
    sd.refresh(source, data)
    stop, bad = threading.Event(), []

    def read():
        while not stop.is_set():
            try:
                jobs = sorted(os.listdir(data / "jobs"))
                for j in jobs:
                    json.loads((data / "jobs" / j / "job.json").read_text())
                if jobs != ["jone", "jtwo"]:
                    bad.append(jobs)
            except FileNotFoundError as e:                 # a snapshot removed under an old path: never the link
                bad.append(repr(e))
    t = threading.Thread(target=read)
    t.start()
    try:
        for i in range(30):
            sd.refresh(source, data, clock=lambda i=i: (2026, 10, 30, 0, i // 60, i % 60, 0, 0, 0))
    finally:
        stop.set()
        t.join()
    assert bad == []


# ---- A3: one refresh at a time ------------------------------------------------------------------------------------------

def _hold(path, ready, release):
    fd = os.open(path, os.O_RDWR | os.O_CREAT, 0o600)
    fcntl.flock(fd, fcntl.LOCK_EX)
    ready.set()
    release.wait(30)
    os.close(fd)


@pytest.fixture
def held_lock(tmp_path):
    """Another process holding the data lock, as a running refresh or monitor does."""
    data = tmp_path / "data"
    data.mkdir()
    ctx = multiprocessing.get_context("fork")
    ready, release = ctx.Event(), ctx.Event()
    p = ctx.Process(target=_hold, args=(data / ".refresh.lock", ready, release))
    p.start()
    assert ready.wait(10)
    yield data
    release.set()
    p.join(10)


def test_a_refresh_while_another_holds_the_lock_is_refused_and_changes_nothing(tmp_path, source, held_lock):
    with pytest.raises(sd.Refused, match="busy"):
        sd.refresh(source, held_lock)
    assert not os.path.lexists(held_lock / "jobs") and not list(held_lock.glob("snap-*"))


def _refresh_in_child(source, data, out):
    try:
        sd.refresh(Path(source), Path(data))
        out.put("ok")
    except sd.Refused as e:
        out.put("busy" if "busy" in str(e) else repr(e))


def test_two_refreshes_at_once_never_both_write(tmp_path, source):
    ctx = multiprocessing.get_context("fork")
    out, data = ctx.Queue(), tmp_path / "data"
    ps = [ctx.Process(target=_refresh_in_child, args=(str(source), str(data), out)) for _ in range(4)]
    for p in ps:
        p.start()
    for p in ps:
        p.join(30)
    got = sorted(out.get(timeout=5) for _ in ps)
    assert set(got) <= {"ok", "busy"} and "ok" in got
    assert sd.current(data) and sd.manifest(data)["jobs"] == ["jone", "jtwo"] and not list(data.glob(".tmp-*"))


def test_a_smoke_test_waits_for_a_refresh_and_gives_up_when_it_never_ends(tmp_path, held_lock, monkeypatch):
    monkeypatch.setattr(sd, "LOCK_WAIT_S", 0.5)
    st = sg.Staging(tmp_path)
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
    st = sg.Staging(tmp_path / "staging", run=no_docker)
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
    fd = os.open(st.data / ".refresh.lock", os.O_RDWR)
    ctx = multiprocessing.get_context("fork")
    ready, release = ctx.Event(), ctx.Event()
    p = ctx.Process(target=_hold, args=(st.data / ".refresh.lock", ready, release))
    p.start()
    try:
        assert ready.wait(10)
        rec = sd.monitor(st, source)
    finally:
        release.set()
        p.join(10)
        os.close(fd)
    assert rec["ok"] is None and "busy" in rec["why"] and smokes == [] and sd.current(st.data) == snap
    assert sd.monitor_summary(st) == (None, 0)                  # a skip is neither a pass nor a failure


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
    d = sd.report(st, lambda sock, host, url: (200, json.dumps(answers[url]).encode()))
    page = (d / "report.html").read_text()
    assert "<script" not in page.lower() and "&lt;script&gt;" in page and "&quot;" in page and "&#x27;" in page
    assert "Content-Security-Policy" in page and "default-src 'none'" in page
    assert stat.S_IMODE(d.parent.stat().st_mode) == 0o700 and stat.S_IMODE(d.stat().st_mode) == 0o700
    assert all(stat.S_IMODE(f.stat().st_mode) == 0o600 for f in d.iterdir())


def test_only_the_last_ten_reports_are_kept(live):
    st, smokes = live
    answers = {"/summary": {"jobs": 0, "cost_usd": "0", "skipped": 0}, "/jobs": []}
    for i in range(12):
        sd.report(st, lambda sock, host, url: (200, json.dumps(answers[url]).encode()),
                  clock=lambda i=i: (2026, 10, 30, 0, 0, i, 0, 0, 0))
    kept = sorted(p.name for p in (st.base / "reports").iterdir())
    assert len(kept) == 10 and kept[0] == "20261030T000002Z"


def test_a_report_of_an_answer_that_is_not_200_is_refused(live):
    st, smokes = live
    with pytest.raises(sd.Refused, match="answered 500"):
        sd.report(st, lambda sock, host, url: (500, b""))


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
    st = sg.Staging(tmp_path, run=lambda *a, **k: pytest.fail("docker must not run"))
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
