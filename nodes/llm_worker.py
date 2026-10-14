"""Phase 2c: the worker as a tool-calling loop, with a per-step memo.

Per step:  model call -> commit reply -> run each tool call -> commit each tool result -> next step.
On resume, committed steps are replayed from the memo: no model call, no tool execution.
The node's reservation starts with what this node run already spent before a crash (ledger).
"""
import json
from pathlib import Path
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
from pydantic import BaseModel, Field

from harness.crash import Crasher
from harness.errors import LLMCallFailed, ReservationExhausted
from harness.steps import (llm_step_key, message_from_json, message_to_json, reservation_from_ledger,
                           tool_step_key)

from .contract import validate_output

# Bump a tool's version when its behaviour or output format changes: memo entries of the old
# version are then never reused.
TOOL_VERSIONS = {"ReadData": "1", "SubmitResult": "1"}   # RunPython: "1:<pinned image>", set per worker


class ReadData(BaseModel):
    """Return every row of the sales CSV as JSON: [{"month", "product", "omzet"}, ...]."""


class SubmitResult(BaseModel):
    """Submit your final output. Call this once, when the value is complete and in the exact format required."""
    value: Any = Field(description="The output value, exactly in the format described in the task.")
    notes: str = Field(default="", description="Optional: one sentence on how it was computed.")


class RunPython(BaseModel):
    """Run Python 3 code in an isolated sandbox and return its stdout/stderr. The sales CSV is at
    /data/penjualan.csv (read-only). /workspace is writable. There is no network. Print what you need."""
    code: str = Field(description="Complete Python 3 program. Print the results you need to stdout.")


TOOLS = [ReadData, SubmitResult]


def system_prompt():
    return """You are a worker agent. You receive one task and must finish it with tools.

Tools:
- ReadData: returns the sales data rows. Call it before computing anything.
- SubmitResult: submit the final value. The harness checks its format; if it is rejected you get
  the errors and can submit again.

Compute exactly; never estimate or round revenue. Submit only the value asked for, in the exact format."""


def task_prompt(task, contract):
    out = contract["outputs"][task["output"]]
    parts = [
        f"Task id: {task['id']}",
        f"Instruction: {task['instruction']}",
        f"Output `{task['output']}`: {out['description']}",
        f"Data: {json.dumps(contract['data'], ensure_ascii=False)}",
    ]
    if task.get("feedback"):
        parts.append(f"Feedback from the previous attempt: {task['feedback']}")
    return "\n".join(parts)


def make_llm_worker(caller, contract, gate, memo, log, *, tokens, usd, max_steps=6, crasher=None, sandbox=None):
    """sandbox: None, or {"cfg": sandbox config, "workspace": dir, "data_dir": dir} to offer RunPython."""
    crasher = crasher or Crasher()
    sys_msg = SystemMessage(system_prompt())
    tools = list(TOOLS) + ([RunPython] if sandbox else [])
    run_python_version = None
    if sandbox:
        from tools.sandbox import tool_version
        run_python_version = tool_version(sandbox["cfg"])

    def version_of(name):   # looked up live, so a bumped TOOL_VERSIONS entry takes effect immediately
        return run_python_version if name == "RunPython" and sandbox else TOOL_VERSIONS.get(name, "unknown")

    def run_tool(call, output_name, meta):
        """Execute one tool call. Returns a JSON-able record: content for the model, and whether a
        valid result was submitted."""
        name, args = call.get("name"), call.get("args") or {}
        if name == "ReadData":
            rows = gate.call("read_data")
            return {"content": json.dumps(rows, ensure_ascii=False), "accepted": False}
        if name == "SubmitResult":
            if "value" not in args:
                return {"content": "Rejected: SubmitResult needs a 'value'.", "accepted": False}
            errors = validate_output(output_name, args["value"])
            if errors:
                return {"content": "Rejected:\n- " + "\n- ".join(errors), "accepted": False, "errors": errors}
            return {"content": "Accepted.", "accepted": True, "value": args["value"]}
        if name == "RunPython" and sandbox:
            from tools.sandbox import SandboxUnavailable
            code = args.get("code")
            if not isinstance(code, str) or not code.strip():
                return {"content": "Rejected: RunPython needs non-empty 'code'.", "accepted": False}
            try:
                r = gate.call("run_python", code, workdir=Path(sandbox["workspace"]) / meta["task"],
                              data_dir=sandbox["data_dir"], sandbox_cfg=sandbox["cfg"], log=log, meta=meta)
            except SandboxUnavailable as e:
                return {"content": f"Sandbox unavailable, code was not run: {e}", "accepted": False}
            return {"content": json.dumps(r, ensure_ascii=False), "accepted": False}
        return {"content": f"Unknown tool {name!r}. Available: {[t.__name__ for t in tools]}.", "accepted": False}

    def worker(p):
        task, it = p["task"], p["iteration"]
        tid, output = task["id"], task["output"]
        meta = {"node": "worker", "task": tid, "iteration": it}
        res = reservation_from_ledger(log, tokens=tokens, usd=usd, **meta)

        def finish(value=None, error=None):
            result = {"output": output, "value": value, "iteration": it}
            if error:
                result["error"] = error
                log.emit("worker_failed", error=error[:300], **meta)
            return {"results": {tid: result}, "tokens_used": res.used_tokens, "usd_used": res.used_usd}

        messages = [sys_msg, HumanMessage(task_prompt(task, contract))]
        for step in range(max_steps):
            key = llm_step_key("worker", tid, it, step, messages, tools, caller.ref)
            cached = memo.get(key)
            if cached is not None:
                msg = message_from_json(cached)
                log.emit("step_replayed", kind="llm", step=step, **meta)
            else:
                try:
                    msg = caller.call(messages, res, tools=tools, meta={**meta, "step": step})
                except ReservationExhausted as e:
                    return finish(error=f"node_reservation: {e}")
                except LLMCallFailed as e:
                    return finish(error=f"llm_failed: {e}")
                crasher.point("worker@after_llm", step=step, **meta)       # reply not yet committed
                memo.put(key, message_to_json(msg))
                log.emit("step_committed", kind="llm", step=step, **meta)
                crasher.point("worker@llm_committed", step=step, **meta)
            messages.append(msg)

            calls = list(msg.tool_calls or [])
            if not calls:
                messages.append(HumanMessage("Use the tools: ReadData to get the data, SubmitResult to finish."))
                continue
            names = [c.get("name") for c in calls]
            if "SubmitResult" in names and len(calls) != 1:
                # Strict contract (GPT audit 2c): a submission must be the reply's only tool call. A mix
                # (or two submissions) is ambiguous, so nothing in this reply is executed or accepted.
                log.emit("submission_rejected", step=step, tools=names, **meta)
                reason = (f"Rejected: SubmitResult must be the only tool call in its reply; this reply had "
                          f"{len(calls)} tool calls {names}. Nothing in it was executed. Call SubmitResult alone.")
                messages += [ToolMessage(reason, tool_call_id=c.get("id") or f"call_{step}_{i}")
                             for i, c in enumerate(calls)]
                continue
            submitted = None
            for c in calls:
                tkey = tool_step_key("worker", tid, it, step, c.get("id"), c.get("name"), c.get("args"),
                                     version_of(c.get("name")), parent=key)
                record = memo.get(tkey)
                if record is not None:
                    log.emit("step_replayed", kind="tool", step=step, tool=c.get("name"), **meta)
                else:
                    record = run_tool(c, output, meta)
                    memo.put(tkey, record)                                  # committed before moving on
                    log.emit("step_committed", kind="tool", step=step, tool=c.get("name"), **meta)
                    crasher.point("worker@tool_committed", step=step, **meta)
                messages.append(ToolMessage(record["content"], tool_call_id=c.get("id") or f"call_{step}"))
                if record.get("accepted") and submitted is None:
                    submitted = record["value"]
            if submitted is not None:
                log.emit("worker_submitted", step=step, **meta)
                return finish(value=submitted)

        return finish(error=f"max_steps: no accepted SubmitResult after {max_steps} steps")

    return worker
