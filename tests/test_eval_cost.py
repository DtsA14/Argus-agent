"""A cost that is not known is never zero in the eval path (docs/reviews/INVESTIGATION_UNKNOWN_COST.md).

A run's cost is known only when its result has usd_billed and usd_complete is true (the rule scripts/run_series.py already
uses). Anything else stops the eval, the tasks after it are not run, and usd_spent is a lower bound with usd_complete
false. The aggregate reports statistics over the known runs and counts the others. No model and no sandbox are used."""
import json
import shutil
import sys
from pathlib import Path

import pytest

from evals import runner as ev
from evals.score import aggregate, cost_is_known, format_cost

ROOT = Path(__file__).resolve().parent.parent
MANIFEST = ROOT / "evals" / "v1" / "manifest.json"


def passing(spec, workspace, sandbox_cfg, log=None):
    return {"status": "pass", "reason": ""}


def eval_with_results(tmp_path, monkeypatch, results, mode="live", max_total_usd=10.0):
    """run_eval with run_code_task replaced: the n-th task that starts gets results[n] as its result.json."""
    from runner import load_config
    started = []

    def fake_run(*, contract_path, run_id, runs_dir, cfg, models, validate):
        started.append(run_id)
        contract = json.loads(Path(contract_path).read_text(encoding="utf-8"))
        run = Path(runs_dir) / run_id
        shutil.copytree(ROOT / contract["inputs"]["workspace"], run / "workspace",
                        ignore=shutil.ignore_patterns("__pycache__"))
        (run / "result.json").write_text(json.dumps({"status": "FAILED_ACCEPTANCE", "attempts": 1, "llm_calls": 3,
                                                     **results[len(started) - 1]}), encoding="utf-8")
        (run / "events.jsonl").write_text("", encoding="utf-8")

    monkeypatch.setattr(ev, "run_code_task", fake_run)
    report = ev.run_eval(MANIFEST, mode, tmp_path / "runs", load_config(),
                         max_total_usd=max_total_usd if mode == "live" else None, validate=passing)
    return report, started, [t["id"] for t in ev.load_manifest(MANIFEST)["tasks"]]


@pytest.mark.parametrize("cost, spent", [
    ({"usd_complete": True}, 0.0),                           # no usd_billed at all: not invented as zero
    ({"usd_billed": None, "usd_complete": True}, 0.0),
    ({"usd_billed": 0.05, "usd_complete": False}, 0.05),     # a partial total: a lower bound, never a complete cost
    ({"usd_billed": 0.30}, 0.30)])                           # no usd_complete: unknown
def test_a_run_whose_cost_is_unknown_stops_the_eval_and_is_never_counted_as_zero(tmp_path, monkeypatch, cost, spent):
    report, started, ids = eval_with_results(tmp_path, monkeypatch, [cost] * 5)
    assert started == [f"live_{ids[0]}"]                                           # nothing after it starts
    assert "cost is unknown" in report["stopped"]["reason"] and report["stopped"]["task"] == ids[0]
    assert all(r["not_run"] and "cost is unknown" in r["why"][0] for r in report["tasks"][1:])
    assert report["usd_spent"] == spent and report["usd_complete"] is False
    assert sorted(p.name for p in (tmp_path / "runs").iterdir()) == [f"live_{ids[0]}"]


def test_an_unknown_cost_stops_the_scripted_modes_too(tmp_path, monkeypatch):
    report, started, ids = eval_with_results(tmp_path, monkeypatch, [{"usd_billed": 0.05, "usd_complete": False}] * 5,
                                             mode="reference")
    assert started == [f"reference_{ids[0]}"] and report["usd_complete"] is False and report["usd_spent"] == 0.05


def test_known_costs_keep_the_eval_going_and_the_total_is_complete(tmp_path, monkeypatch):
    report, started, ids = eval_with_results(tmp_path, monkeypatch, [{"usd_billed": 0.1, "usd_complete": True}] * 50)
    assert len(started) == len(ids) and report["stopped"] is None
    assert report["usd_spent"] == pytest.approx(0.1 * len(ids)) and report["usd_complete"] is True


def test_a_blocked_run_still_stops_the_eval_with_its_own_reason_when_its_cost_is_known(tmp_path, monkeypatch):
    results = [{"usd_billed": 0.1, "usd_complete": True, "status": "BLOCKED", "blocked_reason": "sandbox_unavailable"}] * 5
    report, started, ids = eval_with_results(tmp_path, monkeypatch, results)
    assert len(started) == 1 and report["stopped"]["status"] == "BLOCKED" and "reason" not in report["stopped"]
    assert "ended BLOCKED" in report["tasks"][1]["why"][0] and report["usd_complete"] is True


def test_costs_are_aggregated_over_the_runs_whose_cost_is_known_and_the_others_are_counted():
    def row(cat, stats):
        return {"category": cat, "eval_pass": True, "acceptance_pass": True, "stats": stats}
    rows = [row("a", {"usd_billed": 0.02, "usd_complete": True}), row("a", {"usd_billed": 0.04, "usd_complete": True}),
            row("a", {"usd_billed": None, "usd_complete": True}), row("b", {"usd_billed": 0.05, "usd_complete": False}),
            row("b", {"usd_billed": 0.30})]
    agg = aggregate(rows)
    assert (agg["total"]["usd_total"], agg["total"]["usd_median"], agg["total"]["usd_unknown_runs"]) == (0.06, 0.03, 3)
    assert (agg["by_category"]["a"]["usd_total"], agg["by_category"]["a"]["usd_unknown_runs"]) == (0.06, 1)
    b = agg["by_category"]["b"]
    assert (b["usd_total"], b["usd_median"], b["usd_unknown_runs"]) == (0.0, None, 2)


def test_a_cost_is_shown_as_n_a_when_it_is_not_known():
    assert format_cost({"usd_billed": 0.02, "usd_complete": True}) == "$0.0200"
    assert format_cost({"usd_complete": True}) == "n/a" and format_cost({}) == "n/a" and format_cost(None) == "n/a"
    assert format_cost({"usd_billed": 0.05, "usd_complete": False}) == "n/a (at least $0.0500)"
    assert format_cost({"usd_billed": 0.05}) == "n/a (at least $0.0500)"
    assert not cost_is_known({"usd_billed": 0.05}) and cost_is_known({"usd_billed": 0.0, "usd_complete": True})


def test_run_eval_prints_n_a_and_says_the_total_is_incomplete(tmp_path, monkeypatch, capsys):
    sys.path.insert(0, str(ROOT / "scripts"))
    import run_eval as script
    unknown = {"id": "t2", "category": "c", "expected": "DONE", "status": "FAILED_ACCEPTANCE", "eval_pass": False,
               "why": [], "stats": {"usd_billed": 0.05, "usd_complete": False, "llm_calls": 3}}
    known = {**unknown, "id": "t1", "eval_pass": True, "stats": {"usd_billed": 0.02, "usd_complete": True, "llm_calls": 2}}
    stopped = {"task": "t2", "status": "FAILED_ACCEPTANCE", "blocked_reason": None,
               "reason": "the run's cost is unknown (no complete ledger cost in its report)"}
    report = {"benchmark": "v1", "benchmark_sha256": "0" * 64, "agent": {"commit": "a" * 40, "dirty": False, "model": "m"},
              "tasks": [known, unknown], "stopped": stopped, "ran": 2, "not_run": 0, "usd_spent": 0.07,
              "usd_complete": False, "benchmark_valid": True,
              "summary": {"total": {"tasks": 2, "eval_pass": 1, "acceptance_pass": 1, "positive": 2, "honest_all_attempts": 0,
                                    "recovered": 0, "usd_total": 0.02, "usd_median": 0.02, "usd_unknown_runs": 1}}}
    monkeypatch.setattr(script, "run_eval", lambda *a, **k: report)
    script.main(["--mode", "reference", "--runs-dir", str(tmp_path / "r")])
    out = capsys.readouterr().out
    assert "$0.0200" in out and "n/a (at least $0.0500)" in out and "$0.0000" not in out
    assert "STOPPED after t2: the run's cost is unknown" in out
    assert "excludes 1 run(s) with unknown cost" in out
    assert "cost is incomplete: spent at least $0.07, not a total" in out
