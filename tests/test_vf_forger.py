"""VF probe A10 (docs/reviews/SPEC_VF_CANARY.md): a forger inside the code under test. The fixture's source module writes a consistent pytest
report to the real stdout pipe while pytest imports it, then exits 0 before any test runs; its one test is honestly red. Today the
validation reports it as PASS (probe run 2026-11-12, `ledger_py312_up2` image, `argus` environment here), so the guarantee "a validation
pass means the tests passed" is broken for any code that deliberately forges. The test states the guarantee and is marked
xfail(strict): it fails today, and when a fix makes the forger fail acceptance it XPASSes, which strict turns into a failure that
forces this marker to be removed. Needs Docker and the `argus` image, like tests/test_pytest_sandbox.py (skipped without them)."""
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


def run(cfg, tmp_path):
    ws = tmp_path / "ws"
    shutil.copytree(FORGER, ws)
    spec = {"id": "unit", "executable": "python", "args": ["-m", "pytest", "tests/test_new.py"], "timeout_s": 120,
            "min_tests": 1, "max_skipped": 0, "must_pass": [NODE], "environment": "argus"}
    return va.run_validation(spec, str(ws), cfg)


def test_the_fixture_is_a_real_forger_its_test_is_red_when_run_honestly(tmp_path):
    """Without the forging import the same test fails: the fixture is a forgery, not a green project."""
    ws = tmp_path / "ws"
    shutil.copytree(FORGER, ws)
    text = (ws / "src" / "app.py").read_text()
    assert "os._exit(0)" in text and "return 2" in text and "assert f() == 1" in (ws / "tests" / "test_new.py").read_text()


@pytest.mark.xfail(strict=True, reason="VF/D5: a forger in the code under test makes the validation PASS (probe A10, confirmed 2026-11-12)")
def test_a_forged_report_from_inside_the_code_under_test_does_not_pass_the_validation(cfg, tmp_path):
    v = run(cfg, tmp_path)
    assert v["status"] != "pass", v["evidence"]
