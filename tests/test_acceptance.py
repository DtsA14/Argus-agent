"""Slice 1 of general tasks, the deterministic core without Docker: the contract, the workspace scope, structured
validation commands and their results, SUMMARY.json claims, and the verdict (docs/reviews/ACCEPTANCE_GENERAL.md).

The guarantee under test everywhere: the harness decides from its own evidence. A claim, an exit code 0 with no
tests, a skipped test, a changed protected file or an unverifiable check never adds up to a pass."""
import copy
import json
import math
import os
import shutil
import sys
from pathlib import Path

import pytest

from acceptance import claims as cl
from acceptance import contract as ct
from acceptance import validation as va
from acceptance.verdict import evaluate, outcome
from acceptance.workspace import SPECIAL, diff, prepare, scope_check, snapshot

ROOT = Path(__file__).resolve().parent.parent
CONTRACT = json.loads((ROOT / "fixtures" / "contracts" / "fix_divide.json").read_text(encoding="utf-8"))
REPO = ROOT / CONTRACT["inputs"]["workspace"]
FIXED = "def divide(a, b):\n    return a / b\n"


def contract(**over):
    c = copy.deepcopy(CONTRACT)
    c.update(over)
    return c


def unit(**over):
    return {**copy.deepcopy(CONTRACT["validation"][0]), **over}


# ---- the contract ------------------------------------------------------------------------------

def test_the_fixture_contract_is_valid_and_matches_its_repository():
    assert ct.validate(CONTRACT) == []
    assert ct.check_scope_against(CONTRACT, snapshot(REPO, skip_cache=True)) == []


def test_freezing_is_stable_and_refuses_an_invalid_contract():
    text, sha = ct.freeze(CONTRACT)
    assert ct.freeze(json.loads(text)) == (text, sha)
    with pytest.raises(ct.ContractError):
        ct.freeze(contract(judge=[{"id": "nice"}]))


def _set(path, value):
    def f(c):
        node = c
        for k in path[:-1]:
            node = node[k]
        node[path[-1]] = value
        return c
    return f


BAD_CONTRACTS = {
    "unknown key": lambda c: {**c, "notes": "x"},
    "missing validation": lambda c: {k: v for k, v in c.items() if k != "validation"},
    "shell string": _set(["validation", 0, "args"], "python -m unittest discover"),
    "sh executable": _set(["validation", 0, "executable"], "sh"),
    "bash -c": _set(["validation", 0, "executable"], "bash"),
    "python -c": _set(["validation", 0, "args"], ["-c", "print('Ran 9 tests')"]),
    "other module": _set(["validation", 0, "args"], ["-m", "pip", "install", "x"]),
    "not discover": _set(["validation", 0, "args"], ["-m", "unittest", "tests.test_calc"]),
    "unknown option": _set(["validation", 0, "args"], ["-m", "unittest", "discover", "-v", "x"]),
    "dotdot value": _set(["validation", 0, "args"], ["-m", "unittest", "discover", "-s", "../x"]),
    "absolute value": _set(["validation", 0, "args"], ["-m", "unittest", "discover", "-s", "/etc"]),
    "shell metachar": _set(["validation", 0, "args"], ["-m", "unittest", "discover", "-s", "t;rm"]),
    "option without value": _set(["validation", 0, "args"], ["-m", "unittest", "discover", "-s"]),
    "repeated -s": _set(["validation", 0, "args"], ["-m", "unittest", "discover", "-s", "a", "-s", "b"]),
    "timeout 0": _set(["validation", 0, "timeout_s"], 0),
    "timeout inf": _set(["validation", 0, "timeout_s"], math.inf),
    "timeout too long": _set(["validation", 0, "timeout_s"], 601),
    "min_tests 0": _set(["validation", 0, "min_tests"], 0),
    "min_tests bool": _set(["validation", 0, "min_tests"], True),
    "max_skipped negative": _set(["validation", 0, "max_skipped"], -1),
    "bad must_pass": _set(["validation", 1, "must_pass"], ["test_divide_by_zero"]),
    "duplicate id": _set(["validation", 1, "id"], "unit"),
    "judge criteria": _set(["judge"], [{"id": "style"}]),
    "writable equals protected": _set(["scope", "protected"], ["src/**"]),
    "glob with dotdot": _set(["scope", "writable"], ["../src/**"]),
    "absolute glob": _set(["scope", "protected"], ["/tests/**"]),
    "empty protected": _set(["scope", "protected"], []),
    "workspace outside fixtures": _set(["inputs", "workspace"], "src"),
    "other artifact": _set(["artifacts"], [{"path": "OUT.md", "type": "json", "schema": "claims_v1"}]),
    "max_usd inf": _set(["limits", "max_usd"], math.inf),
    "max_usd too high": _set(["limits", "max_usd"], 50),
    "iterations 0": _set(["limits", "max_iterations"], 0),
}


@pytest.mark.parametrize("case", sorted(BAD_CONTRACTS))
def test_an_invalid_contract_is_refused(case):
    assert ct.validate(BAD_CONTRACTS[case](copy.deepcopy(CONTRACT)))


def test_the_scope_must_fit_the_input_repository():
    files = snapshot(REPO, skip_cache=True)
    overlap = contract(scope={"writable": ["src/**"], "protected": ["src/calc.py", "tests/**"]})
    assert any("both writable and protected" in e for e in ct.check_scope_against(overlap, files))
    typo = contract(scope={"writable": ["src/**"], "protected": ["test/**"]})
    assert any("matches no input file" in e for e in ct.check_scope_against(typo, files))


def test_globs_match_whole_path_components():
    assert ct.matches("src/calc.py", ["src/**"]) and ct.matches("src/a/b.py", ["src/**"])
    assert not ct.matches("srcx/calc.py", ["src/**"]) and not ct.matches("tests/src/x.py", ["src/**"])
    assert ct.matches("tests/test_calc.py", ["tests/*.py"]) and not ct.matches("tests/a/b.py", ["tests/*.py"])


# ---- validation commands -------------------------------------------------------------------------

def test_the_command_run_is_the_allowlisted_argv_and_never_a_shell():
    assert va.argv(CONTRACT["validation"][1]) == ["python3", "-I", "-m", "unittest", "discover", "-s", "tests",
                                                  "-t", ".", "-k", "test_divide_by_zero", "-v"]
    with pytest.raises(ValueError):
        va.argv(unit(executable="sh", args=["-c", "true"]))


VERBOSE_OK = """test_add (tests.test_calc.CalcTest.test_add) ... ok
test_divide_by_zero (tests.test_calc.CalcTest.test_divide_by_zero) ... ok

----------------------------------------------------------------------
Ran 2 tests in 0.001s

OK
"""


def run_result(stderr, exit_code=0, **over):
    return {"exit_code": exit_code, "stdout": "", "stderr": stderr, "timed_out": False, "killed": False,
            "truncated": False, "output_limit_exceeded": False, "cleanup_failed": False, **over}


def test_unittest_output_is_parsed_per_test_and_in_summary():
    p = va.parse_unittest(VERBOSE_OK)
    assert p["tests_run"] == 2 and p["outcome"] == "OK" and p["skipped"] == 0
    assert p["tests"]["tests.test_calc.CalcTest.test_divide_by_zero"] == "ok"
    p = va.parse_unittest("test_a (m.C.test_a) ... skipped 'later'\nRan 1 test in 0s\n\nOK (skipped=1)\n")
    assert p["skipped"] == 1 and p["tests"]["m.C.test_a"].startswith("skipped")
    p = va.parse_unittest("test_a (m.C.test_a)\nDoc line ... FAIL\nRan 1 test in 0s\n\nFAILED (failures=1)\n")
    assert p["tests"]["m.C.test_a"] == "FAIL" and p["failures"] == 1 and p["outcome"] == "FAILED"
    p = va.parse_unittest("\nRan 0 tests in 0.000s\n\nNO TESTS RAN\n")
    assert p["tests_run"] == 0 and p["outcome"] == "NO TESTS RAN"


def test_a_clean_run_with_the_required_tests_passes():
    spec = unit(min_tests=2, must_pass=["tests.test_calc.CalcTest.test_divide_by_zero"])
    assert va.judge_result(spec, run_result(VERBOSE_OK))["status"] == "pass"


BAD_RUNS = {   # case: (spec, run result, what the reason must say)
    "exit 0 but no tests ran": (unit(min_tests=1), run_result("Ran 0 tests in 0s\n\nNO TESTS RAN\n"),
                                "0 tests ran"),
    "exit 0 and no summary": (unit(min_tests=1), run_result("all good, trust me\n"), "no unittest summary"),
    "fewer tests than required": (unit(min_tests=3), run_result(VERBOSE_OK), "2 tests ran"),
    "skipped tests": (unit(min_tests=1, max_skipped=0),
                      run_result("test_a (m.C.test_a) ... skipped 'x'\nRan 1 test in 0s\n\nOK (skipped=1)\n"),
                      "1 tests skipped"),
    "failed tests": (unit(min_tests=1), run_result("Ran 2 tests in 0s\n\nFAILED (failures=1)\n", exit_code=1),
                     "exit code 1"),
    "FAILED summary with exit 0": (unit(min_tests=1), run_result("Ran 2 tests in 0s\n\nFAILED (errors=1)\n"),
                                   "unittest outcome FAILED"),
    "OK printed but exit 1": (unit(min_tests=1), run_result(VERBOSE_OK, exit_code=1), "exit code 1"),
    "required test missing": (unit(min_tests=1, must_pass=["tests.test_calc.CalcTest.test_mean"]),
                              run_result(VERBOSE_OK), "test_mean did not run"),
    "required test failed": (unit(min_tests=1, must_pass=["tests.test_calc.CalcTest.test_add"]),
                             run_result(VERBOSE_OK.replace("test_add) ... ok", "test_add) ... FAIL")),
                             "test_add is 'FAIL'"),
    "timed out": (unit(min_tests=1), run_result(VERBOSE_OK, exit_code=None, timed_out=True),
                  "timed out after 60s"),
    "output flood": (unit(min_tests=1), run_result(VERBOSE_OK, output_limit_exceeded=True), "output limit"),
}


@pytest.mark.parametrize("case", sorted(BAD_RUNS))
def test_a_validation_run_that_does_not_show_success_fails(case):
    spec, r, why = BAD_RUNS[case]
    v = va.judge_result(spec, r)
    assert v["status"] == "fail" and why in v["reason"], v["reason"]


def test_no_sandbox_means_blocked_never_a_pass(tmp_path):
    v = va.run_validation(unit(), tmp_path, {"kind": "none"})
    assert v["status"] == "blocked" and "sandbox unavailable" in v["reason"]


# ---- workspace and scope --------------------------------------------------------------------------

@pytest.fixture
def ws(tmp_path):
    before = prepare(REPO, tmp_path / "ws")
    return tmp_path / "ws", before


def statuses(criteria):
    return {c["id"]: c["status"] for c in criteria}


def test_the_workspace_is_an_exact_copy_without_bytecode_caches(ws, tmp_path):
    root, before = ws
    assert before == snapshot(REPO, skip_cache=True) and "src/calc.py" in before
    src = tmp_path / "input"
    shutil.copytree(REPO, src)
    (src / "src" / "__pycache__").mkdir(exist_ok=True)
    (src / "src" / "__pycache__" / "calc.cpython-313.pyc").write_bytes(b"stale")
    copied = prepare(src, tmp_path / "ws2")
    assert not any("__pycache__" in p for p in copied) and not (tmp_path / "ws2" / "src" / "__pycache__").exists()


def test_changing_only_writable_files_is_in_scope(ws):
    root, before = ws
    (root / "src" / "calc.py").write_text(FIXED, encoding="utf-8")
    (root / "src" / "helpers.py").write_text("X = 1\n", encoding="utf-8")
    (root / "SUMMARY.json").write_text("{}", encoding="utf-8")
    assert set(statuses(scope_check(CONTRACT, before, snapshot(root))).values()) == {"pass"}


SCOPE_BREAKS = {
    "edit a test": (lambda r: (r / "tests" / "test_calc.py").write_text("import unittest\n"), "scope:protected"),
    "delete a test": (lambda r: (r / "tests" / "test_calc.py").unlink(), "scope:protected"),
    "add a test file": (lambda r: (r / "tests" / "test_extra.py").write_text("x = 1\n"), "scope:protected"),
    "write outside scope": (lambda r: (r / "setup.py").write_text("x = 1\n"), "scope:writable"),
}


@pytest.mark.parametrize("case", sorted(SCOPE_BREAKS))
def test_a_change_outside_the_scope_fails(ws, case):
    root, before = ws
    change, failing = SCOPE_BREAKS[case]
    change(root)
    s = statuses(scope_check(CONTRACT, before, snapshot(root)))
    assert s[failing] == "fail"


@pytest.mark.skipif(sys.platform == "win32", reason="symlinks need privileges on Windows; the VM runs this")
def test_a_symlink_in_the_workspace_fails_and_is_not_followed(ws, tmp_path):
    root, before = ws
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "secret.py").write_text("x = 1\n")
    os.symlink(outside, root / "src" / "linked")
    after = snapshot(root)
    assert after["src/linked"] == SPECIAL and not any(p.startswith("src/linked/") for p in after)
    assert statuses(scope_check(CONTRACT, before, after))["scope:regular_files"] == "fail"


# ---- SUMMARY.json claims --------------------------------------------------------------------------

def summary(*claims, text="Fixed divide."):
    return {"claims": list(claims), "summary": text}


@pytest.mark.parametrize("doc", [
    [], {"claims": []}, summary(), summary({"claim": "all_good"}),
    summary({"claim": "tests_pass"}), summary({"claim": "tests_pass", "evidence": "validation:unit", "x": 1}),
    summary({"claim": ["tests_pass"], "evidence": "validation:unit"}),
    summary({"claim": "file_changed", "path": ""}), summary({"claim": "tests_pass", "evidence": "x"}, text=1),
    {"claims": [{"claim": "tests_pass", "evidence": "validation:unit"}], "summary": "x", "confidence": 1.0},
], ids=str)
def test_a_summary_outside_the_schema_is_rejected(doc):
    assert cl.schema_problems(doc)


def passed(vid, must=None):
    return {"id": vid, "status": "pass", "reason": "", "evidence": {"must_pass": must or {}}}


def failed(vid):
    return {"id": vid, "status": "fail", "reason": "exit code 1", "evidence": {"must_pass": {}}}


CHANGES = {"added": [], "removed": [], "modified": ["src/calc.py"]}
TARGET = {"tests.test_calc.CalcTest.test_divide_by_zero": "ok"}


def test_claims_backed_by_evidence_pass():
    doc = summary({"claim": "tests_pass", "evidence": "validation:unit"},
                  {"claim": "issue_fixed", "evidence": "validation:target"},
                  {"claim": "file_changed", "path": "src/calc.py"})
    vals = {"validation:unit": passed("validation:unit"), "validation:target": passed("validation:target", TARGET)}
    assert {c["status"] for c in cl.check_claims(doc, vals, CHANGES)} == {"pass"}


FALSE_CLAIMS = {
    "tests pass but they failed": ({"claim": "tests_pass", "evidence": "validation:unit"},
                                   {"validation:unit": failed("validation:unit")}),
    "evidence that does not exist": ({"claim": "tests_pass", "evidence": "validation:lint"},
                                     {"validation:unit": passed("validation:unit")}),
    "fixed, shown by a run with no required test": ({"claim": "issue_fixed", "evidence": "validation:unit"},
                                                     {"validation:unit": passed("validation:unit")}),
    "changed a file it did not change": ({"claim": "file_changed", "path": "src/other.py"}, {}),
    "changed the summary itself": ({"claim": "file_changed", "path": "SUMMARY.json"}, {}),
}


@pytest.mark.parametrize("case", sorted(FALSE_CLAIMS))
def test_a_claim_the_evidence_does_not_support_fails(case):
    claim, vals = FALSE_CLAIMS[case]
    changes = {"added": ["SUMMARY.json"], "removed": [], "modified": ["src/calc.py"]}
    (v,) = cl.check_claims(summary(claim), vals, changes)
    assert v["status"] == "fail" and v["reason"]


# ---- the verdict ------------------------------------------------------------------------------------

def fake_run(results):
    def run(spec, workspace, sandbox_cfg, log=None):
        r = results[spec["id"]]
        return r(workspace) if callable(r) else {**r, "id": f"validation:{spec['id']}", "layer": "C"}
    return run


GOOD_DOC = summary({"claim": "tests_pass", "evidence": "validation:unit"},
                   {"claim": "issue_fixed", "evidence": "validation:target"},
                   {"claim": "file_changed", "path": "src/calc.py"})
ALL_PASS = {"unit": passed("x"), "target": passed("x", TARGET)}


def finish(root, doc=GOOD_DOC):
    (root / "src" / "calc.py").write_text(FIXED, encoding="utf-8")
    (root / "SUMMARY.json").write_text(json.dumps(doc), encoding="utf-8")


def test_everything_backed_by_evidence_is_a_pass(ws):
    root, before = ws
    finish(root)
    v = evaluate(CONTRACT, root, before, {}, run=fake_run(ALL_PASS))
    assert v["outcome"] == "pass", [c for c in v["criteria"] if c["status"] != "pass"]
    assert {c["layer"] for c in v["criteria"]} == {"A", "B", "C", "D"}
    assert v["summary_sha256"] == snapshot(root)["SUMMARY.json"]


def test_a_missing_summary_fails_the_artifact_and_the_claims(ws):
    root, before = ws
    (root / "src" / "calc.py").write_text(FIXED, encoding="utf-8")
    v = evaluate(CONTRACT, root, before, {}, run=fake_run(ALL_PASS))
    s = statuses(v["criteria"])
    assert v["outcome"] == "fail" and s["artifact:SUMMARY.json"] == "fail" and s["claims"] == "fail"


def test_a_true_claim_does_not_rescue_a_failed_check(ws):
    root, before = ws
    finish(root, summary({"claim": "file_changed", "path": "src/calc.py"}))
    v = evaluate(CONTRACT, root, before, {}, run=fake_run({**ALL_PASS, "unit": failed("x")}))
    assert v["outcome"] == "fail"


def test_blocked_wins_over_fail_and_is_never_a_pass(ws):
    root, before = ws
    finish(root)
    blocked = {"status": "blocked", "reason": "sandbox unavailable", "evidence": {}}
    v = evaluate(CONTRACT, root, before, {}, run=fake_run({"unit": failed("x"), "target": blocked}))
    assert v["outcome"] == "blocked"
    assert outcome([{"status": "pass"}, {"status": "blocked"}]) == "blocked"
    assert outcome([{"status": "pass"}, {"status": "fail"}]) == "fail"


def test_a_workspace_that_changes_during_evaluation_invalidates_the_verdict(ws):
    root, before = ws
    finish(root)

    def sneaky(workspace):
        (Path(workspace) / "src" / "calc.py").write_text(FIXED + "# changed later\n", encoding="utf-8")
        return {**passed("validation:target", TARGET), "layer": "C"}

    v = evaluate(CONTRACT, root, before, {}, run=fake_run({"unit": passed("x"), "target": sneaky}))
    s = statuses(v["criteria"])
    assert v["outcome"] == "fail" and s["workspace:unchanged_during_evaluation"] == "fail"


def test_the_diff_reports_added_removed_and_modified():
    assert diff({"a": "1", "b": "2"}, {"b": "3", "c": "4"}) == {"added": ["c"], "removed": ["a"], "modified": ["b"]}


# ---- claims_v2 (eval live #1): an empty claims list is allowed, and claims_v1 keeps its meaning ----------------

V2 = {"path": "SUMMARY.json", "type": "json", "schema": "claims_v2"}


def test_claims_v2_allows_an_empty_list_and_v1_still_does_not():
    empty = summary()
    assert cl.schema_problems(empty, "claims_v2") == []
    assert cl.schema_problems(empty, "claims_v1") and cl.schema_problems(empty)      # v1 is the default, unchanged
    assert cl.schema_problems(summary({"claim": "all_good"}), "claims_v2")           # still no unknown kinds
    assert cl.schema_problems(summary(*[{"claim": "file_changed", "path": "a"}] * 51), "claims_v2")
    assert cl.schema_problems(empty, "claims_v3") == ["unknown claims schema 'claims_v3'"]


def test_a_contract_names_its_claims_schema():
    assert ct.validate(contract(artifacts=[V2])) == []
    assert ct.validate(contract(artifacts=[{**V2, "schema": "claims_v3"}]))
    assert ct.validate(contract(artifacts=[{**V2, "extra": 1}]))


def test_claiming_nothing_neither_passes_a_failed_task_nor_fails_a_done_one(ws):
    root, before = ws
    c = contract(artifacts=[V2])
    (root / "SUMMARY.json").write_text(json.dumps(summary()), encoding="utf-8")
    failed = evaluate(c, root, before, {}, run=fake_run({"unit": failed("x"), "target": failed("x")}))
    assert failed["outcome"] == "fail" and statuses(failed["criteria"])["claims"] == "pass"
    (root / "src" / "calc.py").write_text(FIXED, encoding="utf-8")
    done = evaluate(c, root, before, {}, run=fake_run(ALL_PASS))
    assert done["outcome"] == "pass" and {x["layer"] for x in done["criteria"]} == {"A", "B", "C", "D"}
    v1 = evaluate(CONTRACT, root, before, {}, run=fake_run(ALL_PASS))                # the same file under claims_v1
    assert v1["outcome"] == "fail" and statuses(v1["criteria"])["artifact:SUMMARY.json"] == "fail"
