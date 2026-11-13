"""SPEC_APPEND_TESTS end to end, in the sandbox (the unit tests are in test_append_tests.py): a draft that only appends a test to an
existing file goes through dr.check and approve, and K1 refuses a required node the real collection already has. This is a sandbox
module in conftest.py's sense (it skips with SANDBOX NOT AVAILABLE), so it runs in the serial sandbox group of verify.sh: a test of
test_acceptance_sandbox.py asserts that no sandbox container is left on the machine, and one running beside it breaks that."""
import copy
import hashlib
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_draft as tdr  # noqa: E402
from acceptance import draft as dr  # noqa: E402
from acceptance import intake  # noqa: E402
from runner import load_config  # noqa: E402
from tools import sandbox as sb  # noqa: E402
from test_draft import root  # noqa: E402,F401  (fixture)


@pytest.fixture(scope="module")
def scfg():
    c = {**(load_config().get("sandbox") or {}), "kind": "docker"}
    ok, why = sb.status({**c, "environment": "argus"})
    if not ok:
        pytest.skip(f"SANDBOX NOT AVAILABLE: {why}")
    return c


FLOOR = "from src.shop import total\n\n\ndef test_total_floor():\n    assert total([1], 5) == 0\n"
FLOOR_NODE = "tests/test_old.py::test_total_floor"
FLOOR_FILE = tdr.OLD_TEST.rstrip("\n") + "\n\n\n" + FLOOR.strip("\n") + "\n"


def appended_draft(must=(FLOOR_NODE,)):
    d = copy.deepcopy(tdr.DRAFT)
    d["new_tests"] = []
    d["contract"]["validation"] = [tdr.spec("target", "tests/test_old.py", list(must))]
    d["changed_tests"] = [{"path": "tests/test_old.py", "content": FLOOR_FILE}]
    return d


@pytest.fixture(scope="module")
def appended_report(tmp_path_factory, scfg):
    tmp = tmp_path_factory.mktemp("appended")
    return tdr.run_check(tdr.make_root(tmp), tdr.patch(tmp, {"src/shop.py": tdr.FIXED}), scfg, draft=appended_draft())


def test_a_draft_that_only_appends_a_test_to_an_existing_file_is_checked_and_approved(root, appended_report):
    r = copy.deepcopy(appended_report)
    assert r["ok"], r["problems"]
    assert r["baseline"]["target"]["must_pass"] == {FLOOR_NODE: "FAIL"}                  # red by assertion, as any new test
    assert r["collection"]["tests/test_old.py"] == {"intake": 1, "new": 2, "gone": []}   # K1 on the real collection
    assert r["reference"]["target"] == "pass"
    rec = dr.approve(r, appended_draft(), root=root)
    task = root / "fixtures" / "repos" / "fix_shop"
    assert (task / "tests" / "test_old.py").read_text() == FLOOR_FILE and intake.check(rec, task) == []
    assert rec["changed"]["tests/test_old.py"]["after"] == hashlib.sha256(FLOOR_FILE.encode()).hexdigest()
    assert rec["added"] == {}


def test_a_required_test_the_intake_already_has_is_refused_by_k1_in_the_real_collection(root, tmp_path, scfg):
    d = appended_draft(must=("tests/test_old.py::test_total_plain",))
    d["new_tests"] = [{"path": "tests/test_new.py", "content": tdr.NEW_TEST}]         # so that only K1 can refuse it
    d["contract"]["validation"].append(tdr.spec("new", "tests/test_new.py", [tdr.NEW_NODE]))
    r = tdr.run_check(root, tdr.patch(tmp_path, {"src/shop.py": tdr.FIXED}), scfg, draft=d)
    assert not r["ok"] and any("already a test of tests/test_old.py" in p for p in r["problems"]), r["problems"]
