"""SPEC_VF_O1_CANARY_NONCE: a pytest validation is trusted only with the harness's record behind the run's nonce. Without Docker: the
harness's own script (`va.GREEN`) is run in a subprocess (the host's pytest, rootdir moved to a temp workspace), so the mapping and the
mutants exercise the real script; the Docker runs are in tests/test_vf_forger.py and tests/test_pytest_sandbox.py."""
import json
import os
import resource
import shutil
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

from acceptance import validation as va
from green_helpers import CANARY_OK, NONCE, judge, record, recorded, with_record

ROOT = Path(__file__).resolve().parent.parent
FORGERS = ROOT / "fixtures" / "forgers"


def spec(*targets, **extra):
    return {"id": "t", "executable": "python", "args": ["-m", "pytest", *targets], "timeout_s": 60, "min_tests": 0,
            "max_skipped": 99, "must_pass": [], **extra}


def limits():
    resource.setrlimit(resource.RLIMIT_AS, (3 * 1024 ** 3, 3 * 1024 ** 3))


def run_green(ws, *targets, env=None, script=None):
    """The harness's script on `ws`, like the sandbox runs it (rootdir moved from /workspace to ws). Returns a run result."""
    fixed = [str(ws) if a == "/workspace" else a for a in va.PYTEST_FIXED]
    e = {k: v for k, v in os.environ.items() if not k.startswith("PYTEST_")}
    e.update(env or {})
    p = subprocess.run([sys.executable, "-I", "-B", "-c", script or va.GREEN, NONCE, json.dumps(fixed), *targets], cwd=ws, env=e,
                       capture_output=True, text=True, timeout=120, stdin=subprocess.DEVNULL, preexec_fn=limits)
    return {"exit_code": p.returncode, "stdout": p.stdout, "stderr": p.stderr, "timed_out": False, "killed": False,
            "output_limit_exceeded": False, "truncated": False}


def project(tmp_path, body, conftest=""):
    ws = tmp_path / "ws"
    (ws / "tests").mkdir(parents=True)
    (ws / "tests" / "test_x.py").write_text(textwrap.dedent(body))
    (ws / "conftest.py").write_text(textwrap.dedent(conftest))
    return ws


def forger(tmp_path, name):
    ws = tmp_path / "ws"
    shutil.copytree(FORGERS / name, ws)
    return ws


def trusted(v):
    return v["evidence"]["record"] is True and v["evidence"]["canary"] == "ok" and "not trusted" not in v["reason"]


# ---- the honest cases: the record agrees with the text, whatever the statuses -----------------------------------------------

MIX = '''
import pytest

def test_ok(): assert 1 == 1
def test_red(): assert 1 == 2
@pytest.mark.skip(reason="x")
def test_skip(): pass
@pytest.mark.xfail(reason="x")
def test_xfail(): assert 1 == 2
@pytest.mark.xfail(reason="x")
def test_xpass_loose(): assert 1 == 1
@pytest.mark.xfail(strict=True, reason="x")
def test_xpass_strict(): assert 1 == 1
@pytest.mark.xfail(run=False, reason="x")
def test_xfail_not_run(): assert 1 == 2
def test_imperative_xfail(): pytest.xfail("late")
def test_imperative_skip(): pytest.skip("late")

@pytest.fixture
def bad_setup(): raise RuntimeError("setup")
def test_setup_error(bad_setup): pass

@pytest.fixture
def bad_teardown():
    yield
    raise RuntimeError("teardown")
def test_teardown_error_after_pass(bad_teardown): pass
def test_teardown_error_after_fail(bad_teardown): assert 1 == 2

@pytest.fixture
def skip_teardown():
    yield
    pytest.skip("late")
def test_pass_then_teardown_skip(skip_teardown): pass

@pytest.fixture
def skip_setup(): pytest.skip("early")
def test_setup_skip(skip_setup): pass

@pytest.mark.parametrize("a", ["x y", "p::q", "z PASSED", "é"])
def test_param(a): assert a

class TestC:
    def test_in_class(self): pass
'''


def test_every_status_of_an_honest_run_agrees_between_the_record_and_the_text(tmp_path):
    ws = project(tmp_path, MIX)
    r = run_green(ws, "tests/test_x.py")
    v = va.judge_result(spec("tests/test_x.py"), r, nonce=NONCE)
    assert trusted(v), (v["reason"], v["evidence"].get("record_problems"))
    text = va.parse_pytest(va.split_record(r["stdout"], NONCE)[0])["tests"]
    assert set(text.values()) == {"ok", "FAIL", "ERROR", "skipped", "expected failure", "unexpected success"}
    assert text["tests/test_x.py::test_pass_then_teardown_skip"] == "ok"            # the first report wins a tie


def test_a_deselected_node_is_missing_on_both_sides(tmp_path):
    ws = project(tmp_path, MIX)
    r = run_green(ws, "tests/test_x.py", "-k", "param or test_ok")
    v = va.judge_result(spec("tests/test_x.py", "-k", "param"), r, nonce=NONCE)
    assert trusted(v), v["evidence"].get("record_problems")


def test_a_subtest_that_is_skipped_does_not_make_the_record_disagree(tmp_path):
    pytest.importorskip("pytest", minversion="9.0")
    ws = project(tmp_path, '''
        def test_sub(subtests):
            with subtests.test("a"):
                import pytest
                pytest.skip("no")
            with subtests.test("b"):
                assert 1 == 1
    ''')
    r = run_green(ws, "tests/test_x.py")
    v = va.judge_result(spec("tests/test_x.py"), r, nonce=NONCE)
    assert trusted(v), (v["reason"], v["evidence"].get("record_problems"))


def test_an_honest_green_run_passes_with_the_old_evidence_and_no_record_line_in_the_output(tmp_path):
    ws = project(tmp_path, "def test_a(): assert 1 == 1\ndef test_b(): assert 2 == 2\n")
    r = run_green(ws, "tests/test_x.py")
    v = va.judge_result(spec("tests/test_x.py"), r, nonce=NONCE)
    assert v["status"] == "pass", v["reason"]
    assert NONCE not in v["evidence"]["output_tail"] and "ARGUS-GREEN" not in v["evidence"]["output_tail"]
    assert "canary" not in v["evidence"]["output_tail"] and "failed" not in v["evidence"]["output_tail"]   # session 2 prints nothing
    assert v["evidence"]["output_tail"].endswith("====\n") and not v["evidence"]["output_tail"].endswith("\n\n")   # the script's blank line is gone
    assert v["evidence"]["tests_run"] == 2 and v["evidence"]["consistent"] is True


def test_code_that_replaces_argv_environment_or_stdout_does_not_break_an_honest_run(tmp_path):
    ws = project(tmp_path, '''
        import os, sys
        def test_argv0():
            assert sys.argv[0].endswith("__main__.py")
        def test_env():
            os.environ["PYTEST_ADDOPTS"] = "-x --nope"
            os.environ["PYTEST_PLUGINS"] = "does_not_exist"
        def test_stdout():
            sys.stdout.write("noise without a newline")
    ''')
    v = va.judge_result(spec("tests/test_x.py"), run_green(ws, "tests/test_x.py"), nonce=NONCE)
    assert v["status"] == "pass" and trusted(v), (v["reason"], v["evidence"].get("record_problems"))


def test_warnings_as_errors_in_the_project_do_not_reach_the_canary(tmp_path):
    ws = project(tmp_path, "def test_a(): assert 1 == 1\n")
    (ws / "pytest.ini").write_text("[pytest]\nfilterwarnings = error\n")
    v = va.judge_result(spec("tests/test_x.py"), run_green(ws, "tests/test_x.py"), nonce=NONCE)
    assert v["status"] == "pass" and trusted(v), v["reason"]


def test_the_record_is_the_same_size_for_one_test_and_for_five_thousand(tmp_path):
    sizes = []
    for k, n in enumerate((1, 5000)):
        ws = project(tmp_path / str(k), f"import pytest\n@pytest.mark.parametrize('i', range({n}))\ndef test_p(i): pass\n")
        out = run_green(ws, "tests/test_x.py")["stdout"]
        sizes.append(max(len(l) for l in out.splitlines() if l.startswith(NONCE)))
    assert max(sizes) < 600 and abs(sizes[0] - sizes[1]) < 50, sizes


# ---- what is refused ------------------------------------------------------------------------------------------------------

def test_the_pipe_forger_leaves_no_record_and_the_validation_fails(tmp_path):
    r = run_green(forger(tmp_path, "pytest_pipe_forger"), "tests/test_new.py")
    assert "1 passed" in r["stdout"] and r["exit_code"] == 0                         # the forgery works as a text
    v = va.judge_result(spec("tests/test_new.py"), r, nonce=NONCE)
    assert v["status"] == "fail" and v["evidence"]["record"] is False and "not trusted" in v["reason"]


def test_the_noop_forger_is_caught_by_the_canary(tmp_path):
    r = run_green(forger(tmp_path, "pytest_noop_forger"), "tests/test_new.py")
    v = va.judge_result(spec("tests/test_new.py"), r, nonce=NONCE)
    assert v["status"] == "fail" and v["evidence"]["record"] is True and v["evidence"]["canary"] != "ok"


@pytest.mark.xfail(strict=True, reason="VF O1 does not promise this: a forger scoped to the contract's tests by path (F1)")
def test_known_gap_f1_path_scoped_forger(tmp_path):
    v = va.judge_result(spec("tests/test_new.py"), run_green(forger(tmp_path, "pytest_path_forger_f1"), "tests/test_new.py"), nonce=NONCE)
    assert v["status"] != "pass"


@pytest.mark.xfail(strict=True, reason="VF O1 does not promise this: a forger restored at the end of session 1 (F2)")
def test_known_gap_f2_session_scoped_forger(tmp_path):
    v = va.judge_result(spec("tests/test_new.py"), run_green(forger(tmp_path, "pytest_session_forger_f2"), "tests/test_new.py"), nonce=NONCE)
    assert v["status"] != "pass"


@pytest.mark.xfail(strict=True, reason="VF O1 does not promise this: a plugin on session 1's Config that flips failures (F3)")
def test_known_gap_f3_config_scoped_forger(tmp_path):
    v = va.judge_result(spec("tests/test_new.py"), run_green(forger(tmp_path, "pytest_config_forger_f3"), "tests/test_new.py"), nonce=NONCE)
    assert v["status"] != "pass"


# ---- the judgement, on crafted records ------------------------------------------------------------------------------------

PYTEST_OK = ("collecting ... collected 2 items\n\ntests/t.py::test_a PASSED\ntests/t.py::test_b PASSED\n\n"
             "======== 2 passed in 0.01s ========\n")
RUN = {"exit_code": 0, "stdout": PYTEST_OK, "stderr": "", "timed_out": False, "killed": False, "output_limit_exceeded": False,
       "truncated": False}


def verdict(stdout, nonce=NONCE, **extra):
    return va.judge_result(spec("tests/t.py"), {**RUN, "stdout": stdout, **extra}, nonce=nonce)


def test_a_crafted_agreeing_record_passes():
    v = verdict(with_record(PYTEST_OK))
    assert v["status"] == "pass" and trusted(v), v["reason"]


@pytest.mark.parametrize("name, stdout", [
    ("no record", PYTEST_OK),
    ("two records", with_record(PYTEST_OK) + record(PYTEST_OK) + "\n"),
    ("record behind another nonce", PYTEST_OK + "\n" + record(PYTEST_OK).replace(NONCE, "ARGUS-GREEN-" + "1" * 32 + ":") + "\n"),
    ("record that is not json", PYTEST_OK + "\n" + NONCE + "{nope\n"),
    ("record that is not an object", PYTEST_OK + "\n" + NONCE + "[1]\n"),
    ("record without a sha", PYTEST_OK + "\n" + NONCE + json.dumps({"rc": 0}) + "\n"),
])
def test_a_missing_or_malformed_record_fails_the_validation(name, stdout):
    v = verdict(stdout)
    assert v["status"] == "fail" and v["evidence"]["record"] is False, name
    assert "validation not trusted" in v["reason"]


@pytest.mark.parametrize("over", [
    {"canary": {**CANARY_OK, "test_fail": "ok"}},
    {"canary": {**CANARY_OK, "test_error": "FAIL:ValueError"}},
    {"canary": {k: v for k, v in CANARY_OK.items() if k != "test_pass"}},
    {"canary": {**CANARY_OK, "test_extra": "ok"}},
    {"canary": {}},
    {"canary_rc": 0},
    {"canary_rc": None},
    {"canary_error": "OSError"},
])
def test_a_canary_that_did_not_end_as_it_must_fails_the_validation(over):
    v = verdict(with_record(PYTEST_OK, **over))
    assert v["status"] == "fail" and v["evidence"]["canary"] != "ok" and "validation not trusted" in v["reason"]


def test_a_record_that_disagrees_with_the_report_fails_the_validation():
    assert verdict(with_record(PYTEST_OK, rc=1))["status"] == "fail"                                       # rc: exit code is 0
    other = PYTEST_OK.replace("test_b PASSED", "test_b FAILED").replace("2 passed", "1 passed, 1 failed")
    v = verdict(PYTEST_OK + "\n" + record(other, rc=0) + "\n")                                             # sha of other text
    assert v["status"] == "fail" and "validation not trusted" in v["reason"]
    v = verdict(with_record(PYTEST_OK, counts={"ok": 1}))
    assert v["status"] == "fail"
    v = verdict(with_record(PYTEST_OK, sha="0" * 64))
    assert v["status"] == "fail"


def test_the_reason_the_agent_reads_does_not_say_what_to_avoid_and_the_evidence_does():
    v = verdict(with_record(PYTEST_OK, canary={**CANARY_OK, "test_fail": "ok"}))
    assert v["reason"].count("validation not trusted") == 1 and "canary" not in v["reason"] and "sha" not in v["reason"]
    assert any("canary" in d for d in v["evidence"]["record_problems"])
    codes = {verdict(PYTEST_OK)["reason"], verdict(with_record(PYTEST_OK, canary_rc=0))["reason"],
             verdict(with_record(PYTEST_OK, rc=1))["reason"], verdict(with_record(PYTEST_OK, sha="0" * 64))["reason"]}
    assert len(codes) == 4                                                                                 # a code per rule, to be counted


def test_without_a_nonce_a_pytest_validation_is_never_trusted():
    v = va.judge_result(spec("tests/t.py"), recorded(RUN))
    assert v["status"] == "fail" and v["evidence"]["record"] is False


def test_the_record_line_is_removed_before_the_text_is_read():
    out = with_record(PYTEST_OK)
    text, rec, n = va.split_record(out, NONCE)
    assert NONCE not in text and n == 1 and rec["rc"] == 0
    assert va.parse_pytest(text) == va.parse_pytest(PYTEST_OK)


def test_a_timeout_still_fails_for_its_own_reason_first():
    v = verdict(PYTEST_OK, timed_out=True)
    assert v["status"] == "fail" and v["reason"].startswith("timed out")


def test_the_script_and_the_host_hash_the_same_way(tmp_path):
    ws = project(tmp_path, MIX)
    r = run_green(ws, "tests/test_x.py")
    text, rec, _ = va.split_record(r["stdout"], NONCE)
    assert rec["sha"] == va.tests_sha(va.parse_pytest(text)["tests"])


def test_the_runner_is_run_by_the_harness_never_named_by_the_contract():
    assert va.argv(spec("tests"), NONCE)[:4] == ["python3", "-I", "-B", "-c"]
    assert va.validate_command("python", ["-m", "pytest", "-c", "x.ini", "tests"])                          # still refused


# ---- review of the first implementation: node ids, the second session's surroundings, the record's line ---------------------------------

YAML_CONFTEST = """
import pytest

def pytest_collect_file(parent, file_path):
    if file_path.suffix == ".yaml" and file_path.name.startswith("test"):
        return YamlFile.from_parent(parent, path=file_path)

class YamlFile(pytest.File):
    def collect(self):
        yield YamlItem.from_parent(self, name="spec.case_one")

class YamlItem(pytest.Item):
    def runtest(self): pass
    def reportinfo(self): return self.path, 0, "spec.case_one"
"""


def test_a_node_the_terminal_prints_with_colons_instead_of_dots_agrees_with_the_record(tmp_path):
    ws = project(tmp_path, "def test_a(): pass\n", YAML_CONFTEST)
    (ws / "tests" / "test_y.yaml").write_text("x: 1\n")
    r = run_green(ws, "tests")
    text = va.split_record(r["stdout"], NONCE)[0]
    assert "tests/test_y.yaml::spec::case_one PASSED" in text                    # what pytest prints is not the nodeid
    v = va.judge_result(spec("tests"), r, nonce=NONCE)
    assert trusted(v), (v["reason"], v["evidence"].get("record_problems"))


def hostile_script(base):
    """The script with its canary directory under `base` (a test's own directory instead of /tmp)."""
    assert va.GREEN.count('dir="/tmp"') == 1
    return va.GREEN.replace('dir="/tmp"', f'dir={str(base)!r}')


def test_an_ini_and_a_conftest_above_the_canary_directory_do_not_reach_the_canary(tmp_path):
    base = tmp_path / "tmpbase"
    base.mkdir()
    (base / "pytest.ini").write_text("[pytest]\nrequired_plugins = no-such-plugin-xyz\naddopts = --no-such-option\n")
    (base / "conftest.py").write_text("raise RuntimeError('a conftest above the canary')\n")
    ws = project(tmp_path / "p", "def test_a(): pass\n")
    r = run_green(ws, "tests/test_x.py", script=hostile_script(base))
    v = va.judge_result(spec("tests/test_x.py"), r, nonce=NONCE)
    assert v["status"] == "pass" and trusted(v), (v["reason"], v["evidence"].get("record_problems"))


def test_the_canary_directory_is_removed_when_the_script_is_done(tmp_path):
    base = tmp_path / "tmpbase"
    base.mkdir()
    ws = project(tmp_path / "p", "def test_a(): pass\n")
    assert run_green(ws, "tests/test_x.py", script=hostile_script(base))["exit_code"] == 0
    assert list(base.iterdir()) == []


def test_a_canary_that_cannot_be_written_is_reported_as_such_and_fails(tmp_path):
    ws = project(tmp_path / "p", "def test_a(): pass\n")
    r = run_green(ws, "tests/test_x.py", script=hostile_script(tmp_path / "does-not-exist"))
    v = va.judge_result(spec("tests/test_x.py"), r, nonce=NONCE)
    assert v["status"] == "fail" and v["evidence"]["record"] is True and "not trusted" in v["reason"]
    assert any("could not write" in d for d in v["evidence"]["record_problems"])


def test_a_project_that_leaves_the_temp_dir_and_the_path_broken_still_gets_its_canary(tmp_path):
    ws = project(tmp_path / "p", """
        import sys, tempfile
        def test_breaks_things():
            tempfile.tempdir = "/nonexistent-temp-dir"
            sys.path[:] = []
    """)
    v = va.judge_result(spec("tests/test_x.py"), run_green(ws, "tests/test_x.py"), nonce=NONCE)
    assert v["status"] == "pass" and trusted(v), (v["reason"], v["evidence"].get("record_problems"))


def test_output_without_a_newline_right_before_the_record_does_not_hide_it(tmp_path):
    ws = project(tmp_path / "p", "def test_a(): pass\n", "import os, sys\n\ndef pytest_unconfigure(config):\n    sys.stdout.flush()\n    os.write(1, b'XYZ')\n")
    r = run_green(ws, "tests/test_x.py")
    assert "XYZ\n" + NONCE in r["stdout"]
    v = va.judge_result(spec("tests/test_x.py"), r, nonce=NONCE)
    assert v["status"] == "pass" and trusted(v), (v["reason"], v["evidence"].get("record_problems"))


@pytest.mark.parametrize("over", [{"rc": True}, {"rc": 1.0}, {"canary_rc": True}, {"canary_rc": 1.0}])
def test_a_record_whose_numbers_are_not_plain_integers_is_not_read(over):
    rec = json.loads(record(PYTEST_OK)[len(NONCE):])
    rec.update(over)
    out = PYTEST_OK + "\n" + NONCE + json.dumps(rec) + "\n"
    v = verdict(out, exit_code=1) if "rc" in over else verdict(out)
    assert v["status"] == "fail" and "validation not trusted" in v["reason"]


def test_a_record_without_its_canary_is_refused_not_raised():
    rec = json.loads(record(PYTEST_OK)[len(NONCE):])
    del rec["canary"]
    v = verdict(PYTEST_OK + "\n" + NONCE + json.dumps(rec) + "\n")
    assert v["status"] == "fail" and v["evidence"]["record"] is False


def test_each_run_gets_a_nonce_of_its_own_and_a_record_behind_another_is_not_read(monkeypatch):
    seen = []

    def fake(argv, **kw):
        seen.append(argv[5])
        return {**RUN, "stdout": with_record(PYTEST_OK, nonce=argv[5] if len(seen) == 1 else "ARGUS-GREEN-" + "9" * 32 + ":")}

    monkeypatch.setattr(va.sb, "run_command", fake)
    first = va.run_validation(spec("tests/t.py"), ".", {})
    second = va.run_validation(spec("tests/t.py"), ".", {})
    assert first["status"] == "pass" and second["status"] == "fail" and seen[0] != seen[1] and seen[0].startswith("ARGUS-GREEN-")


def test_an_honest_run_keeps_its_old_reason_and_evidence_and_gains_three_keys():
    import test_pytest_validation as tpv
    nodes = ["tests/test_isolation.py::test_no_network", "tests/test_isolation.py::test_workspace_is_read_only",
             "tests/test_isolation.py::test_runs_as_nobody"]
    v = judge(tpv.spec("tests/test_isolation.py", must=nodes, min_tests=3), tpv.result("isolation"))
    assert v["status"] == "pass" and v["reason"] == "" and v["layer"] == "C" and v["id"] == "validation:t"
    assert set(v["evidence"]) == {"argv", "exit_code", "timed_out", "killed", "cleanup_failed", "output_limit_exceeded", "truncated", "tests_run",
                                  "outcome", "skipped", "failures", "errors", "must_pass", "output_tail", "runner", "consistent", "collected",
                                  "deselected", "stderr_tail", "failed_nodes", "record", "canary", "record_problems"}


@pytest.mark.xfail(strict=True, reason="VF O1 does not promise this: a forger that reads the run's nonce from the interpreter's argv and writes "
                   "a report and an agreeing record (accepted limit, SPEC_VF_O1_CANARY_NONCE section 2)")
def test_known_gap_f6_a_forger_that_reads_the_nonce(tmp_path):
    v = va.judge_result(spec("tests/test_new.py"), run_green(forger(tmp_path, "pytest_nonce_reader_forger"), "tests/test_new.py"), nonce=NONCE)
    assert v["status"] != "pass"


def test_pytest_run_gives_the_text_without_the_record_and_the_record(monkeypatch):
    seen = {}

    def fake(argv, **kw):
        seen["argv"] = argv
        return {**RUN, "stdout": with_record(PYTEST_OK, nonce=argv[5])}

    monkeypatch.setattr(va.sb, "run_command", fake)
    r, rec = va.pytest_run(spec("tests/t.py"), ".", {})
    assert r["stdout"] == PYTEST_OK and "ARGUS-GREEN" not in r["stdout"] and rec["rc"] == 0 and rec["canary"] == va.CANARY_WANTED
    assert seen["argv"][5].startswith("ARGUS-GREEN-")
