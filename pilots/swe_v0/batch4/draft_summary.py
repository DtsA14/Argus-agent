"""Batch 3 draft summary from the draft alone (no maintainers' patch, no official tests): writable, validations, the
"Why they fail now" block, changed tests and the drafted test files. Usage: draft_summary.py <job id>"""
import json, re, sys
from pathlib import Path
job = sys.argv[1]
J = Path.home() / "pilot3a_live" / "jobs" / job
d = sorted((J / "runs").glob(f"{job}-d*"))[-1]
draft = json.loads((d / "draft.json").read_text())
rev = (d / "DRAFT_REVIEW.md").read_text()
c = draft["contract"]
print("stage:", d.name)
print("writable:", c["scope"]["writable"])
for v in c["validation"]:
    print("validation", v["id"], v.get("environment"), " ".join(v["args"]), "| required:", v.get("must_pass"))
m = re.search(r"Why they fail now.*?```text\n(.*?)```", rev, re.S)
print("---- WHY\n" + (m.group(1) if m else "(not found)") + "----")
print("changed_tests:", [t["path"] for t in draft.get("changed_tests") or []])
x = re.search(r"## Existing tests changed(.*?)## Not verified", rev, re.S)
if x:
    print(x.group(1)[:3000])
for t in draft["new_tests"]:
    print(f"==== {t['path']}\n{t['content']}")
print([l for l in rev.splitlines() if l.startswith("Drafter:")])
