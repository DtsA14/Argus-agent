"""One attempt of the code agent: a tool-calling loop with the same crash guarantees as the M2 worker.

Per step:  model call -> commit reply -> run each tool call -> commit each tool result -> next step.
On resume, committed steps are replayed from the memo (no model call, no tool run). A tool that ran but whose
result was not committed runs again; every tool is safe to repeat (a write replaces the whole file atomically, so
repeating it leaves the same file). The attempt's reservation starts from what this attempt already
spent according to the ledger, so a crash never lets it spend its budget twice.

An attempt ends with Finish, after max_steps, when its reservation is exhausted, when the provider fails, or on a
cut-off reply. Whatever the reason, the harness then checks the workspace; the end reason only shapes what follows.
"""
from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage

from harness.crash import Crasher
from harness.errors import LLMCallFailed, ReservationExhausted
from harness.llm import is_truncated
from harness.steps import (call_ids, invalid_call_errors, llm_step_key, message_from_json, message_to_json,
                           reservation_from_ledger, tool_step_key)

from .tools import offered

NODE = "agent"


def system_prompt(tools):
    names = {t.__name__ for t in tools}
    lines = ["You are a software agent. You fix one issue in a copy of a repository, using only the tools below.",
             "", "Tools:"]
    desc = {"ListFiles": "list every file of the repository",
            "ReadFile": "read one file",
            "WriteFile": "replace a whole file; only files in the writable scope can be written",
            "RunValidation": "run one of the contract's validation commands in a sandbox and see the result",
            "Finish": "end the attempt with your claims"}
    lines += [f"- {n}: {desc[n]}" for n in desc if n in names]
    lines += ["", "Rules:",
              "- Protected files (for example the tests) must not change. Fix the code, not the tests.",
              "- You do not decide whether the task is done. The harness runs every validation itself, checks which "
              "files changed, and checks each claim against its own evidence.",
              "- Claims: tests_pass and issue_fixed name a validation as evidence (validation:<id>) that passes; "
              "file_changed names a file you changed. A claim the evidence does not support fails the task.",
              "- Call Finish alone in its reply, once you are done."]
    return "\n".join(lines)


def task_prompt(contract, feedback=None):
    sc = contract["scope"]
    vals = [f"  - {v['id']}" + (f" (required tests: {', '.join(v['must_pass'])})" if v.get("must_pass") else "")
            for v in contract["validation"]]
    parts = [f"Issue: {contract['inputs']['issue']}",
             f"Writable: {', '.join(sc['writable'])}",
             f"Protected: {', '.join(sc['protected'])}",
             "Validations the harness will run:", *vals]
    if feedback:
        parts += ["", "The previous attempt did not meet the contract. The harness found:", *[f"  - {f}" for f in feedback]]
    return "\n".join(parts)


NUDGE = "Use the tools to work on the issue, then call Finish."


def make_attempt(caller, memo, log, *, tokens, usd, max_steps, tool_versions, crasher=None):
    crasher = crasher or Crasher()

    def attempt(contract, toolbox, iteration, feedback=None):
        tid = contract["contract"]
        meta = {"node": NODE, "task": tid, "iteration": iteration}
        res = reservation_from_ledger(log, tokens=tokens, usd=usd, **meta)
        tools = offered(toolbox.allowed)

        def end(reason, steps):
            log.emit("attempt_end", reason=reason, steps=steps, **meta)
            return {"end": reason, "steps": steps, "tokens_used": res.used_tokens, "usd_used": res.used_usd}

        messages = [SystemMessage(system_prompt(tools)), HumanMessage(task_prompt(contract, feedback))]
        for step in range(max_steps):
            key = llm_step_key(NODE, tid, iteration, step, messages, tools, caller.ref)
            cached = memo.get(key)
            if cached is not None:
                msg = message_from_json(cached)
                log.emit("step_replayed", kind="llm", step=step, **meta)
            else:
                try:
                    msg = caller.call(messages, res, tools=tools, meta={**meta, "step": step})
                except ReservationExhausted:
                    return end("reservation_exhausted", step)
                except LLMCallFailed:
                    return end("llm_failed", step)
                crasher.point("agent@after_llm", step=step, **meta)          # reply not yet committed
                memo.put(key, message_to_json(msg))
                log.emit("step_committed", kind="llm", step=step, **meta)
                crasher.point("agent@llm_committed", step=step, **meta)
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
                messages.append(HumanMessage(NUDGE))
                continue
            names = [c.get("name") for c in calls]
            if "Finish" in names and len(calls) != 1:
                log.emit("finish_rejected", step=step, tools=names, **meta)
                reason = (f"Rejected: Finish must be the only tool call in its reply; this reply had {len(calls)} "
                          f"calls {names}. Nothing in it was executed.")
                messages += [ToolMessage(reason, tool_call_id=c.get("id") or f"call_{step}_{i}")
                             for i, c in enumerate(calls)]
                continue
            finished = False
            for i, c in enumerate(calls):
                tkey = tool_step_key(NODE, tid, iteration, step, c.get("id"), c.get("name"), c.get("args"),
                                     tool_versions.get(c.get("name"), "unknown"), parent=key)
                record = memo.get(tkey)
                if record is not None:
                    log.emit("step_replayed", kind="tool", step=step, tool=c.get("name"), **meta)
                else:
                    record = toolbox.run(c)
                    crasher.point("agent@after_tool", step=step, **meta)      # ran, result not yet committed
                    crasher.point(f"agent@after_tool:{c.get('name')}", step=step, **meta)
                    memo.put(tkey, record)
                    log.emit("step_committed", kind="tool", step=step, tool=c.get("name"), **meta)
                    crasher.point("agent@tool_committed", step=step, **meta)
                messages.append(ToolMessage(record["content"], tool_call_id=c.get("id") or f"call_{step}_{i}"))
                finished = finished or bool(record.get("finished"))
            if finished:
                return end("finished", step)
        return end("max_steps", max_steps)

    return attempt


def feedback_from(verdict, limit=10):
    """What the next attempt is told: the failing criteria and their reasons, bounded."""
    out = [f"{c['id']}: {c['reason'][:300]}" for c in verdict["criteria"] if c["status"] != "pass"]
    return out[:limit]

