"""SPEC_VITEST_FULL_REGRESSION: a vitest draft names every existing test file of the job's commit in a validation, so the
whole old suite must pass at the baseline, the reference and the agent's run; a file vitest would take for a test but
the harness cannot run is refused. One test (or group) per guarantee of section 3, numbered as there. G5 and G6 run in
the pwa_node22 sandbox; without Docker and that image they are skipped with "SANDBOX NOT AVAILABLE", which
scripts/verify.sh does not count as passing."""
import copy
import os
import subprocess
from pathlib import Path

import pytest

from acceptance import draft as dr
from acceptance import intake
from acceptance.workspace import snapshot
from codetask import drafter as cdr
from runner import load_config
from tools import sandbox as sb

SUM = "export const sum = (a, b) => a + b\n"
CLAMPED = "export const sum = (a, b) => Math.max(0, a + b)\n"
OLD_ADDS = "import { expect, test } from 'vitest'\nimport { sum } from './sum.js'\n\ntest('adds', () => {\n" \
           "  expect(sum(1, 2)).toBe(3)\n})\n"
OLD_NEG = "import { expect, test } from 'vitest'\nimport { sum } from './sum.js'\n\ntest('keeps a negative sum', () => {\n" \
          "  expect(sum(-1, -1)).toBe(-2)\n})\n"
NEW_CLAMP = "import { expect, test } from 'vitest'\nimport { sum } from './sum.js'\n\ntest('floors at 0', () => {\n" \
            "  expect(sum(-1, -2)).toBe(0)\n})\n"
OLD_BAD = "import { expect, test } from 'vitest'\nimport { sum } from './sum.js'\n\ntest('is wrong already', () => {\n" \
          "  expect(sum(1, 1)).toBe(3)\n})\n"
BASE = {"src/sum.js": SUM, "src/sum.test.js": OLD_ADDS, "src/neg.test.js": OLD_NEG}


def git(repo, *args):
    env = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@x", "GIT_COMMITTER_NAME": "t",
           "GIT_COMMITTER_EMAIL": "t@x", "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1"}
    return subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, env=env, text=True).stdout


def vspec(id, files, must, min_tests=1):
    return {"id": id, "executable": "vitest", "args": ["run", *files], "timeout_s": 120, "min_tests": min_tests,
            "max_skipped": 0, "must_pass": must, "environment": "pwa_node22"}


def draft(validations):
    return {"draft_version": 1, "base": "sums",
            "plan": {"files": ["src/sum.js"], "steps": ["floor the sum at 0"], "risks": ["none"]},
            "contract": {"scope": {"writable": ["src/sum.js"], "protected": ["src/*.test.js"]},
                         "validation": validations},
            "new_tests": [{"path": "src/clamp.test.js", "content": NEW_CLAMP}], "unverifiable": []}


TARGET = vspec("target", ["src/clamp.test.js"], ["src/clamp.test.js::floors at 0"])
ALL_OLD = vspec("regression", ["src/sum.test.js", "src/neg.test.js"], ["src/sum.test.js::adds"], min_tests=2)
ONLY_ADDS = vspec("regression", ["src/sum.test.js"], ["src/sum.test.js::adds"])
ONLY_NEG = vspec("more", ["src/neg.test.js"], ["src/neg.test.js::keeps a negative sum"])


def make_root(tmp_path, files=BASE):
    repo = tmp_path / "sums_repo"
    for p, text in files.items():
        (repo / p).parent.mkdir(parents=True, exist_ok=True)
        (repo / p).write_text(text)
    git(tmp_path, "init", "-q", str(repo))
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "base")
    proj = tmp_path / "proj"
    proj.mkdir()
    intake.intake(repo, "HEAD", "sums", root=proj)
    return proj, repo


def statics(root, d):
    c = dr.build_contract(d, task="t", workspace="fixtures/repos/t", issue="i", max_usd=0.5, max_iterations=2)
    return dr.static_problems(d, c, snapshot(root / "fixtures" / "repos" / "sums", skip_cache=True))


def f1(problems):
    return [p for p in problems if "is in no validation" in p or "cannot be run by the harness" in p]


# ---- G1-G4, G7: the check, without the sandbox ---------------------------------------------------------------------

def test_g1_a_vitest_draft_that_leaves_an_existing_test_file_out_is_refused_naming_it(tmp_path):
    root, _ = make_root(tmp_path)
    problems = statics(root, draft([TARGET, ONLY_ADDS]))
    assert f1(problems) == ["existing test file src/neg.test.js is in no validation (a vitest draft runs every "
                            "existing test file)"]


def test_g2_every_existing_file_named_across_two_validations_is_not_refused(tmp_path):
    root, _ = make_root(tmp_path)
    assert statics(root, draft([TARGET, ONLY_ADDS, ONLY_NEG])) == []
    assert statics(root, draft([TARGET, ALL_OLD])) == []


def test_g3_the_drafts_new_test_is_not_an_existing_file(tmp_path):
    """The new test is in the task's files but not in the intake; even if the check were given it, it is not 'old'."""
    root, _ = make_root(tmp_path)
    d = draft([TARGET, ALL_OLD])
    c = dr.build_contract(d, task="t", workspace="fixtures/repos/t", issue="i", max_usd=0.5, max_iterations=2)
    files = {**snapshot(root / "fixtures" / "repos" / "sums", skip_cache=True), "src/clamp.test.js": "x"}
    assert dr.full_regression_problems(d, c, files) == []
    d["contract"]["validation"] = [vspec("target", ["src/sum.test.js", "src/neg.test.js"], ["src/sum.test.js::adds"])]
    c = dr.build_contract(d, task="t", workspace="fixtures/repos/t", issue="i", max_usd=0.5, max_iterations=2)
    assert dr.full_regression_problems(d, c, files) == []          # the new file's own rule is "has no required node"


def test_g4_a_python_draft_is_not_held_to_it():
    d = {"draft_version": 1, "base": "shop", "plan": {"files": [], "steps": [], "risks": []},
         "contract": {"scope": {"writable": ["src/*.py"], "protected": ["tests/**"]},
                      "validation": [{"id": "target", "executable": "python",
                                      "args": ["-m", "pytest", "tests/test_new.py"], "timeout_s": 120,
                                      "min_tests": 1, "max_skipped": 0, "must_pass": ["tests/test_new.py::test_x"],
                                      "environment": "argus"}]},
         "new_tests": [{"path": "tests/test_new.py", "content": "def test_x():\n    assert 0\n"}], "unverifiable": []}
    c = dr.build_contract(d, task="t", workspace="fixtures/repos/t", issue="i", max_usd=0.5, max_iterations=2)
    files = {"tests/test_old.py": "a", "tests/test_other.py": "b", "web/app.test.js": "c"}
    assert dr.full_regression_problems(d, c, files) == []


def test_g7_harness_unrunnable_tests_are_refused_and_vitest_excluded_directories_are_not_tests(tmp_path):
    """F1a (files from the job's commit) holds by construction: check() gets the intake snapshot, never the repository.
    Here: F1b, and the directories vitest's default `exclude` leaves out."""
    root, _ = make_root(tmp_path, {**BASE, "src/a.spec.jsx": OLD_ADDS, "src/b.test.mjs": OLD_ADDS,
                                   "node_modules/x/y.test.js": OLD_ADDS, "dist/app.test.js": OLD_ADDS,
                                   "cypress/e2e/login.test.js": OLD_ADDS, "web/dist.test.js": OLD_ADDS})
    problems = statics(root, draft([TARGET, ALL_OLD]))
    assert "existing test file web/dist.test.js is in no validation (a vitest draft runs every existing test file)" \
        in problems                                         # a file named like an excluded directory is still a test
    problems = [p for p in problems if "web/dist.test.js" not in p]
    assert f1(problems) == [
        "test file src/a.spec.jsx cannot be run by the harness (only *.test.js|jsx|ts|tsx with plain names): rename "
        "it in the repository",
        "test file src/b.test.mjs cannot be run by the harness (only *.test.js|jsx|ts|tsx with plain names): rename "
        "it in the repository"]


def test_f3_the_vitest_prompt_asks_for_every_old_file_and_the_python_one_does_not():
    rule = "Name every existing test file (*.test.*) in a validation"
    assert rule in cdr.SYSTEM_VITEST and rule not in cdr.SYSTEM
    assert "leave that file out of the validations" not in cdr.SYSTEM_VITEST
    assert ("changes behaviour that an existing test checks, still name that file, and start unverifiable with "
            "`EXISTING TEST CONFLICT: <file>::<test name>`") in cdr.SYSTEM_VITEST
    assert "A validation names at most 15 files; split them over several validations" in cdr.SYSTEM_VITEST
    assert "An existing test that needs any of these fails there" in cdr.SYSTEM_VITEST


# ---- G5, G6: the 0e27 shape in the sandbox -------------------------------------------------------------------------

@pytest.fixture(scope="module")
def scfg():
    c = {**(load_config().get("sandbox") or {}), "kind": "docker"}
    ok, why = sb.status({**c, "environment": "pwa_node22"})
    if not ok:
        pytest.skip(f"SANDBOX NOT AVAILABLE: {why}")
    return c


def reference(tmp_path, files, changes):
    r = tmp_path / "ref"
    for p, text in files.items():
        (r / p).parent.mkdir(parents=True, exist_ok=True)
        (r / p).write_text(text)
    git(tmp_path, "init", "-q", str(r))
    git(r, "add", "-A")
    git(r, "commit", "-qm", "base")
    for p, text in changes.items():
        (r / p).write_text(text)
    git(r, "add", "-A")
    out = tmp_path / "ref.patch"
    out.write_text(git(r, "diff", "--cached"))
    return out


def check(root, d, ref, scfg, **over):
    return dr.check(d, task="clamp", issue="floor the sum at 0", max_usd=0.5, max_iterations=2,
                    reference_patch=ref, sandbox_cfg=scfg, root=root, profiles=None, **over)


def test_g5_the_0e27_shape_is_refused_before_running_and_at_reference_green(tmp_path, scfg):
    root, _ = make_root(tmp_path)
    ref = reference(tmp_path, {**BASE, "src/clamp.test.js": NEW_CLAMP}, {"src/sum.js": CLAMPED})

    def never(*a, **k):
        raise AssertionError("a validation ran for a draft the static check refuses")
    r = check(root, draft([TARGET, ONLY_ADDS]), ref, scfg, validate=never)
    assert not r["ok"] and f1(r["problems"]) == [
        "existing test file src/neg.test.js is in no validation (a vitest draft runs every existing test file)"]

    r = check(root, draft([TARGET, ALL_OLD]), ref, scfg)          # named: the fix breaks it and the reference says so
    assert not r["ok"] and r["baseline"] and r["reference"], r["problems"]
    assert any("regression" in p for p in r["problems"]), r["problems"]
    assert r["reference"]["regression"] == "fail" and r["reference"]["target"] == "pass", r["reference"]


def test_g6_an_old_file_named_only_in_the_red_validation_must_still_pass_on_the_baseline(tmp_path, scfg):
    root, _ = make_root(tmp_path, {**BASE, "src/bad.test.js": OLD_BAD})
    red = vspec("target", ["src/clamp.test.js", "src/bad.test.js"], ["src/clamp.test.js::floors at 0"], min_tests=2)
    r = check(root, draft([red, ALL_OLD]), None, scfg)
    assert f1(r["problems"]) == [] and not r["ok"], r["problems"]
    assert any("exactly the 1 new required tests may fail" in p and "src/bad.test.js::is wrong already" in p
               for p in r["problems"]), r["problems"]


def test_g5_g6_control_a_good_draft_passes(tmp_path, scfg):
    """Without the broken old test and without the conflicting fix the same draft passes, so G5 and G6 fail for their
    own reason."""
    root, _ = make_root(tmp_path, {"src/sum.js": SUM, "src/sum.test.js": OLD_ADDS})
    ref = reference(tmp_path, {"src/sum.js": SUM, "src/sum.test.js": OLD_ADDS, "src/clamp.test.js": NEW_CLAMP},
                    {"src/sum.js": CLAMPED})
    r = check(root, draft([TARGET, ONLY_ADDS]), ref, scfg)
    assert r["ok"], r["problems"]
