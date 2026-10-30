"""Vitest validations without Docker (docs/reviews/SPEC_PWA_VIEWER.md V, section 9): the contract shape, the judgement
of the harness recorder's JSON (behind a nonce, exactly the requested modules), the contract and draft rules, and the
drafter's runner. The real sandbox runs are in tests/test_vitest_sandbox.py."""
import json

import pytest

from acceptance import contract as ct
from acceptance import draft as dr
from acceptance import validation as va
from codetask import drafter

NONCE = "ARGUS-VITEST-0123456789abcdef:"
FILE = "src/list.test.jsx"
OK = f"{FILE}::shows the total"
RED = f"{FILE}::group > fails by an assertion"


def spec(*files, must=(), **extra):
    return {"id": "t", "executable": "vitest", "args": ["run", *(files or (FILE,))], "timeout_s": 120,
            "min_tests": 1, "max_skipped": 0, "must_pass": list(must), "environment": "pwa_node22", **extra}


def rec(state, type_=None, path=None, message=None, where=None):
    return {"state": state, "type": type_, "path": path, "where": where, "message": message, "message_names": [],
            "repo_paths": [path] if path else []}


def recorded(tests=None, modules=None, **extra):
    tests = tests if tests is not None else {OK: rec("passed")}
    modules = modules if modules is not None else {FILE: {"errors": []}}
    return {"tests": tests, "modules": modules, "count": len(tests), "unhandled": [], "fatal": None, **extra}


def output(record, nonce=NONCE, before="", after=""):
    return before + "\n" + nonce + json.dumps(record) + "\n" + after


def run(stdout, exit_code=0, **extra):
    return {"stdout": stdout, "stderr": "", "exit_code": exit_code, "timed_out": False, "killed": False,
            "cleanup_failed": False, "output_limit_exceeded": False, "truncated": False, **extra}


# --- the contract shape (V1) ---

@pytest.mark.parametrize("args", [["run", FILE], ["run", "a.test.js", "b/c.test.ts", "d.test.tsx"]])
def test_a_vitest_command_is_run_and_plain_test_files(args):
    assert va.validate_command("vitest", args) == []
    assert va.kind({"executable": "vitest", "args": args}) == "vitest"


@pytest.mark.parametrize("args, why", [
    (["run"], "at least one"),
    (["watch", FILE], "run"),
    (["run", FILE, "--reporter=verbose"], "not allowed"),
    (["run", FILE, "-t", "x"], "not allowed"),
    (["run", "src/list.jsx"], "test file"),
    (["run", "../x.test.js"], "test file"),
    (["run", "src/../x.test.js"], "test file"),
    (["run", "/workspace/x.test.js"], "test file"),
    (["run", "src/*.test.js"], "test file"),
    (["run", FILE, FILE], "twice"),
])
def test_anything_else_in_a_vitest_command_is_refused(args, why):
    errors = va.validate_command("vitest", args)
    assert errors and why in " ".join(errors)


def test_python_commands_are_unchanged_and_other_executables_refused():
    assert va.validate_command("python", ["-m", "pytest", "tests"]) == []
    assert "allowlist" in va.validate_command("node", ["x.js"])[0]


def test_the_argv_is_the_harness_recorder_never_a_contract_option():
    a = va.vitest_argv(NONCE, [FILE])
    assert a[:4] == ["node", "--input-type=module", "-e", va.VITEST_RECORDER]
    assert a[4:] == [NONCE, json.dumps(va.RED_LIMITS, sort_keys=True), FILE]


# --- judging the recorder's JSON (V2) ---

def test_a_run_whose_required_tests_passed_passes():
    v = va.judge_result(spec(must=[OK]), run(output(recorded())), nonce=NONCE)
    assert v["status"] == "pass", v["reason"]
    e = v["evidence"]
    assert e["runner"] == "vitest" and e["must_pass"] == {OK: "ok"} and e["consistent"] is True
    assert NONCE not in json.dumps(e)            # the nonce never reaches the evidence (a later run's own is new)


def test_a_failed_required_test_fails_and_is_named_with_its_error():
    r = recorded({OK: rec("passed"), RED: rec("failed", "AssertionError", FILE, "expected 0 to be 1", FILE + ":7")})
    v = va.judge_result(spec(must=[OK, RED]), run(output(r)), nonce=NONCE)
    assert v["status"] == "fail" and f"required test {RED} is 'FAIL'" in v["reason"]
    assert v["evidence"]["failed_nodes"] == [RED] and v["evidence"]["failures"] == 1
    assert "AssertionError: expected 0 to be 1" in v["evidence"]["output_tail"] and FILE + ":7" in \
        v["evidence"]["output_tail"]


@pytest.mark.parametrize("stdout, why", [
    ("no record at all", "no vitest record"),
    (output(recorded()) + output(recorded()), "no vitest record"),
    (output(recorded(), nonce="ARGUS-VITEST-ffffffffffffffff:"), "no vitest record"),
    (NONCE + "{not json\n", "no vitest record"),
    (output(recorded(modules={})), "did not run exactly"),
    (output(recorded(modules={FILE: {"errors": []}, "src/list.test.js": {"errors": []}})), "did not run exactly"),
    (output(recorded(fatal="failed to load config")), "vitest could not start: failed to load config"),
    (output(recorded(unhandled=["TypeError: x"])), "unhandled"),
    (output(recorded(count=2)), "inconsistent"),                    # two tests with the same full name
    (output(recorded({"src/other.test.js::x": rec("passed")})), "did not run exactly"),
])
def test_a_record_that_cannot_be_trusted_never_passes(stdout, why):
    v = va.judge_result(spec(must=[OK]), run(stdout), nonce=NONCE)
    assert v["status"] == "fail" and why in v["reason"], v["reason"]


def test_a_requested_file_that_did_not_run_at_all_is_never_a_pass():
    v = va.judge_result(spec(FILE, "src/b.test.js", must=[OK]), run(output(recorded())), nonce=NONCE)
    assert v["status"] == "fail" and "did not run exactly" in v["reason"], v["reason"]


def test_an_inconsistent_vitest_baseline_is_named_even_when_its_counts_look_right():
    """M34: the red test fails as expected, but the record is not trusted (here: an unhandled error)."""
    ev = {"must_pass": {RED: "FAIL"}, "failures": 1, "errors": 0, "consistent": False, "failed_nodes": [RED]}
    validate = lambda s, ws, cfg: {"status": "fail", "reason": "x", "evidence": ev}
    problems, _ = dr.baseline_problems(contract(spec(must=[RED])), {FILE}, "/ws", {}, validate=validate,
                                       red=lambda *a, **k: ({}, None))
    assert any("vitest output does not account for itself" in p for p in problems), problems


def test_a_module_that_fails_to_load_is_an_error_named_in_the_output():
    r = recorded({OK: rec("passed")}, {FILE: {"errors": []}, "src/b.test.js": {"errors": [
        {"name": "Error", "message": 'Failed to resolve import "./Missing.jsx"'}]}})
    v = va.judge_result(spec(FILE, "src/b.test.js", must=[OK]), run(output(r)), nonce=NONCE)
    assert v["status"] == "fail" and v["evidence"]["errors"] == 1
    assert "src/b.test.js" in v["evidence"]["output_tail"] and "Missing.jsx" in v["evidence"]["output_tail"]


def test_skips_count_against_max_skipped_and_no_tests_is_never_a_pass():
    r = recorded({OK: rec("passed"), FILE + "::later": rec("skipped")})
    v = va.judge_result(spec(must=[OK]), run(output(r)), nonce=NONCE)
    assert v["status"] == "fail" and "1 tests skipped" in v["reason"]
    v = va.judge_result(spec(), run(output(recorded({}))), nonce=NONCE)
    assert v["status"] == "fail" and "NO TESTS RAN" in v["reason"]


def test_a_killed_or_cut_run_never_passes():
    for extra in ({"timed_out": True}, {"output_limit_exceeded": True}, {"truncated": True}, {"exit_code": 137}):
        assert va.judge_result(spec(must=[OK]), run(output(recorded()), **extra), nonce=NONCE)["status"] == "fail"


def test_red_check_records_have_the_pytest_shape():
    r = recorded({RED: rec("failed", "AssertionError", FILE, "expected 0 to be 1"),
                  OK: rec("failed", "TestingLibraryElementError", FILE, "Unable to find an element")})
    got, why = va.red_records(output(r), NONCE, [RED, OK])
    assert why is None and got[RED]["outcome"] == "failed" and got[RED]["assertion"] is True
    assert got[RED]["path"] == FILE
    assert got[OK]["assertion"] is False and got[OK]["type"] == "TestingLibraryElementError"
    assert set(got[RED]) >= {"outcome", "type", "assertion", "path", "message", "message_names", "repo_paths"}
    assert va.red_records(output(r), NONCE, [FILE + "::missing"]) == ({}, None)
    assert va.red_records("nothing", NONCE, [RED]) == (None, "no vitest record in the output")


@pytest.mark.parametrize("record, why", [
    (recorded({RED: rec("failed", "AssertionError", FILE)}, count=2), "inconsistent"),     # two tests, one name
    (recorded({RED: rec("failed", "AssertionError", FILE)}, unhandled=["Error: x"]), "unhandled"),
    (recorded({RED: rec("failed", "AssertionError", FILE)}, fatal="no config"), "could not start"),
    (recorded({RED: rec("failed", "AssertionError", FILE)}, modules={FILE: {"errors": []}, "x.test.js": {"errors": []}}),
     "did not run exactly"),
])
def test_the_red_check_trusts_a_record_no_more_than_a_validation_does(record, why):
    got, reason = va.red_records(output(record), NONCE, [RED])
    assert got is None and why in reason


# --- what vitest loads besides the tests (review of PR 1) ---

@pytest.mark.parametrize("paths, why", [
    (["node_modules/vitest/index.js"], "node_modules"),
    (["src/node_modules/react/index.js"], "src/node_modules"),
    (["src/package.json"], "src/package.json"),
    (["lib/.npmrc"], "lib/.npmrc"),
])
def test_a_workspace_that_would_shadow_the_environments_packages_is_never_run(tmp_path, monkeypatch, paths, why):
    for p in ["package.json", "src/list.jsx", FILE, *paths]:
        (tmp_path / p).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / p).write_text("x")

    def never(*a, **k):
        raise AssertionError("the sandbox must not be started")
    monkeypatch.setattr(va.sb, "run_command", never)
    v = va.run_validation(spec(must=[OK]), str(tmp_path), {})
    assert v["status"] == "fail" and why in v["reason"], v["reason"]
    got, reason = va.red_check([RED], str(tmp_path), {}, timeout_s=9, environment="pwa_node22", runner="vitest")
    assert got is None and why in reason


def test_a_root_package_json_and_the_repositorys_own_files_are_fine(tmp_path):
    for p in ["package.json", "vite.config.js", "src/list.jsx", FILE]:
        (tmp_path / p).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / p).write_text("x")
    assert va.vitest_workspace_problems(str(tmp_path)) == []


@pytest.mark.parametrize("glob, refused", [
    ("**", True), ("*", True), ("*.js", True), ("vite.config.js", True), ("vitest.config.ts", True),
    ("package.json", True), (".npmrc", True), ("src/**", False), ("src/list.jsx", False), ("src/*.jsx", False),
])
def test_a_vitest_scope_never_makes_the_config_or_the_packages_writable(glob, refused):
    c = contract()
    c["scope"]["writable"] = [glob]
    problems = ct.setup_problems(c, {"src/list.jsx": "s", FILE: "s"}, profiles=None, environments_configured=None)
    assert any("vitest loads" in p for p in problems) is refused, problems


def test_a_repository_with_its_own_node_modules_is_refused_for_vitest():
    problems = ct.setup_problems(contract(), {"src/list.jsx": "s", FILE: "s", "node_modules/react/index.js": "s"},
                                 profiles=None, environments_configured=None)
    assert any("node_modules" in p for p in problems)
    py = contract({"id": "p", "executable": "python", "args": ["-m", "pytest", "t"], "timeout_s": 9, "min_tests": 1,
                   "max_skipped": 0, "must_pass": []})
    py["scope"]["writable"] = ["**"]
    py["scope"]["protected"] = ["t/**"]
    assert not [p for p in ct.setup_problems(py, {"t/x.py": "s"}, profiles=None, environments_configured=None)
                if "vitest" in p or "node_modules" in p]


# --- contract (section 9) ---

def contract(*vals):
    return {"contract": "t", "version": 1, "inputs": {"workspace": "fixtures/repos/viewer", "issue": "i"},
            "scope": {"writable": ["src/list.jsx"], "protected": ["src/*.test.jsx"]},
            "artifacts": [{"path": "SUMMARY.json", "type": "json", "schema": "claims_v1"}],
            "validation": list(vals) or [spec(must=[OK, RED])], "judge": [],
            "limits": {"max_usd": 1, "max_iterations": 3}}


def test_vitest_node_ids_may_have_spaces_but_not_newlines():
    assert ct.validate(contract()) == []
    for ch in ("\n", "\r", "\x1b", "\x00", "\x7f"):     # printed in logs and screens: no control characters
        assert any("must_pass" in e for e in ct.validate(contract(spec(must=[FILE + "::a" + ch + "b"])))), repr(ch)
    assert any("must_pass" in e for e in ct.validate(contract(spec(must=["src/other.py::test_x"]))))


def test_the_command_must_match_the_runner_of_its_environment():
    envs = {"pwa_node22": {"image": "x", "runner": "vitest"}, "argus": {"image": "y"}}
    assert ct.setup_problems(contract(), {"src/list.jsx": "s", FILE: "s"}, profiles=None,
                             environments_configured=envs) == []
    wrong = contract(spec(environment="argus"))
    assert any("runner" in p for p in ct.setup_problems(wrong, {"src/list.jsx": "s", FILE: "s"}, profiles=None,
                                                        environments_configured=envs))
    py = contract({"id": "p", "executable": "python", "args": ["-m", "pytest", "t"], "timeout_s": 9, "min_tests": 1,
                   "max_skipped": 0, "must_pass": [], "environment": "pwa_node22"})
    assert any("runner" in p for p in ct.setup_problems(py, {"src/list.jsx": "s", FILE: "s"}, profiles=None,
                                                        environments_configured=envs))
    no_env = contract({k: v for k, v in spec().items() if k != "environment"})
    assert any("runner" in p for p in ct.setup_problems(no_env, {"src/list.jsx": "s", FILE: "s"}, profiles=None,
                                                        environments_configured=envs))


# --- drafts (section 9) ---

def draft(new_path=FILE, **extra):
    return {"draft_version": dr.VERSION, "base": "b",
            "plan": {"files": ["src/list.jsx"], "steps": ["s"], "risks": []},
            "contract": {"scope": {"writable": ["src/list.jsx"], "protected": ["src/*.test.jsx"]},
                         "validation": [spec(must=[RED])], "budget_profile": "default"},
            "new_tests": [{"path": new_path, "content": "test('x', () => {})"}], "unverifiable": [], **extra}


def test_a_vitest_draft_adds_test_files_of_its_runner():
    assert dr.validate_draft(draft()) == []
    assert any("test file" in e for e in dr.validate_draft(draft("tests/test_list.py")))
    assert any("test file" in e for e in dr.validate_draft(draft("src/list.jsx")))


def test_a_pytest_draft_still_adds_test_py_files():
    d = draft("tests/test_list.py")
    d["contract"]["validation"] = [{"id": "p", "executable": "python", "args": ["-m", "pytest", "tests"],
                                    "timeout_s": 9, "min_tests": 1, "max_skipped": 0, "must_pass": []}]
    assert dr.validate_draft(d) == []
    assert any("test_*.py" in e for e in dr.validate_draft({**d, "new_tests": [{"path": FILE, "content": "x"}]}))


def test_changed_tests_are_refused_for_vitest_in_v0():
    d = draft(changed_tests=[{"path": "src/old.test.jsx", "content": "x"}])
    assert any("changed_tests" in e and "vitest" in e for e in dr.validate_draft(d))


def test_one_draft_never_mixes_runners():
    d = draft()
    d["contract"]["validation"].append({"id": "p", "executable": "python", "args": ["-m", "pytest", "tests"],
                                        "timeout_s": 9, "min_tests": 1, "max_skipped": 0, "must_pass": []})
    errors = dr.validate_draft(d)
    assert any("runner" in e for e in errors)
    assert not any("new_tests" in e for e in errors), errors      # no advice about test files before one runner


def test_red_by_assertion_reads_vitest_records_like_pytest_ones():
    c = contract()
    good = {RED: {"outcome": "failed", "type": "AssertionError", "assertion": True, "path": FILE, "message": "m",
                  "message_names": [], "repo_paths": [FILE]}}
    seen = {}

    def red(nodes, ws, cfg, **kw):
        seen.update(kw)
        return good, None
    assert dr.red_by_assertion(spec(must=[RED]), [RED], "/ws", {}, c, {FILE}, red=red) == ([], good)
    assert seen["runner"] == "vitest"
    bad = {RED: {**good[RED], "type": "TestingLibraryElementError", "assertion": False}}
    problems, _ = dr.red_by_assertion(spec(must=[RED]), [RED], "/ws", {}, c, {FILE},
                                      red=lambda *a, **k: (bad, None))
    assert problems and "TestingLibraryElementError" in problems[0]
    assert "queryByText" in problems[0] and "hasattr" not in problems[0]       # the vitest hint, not Python's


# --- the drafter (V5) ---

POLICY = {"environment": "pwa_node22", "runner": "vitest", "validation_timeout_s": 120, "profiles": ["default"],
          "max_submits": 3}


def test_the_drafter_builds_vitest_validations_for_a_vitest_environment():
    args = {"plan": {"files": ["src/list.jsx"], "steps": ["s"], "risks": []},
            "scope": {"writable": ["src/list.jsx"], "protected": ["src/*.test.jsx"]},
            "validation": [{"id": "target", "paths": [FILE], "must_pass": [RED], "min_tests": 1}],
            "new_tests": [{"path": FILE, "content": "x"}], "unverifiable": [], "budget_profile": "default"}
    d, problems = drafter.draft_from_args(args, base="b", policy=POLICY)
    assert problems == [] and d["contract"]["validation"][0]["executable"] == "vitest"
    assert d["contract"]["validation"][0]["args"] == ["run", FILE]
    d, problems = drafter.draft_from_args(args, base="b", policy={**POLICY, "runner": "pytest"})
    assert d is None or d["contract"]["validation"][0]["executable"] == "python"


def test_the_drafter_is_told_its_runner():
    assert "vitest" in drafter.system("vitest") and "pytest" not in drafter.system("vitest")
    assert drafter.system("pytest") == drafter.SYSTEM
    prompt = drafter.task_prompt({"issue": "i", "intake": "x"}, 3, {**POLICY, "profile_info": {}, "agent_tools": []})
    assert "vitest" in prompt and "python -m pytest" not in prompt
    old = {k: v for k, v in POLICY.items() if k != "runner"}             # a policy frozen before runners existed
    assert "python -m pytest" in drafter.task_prompt({"issue": "i", "intake": "x"}, 3,
                                                     {**old, "profile_info": {}, "agent_tools": []})


# --- the drafter's tools, call path and swallowed errors for vitest (review of PR 1) ---

def schema(tool):
    from langchain_core.utils.function_calling import convert_to_openai_tool
    return convert_to_openai_tool(tool)["function"]


def test_a_vitest_drafter_is_offered_the_same_tools_by_name_without_changed_tests():
    vit = drafter.offered({"read_file"}, "vitest")
    assert [t.__name__ for t in vit] == ["ReadFile", "SubmitDraft", "ReviseDraft"]
    for t in vit[1:]:
        s = schema(t)
        assert s["name"] == t.__name__ and "changed_tests" not in s["parameters"]["properties"]
        text = json.dumps(s)
        assert "vitest" in text and "pytest" not in text
    py = drafter.offered({"read_file"})
    assert py[1:] == [drafter.SubmitDraft, drafter.ReviseDraft]                  # pytest's tools are unchanged
    assert "changed_tests" in schema(py[1])["parameters"]["properties"]


def test_the_scope_question_reads_the_vitest_call_path():
    d = draft()
    tail = f"FAIL {RED}\n  TypeError: x\n  at src/api.js:3\n  at src/list.jsx:9\n  at {FILE}:7\n1 passed, 1 failed"
    report = {"baseline": {"t": {"status": "fail", "output_tail": tail}}}
    assert drafter.call_path_outside(d, report) == ["src/api.js:3"]          # writable src/list.jsx and the test left out


def test_a_swallowed_vitest_error_is_told_the_vitest_way():
    d = draft()
    rec_ = {"outcome": "failed", "type": "AssertionError", "assertion": True, "path": FILE, "message": "threw TypeError",
            "message_names": ["TypeError"], "repo_paths": [FILE]}
    out = drafter.swallowed_problems(d, {"baseline": {"t": {"red_check": {RED: rec_}}}})
    assert len(out) == 1 and "cause: e" in out[0] and "pytest" not in out[0]
    rec_["repo_paths"] = ["src/list.jsx", FILE]                                # the cause's stack reached the code
    assert drafter.swallowed_problems(d, {"baseline": {"t": {"red_check": {RED: rec_}}}}) == []
    assert "not.toThrow()" not in drafter.SYSTEM_VITEST.split("Never use")[0]
