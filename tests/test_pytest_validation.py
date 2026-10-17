"""M6 W1, without Docker: pytest validation commands (allowlist), the per-node parser on real pytest output captured in
the argus sandbox environment (tests/data/pytest_*.txt, from fixtures/repos/pytest_demo), the fail-closed judgement,
the contract fields, and how a named sandbox environment selects its image.

The real runs in the sandbox are in tests/test_pytest_sandbox.py."""
import copy
from pathlib import Path

import pytest

from acceptance import contract as ct
from acceptance import validation as va
from tools import sandbox as sb

DATA = Path(__file__).resolve().parent / "data"
DEMO = "tests/test_demo.py::"


def captured(name):
    """(exit code, stdout, stderr) of one real run, as saved from the sandbox."""
    text = (DATA / f"pytest_{name}.txt").read_text(encoding="utf-8")
    head, rest = text.split("\n--- stdout\n", 1)
    out, err = rest.split("\n--- stderr\n", 1)
    return int(head.split()[1]), out, err


def result(name, **over):
    code, out, err = captured(name)
    return {"exit_code": code, "stdout": out, "stderr": err, "timed_out": False, "killed": False,
            "output_limit_exceeded": False, "truncated": False, **over}


def spec(*targets, must=(), **extra):
    return {"id": "t", "executable": "python", "args": ["-m", "pytest", *targets], "timeout_s": 60, "min_tests": 1,
            "max_skipped": 0, "must_pass": list(must), **extra}


# ---- the command allowlist ------------------------------------------------------------------------------------

@pytest.mark.parametrize("args", [
    ["-m", "pytest", "tests"],
    ["-m", "pytest", "tests/test_demo.py"],
    ["-m", "pytest", "tests/test_demo.py::TestDiv::test_div", "tests/test_isolation.py"],
    ["-m", "pytest", "tests/test_demo.py::test_add_param[1-2-3]"],
    ["-m", "pytest", "-k", "add", "tests"],
])
def test_allowed_pytest_commands(args):
    assert va.validate_command("python", args) == []


@pytest.mark.parametrize("args, why", [
    (["-m", "pytest"], "at least one test path"),
    (["-m", "pytest", "-k", "add"], "at least one test path"),
    (["-m", "pytest", "-p", "myplugin", "tests"], "not allowed"),
    (["-m", "pytest", "-o", "addopts=-x", "tests"], "not allowed"),
    (["-m", "pytest", "-c", "other.ini", "tests"], "not allowed"),
    (["-m", "pytest", "--rootdir", "/", "tests"], "not allowed"),
    (["-m", "pytest", "--rootdir=/", "tests"], "not allowed"),
    (["-m", "pytest", "-x", "tests"], "not allowed"),
    (["-m", "pytest", "/etc/passwd"], "not a plain relative path"),
    (["-m", "pytest", "../other/tests"], "not a plain relative path"),
    (["-m", "pytest", "tests/../../x"], "not a plain relative path"),
    (["-m", "pytest", "tests/test x.py"], "not a plain relative path"),
    (["-m", "pytest", "tests", "-k"], "needs a value"),
    (["-m", "pytest", "-k", "a or b", "tests"], "not a plain name"),
])
def test_refused_pytest_commands(args, why):
    errors = va.validate_command("python", args)
    assert errors and any(why in e for e in errors), errors


def test_the_harness_alone_sets_pytest_options_and_the_contract_only_names_targets():
    argv = va.argv(spec("-k", "add", "tests"))
    assert argv[:5] == ["python3", "-I", "-B", "-m", "pytest"]
    assert argv[5:5 + len(va.PYTEST_FIXED)] == va.PYTEST_FIXED
    assert argv[5 + len(va.PYTEST_FIXED):] == ["-k", "add", "tests"]
    assert "--rootdir" in va.PYTEST_FIXED and "no:cacheprovider" in va.PYTEST_FIXED and "addopts=" in va.PYTEST_FIXED


def test_unittest_commands_are_unchanged():
    args = ["-m", "unittest", "discover", "-s", "tests"]
    assert va.validate_command("python", args) == [] and va.kind({"args": args}) == "unittest"
    assert va.argv({"executable": "python", "args": args}) == ["python3", "-I", *args, "-v"]


# ---- the parser, on real output --------------------------------------------------------------------------------

def test_every_outcome_is_mapped_per_node():
    p = va.parse_pytest(captured("all")[1])
    assert p["tests"] == {
        DEMO + "test_add": "ok", DEMO + "test_add_param[1-2-3]": "ok", DEMO + "test_add_param[2-2-4]": "ok",
        DEMO + "TestDiv::test_div": "ok", DEMO + "test_fails": "FAIL", DEMO + "test_skipped": "skipped",
        DEMO + "test_xfail": "expected failure", DEMO + "test_xpass": "unexpected success",
        DEMO + "test_setup_error": "ERROR",
        DEMO + "test_teardown_error": "ERROR",          # passed, then its teardown failed: the worse status wins
        "tests/test_isolation.py::test_no_network": "ok", "tests/test_isolation.py::test_workspace_is_read_only": "ok",
        "tests/test_isolation.py::test_runs_as_nobody": "ok"}
    assert (p["tests_run"], p["failures"], p["errors"], p["skipped"]) == (13, 1, 2, 3)   # skipped incl. xfail/xpass
    assert p["consistent"] and p["collected"] == 13 and p["outcome"] == "FAILED"


def test_node_ids_with_spaces_are_parsed():
    """Real output of Argus's own tests (tests/test_parse_subtests.py) in the argus environment: parametrize ids
    with spaces, quotes, brackets and ' ... '."""
    code, out, _ = captured("spaces")
    p = va.parse_pytest(out)
    assert code == 0 and p["consistent"] and p["outcome"] == "OK" and p["tests_run"] == p["collected"] == 7
    assert any(" ... " in n for n in p["tests"]) and set(p["tests"].values()) == {"ok"}


def test_a_status_word_in_a_skip_reason_cannot_turn_a_skip_into_a_pass():
    # the reason is written by the test code; a line read with the wrong status no longer matches the summary
    line = DEMO + "test_skipped SKIPPED (not on this platform)"
    out = captured("all")[1]
    assert line in out
    p = va.parse_pytest(out.replace(line, DEMO + "test_skipped SKIPPED (x) PASSED (y)"))
    assert not p["consistent"]


def test_a_later_pass_line_never_hides_a_failure_of_the_same_node():
    line = DEMO + "test_fails FAILED"
    p = va.parse_pytest(captured("all")[1].replace(line, line + "\n" + DEMO + "test_fails PASSED"))
    assert p["tests"][DEMO + "test_fails"] == "FAIL" and not p["consistent"]


def test_a_collection_error_is_not_consistent():
    p = va.parse_pytest(captured("collection_error")[1])
    assert p["tests"] == {} and p["errors"] == 1 and not p["consistent"]


# ---- the judgement fails closed --------------------------------------------------------------------------------

def test_a_clean_run_with_every_required_node_passes():
    nodes = ["tests/test_isolation.py::test_no_network", "tests/test_isolation.py::test_workspace_is_read_only",
             "tests/test_isolation.py::test_runs_as_nobody"]
    v = va.judge_result(spec("tests/test_isolation.py", must=nodes, min_tests=3), result("isolation"))
    assert v["status"] == "pass", v["reason"]
    assert v["evidence"]["must_pass"] == {n: "ok" for n in nodes} and v["evidence"]["runner"] == "pytest"


def test_required_nodes_are_reported_one_by_one_and_only_ok_passes():
    must = [DEMO + "test_add", DEMO + "test_teardown_error", DEMO + "test_xpass", DEMO + "test_skipped"]
    v = va.judge_result(spec("tests", must=must, max_skipped=5), result("all"))
    assert v["status"] == "fail"
    assert v["evidence"]["must_pass"] == {DEMO + "test_add": "ok", DEMO + "test_teardown_error": "ERROR",
                                          DEMO + "test_xpass": "unexpected success", DEMO + "test_skipped": "skipped"}
    for n in must[1:]:
        assert f"required test {n} is" in v["reason"]


def test_a_required_node_that_was_not_collected_fails():
    missing = "tests/test_isolation.py::test_never_written"
    v = va.judge_result(spec("tests/test_isolation.py", must=[missing]), result("isolation"))
    assert v["status"] == "fail" and v["evidence"]["must_pass"] == {missing: None}
    assert f"required test {missing} did not run" in v["reason"]


@pytest.mark.parametrize("name, why", [
    ("collection_error", "exit code 2"),
    ("file_not_found", "exit code 4"),
    ("node_not_found", "exit code 4"),
    ("deselected", "exit code 5"),
])
def test_runs_that_did_not_test_anything_fail(name, why):
    v = va.judge_result(spec("tests"), result(name))
    assert v["status"] == "fail" and why in v["reason"] and "outcome NO TESTS RAN" in v["reason"]


def drop_line(text, needle):
    return "\n".join(l for l in text.splitlines() if needle not in l)


@pytest.mark.parametrize("tamper", ["drop_a_test_line", "forge_a_test_line", "no_summary", "summary_says_more"])
def test_output_whose_lines_do_not_account_for_the_summary_fails_even_with_exit_0(tamper):
    code, out, err = captured("isolation")
    if tamper == "drop_a_test_line":
        out = drop_line(out, "test_runs_as_nobody PASSED")
    elif tamper == "forge_a_test_line":
        out = out.replace("tests/test_isolation.py::test_runs_as_nobody PASSED",
                          "tests/test_isolation.py::test_runs_as_nobody PASSED\ntests/test_isolation.py::test_extra PASSED")
    elif tamper == "no_summary":
        out = drop_line(out, "3 passed in")
    else:
        out = out.replace("3 passed in", "4 passed in")
    v = va.judge_result(spec("tests/test_isolation.py"), {**result("isolation"), "stdout": out})
    assert v["status"] == "fail"
    assert ("inconsistent" in v["reason"]) or ("no pytest summary" in v["reason"])


def test_truncated_output_fails_closed():
    v = va.judge_result(spec("tests/test_isolation.py"), result("isolation", truncated=True))
    assert v["status"] == "fail" and "output truncated" in v["reason"]


def test_exit_0_with_a_failing_summary_fails():
    v = va.judge_result(spec("tests"), result("all", exit_code=0))
    assert v["status"] == "fail" and "pytest outcome FAILED" in v["reason"]


# ---- contract fields ---------------------------------------------------------------------------------------------

BASE = {"contract": "demo", "version": 1, "inputs": {"workspace": "fixtures/repos/pytest_demo", "issue": "x"},
        "scope": {"writable": ["src/*.py"], "protected": ["tests/**"]},
        "artifacts": [{"path": "SUMMARY.json", "type": "json", "schema": "claims_v2"}],
        "validation": [spec("tests/test_isolation.py", must=["tests/test_isolation.py::test_no_network"],
                            environment="argus")],
        "judge": [], "limits": {"max_usd": 0.5, "max_iterations": 2}}


def with_validation(**changes):
    c = copy.deepcopy(BASE)
    c["validation"][0].update(changes)
    return c


def test_a_pytest_validation_in_a_named_environment_is_a_valid_contract():
    assert ct.validate(BASE) == [] and ct.environments(BASE) == ["argus"]


@pytest.mark.parametrize("changes, why", [
    ({"must_pass": ["tests.test_isolation.test_no_network"]}, "pytest node ids"),
    ({"must_pass": ["tests/test_isolation.py"]}, "pytest node ids"),
    ({"must_pass": ["tests/test_isolation.py::test_no_network"] * 2}, "duplicates"),
    ({"environment": "Argus"}, "environment must be a lower-case name"),
    ({"environment": ""}, "environment must be a lower-case name"),
    ({"args": ["-m", "pytest", "-p", "x", "tests"]}, "not allowed"),
])
def test_invalid_pytest_validations_are_refused(changes, why):
    errors = ct.validate(with_validation(**changes))
    assert any(why in e for e in errors), errors


def test_unittest_validations_still_need_dotted_ids():
    c = with_validation(args=["-m", "unittest", "discover", "-s", "tests"],
                        must_pass=["tests/test_isolation.py::test_no_network"])
    assert any("dotted test ids" in e for e in ct.validate(c))


def test_a_contract_without_environment_names_none():
    c = with_validation()
    del c["validation"][0]["environment"]
    assert ct.validate(c) == [] and ct.environments(c) == []


# ---- named environments select their image ------------------------------------------------------------------

ENVS = {"kind": "docker", "image": "sha256:" + "a" * 64, "environments": {"argus": {"image": "sha256:" + "b" * 64}}}


@pytest.fixture(autouse=True)
def no_image_overrides(monkeypatch):
    """The image overrides of the machine running the tests (verify.sh sets them) must not leak into these."""
    monkeypatch.delenv("ARGUS_SANDBOX_IMAGE", raising=False)
    monkeypatch.delenv("ARGUS_SANDBOX_IMAGE_ARGUS", raising=False)


def test_an_environment_runs_its_own_image_and_the_default_override_never_replaces_it(monkeypatch):
    monkeypatch.setenv("ARGUS_SANDBOX_IMAGE", "sha256:" + "c" * 64)
    assert sb.settings(ENVS)["image"] == "sha256:" + "c" * 64                    # the default image is overridden
    assert sb.settings({**ENVS, "environment": "argus"})["image"] == "sha256:" + "b" * 64   # the environment is not
    monkeypatch.setenv("ARGUS_SANDBOX_IMAGE_ARGUS", "sha256:" + "d" * 64)
    assert sb.settings({**ENVS, "environment": "argus"})["image"] == "sha256:" + "d" * 64   # only by its own variable


@pytest.mark.parametrize("name", ["nosuch", "ARGUS", "../argus", ""])
def test_an_unknown_environment_is_not_available(name, monkeypatch):
    monkeypatch.setenv("ARGUS_SANDBOX_IMAGE", "sha256:" + "c" * 64)   # a usable default image must not be used
    assert sb.settings({**ENVS, "environment": name})["image"] is None
    ok, why = sb.status({**ENVS, "environment": name})
    assert not ok and "unknown sandbox environment" in why


def test_an_environment_without_an_image_is_not_available():
    cfg = {**ENVS, "environments": {"argus": {"image": None}}, "environment": "argus"}
    ok, why = sb.status(cfg)
    assert not ok and "has no image configured" in why


def test_an_unknown_environment_never_starts_a_container(monkeypatch):
    def no_docker(*a, **k):
        raise AssertionError("docker must not be called")
    monkeypatch.setattr(sb.subprocess, "run", no_docker)
    monkeypatch.setattr(sb.subprocess, "Popen", no_docker)
    v = va.run_validation(spec("tests", environment="nosuch"), ".", ENVS)
    assert v["status"] == "blocked" and "unknown sandbox environment" in v["reason"]


def test_the_memo_version_is_unchanged_without_environments_and_follows_an_environments_image():
    assert sb.tool_version(ENVS) == "1:sha256:" + "a" * 64                       # what every existing run used
    v1 = sb.tool_version(ENVS, ["argus"])
    other = {**ENVS, "environments": {"argus": {"image": "sha256:" + "e" * 64}}}
    assert v1 != sb.tool_version(other, ["argus"]) and v1.endswith("argus=sha256:" + "b" * 64)
