"""Token simulation for M6 pilot 5 (no model, no cost): scripted trajectories through the real harness loop, the real tools and the
calibrated token counter (scripts/measure_context.py). Run from a checkout of the base commit with the new test file in tests/:
  P3_TESTFILE=... P4_ISSUE=... P5_REF=<pricing.py with the reference patch applied> PYTHONPATH=. python sim_tokens.py <runs_dir> <plan> [attempt_tokens ...]"""
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

SIM = ROOT / "fixtures" / "repos" / "p5sim"
shutil.rmtree(SIM, ignore_errors=True)
shutil.copytree(ROOT, SIM, ignore=shutil.ignore_patterns("verification", "pilots", ".git", "__pycache__", ".sandbox_image*", ".venv*",
                                                          "runs", "exports", "p5sim", "repos"))
(SIM / "fixtures" / "repos").mkdir(parents=True, exist_ok=True)
shutil.copy(os.environ["P3_TESTFILE"], SIM / "tests" / "test_peak_window_strict.py")
contract = {"contract": "p5sim", "version": 1,
            "inputs": {"workspace": "fixtures/repos/p5sim", "issue": Path(os.environ["P4_ISSUE"]).read_text(encoding="utf-8").strip()},
            "scope": {"writable": ["models/pricing.py"], "protected": ["tests/**", "conftest.py", "config.yaml", "harness/**"]},
            "artifacts": [{"path": "SUMMARY.json", "type": "json", "schema": "claims_v2"}],
            "validation": [{"id": "target", "executable": "python", "args": ["-m", "pytest", "tests/test_peak_window_strict.py"],
                            "timeout_s": 240, "min_tests": 1, "max_skipped": 0,
                            "must_pass": ["tests/test_peak_window_strict.py::test_x"], "environment": "argus"}],
            "judge": [], "limits": {"max_usd": 0.5, "max_iterations": 3}, "tools": ["search_files", "edit_file"]}

base = (ROOT / "models" / "pricing.py").read_text(encoding="utf-8").replace("\r\n", "\n")
ref = Path(os.environ["P5_REF"]).read_text(encoding="utf-8").replace("\r\n", "\n")
OLD = base[base.index("def is_peak"):base.index("def multiplier")].rstrip("\n")
NEW = ref[ref.index("class WindowError"):ref.index("def multiplier")].rstrip("\n")
BAD_NEW = NEW.replace("    _checked(window)\n", "")

rd = lambda *fs: [("ReadFile", {"path": f}) for f in fs]  # noqa: E731
EDIT = ("EditFile", {"path": "models/pricing.py", "old_text": OLD, "new_text": NEW})
BAD = ("EditFile", {"path": "models/pricing.py", "old_text": OLD, "new_text": BAD_NEW})
FIX = ("EditFile", {"path": "models/pricing.py", "old_text": BAD_NEW, "new_text": NEW})
V = [("RunValidation", {"id": "target"})]
FIN = [("Finish", {"claims": [{"claim": "file_changed", "path": "models/pricing.py"}, {"claim": "issue_fixed", "evidence": "validation:target"}],
                   "summary": "is_peak refuses windows and times it cannot read safely"})]
PEAK_USERS = ["harness/llm.py", "tests/test_models.py", "tests/test_llm_wrapper.py", "tests/test_calibration.py", "tests/test_judge.py",
              "scripts/calibrate_judge.py"]
PLANS = {
    "search_first": [[("SearchFiles", {"text": "def is_peak"})], rd("models/pricing.py"), [EDIT], V, FIN],
    "minimal": [rd("models/pricing.py", "tests/test_peak_window_strict.py"), [EDIT], V, FIN],
    "typical": [[("ListFiles", {})], rd("models/pricing.py", "tests/test_peak_window_strict.py", "tests/test_peak_window.py"), [EDIT], V, FIN],
    "typical_plus_models": [[("ListFiles", {})], rd("models/pricing.py", "tests/test_peak_window_strict.py", "tests/test_peak_window.py", "tests/test_models.py"),
                            [EDIT], V, FIN],
    "minimal_one_fix": [rd("models/pricing.py", "tests/test_peak_window_strict.py"), [BAD], V, [FIX], V, FIN],
    "read_all": [[("SearchFiles", {"text": "is_peak"})], rd("models/pricing.py", "tests/test_peak_window_strict.py", "tests/test_peak_window.py")] +
                [rd(f) for f in PEAK_USERS] + [[EDIT], V, FIN],
    "read_all_batched": [[("SearchFiles", {"text": "is_peak"})],
                         rd("models/pricing.py", "tests/test_peak_window_strict.py", "tests/test_peak_window.py", *PEAK_USERS), [EDIT], V, FIN],
}
for tokens in sizes:
    out = runs_dir / f"t{tokens}"
    shutil.rmtree(out, ignore_errors=True)
    r = mc.full_run(contract, PLANS[plan_name], f"p5_{plan_name}_{tokens}", out, attempt_tokens=tokens)
    evs = [json.loads(line) for line in (out / f"p5_{plan_name}_{tokens}" / "events.jsonl").read_text().splitlines()]
    steps = [(e["step"], e["status"], e.get("input_tokens") or e.get("est_input"), e.get("output_tokens"))
             for e in evs if e["event"] == "llm_call" and e.get("iteration") == 0]
    print(json.dumps({k: r[k] for k in ("status", "attempts", "attempt_ends", "tokens_per_attempt", "usd_estimate")}), plan_name, tokens)
    print("   attempt 0 steps:", steps)
shutil.rmtree(SIM, ignore_errors=True)
