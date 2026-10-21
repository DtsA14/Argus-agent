"""Where did the tokens of the live run pilot3a go, and what did the agent see? Read-only: reads the ledger (events.jsonl), the memo and the verdicts of
a finished run. No model, no sandbox, no cost.
  PYTHONPATH=. python pilots/m6_pilot3/3a/investigate.py runs/pilot3a
"""
import json
import sys
from pathlib import Path

ROOT = Path.cwd()
sys.path.insert(0, str(ROOT))
from codetask.agent import feedback_from, task_prompt  # noqa: E402

run = Path(sys.argv[1])
events = [json.loads(line) for line in (run / "events.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
contract = json.loads((run / "contract.json").read_text(encoding="utf-8"))
RESERVATION = 45000

print("== 1. the ledger: every model call of the run")
print(f"{'it':>2} {'step':>4} {'status':<8} {'est_in':>7} {'in':>7} {'out':>6} {'max_tok':>7} {'used_before':>11} {'left_before':>11}")
used = {}
for e in events:
    if e["event"] == "llm_call_started":
        it = e["iteration"]
        used.setdefault(it, 0)
        e["_used_before"] = used[it]
    if e["event"] == "llm_call":
        it = e["iteration"]
        before = used.get(it, 0)
        tin, tout = e.get("input_tokens") or 0, e.get("output_tokens") or 0
        print(f"{it:>2} {e['step']:>4} {e['status']:<8} {e.get('est_input', 0):>7} {tin:>7} {tout:>6} {e.get('max_tokens', 0):>7} {before:>11} {RESERVATION - before:>11}")
        if e["status"] == "ok":
            used[it] = before + tin + tout
        if e["status"] == "refused":
            print(f"      refused: est_in {e.get('est_input')} + at least min_output would need {e.get('est_input', 0) + 64}, left {RESERVATION - before}")

print()
print("== 2. what each tool result added to the context (characters -> tokens at ~0.3186 per character + 407 per call)")
import sqlite3  # noqa: E402
db = sqlite3.connect(run / "memo.sqlite")
rows = []
for k, v in db.execute("select key, value from memo"):
    key = json.loads(k)
    if key[0] == "tool":
        val = json.loads(v)
        content = val.get("content") if isinstance(val, dict) else str(val)
        rows.append((key[3], key[4], key[5], len(content or ""), (content or "")[:70].replace("\n", " ")))
for it, step, cid, n, head in sorted(rows):
    print(f"  it{it} s{step} {cid:<8} {n:>6} chars (~{round(0.3186 * n):>5} tokens)  {head!r}")

print()
print("== 3. what the agent was told when attempt 1 started (task prompt with the feedback of verdict_0)")
verdict0 = json.loads((run / "verdict_0.json").read_text(encoding="utf-8"))
feedback = feedback_from(verdict0)
prompt = task_prompt(contract, feedback)
i = prompt.find("feedback") if "feedback" in prompt else 0
print(f"  prompt length {len(prompt)} chars; the feedback part:")
print("  " + "\n  ".join(str(prompt[prompt.lower().find('previous') if 'previous' in prompt.lower() else 0:][:2600]).splitlines()))
