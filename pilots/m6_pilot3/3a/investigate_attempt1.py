import json, sqlite3, sys
from pathlib import Path
run = Path("runs/pilot3a")
db = sqlite3.connect(run / "memo.sqlite")
for k, v in db.execute("select key, value from memo"):
    key = json.loads(k)
    if key[0] == "tool" and key[3] == 1 and key[4] == 0 and key[5] == "toolu_01KP3hQo6QqCCavNBi8UDNii":
        c = json.loads(v)["content"]
        print("RunValidation(inspectors) result seen by the agent in attempt 1, step 0 (%d chars):" % len(c))
        d = json.loads(c)
        print("keys:", list(d))
        print("must_pass:", {t.split("::")[1][:55]: s for t, s in d["must_pass"].items()})
        print("output_tail present:", "output_tail" in d, "| length:", len(d.get("output_tail", "")))
        print("--- output_tail (what the agent could read about the failure):")
        print(d.get("output_tail", "")[-1500:])
print()
import sys
sys.path.insert(0, ".")
from codetask.agent import feedback_from, system_prompt, task_prompt
from codetask.tools import offered
import harness.llm as hl
from langchain_core.messages import HumanMessage, SystemMessage
contract = json.load(open(run / "contract.json"))
v0 = json.load(open(run / "verdict_0.json"))
prompt = task_prompt(contract, feedback_from(v0))
print("full task prompt of attempt 1: %d chars" % len(prompt))
for word in ("NameError", "Traceback", "read_result"):
    print(f"  contains {word!r}: {word in prompt}   (read_result is in the issue text itself)")
tools = offered(["list_files", "read_file", "write_file", "run_validation", "search_files", "edit_file"])
ev = [json.loads(l) for l in open(run / "events.jsonl")]
first = [e for e in ev if e["event"] == "llm_call" and e["iteration"] == 1 and e["step"] == 0][0]
h = hl.prompt_hash([SystemMessage(system_prompt(tools)), HumanMessage(prompt)], tools)
print("rebuilt prompt hash equals the ledger's (so this is exactly what the agent got):", h == first["prompt_hash"])
i = prompt.find("previous attempt")
print("--- the feedback part of the prompt:")
print(prompt[i:i + 3200])
