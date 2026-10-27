"""SPEC_DRAFTER_SKIPPED_STEPS (from the 21379 re-run, attempt 2): a "tests skipped" reason names the nodes, and the
drafter has 24 steps."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_pytest_validation as tpv  # noqa: E402

from acceptance import validation as va  # noqa: E402
from runner import load_config  # noqa: E402

NOT_RUN = ["tests/test_demo.py::test_skipped", "tests/test_demo.py::test_xfail", "tests/test_demo.py::test_xpass"]


def test_a_skipped_reason_names_the_skipped_xfail_and_xpass_nodes():
    v = va.judge_result(tpv.spec("tests/test_demo.py"), tpv.result("all"))     # a real run: 1 skipped, 1 xfail, 1 xpass
    assert v["status"] == "fail" and v["evidence"]["skipped_nodes"] == NOT_RUN
    assert "3 tests skipped, contract allows 0: " + ", ".join(NOT_RUN) in v["reason"]


def test_more_than_ten_skipped_nodes_are_counted_not_listed():
    lines = [f"tests/t.py::test_{k:02d} SKIPPED (x)" for k in range(12)]
    out = ("collecting ... collected 12 items\n" + "\n".join(lines) + "\n==== 12 skipped in 0.01s ====\n")
    r = {"exit_code": 0, "stdout": out, "stderr": "", "timed_out": False, "killed": False,
         "output_limit_exceeded": False, "truncated": False}
    v = va.judge_result(tpv.spec("tests/t.py"), r)
    assert "12 tests skipped, contract allows 0: tests/t.py::test_00" in v["reason"]
    assert "tests/t.py::test_09 and 2 more" in v["reason"] and "test_10" not in v["reason"]
    assert len(v["evidence"]["skipped_nodes"]) == 12


def test_no_skip_no_names():
    v = va.judge_result(tpv.spec("tests/test_demo.py", max_skipped=3), tpv.result("all"))
    assert "skipped" not in v["reason"] and v["evidence"]["skipped_nodes"] == NOT_RUN


def test_the_drafter_has_24_steps():
    from codetask import drafter as dt
    c = load_config()
    assert c["drafter"]["max_steps"] == 24 and dt.drafter_settings(c)["max_steps"] == 24
