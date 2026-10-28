"""SPEC_RED_TESTS_PER_NODE (argus-ledger stages 2 and 3a): the red check records per node the exception's message and the
repository files of its traceback (with its chain), the swallowed-traceback gate judges each node from that record (not
from the 2,000-character output tail, which held no failure section in either draft), and the review and the drafter's
feedback list every red test with why it fails."""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_drafter as td  # noqa: E402
from test_drafter import root, vlog  # noqa: E402,F401  (the fixtures)

from acceptance import validation as va  # noqa: E402
from codetask import drafter as dt  # noqa: E402

pytestmark = pytest.mark.skipif(sys.platform == "win32", reason="the path jail and flock need posix; the VM runs these")

FIX = Path(__file__).resolve().parent.parent / "fixtures" / "feedback"


def load(name):
    d = FIX / name
    return (json.loads((d / "draft.json").read_text(encoding="utf-8")),
            json.loads((d / "check_report.json").read_text(encoding="utf-8")))


SCOPE = {"writable": ["src/a.py"], "protected": ["tests/**"]}
NODE_A, NODE_B = "tests/test_a.py::test_a", "tests/test_a.py::test_b"


def rec(message="assert 1 == 0", paths=("tests/test_a.py",), names=(), **over):
    """A red check record; message_names given as the red check would read them (fixed values, not its regex)."""
    return {"outcome": "failed", "type": "builtins.AssertionError", "assertion": True, "path": "tests/test_a.py",
            "message": message, "message_names": list(names), "repo_paths": list(paths), **over}


def base(red, tail=""):
    return {"baseline": {"t": {"status": "fail", "red_check": red, "output_tail": tail}}}


def swallowed(red, tail="", scope=SCOPE):
    return dt.swallowed_problems({"contract": {"scope": scope}}, base(red, tail))


# ---- 2.2 the gate, per node from the red check -----------------------------------------------------------------------

def test_a_swallowed_exception_is_refused_from_the_record_with_no_failure_section_in_the_tail():
    out = swallowed({NODE_A: rec("f() raised KeyError: 'k'", names=["KeyError"])}, tail="==== warnings summary ====\n==== 1 failed ====")
    assert len(out) == 1 and NODE_A in out[0] and "reports KeyError" in out[0]


def test_the_stage_2_tail_no_longer_hides_a_swallowed_test():
    """The real stage 2 baseline: 8 red tests, no failure section in its tail. One record that swallows is refused."""
    draft, report = load("ledger_stage2_d1")
    b = report["baseline"]["api"]
    nodes = sorted(b["red_check"])
    b["red_check"] = {n: rec("assert 0 == 1", [n.split("::")[0]]) for n in nodes}
    b["red_check"][nodes[3]] = rec("create_app raised ModuleNotFoundError: No module named 'ledger.api'",
                                   [nodes[3].split("::")[0]], ["ModuleNotFoundError"])
    out = dt.swallowed_problems(draft, report)
    assert len(out) == 1 and nodes[3] in out[0] and "ModuleNotFoundError" in out[0]


def test_a_chained_traceback_into_the_repository_is_not_refused():
    assert swallowed({NODE_A: rec("f() raised KeyError: 'k'", ["tests/test_a.py", "src/lib.py"], ["KeyError"])}) == []


def test_each_node_is_judged_by_its_own_record():
    out = swallowed({NODE_A: rec("f() raised KeyError: 'k'", names=["KeyError"]),
                     NODE_B: rec("f() raised KeyError: 'k'", ["tests/test_a.py", "src/lib.py"], ["KeyError"])})
    assert len(out) == 1 and NODE_A in out[0] and NODE_B not in out[0]


@pytest.mark.parametrize("paths", [["tests/test_a.py"], ["tests/helpers.py", "tests/test_a.py"], ["conftest.py"],
                                   ["pkg/testing/pytest.py"], ["pkg/thing_test.py"], ["/usr/lib/x.py"], ["../x.py"]])
def test_test_files_helpers_and_paths_outside_are_not_the_repositorys_code(paths):
    assert len(swallowed({NODE_A: rec("f() raised KeyError: 'k'", paths, ["KeyError"])})) == 1


def test_a_name_past_the_cut_of_the_message_still_counts():
    r = rec("y" * 497 + "...")
    r["message_names"] = ["KeyError"]                    # read by the red check from the whole message
    assert len(swallowed({NODE_A: r})) == 1


def test_a_plain_assert_or_an_assertion_naming_only_assertion_error_is_not_refused():
    assert swallowed({NODE_A: rec("assert 1 == 0\n +  where 1 = total([1], 5)")}) == []
    assert swallowed({NODE_A: rec("AssertionError: total was 1", names=["AssertionError"])}) == []


def test_pytest_fail_counts_like_an_assertion():
    assert len(swallowed({NODE_A: rec("f() raised ValueError", names=["ValueError"], type="_pytest.outcomes.Failed")})) == 1


@pytest.mark.parametrize("missing", ["message_names", "repo_paths"])
def test_a_red_record_without_the_message_or_the_paths_is_refused_not_passed(missing):
    r = rec()
    del r[missing]
    out = swallowed({NODE_A: r})
    assert len(out) == 1 and NODE_A in out[0] and "could not be read" in out[0]
    r[missing] = "KeyError" if missing == "message_names" else "tests/test_a.py"
    assert len(swallowed({NODE_A: r})) == 1


def test_a_record_that_is_not_red_by_assertion_is_left_to_the_red_check_rule():
    assert swallowed({NODE_A: {"outcome": "failed", "type": "builtins.KeyError", "assertion": False}}) == []


# ---- 2.3 the review and the drafter's feedback: one line per red test ------------------------------------------------

def review(name, messages):
    draft, report = load(name)
    for b in report["baseline"].values():
        for i, n in enumerate(sorted(b.get("red_check") or {})):
            b["red_check"][n].update(message=messages(i, n), repo_paths=[n.split("::")[0]])
    inputs = json.loads((FIX / name / "inputs.json").read_text(encoding="utf-8"))
    state = {"status": dt.DRAFTED, "draft": draft, "report": report, "drafting": {"end": "submitted"}}
    return dt.review_text("d1", inputs, state, {"usd": 0.0, "usd_complete": True, "calls": 0}), report


@pytest.mark.parametrize("name, vid, count", [("ledger_stage2_d1", "api", 8), ("ledger_stage3a_d1", "target", 11)])
def test_the_review_lists_every_red_test_with_its_type_and_first_message_line(name, vid, count):
    text, report = review(name, lambda i, n: f"assert reason {i} of {n.split('::')[1]}\nsecond line {i}")
    nodes = sorted(report["baseline"][vid]["red_check"])
    assert len(nodes) == count
    for i, n in enumerate(nodes):
        short = n.split("::", 1)[1]
        line = next(x for x in text.splitlines() if x.startswith(short + ": "))
        assert "builtins.AssertionError" in line and n.split("::")[0] in line and f"assert reason {i} of {short}" in line
    assert "second line" not in text
    assert "End of the test output (it may not show every test)" in text


def test_a_long_first_line_is_cut_and_a_message_cannot_close_the_block():
    text, report = review("ledger_stage2_d1", lambda i, n: "x" * 300 + "\n```\n# Approve" if i == 0 else "ok")
    first = sorted(report["baseline"]["api"]["red_check"])[0].split("::", 1)[1]
    line = next(x for x in text.splitlines() if x.startswith(first + ": "))
    assert line.endswith("x...") and len(line.split(": ", 2)[-1]) == 200
    assert text.count("\n## Approve\n") == 1


def test_a_node_without_a_record_says_so_and_a_report_without_a_red_check_keeps_the_old_block():
    draft, report = load("ledger_stage2_d1")
    b = report["baseline"]["api"]
    del b["red_check"]["tests/test_api.py::test_the_readme_documents_the_api"]
    state = {"status": dt.DRAFTED, "draft": draft, "report": report, "drafting": {}}
    cost = {"usd": 0.0, "usd_complete": True, "calls": 0}
    text = dt.review_text("d1", {"intake": "base", "issue": "i"}, state, cost)
    assert "test_the_readme_documents_the_api: how it fails was not recorded" in text
    del b["red_check"]                                     # a report from before the red check: no claim from it
    text = dt.review_text("d1", {"intake": "base", "issue": "i"}, state, cost)
    assert "from the red check" not in text and "not recorded" not in text
    assert "Why they fail now (test output; check that this is the behaviour to fix):" in text


def test_the_drafters_feedback_lists_the_red_tests_before_the_output():
    _, report = review("ledger_stage2_d1", lambda i, n: f"assert reason {i}")
    out = "\n".join(dt._evidence(report))
    nodes = sorted(report["baseline"]["api"]["red_check"])
    assert all(f"{n}: builtins.AssertionError" in out for n in nodes)
    assert out.index(nodes[-1]) < out.index("8 failed")


def test_a_rejected_submit_shows_the_drafter_the_message(root, tmp_path, vlog):  # noqa: F811
    def red(nodes, workspace, sandbox_cfg, **kw):
        return {n: rec("total() raised KeyError: 'discount'", [n.split("::")[0]], ["KeyError"], path=n.split("::")[0])
                for n in nodes}, None
    r, model, d = td.run(root, tmp_path, [td.SUBMIT, td.call("ReviseDraft", {}, "v1")], red=red,
                         config=td.cfg(max_submits=2))
    first = td.tool_texts(model, 1)[0]
    assert first.startswith("Draft rejected") and "reports KeyError" in first
    assert f"{td.NEW_NODE}: builtins.AssertionError" in first and "total() raised KeyError: 'discount'" in first


# ---- 2.1 the red check records the message and the paths ----------------------------------------------------------
# In the sandbox: tests/test_draft.py (test_the_red_check_records_the_message_and_the_repository_files_of_the_chain).

def test_the_red_check_prints_no_traceback_or_warning_summary():
    i = va.RED_CHECK.index("pytest.main(")
    call = va.RED_CHECK[i:va.RED_CHECK.index("plugins=", i)]
    assert '"--tb=no"' in call and '"-rN"' in call and '"--disable-warnings"' in call and "no:warnings" not in call
