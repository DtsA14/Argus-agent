"""For each failing run: per attempt and step, the input tokens, the tool calls, and the model's own text, from the
ledger and the memo. Run from the repository root on the VM with PYTHONPATH=.: failure_trace.py <run_dir>...
A directory with no result.json is reported as such; a line of the event log that does not decode is skipped and counted."""
import json
import sys
from pathlib import Path

from evals import runlog
from harness.steps import message_from_json

for rd in sys.argv[1:]:
    found = next(Path(rd).rglob("result.json"), None)
    if found is None:
        print(f"##### {Path(rd).name}: no result.json")
        continue
    run = found.parent
    evs, skipped = runlog.read_events(run)
    calls = {(e["iteration"], e["step"]): e for e in evs if e["event"] == "llm_call"}
    llm = {}
    for k, v in runlog.read_memo(run).items():
        key = json.loads(k)
        if key[0] == "llm":
            llm[(key[3], key[4])] = message_from_json(v)
    print(f"##### {Path(rd).name}")
    for (it, st), e in sorted(calls.items()):
        msg = llm.get((it, st))
        text = ""
        tools = []
        if msg is not None:
            c = msg.content
            text = c if isinstance(c, str) else " ".join(p.get("text", "") for p in c if isinstance(p, dict))
            tools = [f"{t['name']}({t['args'].get('path') or t['args'].get('text') or t['args'].get('id') or ''})"
                     for t in msg.tool_calls or []]
        tok = e.get("input_tokens") or e.get("est_input")
        print(f"  it{it} s{st} {e['status']:<7} in {tok:>5} | {' '.join(tools)[:150]}")
        if text.strip():
            print(f"        text: {' '.join(text.split())[:400]}")
    if runlog.skipped_line(skipped):
        print(runlog.skipped_line(skipped))
