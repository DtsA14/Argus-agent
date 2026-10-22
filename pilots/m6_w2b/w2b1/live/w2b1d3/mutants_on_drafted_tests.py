"""The 20 mutants of the 3b reference (pilots/m6_pilot3/3b/mutants_3b.py) against the tests the drafter wrote in
w2b1d3, run in the sandbox (the tests are model-written). Usage: python m3b_drafted.py <copy of the repo> <list file>"""
import json, sys
from pathlib import Path
WT, LIST = Path(sys.argv[1]), sys.argv[2]
sys.path.insert(0, str(WT))
from runner import load_config
from acceptance.validation import run_validation
ns = {}
exec(open(LIST).read(), ns)
M = ns["M"]
F = WT / "scripts" / "pilot_report.py"
original = F.read_text(encoding="utf-8")
cfg = {**(load_config(str(WT / "config.yaml")).get("sandbox") or {}), "kind": "docker"}
spec = {"id": "x", "executable": "python", "args": ["-m", "pytest", "tests/test_pilot_report_drafted.py"], "timeout_s": 300,
        "min_tests": 1, "max_skipped": 0, "environment": "argus"}
v = run_validation(spec, str(WT), cfg)
print("reference:", v["status"], v["evidence"].get("tests_run"), flush=True)
killed = 0
for m in M:
    name, old, new = m[:3]
    count = m[3] if len(m) > 3 else 1
    assert original.count(old) == count, (name, original.count(old))
    F.write_text(original.replace(old, new), encoding="utf-8")
    v = run_validation(spec, str(WT), cfg)
    k = v["status"] != "pass"
    killed += k
    print(f"{'KILLED ' if k else 'SURVIVED'} {name}: {(v['evidence'].get('failed_nodes') or [])[:2]}", flush=True)
F.write_text(original, encoding="utf-8")
print(f"RESULT: {killed}/{len(M)} killed")
