"""Per-step memo for agent loops, and node reservations that survive a crash.

Step keys carry the identity of the step's input, so a memo entry is reused only for exactly the
same input. Replaying committed steps rebuilds the same messages, so later keys match too; any
change to the instruction, feedback, model, tools or tool version changes the hash and the old
entry is simply never looked up.

  LLM step : ("llm",  node, task, iteration, step, sha256(messages, tool schemas, model))
  tool step: ("tool", node, task, iteration, step, tool_call_id, sha256(name, args, LLM step key), tool version)

A tool step is tied to the LLM step that requested it (its key carries the input hash), so a tool
result is never reused under a different input, even when name, arguments and call id coincide.

The memo prevents re-calls; the ledger stays the source of truth for spend. reservation_from_ledger()
starts a node run's reservation with everything that (node, task, iteration) already spent in
earlier processes, including calls cut off by a crash at their worst case, so a node can never spend
its estimate twice across a crash, and replays from the memo cost nothing extra.
"""
import hashlib
import json

from langchain_core.messages import AIMessage

from .llm import Reservation, _text, _tool_schema_text, is_truncated, reconcile_ledger


def _sha(obj):
    return hashlib.sha256(json.dumps(obj, sort_keys=True, ensure_ascii=False, default=str).encode()).hexdigest()


def llm_step_key(node, task, iteration, step, messages, tools, model_ref):
    identity = {
        "messages": [(type(m).__name__, _text(m)) for m in messages],
        "tools": [_tool_schema_text(t) for t in (tools or [])],
        "model": str(model_ref),
    }
    return json.dumps(["llm", node, task, iteration, step, _sha(identity)])


def tool_step_key(node, task, iteration, step, tool_call_id, name, args, version, parent):
    """parent: the key of the LLM step whose reply contained this tool call."""
    return json.dumps(["tool", node, task, iteration, step, tool_call_id, _sha([name, args, parent]), version])


def invalid_calls(msg):
    """Tool calls the provider returned but whose arguments could not be parsed (LangChain's invalid_tool_calls).
    They are never treated as valid calls, but they are still tool calls: each must be answered."""
    return list(getattr(msg, "invalid_tool_calls", None) or [])


def call_ids(msg, prefix):
    """Every tool call id in a reply, valid or not. Each needs a ToolMessage before the next model turn: providers
    reject the request otherwise (DeepSeek answered HTTP 400 in calibration run #3, docs/reviews/REVIEW_3D.md)."""
    return [c.get("id") or f"{prefix}_{i}" for i, c in enumerate(list(msg.tool_calls or []) + invalid_calls(msg))]


def invalid_call_errors(msg):
    return [f"the {c.get('name') or 'tool'} call had arguments that are not valid JSON ({str(c.get('error') or '')[:120]}); "
            f"call it again with valid arguments" for c in invalid_calls(msg)]


def message_to_json(msg):
    return {
        "content": msg.content,
        "tool_calls": [{"name": c["name"], "args": c["args"], "id": c["id"]} for c in (msg.tool_calls or [])],
        # kept so a replayed reply is the reply that was received (and is answered the same way)
        "invalid_tool_calls": [{"name": c.get("name"), "args": c.get("args"), "id": c.get("id"), "error": c.get("error")}
                               for c in invalid_calls(msg)],
        "usage_metadata": dict(msg.usage_metadata) if getattr(msg, "usage_metadata", None) else None,
        "truncated": is_truncated(msg),  # a replayed cut-off reply must stay cut off
    }


def message_from_json(d):
    kw = {"content": d["content"]}
    if d.get("tool_calls"):
        kw["tool_calls"] = d["tool_calls"]
    if d.get("invalid_tool_calls"):
        kw["invalid_tool_calls"] = [{**c, "type": "invalid_tool_call"} for c in d["invalid_tool_calls"]]
    if d.get("usage_metadata"):
        kw["usage_metadata"] = d["usage_metadata"]
    if d.get("truncated"):
        kw["response_metadata"] = {"truncated": True}
    return AIMessage(**kw)


def reservation_from_ledger(log, *, tokens, usd, node, task, iteration, max_input=None):
    """A fresh reservation for one node run, already charged with what this same node run spent in
    earlier processes (all attempts, plus calls cut off by a crash at worst case)."""
    mine = [e for e in log.read()
            if e.get("event") in ("llm_call_started", "llm_call") and e.get("status") != "refused"
            and e.get("node") == node and e.get("task") == task and e.get("iteration") == iteration]
    res = Reservation(tokens=tokens, usd=usd, max_input=max_input)
    if mine:
        _, totals = reconcile_ledger(mine)
        res.charge(totals["tokens"], totals["usd_nano"])
        log.emit("reservation_restored", node=node, task=task, iteration=iteration,
                 calls=totals["calls"], unknown_after_crash=totals["unknown_after_crash"],
                 tokens=totals["tokens"], usd_nano=totals["usd_nano"])
    return res
