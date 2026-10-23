"""`argus list` (router): every job in the jobs directory on one line, sorted by job id, read only.

  <job id> <state> spent $<spent 4dp> of $<cap 2dp>

The job files and their ledgers are written by hand here, so the test does not depend on a stage running."""
import importlib.util
import json
import sys
from pathlib import Path

import pytest

from router import job as rj

ROOT = Path(__file__).resolve().parent.parent


def ledger(path, nano=None, crash_nano=None):
    """One finished model call (and optionally one cut off by a crash, charged at its worst case)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = []
    if nano is not None:
        lines += [{"event": "llm_call_started", "call_id": "c1", "worst_tokens": 500,
                   "worst_usd_nano": nano},
                  {"event": "llm_call", "call_id": "c1", "status": "ok", "tokens": 400, "usd_nano": nano}]
    if crash_nano is not None:
        lines += [{"event": "llm_call_started", "call_id": "c2", "worst_tokens": 700,
                   "worst_usd_nano": crash_nano}]
    path.write_text("".join(json.dumps(e) + "\n" for e in lines), encoding="utf-8")


def job(jobs, job_id, state="AWAITING_APPROVAL", cap=1.0, stages=None, d=None):
    jd = Path(jobs) / (d or job_id)
    jd.mkdir(parents=True, exist_ok=True)
    (jd / "job.json").write_text(json.dumps({"job": job_id, "kind": "code", "state": state, "max_usd": cap,
                                              "inputs": {"repo": "/x", "commit": "HEAD", "issue": "i"},
                                              "stages": stages or {}}), encoding="utf-8")
    return jd


def listed(jobs):
    assert hasattr(rj, "list_jobs"), "router/job.py has no list_jobs"
    return rj.list_jobs(jobs_dir=jobs)


@pytest.fixture
def jobs(tmp_path):
    return tmp_path / "jobs"


def test_list_prints_one_sorted_line_per_job(jobs):
    job(jobs, "jb", state="DRAFT_FAILED", cap=0.5)
    job(jobs, "ja", state="REVIEW_READY", cap=1.25)
    job(jobs, "j10", state="NEW", cap=2.0)
    assert listed(jobs).splitlines() == ["j10 NEW spent $0.0000 of $2.00",
                                         "ja REVIEW_READY spent $0.0000 of $1.25",
                                         "jb DRAFT_FAILED spent $0.0000 of $0.50"]


def test_list_shows_the_spend_its_stage_runs_recorded(jobs):
    first = job(jobs, "ja", stages={"d1": {"kind": "draft", "run_id": "ja-d1", "cap_usd": 0.4},
                                     "a1": {"kind": "agent", "run_id": "ja-a1", "cap_usd": 0.5}})
    ledger(first / "runs" / "ja-d1" / "events.jsonl", nano=125_000_000)
    ledger(first / "runs" / "ja-a1" / "events.jsonl", nano=50_000_000)
    second = job(jobs, "jb", state="NEW", cap=3.0)
    ledger(second / "runs" / "jb-d1" / "events.jsonl", crash_nano=250_000_000)      # cut off: its worst case
    assert listed(jobs).splitlines() == ["ja AWAITING_APPROVAL spent $0.1750 of $1.00",
                                         "jb NEW spent $0.2500 of $3.00"]


def test_a_job_json_that_cannot_be_read_is_named_and_others_still_listed(jobs):
    job(jobs, "ja", state="NEW", cap=1.0)
    broken = job(jobs, "jb", state="NEW", cap=1.0)
    (broken / "job.json").write_text('{"job": "jb", ', encoding="utf-8")
    empty = job(jobs, "jc", state="NEW", cap=1.0)
    (empty / "job.json").write_text("", encoding="utf-8")
    a_directory = job(jobs, "jd", state="NEW", cap=1.0)
    (a_directory / "job.json").unlink()
    (a_directory / "job.json").mkdir()
    assert listed(jobs).splitlines() == ["ja NEW spent $0.0000 of $1.00", "jb unreadable", "jc unreadable",
                                         "jd unreadable"]


def test_only_directories_with_a_job_json_are_jobs(jobs):
    job(jobs, "ja", state="BLOCKED", cap=1.0)
    (jobs / "scratch").mkdir()                              # a directory that is not a job
    (jobs / "notes.txt").write_text("x", encoding="utf-8")
    (jobs / "jj" / ".lock").parent.mkdir()                 # only a lock: no job.json, not a job
    (jobs / "jj" / ".lock").write_text("", encoding="utf-8")
    assert listed(jobs).splitlines() == ["ja BLOCKED spent $0.0000 of $1.00"]


def test_no_jobs_and_a_missing_directory_say_exactly_no_jobs(jobs, tmp_path):
    assert listed(jobs) == "no jobs"
    jobs.mkdir()
    assert listed(jobs) == "no jobs"
    (jobs / "scratch").mkdir()
    (jobs / "notes.txt").write_text("x", encoding="utf-8")
    assert listed(jobs) == "no jobs"
    assert listed(tmp_path / "nowhere") == "no jobs"


def test_list_takes_no_lock_and_changes_nothing(jobs):
    jd = job(jobs, "ja", stages={"d1": {"kind": "draft", "run_id": "ja-d1", "cap_usd": 0.4}})
    log = jd / "runs" / "ja-d1" / "events.jsonl"
    ledger(log, nano=10_000_000)
    log.write_bytes(log.read_bytes() + b'{"event": "llm_call_started", "call_id": "cut", "wor')
    before_file, before_log = (jd / "job.json").read_bytes(), log.read_bytes()
    holder = rj.Job(jd)
    with holder.lock():                                    # a stage holds the job: list must not need the lock
        text = listed(jobs)
        files = sorted(str(p.relative_to(jd)) for p in jd.rglob("*"))
    assert text.splitlines() == ["ja AWAITING_APPROVAL spent $0.0100 of $1.00"]
    assert files == [".lock", "job.json", "runs", "runs/ja-d1", "runs/ja-d1/events.jsonl"]   # nothing written
    assert (jd / "job.json").read_bytes() == before_file and log.read_bytes() == before_log


def cli():
    spec = importlib.util.spec_from_file_location("argus_cli_list", ROOT / "scripts" / "argus.py")
    mod = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(ROOT / "scripts"))
    spec.loader.exec_module(mod)
    return mod


def test_the_cli_lists_jobs_and_exits_zero(jobs, capsys):
    job(jobs, "ja", state="REVIEW_READY", cap=1.0)
    job(jobs, "jb", state="NEW", cap=0.75)
    rc = cli().main(["--jobs-dir", str(jobs), "list"], deps=rj.Deps(confirm=lambda text: False))
    out = capsys.readouterr().out
    assert rc == 0
    assert out.splitlines() == ["ja REVIEW_READY spent $0.0000 of $1.00", "jb NEW spent $0.0000 of $0.75"]


def test_the_cli_says_no_jobs_for_a_directory_that_does_not_exist(tmp_path, capsys):
    rc = cli().main(["--jobs-dir", str(tmp_path / "nowhere"), "list"], deps=rj.Deps())
    assert rc == 0 and capsys.readouterr().out == "no jobs\n"
