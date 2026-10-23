# Draft review: `base` (j20261023_062122_c7a4-d1)

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
- Add a read-only `list` function in router/job.py that walks the jobs directory (default JOBS) and, for every directory entry that contains a job.json, produces one line "<job id> <state> spent $<spent:.4f> of $<cap:.2f>" using job.data['state'] and job.data['max_usd'] and spent_nano(job) for spent, so the figure is the one status reports.
- Treat a job.json that cannot be read or parsed (OSError / ValueError / JSONDecodeError) as the line "<directory name> unreadable" and keep listing the other jobs.
- Sort the lines by job id, return exactly "no jobs" when the jobs directory does not exist or holds no job, and never call Job.lock() or write anything.
- Add the `list` subparser to scripts/argus.py, call the router function with the global --jobs-dir and print its result, returning exit code 0.

Risks:
- Taking the job's flock (or creating a .lock file) while listing, so a running job is hidden or a JobBusy is raised.
- Letting one broken job.json (invalid JSON, undecodable bytes, missing keys) raise and stop the whole listing instead of printing the unreadable line.
- Crashing or printing something other than exactly "no jobs" when the jobs directory is missing or empty.
- Printing money with the wrong precision (2 decimals for spent, 4 for the cap) or reading the cap/spent from the wrong place.
- Sorting by creation order or by dict order instead of by job id, and computing spent differently from status (e.g. from the stage's usd field instead of the run ledgers).
- Reusing status/open_job in a way that needs a JOB_ID match or the draft of an AWAITING_APPROVAL job, so some jobs break the listing.

## Scope

Writable: `router/job.py`, `scripts/argus.py`

Protected: `tests/**`, `fixtures/**`, `conftest.py`

No scope warnings.

## Validations

- `target`: `python -m pytest tests/test_argus_list.py`, at least 6 tests, environment `argus`; required new tests: 6, required existing tests: 0
  - new: `tests/test_argus_list.py::test_list_prints_one_line_per_job_sorted_by_job_id`
  - new: `tests/test_argus_list.py::test_list_ignores_entries_that_are_not_jobs`
  - new: `tests/test_argus_list.py::test_list_marks_a_job_json_that_is_not_valid_json`
  - new: `tests/test_argus_list.py::test_list_marks_a_job_json_it_cannot_read`
  - new: `tests/test_argus_list.py::test_list_says_no_jobs_for_a_missing_or_empty_jobs_dir`
  - new: `tests/test_argus_list.py::test_list_takes_no_lock_and_changes_nothing`

Budget profile for the agent: `large_usd`

Tools added for the agent: `edit_file`, `search_files`

## New tests

### `tests/test_argus_list.py`

On the code as it is now, validation `target`: `test_list_prints_one_line_per_job_sorted_by_job_id` FAIL, `test_list_ignores_entries_that_are_not_jobs` FAIL, `test_list_marks_a_job_json_that_is_not_valid_json` FAIL, `test_list_marks_a_job_json_it_cannot_read` FAIL, `test_list_says_no_jobs_for_a_missing_or_empty_jobs_dir` FAIL, `test_list_takes_no_lock_and_changes_nothing` FAIL

Why they fail now (test output; check that this is the behaviour to fix):

```text
tests/test_argus_list.py:51: in run_list
E   AssertionError: `argus list` is not a command: 2
========================= 6 failed, 1 passed in Xs ==========================
```

The file:

```python
"""`argus list` (router/job.py, scripts/argus.py): every job in the jobs directory on one line, sorted by job id.

The jobs are built by hand here - a job.json plus the ledgers of its stage runs under runs/ - so no model, no
sandbox and no git is needed: `list` reads only what `status` reads."""
import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from router import job as rj  # noqa: E402


# ---- the jobs on disk ---------------------------------------------------------------------------------------------

def write_ledger(run_dir, usd_nano):
    """One finished model call in a stage's ledger: reconcile_ledger charges its usd_nano (as status counts it)."""
    run_dir.mkdir(parents=True, exist_ok=True)
    events = [{"event": "llm_call_started", "call_id": "c1", "worst_tokens": 100, "worst_usd_nano": usd_nano},
              {"event": "llm_call", "call_id": "c1", "status": "ok", "tokens": 100, "usd_nano": usd_nano}]
    (run_dir / "events.jsonl").write_text("\n".join(json.dumps(e) for e in events) + "\n", encoding="utf-8")


def write_job(jobs_dir, job_id, *, state, max_usd, stages=(), ledgers=()):
    """jobs/<job_id>/job.json (state, max_usd, stages) plus the ledgers of its stage runs."""
    job = Path(jobs_dir) / job_id
    (job / "runs").mkdir(parents=True, exist_ok=True)
    data = {"job": job_id, "kind": "code", "state": state, "max_usd": max_usd,
            "inputs": {"repo": "/nowhere/repo", "commit": "HEAD"},
            "stages": {sid: {"kind": "draft", "run_id": run_id, "cap_usd": 0.5} for sid, run_id in stages}}
    (job / "job.json").write_text(json.dumps(data), encoding="utf-8")
    for run_id, usd_nano in ledgers:
        write_ledger(job / "runs" / run_id, usd_nano)
    return job


def snapshot(root):
    """Every path under root and the bytes of every file: what a read-only command must leave untouched."""
    return {str(p.relative_to(root)): (p.read_bytes() if p.is_file() else None)
            for p in sorted(Path(root).rglob("*"))}


def run_list(cli, jobs_dir, capsys):
    """(exit code, the lines `argus list --jobs-dir <jobs_dir>` printed)."""
    try:
        rc = cli.main(["--jobs-dir", str(jobs_dir), "list"])
    except SystemExit as e:                       # argparse: `list` is not a command
        raise AssertionError(f"`argus list` is not a command: {e}") from None
    return rc, capsys.readouterr().out.splitlines()


import pytest  # noqa: E402


@pytest.fixture(scope="module")
def cli():
    """scripts/argus.py as a module, the way `python scripts/argus.py ... list` runs it."""
    spec = importlib.util.spec_from_file_location("argus_cli_list", ROOT / "scripts" / "argus.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ---- what `argus list` prints ------------------------------------------------------------------------------------

def test_list_prints_one_line_per_job_sorted_by_job_id(cli, tmp_path, capsys):
    """One line per job, sorted by job id, whatever order they were created in; spent is the stage ledgers' sum."""
    jobs = tmp_path / "jobs"
    write_job(jobs, "jb", state="AGENT_RUNNING", max_usd=0.5, stages=[("a1", "jb-a1")],
              ledgers=[("jb-a1", 250_000_000)])
    write_job(jobs, "ja", state="AWAITING_APPROVAL", max_usd=1, stages=[("d1", "ja-d1"), ("d2", "ja-d2")],
              ledgers=[("ja-d1", 125_000_000), ("ja-d2", 250_000_000)])
    write_job(jobs, "jc", state="BLOCKED", max_usd=2.5)
    rc, lines = run_list(cli, jobs, capsys)
    assert rc == 0
    assert lines == ["ja AWAITING_APPROVAL spent $0.3750 of $1.00",
                     "jb AGENT_RUNNING spent $0.2500 of $0.50",
                     "jc BLOCKED spent $0.0000 of $2.50"]


def test_list_ignores_entries_that_are_not_jobs(cli, tmp_path, capsys):
    """Only a directory that contains a job.json is a job; anything else in the jobs directory is ignored."""
    jobs = tmp_path / "jobs"
    write_job(jobs, "ja", state="NEW", max_usd=1.0)
    (jobs / "notes.txt").write_text("not a job\n", encoding="utf-8")
    (jobs / "job.json").write_text("{}\n", encoding="utf-8")
    (jobs / "empty_dir").mkdir()
    (jobs / "runs").mkdir()
    rc, lines = run_list(cli, jobs, capsys)
    assert (rc, lines) == (0, ["ja NEW spent $0.0000 of $1.00"])


def test_list_marks_a_job_json_that_is_not_valid_json(cli, tmp_path, capsys):
    """A job.json that is not valid JSON gives '<directory name> unreadable', and the other jobs are still listed."""
    jobs = tmp_path / "jobs"
    write_job(jobs, "ja", state="DRAFTING", max_usd=1.0, stages=[("d1", "ja-d1")],
              ledgers=[("ja-d1", 5_000_000)])
    bad = jobs / "jb"
    bad.mkdir(parents=True)
    (bad / "job.json").write_text("{ this is not json", encoding="utf-8")
    write_job(jobs, "jd", state="REVIEW_READY", max_usd=0.75)
    rc, lines = run_list(cli, jobs, capsys)
    assert (rc, lines) == (0, ["ja DRAFTING spent $0.0050 of $1.00",
                               "jb unreadable",
                               "jd REVIEW_READY spent $0.0000 of $0.75"])


def test_list_marks_a_job_json_it_cannot_read(cli, tmp_path, capsys):
    """A job.json that cannot be read as text gives '<directory name> unreadable' too, and listing goes on."""
    jobs = tmp_path / "jobs"
    write_job(jobs, "ja", state="DRAFTING", max_usd=1.0)
    weird = jobs / "jc"
    weird.mkdir(parents=True)
    (weird / "job.json").write_bytes(b"\xff\xfe\x00\x01 not text")
    write_job(jobs, "jd", state="REVIEW_READY", max_usd=0.75)
    rc, lines = run_list(cli, jobs, capsys)
    assert (rc, lines) == (0, ["ja DRAFTING spent $0.0000 of $1.00",
                               "jc unreadable",
                               "jd REVIEW_READY spent $0.0000 of $0.75"])


def test_list_says_no_jobs_for_a_missing_or_empty_jobs_dir(cli, tmp_path, capsys):
    """A jobs directory that does not exist, or holds no job, prints exactly 'no jobs' and exits 0."""
    missing = tmp_path / "no_such_dir"
    assert not missing.exists()
    assert run_list(cli, missing, capsys) == (0, ["no jobs"])
    empty = tmp_path / "jobs"
    empty.mkdir()
    (empty / "notes.txt").write_text("x", encoding="utf-8")
    (empty / "not_a_job").mkdir()
    assert run_list(cli, empty, capsys) == (0, ["no jobs"])


def test_list_takes_no_lock_and_changes_nothing(cli, tmp_path, capsys):
    """A job another command holds the lock of is still listed: `list` takes no lock and writes nothing."""
    import fcntl
    jobs = tmp_path / "jobs"
    job = write_job(jobs, "ja", state="AGENT_RUNNING", max_usd=1.0, stages=[("a1", "ja-a1")],
                    ledgers=[("ja-a1", 100_000_000)])
    fd = __import__("os").open(job / ".lock", __import__("os").O_RDWR | __import__("os").O_CREAT, 0o644)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)          # e.g. the agent's stage running elsewhere
        before = snapshot(jobs)
        rc, lines = run_list(cli, jobs, capsys)
        after = snapshot(jobs)
    finally:
        __import__("os").close(fd)
    assert rc == 0
    assert lines == ["ja AGENT_RUNNING spent $0.1000 of $1.00"]
    assert after == before


# ---- what `list` counts, unchanged -------------------------------------------------------------------------------

def test_status_reports_the_same_spend_the_ledgers_record(tmp_path):
    """The spend `list` shows is the one status shows: the stage runs' ledgers, summed (this already holds)."""
    jobs = tmp_path / "jobs"
    write_job(jobs, "ja", state="DRAFTING", max_usd=1.0, stages=[("d1", "ja-d1"), ("d2", "ja-d2")],
              ledgers=[("ja-d1", 125_000_000), ("ja-d2", 250_000_000)])
    assert "money: cap $1.00, spent $0.3750" in rj.status("ja", jobs_dir=jobs)

```

## Not verified automatically

- No existing test can serve as a regression run in the sandbox: tests/test_router.py is the only test of router/job.py and scripts/argus.py, and every one of its tests builds a git repository through subprocess git, which the sandbox does not have. The new file's test_status_reports_the_same_spend_the_ledgers_record runs in the same validation and pins the status spend figure (money: cap $1.00, spent $0.3750) that `list` must report, so a fix that changes how status counts spend is caught there.
- The default of --jobs-dir (jobs/ inside the Argus checkout) is not exercised: the tests pass --jobs-dir explicitly, because creating jobs/ in the repository under test would be intrusive.
- The process exit status of `python scripts/argus.py list` in a shell is not run (main() is called in-process); the tests do check that main() returns 0.
- What `list` should print for a job.json that is valid JSON but lacks 'state' or 'max_usd', or holds a non-numeric max_usd, is not specified by the issue and is not tested.
- That `argus list --help` documents the command, and that it appears in the module docstring, are not tested.

## Cost

Drafter: $0.0482, 13 model calls, 2 submits, 12 steps (ended: submitted).

## Approve

`approve_draft.py` checks the draft again under your task name, issue, cap and attempt limit, and publishes it only with `--approve`. Without a reference patch the task is recorded as `feasibility: unproven`; with one (`--reference-patch <patch>` instead of `--no-reference`) it is proven before the agent runs.

```bash
python scripts/approve_draft.py --draft runs/j20261023_062122_c7a4-d1/draft.json --task <name> --issue-file runs/j20261023_062122_c7a4-d1/issue.txt --max-usd <cap> --max-iterations <n> --no-reference
```
