"""Rebuild every request of pilot3a4 from the memo, with the D3 after_step message inserted, and compare prompt hashes."""
import json, sqlite3, sys
from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
import harness.llm as hl
from codetask.agent import system_prompt, task_prompt
from codetask.tools import offered
from harness.steps import after_step_key, llm_step_key, message_from_json
from models.registry import ModelRef
run = "runs/pilot3a4"
contract = json.load(open(run + "/contract.json"))
events = [json.loads(l) for l in open(run + "/events.jsonl")]
tools = offered(next(e for e in events if e["event"] == "tools_effective")["tools"])
memo = {k: json.loads(v) for k, v in sqlite3.connect(run + "/memo.sqlite").execute("select key, value from memo")}
calls = [e for e in events if e["event"] == "llm_call" and e.get("node") == "agent"]
ref = ModelRef.parse("anthropic:claude-sonnet-5-5")
msgs = [SystemMessage(system_prompt(tools)), HumanMessage(task_prompt(contract, None))]
for step in range(12):
    led = [e for e in calls if e["iteration"] == 0 and e["step"] == step]
    if not led: break
    print("step", step, "hash", "ok" if led[0]["prompt_hash"] == hl.prompt_hash(msgs, tools) else "MISMATCH", led[0]["status"])
    key = llm_step_key("agent", contract["contract"], 0, step, msgs, tools, ref)
    if key not in memo: break
    m = message_from_json(memo[key]); msgs.append(m)
    for i, c in enumerate(m.tool_calls or []):
        tk = [k for k in memo if k.startswith("[\"tool\", \"agent\"") and json.loads(k)[3] == 0 and json.loads(k)[4] == step and json.loads(k)[5] == c.get("id")]
        msgs.append(ToolMessage(memo[tk[0]]["content"], tool_call_id=c.get("id")))
    after = [v for k, v in memo.items() if k.startswith("[\"after_step\"") and json.loads(k)[3] == 0 and json.loads(k)[4] == step]
    if after and after[0].get("content"):
        msgs.append(HumanMessage(after[0]["content"]))
