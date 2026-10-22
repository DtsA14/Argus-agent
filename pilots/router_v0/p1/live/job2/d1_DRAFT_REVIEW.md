# Draft review: `base` (j20261022_193531_259d-d1)

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
- In router/job.py add a read-only function (e.g. list_jobs(jobs_dir)) that scans the jobs directory sorted by name, keeps only directories containing job.json, and builds one line per job.
- For a readable job, build the line '<id> <state> spent $<spent:.4f> of $<max_usd:.2f>' using the same ledger-based spend as status; for a job.json that cannot be read or parsed, emit '<dir name> unreadable'.
- Compute spend without taking the job lock and without any write (do not create .lock, do not use code paths that create directories or repair a log's last line); return 'no jobs' when the directory is missing or holds no job.
- In scripts/argus.py add a 'list' subcommand (no positional arguments) that prints the result using --jobs-dir and returns 0 before loading config; update the module docstring.

Risks:
- Reusing spent_nano as is builds an EventLog, which can append a newline to an events.jsonl that ends mid-line, so the command would change a file.
- Job.lock() or open_job would create .lock / refuse a busy job; list must not use them.
- A job with a missing 'stages' key, a stage with no events.jsonl yet, or a call cut off by a crash must still be summed as status does.
- Non-UTF-8 bytes or an empty job.json must give 'unreadable', not a traceback; entries that are files or directories without job.json must be ignored.

## Scope

Writable: `router/job.py`, `scripts/argus.py`

Protected: `tests/**`, `conftest.py`, `harness/**`, `acceptance/**`, `codetask/**`, `fixtures/**`, `config.yaml`

No scope warnings.

## Validations

- `target`: `python -m pytest tests/test_argus_list.py`, at least 7 tests, environment `argus`; required new tests: 7, required existing tests: 0
  - new: `tests/test_argus_list.py::test_lists_jobs_sorted_with_state_spend_and_cap`
  - new: `tests/test_argus_list.py::test_unreadable_job_json_is_reported_and_the_others_still_listed`
  - new: `tests/test_argus_list.py::test_no_jobs[missing]`
  - new: `tests/test_argus_list.py::test_no_jobs[empty]`
  - new: `tests/test_argus_list.py::test_no_jobs[only_non_jobs]`
  - new: `tests/test_argus_list.py::test_list_changes_nothing_not_even_a_log_cut_mid_line`
  - new: `tests/test_argus_list.py::test_list_works_while_another_command_holds_the_job_lock`

Budget profile for the agent: `large`

Tools added for the agent: `edit_file`, `search_files`

## New tests

### `tests/test_argus_list.py`

On the code as it is now, validation `target`: `test_lists_jobs_sorted_with_state_spend_and_cap` FAIL, `test_unreadable_job_json_is_reported_and_the_others_still_listed` FAIL, `test_no_jobs[missing]` FAIL, `test_no_jobs[empty]` FAIL, `test_no_jobs[only_non_jobs]` FAIL, `test_list_changes_nothing_not_even_a_log_cut_mid_line` FAIL, `test_list_works_while_another_command_holds_the_job_lock` FAIL

Why they fail now (test output; check that this is the behaviour to fix):

```text
tests/test_argus_list.py:78: in test_lists_jobs_sorted_with_state_spend_and_cap
E   assert 2 == 0
============================== 7 failed in Xs ===============================
```

The file:

```python
"""argus list: one line per job in the jobs directory, read-only."""
import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent

pytestmark = pytest.mark.skipif(sys.platform == "win32", reason="flock needs posix")


def load_cli():
    sys.path.insert(0, str(ROOT / "scripts"))
    spec = importlib.util.spec_from_file_location("argus_cli_list", ROOT / "scripts" / "argus.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def run_list(jobs_dir, capsys):
    mod = load_cli()
    try:
        rc = mod.main(["--jobs-dir", str(jobs_dir), "list"])
    except SystemExit as e:
        rc = e.code
    return rc, capsys.readouterr().out


def started(cid, worst_nano):
    return {"event": "llm_call_started", "call_id": cid, "worst_tokens": 100, "worst_usd_nano": worst_nano}


def final(cid, nano):
    return {"event": "llm_call", "call_id": cid, "status": "ok", "tokens": 10, "usd_nano": nano}


def write_events(jobs, job_id, run_id, events, tail=""):
    path = jobs / job_id / "runs" / run_id / "events.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(e) + "\n" for e in events) + tail, encoding="utf-8")
    return path


def write_job(jobs, job_id, state, max_usd, stages=None):
    data = {"job": job_id, "kind": "code", "state": state, "max_usd": max_usd,
            "inputs": {"repo": "/r", "commit": "HEAD", "issue": "x", "exclude": []}, "approval": None, "log": []}
    if stages is not None:
        data["stages"] = stages
    (jobs / job_id).mkdir(parents=True, exist_ok=True)
    (jobs / job_id / "job.json").write_text(json.dumps(data), encoding="utf-8")


def stage(job_id, sid, kind):
    return {"kind": kind, "run_id": f"{job_id}-{sid}", "cap_usd": 0.5}


def test_lists_jobs_sorted_with_state_spend_and_cap(tmp_path, capsys):
    jobs = tmp_path / "jobs"
    # jb: two stages, 1.234 + 0.5 = 1.734 spent
    write_job(jobs, "jb_two", "REVIEW_READY", 2.5,
              {"d1": stage("jb_two", "d1", "draft"), "a1": stage("jb_two", "a1", "agent")})
    write_events(jobs, "jb_two", "jb_two-d1", [started("c1", 900_000_000), final("c1", 1_234_000_000)])
    write_events(jobs, "jb_two", "jb_two-a1", [started("c2", 700_000_000), final("c2", 500_000_000)])
    # ja: no "stages" key at all
    write_job(jobs, "ja_new", "NEW", 1)
    # jc: a stage with no events yet, and a stage with a call cut off by a crash (worst case 0.25 counts)
    write_job(jobs, "jc_crash", "AGENT_RUNNING", 0.456,
              {"d1": stage("jc_crash", "d1", "draft"), "a1": stage("jc_crash", "a1", "agent")})
    write_events(jobs, "jc_crash", "jc_crash-d1", [started("c3", 250_000_000)])
    # entries that are not jobs
    (jobs / "jz_file").write_text("not a job")
    (jobs / "notes").mkdir()
    (jobs / "notes" / "readme.txt").write_text("x")
    (jobs / "jy_norecord" / "runs").mkdir(parents=True)
    rc, out = run_list(jobs, capsys)
    assert rc == 0
    assert out == ("ja_new NEW spent $0.0000 of $1.00\n"
                   "jb_two REVIEW_READY spent $1.7340 of $2.50\n"
                   "jc_crash AGENT_RUNNING spent $0.2500 of $0.46\n")


def test_unreadable_job_json_is_reported_and_the_others_still_listed(tmp_path, capsys):
    jobs = tmp_path / "jobs"
    write_job(jobs, "jaa_ok", "DRAFT_FAILED", 1.0)
    write_job(jobs, "jzz_ok", "REJECTED", 3.0)
    (jobs / "jb_badjson").mkdir()
    (jobs / "jb_badjson" / "job.json").write_text('{"job": "jb_badjson", "state": ', encoding="utf-8")
    (jobs / "jc_empty").mkdir()
    (jobs / "jc_empty" / "job.json").write_text("")
    (jobs / "jd_binary").mkdir()
    (jobs / "jd_binary" / "job.json").write_bytes(b"\xff\xfe\x00\x9f not utf-8")
    rc, out = run_list(jobs, capsys)
    assert rc == 0
    assert out == ("jaa_ok DRAFT_FAILED spent $0.0000 of $1.00\n"
                   "jb_badjson unreadable\n"
                   "jc_empty unreadable\n"
                   "jd_binary unreadable\n"
                   "jzz_ok REJECTED spent $0.0000 of $3.00\n")


def make_missing(tmp_path):
    return tmp_path / "nowhere"


def make_empty(tmp_path):
    d = tmp_path / "jobs"
    d.mkdir()
    return d


def make_only_non_jobs(tmp_path):
    d = tmp_path / "jobs"
    (d / "notes").mkdir(parents=True)
    (d / "stray.txt").write_text("x")
    (d / "jx_no_record" / "runs").mkdir(parents=True)
    return d


@pytest.mark.parametrize("make", [make_missing, make_empty, make_only_non_jobs],
                         ids=["missing", "empty", "only_non_jobs"])
def test_no_jobs(tmp_path, capsys, make):
    rc, out = run_list(make(tmp_path), capsys)
    assert rc == 0
    assert out == "no jobs\n"


def snapshot(root):
    return {str(p.relative_to(root)): (p.read_bytes() if p.is_file() else None) for p in sorted(root.rglob("*"))}


def test_list_changes_nothing_not_even_a_log_cut_mid_line(tmp_path, capsys):
    jobs = tmp_path / "jobs"
    write_job(jobs, "jq_cut", "AGENT_RUNNING", 1.0, {"a1": stage("jq_cut", "a1", "agent")})
    # the process died mid-write: the last line is cut and there is no final newline
    write_events(jobs, "jq_cut", "jq_cut-a1", [started("c1", 300_000_000), final("c1", 100_000_000)],
                 tail='{"event": "llm_call_started", "call_id": "c2", "wor')
    write_job(jobs, "jr_other", "NEW", 2.0)
    (jobs / "jb_bad").mkdir()
    (jobs / "jb_bad" / "job.json").write_text("{")
    before = snapshot(jobs)
    rc, out = run_list(jobs, capsys)
    assert rc == 0
    assert out == ("jb_bad unreadable\n"
                   "jq_cut AGENT_RUNNING spent $0.1000 of $1.00\n"
                   "jr_other NEW spent $0.0000 of $2.00\n")
    assert snapshot(jobs) == before          # no .lock, no repaired log, no new directory, no rewritten job.json


def test_list_works_while_another_command_holds_the_job_lock(tmp_path, capsys):
    sys.path.insert(0, str(ROOT))
    from router import job as rj
    jobs = tmp_path / "jobs"
    write_job(jobs, "jl_busy", "AGENT_RUNNING", 1.5)
    with rj.Job(jobs / "jl_busy").lock():     # e.g. an agent stage running in another terminal
        rc, out = run_list(jobs, capsys)
    assert rc == 0
    assert out == "jl_busy AGENT_RUNNING spent $0.0000 of $1.50\n"

```

## Not verified automatically

- The listing code lives in router/job.py and the command in scripts/argus.py (tests only exercise the CLI entry point main(['--jobs-dir', d, 'list']))
- Docstring/usage text updates for the new command
- Behaviour for job.json that is valid JSON but lacks 'state' or 'max_usd', or is not an object, is not specified and not tested

## Cost

Drafter: $0.1392, 6 model calls, 1 submits, 5 steps (ended: submitted).

## Approve

`approve_draft.py` checks the draft again under your task name, issue, cap and attempt limit, and publishes it only with `--approve`. Without a reference patch the task is recorded as `feasibility: unproven`; with one (`--reference-patch <patch>` instead of `--no-reference`) it is proven before the agent runs.

```bash
python scripts/approve_draft.py --draft runs/j20261022_193531_259d-d1/draft.json --task <name> --issue-file runs/j20261022_193531_259d-d1/issue.txt --max-usd <cap> --max-iterations <n> --no-reference
```
