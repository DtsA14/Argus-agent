"""Measure how the code agent's token use grows with the number of files it reads (experiment B, no real model).

  python scripts/measure_context.py calibrate runs/eval_live_4/live_inventory_import ...
  python scripts/measure_context.py simulate

calibrate  Rebuilds the exact messages of every model call of finished live runs from their memo (the rebuild is
           proven exact: each step's recomputed memo key must be found in the memo), counts their characters the way
           the harness does (harness.llm._text plus the tool schemas), and compares with the input tokens Anthropic
           billed. Result: characters per token for this model and this conversation shape.
simulate   Runs the real agent loop (codetask.agent), the real LLMCaller (reservation, refusal before sending) and the
           real tools on synthetic repositories, with a scripted model that follows a reading pattern and a counter
           that uses the calibrated characters per token. Reports, per configuration, the tokens of every call, the
           cumulative total against attempt_tokens, and when and why the attempt ends.

Counts in `simulate` are estimates: they use a ratio calibrated on three live runs, not the provider's tokenizer.
"""
import json
import sqlite3
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage  # noqa: E402

from codetask.agent import make_attempt, system_prompt, task_prompt  # noqa: E402
from codetask.tools import Toolbox, offered  # noqa: E402
from harness import llm as hl  # noqa: E402
from harness.events import EventLog  # noqa: E402
from harness.memo import Memo  # noqa: E402
from harness.steps import llm_step_key, message_from_json  # noqa: E402
from runner import load_config  # noqa: E402

TOOL_VERSIONS = {"ListFiles": "1", "ReadFile": "1", "WriteFile": "1", "Finish": "1", "RunValidation": "1:x"}


def chars(messages, tools):
    return sum(len(hl._text(m)) for m in messages) + sum(len(hl._tool_schema_text(t)) for t in (tools or []))


def rebuild(run_dir, cfg):
    """[(step, messages, tools)] for every model call of attempt 0, rebuilt from the memo and proven exact."""
    run_dir = Path(run_dir)
    contract = json.loads((run_dir / "contract.json").read_text())
    tools = offered(cfg["tools"]["coder"])
    ref = hl.ModelRef.parse(cfg["roles"]["coder"]["model"])
    db = sqlite3.connect(run_dir / "memo.sqlite")
    memo = {k: json.loads(v) for k, v in db.execute("select key, value from memo")}
    messages = [SystemMessage(system_prompt(tools)), HumanMessage(task_prompt(contract))]
    out = []
    for step in range(64):
        key = llm_step_key("agent", contract["contract"], 0, step, messages, tools, ref)
        if key not in memo:
            break
        out.append((step, list(messages), tools))
        msg = message_from_json(memo[key])
        messages.append(msg)
        for i, c in enumerate(msg.tool_calls or []):
            tkey = [k for k in memo if k.startswith('["tool", "agent"') and json.loads(k)[4] == step
                    and json.loads(k)[5] == c.get("id")]
            messages.append(ToolMessage(memo[tkey[0]]["content"], tool_call_id=c.get("id") or f"call_{step}_{i}"))
    return out


def calibrate(run_dirs):
    cfg = load_config()
    rows = []
    for d in run_dirs:
        billed = {e["step"]: e["input_tokens"] for e in map(json.loads, (Path(d) / "events.jsonl").read_text()
                                                              .splitlines()) if e["event"] == "llm_call"
                  and e.get("iteration") == 0}
        calls = rebuild(d, cfg)
        assert len(calls) == len(billed), (d, len(calls), len(billed))
        for step, messages, tools in calls:
            rows.append((Path(d).name, step, chars(messages, tools), billed[step]))
    total_c, total_t = sum(r[2] for r in rows), sum(r[3] for r in rows)
    for r in rows:
        print(f"  {r[0]:<24} step {r[1]}  chars {r[2]:>6}  billed input {r[3]:>5}  chars/token {r[2] / r[3]:.2f}")
    ratio = total_c / total_t
    print(f"calls {len(rows)}: chars/token overall {ratio:.3f} "
          f"(min {min(r[2] / r[3] for r in rows):.2f}, max {max(r[2] / r[3] for r in rows):.2f})")
    return ratio


if __name__ == "__main__":
    if sys.argv[1] == "calibrate":
        calibrate(sys.argv[2:])
