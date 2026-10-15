from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
from langgraph.graph import END
from langgraph.types import Send

from harness.errors import LLMCallFailed, PlanRejected, ReservationExhausted
from harness.crash import Crasher
from harness.llm import is_truncated
from harness.steps import call_ids, invalid_call_errors, reservation_from_ledger

from .plan import SubmitPlan, system_prompt, user_prompt, validate_plan

# ---- fake planner (deterministic; used by tests and by M1 scenarios) ---------------

FAKE_TASKS = [
    {"id": "T1", "output": "data_check", "instruction": "Read and validate the CSV: columns, empty values, row count."},
    {"id": "T2", "output": "top3", "instruction": "Compute the 3 products with the highest total revenue."},
    {"id": "T3", "output": "trend", "instruction": "Compute total revenue per month for every month."},
]


def failed_outputs(verdict):
    return sorted({f["task"] for f in (verdict or {}).get("failures", [])})


def make_orchestrator(log, usd=0.0):
    """Deterministic planner. On a revision it attaches feedback to the tasks whose outputs failed."""

    def orchestrator(state):
        prev = state.get("spec")
        failed = set(failed_outputs(state.get("verdict")))
        tasks = [{**t, "feedback": (f"Output {t['output']!r} failed the evaluator; fix it." if t["output"] in failed
                                    else "")} for t in FAKE_TASKS]
        revision = 0 if prev is None else prev["revision"] + 1
        spec = {"goal": state["goal"], "tasks": tasks, "revision": revision, "rationale": "fixed demo plan"}
        log.emit("spec_created" if prev is None else "spec_revised", revision=revision,
                 tasks=[t["id"] for t in tasks], revised=sorted(failed))
        return {"spec": spec, "tokens_used": 3000, "usd_used": usd, "status": "RUNNING"}

    return orchestrator


# ---- LLM planner ---------------------------------------------------------------------

def make_llm_orchestrator(caller, contract, *, max_workers, log, tokens, usd, attempts=3, tool_choice="SubmitPlan",
                          crasher=None):
    """Asks the model for a plan via the SubmitPlan tool, validates it, and on rejection returns the exact
    errors to the model, at most `attempts` calls in total. Every call is paid from one node reservation
    of (tokens, usd), the node's estimate, so the node can never report more than it reserved. The
    reservation starts with what this node run already spent before a crash (from the ledger), so the
    limit holds across processes too."""
    crasher = crasher or Crasher()
    sys_msg = SystemMessage(system_prompt(contract, max_workers))

    def orchestrator(state):
        iteration = state.get("iteration", 0)
        res = reservation_from_ledger(log, tokens=tokens, usd=usd, node="orchestrator", task=None, iteration=iteration)
        prev = state.get("spec")
        failures = [{"output": f["task"], "check": f["id"], "detail": f["detail"]}
                    for f in (state.get("verdict") or {}).get("failures", [])]
        messages = [sys_msg, HumanMessage(user_prompt(state["goal"], prev, failures if prev else None))]
        meta = {"node": "orchestrator", "iteration": iteration}

        def stop(status, reason):
            log.emit("orchestrator_stop", status=status, reason=reason[:300], iteration=iteration)
            return {"status": status, "stop_reason": reason, "tokens_used": res.used_tokens, "usd_used": res.used_usd}

        errors = []
        for attempt in range(1, attempts + 1):
            try:
                msg = caller.call(messages, res, tools=[SubmitPlan], tool_choice=tool_choice, meta=meta)
            except ReservationExhausted as e:
                return stop("FAILED_BUDGET", f"node_reservation: {e}")
            except LLMCallFailed as e:
                return stop("FAILED_LLM", str(e))
            crasher.point("orchestrator@after_llm", node="orchestrator", iteration=iteration)

            if is_truncated(msg):
                # The plan may be cut off mid-argument, so it is never validated or accepted. Retrying is
                # not worth paying for: the next attempt gets no more output room than this one had.
                out = (getattr(msg, "usage_metadata", None) or {}).get("output_tokens")
                log.emit("plan_truncated", attempt=attempt, iteration=iteration, output_tokens=out)
                return stop("FAILED_PLAN", f"output_truncated: the plan reply hit max_tokens after {out} "
                                           f"output tokens; not accepted, not retried")

            calls = list(getattr(msg, "tool_calls", None) or [])
            plan_calls = [c for c in calls if c.get("name") == "SubmitPlan"]
            if invalid_call_errors(msg):   # a malformed call is never read as a plan
                errors, plan = invalid_call_errors(msg), None
            elif len(calls) != 1 or len(plan_calls) != 1:
                # Strict contract: the reply must be exactly one SubmitPlan call and nothing else.
                others = sorted({c.get("name") or "?" for c in calls} - {"SubmitPlan"})
                errors = [f"call only the SubmitPlan tool, exactly once: got {len(calls)} tool call(s), "
                          f"{len(plan_calls)} of them SubmitPlan" + (f"; unexpected tools: {others}" if others else "")]
                plan = None
            else:
                plan, errors = validate_plan(plan_calls[0].get("args") or {}, contract, max_workers)

            if plan is not None:
                revision = 0 if prev is None else prev["revision"] + 1
                spec = {"goal": state["goal"], "tasks": plan["tasks"], "revision": revision,
                        "rationale": plan.get("rationale", "")}
                log.emit("spec_created" if prev is None else "spec_revised", revision=revision, attempt=attempt,
                         tasks=[t["id"] for t in plan["tasks"]], outputs=[t["output"] for t in plan["tasks"]])
                return {"spec": spec, "tokens_used": res.used_tokens, "usd_used": res.used_usd,
                        "status": "RUNNING"}

            log.emit("plan_invalid", attempt=attempt, errors=errors, iteration=iteration)
            feedback = "Plan rejected by the harness:\n- " + "\n- ".join(errors) + "\nFix these and call SubmitPlan again."
            messages.append(msg)
            ids = call_ids(msg, "call")
            if ids:  # every tool call, valid or not, must be answered before the next turn
                messages += [ToolMessage(content=feedback, tool_call_id=i) for i in ids]
            else:
                messages.append(HumanMessage(feedback))

        return stop("FAILED_PLAN", f"plan_invalid after {attempts} attempts: {'; '.join(errors)}")

    return orchestrator


# ---- fan-out ---------------------------------------------------------------------------

def make_fan_out(max_workers, log):
    """Fan-out: one parallel worker per task; each gets only its own slice of context.

    Ends the run when the orchestrator stopped it (invalid plan, failed model call, no budget).
    The harness also refuses plans wider than max_workers, because the iteration's token
    reservation was sized for at most that many workers.
    """

    def fan_out(state):
        if state.get("status") != "RUNNING":
            return END
        tasks = state["spec"]["tasks"]
        if len(tasks) > max_workers:
            log.emit("plan_rejected", tasks=len(tasks), max_workers=max_workers)
            raise PlanRejected(f"orchestrator planned {len(tasks)} tasks, max_workers is {max_workers}")
        return [
            Send("worker", {"task": t, "iteration": state.get("iteration", 0),
                            "scenario": state["scenario"], "run_id": state["run_id"]})
            for t in tasks
        ]

    return fan_out
