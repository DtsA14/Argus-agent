# Draft review: `argus_p6` (w2b1d3)

Status: **DRAFTED** (a draft passed its check)

Written by the harness from the draft and its check. The draft itself was written by a model: read the tests. A passing baseline shows only that the new tests fail now, not that they test the right thing.

## Issue

```text
Add scripts/pilot_report.py: python scripts/pilot_report.py RUN_DIR... [--supervision FILE]. Change nothing else.
Read runs only via evals/runlog.py (read_events, read_result); cost known iff evals.score.cost_is_known(result).
Print json.dumps(obj, indent=2, ensure_ascii=False) + newline, exit 0. Keys in this order:
runs: per argument, in order: run_id (dir name), status (result status, or "NO_RESULT" if no result.json), done (status=="DONE"), attempts, llm_calls, usd_billed (as in result.json; null if NO_RESULT), cost_known (false if NO_RESULT), events_skipped (from read_events), supervision_minutes (null if none; never 0 instead).
runs_total; done; no_result;
success_rate = done/(runs_total-no_result), round 4; null if divisor 0;
usd_known_total = sum of usd_billed over cost_known runs, summed as round(x*1e9) nano-dollars, /1e9, round 6; 0.0 if none;
usd_unknown_runs = runs not cost_known;
cost_per_success = usd_known_total / runs both done and cost_known, round 6; null if divisor 0;
cost_complete = usd_unknown_runs == 0;
attempts = {mean round 3, median (statistics.median)} over done runs; null if none;
attempts_distribution = {"<attempts>": count} over runs with result.json, keys numeric order;
supervision = {runs_with_data, total, mean round 2} over runs with minutes; total, mean null if none;
events_skipped = sum.
Supervision file: JSON object {run_id: minutes}; each value int/float, not bool, finite, >= 0; each key a given run_id.
Exit 2, stdout empty, one stderr line, when: no runs ("no run directory given"); an argument not a directory or without events.jsonl (the argument and "not a run directory"); a supervision file unreadable or invalid ("supervision file" and its path).
```

## Plan

Files: `scripts/pilot_report.py`

Steps:
- Create scripts/pilot_report.py: insert the repo root in sys.path like the other scripts, parse RUN_DIR... and --supervision FILE by hand or argparse, but report usage errors as exit 2 with one stderr line and empty stdout.
- Validate every argument (directory with events.jsonl) and the supervision file (JSON object, keys are given run_ids, values int/float not bool, finite, >= 0) before printing anything.
- Per run, read result via evals.runlog.read_result and skipped count via read_events; cost_known via evals.score.cost_is_known; build the per-run rows in the specified key order.
- Compute the aggregates (success_rate, nano-dollar usd_known_total, cost_per_success, cost_complete, attempts mean/median, attempts_distribution in numeric key order, supervision, events_skipped) with the specified rounding and null rules.
- Print json.dumps(obj, indent=2, ensure_ascii=False) + newline and exit 0.

Risks:
- Dividing by zero or printing 0 where null is required (success_rate, cost_per_success, supervision total/mean, supervision_minutes).
- Wrong key order or sorting attempts_distribution keys as strings ('10' before '2').
- Counting a run with usd_complete false/missing as cost known, or summing floats instead of nano-dollars.
- Accepting bool or NaN/Infinity supervision values (json.loads accepts NaN and 1e999).
- Script fails when run as 'python scripts/pilot_report.py' because the repo root is not on sys.path.
- Writing to stdout before a later argument is found invalid.

## Scope

Writable: `scripts/pilot_report.py`

Protected: `tests/**`, `conftest.py`, `evals/**`, `harness/**`, `acceptance/**`, `codetask/**`, `fixtures/**`, `scripts/run_series.py`, `scripts/audit_run.py`, `scripts/run_eval.py`, `AGENTS.md`, `config.yaml`

No scope warnings.

## Validations

- `target`: `python -m pytest tests/test_pilot_report.py`, at least 20 tests, environment `argus`; required new tests: 20, required existing tests: 0
  - new: `tests/test_pilot_report.py::test_mixed_runs_full_report`
  - new: `tests/test_pilot_report.py::test_output_is_exactly_the_indented_dump`
  - new: `tests/test_pilot_report.py::test_success_rate_rounds_to_four_digits`
  - new: `tests/test_pilot_report.py::test_distribution_keys_in_numeric_order`
  - new: `tests/test_pilot_report.py::test_nothing_known_gives_nulls`
  - new: `tests/test_pilot_report.py::test_without_supervision_minutes_are_null_not_zero`
  - new: `tests/test_pilot_report.py::test_no_run_directory_given`
  - new: `tests/test_pilot_report.py::test_a_bad_argument_is_refused_before_any_output`
  - new: `tests/test_pilot_report.py::test_invalid_supervision_file[missing]`
  - new: `tests/test_pilot_report.py::test_invalid_supervision_file[not_json]`
  - new: `tests/test_pilot_report.py::test_invalid_supervision_file[list]`
  - new: `tests/test_pilot_report.py::test_invalid_supervision_file[bool]`
  - new: `tests/test_pilot_report.py::test_invalid_supervision_file[negative]`
  - new: `tests/test_pilot_report.py::test_invalid_supervision_file[string]`
  - new: `tests/test_pilot_report.py::test_invalid_supervision_file[null]`
  - new: `tests/test_pilot_report.py::test_invalid_supervision_file[nan]`
  - new: `tests/test_pilot_report.py::test_invalid_supervision_file[infinity]`
  - new: `tests/test_pilot_report.py::test_invalid_supervision_file[overflow]`
  - new: `tests/test_pilot_report.py::test_invalid_supervision_file[unknown_run]`
  - new: `tests/test_pilot_report.py::test_supervision_zero_and_float_are_valid`
- `regression`: `python -m pytest tests/test_eval_cost.py tests/test_run_series.py`, at least 1 tests, environment `argus`; required new tests: 0, required existing tests: 0

## New tests

### `tests/test_pilot_report.py`

On the code as it is now, validation `target`: `test_mixed_runs_full_report` FAIL, `test_output_is_exactly_the_indented_dump` FAIL, `test_success_rate_rounds_to_four_digits` FAIL, `test_distribution_keys_in_numeric_order` FAIL, `test_nothing_known_gives_nulls` FAIL, `test_without_supervision_minutes_are_null_not_zero` FAIL, `test_no_run_directory_given` FAIL, `test_a_bad_argument_is_refused_before_any_output` FAIL, `test_invalid_supervision_file[missing]` FAIL, `test_invalid_supervision_file[not_json]` FAIL, `test_invalid_supervision_file[list]` FAIL, `test_invalid_supervision_file[bool]` FAIL, `test_invalid_supervision_file[negative]` FAIL, `test_invalid_supervision_file[string]` FAIL, `test_invalid_supervision_file[null]` FAIL, `test_invalid_supervision_file[nan]` FAIL, `test_invalid_supervision_file[infinity]` FAIL, `test_invalid_supervision_file[overflow]` FAIL, `test_invalid_supervision_file[unknown_run]` FAIL, `test_supervision_zero_and_float_are_valid` FAIL

Why they fail now (test output; check that this is the behaviour to fix):

```text
tests/test_pilot_report.py:51: in refused
E   AssertionError: /usr/bin/python3: can't open file '/workspace/scripts/pilot_report.py': [Errno 2] No such file or directory
E     
============================== 20 failed in Xs ==============================
```

The file:

```python
"""scripts/pilot_report.py: a report over run directories, read only through evals/runlog.py."""
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent

TOP_KEYS = ["runs", "runs_total", "done", "no_result", "success_rate", "usd_known_total", "usd_unknown_runs",
            "cost_per_success", "cost_complete", "attempts", "attempts_distribution", "supervision",
            "events_skipped"]
RUN_KEYS = ["run_id", "status", "done", "attempts", "llm_calls", "usd_billed", "cost_known", "events_skipped",
            "supervision_minutes"]


def make_run(base, name, status="DONE", attempts=1, llm_calls=3, usd=0.1, complete=True, bad_lines=0, result=True):
    d = base / name
    d.mkdir(parents=True)
    lines = [json.dumps({"ts": 1, "event": "status", "status": status})]
    lines += ["{not json"] * bad_lines
    (d / "events.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")
    if result:
        doc = {"status": status, "attempts": attempts, "llm_calls": llm_calls, "usd_billed": usd,
               "usd_complete": complete}
        (d / "result.json").write_text(json.dumps(doc), encoding="utf-8")
    return d


def run(args):
    env = {k: v for k, v in os.environ.items() if k != "PYTHONPATH"}
    env.update(PYTHONIOENCODING="utf-8", PYTHONUTF8="1")
    return subprocess.run([sys.executable, "scripts/pilot_report.py", *map(str, args)], cwd=ROOT, env=env,
                          capture_output=True, text=True, encoding="utf-8")


def report(args):
    p = run(args)
    assert p.returncode == 0, p.stderr
    return json.loads(p.stdout), p.stdout


def refused(args, *needles):
    p = run(args)
    assert p.returncode == 2, (p.returncode, p.stderr)
    assert p.stdout == ""
    assert len(p.stderr.strip().splitlines()) == 1, p.stderr
    for n in needles:
        assert str(n) in p.stderr, p.stderr


def test_mixed_runs_full_report(tmp_path):
    a = make_run(tmp_path, "a", "DONE", attempts=1, llm_calls=4, usd=0.1234564, bad_lines=2)
    b = make_run(tmp_path, "b", "FAILED_ACCEPTANCE", attempts=3, llm_calls=9, usd=0.2)
    c = make_run(tmp_path, "c", "DONE", attempts=2, llm_calls=6, usd=0.3, complete=False)
    d = make_run(tmp_path, "d", result=False, bad_lines=1)
    e = make_run(tmp_path, "e", "DONE", attempts=4, llm_calls=5, usd=0.12)
    sup = tmp_path / "sup.json"
    sup.write_text(json.dumps({"a": 10, "b": 0, "e": 1}), encoding="utf-8")
    out, _ = report([a, b, c, d, e, "--supervision", sup])
    assert list(out) == TOP_KEYS
    assert [list(r) for r in out["runs"]] == [RUN_KEYS] * 5
    assert [r["run_id"] for r in out["runs"]] == ["a", "b", "c", "d", "e"]
    assert [r["status"] for r in out["runs"]] == ["DONE", "FAILED_ACCEPTANCE", "DONE", "NO_RESULT", "DONE"]
    assert [r["done"] for r in out["runs"]] == [True, False, True, False, True]
    assert [r["attempts"] for r in out["runs"]][:3] == [1, 3, 2]
    assert out["runs"][4]["attempts"] == 4
    assert [r["llm_calls"] for r in out["runs"]][:3] == [4, 9, 6]
    assert [r["usd_billed"] for r in out["runs"]] == [0.1234564, 0.2, 0.3, None, 0.12]
    assert [r["cost_known"] for r in out["runs"]] == [True, True, False, False, True]
    assert [r["events_skipped"] for r in out["runs"]][:4] == [2, 0, 0, 1]
    assert [r["supervision_minutes"] for r in out["runs"]] == [10, 0, None, None, 1]
    assert out["runs_total"] == 5 and out["done"] == 3 and out["no_result"] == 1
    assert out["success_rate"] == 0.75
    assert out["usd_known_total"] == 0.443456
    assert out["usd_unknown_runs"] == 2
    assert out["cost_per_success"] == 0.221728          # known total / the 2 runs that are done and cost-known
    assert out["cost_complete"] is False
    assert list(out["attempts"]) == ["mean", "median"]
    assert out["attempts"] == {"mean": 2.333, "median": 2}
    assert out["attempts_distribution"] == {"1": 1, "2": 1, "3": 1, "4": 1}
    assert list(out["supervision"]) == ["runs_with_data", "total", "mean"]
    assert out["supervision"] == {"runs_with_data": 3, "total": 11, "mean": 3.67}
    assert out["events_skipped"] == 3


def test_output_is_exactly_the_indented_dump(tmp_path):
    a = make_run(tmp_path, "ürun", "DONE", usd=0.5)
    out, text = report([a])
    assert text == json.dumps(out, indent=2, ensure_ascii=False) + "\n"
    assert "ürun" in text
    assert out["cost_complete"] is True and out["usd_unknown_runs"] == 0


def test_success_rate_rounds_to_four_digits(tmp_path):
    dirs = [make_run(tmp_path, "x1", "DONE"), make_run(tmp_path, "x2", "DONE"),
            make_run(tmp_path, "x3", "FAILED_ACCEPTANCE"), make_run(tmp_path, "x4", result=False)]
    out, _ = report(dirs)
    assert out["success_rate"] == 0.6667            # the run without result is left out of the divisor
    assert out["usd_known_total"] == 0.3            # three known runs of 0.1 each
    assert out["cost_per_success"] == 0.15          # 0.3 over the 2 runs that are done and cost-known


def test_distribution_keys_in_numeric_order(tmp_path):
    dirs = [make_run(tmp_path, "r1", attempts=10), make_run(tmp_path, "r2", attempts=2),
            make_run(tmp_path, "r3", "FAILED_ACCEPTANCE", attempts=2), make_run(tmp_path, "r4", attempts=1)]
    out, _ = report(dirs)
    assert list(out["attempts_distribution"].items()) == [("1", 1), ("2", 2), ("10", 1)]
    assert out["attempts"] == {"mean": 4.333, "median": 2}      # failed runs are not in the attempts statistics


def test_nothing_known_gives_nulls(tmp_path):
    a = make_run(tmp_path, "n1", result=False)
    b = make_run(tmp_path, "n2", result=False)
    out, _ = report([a, b])
    assert out["runs_total"] == 2 and out["done"] == 0 and out["no_result"] == 2
    assert out["success_rate"] is None
    assert out["usd_known_total"] == 0.0
    assert out["usd_unknown_runs"] == 2 and out["cost_complete"] is False
    assert out["cost_per_success"] is None
    assert out["attempts"] is None
    assert out["attempts_distribution"] == {}
    assert out["supervision"] == {"runs_with_data": 0, "total": None, "mean": None}
    assert out["events_skipped"] == 0
    assert all(r["usd_billed"] is None and r["cost_known"] is False for r in out["runs"])


def test_without_supervision_minutes_are_null_not_zero(tmp_path):
    a = make_run(tmp_path, "s1")
    sup = tmp_path / "sup.json"
    sup.write_text("{}", encoding="utf-8")
    for args in ([a], [a, "--supervision", sup]):
        out, _ = report(args)
        assert out["runs"][0]["supervision_minutes"] is None
        assert out["supervision"] == {"runs_with_data": 0, "total": None, "mean": None}


def test_supervision_zero_and_float_are_valid(tmp_path):
    a, b = make_run(tmp_path, "z1"), make_run(tmp_path, "z2")
    sup = tmp_path / "sup.json"
    sup.write_text('{"z1": 0, "z2": 2.5}', encoding="utf-8")
    out, _ = report([a, b, "--supervision", sup])
    assert [r["supervision_minutes"] for r in out["runs"]] == [0, 2.5]
    assert out["supervision"] == {"runs_with_data": 2, "total": 2.5, "mean": 1.25}


def test_no_run_directory_given(tmp_path):
    refused([], "no run directory given")
    sup = tmp_path / "sup.json"
    sup.write_text("{}", encoding="utf-8")
    refused(["--supervision", sup], "no run directory given")


def test_a_bad_argument_is_refused_before_any_output(tmp_path):
    good = make_run(tmp_path, "good")
    no_events = tmp_path / "noevents"
    no_events.mkdir()
    (no_events / "result.json").write_text("{}", encoding="utf-8")
    a_file = tmp_path / "afile"
    a_file.write_text("x", encoding="utf-8")
    for bad in (tmp_path / "missing", a_file, no_events):
        refused([good, bad], bad, "not a run directory")
        refused([bad, good], bad, "not a run directory")


SUPERVISION = {
    "missing": None,
    "not_json": "{oops",
    "list": "[1, 2]",
    "bool": '{"v1": true}',
    "negative": '{"v1": -1}',
    "string": '{"v1": "5"}',
    "null": '{"v1": null}',
    "nan": '{"v1": NaN}',
    "infinity": '{"v1": Infinity}',
    "overflow": '{"v1": 1e999}',
    "unknown_run": '{"other": 3}',
}


@pytest.mark.parametrize("case", list(SUPERVISION))
def test_invalid_supervision_file(tmp_path, case):
    a = make_run(tmp_path, "v1")
    sup = tmp_path / "sup.json"
    if SUPERVISION[case] is not None:
        sup.write_text(SUPERVISION[case], encoding="utf-8")
    refused([a, "--supervision", sup], "supervision file", sup)

```

## Not verified automatically

- Run directories are read only through evals/runlog.py (read_events, read_result) and cost_known uses evals.score.cost_is_known: tests check behaviour, not which functions are called.
- Nano-dollar summation (round(x*1e9) integer sum) is not distinguishable from float summation at 6 decimals by these tests.
- That nothing else in the repository changes is enforced by the writable scope, not by a test.
- Values for attempts/llm_calls of a NO_RESULT run are unspecified by the issue and not tested.

## Cost

Drafter: $0.2911, 8 model calls, 2 submits, 7 steps (ended: submitted).

## Approve

`approve_draft.py` checks the draft again under your task name, issue, cap and attempt limit, and publishes it only with `--approve`. Without a reference patch the task is recorded as `feasibility: unproven`; with one (`--reference-patch <patch>` instead of `--no-reference`) it is proven before the agent runs.

```bash
python scripts/approve_draft.py --draft runs/w2b1d3/draft.json --task <name> --issue-file runs/w2b1d3/issue.txt --max-usd <cap> --max-iterations <n> --no-reference
```
