"""Tests added after the external audit: token budget invariant, stagnation/status transitions,
retry semantics, estimate enforcement, plan width, and termination logging."""
import copy
import json
from pathlib import Path

import pytest

from harness.budget import Budget, iteration_cost, next_iteration_blocker
from harness.errors import EstimateExceeded, PlanRejected, TransientError
from harness.events import EventLog
from harness.guard import guard
from harness.progress import decide_status, update_progress
from nodes.orchestrator import make_fan_out
from runner import load_config, run_task

ITER = iteration_cost(load_config()["token_estimates"], 3)  # 11,500


def events(path):
    return [json.loads(l) for l in Path(path).read_text(encoding="utf-8").splitlines()]


def run(tmp_path, scenario, run_id="t", **budget):
    cfg = copy.deepcopy(load_config())
    cfg["budget"].update(budget)
    return run_task(goal="x", scenario=scenario, run_id=run_id, runs_dir=tmp_path, cfg=cfg)


# ---- P1: the token budget can never be exceeded -----------------------------

@pytest.mark.parametrize("max_tokens", list(range(0, 60_001, 2_500)) + [ITER - 1, ITER, 2 * ITER, 2 * ITER + 1])
def test_tokens_never_exceed_budget_and_stop_is_not_premature(tmp_path, max_tokens):
    r = run(tmp_path, "never_pass", max_tokens=max_tokens, max_iterations=99, stagnation_rounds=99)
    assert r["status"] == "FAILED_BUDGET" and r["stop_reason"] == "max_tokens"
    used = r["tokens_used"] or 0
    assert used <= max_tokens                 # never over
    assert used + ITER > max_tokens           # stopped only because another iteration would not fit
    assert used == (max_tokens // ITER) * ITER


def test_first_iteration_refused_when_budget_too_small(tmp_path):
    r = run(tmp_path, "pass", max_tokens=ITER - 1)
    assert r["status"] == "FAILED_BUDGET" and r["iteration"] == 0 and not r["tokens_used"]
    evs = events(tmp_path / "t" / "events.jsonl")
    assert not any(e["event"] == "node_start" for e in evs)  # no node ran at all


def test_exact_budget_fits_exactly_one_iteration(tmp_path):
    r = run(tmp_path, "pass", max_tokens=ITER)
    assert r["status"] == "DONE" and r["tokens_used"] == ITER


def test_node_over_its_estimate_is_a_hard_error(tmp_path):
    log = EventLog(tmp_path / "e.jsonl")
    node = guard("worker", lambda s: {"tokens_used": 2001}, log=log,
                 retry={"attempts": 1, "base_delay": 0}, estimate=2000)
    with pytest.raises(EstimateExceeded):
        node({})
    assert events(tmp_path / "e.jsonl")[-1]["event"] == "estimate_overrun"


def test_node_over_its_usd_estimate_is_a_hard_error(tmp_path):
    log = EventLog(tmp_path / "e.jsonl")
    node = guard("worker", lambda s: {"tokens_used": 1, "usd_used": 0.0011}, log=log,
                 retry={"attempts": 1, "base_delay": 0}, estimate=2000, usd_estimate=0.001)
    with pytest.raises(EstimateExceeded):
        node({})


def test_plan_wider_than_max_workers_is_rejected(tmp_path):
    fan_out = make_fan_out(2, EventLog(tmp_path / "e.jsonl"))
    state = {"status": "RUNNING", "spec": {"tasks": [{"id": i, "output": "top3"} for i in "abc"]},
             "iteration": 0, "scenario": "pass", "run_id": "t"}
    with pytest.raises(PlanRejected):
        fan_out(state)


def test_blocker_order_and_boundaries():
    b = Budget(max_iterations=3, max_tokens=100, max_seconds=10, stagnation_rounds=2)
    kw = dict(elapsed_s=0.0, iteration_tokens=50)
    assert next_iteration_blocker(b, iteration=0, tokens_used=50, **kw) is None       # 50 + 50 == 100 fits
    assert next_iteration_blocker(b, iteration=0, tokens_used=51, **kw) == "max_tokens"
    assert next_iteration_blocker(b, iteration=3, tokens_used=0, **kw) == "max_iterations"
    assert next_iteration_blocker(b, iteration=0, tokens_used=0, elapsed_s=10, iteration_tokens=50) == "max_seconds"


# ---- P2: stagnation and status transitions ----------------------------------

@pytest.mark.parametrize("scores, expected", [
    ([0.4], [(0.4, 0)]),                                           # first score always improves on -1
    ([0.4, 0.6], [(0.4, 0), (0.6, 0)]),                            # improvement resets
    ([0.6, 0.6], [(0.6, 0), (0.6, 1)]),                            # equal is stale
    ([0.6, 0.5], [(0.6, 0), (0.6, 1)]),                            # drop is stale, best is kept
    ([0.4, 0.6, 0.6, 0.5], [(0.4, 0), (0.6, 0), (0.6, 1), (0.6, 2)]),
    ([0.6, 0.5, 0.7, 0.7], [(0.6, 0), (0.6, 1), (0.7, 0), (0.7, 1)]),  # recovery after a drop resets
    ([0.5, 0.4, 0.55], [(0.5, 0), (0.5, 1), (0.55, 0)]),           # beating the best (not the last) resets
])
def test_update_progress_transitions(scores, expected):
    best, stale, seen = -1.0, 0, []
    for s in scores:
        best, stale = update_progress(best, stale, s)
        seen.append((best, stale))
    assert seen == expected


@pytest.mark.parametrize("passed, blocker, stale, expected", [
    (True, "max_tokens", 5, ("DONE", "")),                 # passing on the last affordable round still wins
    (False, "max_iterations", 5, ("FAILED_BUDGET", "max_iterations")),  # budget beats stagnation
    (False, None, 2, ("FAILED_STAGNANT", "no improvement for 2 rounds")),
    (False, None, 1, ("RUNNING", "")),
])
def test_decide_status_priority(passed, blocker, stale, expected):
    assert decide_status(passed=passed, budget_blocker=blocker,
                         stale_rounds=stale, stagnation_rounds=2) == expected


def test_many_iterations_stop_on_budget_not_on_recursion_limit(tmp_path):
    r = run(tmp_path, "never_pass", max_iterations=30, stagnation_rounds=99, max_tokens=10**9, max_usd=100)
    assert r["status"] == "FAILED_BUDGET" and r["stop_reason"] == "max_iterations" and r["iteration"] == 30


def test_stagnation_rounds_setting_is_respected(tmp_path):
    assert run(tmp_path, "never_pass", run_id="a", stagnation_rounds=1)["iteration"] == 2
    assert run(tmp_path, "never_pass", run_id="b", stagnation_rounds=3)["iteration"] == 4


def test_pass_on_last_allowed_iteration_is_done(tmp_path):
    r = run(tmp_path, "fail_then_pass", max_iterations=2)
    assert r["status"] == "DONE" and r["iteration"] == 2


# ---- P2: retry semantics -----------------------------------------------------

def _counting(fails, exc=TransientError):
    calls = []

    def fn(state):
        calls.append(1)
        if len(calls) <= fails:
            raise exc("boom")
        return {"tokens_used": 1}

    return fn, calls


def test_retry_recovers_after_transient_failures(tmp_path):
    fn, calls = _counting(fails=2)
    node = guard("w", fn, log=EventLog(tmp_path / "e.jsonl"), retry={"attempts": 3, "base_delay": 0})
    assert node({})["tokens_used"] == 1
    assert len(calls) == 3
    assert [e["attempt"] for e in events(tmp_path / "e.jsonl") if e["event"] == "retry"] == [1, 2]


def test_retry_gives_up_after_max_attempts(tmp_path):
    fn, calls = _counting(fails=99)
    node = guard("w", fn, log=EventLog(tmp_path / "e.jsonl"), retry={"attempts": 3, "base_delay": 0})
    with pytest.raises(TransientError):
        node({})
    assert len(calls) == 3
    assert events(tmp_path / "e.jsonl")[-1]["event"] == "retry_exhausted"


def test_non_transient_errors_are_not_retried(tmp_path):
    fn, calls = _counting(fails=1, exc=ValueError)
    node = guard("w", fn, log=EventLog(tmp_path / "e.jsonl"), retry={"attempts": 3, "base_delay": 0})
    with pytest.raises(ValueError):
        node({})
    assert len(calls) == 1


# ---- evaluator: invalid content must not pass -------------------------------

def _report(tmp_path, extra_trend=()):
    import dataset
    t = dataset.truth()
    lines = ["# Laporan Penjualan", "", "## Top 3 Produk"] + [f"- {n}: {v}" for n, v in t["top3"]]
    lines += ["", "## Tren Bulanan"] + [f"- {m}: {v}" for m, v in t["trend"]] + list(extra_trend)
    lines += ["", "## Rekomendasi", "1. Bundle A + B: 72%.", "2. Raise stock 10%."]
    p = tmp_path / "laporan.md"
    p.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return p, t


def test_evaluator_accepts_a_correct_report(tmp_path):
    from nodes.evaluator import run_checks
    p, t = _report(tmp_path)
    assert [c["id"] for c in run_checks(p, t) if not c["ok"]] == []


def test_evaluator_rejects_months_that_are_not_in_the_data(tmp_path):
    from nodes.evaluator import run_checks
    p, t = _report(tmp_path, extra_trend=["- 2027-01: 999999"])   # a real month, absent from the data
    assert [c["id"] for c in run_checks(p, t) if not c["ok"]] == ["trend_no_extra_months"]


# ---- durable memo ------------------------------------------------------------

def test_memo_survives_a_new_instance(tmp_path):
    from harness.memo import Memo
    Memo(tmp_path / "m.sqlite").put("k", {"tokens_used": 7, "results": {"T1": [1, 2]}})
    assert Memo(tmp_path / "m.sqlite").get("k") == {"tokens_used": 7, "results": {"T1": [1, 2]}}
    assert Memo(tmp_path / "m.sqlite").get("missing") is None


def test_guard_answers_from_memo_without_redoing_work(tmp_path):
    from harness.memo import Memo
    log, memo = EventLog(tmp_path / "e.jsonl"), Memo(tmp_path / "m.sqlite")
    calls = []
    node = guard("worker", lambda s: calls.append(1) or {"tokens_used": 5},
                 log=log, retry={"attempts": 1, "base_delay": 0}, memo=memo)
    state = {"task": {"id": "T1"}, "iteration": 0}
    first, second = node(state), node(state)
    assert calls == [1]                                   # the work ran once
    assert first["tokens_used"] == second["tokens_used"] == 5
    kinds = [e["event"] for e in events(tmp_path / "e.jsonl")]
    assert kinds == ["node_start", "body_done", "result_committed", "node_end", "memo_hit"]
    node({"task": {"id": "T1"}, "iteration": 1})          # a different iteration is new work
    assert calls == [1, 1]


def test_fresh_run_refuses_an_existing_run_id(tmp_path):
    from runner import RunExists
    run(tmp_path, "pass")
    with pytest.raises(RunExists):
        run(tmp_path, "pass")  # would otherwise reuse the old checkpoint and memo


def test_resume_without_a_checkpoint_is_an_error(tmp_path):
    from runner import RunExists
    with pytest.raises(RunExists):
        run_task(goal="x", scenario="pass", run_id="none", runs_dir=tmp_path, cfg=load_config(), resume=True)


# ---- DoD: every termination is recorded with its reason ---------------------

@pytest.mark.parametrize("scenario, budget, status, reason", [
    ("pass", {}, "DONE", ""),
    ("never_pass", {}, "FAILED_STAGNANT", "no improvement for 2 rounds"),
    ("never_pass", {"max_iterations": 2}, "FAILED_BUDGET", "max_iterations"),
    ("never_pass", {"max_tokens": 20_000}, "FAILED_BUDGET", "max_tokens"),
])
def test_termination_is_logged_with_reason(tmp_path, scenario, budget, status, reason):
    run(tmp_path, scenario, **budget)
    end = events(tmp_path / "t" / "events.jsonl")[-1]
    assert end["event"] == "run_end" and end["status"] == status and end["stop_reason"] == reason
    result = json.loads((tmp_path / "t" / "result.json").read_text())
    assert result["status"] == status and result["stop_reason"] == reason
