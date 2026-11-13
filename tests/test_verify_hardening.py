"""SPEC_VERIFY_HARDENING (docs/reviews/SPEC_VERIFY_HARDENING.md): the pre-check that picks and runs the tests of a change in under a minute
(scripts/precheck.sh, scripts/precheck_select.py), the durations that verify.sh records and the per-group totals conftest.py prints,
the opt-in fail-fast, and the grouping of a test by the fixtures it uses. Nothing here needs the Docker sandbox."""
import collections
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT))
import conftest  # noqa: E402
import precheck_select as ps  # noqa: E402

MARK = "SANDBOX NOT " "AVAILABLE"         # built in two pieces: this module must not itself be taken for a sandbox module
GIT_ENV = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@x", "GIT_COMMITTER_NAME": "t",
           "GIT_COMMITTER_EMAIL": "t@x", "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1"}
FIXED = ["tests/test_acceptance_sandbox.py", "tests/test_verification_names.py", "tests/test_verify_at.py",
         "tests/test_verify_provenance.py", "tests/test_xdist_groups.py"]
EXISTING = FIXED + ["tests/test_draft.py", "tests/test_draft_call_path.py", "tests/test_drafter.py",
                    "tests/test_drafter_form_fixes.py", "tests/test_other.py", "tests/test_changed_x.py"]


# ---- which tests the pre-check runs -------------------------------------------------------------------------------------

def test_the_fixed_set_is_always_selected_and_only_what_exists():
    assert ps.select([], EXISTING) == FIXED
    assert ps.select([], ["tests/test_other.py"]) == []                       # the fixed ones that do not exist are not invented


def test_a_touched_test_module_is_selected_if_it_exists():
    assert "tests/test_other.py" in ps.select(["tests/test_other.py"], EXISTING)
    assert "tests/test_gone.py" not in ps.select(["tests/test_gone.py"], EXISTING)


def test_a_touched_source_module_selects_the_tests_named_after_it():
    got = ps.select(["codetask/drafter.py"], EXISTING)
    assert "tests/test_drafter.py" in got and "tests/test_drafter_form_fixes.py" in got
    assert "tests/test_other.py" not in got and "tests/test_draft.py" not in got      # "drafter" is not a prefix of test_draft


def test_the_name_of_a_source_module_is_a_prefix_not_a_substring():
    got = ps.select(["acceptance/draft.py"], EXISTING)
    assert {"tests/test_draft.py", "tests/test_draft_call_path.py", "tests/test_drafter.py"} <= set(got)
    assert "tests/test_changed_x.py" not in got
    assert "tests/test_changed_x.py" not in ps.select(["acceptance/x.py"], EXISTING)


def test_nothing_else_selects_anything_and_the_result_is_sorted_and_unique():
    assert ps.select(["docs/x.md", "README.md", "scripts/a.sh", "docs/drafter.md", "notes/draft.txt"], EXISTING) == FIXED
    got = ps.select(["tests/test_other.py", "tests/test_other.py", "codetask/drafter.py"], EXISTING)
    assert got == sorted(set(got))


def repo_with_precheck(tmp_path):
    r = tmp_path / "repo"
    (r / "scripts").mkdir(parents=True)
    (r / "tests").mkdir()
    for name in ("precheck.sh", "precheck_select.py"):
        shutil.copy(ROOT / "scripts" / name, r / "scripts" / name)
    for t in EXISTING:
        (r / t).write_text("def test_x():\n    pass\n")
    subprocess.run(["git", "-C", str(tmp_path), "init", "-q", str(r)], check=True, env=GIT_ENV)
    subprocess.run(["git", "-C", str(r), "add", "-A"], check=True, env=GIT_ENV)
    subprocess.run(["git", "-C", str(r), "commit", "-qm", "base"], check=True, env=GIT_ENV, capture_output=True)
    return r


def printed(r, base="HEAD"):
    out = subprocess.run(["bash", "scripts/precheck.sh", base], cwd=r, capture_output=True, text=True, timeout=60,
                         env={**GIT_ENV, "PRECHECK_PRINT": "1"})
    assert out.returncode == 0, (out.stdout, out.stderr)
    return dict(line.split(": ", 1) for line in out.stdout.splitlines() if ": " in line)


def test_the_precheck_prints_what_it_would_run_for_the_changes_since_a_base(tmp_path):
    r = repo_with_precheck(tmp_path)
    (r / "tests" / "test_other.py").write_text("def test_x():\n    assert True\n")              # a tracked change
    (r / "tests" / "test_new.py").write_text("def test_n():\n    pass\n")                         # an untracked file
    (r / "codetask").mkdir()
    (r / "codetask" / "drafter.py").write_text("x = 1\n")                                         # an untracked source module
    p = printed(r)
    tests = p["tests"].split()
    assert "tests/test_other.py" in tests and "tests/test_new.py" in tests and "tests/test_drafter.py" in tests
    assert set(FIXED) <= set(tests)
    assert "-n 4 --dist loadgroup" in p["pytest"] and "-p no:cacheprovider" in p["pytest"]


def test_the_precheck_exports_the_pins_by_name_and_never_prints_their_values(tmp_path):
    r = repo_with_precheck(tmp_path)
    (r / ".sandbox_image").write_text("python@sha256:aaa\n")
    (r / ".sandbox_image_argus").write_text("sha256:bbb\n")
    (r / ".sandbox_image_ledger_py312_up2").write_text("sha256:ccc\n")
    (r / ".sandbox_image_argus.json").write_text('{"image": "sha256:ddd"}')                      # metadata, not a pin
    (r / ".sandbox_image_argus.check.json").write_text("{}")
    out = subprocess.run(["bash", "scripts/precheck.sh", "HEAD"], cwd=r, capture_output=True, text=True, timeout=60,
                         env={**GIT_ENV, "PRECHECK_PRINT": "1"})
    pins = dict(line.split(": ", 1) for line in out.stdout.splitlines() if ": " in line)["pins"].split()
    assert pins == ["ARGUS_SANDBOX_IMAGE", "ARGUS_SANDBOX_IMAGE_ARGUS", "ARGUS_SANDBOX_IMAGE_LEDGER_PY312_UP2"]
    assert "sha256" not in out.stdout and "python@" not in out.stdout


def test_the_precheck_needs_a_base_that_exists(tmp_path):
    r = repo_with_precheck(tmp_path)
    out = subprocess.run(["bash", "scripts/precheck.sh", "no-such-ref"], cwd=r, capture_output=True, text=True, timeout=60,
                         env={**GIT_ENV, "PRECHECK_PRINT": "1"})
    assert out.returncode == 2 and "the base no-such-ref does not exist" in out.stderr


# ---- the durations of a run ----------------------------------------------------------------------------------------------

Report = collections.namedtuple("Report", "when duration keywords")


def test_durations_are_summed_per_group_over_all_phases_and_tests_are_counted_by_their_call():
    reports = [Report("setup", 0.5, {"xdist_group": 1}), Report("call", 2.0, {"xdist_group": 1}),
               Report("teardown", 0.1, {"xdist_group": 1}),
               Report("setup", 0.1, {}), Report("call", 0.2, {}), Report("teardown", 0.0, {}),
               Report("call", 1.0, {})]
    t = conftest.group_totals(reports)
    assert t["sandbox"] == {"seconds": pytest.approx(2.6), "tests": 1}
    assert t["other"] == {"seconds": pytest.approx(1.3), "tests": 2}


def test_a_report_without_a_duration_or_keywords_is_counted_as_other_and_never_breaks_the_summary():
    t = conftest.group_totals([object(), Report("call", None, None), Report("call", 0.3, {})])
    assert t["sandbox"] == {"seconds": 0.0, "tests": 0}
    assert t["other"]["tests"] == 2 and t["other"]["seconds"] == pytest.approx(0.3)


def test_the_totals_line_names_both_groups_and_what_it_adds_up():
    line = conftest.format_group_totals({"sandbox": {"seconds": 612.34, "tests": 735}, "other": {"seconds": 401.0, "tests": 3377}})
    assert line == ("durations by group (seconds, setup+call+teardown): sandbox 612.3 (735 tests), other 401.0 (3377 tests)")


def project(tmp_path, files):
    p = tmp_path / "proj"
    p.mkdir()
    shutil.copy(ROOT / "conftest.py", p / "conftest.py")
    for name, text in files.items():
        (p / name).write_text(text)
    return p


def run_pytest(p, *args, **env):
    return subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "-o", "addopts=", *args], cwd=p,
                          capture_output=True, text=True, timeout=120, env={**os.environ, **env})


def test_a_run_ends_with_the_totals_of_the_sandbox_group_and_of_the_rest(tmp_path):
    p = project(tmp_path, {
        "test_a.py": f'"""{MARK}"""\nimport time\n\n\ndef test_a():\n    time.sleep(0.3)\n',
        "test_b.py": "def test_b():\n    pass\n\n\ndef test_c():\n    pass\n",
        "test_d.py": "def test_d():\n    assert False\n"})                 # a failing test is counted too
    out = run_pytest(p)
    assert out.returncode == 1, out.stdout
    line = [ln for ln in out.stdout.splitlines() if ln.startswith("durations by group")]
    assert len(line) == 1 and "sandbox 0." in line[0] and "(1 tests)" in line[0] and "other 0." in line[0] and "(3 tests)" in line[0], out.stdout


def test_verify_sh_records_every_duration_of_a_second_or_more_not_the_top_25():
    text = (ROOT / "scripts" / "verify.sh").read_text()
    assert "--durations=0 --durations-min=1.0" in text and "--durations=25" not in text


def test_fail_fast_is_opt_in_and_says_so_in_the_log():
    text = (ROOT / "scripts" / "verify.sh").read_text()
    assert text.count("VERIFY_MAXFAIL") == 3                                  # the test, the argument and the log line
    assert 'if [ -n "${VERIFY_MAXFAIL:-}" ]' in text and '--maxfail="$VERIFY_MAXFAIL"' in text
    assert "maxfail: $VERIFY_MAXFAIL" in text and "not a full run" in text
    assert text.index('if [ -n "${VERIFY_MAXFAIL:-}" ]') < text.index("-m pytest") < text.index('"${PYTEST_EXTRA[@]}"')   # the argument reaches pytest


# ---- grouping by the fixtures a test uses ----------------------------------------------------------------------------------

GROUPS = {
    "test_a.py": f'"""{MARK}"""\nimport pytest\n\n\n@pytest.fixture\ndef box():\n    return 1\n\n\n'
                 "def test_uses_box(box):\n    pass\n\n\ndef test_plain_in_a_sandbox_module():\n    pass\n",
    "test_b.py": "from test_a import box  # noqa: F401\n\n\ndef test_uses_the_imported_fixture(box):\n    pass\n\n\n"
                 "def test_b_plain():\n    pass\n",
    "test_c.py": "import pytest\nfrom test_a import box  # noqa: F401\n\n\n@pytest.fixture\ndef dep(box):\n    return box\n\n\n"
                 "def test_uses_a_fixture_that_needs_box(dep):\n    pass\n\n\n@pytest.fixture\ndef alone():\n    return 0\n\n\n"
                 "def test_uses_a_fixture_of_its_own(alone):\n    pass\n",
}


def grouped(tmp_path, files):
    p = project(tmp_path, files)
    shutil.copy(ROOT / "tests" / "grouplist_plugin.py", p / "grouplist_plugin.py")
    out = tmp_path / "groups.json"
    r = run_pytest(p, "--collect-only", "-p", "grouplist_plugin", GROUPLIST_OUT=str(out), PYTHONPATH=str(p))
    assert r.returncode == 0, r.stdout + r.stderr
    return json.loads(out.read_text())


def test_a_test_is_grouped_when_its_module_says_so_or_a_fixture_it_needs_comes_from_a_file_that_does(tmp_path):
    g = grouped(tmp_path, GROUPS)
    assert g["test_a.py::test_uses_box"] is True
    assert g["test_a.py::test_plain_in_a_sandbox_module"] is True              # the module itself says so
    assert g["test_b.py::test_uses_the_imported_fixture"] is True              # the fixture is imported: the module's text does not say so
    assert g["test_b.py::test_b_plain"] is False
    assert g["test_c.py::test_uses_a_fixture_that_needs_box"] is True          # through another fixture
    assert g["test_c.py::test_uses_a_fixture_of_its_own"] is False


def test_a_fixture_of_the_conftest_is_not_a_sandbox_fixture_unless_it_comes_from_a_marked_file(tmp_path):
    files = {"test_d.py": "def test_d(shared):\n    pass\n"}
    p = project(tmp_path, files)
    (p / "conftest.py").write_text((ROOT / "conftest.py").read_text() + "\n\n@pytest.fixture\ndef shared():\n    return 1\n")
    shutil.copy(ROOT / "tests" / "grouplist_plugin.py", p / "grouplist_plugin.py")
    out = tmp_path / "g.json"
    r = run_pytest(p, "--collect-only", "-p", "grouplist_plugin", GROUPLIST_OUT=str(out), PYTHONPATH=str(p))
    assert r.returncode == 0, r.stdout + r.stderr
    assert json.loads(out.read_text()) == {"test_d.py::test_d": False}


def test_the_closure_of_a_test_without_fixtures_is_empty_and_never_breaks_the_hook(tmp_path):
    assert grouped(tmp_path, {"test_e.py": "def test_e():\n    pass\n"}) == {"test_e.py::test_e": False}
