from pathlib import Path

from langgraph.graph import END, START, StateGraph

from harness.budget import Budget, iteration_cost, iteration_usd, next_iteration_blocker, node_usd_estimates
from harness.guard import guard
from harness.crash import Crasher
from harness.memo import Memo
from nodes.evaluator import make_evaluator
from harness.llm import LLMCaller
from models.registry import ConfigError
from nodes.contract import SALES_REPORT
from nodes.llm_worker import make_llm_worker
from nodes.orchestrator import make_fan_out, make_llm_orchestrator, make_orchestrator
from nodes.synthesize import make_synthesize
from nodes.worker import make_worker
from state import State
from tools.registry import ToolGate


def route_after_eval(state):
    return END if state["status"] != "RUNNING" else "orchestrator"


def make_orchestrator_node(cfg, log, budget, est, usd_est, models=None, crasher=None):
    """impl.orchestrator: 'fake' (deterministic demo plan) or 'llm' (model plans via SubmitPlan)."""
    impl = (cfg.get("impl") or {}).get("orchestrator", "fake")
    if impl == "fake":
        return make_orchestrator(log, usd=usd_est["orchestrator"])
    if impl != "llm":
        raise ConfigError(f"impl.orchestrator must be 'fake' or 'llm', got {impl!r}")
    ocfg = cfg.get("orchestrator") or {}
    caller = LLMCaller(cfg, "orchestrator", log, model=(models or {}).get("orchestrator"))
    return make_llm_orchestrator(
        caller, SALES_REPORT, max_workers=budget.max_workers, log=log,
        tokens=est["orchestrator"], usd=usd_est["orchestrator"],
        attempts=int(ocfg.get("plan_attempts", 3)),
        tool_choice="SubmitPlan" if ocfg.get("force_tool", True) else None,
        crasher=crasher,
    )


def make_worker_node(cfg, log, gate, memo, est, usd_est, models=None, crasher=None):
    """impl.worker: 'fake' (deterministic, computes outputs directly) or 'llm' (tool-calling loop)."""
    impl = (cfg.get("impl") or {}).get("worker", "fake")
    if impl == "fake":
        return make_worker(gate, usd=usd_est["worker"])
    if impl != "llm":
        raise ConfigError(f"impl.worker must be 'fake' or 'llm', got {impl!r}")
    caller = LLMCaller(cfg, "worker", log, model=(models or {}).get("worker"))
    return make_llm_worker(caller, SALES_REPORT, gate, memo, log, tokens=est["worker"], usd=usd_est["worker"],
                           max_steps=int(cfg["roles"]["worker"].get("max_steps", 6)), crasher=crasher)


def build_graph(cfg, run_dir, log, checkpointer, crash_at=None, models=None):
    budget = Budget.from_cfg(cfg["budget"])
    est = cfg["token_estimates"]
    iter_tokens = iteration_cost(est, budget.max_workers)
    usd_est = node_usd_estimates(cfg)
    iter_usd = iteration_usd(usd_est, budget.max_workers)
    run_dir = Path(run_dir)
    report_path = str(run_dir / "laporan.md")
    memo = Memo(run_dir / "memo.sqlite")
    common = dict(log=log, retry=cfg["retry"], memo=memo,
                  crash_at=crash_at, crash_marker=str(run_dir / ".crashed"))

    def admit_iteration(state):
        # Safety net. The evaluator normally stops the loop gracefully first; this gate
        # also covers the first iteration and resumes with a changed budget.
        return next_iteration_blocker(
            budget,
            iteration=state.get("iteration", 0),
            tokens_used=state.get("tokens_used", 0),
            elapsed_s=state.get("elapsed_s", 0.0),
            iteration_tokens=iter_tokens,
            usd_used=state.get("usd_used", 0.0),
            iteration_usd=iter_usd,
        )

    orch_gate = ToolGate("orchestrator", cfg["tools"]["orchestrator"], log)
    worker_gate = ToolGate("worker", cfg["tools"]["worker"], log)

    g = StateGraph(State)
    crasher = Crasher(crash_at, str(run_dir / ".crashed"), log)
    orchestrator = make_orchestrator_node(cfg, log, budget, est, usd_est, models, crasher)
    worker = make_worker_node(cfg, log, worker_gate, memo, est, usd_est, models, crasher)
    g.add_node("orchestrator", guard("orchestrator", orchestrator,
                                     admit=admit_iteration, estimate=est["orchestrator"],
                                     usd_estimate=usd_est["orchestrator"], **common))
    g.add_node("worker", guard("worker", worker,
                               estimate=est["worker"], usd_estimate=usd_est["worker"], **common))
    g.add_node("synthesize", guard("synthesize", make_synthesize(orch_gate, report_path, log),
                                   estimate=est["synthesize"], usd_estimate=usd_est["synthesize"], **common))
    g.add_node("evaluator", guard("evaluator", make_evaluator(report_path, budget, log, iter_tokens, iter_usd),
                                  estimate=est["evaluator"], usd_estimate=usd_est["evaluator"], **common))

    g.add_edge(START, "orchestrator")
    g.add_conditional_edges("orchestrator", make_fan_out(budget.max_workers, log), ["worker", END])
    g.add_edge("worker", "synthesize")
    g.add_edge("synthesize", "evaluator")
    g.add_conditional_edges("evaluator", route_after_eval, {"orchestrator": "orchestrator", END: END})
    return g.compile(checkpointer=checkpointer)
