# Draft review: `base` (j20261023_031205_d0f8-d3)

Status: **DRAFTED** (a draft passed its check)

Written by the harness from the draft and its check. The draft itself was written by a model: read the tests. A passing baseline shows only that the new tests fail now, not that they test the right thing.

## Issue

```text
argus has no way to see all jobs: status needs a job id the user must already know.

Add a read-only command `argus list` (scripts/argus.py, with its logic in router/job.py) that prints one line per job
in the jobs directory (--jobs-dir, default jobs/), sorted by job id:

  <job id> <state> spent $<spent with 4 decimals> of $<cap with 2 decimals>

where state and cap come from the job's job.json ("state", "max_usd") and spent is what the job's stage runs have
spent, computed the same way status computes it. Rules:
- only directories that contain a job.json are jobs; any other entry is ignored;
- a job.json that cannot be read or is not valid JSON gives the line "<directory name> unreadable" instead, and the
  other jobs are still listed;
- when the jobs directory does not exist or holds no job, it prints exactly "no jobs";
- it never takes a job's lock and never changes anything; it exits 0.
```

## Plan

Files: `router/job.py`, `scripts/argus.py`

Steps:
- Add a read-only function router/job.py (e.g. list_jobs) that scans the jobs directory with os.scandir/sorted(): for each directory holding a job.json, print the job id, its state and max_usd from job.json, and the spend its stage runs' ledgers show via the existing spent_nano(); print '<dir name> unreadable' when job.json is a directory or holds invalid JSON (or the job has no id/max_usd), and 'no jobs' when the directory is absent or holds no job.
- Make the line format exactly '<job id> <state> spent $<spent 4dp> of $<cap 2dp>' and sort the lines by directory name, never taking a lock and never writing anything.
- Register a `list` subcommand in scripts/argus.py that takes no job argument, calls the new function with o.jobs_dir, prints what it returns and returns 0.

Risks:
- Taking a lock (or an EventLog that repairs a cut last line) and so changing the jobs directory while listing.
- Letting one bad job.json (a directory, invalid JSON, missing 'job'/'max_usd') abort the whole listing instead of printing its '<name> unreadable' line.
- Treating a plain file named job.json inside a job directory as a valid job, or listing directories without a job.json.
- Printing 'no jobs' when the directory holds only non-job entries (it must still print exactly 'no jobs'), or printing nothing / exiting non-zero for a missing directory.
- Formatting the money wrong: 4 decimals for spent, 2 for the cap, or counting spend from job.json instead of the stage runs' ledgers.

## Scope

Writable: `router/job.py`, `scripts/argus.py`

Protected: `tests/**`, `conftest.py`, `config.yaml`, `harness/**`, `models/**`, `runner.py`, `codetask/**`, `acceptance/**`, `router/__init__.py`, `README.md`, `AGENTS.md`, `PENDING.md`

No scope warnings.

## Validations

- `target`: `python -m pytest tests/test_router_list.py`, at least 8 tests, environment `argus`; required new tests: 8, required existing tests: 0
  - new: `tests/test_router_list.py::test_list_prints_one_sorted_line_per_job`
  - new: `tests/test_router_list.py::test_list_shows_the_spend_its_stage_runs_recorded`
  - new: `tests/test_router_list.py::test_a_job_json_that_cannot_be_read_is_named_and_others_still_listed`
  - new: `tests/test_router_list.py::test_list_takes_no_lock_and_changes_nothing`
  - new: `tests/test_router_list.py::test_the_cli_lists_jobs_and_exits_zero`
  - new: `tests/test_router_list.py::test_the_cli_says_no_jobs_for_a_directory_that_does_not_exist`
  - new: `tests/test_router_list.py::test_only_directories_with_a_job_json_are_jobs`
  - new: `tests/test_router_list.py::test_no_jobs_and_a_missing_directory_say_exactly_no_jobs`

Budget profile for the agent: `large_usd`

Tools added for the agent: `edit_file`, `search_files`

## New tests

### `tests/test_router_list.py`

On the code as it is now, validation `target`: `test_list_prints_one_sorted_line_per_job` FAIL, `test_list_shows_the_spend_its_stage_runs_recorded` FAIL, `test_a_job_json_that_cannot_be_read_is_named_and_others_still_listed` FAIL, `test_list_takes_no_lock_and_changes_nothing` FAIL, `test_the_cli_lists_jobs_and_exits_zero` FAIL, `test_the_cli_says_no_jobs_for_a_directory_that_does_not_exist` FAIL, `test_only_directories_with_a_job_json_are_jobs` FAIL, `test_no_jobs_and_a_missing_directory_say_exactly_no_jobs` FAIL

Why they fail now (test output; check that this is the behaviour to fix):

```text
/usr/lib/python3.12/argparse.py:2600: in _check_value
E   argparse.ArgumentError: argument cmd: invalid choice: 'list' (choose from 'code', 'status', 'redraft', 'resume', 'approve', 'reject', 'abandon')
/usr/lib/python3.12/argparse.py:2664: in exit
E   SystemExit: 2
============================== 8 failed in Xs ===============================
```

The file:

```python
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

```

## Not verified automatically

- that the command is listed in the README or in the module's docstring, and how the usage text reads
- that `argus list` is fast on a large jobs directory (no performance bound is asked nor checked)
- that a jobs directory the user may not read (a permission error on the directory itself) prints anything rather than failing; the issue does not say

## Cost

Drafter: $0.0216, 16 model calls, 2 submits, 15 steps (ended: submitted).

## Approve

`approve_draft.py` checks the draft again under your task name, issue, cap and attempt limit, and publishes it only with `--approve`. Without a reference patch the task is recorded as `feasibility: unproven`; with one (`--reference-patch <patch>` instead of `--no-reference`) it is proven before the agent runs.

```bash
python scripts/approve_draft.py --draft runs/j20261023_031205_d0f8-d3/draft.json --task <name> --issue-file runs/j20261023_031205_d0f8-d3/issue.txt --max-usd <cap> --max-iterations <n> --no-reference
```
