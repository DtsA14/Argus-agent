"""SPEC_SANDBOX_SPLIT: the sandbox tests run in two serial xdist groups (`sandbox_a`: the tests defined in tests/test_draft.py;
`sandbox_b`: every other sandbox test), or in one (`sandbox`) with VERIFY_SANDBOX_GROUPS=1. Nothing here needs the Docker sandbox."""
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import conftest  # noqa: E402

MARK = "SANDBOX NOT " "AVAILABLE"         # built in two pieces: this module must not itself be taken for a sandbox module


def project(tmp_path, files):
    p = tmp_path / "proj"
    p.mkdir()
    shutil.copy(ROOT / "conftest.py", p / "conftest.py")
    for name, text in files.items():
        (p / name).write_text(text)
    return p


def run_pytest(p, *args, **env):
    e = {k: v for k, v in os.environ.items() if k != "VERIFY_SANDBOX_GROUPS"}
    return subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "-o", "addopts=", *args], cwd=p,
                          capture_output=True, text=True, timeout=180, env={**e, **env})


def names(tmp_path, files, **env):
    p = project(tmp_path, files)
    shutil.copy(ROOT / "tests" / "grouplist_plugin.py", p / "grouplist_plugin.py")
    out, nm = tmp_path / "groups.json", tmp_path / "names.json"
    r = run_pytest(p, "--collect-only", "-p", "grouplist_plugin", GROUPLIST_OUT=str(out), GROUPNAMES_OUT=str(nm),
                   PYTHONPATH=str(p), **env)
    assert r.returncode == 0, r.stdout + r.stderr
    return json.loads(nm.read_text())


FILES = {
    "test_draft.py": f'"""{MARK}"""\nimport pytest\n\n\n@pytest.fixture\ndef box():\n    return 1\n\n\ndef test_in_draft(box):\n    pass\n',
    "test_red.py": "from test_draft import box  # noqa: F401\n\n\ndef test_uses_the_fixture_of_draft(box):\n    pass\n",
    "test_own.py": f'"""{MARK}"""\n\n\ndef test_own_text():\n    pass\n',
    "test_plain.py": "def test_plain():\n    pass\n",
}


# ---- which group a test is in ------------------------------------------------------------------------------------------------


def test_two_groups_by_default_draft_alone_and_everything_else_in_b(tmp_path):
    g = names(tmp_path, FILES)
    assert g["test_draft.py::test_in_draft"] == "sandbox_a"
    assert g["test_red.py::test_uses_the_fixture_of_draft"] == "sandbox_b"      # grouped by a fixture of test_draft, but defined elsewhere
    assert g["test_own.py::test_own_text"] == "sandbox_b"
    assert g["test_plain.py::test_plain"] is None


def test_one_group_when_asked_for(tmp_path):
    g = names(tmp_path, FILES, VERIFY_SANDBOX_GROUPS="1")
    assert {g["test_draft.py::test_in_draft"], g["test_red.py::test_uses_the_fixture_of_draft"], g["test_own.py::test_own_text"]} == {"sandbox"}
    assert g["test_plain.py::test_plain"] is None


def test_two_is_the_same_as_the_default(tmp_path):
    (tmp_path / "x").mkdir()
    assert names(tmp_path, FILES, VERIFY_SANDBOX_GROUPS="2") == names(tmp_path / "x", FILES)


@pytest.mark.parametrize("value", ["", "0", "3", "two", "1 ", " 2", "01", "-1"])
def test_any_other_value_is_refused_not_guessed(value):
    with pytest.raises(pytest.UsageError):
        conftest.sandbox_group_count({"VERIFY_SANDBOX_GROUPS": value})


def test_the_count_defaults_to_two_and_reads_one_and_two():
    assert conftest.sandbox_group_count({}) == 2
    assert conftest.sandbox_group_count({"VERIFY_SANDBOX_GROUPS": "1"}) == 1
    assert conftest.sandbox_group_count({"VERIFY_SANDBOX_GROUPS": "2"}) == 2


def test_a_bad_value_stops_the_run_with_a_message_before_any_test(tmp_path):
    p = project(tmp_path, {"test_p.py": "def test_p():\n    pass\n"})
    r = run_pytest(p, VERIFY_SANDBOX_GROUPS="3")
    assert r.returncode != 0 and "VERIFY_SANDBOX_GROUPS" in (r.stdout + r.stderr) and "passed" not in r.stdout


def test_the_group_names_are_the_ones_the_spec_names():
    assert conftest.SANDBOX_GROUP == "sandbox"
    assert (conftest.GROUP_DRAFT, conftest.GROUP_REST) == ("sandbox_a", "sandbox_b")
    assert conftest.DRAFT_MODULE == "test_draft.py"


# ---- the real tests of the repository ----------------------------------------------------------------------------------------


def real_names(tmp_path, **env):
    out, nm = tmp_path / "g.json", tmp_path / "n.json"
    e = {k: v for k, v in os.environ.items() if k != "VERIFY_SANDBOX_GROUPS"}
    r = subprocess.run([sys.executable, "-m", "pytest", "--collect-only", "-q", "-p", "no:cacheprovider", "-o", "addopts=",
                        "-p", "grouplist_plugin", str(ROOT / "tests")], cwd=ROOT, capture_output=True, text=True, timeout=300,
                       env={**e, **env, "GROUPLIST_OUT": str(out), "GROUPNAMES_OUT": str(nm), "PYTHONPATH": str(ROOT / "tests")})
    assert r.returncode == 0, r.stdout[-800:] + r.stderr[-800:]
    return json.loads(nm.read_text())


def test_in_the_repository_only_the_tests_defined_in_test_draft_are_in_group_a(tmp_path):
    g = real_names(tmp_path)
    a = {n.split("::", 1)[0] for n, v in g.items() if v == "sandbox_a"}
    assert a == {"tests/test_draft.py"}
    assert {n for n in g if n.startswith("tests/test_draft.py::")} and all(
        g[n] == "sandbox_a" for n in g if n.startswith("tests/test_draft.py::"))
    for module in ("tests/test_red_caught.py", "tests/test_append_tests_sandbox.py"):       # they use fixtures or helpers of test_draft
        mine = {v for n, v in g.items() if n.startswith(module + "::") and v}
        assert mine == {"sandbox_b"}, module
    assert {v for v in g.values() if v} == {"sandbox_a", "sandbox_b"}


def test_the_machine_wide_modules_are_all_in_group_b(tmp_path):
    g = real_names(tmp_path)
    for module in ("test_codetask_crash.py", "test_auto_validation.py", "test_env_node.py", "test_env_from_base.py", "test_stage.py",
                   "test_stage_viewer.py", "test_sandbox.py", "test_acceptance_sandbox.py"):
        mine = {v for n, v in g.items() if n.startswith("tests/" + module + "::") and v}
        assert mine == {"sandbox_b"}, (module, mine)


def test_with_one_group_the_repository_has_one_sandbox_group(tmp_path):
    g = real_names(tmp_path, VERIFY_SANDBOX_GROUPS="1")
    assert {v for v in g.values() if v} == {"sandbox"}


# ---- what the log shows ------------------------------------------------------------------------------------------------------


class R:
    def __init__(self, nodeid, when, start, stop, keywords=None):
        self.nodeid, self.when, self.start, self.stop = nodeid, when, start, stop
        self.duration = stop - start
        self.keywords = keywords if keywords is not None else {"xdist_group": 1}


def test_wall_time_per_group_is_the_first_start_to_the_last_stop():
    reports = [R("t.py::a@sandbox_a", "setup", 100.0, 101.0), R("t.py::a@sandbox_a", "call", 101.0, 150.0),
               R("t.py::b@sandbox_a", "call", 151.0, 160.0),
               R("t.py::c@sandbox_b", "call", 102.0, 130.0), R("t.py::c@sandbox_b", "teardown", 130.0, 131.0),
               R("t.py::d", "call", 100.0, 500.0, {})]
    w = conftest.group_walls(reports)
    assert w == {"sandbox_a": {"seconds": 60.0, "tests": 2}, "sandbox_b": {"seconds": 29.0, "tests": 1}}


def test_a_node_id_with_an_at_sign_inside_is_not_taken_for_a_group():
    w = conftest.group_walls([R("t.py::x[@pytest.fixture]@sandbox_a", "call", 0.0, 1.0), R("t.py::y[@sandbox_a-1]", "call", 0.0, 9.0)])
    assert w == {"sandbox_a": {"seconds": 1.0, "tests": 1}}


def test_the_walls_line_names_each_group_and_the_setting():
    line = conftest.format_group_walls({"sandbox_a": {"seconds": 545.04, "tests": 300}, "sandbox_b": {"seconds": 580.0, "tests": 444}}, 2)
    assert line == "sandbox groups: 2 (VERIFY_SANDBOX_GROUPS); wall seconds: sandbox_a 545.0 (300 tests), sandbox_b 580.0 (444 tests)"
    assert conftest.format_group_walls({"sandbox": {"seconds": 1.5, "tests": 2}}, 1) == (
        "sandbox groups: 1 (VERIFY_SANDBOX_GROUPS); wall seconds: sandbox 1.5 (2 tests)")


def test_a_run_without_xdist_has_no_group_suffix_and_prints_no_walls_line_but_does_not_break(tmp_path):
    p = project(tmp_path, FILES)
    r = run_pytest(p)
    assert r.returncode == 0 and not [ln for ln in r.stdout.splitlines() if ln.startswith("sandbox groups:")], r.stdout


def test_the_group_walls_line_also_works_under_xdist_and_names_the_groups_the_workers_ran(tmp_path):
    p = project(tmp_path, FILES)
    r = run_pytest(p, "-n", "2", "--dist", "loadgroup")
    line = [ln for ln in r.stdout.splitlines() if ln.startswith("sandbox groups:")]
    assert r.returncode == 0 and len(line) == 1 and line[0].startswith("sandbox groups: 2 (VERIFY_SANDBOX_GROUPS)"), r.stdout
    assert "sandbox_a" in line[0] and "sandbox_b" in line[0], r.stdout


# ---- the per-test times for the observer ---------------------------------------------------------------------------------------


def test_every_test_call_is_timestamped_once_to_the_file_asked_for_even_under_xdist(tmp_path):
    p = project(tmp_path, FILES)
    out = tmp_path / "times.jsonl"
    r = run_pytest(p, "-n", "2", "--dist", "loadgroup", ARGUS_TEST_TIMES=str(out))
    assert r.returncode == 0, r.stdout
    rows = [json.loads(line) for line in out.read_text().splitlines()]
    assert sorted(x["nodeid"].split("@")[0] for x in rows) == sorted(
        ["test_draft.py::test_in_draft", "test_red.py::test_uses_the_fixture_of_draft", "test_own.py::test_own_text", "test_plain.py::test_plain"])
    assert all(x["stop"] >= x["start"] > 1e9 for x in rows)


def test_no_file_is_written_without_the_variable(tmp_path):
    p = project(tmp_path, FILES)
    r = run_pytest(p)
    assert r.returncode == 0 and not list(p.glob("*.jsonl")) and not list(tmp_path.glob("*.jsonl"))


# ---- the scripts ------------------------------------------------------------------------------------------------------------


@pytest.mark.parametrize("script", ["verify.sh", "precheck.sh"])
def test_no_script_turns_the_reordering_of_xdist_off(script):
    text = (ROOT / "scripts" / script).read_text(encoding="utf-8")
    assert "no-loadscope-reorder" not in text and "loadscope-reorder" not in text.replace("--no-loadscope-reorder", "")


def test_verify_sh_prints_the_setting_and_the_xdist_version_in_its_header():
    text = (ROOT / "scripts" / "verify.sh").read_text(encoding="utf-8")
    assert 'echo "VERIFY_SANDBOX_GROUPS=${VERIFY_SANDBOX_GROUPS:-2}' in text
    assert 'echo "xdist: $("$VENV/bin/pip" show pytest-xdist' in text
    assert text.index('echo "xdist:') < text.index('-m pytest')        # printed before the run, so the log has it even when the run dies


def test_the_precheck_prints_the_setting_it_runs_with():
    text = (ROOT / "scripts" / "precheck.sh").read_text(encoding="utf-8")
    assert 'echo "sandbox groups: ${VERIFY_SANDBOX_GROUPS:-2} (VERIFY_SANDBOX_GROUPS)"' in text
    assert text.index('echo "sandbox groups:') < text.index("exec ")


def test_requirements_pin_the_xdist_whose_scheduling_the_split_relies_on():
    req = (ROOT / "requirements.txt").read_text(encoding="utf-8")
    assert re.search(r"^pytest-xdist==\d", req, re.M)
