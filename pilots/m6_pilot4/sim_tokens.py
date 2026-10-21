"""Token simulation for M6 pilot 4 (no model, no cost): scripted trajectories through the real harness loop, the real tools and the
calibrated token counter (scripts/measure_context.py). Run from a checkout of the base commit with the new test file in tests/:
  P3_TESTFILE=... PYTHONPATH=. python sim_tokens.py <runs_dir> <plan> [attempt_tokens ...]"""
import json
import os
import shutil
import sys
from pathlib import Path

ROOT = Path(os.getcwd()).resolve()
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
import measure_context as mc  # noqa: E402

os.environ["ARGUS_SANDBOX_IMAGE_ARGUS"] = Path(".sandbox_image_argus").read_text().strip()
os.environ["ARGUS_SANDBOX_IMAGE"] = Path(".sandbox_image").read_text().strip()
runs_dir, plan_name = Path(sys.argv[1]), sys.argv[2]
sizes = [int(x) for x in sys.argv[3:]] or [30000]

SIM = ROOT / "fixtures" / "repos" / "p4sim"
shutil.rmtree(SIM, ignore_errors=True)
shutil.copytree(ROOT, SIM, ignore=shutil.ignore_patterns("verification", "pilots", ".git", "__pycache__", ".sandbox_image*", ".venv*",
                                                          "runs", "exports", "p4sim", "repos"))
(SIM / "fixtures" / "repos").mkdir(parents=True, exist_ok=True)
shutil.copy(os.environ["P3_TESTFILE"], SIM / "tests" / "test_peak_window.py")
contract = {"contract": "p4sim", "version": 1,
            "inputs": {"workspace": "fixtures/repos/p4sim", "issue": Path(os.environ["P4_ISSUE"]).read_text(encoding="utf-8").strip()},
            "scope": {"writable": ["models/pricing.py"], "protected": ["tests/**", "conftest.py", "config.yaml", "harness/**"]},
            "artifacts": [{"path": "SUMMARY.json", "type": "json", "schema": "claims_v2"}],
            "validation": [{"id": "target", "executable": "python", "args": ["-m", "pytest", "tests/test_peak_window.py"], "timeout_s": 240,
                            "min_tests": 1, "max_skipped": 0, "must_pass": ["tests/test_peak_window.py::test_x"], "environment": "argus"}],
            "judge": [], "limits": {"max_usd": 0.5, "max_iterations": 3}, "tools": ["search_files", "edit_file"]}

rd = lambda *fs: [("ReadFile", {"path": f}) for f in fs]  # noqa: E731
OLD = '    return any(start <= now.hour < end for start, end in window["utc_hours"])'
NEW = ('    return any(start <= now.hour < end if start <= end else (now.hour >= start or now.hour < end)\n'
        '               for start, end in window["utc_hours"])')
EDIT = ("EditFile", {"path": "models/pricing.py", "old_text": OLD, "new_text": NEW})
BAD = ("EditFile", {"path": "models/pricing.py", "old_text": OLD, "new_text": OLD.replace("<", "<=")})
V = [("RunValidation", {"id": "target"})]
FIN = [("Finish", {"claims": [{"claim": "file_changed", "path": "models/pricing.py"}, {"claim": "issue_fixed", "evidence": "validation:target"}],
                   "summary": "is_peak handles windows across midnight"})]
PEAK_USERS = ["harness/llm.py", "tests/test_models.py", "tests/test_llm_wrapper.py", "tests/test_calibration.py", "tests/test_judge.py",
              "scripts/calibrate_judge.py"]
PLANS = {
    "search_first": [[("SearchFiles", {"text": "def is_peak"})], [EDIT], V, FIN],
    "minimal": [rd("models/pricing.py", "tests/test_peak_window.py"), [EDIT], V, FIN],
    "typical": [[("ListFiles", {})], rd("models/pricing.py", "tests/test_peak_window.py", "tests/test_models.py"), [EDIT], V, FIN],
    "minimal_one_fix": [rd("models/pricing.py", "tests/test_peak_window.py"), [BAD], V, [EDIT], V, FIN],
    # the agent follows every user of is_peak and reads every test that mentions it, one file per step
    "read_all": [[("SearchFiles", {"text": "is_peak"})], rd("models/pricing.py", "tests/test_peak_window.py")] +
                [rd(f) for f in PEAK_USERS] + [[EDIT], V, FIN],
    # the same, but several reads per step (cheaper in steps, the same in context)
    "read_all_batched": [[("SearchFiles", {"text": "is_peak"})], rd("models/pricing.py", "tests/test_peak_window.py", *PEAK_USERS),
                         [EDIT], V, FIN],
}
for tokens in sizes:
    out = runs_dir / f"t{tokens}"
    shutil.rmtree(out, ignore_errors=True)
    r = mc.full_run(contract, PLANS[plan_name], f"p4_{plan_name}_{tokens}", out, attempt_tokens=tokens)
    evs = [json.loads(l) for l in (out / f"p4_{plan_name}_{tokens}" / "events.jsonl").read_text().splitlines()]
    steps = [(e["step"], e["status"], e.get("input_tokens") or e.get("est_input"), e.get("output_tokens"))
             for e in evs if e["event"] == "llm_call" and e.get("iteration") == 0]
    print(json.dumps({k: r[k] for k in ("status", "attempts", "attempt_ends", "tokens_per_attempt", "usd_estimate")}), plan_name, tokens)
    print("   attempt 0 steps:", steps)
shutil.rmtree(SIM, ignore_errors=True)
