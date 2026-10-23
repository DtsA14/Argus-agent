# Draft review: `base` (j20261023_164114_cfcb-d1)

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
- In build(), compute the all-runs rate from the total number of run directories given (len(rows)) rather than from the runs that left a result.
- Insert the key "success_rate_all" into the returned dict immediately after "success_rate", as round(len(done) / total, 4) when total is not 0 and None otherwise.
- Leave success_rate, every other key, its position and the exit-2 behaviour untouched.

Risks:
- Writing the new key beside the old one in a different order (it must be the key right after "success_rate").
- Reusing the with_result denominator (the whole point of the issue is that a NO_RESULT run is in this denominator).
- Truncating instead of rounding to 4 decimals, or returning 0 instead of null when runs_total is 0.
- Touching success_rate or other aggregates while adding the key, which the whole-report comparison tests would catch.

## Scope

Writable: `scripts/pilot_report.py`

Protected: `tests/**`, `conftest.py`, `evals/**`, `harness/**`, `acceptance/**`, `codetask/**`, `tools/**`, `models/**`, `nodes/**`, `router/**`, `runner.py`, `graph.py`, `config.yaml`, `fixtures/**`

No scope warnings.

## Validations

- `target`: `python -m pytest tests/test_pilot_report_all.py`, at least 4 tests, environment `argus`; required new tests: 4, required existing tests: 0
  - new: `tests/test_pilot_report_all.py::test_a_run_that_left_no_result_counts_in_the_denominator_of_the_all_rate`
  - new: `tests/test_pilot_report_all.py::test_the_all_rate_is_rounded_to_four_decimals`
  - new: `tests/test_pilot_report_all.py::test_the_key_goes_right_after_success_rate_and_the_rest_of_the_report_is_unchanged`
  - new: `tests/test_pilot_report_all.py::test_when_every_run_left_no_result_the_all_rate_is_zero`
- `changed_report`: `python -m pytest tests/test_pilot_report.py`, at least 17 tests, environment `argus`; required new tests: 0, required existing tests: 6
  - existing: `tests/test_pilot_report.py::test_the_report_over_seven_kinds_of_run`
  - existing: `tests/test_pilot_report.py::test_the_report_with_supervision_minutes`
  - existing: `tests/test_pilot_report.py::test_missing_minutes_are_null_and_a_zero_is_data`
  - existing: `tests/test_pilot_report.py::test_no_run_done`
  - existing: `tests/test_pilot_report.py::test_no_cost_known`
  - existing: `tests/test_pilot_report.py::test_only_runs_without_a_result`
- `regression`: `python -m pytest tests/test_run_inspectors.py tests/test_run_inspectors_data.py tests/test_eval_cost.py tests/test_run_stats.py`, at least 30 tests, environment `argus`; required new tests: 0, required existing tests: 8
  - existing: `tests/test_run_inspectors.py::test_a_cut_line_in_the_middle_of_the_log_adds_one_line_and_changes_nothing_else`
  - existing: `tests/test_run_inspectors.py::test_a_run_blocked_before_any_model_call_is_audited`
  - existing: `tests/test_eval_cost.py::test_an_unknown_cost_stops_the_scripted_modes_too`
  - existing: `tests/test_eval_cost.py::test_known_costs_keep_the_eval_going_and_the_total_is_complete`
  - existing: `tests/test_eval_cost.py::test_a_cost_is_shown_as_n_a_when_it_is_not_known`
  - existing: `tests/test_run_stats.py::test_a_log_without_damage_is_counted_as_before`
  - existing: `tests/test_run_stats.py::test_a_line_cut_short_in_the_middle_is_skipped`
  - existing: `tests/test_run_stats.py::test_every_line_that_is_not_json_is_skipped_and_blank_lines_too`

Budget profile for the agent: `large_usd`

Tools added for the agent: `edit_file`, `search_files`

## New tests

### `tests/test_pilot_report_all.py`

On the code as it is now, validation `target`: `test_a_run_that_left_no_result_counts_in_the_denominator_of_the_all_rate` FAIL, `test_the_all_rate_is_rounded_to_four_decimals` FAIL, `test_the_key_goes_right_after_success_rate_and_the_rest_of_the_report_is_unchanged` FAIL, `test_when_every_run_left_no_result_the_all_rate_is_zero` FAIL

Why they fail now (test output; check that this is the behaviour to fix):

```text
tests/test_pilot_report_all.py:64: in test_the_all_rate_is_rounded_to_four_decimals
E   AssertionError: assert None == 0.6667
E    +  where None = <built-in method get of dict object at 0xed6f5fd6fd80>('success_rate_all')
E    +    where <built-in method get of dict object at 0xed6f5fd6fd80> = {'runs': [{'run_id': 'd1', 'status': 'DONE', 'done': True, 'attempts': 1, ...}, {'ru...
tests/test_pilot_report_all.py:73: in test_the_key_goes_right_after_success_rate_and_the_rest_of_the_report_is_unchanged
E   AssertionError: ['runs', 'runs_total', 'done', 'no_result', 'success_rate', 'usd_known_total', ...]
tests/test_pilot_report_all.py:90: in test_when_every_run_left_no_result_the_all_rate_is_zero
E   AssertionError: assert None == 0.0
E    +  where None = <built-in method get of dict object at 0xed6f5f83c540>('success_rate_all')
E    +    where <built-in method get of dict object at 0xed6f5f83c540> = {'runs': [{'run_id': 'n1', 'status': 'NO_RESULT', 'done': False, 'attempts': None, ....
============================== 4 failed in Xs ===============================
```

The file:

```python
"""The success rate over every run, beside the one that leaves NO_RESULT out (PENDING.md, review 2026-10-22):

  success_rate     = done / (runs_total - no_result), round 4, null when the divisor is 0   (unchanged)
  success_rate_all = done / runs_total, round 4, null when runs_total is 0                 (new, the key right after it)

A run directory here is what scripts/pilot_report.py reads: result.json (status, attempts, llm_calls, usd_billed,
usd_complete) and events.jsonl. No model, no sandbox, no Docker. A run with no result.json is a run that left no result
(NO_RESULT); no run at all is refused by the script, so runs_total is never 0 from the command line.
"""
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent

REPORT_KEYS = ["runs", "runs_total", "done", "no_result", "success_rate", "usd_known_total", "usd_unknown_runs",
               "cost_per_success", "cost_complete", "attempts", "attempts_distribution", "supervision", "events_skipped"]


def run_dir(base, name, status, attempts, calls, usd, complete=True):
    """One run directory. status None: a run that died and left no result.json at all."""
    d = Path(base) / name
    d.mkdir()
    (d / "events.jsonl").write_text("", encoding="utf-8")
    if status is not None:
        (d / "result.json").write_text(json.dumps({"status": status, "attempts": attempts, "llm_calls": calls,
                                                    "usd_billed": usd, "usd_complete": complete}),
                                        encoding="utf-8")
    return d


@pytest.fixture(scope="module")
def runs(tmp_path_factory):
    base = tmp_path_factory.mktemp("runs")
    return {"d1": run_dir(base, "d1", "DONE", 1, 1, 0.5),
            "d2": run_dir(base, "d2", "DONE", 2, 3, 0.25),
            "f1": run_dir(base, "f1", "FAILED_ACCEPTANCE", 2, 2, 0.125),
            "n1": run_dir(base, "n1", None, None, None, None)}          # died: no result.json


def report(*args):
    return subprocess.run([sys.executable, str(ROOT / "scripts" / "pilot_report.py"), *map(str, args)], cwd=ROOT,
                          env={**os.environ, "PYTHONPATH": str(ROOT)}, capture_output=True, text=True, timeout=120)


def test_a_run_that_left_no_result_counts_in_the_denominator_of_the_all_rate(runs):
    r = report(runs["d1"], runs["f1"], runs["n1"])
    assert r.returncode == 0, r.stderr[-500:]
    got = json.loads(r.stdout)
    assert (got["runs_total"], got["done"], got["no_result"]) == (3, 1, 1)
    assert got.get("success_rate_all") == 0.3333               # done / runs_total = 1 / 3, round 4: the dead run counts
    assert got.get("success_rate") == 0.5                      # unchanged: done / (runs_total - no_result) = 1 / 2


def test_the_all_rate_is_rounded_to_four_decimals(runs):
    r = report(runs["d1"], runs["d2"], runs["f1"])
    assert r.returncode == 0, r.stderr[-500:]
    got = json.loads(r.stdout)
    assert got.get("success_rate") == 0.6667                   # unchanged: 2 done over the 3 runs that left a result
    assert got.get("success_rate_all") == 0.6667               # 2 / 3 = 0.66666... rounded, not cut to 0.6666
    assert got.get("success_rate_all") == got.get("success_rate")   # no NO_RESULT run: the two rates agree


def test_the_key_goes_right_after_success_rate_and_the_rest_of_the_report_is_unchanged(runs):
    r = report(runs["d1"], runs["n1"])
    assert r.returncode == 0, r.stderr[-500:]
    got = json.loads(r.stdout)
    keys = list(got)
    assert "success_rate_all" in keys, keys
    assert keys == REPORT_KEYS[:5] + ["success_rate_all"] + REPORT_KEYS[5:]
    assert got["runs"] == [
        {"run_id": "d1", "status": "DONE", "done": True, "attempts": 1, "llm_calls": 1, "usd_billed": 0.5,
         "cost_known": True, "events_skipped": 0, "supervision_minutes": None},
        {"run_id": "n1", "status": "NO_RESULT", "done": False, "attempts": None, "llm_calls": None,
         "usd_billed": None, "cost_known": False, "events_skipped": 0, "supervision_minutes": None}]
    assert got.get("success_rate") == 1.0                      # unchanged: 1 done over the 1 run that left a result
    assert got.get("success_rate_all") == 0.5                  # done / runs_total = 1 / 2


def test_when_every_run_left_no_result_the_all_rate_is_zero(runs):
    r = report(runs["n1"])
    assert r.returncode == 0, r.stderr[-500:]
    got = json.loads(r.stdout)
    assert (got["runs_total"], got["done"], got["no_result"]) == (1, 0, 1)
    assert got.get("success_rate") is None                     # unchanged: the divisor runs_total - no_result is 0
    assert got.get("success_rate_all") == 0.0                  # done / runs_total = 0 / 1
    assert got.get("success_rate_all") is not None

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
@@ -3,7 +3,9 @@
 The runs are the synthetic ones of tests/test_run_inspectors.py (build(): a scripted model, an injected validation; no Docker,
 no money) plus copies with result.json changed. Expected reports are written here from the definitions of the issue: statuses,
 attempts and calls as literals; each run's usd_billed is read from its own result.json (an input of the report) and every
-aggregate is computed below with the issue's formulas, independently of the script."""
+aggregate is computed below with the issue's formulas, independently of the script. Two success rates: success_rate over the
+runs that left a result, and success_rate_all (done / runs_total) over all of them, so a run that died (NO_RESULT) is in the
+second denominator too."""
 import json
 import os
 import shutil
@@ -65,6 +67,7 @@
     mins = [r["supervision_minutes"] for r in rows if r["supervision_minutes"] is not None]
     return {"runs": rows, "runs_total": len(rows), "done": len(done), "no_result": no_result,
             "success_rate": round(len(done) / (len(rows) - no_result), 4) if len(rows) - no_result else None,
+            "success_rate_all": round(len(done) / len(rows), 4) if len(rows) else None,
             "usd_known_total": round(total_nano / 1e9, 6), "usd_unknown_runs": len(rows) - len(known),
             "cost_per_success": round(total_nano / 1e9 / done_known, 6) if done_known else None,
             "cost_complete": len(known) == len(rows),
@@ -102,6 +105,7 @@
     assert r.stdout == text(want)
     # the facts the definitions turn on, spelled out
     assert (want["done"], want["no_result"], want["success_rate"], want["usd_unknown_runs"]) == (4, 1, 0.6667, 2)
+    assert want["success_rate_all"] == 0.5714                            # 4 done over all 7 runs, the dead one included
     assert want["attempts"] == {"mean": 1.25, "median": 1.0} and want["attempts_distribution"] == {"0": 1, "1": 3, "2": 2}
     assert want["cost_complete"] is False and want["events_skipped"] == 1
 
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
+    assert want["success_rate_all"] == 0.0                                # no success out of the one run taken
 
 
 # ---- refused: exit 2, one line on stderr, nothing on stdout ----------------------------------------------------------
```

## Not verified automatically

- The null branch for runs_total == 0 cannot be reached through the command line: no run directory given is refused (exit 2, one line on stderr), so no run set makes runs_total 0 and no test can check that the new key is then null.
- The issue says nothing else in the report changes: the tests check the report's key order and the run rows, but an unrelated change to an aggregate's value is only caught where the tests happen to compare a value.

## Cost

Drafter: $0.0192, 9 model calls, 3 submits, 8 steps (ended: submitted).

## Approve

`approve_draft.py` checks the draft again under your task name, issue, cap and attempt limit, and publishes it only with `--approve`. Without a reference patch the task is recorded as `feasibility: unproven`; with one (`--reference-patch <patch>` instead of `--no-reference`) it is proven before the agent runs.

```bash
python scripts/approve_draft.py --draft runs/j20261023_164114_cfcb-d1/draft.json --task <name> --issue-file runs/j20261023_164114_cfcb-d1/issue.txt --max-usd <cap> --max-iterations <n> --no-reference
```
