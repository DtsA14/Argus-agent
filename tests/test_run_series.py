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

    def run(mode, manifest, task, runs, max_usd, config=None):
        code, status, write, *rest = outcomes[len(calls)]
        usd = rest[0] if rest else 0.05
        calls.append((task, config) if config else task)
        if write:
            runs.mkdir(parents=True)
            (runs / "report.json").write_text(json.dumps({"tasks": [
                {"id": task, "status": status, "eval_pass": status == "DONE",
                 "stats": {"usd_billed": usd}}]}), encoding="utf-8")
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


# ---- arms, pairs and the series cap (docs/reviews/DESIGN_BUDGET_45K.md) -------------------------------------------

ARMS = {"30": "evals/budget_v1/config_30k.yaml", "45": "evals/budget_v1/config_45k.yaml"}


def paired(tmp_path, outcomes, order, **kw):
    run, calls = fake(outcomes)
    record = rs.run_series(order, manifest="m.json", task_prefix="ledger_cap1_", out=tmp_path / "s", max_usd=1.0,
                           run=run, arm_configs=ARMS, pairs=True, **kw)
    assert json.loads((tmp_path / "s" / "series.json").read_text(encoding="utf-8")) == record
    return record, calls


def test_each_entry_runs_with_its_arms_config(tmp_path):
    record, calls = paired(tmp_path, [(0, "DONE", True)] * 4, ["a1@45", "a1@30", "c2@30", "c2@45"])
    assert calls == [("ledger_cap1_a", ARMS["45"]), ("ledger_cap1_a", ARMS["30"]),
                     ("ledger_cap1_c", ARMS["30"]), ("ledger_cap1_c", ARMS["45"])]
    assert [r["arm"] for r in record["runs"]] == ["45", "30", "30", "45"]
    assert [p["state"] for p in record["pairs"]] == ["complete", "complete"]
    assert (tmp_path / "s" / "01_a1_45").is_dir()


@pytest.mark.parametrize("order,arms,pairs", [
    (["a1@45", "a1"], ARMS, False),                      # arms on some entries only
    (["a1@60", "a1@30"], ARMS, True),                    # an arm without a config
    (["a1@45", "b1@30"], ARMS, True),                    # two cells, not a pair
    (["a1@45", "a1@45"], ARMS, True),                    # a repeated entry
    (["a1@45", "a1@30", "b1@45"], ARMS, True),           # an odd number of entries
])
def test_a_malformed_series_is_refused_before_anything_runs(tmp_path, order, arms, pairs):
    run, calls = fake([])
    with pytest.raises(ValueError):
        rs.run_series(order, manifest="m.json", task_prefix="p_", out=tmp_path / "s", max_usd=1.0, run=run,
                      arm_configs=arms, pairs=pairs)
    assert calls == []


def test_the_series_cap_never_splits_a_pair_and_is_never_exceeded(tmp_path):
    # Each run spends $0.80 by its ledger. After two pairs ($3.20), the next pair could need 2 x $1.00: 5.20 > 5.00.
    order = ["a1@45", "a1@30", "b1@30", "b1@45", "c1@45", "c1@30"]
    record, calls = paired(tmp_path, [(0, "DONE", True, 0.80)] * 6, order, max_usd_series=5.0)
    assert len(calls) == 4 and record["usd_spent"] == 3.2
    assert record["stopped"]["entry"] == "c1@45" and record["stopped"]["reason"].startswith("series cap")
    assert [p["state"] for p in record["pairs"]] == ["complete", "complete", "not run"]


def test_a_stop_inside_a_pair_marks_it_incomplete(tmp_path):
    record, calls = paired(tmp_path, [(0, "DONE", True), (0, "BLOCKED", True)], ["a1@45", "a1@30", "b1@30", "b1@45"])
    assert [p["state"] for p in record["pairs"]] == ["incomplete", "not run"]
    assert record["stopped"] == {"entry": "a1@30", "reason": "BLOCKED"}


def test_without_pairs_the_series_cap_is_checked_per_run(tmp_path):
    run, calls = fake([(0, "DONE", True, 0.60)] * 5)
    record = rs.run_series(["a1", "b1", "c1", "a2", "b2"], manifest="m.json", task_prefix="p_", out=tmp_path / "s",
                           max_usd=1.0, run=run, max_usd_series=2.5)
    assert len(calls) == 3 and record["usd_spent"] == 1.8 and record["stopped"]["entry"] == "a2"
