"""Run sympy__sympy-23534's official tests in Argus's sandbox (environment sympy) on a prepared tree."""
import json, os, sys
sys.path.insert(0, os.path.expanduser("~/Argus-agent"))
from runner import load_config
from acceptance.validation import run_validation
cfg = {**(load_config().get("sandbox") or {}), "kind": "docker"}
cfg["environments"] = {**(cfg.get("environments") or {}), "sympy": {"image": None}}
os.environ["ARGUS_SANDBOX_IMAGE"] = open(os.path.expanduser("~/Argus-agent/.sandbox_image")).read().strip()
os.environ["ARGUS_SANDBOX_IMAGE_SYMPY"] = open(os.path.expanduser("~/Argus-agent/.sandbox_image_sympy")).read().strip()
f = "sympy/core/tests/test_symbol.py"
f2p = [f"{f}::test_symbols"]
p2p = [f"{f}::{t}" for t in ["test_Str", "test_Symbol", "test_Dummy", "test_Dummy_force_dummy_index", "test_lt_gt",
       "test_no_len", "test_ineq_unequal", "test_Wild_properties", "test_symbols_become_functions_issue_3539",
       "test_unicode", "test_uniquely_named_symbol_and_Symbol"]]
spec = {"id": "official", "executable": "python", "args": ["-m", "pytest", f], "timeout_s": 300, "min_tests": 1,
        "max_skipped": 0, "must_pass": f2p + p2p, "environment": "sympy"}
r = run_validation(spec, sys.argv[1], cfg)
ev = r["evidence"]
print(r["status"], r["reason"][:300])
print({k: ev.get(k) for k in ("tests_run", "failures", "errors", "skipped", "exit_code", "timed_out")})
print({k.split("::")[1]: v for k, v in (ev.get("must_pass") or {}).items() if v != "ok"} or "all must_pass ok")
