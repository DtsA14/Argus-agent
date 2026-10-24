"""SPEC_AGENT_CONTEXT_RETRY.md section 4: estimated / billed input of every DeepSeek llm_call (status ok, input_tokens > 0)
in the router jobs' ledgers. Read only.

  python3 verification/deepseek_estimate_ratio.py ~/pilot3a_live/jobs
"""
import glob
import json
import os
import statistics as s
import sys

rows, runs = [], set()
for f in glob.glob(os.path.join(sys.argv[1], "*", "runs", "*", "events.jsonl")):
    for line in open(f, encoding="utf-8"):
        try:
            e = json.loads(line)
        except ValueError:
            continue
        if e.get("event") == "llm_call" and e.get("status") == "ok" and "deepseek" in str(e.get("model")) \
                and e.get("input_tokens"):
            rows.append((e["role"], e["est_input"] / e["input_tokens"]))
            runs.add(f)
print(f"{len(runs)} runs, {len(rows)} calls")
for role in sorted({r for r, _ in rows}):
    r = sorted(x for k, x in rows if k == role)
    print(f"{role}: {len(r)} calls; est/billed min {r[0]:.3f} median {s.median(r):.3f} max {r[-1]:.3f}")
