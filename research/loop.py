"""One tool-calling loop and one stage run for the research job's stages (SPEC_RESEARCH_JOB §3-4, §9).

The loop follows codetask/research.py (r1): every model reply and every tool result is committed to the memo before the
loop moves on, a tool step's key carries its parent LLM step and the tool's version, a submit whose result was committed
is never gated again, and every model call goes through LLMCaller within one reservation restored from the ledger. The
same reservation pays the stage's web requests (harness/paid.py), so a resumed stage starts from everything it spent.

A stage run is a LangGraph graph with one guarded node (its result committed by harness.guard, checkpoints with
durability="sync"), then result.json.
"""
import json
from pathlib import Path
from typing import TypedDict

from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, StateGraph

from codetask.drafter import FINAL_STEPS, _write, final_from
from codetask.run import RunExists
from harness.crash import Crasher
from harness.errors import EstimateExceeded, InputLimitExceeded, LLMCallFailed, ReservationExhausted
from harness.events import EventLog
from harness.guard import guard
from harness.llm import LLMCaller, http_status, is_truncated, reconcile_ledger
from harness.memo import Memo
from harness.steps import (call_ids, invalid_call_errors, llm_step_key, message_from_json, message_to_json,
                           reservation_from_ledger, tool_step_key)
from models.registry import ConfigError

INPUTS = "inputs.json"


def tool_loop(caller, memo, log, *, node, task_id, lim, system, prompt, tools, submit, versions, run_tool, gate_submit,
              crasher, nudge, steps_note, final_note):
    """Run until the submit tool's result is accepted, the submits or steps run out, or a call cannot be made.
    run_tool(name, args, step_key, reservation) -> {"content"}; gate_submit(args, n, last_step) -> {"content", "finished",
    "exhausted", "result"}. Returns {"end", "steps", "submits", "tokens_used", "usd_used", ["result"]}."""
    meta = {"node": node, "task": task_id, "iteration": 0}
    res = reservation_from_ledger(log, tokens=lim["attempt_tokens"], usd=lim["attempt_usd"],
                                  max_input=lim["max_input_tokens"], **meta)
    name_of_submit = submit.__name__
    submits = 0
    max_steps = lim["max_steps"]

    def end(reason, steps, **out):
        log.emit("loop_end", reason=reason, steps=steps, submits=submits, **meta)
        return {"end": reason, "steps": steps, "submits": submits, "tokens_used": res.used_tokens,
                "usd_used": res.used_usd, **out}

    messages = [SystemMessage(system), HumanMessage(prompt)]
    for step in range(max_steps):
        final = step >= final_from(max_steps)
        if step > 0 and step == max_steps // 2 and not final:
            messages.append(HumanMessage(steps_note.format(n=max_steps - step, max=max_steps)))
        if step == final_from(max_steps):
            messages.append(HumanMessage(final_note.format(n=FINAL_STEPS)))
        step_tools = [submit] if final else tools
        key = llm_step_key(node, task_id, 0, step, messages, step_tools, caller.ref)
        cached = memo.get(key)
        if cached is not None:
            msg = message_from_json(cached)
            log.emit("step_replayed", kind="llm", step=step, **meta)
        else:
            try:
                msg = caller.call(messages, res, tools=step_tools, meta={**meta, "step": step})
            except InputLimitExceeded:
                return end("context_limit", step)
            except ReservationExhausted:
                return end("reservation_exhausted", step)
            except LLMCallFailed as e:
                return end("llm_failed", step, http_status=http_status(e.__cause__) if e.__cause__ else None)
            crasher.point(f"{node}@after_llm", step=step, **meta)
            memo.put(key, message_to_json(msg))
            log.emit("step_committed", kind="llm", step=step, **meta)
        messages.append(msg)
        if is_truncated(msg):
            log.emit("reply_truncated", step=step, tools=[c.get("name") for c in msg.tool_calls or []], **meta)
            return end("output_truncated", step)
        if invalid_call_errors(msg):
            log.emit("invalid_tool_call", step=step, tools=[c.get("name") for c in msg.invalid_tool_calls], **meta)
            reason = "Rejected: " + "; ".join(invalid_call_errors(msg)) + ". Nothing in this reply was executed."
            messages += [ToolMessage(reason, tool_call_id=i) for i in call_ids(msg, f"call_{step}")]
            continue
        calls = list(msg.tool_calls or [])
        if not calls:
            messages.append(HumanMessage(nudge))
            continue
        names = [c.get("name") for c in calls]
        if name_of_submit in names and len(calls) != 1:
            log.emit("submit_rejected", step=step, tools=names, **meta)
            reason = (f"Rejected: {name_of_submit} must be the only tool call in its reply; this reply had "
                      f"{len(calls)} calls {names}. Nothing in it was executed.")
            messages += [ToolMessage(reason, tool_call_id=c.get("id") or f"call_{step}_{i}")
                         for i, c in enumerate(calls)]
            continue
        offered = {t.__name__ for t in step_tools}
        for i, c in enumerate(calls):
            name = c.get("name")
            tkey = tool_step_key(node, task_id, 0, step, c.get("id"), name, c.get("args"),
                                 versions.get(name, "unknown"), parent=key)
            record = memo.get(tkey)
            if record is not None:
                log.emit("step_replayed", kind="tool", step=step, tool=name, **meta)
            else:
                if name not in offered:
                    record = {"content": f"Refused: {name} is not offered " + (
                        f"in the last {FINAL_STEPS} steps; only {name_of_submit} is." if final else "here.")
                        + " Nothing was run.", "finished": False}
                elif name == name_of_submit:
                    record = gate_submit(c.get("args") or {}, submits + 1, step == max_steps - 1)
                else:
                    record = {"content": run_tool(name, c.get("args") or {}, tkey, res), "finished": False}
                crasher.point(f"{node}@after_tool", step=step, **meta)
                crasher.point(f"{node}@after_tool:{name}", step=step, **meta)
                memo.put(tkey, record)
                log.emit("step_committed", kind="tool", step=step, tool=name, **meta)
            if name == name_of_submit:
                submits += 1
            messages.append(ToolMessage(record["content"], tool_call_id=c.get("id") or f"call_{step}_{i}"))
            if record.get("finished"):
                return end("submitted", step, result=record["result"])
            if record.get("exhausted"):
                return end("submits_exhausted", step)
    return end("max_steps", max_steps)


def with_fallbacks(cfg, role, log, memo, *, node, task_id, models, loop):
    """loop(caller) -> tool_loop's result, on the role's model, or on its next free fallback when the model was rate
    limited (HTTP 429, after LLMCaller's retries) before any reply of this loop (step 0). The model in use is committed
    to the memo before its first call, so a resumed stage continues on it and never asks an earlier model again (its
    committed steps are keyed by its model). models: injected chat models by role, or by "role@model" (tests)."""
    from models.gateway import fallback_chain
    chain = fallback_chain(cfg, role)
    key = f"model_choice:{node}:{task_id}"
    chosen = memo.get(key)
    if chosen is not None and chosen not in chain:
        raise ConfigError(f"{node} {task_id} runs on {chosen}, which is no longer in roles.{role}'s fallback chain "
                          f"{chain}; put it back to resume this stage")
    i = chain.index(chosen) if chosen is not None else 0
    caps = (cfg.get("research_job") or {}).get("max_output_tokens_by_model") or {}
    while True:
        model = chain[i]
        role_cfg = {**cfg["roles"][role], "model": model}
        if i > 0 and model in caps:                      # a fallback's own output cap (the primary's was set before)
            role_cfg["max_output_tokens"] = int(caps[model])
        rcfg = {**cfg, "roles": {**cfg["roles"], role: role_cfg}}
        injected = (models or {}).get(f"{role}@{model}") or ((models or {}).get(role) if i == 0 else None)
        a = loop(LLMCaller(rcfg, role, log, model=injected))
        if a["end"] == "llm_failed" and a["steps"] == 0 and a.get("http_status") == 429 and i + 1 < len(chain):
            memo.put(key, chain[i + 1])                  # committed first: a crash here resumes on the next model
            log.emit("model_fallback", role=role, node=node, task=task_id, model=model, next=chain[i + 1])
            i += 1
            continue
        return a


class State(TypedDict, total=False):
    run_id: str
    out: dict
    tokens_used: int
    usd_used: float
    elapsed_s: float


def run_stage(*, run_id, runs_dir, inputs, resume, kind, work, estimate, usd_estimate, retry, crash_at=None, echo=False):
    """One stage run: inputs.json kept for a resume, one guarded node `work(log, memo, crasher, inputs) -> dict`, and
    result.json with the ledger's totals. Returns the result."""
    run_dir = Path(runs_dir) / run_id
    if not resume and (run_dir / "checkpoints.sqlite").exists():
        raise RunExists(f"run '{run_id}' already exists in {runs_dir}; resume it or pick a new run id")
    if resume and not (run_dir / "checkpoints.sqlite").exists():
        raise RunExists(f"nothing to resume: run '{run_id}' has no checkpoint in {runs_dir}")
    run_dir.mkdir(parents=True, exist_ok=True)
    if resume:
        inputs = json.loads((run_dir / INPUTS).read_text(encoding="utf-8"))
    else:
        _write(run_dir / INPUTS, json.dumps(inputs, indent=2, ensure_ascii=False) + "\n")
    log = EventLog(run_dir / "events.jsonl", echo=echo)
    memo = Memo(run_dir / "memo.sqlite")
    crasher = Crasher(crash_at, str(run_dir / ".crashed"), log)
    common = dict(log=log, retry=retry, memo=memo, crash_at=crash_at, crash_marker=str(run_dir / ".crashed"))

    def node(state):
        out = work(log, memo, crasher, inputs, run_dir)
        # reported to guard, which refuses a node run that spent more than its estimate (EstimateExceeded)
        return {"out": out, "tokens_used": out.get("tokens_used", 0), "usd_used": out.get("usd_used", 0.0)}

    g = StateGraph(State)
    g.add_node("work", guard("work", node, estimate=estimate, usd_estimate=usd_estimate, **common))
    g.add_edge(START, "work")
    g.add_edge("work", END)
    config = {"configurable": {"thread_id": run_id}, "recursion_limit": 10}
    with SqliteSaver.from_conn_string(str(run_dir / "checkpoints.sqlite")) as cp:
        graph = g.compile(checkpointer=cp)
        try:
            if resume and graph.get_state(config).values:
                log.emit("resume", run_id=run_id)
                graph.invoke(None, config, durability="sync")
            else:                                          # new, or a crash before the first checkpoint was written
                log.emit("run_start", run_id=run_id, kind=kind, max_usd=inputs.get("max_usd"))
                graph.invoke({"run_id": run_id}, config, durability="sync")
            out = dict(graph.get_state(config).values).get("out") or {}
        except EstimateExceeded as e:
            log.emit("budget_violation", source="node", error=str(e))
            out = {"status": "FAILED_BUDGET", "stop_reason": f"budget_violation: {e}"}
    _, totals = reconcile_ledger(log.read())
    result = {**out, "run_id": run_id, "kind": kind, "usd_billed": totals["usd"], "usd_complete": totals["usd_complete"],
              "calls": totals["calls"], "calls_unknown": totals["unknown_after_crash"]}
    _write(run_dir / "result.json", json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    log.emit("run_end", **{k: v for k, v in result.items() if k not in ("plan", "findings")})
    return result
