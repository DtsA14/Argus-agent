# Draft review: `base` (j20261023_104529_ca7d-d1)

Status: **DRAFTED** (a draft passed its check)

Written by the harness from the draft and its check. The draft itself was written by a model: read the tests. A passing baseline shows only that the new tests fail now, not that they test the right thing.

## Issue

```text
scripts/pilot_report.py reports success_rate as done / (runs_total - no_result): a run that left no result (NO_RESULT)
is dropped from the denominator, so a run that died looks like neither a success nor a failure.

Keep success_rate exactly as it is, and add one key to the report, right after it:

  "success_rate_all": done / runs_total, rounded to 4 decimals like success_rate, or null when runs_total is 0

so the report shows both. Nothing else in the report changes. tests/test_pilot_report.py compares the whole report
with one it computes itself from the issue's formulas, so it must be updated to expect the new key with that formula.
```

## Plan

Files: `scripts/pilot_report.py`

Steps:
- In build(), compute the rate over every run as round(len(done) / total, 4) when total is not 0, else None.
- Add the key "success_rate_all" to the returned dict immediately after "success_rate", whose expression stays exactly as it is.
- Change nothing else: no other key, no other ordering, no other value.

Risks:
- Putting success_rate_all anywhere but right after success_rate (the test pins the key order).
- Changing success_rate itself, e.g. switching its denominator to runs_total.
- Getting the null branch wrong (must be checked against total, not against total - no_result, and must not divide by zero).
- Rounding the new rate differently from success_rate (round(..., 4)).
- Touching the tests or any other report key while editing.

## Scope

Writable: `scripts/pilot_report.py`

Protected: `tests/**`, `evals/**`, `fixtures/**`, `conftest.py`, `scripts/audit_run.py`, `scripts/failure_trace.py`

No scope warnings.

## Validations

- `target`: `python -m pytest tests/test_pilot_report_all.py`, at least 5 tests, environment `argus`; required new tests: 5, required existing tests: 0
  - new: `tests/test_pilot_report_all.py::test_a_run_without_a_result_counts_against_success_rate_all`
  - new: `tests/test_pilot_report_all.py::test_success_rate_all_is_rounded_to_four_decimals_over_seven_runs`
  - new: `tests/test_pilot_report_all.py::test_success_rate_all_comes_right_after_success_rate_and_nothing_else_is_added`
  - new: `tests/test_pilot_report_all.py::test_with_no_done_run_both_rates_are_zero`
  - new: `tests/test_pilot_report_all.py::test_a_report_of_only_runs_without_a_result_has_no_success_rate`
- `report`: `python -m pytest tests/test_pilot_report.py`, at least 17 tests, environment `argus`; required new tests: 0, required existing tests: 6
  - existing: `tests/test_pilot_report.py::test_the_report_over_seven_kinds_of_run`
  - existing: `tests/test_pilot_report.py::test_the_report_with_supervision_minutes`
  - existing: `tests/test_pilot_report.py::test_missing_minutes_are_null_and_a_zero_is_data`
  - existing: `tests/test_pilot_report.py::test_no_run_done`
  - existing: `tests/test_pilot_report.py::test_no_cost_known`
  - existing: `tests/test_pilot_report.py::test_only_runs_without_a_result`
- `regression`: `python -m pytest tests/test_run_inspectors.py`, at least 14 tests, environment `argus`; required new tests: 0, required existing tests: 14
  - existing: `tests/test_run_inspectors.py::test_audit_run_still_prints_what_it_always_printed[f1]`
  - existing: `tests/test_run_inspectors.py::test_audit_run_still_prints_what_it_always_printed[f2]`
  - existing: `tests/test_run_inspectors.py::test_audit_run_still_prints_what_it_always_printed[f3]`
  - existing: `tests/test_run_inspectors.py::test_audit_run_still_prints_what_it_always_printed[f5]`
  - existing: `tests/test_run_inspectors.py::test_audit_run_still_prints_what_it_always_printed[f8]`
  - existing: `tests/test_run_inspectors.py::test_failure_trace_still_prints_what_it_always_printed[f1]`
  - existing: `tests/test_run_inspectors.py::test_failure_trace_still_prints_what_it_always_printed[f2]`
  - existing: `tests/test_run_inspectors.py::test_failure_trace_still_prints_what_it_always_printed[f3]`
  - existing: `tests/test_run_inspectors.py::test_failure_trace_still_prints_what_it_always_printed[f5]`
  - existing: `tests/test_run_inspectors.py::test_failure_trace_still_prints_what_it_always_printed[f8]`
  - existing: `tests/test_run_inspectors.py::test_failure_trace_still_prints_what_it_always_printed[wrap]`
  - existing: `tests/test_run_inspectors.py::test_a_cut_line_in_the_middle_of_the_log_adds_one_line_and_changes_nothing_else`
  - existing: `tests/test_run_inspectors.py::test_a_run_blocked_before_any_model_call_is_audited`
  - existing: `tests/test_run_inspectors.py::test_a_directory_without_a_result_is_reported_and_the_next_one_is_still_traced`

Budget profile for the agent: `large_usd`

Tools added for the agent: none (it rewrites whole files with WriteFile)

## New tests

### `tests/test_pilot_report_all.py`

On the code as it is now, validation `target`: `test_a_run_without_a_result_counts_against_success_rate_all` FAIL, `test_success_rate_all_is_rounded_to_four_decimals_over_seven_runs` FAIL, `test_success_rate_all_comes_right_after_success_rate_and_nothing_else_is_added` FAIL, `test_with_no_done_run_both_rates_are_zero` FAIL, `test_a_report_of_only_runs_without_a_result_has_no_success_rate` FAIL

Why they fail now (test output; check that this is the behaviour to fix):

```text
tests/test_pilot_report_all.py:57: in test_with_no_done_run_both_rates_are_zero
E   AssertionError: assert None == 0.0
E    +  where None = <built-in method get of dict object at 0xeb31c4888c40>('success_rate_all')
E    +    where <built-in method get of dict object at 0xeb31c4888c40> = {'runs': [{'run_id': 'f3', 'status': 'FAILED_ACCEPTANCE', 'done': False, 'attempts':...
tests/test_pilot_report_all.py:69: in test_success_rate_all_comes_right_after_success_rate_and_nothing_else_is_added
E   KeyError: 'f6a'
============================== 5 failed in Xs ===============================
```

The file:

```python
"""scripts/pilot_report.py: success_rate keeps its own denominator (runs with a result) and a new key success_rate_all,
right after it, is done / runs_total (4 decimals, like success_rate), so a run that left no result counts as not done.

The runs are the synthetic ones of tests/test_run_inspectors.py (a scripted model, an injected validation: no Docker, no
money). Every expected number below is written from the issue's formulas, not from the script."""
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_run_inspectors import build  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def runs(tmp_path_factory):
    return build(ROOT, tmp_path_factory.mktemp("runs") / "b")


def report(*args):
    return subprocess.run([sys.executable, str(ROOT / "scripts" / "pilot_report.py"), *map(str, args)], cwd=ROOT,
                          env={**os.environ, "PYTHONPATH": str(ROOT)}, capture_output=True, text=True, timeout=120)


def got(*args):
    r = report(*args)
    assert r.returncode == 0, r.stderr[-500:]
    return json.loads(r.stdout)


# ---- the new key, and the old one unchanged --------------------------------------------------------------------------

def test_a_run_without_a_result_counts_against_success_rate_all(runs):
    # f1 is DONE, f7 left no result: done over the runs with a result is 1/1, done over every run is 1/2
    g = got(runs["f1"], runs["f7"])
    assert (g.get("runs_total"), g.get("done"), g.get("no_result")) == (2, 1, 1)
    assert g.get("success_rate") == 1.0                    # unchanged: NO_RESULT stays out of this denominator
    assert g.get("success_rate_all") == 0.5                # done / runs_total


def test_success_rate_all_is_rounded_to_four_decimals_over_seven_runs(runs):
    g = got(runs["f1"], runs["f2"], runs["f3"], runs["f4"], runs["f5c"], runs["f6a"], runs["f7"])
    assert (g.get("runs_total"), g.get("done"), g.get("no_result")) == (7, 4, 1)
    assert g.get("success_rate") == 0.6667                 # 4 / (7 - 1)
    assert g.get("success_rate_all") == 0.5714             # 4 / 7, rounded like success_rate


def test_with_no_done_run_both_rates_are_zero(runs):
    g = got(runs["f3"], runs["f4"], runs["f7"])
    assert (g.get("done"), g.get("no_result")) == (0, 1)
    assert g.get("success_rate") == 0.0                    # 0 / (3 - 1)
    assert g.get("success_rate_all") == 0.0                # 0 / 3


def test_a_report_of_only_runs_without_a_result_has_no_success_rate(runs):
    g = got(runs["f7"])
    assert g.get("runs_total") == 1 and g.get("success_rate") is None      # nothing with a result
    assert g.get("success_rate_all") == 0.0                # 0 / 1: null only when runs_total is 0


# ---- one key, right after success_rate, nothing else added ----------------------------------------------------------

def test_success_rate_all_comes_right_after_success_rate_and_nothing_else_is_added(runs):
    g = got(runs["f1"], runs["f2"], runs["f3"], runs["f4"], runs["f5c"], runs["f6a"], runs["f7"])
    assert list(g) == ["runs", "runs_total", "done", "no_result", "success_rate", "success_rate_all",
                       "usd_known_total", "usd_unknown_runs", "cost_per_success", "cost_complete", "attempts",
                       "attempts_distribution", "supervision", "events_skipped"]

```

## Existing tests changed

The draft changes 1 existing test file(s). The harness checked that no old test is lost unless listed in removed, that no test function changes unless it is required or listed in modified, and that no test of these files is skipped or xfail unless it was before. It cannot tell whether a test got weaker: read the diff.

**Warnings (K3):**

- tests/test_pilot_report.py changes module-level code (helpers, fixtures, imports or class bodies): read it, it is not held to the old version

### `tests/test_pilot_report.py`


Diff from the intake version:

```diff
--- a/tests/test_pilot_report.py
+++ b/tests/test_pilot_report.py
@@ -3,7 +3,8 @@
 The runs are the synthetic ones of tests/test_run_inspectors.py (build(): a scripted model, an injected validation; no Docker,
 no money) plus copies with result.json changed. Expected reports are written here from the definitions of the issue: statuses,
 attempts and calls as literals; each run's usd_billed is read from its own result.json (an input of the report) and every
-aggregate is computed below with the issue's formulas, independently of the script."""
+aggregate is computed below with the issue's formulas, independently of the script. success_rate is done / (runs_total -
+no_result) and success_rate_all, the key right after it, is done / runs_total."""
 import json
 import os
 import shutil
@@ -65,6 +66,7 @@
     mins = [r["supervision_minutes"] for r in rows if r["supervision_minutes"] is not None]
     return {"runs": rows, "runs_total": len(rows), "done": len(done), "no_result": no_result,
             "success_rate": round(len(done) / (len(rows) - no_result), 4) if len(rows) - no_result else None,
+            "success_rate_all": round(len(done) / len(rows), 4) if len(rows) else None,
             "usd_known_total": round(total_nano / 1e9, 6), "usd_unknown_runs": len(rows) - len(known),
             "cost_per_success": round(total_nano / 1e9 / done_known, 6) if done_known else None,
             "cost_complete": len(known) == len(rows),
@@ -101,9 +103,11 @@
     want = expected(the_set(runs))
     assert r.stdout == text(want)
     # the facts the definitions turn on, spelled out
-    assert (want["done"], want["no_result"], want["success_rate"], want["usd_unknown_runs"]) == (4, 1, 0.6667, 2)
+    assert (want["done"], want["no_result"], want["success_rate"], want["success_rate_all"],
+            want["usd_unknown_runs"]) == (4, 1, 0.6667, 0.5714, 2)
     assert want["attempts"] == {"mean": 1.25, "median": 1.0} and want["attempts_distribution"] == {"0": 1, "1": 3, "2": 2}
     assert want["cost_complete"] is False and want["events_skipped"] == 1
+    assert list(want)[5] == "success_rate_all"                                  # right after success_rate
 
 
 def test_the_report_with_supervision_minutes(runs, tmp_path):
@@ -134,6 +138,7 @@
                      row("f4", "BLOCKED", 0, 0, usd(runs["f4"]), True)])
     assert r.returncode == 0 and r.stdout == text(want)
     assert want["cost_per_success"] is None and want["attempts"] is None and want["success_rate"] == 0.0
+    assert want["success_rate_all"] == 0.0
 
 
 def test_no_cost_known(runs):
@@ -151,6 +156,7 @@
     want = expected([row("f7", "NO_RESULT", None, None, None, False)])
     assert r.returncode == 0 and r.stdout == text(want)
     assert want["success_rate"] is None and want["attempts_distribution"] == {}
+    assert want["success_rate_all"] == 0.0                                     # 0 / 1: null only when runs_total is 0
 
 
 # ---- refused: exit 2, one line on stderr, nothing on stdout ----------------------------------------------------------
```

## Not verified automatically

- The null branch of success_rate_all (runs_total == 0) cannot be reached through the script: with no run directory it refuses with exit 2, and every accepted argument adds a row, so runs_total is never 0. No test exercises that branch.
- Whether the report reads well for a human scanning both rates (the point of the change) is a judgement no test makes.

## Cost

Drafter: $0.0143, 8 model calls, 2 submits, 7 steps (ended: submitted).

## Approve

`approve_draft.py` checks the draft again under your task name, issue, cap and attempt limit, and publishes it only with `--approve`. Without a reference patch the task is recorded as `feasibility: unproven`; with one (`--reference-patch <patch>` instead of `--no-reference`) it is proven before the agent runs.

```bash
python scripts/approve_draft.py --draft runs/j20261023_104529_ca7d-d1/draft.json --task <name> --issue-file runs/j20261023_104529_ca7d-d1/issue.txt --max-usd <cap> --max-iterations <n> --no-reference
```
