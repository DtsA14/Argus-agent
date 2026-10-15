"""Slice 1 of general tasks in a real sandbox: the fixture repository's validation commands run in Docker, read-only,
without a shell, and the verdict follows what actually ran. Needs Docker and a pinned image; without them the tests
are skipped with "SANDBOX NOT AVAILABLE", which scripts/verify.sh does not count as passing."""
import copy
import json
import subprocess
import time
from pathlib import Path

import pytest

from acceptance import validation as va
from acceptance.verdict import evaluate
from acceptance.workspace import prepare, snapshot
from tools import sandbox as sb

ROOT = Path(__file__).resolve().parent.parent
CONTRACT = json.loads((ROOT / "fixtures" / "contracts" / "fix_divide.json").read_text(encoding="utf-8"))
REPO = ROOT / CONTRACT["inputs"]["workspace"]
CFG = {"kind": "docker", "memory": "256m", "cpus": "1", "pids": 64, "max_output_bytes": 65536}
CALC = REPO / "src" / "calc.py"
FIXED = CALC.read_text(encoding="utf-8").replace("    if b == 0:\n        return 0\n", "")
DOC = {"claims": [{"claim": "tests_pass", "evidence": "validation:unit"},
                  {"claim": "issue_fixed", "evidence": "validation:target"},
                  {"claim": "file_changed", "path": "src/calc.py"}],
       "summary": "divide now raises ZeroDivisionError."}


@pytest.fixture(scope="module")
def cfg():
    ok, reason = sb.status(CFG)
    if not ok:
        pytest.skip(f"SANDBOX NOT AVAILABLE: {reason}")
    return dict(CFG)


@pytest.fixture
def ws(tmp_path):
    return tmp_path / "ws", prepare(REPO, tmp_path / "ws")


def statuses(v):
    return {c["id"]: c["status"] for c in v["criteria"]}


def write(root, rel, text):
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


def test_the_fixture_bug_is_real_unit_and_target_fail(cfg, ws):
    root, before = ws
    write(root, "SUMMARY.json", json.dumps(DOC))           # the agent claims success; nothing was fixed
    v = evaluate(CONTRACT, root, before, cfg)
    s = statuses(v)
    assert v["outcome"] == "fail"
    assert s["validation:unit"] == "fail" and s["validation:target"] == "fail"
    unit = next(c for c in v["criteria"] if c["id"] == "validation:unit")
    assert unit["evidence"]["tests_run"] == 7 and unit["evidence"]["failures"] == 1
    assert s["claim[0]:tests_pass"] == "fail" and s["claim[1]:issue_fixed"] == "fail"


def test_a_real_fix_with_honest_claims_passes(cfg, ws):
    assert FIXED != CALC.read_text(encoding="utf-8")
    root, before = ws
    write(root, "src/calc.py", FIXED)
    write(root, "SUMMARY.json", json.dumps(DOC))
    v = evaluate(CONTRACT, root, before, cfg)
    assert v["outcome"] == "pass", [c for c in v["criteria"] if c["status"] != "pass"]
    target = next(c for c in v["criteria"] if c["id"] == "validation:target")
    assert target["evidence"]["must_pass"] == {"tests.test_calc.CalcTest.test_divide_by_zero": "ok"}
    assert target["evidence"]["tests_run"] == 1


def test_making_the_test_pass_by_editing_it_fails(cfg, ws):
    root, before = ws
    test = root / "tests" / "test_calc.py"
    write(root, "tests/test_calc.py", test.read_text().replace("with self.assertRaises(ZeroDivisionError):",
                                                               "if True:"))
    write(root, "SUMMARY.json", json.dumps(DOC))
    v = evaluate(CONTRACT, root, before, cfg)
    s = statuses(v)
    assert s["validation:unit"] == "pass"                  # the edited tests do pass ...
    assert s["scope:protected"] == "fail" and v["outcome"] == "fail"   # ... and that is exactly why it fails


def test_skipping_the_failing_test_fails(cfg, ws):
    root, before = ws
    test = root / "tests" / "test_calc.py"
    write(root, "tests/test_calc.py", test.read_text().replace(
        "    def test_divide_by_zero(self):", "    @unittest.skip('later')\n    def test_divide_by_zero(self):"))
    v = evaluate(CONTRACT, root, before, cfg)
    s = statuses(v)
    unit = next(c for c in v["criteria"] if c["id"] == "validation:unit")
    assert unit["evidence"]["skipped"] == 1 and s["validation:unit"] == "fail"
    assert s["validation:target"] == "fail" and s["scope:protected"] == "fail"


def test_a_command_that_runs_no_tests_fails(cfg, ws):
    root, before = ws
    write(root, "src/calc.py", FIXED)
    spec = {**CONTRACT["validation"][0], "args": ["-m", "unittest", "discover", "-s", "tests", "-t", ".",
                                                   "-p", "nothing_*.py"]}
    v = va.run_validation(spec, root, cfg)
    assert v["status"] == "fail" and v["evidence"]["tests_run"] == 0, v


def test_validation_cannot_write_to_the_workspace(cfg, ws):
    root, before = ws
    write(root, "src/calc.py", FIXED + "\nopen('/workspace/src/planted.txt', 'w').write('x')\n")
    v = va.run_validation(CONTRACT["validation"][0], root, cfg)
    assert v["status"] == "fail" and "Read-only file system" in v["evidence"]["output_tail"]
    assert not (root / "src" / "planted.txt").exists()


def test_a_validation_that_hangs_is_killed_at_its_timeout(cfg, ws):
    root, before = ws
    write(root, "src/calc.py", "while True:\n    pass\n")
    spec = {**CONTRACT["validation"][0], "timeout_s": 3}
    t0 = time.monotonic()
    v = va.run_validation(spec, root, {**cfg, "cleanup_timeout_s": 15})
    took = time.monotonic() - t0
    assert v["status"] == "fail" and "timed out after 3s" in v["reason"], v
    assert v["evidence"]["timed_out"] is True and v["evidence"]["cleanup_failed"] is False
    assert took < 3 + 15 + 5
    left = subprocess.run(["docker", "ps", "-q", "--filter", "label=argus.sandbox=1"],
                          capture_output=True, text=True).stdout.split()
    assert left == []                                       # the container is gone, not just abandoned


def test_validation_runs_without_a_shell(cfg, ws):
    # A value that would mean something to a shell is refused by the allowlist; and run_command only takes an
    # argv list, so even a caller that skipped the allowlist could not reach a shell.
    root, before = ws
    assert va.validate_command("python", ["-m", "unittest", "discover", "-s", "tests;touch x"])
    with pytest.raises(ValueError):
        sb.run_command("python3 -m unittest", workdir=root, cfg=cfg)
    r = sb.run_command(["python3", "-I", "-c", "import sys; print(sys.argv)", "$(touch /workspace/x)"],
                       workdir=root, cfg=cfg)
    assert r["exit_code"] == 0 and "$(touch /workspace/x)" in r["stdout"] and not (root / "x").exists()


def test_the_contract_and_input_repository_are_untouched(cfg, ws):
    root, before = ws
    write(root, "src/calc.py", FIXED)
    evaluate(CONTRACT, root, before, cfg)
    assert snapshot(REPO, skip_cache=True) == before          # the input checkout is never the workspace
