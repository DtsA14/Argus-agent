import copy
import json
import os
from collections import Counter
import subprocess
import sys
from pathlib import Path

import pytest

from harness.errors import BudgetExceeded, PermissionDenied
from harness.events import EventLog
from harness.guard import guard
from runner import ROOT, load_config, run_task
from tools.registry import ToolGate


def events(runs_dir, run_id):
    path = Path(runs_dir) / run_id / "events.jsonl"
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines()]


def run(tmp_path, scenario, run_id="t", **budget):
    cfg = copy.deepcopy(load_config())
    cfg["budget"].update(budget)
    return run_task(goal="x", scenario=scenario, run_id=run_id, runs_dir=tmp_path, cfg=cfg)


def test_pass_first_try(tmp_path):
    r = run(tmp_path, "pass")
    assert r["status"] == "DONE" and r["iteration"] == 1
    assert (tmp_path / "t" / "laporan.md").exists()


def test_fail_then_pass_uses_feedback(tmp_path):
    r = run(tmp_path, "fail_then_pass")
    assert r["status"] == "DONE" and r["iteration"] == 2
    verdicts = [e for e in events(tmp_path, "t") if e["event"] == "eval_verdict"]
    assert verdicts[0]["passed"] is False
    assert {"T2:top3_amounts", "T3:trend_months"} <= set(verdicts[0]["failures"])
    assert verdicts[1]["passed"] is True
    revised = [e for e in events(tmp_path, "t") if e["event"] == "spec_revised"]
    assert revised[0]["fix_ids"] == ["T2", "T3"]


def test_stops_when_score_stagnates(tmp_path):
    r = run(tmp_path, "never_pass")
    assert r["status"] == "FAILED_STAGNANT" and r["iteration"] == 3


def test_iteration_budget(tmp_path):
    r = run(tmp_path, "never_pass", max_iterations=2)
    assert r["status"] == "FAILED_BUDGET" and r["stop_reason"] == "max_iterations"


def test_token_budget(tmp_path):
    # one iteration reserves 11,500 tokens; 25,000 fits two, not a third
    r = run(tmp_path, "never_pass", max_tokens=25_000, stagnation_rounds=99)
    assert r["status"] == "FAILED_BUDGET" and r["stop_reason"] == "max_tokens"
    assert r["iteration"] == 2 and r["tokens_used"] == 23_000


def test_guard_admission_refuses_to_run(tmp_path):
    log = EventLog(tmp_path / "e.jsonl")
    calls = []
    node = guard("orchestrator", lambda s: calls.append(1) or {}, log=log,
                 retry={"attempts": 1, "base_delay": 0}, admit=lambda s: "max_tokens")
    with pytest.raises(BudgetExceeded):
        node({"iteration": 1, "tokens_used": 0, "elapsed_s": 0.0})
    assert calls == []  # the node body never ran


def test_transient_errors_are_retried(tmp_path):
    r = run(tmp_path, "flaky")
    assert r["status"] == "DONE"
    assert any(e["event"] == "retry" for e in events(tmp_path, "t"))


def test_tool_allowlist_enforced(tmp_path):
    log = EventLog(tmp_path / "e.jsonl")
    gate = ToolGate("worker", ["read_data"], log)
    gate.call("read_data")
    with pytest.raises(PermissionDenied):
        gate.call("run_shell", "rm -rf /")
    logged = [json.loads(l)["event"] for l in (tmp_path / "e.jsonl").read_text().splitlines()]
    assert logged == ["tool_call", "tool_denied"]


CRASH_REPEATS = int(os.environ.get("CRASH_REPEATS", "1"))  # scripts/verify.sh sets 5
CRASH_STRESS = int(os.environ.get("CRASH_STRESS", "3"))    # scripts/verify.sh sets 50


def crash_and_resume(tmp_path, crash_at):
    base = [sys.executable, "main.py", "--scenario", "fail_then_pass", "--run-id", "rc",
            "--runs-dir", str(tmp_path), "--quiet"]
    r1 = subprocess.run(base + ["--crash-at", crash_at], cwd=ROOT, capture_output=True, text=True)
    assert r1.returncode == 42, r1.stderr
    assert not (tmp_path / "rc" / "result.json").exists()  # it really died mid-run
    r2 = subprocess.run(base + ["--resume"], cwd=ROOT, capture_output=True, text=True)
    assert r2.returncode == 0, r2.stderr
    return json.loads((tmp_path / "rc" / "result.json").read_text()), events(tmp_path, "rc")


def key(e):
    return (e["node"], e.get("task"), e.get("iteration"))


def assert_resume_guarantees(result, evs):
    """The guarantee we can actually give against a hard crash (at-least-once + durable memo):

    1. Outcome is identical to an uninterrupted run (state counts every node run exactly once).
    2. Every node run commits its result exactly once (result_committed).
    3. A node run whose result was committed is never performed again: it is either not
       scheduled again or answered from the memo (memo_hit).
    4. Work is redone only for a node run that had no committed result when the process died,
       and the ledger (body_done / tokens_spent) shows that extra spend honestly.
    """
    assert result["status"] == "DONE" and result["iteration"] == 2 and result["tokens_used"] == 23_000

    names = [e["event"] for e in evs]
    assert "crash_simulated" in names and "resume" in names
    crash = names.index("crash_simulated")
    before, after = evs[:crash], evs[crash:]

    committed = Counter(key(e) for e in evs if e["event"] == "result_committed")
    assert all(n == 1 for n in committed.values()), committed
    assert len(committed) == 2 * (1 + 3 + 1 + 1)  # 2 iterations x (orchestrator + 3 workers + synthesize + evaluator)

    committed_before = {key(e) for e in before if e["event"] == "result_committed"}
    redone_after = {key(e) for e in after if e["event"] == "body_done"}
    assert not committed_before & redone_after, committed_before & redone_after

    for e in after:
        if e["event"] == "memo_hit":
            assert key(e) in committed_before  # memo only answers for results that were committed

    spent = sum(e.get("tokens", 0) for e in evs if e["event"] == "body_done")
    assert result["tokens_spent"] == spent >= result["tokens_used"]


@pytest.mark.parametrize("repeat", range(CRASH_REPEATS))
@pytest.mark.parametrize("crash_at", ["orchestrator", "worker", "synthesize", "evaluator"])
def test_crash_then_resume_from_checkpoint(tmp_path, crash_at, repeat):
    """Kill the real process before a node, restart it, and require the same outcome as an uninterrupted run."""
    assert_resume_guarantees(*crash_and_resume(tmp_path, crash_at))


@pytest.mark.parametrize("repeat", range(CRASH_REPEATS))
@pytest.mark.parametrize("node", ["orchestrator", "worker", "synthesize", "evaluator"])
def test_crash_after_commit_is_answered_from_memo(tmp_path, node, repeat):
    """Deterministic version of the race: the node finished and committed its result, then the process
    died before LangGraph saved it. Resume must take the result from the memo and redo nothing."""
    result, evs = crash_and_resume(tmp_path, f"{node}@after_commit")
    assert_resume_guarantees(result, evs)

    crash = next(e for e in evs if e["event"] == "crash_simulated")
    crashed = (crash["node"], crash.get("task"), crash.get("iteration"))
    hits = [key(e) for e in evs if e["event"] == "memo_hit"]
    assert hits == [crashed]                              # answered from the memo, exactly once
    performed = Counter(key(e) for e in evs if e["event"] == "body_done")
    assert performed[crashed] == 1                        # its work was not redone
    if node != "worker":
        # a node that runs alone: nothing at all is redone, spend equals the uninterrupted run
        assert all(n == 1 for n in performed.values())
        assert result["tokens_spent"] == result["tokens_used"] == 23_000
    # parallel workers: a sibling still mid-work at the crash had nothing committed, so it may
    # legitimately run again; assert_resume_guarantees already checks only those are redone.


@pytest.mark.parametrize("repeat", range(CRASH_STRESS))
def test_parallel_worker_crash_stress(tmp_path, repeat):
    """Crashing one of three parallel workers is the race that used to redo finished workers (~27% of runs)."""
    assert_resume_guarantees(*crash_and_resume(tmp_path, "worker"))
