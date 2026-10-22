"""Audit of one live code-task run: rebuild every model call from the memo with the run's effective tools,
check each ledger prompt_hash against it, and list calls, tool calls, refusals and statuses.

  PYTHONPATH=. python scripts/audit_run.py <run_dir>
"""
import hashlib
import json
import sqlite3
import sys
from pathlib import Path

from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage

import harness.llm as hl
from codetask.agent import feedback_from, system_prompt, task_prompt
from codetask.tools import offered
from harness.llm import is_truncated
from harness.steps import llm_step_key, message_from_json
from runner import load_config

run_dir = Path(sys.argv[1])
cfg = load_config()
contract = json.loads((run_dir / "contract.json").read_text())
result = json.loads((run_dir / "result.json").read_text())
tools = offered(result["tools"])
sp = system_prompt(tools)
print("effective tools", result["tools"])
print("effective system prompt sha256", hashlib.sha256(sp.encode()).hexdigest())
memo = {k: json.loads(v) for k, v in sqlite3.connect(run_dir / "memo.sqlite").execute("select key, value from memo")}
events = [json.loads(l) for l in (run_dir / "events.jsonl").read_text().splitlines()]
calls = [e for e in events if e["event"] == "llm_call"]
ref = hl.ModelRef.parse(calls[0]["model"])          # the model the run used (the ledger records it)
started = [e for e in events if e["event"] == "llm_call_started"]
print(f"llm_call_started {len(started)}, llm_call {len(calls)} "
      f"(ok {sum(e['status'] == 'ok' for e in calls)}, refused {sum(e['status'] == 'refused' for e in calls)})")

mismatch, checked = 0, 0
for it in range(contract["limits"].get("max_iterations", 5)):
    feedback = None
    if it > 0:
        prev = run_dir / f"verdict_{it - 1}.json"
        if not prev.exists():
            break
        verdict = json.loads(prev.read_text())
        feedback = feedback_from(verdict)
        first = [e for e in calls if e.get("iteration") == it and e.get("step") == 0]
        legacy = [f"{c['id']}: {c['reason'][:300]}" for c in verdict["criteria"] if c["status"] != "pass"][:10]

        def matches(fb):
            return bool(first) and hl.prompt_hash([SystemMessage(sp), HumanMessage(task_prompt(contract, fb))],
                                                  tools) == first[0]["prompt_hash"]
        if not matches(feedback):
            plain = feedback_from(verdict, excerpts=False)
            if matches(plain):
                feedback = plain            # a run from before D2, or with code_task.feedback_error_excerpt: false
                print(f"  it {it}: feedback without error excerpts")
            elif matches(legacy):
                feedback = legacy           # a run from before the feedback carried the harness's checks
                print(f"  it {it}: feedback in the older form (failing criteria only)")
    messages = [SystemMessage(sp), HumanMessage(task_prompt(contract, feedback))]
    for step in range(64):
        led = [e for e in calls if e.get("iteration") == it and e.get("step") == step]
        if not led:
            break
        want = hl.prompt_hash(messages, tools)
        for e in led:
            checked += 1
            ok = e["prompt_hash"] == want
            mismatch += not ok
            print(f"  it {it} step {step:2} {e['status']:<8} hash {'ok' if ok else 'MISMATCH'} "
                  f"in {e.get('input_tokens', e.get('est_input'))} out {e.get('output_tokens')} "
                  f"usd {e.get('usd')} " + (f"tokens_left {e.get('tokens_left')}" if e['status'] != 'ok' else ""))
        key = llm_step_key("agent", contract["contract"], it, step, messages, tools, ref)
        if key not in memo:
            break
        msg = message_from_json(memo[key])
        messages.append(msg)
        if is_truncated(msg):                   # the harness ran none of its tool calls and ended the attempt
            print(f"      (reply cut off at max_tokens: {[c['name'] for c in msg.tool_calls or []]} not run)")
            break
        for i, c in enumerate(msg.tool_calls or []):
            print(f"      -> {c['name']} {json.dumps(c['args'])[:160]}")
            tk = [k for k in memo if k.startswith('["tool", "agent"') and json.loads(k)[3] == it
                  and json.loads(k)[4] == step and json.loads(k)[5] == c.get("id")]
            messages.append(ToolMessage(memo[tk[0]]["content"], tool_call_id=c.get("id") or f"call_{step}_{i}"))
        after = [v for k, v in memo.items() if k.startswith('["after_step", "agent"') and json.loads(k)[3] == it
                 and json.loads(k)[4] == step and v.get("content")]
        if after:                               # D3: the auto-validation message the agent got after this step
            print(f"      (harness check after the step: {'limit notice' if after[0].get('limit_notice') else 'validated'})")
            messages.append(HumanMessage(after[0]["content"]))
print(f"prompt_hash checked {checked}, mismatches {mismatch}")
for e in events:
    if e["event"] in ("attempt_end", "status", "budget_violation", "tools_config_changed", "tool_denied"):
        print(" ", {k: v for k, v in e.items() if k not in ("ts",)})
print("result", {k: result.get(k) for k in ("status", "stop_reason", "blocked_reason", "attempts", "usd_billed",
                                           "llm_calls", "llm_calls_unknown", "tools")})
