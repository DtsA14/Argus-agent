"""scripts/run_series.py: a live series stops at the first harness anomaly or infrastructure/budget stop, never runs
the next entry after it, and always writes series.json with the reason. run_eval is replaced by a fake here."""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import run_series as rs  # noqa: E402


def fake(outcomes):
    """A run_eval stand-in: for each call, (exit code, status or None for no report, report written?)."""
    calls = []

    def run(mode, manifest, task, runs, max_usd):
        code, status, write = outcomes[len(calls)]
        calls.append(task)
        if write:
            runs.mkdir(parents=True)
            (runs / "report.json").write_text(json.dumps({"tasks": [
                {"id": task, "status": status, "eval_pass": status == "DONE",
                 "stats": {"usd_billed": 0.05}}]}), encoding="utf-8")
        return code, "", "Traceback: boom" if code else ""
    return run, calls


def series(tmp_path, outcomes, order=("c2", "b3", "a1")):
    run, calls = fake(outcomes)
    record = rs.run_series(list(order), manifest="m.json", task_prefix="ledger_terms_", out=tmp_path / "s",
                           max_usd=0.5, run=run)
    written = json.loads((tmp_path / "s" / "series.json").read_text(encoding="utf-8"))
    assert written == record
    return record, calls


def test_a_nonzero_exit_stops_the_series_even_when_a_report_exists(tmp_path):
    record, calls = series(tmp_path, [(0, "DONE", True), (1, "DONE", True), (0, "DONE", True)])
    assert calls == ["ledger_terms_c", "ledger_terms_b"]                  # a1 never ran
    assert record["stopped"]["entry"] == "b3" and record["stopped"]["reason"] == "run_eval exited 1"
    assert "boom" in record["stopped"]["stderr"]
    assert [r["exit_code"] for r in record["runs"]] == [0, 1] and record["usd_spent"] == 0.1


def test_failed_acceptance_is_data_and_the_series_goes_on(tmp_path):
    record, calls = series(tmp_path, [(0, "FAILED_ACCEPTANCE", True), (0, "DONE", True), (0, "DONE", True)])
    assert len(calls) == 3 and record["stopped"] is None


@pytest.mark.parametrize("outcome,reason", [
    ((0, "BLOCKED", True), "BLOCKED"),
    ((0, "FAILED_BUDGET", True), "FAILED_BUDGET"),
    ((0, None, True), "the task has no status"),
    ((0, None, False), "no report"),
    ((2, None, False), "run_eval exited 2"),
])
def test_an_infrastructure_budget_or_harness_stop_ends_the_series(tmp_path, outcome, reason):
    record, calls = series(tmp_path, [(0, "DONE", True), outcome, (0, "DONE", True)])
    assert len(calls) == 2 and record["stopped"] == {**record["stopped"], "entry": "b3", "reason": reason}


def test_a_repeated_entry_is_refused_before_anything_runs(tmp_path):
    run, calls = fake([])
    with pytest.raises(ValueError):
        rs.run_series(["a1", "a1"], manifest="m.json", task_prefix="p_", out=tmp_path / "s", max_usd=0.5, run=run)
    assert calls == []
