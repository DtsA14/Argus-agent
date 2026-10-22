"""Per call: input, the output cap the harness set, and what the attempt reservation left. Usage: caps.py <events.jsonl>"""
import json
import sys

calls = [json.loads(line) for line in open(sys.argv[1]) if '"event": "llm_call"' in line]
for it in sorted({c["iteration"] for c in calls}):
    spent = 0
    for c in (c for c in calls if c["iteration"] == it):
        left = 30000 - spent
        tin = c.get("input_tokens") or c.get("est_input")
        print(f"it{it} s{c['step']} in {tin:>6} cap {c.get('max_tokens')!s:>5} out {c.get('output_tokens')!s:>5} "
              f"reasoning {c.get('reasoning_tokens')!s:>5} | attempt left before {left:>6}, after input {left - tin:>6}")
        spent += c.get("tokens") or 0
