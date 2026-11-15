"""VF probe A10 (docs/reviews/SPEC_VF_CANARY.md), closed by VF O1 (docs/reviews/SPEC_VF_O1_CANARY_NONCE.md): a forger inside the code under test.
The fixture's source module writes a consistent pytest report to the real stdout pipe while pytest imports it, then exits 0 before any
test runs; its one test is honestly red. Before O1 the validation reported it as PASS (probe run 2026-11-12); now there is no harness
record behind the run's nonce, so it fails. The forgers O1 does not stop (F1 to F3) are the known-gap tests in tests/test_vf_canary.py.
Needs Docker and the `argus` image, like tests/test_pytest_sandbox.py (skipped without them: SANDBOX NOT AVAILABLE)."""
import shutil
from pathlib import Path

import pytest

from acceptance import validation as va
from runner import load_config
from tools import sandbox as sb

ROOT = Path(__file__).resolve().parent.parent
FORGER = ROOT / "fixtures" / "forgers" / "pytest_pipe_forger"
NODE = "tests/test_new.py::test_new"


@pytest.fixture(scope="module")
def cfg():
    c = {**(load_config().get("sandbox") or {}), "kind": "docker", "memory": "512m"}
    ok, reason = sb.status({**c, "environment": "argus"})
    if not ok:
        pytest.skip(f"SANDBOX NOT AVAILABLE: {reason}")
    return c


def run(cfg, tmp_path, fixture="pytest_pipe_forger"):
    ws = tmp_path / "ws"
    shutil.copytree(ROOT / "fixtures" / "forgers" / fixture, ws)
    spec = {"id": "unit", "executable": "python", "args": ["-m", "pytest", "tests/test_new.py"], "timeout_s": 120,
            "min_tests": 1, "max_skipped": 0, "must_pass": [NODE], "environment": "argus"}
    return va.run_validation(spec, str(ws), cfg)


def test_the_fixture_is_a_real_forger_its_test_is_red_when_run_honestly(tmp_path):
    """Without the forging import the same test fails: the fixture is a forgery, not a green project."""
    ws = tmp_path / "ws"
    shutil.copytree(FORGER, ws)
    text = (ws / "src" / "app.py").read_text()
    assert "os._exit(0)" in text and "return 2" in text and "assert f() == 1" in (ws / "tests" / "test_new.py").read_text()


def test_a_forged_report_from_inside_the_code_under_test_does_not_pass_the_validation(cfg, tmp_path):
    """VF O1 (SPEC_VF_O1_CANARY_NONCE): the forged text is read, but there is no harness record behind the run's nonce."""
    v = run(cfg, tmp_path)
    assert v["status"] == "fail" and v["evidence"]["record"] is False and "validation not trusted" in v["reason"], v["evidence"]


def test_a_forger_that_turns_every_test_into_a_no_op_fails_the_canary(cfg, tmp_path):
    v = run(cfg, tmp_path, "pytest_noop_forger")
    assert v["status"] == "fail" and v["evidence"]["record"] is True and v["evidence"]["canary"] != "ok", v["evidence"]


def test_an_honest_red_project_is_trusted_and_fails_only_for_its_own_test(cfg, tmp_path):
    ws = tmp_path / "ws"
    shutil.copytree(FORGER, ws)
    (ws / "src" / "app.py").write_text("def f():\n    return 2\n")
    spec = {"id": "unit", "executable": "python", "args": ["-m", "pytest", "tests/test_new.py"], "timeout_s": 120, "min_tests": 1,
            "max_skipped": 0, "must_pass": [NODE], "environment": "argus"}
    v = va.run_validation(spec, str(ws), cfg)
    assert v["status"] == "fail" and v["evidence"]["record"] is True and v["evidence"]["canary"] == "ok"
    assert "not trusted" not in v["reason"] and v["evidence"]["failed_nodes"] == [NODE], v["evidence"]
