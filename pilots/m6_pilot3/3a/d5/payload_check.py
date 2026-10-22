"""D5 preflight without the provider: the Anthropic request body langchain_anthropic builds from a coder step with Argus's
cache markers (harness.llm.with_cache_markers). No network, no key: ChatAnthropic only formats the payload here.

  PYTHONPATH=. python pilots/m6_pilot3/3a/d5/payload_check.py

Checks: one marker on the last system block (tools and system render before it), one on the last block of the last
message (a tool_result after a tool step, a text block otherwise), none elsewhere, at most 4, and the messages the harness
keeps (memo, hashes) carry none.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path.cwd()))
from langchain_anthropic import ChatAnthropic  # noqa: E402
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage  # noqa: E402

from codetask.agent import system_prompt  # noqa: E402
from codetask.tools import offered  # noqa: E402
from harness.llm import prompt_hash, with_cache_markers  # noqa: E402

tools = offered(["list_files", "read_file", "write_file", "run_validation", "search_files", "edit_file"])
chat = ChatAnthropic(model="claude-sonnet-5-5", api_key="not-a-key-payload-only", max_tokens=8192)
bound_kwargs = chat.bind_tools(tools).kwargs
cases = {
    "first request": [SystemMessage(system_prompt(tools)), HumanMessage("the task")],
    "after a tool step": [SystemMessage(system_prompt(tools)), HumanMessage("the task"),
                          AIMessage("", tool_calls=[{"name": "ReadFile", "args": {"path": "a.py"}, "id": "t1"},
                                                    {"name": "ReadFile", "args": {"path": "b.py"}, "id": "t2"}]),
                          ToolMessage("contents of a", tool_call_id="t1"), ToolMessage("contents of b", tool_call_id="t2")],
    "after an auto-validation message (D3)": [SystemMessage(system_prompt(tools)), HumanMessage("the task"),
                          AIMessage("", tool_calls=[{"name": "WriteFile", "args": {"path": "a.py", "content": "x"}, "id": "w1"}]),
                          ToolMessage("a.py now has 1 bytes", tool_call_id="w1"),
                          HumanMessage("Harness check after your changes (...): validation:x: fail")],
}
ok = True


def markers(obj, path=""):
    """Every place in the payload that carries cache_control."""
    out = []
    if isinstance(obj, dict):
        if "cache_control" in obj:
            out.append((path, obj["cache_control"]))
        for k, v in obj.items():
            out += markers(v, f"{path}.{k}")
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            out += markers(v, f"{path}[{i}]")
    return out


for name, msgs in cases.items():
    before = prompt_hash(msgs, tools)
    payload = chat._get_request_payload(with_cache_markers(msgs), **bound_kwargs)
    found = markers(payload)
    last = payload["messages"][-1]["content"][-1]
    want_sys = f".system[{len(payload['system']) - 1}]"
    want_last = f".messages[{len(payload['messages']) - 1}].content[{len(payload['messages'][-1]['content']) - 1}]"
    good = (sorted(p for p, _ in found) == sorted([want_sys, want_last]) and len(found) <= 4
            and all(c == {"type": "ephemeral"} for _, c in found)
            and prompt_hash(msgs, tools) == before
            and not any("cache_control" in json.dumps(m.content) for m in msgs))
    ok = ok and good
    print(f"{'ok ' if good else 'BAD'} {name}: markers at {[p for p, _ in found]}; last block type {last.get('type')}; "
          f"{len(payload['tools'])} tools; messages kept unmarked: {not any('cache_control' in json.dumps(m.content) for m in msgs)}")
print("RESULT:", "ok" if ok else "FAILED")
sys.exit(0 if ok else 1)
