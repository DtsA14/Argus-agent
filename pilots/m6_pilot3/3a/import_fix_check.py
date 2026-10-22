"""Run the contract's validations, in the Argus sandbox, on the workspaces the agent left (pilot3a, pilot3a2), as they are and with
one import line added to scripts/audit_run.py. The agent-written code runs only inside the sandbox."""
import json
import re
import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, ".")
sys.path.insert(0, "scripts")
from approve_draft import sandbox_cfg  # noqa: E402
from acceptance.validation import run_validation  # noqa: E402

contract = json.load(open("fixtures/contracts/fix_run_inspectors.json"))
cfg = sandbox_cfg()
ANCHOR = "from runner import load_config\n"
LINE = "from evals.runlog import read_events, read_memo, read_result\n"   # the line PR #122 added
for run in ("pilot3a", "pilot3a2"):
    for variant in ("as left", "with the import"):
        tmp = Path(tempfile.mkdtemp()) / "ws"
        shutil.copytree(Path("runs") / run / "workspace", tmp)
        a = tmp / "scripts" / "audit_run.py"
        if variant == "with the import":
            txt = a.read_text()
            assert txt.count(ANCHOR) == 1
            a.write_text(txt.replace(ANCHOR, ANCHOR + LINE))
        for spec in contract["validation"]:
            r = run_validation(spec, tmp, cfg)
            ev = r.get("evidence") or {}
            must = {k.split("::")[-1][:48]: v for k, v in (ev.get("must_pass") or {}).items()}
            bad = [k for k, v in must.items() if v != "ok"]
            print(f"{run:9} {variant:16} {spec['id']:10} {r['status']:5} tests {ev.get('tests_run')} failures {ev.get('failures')} "
                  f"errors {ev.get('errors')} | required not ok ({len(bad)}): {bad}")
            if spec["id"] == "inspectors" and variant == "with the import":
                print("          exceptions named in the tail:", sorted(set(re.findall(r"\b(\w+Error|StopIteration)\b", ev.get("output_tail", "")))))
        shutil.rmtree(tmp.parent, ignore_errors=True)
