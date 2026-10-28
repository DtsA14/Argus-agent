"""M6 W2a: a task draft is checked deterministically (contract, new tests, baseline red in the sandbox, the human's
reference patch green) and only an approved, ok report becomes a task: a record binding the intake, the added tests
and the contract, the contract, and the task repository. The sandbox checks run in the `argus` environment; without
it they are skipped with "SANDBOX NOT AVAILABLE", which scripts/verify.sh does not count as passing."""
import copy
import hashlib
import json
import os
import subprocess

from pathlib import Path

import pytest

from acceptance import changed as ch
from acceptance import contract as ct
from acceptance import draft as dr
from acceptance import intake
from acceptance import validation as va
from acceptance.workspace import snapshot
from runner import load_config
from tools import sandbox as sb

ROOT_DIR = Path(__file__).resolve().parent.parent
BUGGY = "def total(prices, discount):\n    return sum(prices) - discount\n"
FIXED = "def total(prices, discount):\n    return max(sum(prices) - discount, 0)\n"
OLD_TEST = "from src.shop import total\n\n\ndef test_total_plain():\n    assert total([2, 3], 1) == 4\n"
NEW_TEST = "from src.shop import total\n\n\ndef test_total_never_negative():\n    assert total([1], 5) == 0\n"
NEW_NODE = "tests/test_new.py::test_total_never_negative"
OLD_NODE = "tests/test_old.py::test_total_plain"
SKIP_TEST = "import pytest\n\n\ndef test_skipped_here():\n    pytest.skip('not here')\n"
# W2a-ext: an existing test that locks in the behaviour the issue changes, and one the intake already skips by a marker
LOCK_TEST = ("import pytest\n\nfrom src.shop import total\n\n\n"
             "def test_total_negative():\n    assert total([1], 5) == -4\n\n\n"
             "def test_total_zero():\n    assert total([], 0) == 0\n\n\n"
             "@pytest.mark.parametrize('n', [1, 2])\ndef test_total_param(n):\n    assert total([n], 0) == n\n\n\n"
             "@pytest.mark.skip(reason='old')\ndef test_old_skip():\n    assert False\n")
LOCK_NEW = LOCK_TEST.replace("== -4", "== 0")
LOCK_NODE = "tests/test_lock.py::test_total_negative"


def git(repo, *args):
    env = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@x", "GIT_COMMITTER_NAME": "t",
           "GIT_COMMITTER_EMAIL": "t@x", "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1"}
    return subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, env=env, text=True).stdout


def spec(id, target, must):
    targets = target if isinstance(target, list) else [target]
    return {"id": id, "executable": "python", "args": ["-m", "pytest", *targets], "timeout_s": 120, "min_tests": 1,
            "max_skipped": 0, "must_pass": must, "environment": "argus"}


DRAFT = {"draft_version": 1, "base": "shop",
         "plan": {"files": ["src/shop.py"], "steps": ["floor the total at 0"], "risks": ["none"]},
         "contract": {"scope": {"writable": ["src/*.py"], "protected": ["tests/**", "conftest.py"]},
                      "validation": [spec("target", "tests/test_new.py", [NEW_NODE]),
                                     spec("regression", "tests/test_old.py", [OLD_NODE])]},
         "new_tests": [{"path": "tests/test_new.py", "content": NEW_TEST}],
         "unverifiable": ["the error message reads well"]}


@pytest.fixture
def root(tmp_path):
    return make_root(tmp_path)


def make_root(tmp_path):
    repo = tmp_path / "shop_repo"
    (repo / "src").mkdir(parents=True)
    (repo / "tests").mkdir()
    (repo / "conftest.py").write_text("")
    (repo / "src" / "shop.py").write_text(BUGGY)
    (repo / "tests" / "test_old.py").write_text(OLD_TEST)
    (repo / "tests" / "test_skip.py").write_text(SKIP_TEST)
    (repo / "tests" / "test_lock.py").write_text(LOCK_TEST)
    # red by assertion: an assert in the code under test, and a protected assert helper beside the tests
    (repo / "src" / "guard.py").write_text("def checked(x):\n    assert x >= 0, 'negative'\n    return x\n")
    (repo / "tests" / "checks.py").write_text("def floor_ok(x):\n    assert x >= 0, 'below 0'\n")
    git(tmp_path, "init", "-q", str(repo))
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "base")
    proj = tmp_path / "proj"
    proj.mkdir()
    intake.intake(repo, "HEAD", "shop", root=proj)
    return proj


def patch(tmp_path, changes):
    """A git diff against the baseline (the intake plus the draft's test) that writes `changes` ({path: text})."""
    r = tmp_path / f"patch_{len(list(tmp_path.glob('patch_*')))}"
    r.mkdir()
    for p, t in {"src/shop.py": BUGGY, "tests/test_old.py": OLD_TEST, "conftest.py": "", "tests/test_skip.py": SKIP_TEST,
                 "tests/test_new.py": NEW_TEST}.items():
        (r / p).parent.mkdir(parents=True, exist_ok=True)
        (r / p).write_text(t)
    git(r, "init", "-q")
    git(r, "add", "-A")
    git(r, "commit", "-qm", "base")
    for p, t in changes.items():
        (r / p).parent.mkdir(parents=True, exist_ok=True)
        (r / p).write_text(t)
    git(r, "add", "-A")
    out = r.parent / f"{r.name}.patch"
    out.write_text(git(r, "diff", "--cached"))
    return out


@pytest.fixture(scope="module")
def scfg():
    c = {**(load_config().get("sandbox") or {}), "kind": "docker"}
    ok, why = sb.status({**c, "environment": "argus"})
    if not ok:
        pytest.skip(f"SANDBOX NOT AVAILABLE: {why}")
    return c


def run_check(root, ref, scfg, draft=None, **over):
    kw = {"task": "fix_shop", "issue": "the total can go negative", "max_usd": 0.5, "max_iterations": 3,
          "reference_patch": ref, "sandbox_cfg": scfg, "root": root, "profiles": None, **over}
    return dr.check(draft or DRAFT, **kw)


@pytest.fixture(scope="module")
def good_report(tmp_path_factory, scfg):
    """The check of the default draft with the reference fix, run once for the module (two sandbox runs, ~12 s).
    check() reads only the content of the root (intake record and snapshot, draft, patch), never its path, and every
    `root` is built with the same content; approve() then checks the intake of the test's own root. So this report is
    the one each test's own check would give. Tests that change what is checked still run their own check.
    Use it through copy.deepcopy: some tests tamper with the report."""
    tmp = tmp_path_factory.mktemp("good")
    return run_check(make_root(tmp), patch(tmp, {"src/shop.py": FIXED}), scfg)


# ---- the draft's shape and what it may not set (no sandbox) ---------------------------------------------------

@pytest.mark.parametrize("change, why", [
    (lambda d: d.pop("unverifiable"), "missing key 'unverifiable'"),
    (lambda d: d.update(extra=1), "unknown key 'extra'"),
    (lambda d: d["contract"].update(limits={"max_usd": 5, "max_iterations": 10}), "contract must have"),
    (lambda d: d["contract"].update(inputs={"workspace": "fixtures/repos/x", "issue": "y"}), "contract must have"),
    (lambda d: d.update(new_tests=[]), "at least one new test"),
    (lambda d: d["new_tests"][0].update(path="src/helper.py"), "test_*.py"),
    (lambda d: d["new_tests"][0].update(path="../tests/test_x.py"), "test_*.py"),
    (lambda d: d["new_tests"].append(dict(d["new_tests"][0])), "duplicate paths"),
    (lambda d: d["new_tests"][0].update(content="x" * 60_000), "larger than"),
    (lambda d: d["plan"].pop("risks"), "plan must have"),
    (lambda d: d.update(unverifiable=[""]), "unverifiable"),
])
def test_malformed_drafts_and_drafts_that_set_what_only_a_human_sets_are_refused(change, why):
    d = copy.deepcopy(DRAFT)
    change(d)
    assert any(why in e for e in dr.validate_draft(d)), dr.validate_draft(d)


def test_the_human_sets_the_input_issue_cap_and_attempts():
    c = dr.build_contract(DRAFT, task="t", workspace="fixtures/repos/t", issue="i", max_usd=0.4, max_iterations=2)
    assert c["inputs"] == {"workspace": "fixtures/repos/t", "issue": "i"}
    assert c["limits"] == {"max_usd": 0.4, "max_iterations": 2} and ct.validate(c) == []


@pytest.mark.parametrize("change, why", [
    (lambda d: d["contract"]["scope"].update(writable=["src/*.py", "tests/test_new.py"]), "must be protected and not writable"),
    (lambda d: d["contract"]["scope"].update(protected=["tests/test_old.py", "conftest.py"]), "must be protected"),
    (lambda d: d["contract"]["validation"][0].update(must_pass=[]), "has no required node"),
    (lambda d: d["new_tests"][0].update(path="tests/test_old.py"), "already exists in the intake"),
    (lambda d: d["contract"]["validation"][0].update(args=["-m", "unittest", "discover", "-s", "tests"],
                                                     must_pass=["tests.test_new.T.test_x"]), "has no required node"),
])
def test_static_problems(root, change, why):
    d = copy.deepcopy(DRAFT)
    change(d)
    c = dr.build_contract(d, task="t", workspace="fixtures/repos/t", issue="i", max_usd=0.5, max_iterations=2)
    problems = dr.static_problems(d, c, {"src/shop.py": "x", "tests/test_old.py": "y", "conftest.py": "z",
                                        "tests/test_skip.py": "w"})
    assert any(why in p for p in problems), problems


@pytest.mark.parametrize("change, over, why", [
    # pilot W2b-3 run 2: a directory name passed this check and then blocked setup after approval
    (lambda d: d["contract"]["scope"].update(protected=["tests", "tests/**", "conftest.py"]), {},
     "contract: protected glob 'tests' matches no input file (it names a directory; globs match files: use "
     "'tests/**')"),
    (lambda d: d["contract"].update(budget_profile="huge"), {"profiles": ["default", "large_usd"]},
     "contract: unknown budget profile 'huge' (configured: ['default', 'large_usd'])"),
    (lambda d: None, {"sandbox_cfg": {"environments": {"other": {}}}},
     "contract: unknown sandbox environment(s) ['argus'] (configured: ['other'])"),
    # a sandbox config without the key: no environment is configured, as setup reads it (review of #180)
    (lambda d: None, {"sandbox_cfg": {"kind": "docker"}},
     "contract: unknown sandbox environment(s) ['argus'] (configured: [])"),
])
def test_what_setup_would_refuse_is_refused_by_the_draft_check(root, change, over, why):
    d = copy.deepcopy(DRAFT)
    change(d)
    r = run_check(root, None, over.pop("sandbox_cfg", {}), draft=d, **over)
    assert not r["ok"] and r["problems"] == [why] and "baseline" not in r


def test_the_draft_check_needs_profiles_given_explicitly():
    # review of #180: a caller that forgets profiles must not silently skip the profile check
    with pytest.raises(TypeError, match="profiles"):
        dr.check(DRAFT, task="t", issue="i", max_usd=0.5, max_iterations=1, reference_patch=None, sandbox_cfg={})


def test_the_draft_check_runs_the_checks_setup_runs_through_their_shared_function(root, monkeypatch):
    seen = []
    monkeypatch.setattr(ct, "setup_problems", lambda c, files, **kw: seen.append((set(files), kw)) or ["sentinel"])
    r = run_check(root, None, {}, profiles=["default"])
    assert not r["ok"] and r["problems"] == ["contract: sentinel"]
    files, kw = seen[0]
    assert "tests/test_new.py" in files and "src/shop.py" in files          # the task baseline: intake plus new tests
    assert kw == {"profiles": ["default"], "environments_configured": None}


def test_a_draft_on_an_intake_that_changed_is_refused(root, tmp_path):
    (root / "fixtures" / "repos" / "shop" / "src" / "shop.py").write_text(FIXED)
    r = run_check(root, patch(tmp_path, {"src/shop.py": FIXED}), {})
    assert not r["ok"] and "intake shop" in r["problems"][0]


def test_a_draft_on_no_intake_is_refused(root, tmp_path):
    r = run_check(root, patch(tmp_path, {}), {}, draft={**DRAFT, "base": "nosuch"})
    assert not r["ok"] and "no intake named 'nosuch'" in r["problems"][0]


# ---- baseline red and reference green, in the sandbox -----------------------------------------------------------

def test_a_good_draft_is_ok_and_approval_publishes_a_task_bound_to_its_contract(root, good_report):
    r = copy.deepcopy(good_report)
    assert r["ok"], r["problems"]
    assert r["baseline"]["target"]["must_pass"] == {NEW_NODE: "FAIL"} and r["baseline"]["regression"]["status"] == "pass"
    assert r["reference"]["target"] == r["reference"]["regression"] == "pass"
    assert r["reference"]["changed"]["modified"] == ["src/shop.py"] and r["unverifiable"] == DRAFT["unverifiable"]
    rec = dr.approve(r, DRAFT, root=root)
    task = root / "fixtures" / "repos" / "fix_shop"
    assert (task / "tests" / "test_new.py").read_text() == NEW_TEST and (task / "src" / "shop.py").read_text() == BUGGY
    assert intake.check(rec, task) == [] and intake.record_for("fixtures/repos/fix_shop", root) == rec
    contract = json.loads((root / "fixtures" / "contracts" / "fix_shop.json").read_text())
    assert ct.freeze(contract)[1] == rec["contract_sha256"] and contract["inputs"]["workspace"] == "fixtures/repos/fix_shop"
    assert rec["kind"] == "task" and rec["base"]["commit"] == rec["commit"]
    assert set(rec["added"]) == {"tests/test_new.py"} and rec["unverifiable"] == DRAFT["unverifiable"]
    assert r["feasibility"] == rec["feasibility"] == "proven"                # W2b: a reference patch passed
    assert "assert" in r["baseline"]["target"]["output_tail"]                # W2b: the test output, for the review


# ---- W2b: no reference patch ------------------------------------------------------------------------------------

def test_without_a_reference_patch_the_baseline_is_still_checked_and_the_task_is_unproven(root, scfg):
    r = run_check(root, None, scfg)
    assert r["ok"], r["problems"]
    assert r["reference"] is None and r["feasibility"] == "unproven"
    assert r["baseline"]["target"]["must_pass"] == {NEW_NODE: "FAIL"}
    rec = dr.approve(r, DRAFT, root=root)
    assert rec["feasibility"] == "unproven" and rec["kind"] == "task"
    bad = run_check(root, None, scfg, draft=with_new_test(NEW_TEST.replace("== 0", "== -4")), task="fix_shop2")
    assert not bad["ok"] and any("not a failure by assertion" in p for p in bad["problems"])


def test_a_test_that_fails_on_the_baseline_without_being_required_is_named(root, scfg):
    r = run_check(root, None, scfg, draft=with_new_test(NEW_TEST + "\n\ndef test_also_failing():\n    assert False\n"))
    assert not r["ok"]
    assert any("not required: tests/test_new.py::test_also_failing" in p for p in r["problems"]), r["problems"]
    assert r["baseline"]["target"]["failed_nodes"] == ["tests/test_new.py::test_also_failing", NEW_NODE]


@pytest.mark.parametrize("ref", [[], ["--reference-patch", "x.patch", "--no-reference"]])
def test_approve_draft_needs_exactly_one_of_a_reference_patch_or_no_reference(ref, capsys):
    import importlib.util
    spec = importlib.util.spec_from_file_location("approve_draft", ROOT_DIR / "scripts" / "approve_draft.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    with pytest.raises(SystemExit) as e:
        mod.main(["--draft", "d.json", "--task", "t", "--issue-file", "i.txt", "--max-usd", "0.5",
                  "--max-iterations", "1", *ref])
    assert e.value.code == 2


def with_new_test(content, must=None):
    d = copy.deepcopy(DRAFT)
    d["new_tests"][0]["content"] = content
    if must is not None:
        d["contract"]["validation"][0]["must_pass"] = must
    return d


@pytest.mark.parametrize("draft, why", [
    (with_new_test(NEW_TEST.replace("== 0", "== -4")), "is 'ok', not a failure by assertion"),          # green at base
    (with_new_test("import nosuchmodule\n\n\ndef test_total_never_negative():\n    pass\n"), "was not collected"),
    (with_new_test("import pytest\n\n\n@pytest.fixture\ndef broken():\n    raise RuntimeError\n\n\n"
                   "def test_total_never_negative(broken):\n    pass\n"), "is 'ERROR'"),
    (with_new_test(NEW_TEST, must=["tests/test_new.py::test_not_written"]), "was not collected"),
    (with_new_test(NEW_TEST + "\n\ndef test_also_failing():\n    assert False\n"), "exactly the 1 new required"),
])
def test_the_baseline_must_be_red_by_assertion_and_only_where_required(root, tmp_path, scfg, draft, why):
    r = run_check(root, patch(tmp_path, {"src/shop.py": FIXED}), scfg, draft=draft)
    assert not r["ok"] and any(why in p for p in r["problems"]), r["problems"]
    assert "reference" not in r                                  # the reference patch is never tried on a bad baseline


def test_an_existing_required_test_that_does_not_pass_on_the_baseline_is_refused(root, tmp_path, scfg):
    # skipped, so the failure count alone would not notice it
    d = copy.deepcopy(DRAFT)
    d["contract"]["validation"][0] = spec("target", ["tests/test_new.py", "tests/test_skip.py"],
                                          [NEW_NODE, "tests/test_skip.py::test_skipped_here"])
    d["contract"]["validation"][0]["max_skipped"] = 1
    r = run_check(root, patch(tmp_path, {"src/shop.py": FIXED}), scfg, draft=d)
    assert not r["ok"] and any("existing test tests/test_skip.py::test_skipped_here must pass on the baseline, is "
                               "'skipped'" in p for p in r["problems"]), r["problems"]


def test_a_baseline_whose_pytest_output_does_not_account_for_itself_is_refused(tmp_path):
    def inconsistent(spec, ws, cfg, log=None):
        must = {n: ("FAIL" if n == NEW_NODE else "ok") for n in spec.get("must_pass", [])}
        return {"id": f"validation:{spec['id']}", "status": "fail" if NEW_NODE in must else "pass", "reason": "x",
                "evidence": {"must_pass": must, "failures": 1 if NEW_NODE in must else 0, "errors": 0,
                             "consistent": False}}
    c = dr.build_contract(DRAFT, task="t", workspace="fixtures/repos/t", issue="i", max_usd=0.5, max_iterations=2)
    problems, _ = dr.baseline_problems(c, {"tests/test_new.py"}, tmp_path, {}, validate=inconsistent)
    assert problems == ["validation target: pytest output does not account for itself"]


def test_a_regression_validation_that_fails_on_the_baseline_is_refused(root, tmp_path, scfg):
    d = copy.deepcopy(DRAFT)
    d["contract"]["validation"][1] = spec("regression", "tests", [OLD_NODE])        # also runs the red new test
    r = run_check(root, patch(tmp_path, {"src/shop.py": FIXED}), scfg, draft=d)
    assert not r["ok"] and any("must pass on the baseline" in p for p in r["problems"]), r["problems"]


@pytest.mark.parametrize("changes, why", [
    ({"src/shop.py": FIXED, "tests/test_new.py": NEW_TEST.replace("== 0", "== -4")}, "changes tests/test_new.py"),
    ({"tests/test_old.py": OLD_TEST + "\n"}, "changes tests/test_old.py"),
    ({"src/shop.py": FIXED, "src/sub/extra.py": ""}, "changes src/sub/extra.py"),
    ({}, "changes nothing"),
    ({"src/shop.py": BUGGY.replace("discount", "d")}, "does not pass with the reference patch"),
])
def test_the_reference_patch_must_fix_it_by_changing_only_writable_files(root, tmp_path, scfg, changes, why):
    r = run_check(root, patch(tmp_path, changes), scfg)
    assert not r["ok"] and any(why in p for p in r["problems"]), r["problems"]


def test_a_reference_patch_that_does_not_apply_is_refused(root, tmp_path, scfg):
    bad = tmp_path / "bad.patch"
    bad.write_text("--- a/src/missing.py\n+++ b/src/missing.py\n@@ -1 +1 @@\n-x\n+y\n")
    r = run_check(root, bad, scfg)
    assert not r["ok"] and "does not apply" in r["problems"][0]


# ---- approval -------------------------------------------------------------------------------------------------

def test_only_an_ok_report_is_approved_and_approval_never_overwrites(root, good_report):
    with pytest.raises(dr.DraftError, match="only a report"):
        dr.approve({"ok": False, "task": "fix_shop"}, DRAFT, root=root)
    r = copy.deepcopy(good_report)
    dr.approve(r, DRAFT, root=root)
    with pytest.raises(dr.DraftError, match="never overwrites"):
        dr.approve(r, DRAFT, root=root)


def test_tests_changed_between_check_and_approval_are_refused(root, good_report):
    r = copy.deepcopy(good_report)
    other = with_new_test(NEW_TEST.replace("[1], 5", "[2], 9"))
    with pytest.raises(dr.DraftError, match="differs from the one that was checked"):
        dr.approve(r, other, root=root)
    assert not (root / "fixtures" / "repos" / "fix_shop").exists()


def test_a_stop_before_the_task_repository_leaves_a_record_that_setup_refuses(root, good_report, monkeypatch):
    r = copy.deepcopy(good_report)
    real = os.replace
    monkeypatch.setattr(dr.os, "replace", lambda s, d: (_ for _ in ()).throw(OSError("stop"))
                        if os.path.basename(str(d)) == "fix_shop" else real(s, d))
    with pytest.raises(OSError):
        dr.approve(r, DRAFT, root=root)
    rec = intake.record_for("fixtures/repos/fix_shop", root)
    assert rec is not None and "missing" in intake.check(rec, root / "fixtures" / "repos" / "fix_shop")[0]


def test_an_approved_task_changed_afterwards_fails_its_check(root, good_report):
    r = copy.deepcopy(good_report)
    rec = dr.approve(r, DRAFT, root=root)
    test = root / "fixtures" / "repos" / "fix_shop" / "tests" / "test_new.py"
    test.write_text(NEW_TEST.replace("== 0", "== -4"))                 # the approved test is edited later
    assert intake.check(rec, test.parent.parent)


def nothing_published(root):
    return not any((root / "fixtures" / d / n).exists() for d, n in
                   (("repos", "fix_shop"), ("intake", "fix_shop.json"), ("contracts", "fix_shop.json")))


def change_limits(r, d):
    r["contract"]["limits"]["max_usd"] = 5.0                      # after the check, before approval


def forge_scope(r, d):
    r["contract"]["scope"]["writable"].append("tests/*.py")       # and recompute the hash to match
    r["contract_sha256"] = ct.freeze(r["contract"])[1]


def change_draft(r, d):
    d["plan"]["steps"].append("also rewrite the tests")


@pytest.mark.parametrize("tamper, why", [
    (change_limits, "the contract differs from the one that was checked"),
    (forge_scope, "the contract is not the draft plus the human's fields"),
    (change_draft, "the draft differs from the one that was checked"),
])
def test_a_report_or_draft_changed_between_check_and_approval_is_refused_and_publishes_nothing(
        root, good_report, tamper, why):
    # review of #79: approve() publishes exactly what check() checked, whoever calls it
    r = copy.deepcopy(good_report)
    assert r["ok"] and r["contract_sha256"] == ct.freeze(r["contract"])[1]
    d = copy.deepcopy(DRAFT)
    tamper(r, d)
    with pytest.raises(dr.DraftError, match=why):
        dr.approve(r, d, root=root)
    assert nothing_published(root)


def test_the_contract_never_shares_objects_with_the_draft():
    c = dr.build_contract(DRAFT, task="t", workspace="fixtures/repos/t", issue="i", max_usd=0.5, max_iterations=2)
    c["scope"]["writable"].append("tests/*.py")
    c["validation"][0]["must_pass"].clear()
    assert DRAFT["contract"]["scope"]["writable"] == ["src/*.py"] and DRAFT["contract"]["validation"][0]["must_pass"]


def test_an_intake_changed_between_check_and_approval_is_refused(root, good_report):
    r = copy.deepcopy(good_report)
    (root / "fixtures" / "repos" / "shop" / "src" / "shop.py").write_text(FIXED)
    with pytest.raises(dr.DraftError, match="changed since the check"):
        dr.approve(r, DRAFT, root=root)
    assert nothing_published(root)


# ---- W2a-ext: a draft that changes existing tests (docs/reviews/SPEC_W2A_EXT_CHANGED_TESTS.md) -----------------------

def changing(content=LOCK_NEW, must=(LOCK_NODE,), path="tests/test_lock.py", max_skipped=1, **entry):
    """The default draft, plus a changed test file and a validation that runs it whole."""
    d = copy.deepcopy(DRAFT)
    d["contract"]["validation"].append(spec("lock", path, list(must)))
    d["contract"]["validation"][-1]["max_skipped"] = max_skipped
    d["changed_tests"] = [{"path": path, "content": content, **entry}]
    return d


DRAFT_CH = changing()


@pytest.fixture(scope="module")
def changed_report(tmp_path_factory, scfg):
    """The check of DRAFT_CH with the reference fix, once for the module (like good_report; deepcopy it)."""
    tmp = tmp_path_factory.mktemp("changed")
    return run_check(make_root(tmp), patch(tmp, {"src/shop.py": FIXED}), scfg, draft=DRAFT_CH)


def five_changes(d):
    d["changed_tests"] = [{"path": f"tests/test_c{i}.py", "content": "x"} for i in range(6)]


@pytest.mark.parametrize("change, why", [
    *[(lambda d, p=p: d["changed_tests"][0].update(path=p),
       "conftest.py, pytest.ini, pyproject.toml and setup.cfg are never changed")
      for p in ("conftest.py", "tests/conftest.py", "pytest.ini", "pyproject.toml", "setup.cfg", "src/helper.py",
                "../tests/test_lock.py")],
    (five_changes, "at most 5 files"),
    (lambda d: d["changed_tests"][0].update(removed=[{"node": "tests/test_lock.py::test_total_zero", "reason": "x"}]),
     "removed must be a list"),
    (lambda d: d["changed_tests"][0].update(removed=[{"node": "test_total_zero", "reason": " "}]), "removed must be"),
    (lambda d: d["changed_tests"][0].update(modified=[{"node": "test_total_param[1]", "reason": "x"}]),
     "modified must be"),
    (lambda d: d["changed_tests"][0].update(removed=[{"node": "test_total_zero", "reason": "x"}],
                                            modified=[{"node": "test_total_zero", "reason": "y"}]), "listed twice"),
    (lambda d: d["changed_tests"].append(dict(d["changed_tests"][0])), "duplicate paths"),
    (lambda d: d["changed_tests"][0].update(path="tests/test_new.py"), "is also a new test"),
    (lambda d: d["changed_tests"][0].update(content="x" * 60_000), "larger than"),
    (lambda d: d["changed_tests"][0].update(extra=1), "must be {path, content"),
    (lambda d: d["contract"]["validation"][0].update(no_skip={"paths": ["tests/test_lock.py"], "allowed": []}),
     "no_skip is set by the harness"),
])
def test_changed_tests_of_the_wrong_shape_are_refused(change, why):
    d = copy.deepcopy(DRAFT_CH)
    change(d)
    assert any(why in e for e in dr.validate_draft(d)), dr.validate_draft(d)


def test_a_draft_without_changed_tests_is_the_draft_it_was():
    assert dr.validate_draft(DRAFT) == [] and dr.validate_draft(DRAFT_CH) == []
    c = dr.build_contract(DRAFT, task="t", workspace="fixtures/repos/t", issue="i", max_usd=0.5, max_iterations=2)
    assert all("no_skip" not in v for v in c["validation"])


def altered(change):
    d = copy.deepcopy(DRAFT_CH)
    change(d)
    return d


def statics(root, d):
    base = root / "fixtures" / "repos" / "shop"
    old = dr.old_tests(base, d)
    c = dr.build_contract(d, task="t", workspace="fixtures/repos/t", issue="i", max_usd=0.5, max_iterations=2, old=old)
    return dr.static_problems(d, c, snapshot(base, skip_cache=True), old)


@pytest.mark.parametrize("draft, why", [
    (changing(path="tests/test_missing.py", must=[]), "tests/test_missing.py does not exist in the intake"),
    (changing(LOCK_TEST), "is the same as in the intake"),
    (altered(lambda d: d["contract"]["scope"]["writable"].append("tests/test_lock.py")),
     "must be protected and not writable"),
    (altered(lambda d: d["contract"]["validation"][2]["args"].extend(["-k", "negative"])),
     "is not run whole by any pytest validation"),
    # addition 1: a test function that is not required may not change unless modified names it
    (changing(LOCK_NEW.replace("total([], 0) == 0", "total([], 0) >= 0")),
     "tests/test_lock.py::test_total_zero differs from the intake version but is neither required nor listed in modified"),
    (changing(LOCK_NEW.replace("def test_total_zero", "@pytest.mark.skip\ndef test_total_zero")),
     "tests/test_lock.py::test_total_zero differs"),
    (changing(LOCK_NEW, modified=[{"node": "test_total_zero", "reason": "x"}]), "modified tests/test_lock.py::test_total_zero is unchanged"),
    (changing(LOCK_NEW, modified=[{"node": "test_nothing", "reason": "x"}]), "is not a test function in both"),
    (changing(LOCK_NEW, removed=[{"node": "test_total_negative", "reason": "x"}]), "is also required"),
    (changing(LOCK_NEW + "\ndef broken(:\n"), "does not parse"),
])
def test_static_problems_of_changed_tests(root, draft, why):
    problems = statics(root, draft)
    assert any(why in p for p in problems), problems


@pytest.mark.parametrize("content, entry", [
    (LOCK_NEW, {}),                                                                       # the required node changes
    (LOCK_NEW.replace("total([], 0) == 0", "total([], 0) >= 0"), {"modified": [{"node": "test_total_zero", "reason": "x"}]}),
    ("import pytest\nfrom src.shop import total\n\nHELPER = 1\n\n\n" + LOCK_NEW.split("\n\n\n", 1)[1], {}),  # module level
])
def test_what_a_changed_test_may_change_without_a_static_problem(root, content, entry):
    assert statics(root, changing(content, **entry)) == []


def test_the_contract_holds_the_no_skip_rule_built_from_the_intake_version(root):
    base = root / "fixtures" / "repos" / "shop"
    c = dr.build_contract(DRAFT_CH, task="t", workspace="fixtures/repos/t", issue="i", max_usd=0.5, max_iterations=2,
                          old=dr.old_tests(base, DRAFT_CH))
    assert [v.get("no_skip") for v in c["validation"]] == [
        None, None, {"paths": ["tests/test_lock.py"], "allowed": ["tests/test_lock.py::test_old_skip"]}]
    assert ct.validate(c) == []


@pytest.mark.parametrize("old, allowed", [
    ("import pytest\npytestmark = pytest.mark.skip\n\ndef test_a():\n    pass\n", ["t/test_x.py"]),
    ("import pytest\npytestmark = [pytest.mark.xfail(reason='x')]\n\ndef test_a():\n    pass\n", ["t/test_x.py"]),
    ("import pytest\n\n@pytest.mark.skipif(True, reason='x')\nclass TestA:\n    def test_a(self):\n        pass\n",
     ["t/test_x.py::TestA"]),
    ("import pytest\n\nclass TestA:\n    pytestmark = pytest.mark.skip\n\n    def test_a(self):\n        pass\n",
     ["t/test_x.py::TestA"]),
    ("import pytest\n\nclass TestA:\n    @pytest.mark.xfail\n    def test_a(self):\n        pass\n\n"
     "    def test_b(self):\n        pass\n", ["t/test_x.py::TestA::test_a"]),
    ("import pytest\n\ndef test_a():\n    pytest.skip('at run time')\n", []),         # not a marker: not allowed
    ("def helper():\n    pass\n", []),
])
def test_what_counts_as_already_skipped_is_read_from_the_intake_versions_markers(old, allowed):
    assert ch.skip_allowed("t/test_x.py", old) == allowed


PYTEST_OUT = ("collecting ... collected 4 items\n\n"
              "tests/test_lock.py::test_a PASSED\n"
              "tests/test_lock.py::test_b SKIPPED (x)\n"
              "tests/test_lock.py::test_c[1] XFAIL (y)\n"
              "tests/test_other.py::test_d SKIPPED (z)\n\n"
              "======== 1 passed, 2 skipped, 1 xfailed in 0.01s ========\n")


@pytest.mark.parametrize("no_skip, violations", [
    ({"paths": ["tests/test_lock.py"], "allowed": []}, ["tests/test_lock.py::test_b", "tests/test_lock.py::test_c[1]"]),
    ({"paths": ["tests/test_lock.py"], "allowed": ["tests/test_lock.py::test_b"]}, ["tests/test_lock.py::test_c[1]"]),
    ({"paths": ["tests/test_lock.py"], "allowed": ["tests/test_lock.py::test_b", "tests/test_lock.py::test_c"]}, []),
    ({"paths": ["tests/test_lock.py"], "allowed": ["tests/test_lock.py"]}, []),
    (None, None),
])
def test_acceptance_refuses_a_skip_or_xfail_in_a_changed_file_that_was_not_marked_before(no_skip, violations):
    # the same judge_result decides the baseline, the reference run and the agent's acceptance
    from acceptance.validation import judge_result
    s = {**spec("lock", ["tests/test_lock.py", "tests/test_other.py"], []), "max_skipped": 5}
    if no_skip:
        s["no_skip"] = no_skip
    v = judge_result(s, {"stdout": PYTEST_OUT, "exit_code": 0})
    assert v["evidence"].get("skip_violations") == violations
    assert v["status"] == ("fail" if violations else "pass"), v["reason"]
    if violations:
        assert "skipped or xfail in a changed test file" in v["reason"]


@pytest.mark.parametrize("no_skip", [
    {"paths": [], "allowed": []}, {"paths": ["tests/test_lock.py"]}, {"paths": ["tests/*.py"], "allowed": []},
    {"paths": ["tests/test_lock.py"], "allowed": ["tests/test_other.py::test_a"]},
])
def test_a_contract_no_skip_rule_of_the_wrong_shape_is_invalid(no_skip):
    c = dr.build_contract(DRAFT, task="t", workspace="fixtures/repos/t", issue="i", max_usd=0.5, max_iterations=2)
    c["validation"][1]["no_skip"] = no_skip
    assert any("no_skip must be" in e for e in ct.validate(c)), ct.validate(c)
    c["validation"][1]["no_skip"] = {"paths": ["tests/test_old.py"], "allowed": []}
    c["validation"][1]["args"] = ["-m", "unittest", "discover", "-s", "tests"]
    c["validation"][1]["must_pass"] = []
    assert any("no_skip must be" in e for e in ct.validate(c))


def test_k3_warnings_point_at_where_a_changed_test_may_be_weaker():
    old = ("import pytest\n\ndef helper():\n    return 1\n\n\ndef test_a():\n    assert 1\n    assert 2\n\n\n"
           "def test_b():\n    assert 3\n")
    new = ("import pytest\n\ndef helper():\n    return 2\n\n\ndef test_a():\n    assert 1\n\n\n"
           "def test_b():\n    pytest.skip('later')\n    assert True\n")
    w = ch.warnings("t/test_x.py", old, new, [{"node": "test_c", "reason": "replaced"}])
    assert "t/test_x.py::test_c is removed: replaced" in w
    assert "t/test_x.py::test_a has fewer asserts (2 -> 1)" in w
    assert "t/test_x.py has more skip, xfail or `assert True` (0 -> 2)" in w
    assert any("t/test_x.py changes module-level code" in x for x in w)
    assert ch.warnings("t/test_x.py", old, old, []) == []


# ---- W2a-ext in the sandbox ------------------------------------------------------------------------------------------

def test_a_draft_that_changes_an_old_test_is_checked_and_approved_with_its_before_and_after(root, changed_report):
    r = copy.deepcopy(changed_report)
    assert r["ok"], r["problems"]
    assert r["baseline"]["lock"]["must_pass"] == {LOCK_NODE: "FAIL"}                 # K4: red by assertion
    assert r["collection"]["tests/test_lock.py"] == {"intake": 5, "new": 5, "gone": []}
    assert r["reference"]["lock"] == "pass"                     # the old marker skip is allowed by no_skip there too
    assert r["contract"]["validation"][2]["no_skip"]["allowed"] == ["tests/test_lock.py::test_old_skip"]
    assert r["warnings"] == []
    rec = dr.approve(r, DRAFT_CH, root=root)
    task = root / "fixtures" / "repos" / "fix_shop"
    assert (task / "tests" / "test_lock.py").read_text() == LOCK_NEW and intake.check(rec, task) == []
    lock = rec["changed"]["tests/test_lock.py"]
    assert lock["before"] == hashlib.sha256(LOCK_TEST.encode()).hexdigest()
    assert lock["after"] == hashlib.sha256(LOCK_NEW.encode()).hexdigest() and lock["removed"] == lock["modified"] == []
    assert set(rec["added"]) == {"tests/test_new.py"}


def test_an_intake_changed_between_the_check_and_approval_of_a_changed_test_is_refused(root, changed_report):
    r = copy.deepcopy(changed_report)
    (root / "fixtures" / "repos" / "shop" / "tests" / "test_lock.py").write_text(LOCK_TEST + "\n")
    with pytest.raises(dr.DraftError, match="changed since the check"):
        dr.approve(r, DRAFT_CH, root=root)
    assert nothing_published(root)


def test_a_report_whose_changed_tests_differ_from_the_draft_is_refused(root, changed_report):
    r = copy.deepcopy(changed_report)
    r["changed"]["tests/test_lock.py"]["removed"] = [{"node": "test_total_zero", "reason": "x"}]
    with pytest.raises(dr.DraftError, match="changed tests differ"):
        dr.approve(r, DRAFT_CH, root=root)
    assert nothing_published(root)


LOCK_LESS = LOCK_NEW.replace("def test_total_zero():\n    assert total([], 0) == 0\n\n\n", "")
LOCK_ONE_PARAM = LOCK_NEW.replace("[1, 2]", "[1]")


@pytest.mark.parametrize("draft, why", [
    (changing(LOCK_LESS), "loses 1 test(s) not listed in removed: tests/test_lock.py::test_total_zero"),
    # K1 by collection: a parametrized variant that is gone is named (modified: its decorator changed)
    (changing(LOCK_ONE_PARAM, modified=[{"node": "test_total_param", "reason": "fewer cases"}]),
     "loses 1 test(s) not listed in removed: tests/test_lock.py::test_total_param[2]"),
    (changing(LOCK_NEW, removed=[{"node": "test_total_zero", "reason": "x"}]),
     "removed tests/test_lock.py::test_total_zero is still collected"),
    (changing(LOCK_NEW, removed=[{"node": "test_nowhere", "reason": "x"}]), "is not a test of the intake version"),
])
def test_an_old_test_that_is_lost_without_a_reason_is_refused_and_named(root, scfg, draft, why):
    r = run_check(root, None, scfg, draft=draft)
    assert not r["ok"] and any(why in p for p in r["problems"]), r["problems"]
    assert "baseline" not in r                                   # the baseline never runs on a draft that loses tests


@pytest.mark.parametrize("draft", [
    changing(LOCK_LESS, removed=[{"node": "test_total_zero", "reason": "the floor makes it trivial"}]),
    changing(LOCK_ONE_PARAM, removed=[{"node": "test_total_param[2]", "reason": "one case is enough"}],
             modified=[{"node": "test_total_param", "reason": "fewer cases"}]),
])
def test_an_old_test_removed_with_a_reason_is_accepted_and_warned_about(root, scfg, draft):
    r = run_check(root, None, scfg, draft=draft)
    assert r["ok"], r["problems"]
    assert any("is removed:" in w for w in r["warnings"])


def test_a_test_of_a_changed_file_that_fails_without_being_required_is_named(root, scfg):
    d = changing(LOCK_NEW.replace("total([], 0) == 0", "total([], 0) == 1"),
                 modified=[{"node": "test_total_zero", "reason": "x"}])
    r = run_check(root, None, scfg, draft=d)
    assert not r["ok"]
    assert any("not required: tests/test_lock.py::test_total_zero" in p for p in r["problems"]), r["problems"]


@pytest.mark.parametrize("extra", [
    "pytestmark = pytest.mark.skip\n",
    "pytestmark = [pytest.mark.xfail(reason='later')]\n",
    "@pytest.fixture(autouse=True)\ndef _off():\n    pytest.skip('off')\n",
])
def test_a_changed_test_file_that_skips_or_xfails_its_old_tests_is_refused(root, scfg, extra):
    # addition 2: only module-level code changes, so the AST rule lets it through; the contract's no_skip does not
    content = LOCK_TEST.replace("from src.shop import total\n", "from src.shop import total\n\n" + extra)
    d = changing(content, must=[], max_skipped=10)
    assert statics(root, d) == []
    r = run_check(root, None, scfg, draft=d)
    assert not r["ok"]
    assert any("skipped or xfail in a changed test file" in p and "tests/test_lock.py::test_total_zero" in p
               for p in r["problems"]), r["problems"]
    assert not any("test_old_skip" in p for p in r["problems"])            # skipped by a marker in the intake: allowed


def test_a_skip_next_to_a_red_required_test_of_a_changed_file_is_refused(root, scfg):
    # the validation is red (its required node fails), so the baseline check reads the skip itself
    off = ("@pytest.fixture(autouse=True)\ndef _off(request):\n    if request.node.name == 'test_total_zero':\n"
           "        pytest.skip('off')\n")
    d = changing(LOCK_NEW.replace("from src.shop import total\n", "from src.shop import total\n\n" + off),
                 max_skipped=5)
    r = run_check(root, None, scfg, draft=d)
    assert not r["ok"], r["problems"]
    assert any(p == "validation lock: skipped or xfail in a changed test file, and not marked so before the change: "
               "tests/test_lock.py::test_total_zero" for p in r["problems"]), r["problems"]


def test_a_test_skipped_only_at_run_time_in_the_intake_cannot_be_kept_skipped_by_a_change(root, scfg):
    # the limit of addition 2: pytest.skip() in a test body is not a marker, so the old skip is not "already skipped"
    d = changing(SKIP_TEST + "\n\ndef test_more():\n    assert True\n", path="tests/test_skip.py", must=[],
                 max_skipped=1)
    r = run_check(root, None, scfg, draft=d)
    assert not r["ok"] and any("tests/test_skip.py::test_skipped_here" in p for p in r["problems"]), r["problems"]


# ---- red by assertion, really (docs/reviews/SPEC_W2A_RED_BY_ASSERTION.md) ------------------------------------------

SHOP_IMPORT = "import pytest\n\nfrom src.shop import total\n\n\n"


@pytest.mark.parametrize("body, why", [
    # pilot W2b-3: a KeyError in the test body fails whatever the fix is
    ("def test_total_never_negative():\n    assert {'total': total([1], 5)}['floor'] == 0\n",
     "fails with builtins.KeyError, not by an assertion"),
    ("def test_total_never_negative():\n    assert total.floor([1], 5) == 0\n",
     "fails with builtins.AttributeError, not by an assertion"),
    # an assert of the code under test, not of the test: the test checks nothing yet
    ("from src.guard import checked\n\n\ndef test_total_never_negative():\n    checked(total([1], 5))\n",
     "fails by builtins.AssertionError raised in src/guard.py, not in a test file"),
])
def test_a_required_test_that_is_red_but_not_by_its_own_assertion_is_refused(root, scfg, body, why):
    r = run_check(root, None, scfg, draft=with_new_test(SHOP_IMPORT + body))
    assert not r["ok"] and any(why in p and NEW_NODE in p for p in r["problems"]), r["problems"]
    if "KeyError" in why:
        assert any('assert "key" in report' in p for p in r["problems"])


@pytest.mark.parametrize("body, must", [
    ("def test_total_never_negative():\n    if total([1], 5) != 0:\n        raise AssertionError('below 0')\n", None),
    ("def test_total_never_negative():\n    if total([1], 5) < 0:\n        pytest.fail('below 0')\n", None),
    ("def test_total_never_negative():\n    with pytest.raises(ValueError):\n        total([1], 5)\n", None),
    ("from checks import floor_ok\n\n\ndef test_total_never_negative():\n    floor_ok(total([1], 5))\n", None),
    ("class TestTotal:\n    def test_total_never_negative(self):\n        assert total([1], 5) == 0\n",
     ["tests/test_new.py::TestTotal::test_total_never_negative"]),
    ("@pytest.mark.parametrize('d', [5, 6])\ndef test_total_never_negative(d):\n    assert total([1], d) == 0\n",
     ["tests/test_new.py::test_total_never_negative[5]", "tests/test_new.py::test_total_never_negative[6]"]),
])
def test_a_required_test_red_by_an_assertion_of_a_test_file_is_accepted(root, scfg, body, must):
    r = run_check(root, None, scfg, draft=with_new_test(SHOP_IMPORT + body, must=must))
    assert r["ok"], r["problems"]
    rec = r["baseline"]["target"]["red_check"]
    assert all(rec[n]["assertion"] for n in (must or [NEW_NODE]))
    assert {rec[n]["path"] for n in (must or [NEW_NODE])} <= {"tests/test_new.py", "tests/checks.py"}


def red_spec():
    c = dr.build_contract(DRAFT, task="t", workspace="fixtures/repos/t", issue="i", max_usd=0.5, max_iterations=2)
    return c, c["validation"][0]


@pytest.mark.parametrize("got, why", [
    ((None, "no record of the run (exit code 1)"), "how its required tests fail could not be read: no record"),
    (({}, None), "no record of how it fails"),
    (({NEW_NODE: {"outcome": "passed", "type": None, "assertion": False, "path": None}}, None), "no record of how"),
    # SPEC_RED_TESTS_PER_NODE 2.2: an error in a fixture is named as such, not as a missing record
    (({NEW_NODE: {"outcome": "error", "type": None, "assertion": False, "path": None}}, None),
     "errors in its setup or teardown (a fixture)"),
    (({NEW_NODE: {"outcome": "failed", "type": "builtins.TypeError", "assertion": False,
                  "path": "tests/test_new.py"}}, None), "fails with builtins.TypeError, not by an assertion"),
    (({NEW_NODE: {"outcome": "failed", "type": "builtins.AssertionError", "assertion": True,
                  "path": "src/shop.py"}}, None), "raised in src/shop.py, not in a test file"),
    (({NEW_NODE: {"outcome": "failed", "type": "builtins.AssertionError", "assertion": True,
                  "path": None}}, None), "raised in no file of the repository"),
    (({NEW_NODE: {"outcome": "failed", "type": "builtins.AssertionError", "assertion": True,
                  "path": "tests/helper_w.py"}}, None), "raised in tests/helper_w.py"),     # writable helper: no
])
def test_the_red_check_refuses_what_it_cannot_read_or_what_is_not_the_tests_own_assertion(got, why):
    c, s = red_spec()
    c["scope"]["writable"] = ["src/*.py", "tests/helper_w.py"]
    problems, _ = dr.red_by_assertion(s, [NEW_NODE], "/ws", {}, c, {"tests/test_new.py"}, red=lambda *a, **k: got)
    assert len(problems) == 1 and why in problems[0], problems


@pytest.mark.parametrize("path", ["tests/test_new.py", "tests/checks.py"])
def test_the_red_check_accepts_an_assertion_of_the_test_or_a_protected_helper_beside_it(path):
    c, s = red_spec()
    got = {NEW_NODE: {"outcome": "failed", "type": "_pytest.outcomes.Failed", "assertion": True, "path": path}}
    assert dr.red_by_assertion(s, [NEW_NODE], "/ws", {}, c, {"tests/test_new.py"},
                               red=lambda *a, **k: (got, None)) == ([], got)


# ---- SPEC_RED_TESTS_PER_NODE 2.1: the red check records the message and the repository files of the chain -------------

LIB = "def f(d):\n    return d['k']\n"
TESTS = '''from src.lib import f


def test_swallowed():
    try:
        f({})
        err = None
    except KeyError as e:
        err = e
    assert err is None, f"f() raised {err!r}"


def test_chained():
    try:
        f({})
    except KeyError as e:
        raise AssertionError(f"f() raised {e!r}") from e


def test_context():
    try:
        f({})
    except KeyError as e:
        assert False, f"f() raised {e!r}"


def test_cause_outside_except():
    try:
        f({})
        err = None
    except KeyError as e:
        err = e
    raise AssertionError("f() raised") from err                    # __cause__ only, no __context__


def test_from_none():
    try:
        f({})
    except KeyError as e:
        raise AssertionError(f"f() raised {e!r}") from None


def test_long():
    assert False, "y" * 2000 + " and then a KeyError"


def test_deep():
    from src.deep import d0
    try:
        d0()
    except KeyError as e:
        raise AssertionError("d0() raised") from e


import pytest


@pytest.fixture
def broken():
    raise RuntimeError("no data")


def test_fixture_error(broken):
    assert broken


def test_warns():
    import warnings
    warnings.warn("noisy " * 50, DeprecationWarning)
    assert 1 == 0
'''


def test_the_red_check_records_the_message_and_the_repository_files_of_the_chain(tmp_path, scfg):
    tmp_path.chmod(0o755)                                     # read by the sandbox's own user
    (tmp_path / "src").mkdir()
    (tmp_path / "tests").mkdir()
    (tmp_path / "src" / "__init__.py").write_text("")
    (tmp_path / "conftest.py").write_text("")                  # the rootdir on sys.path, as in a task repository
    (tmp_path / "src" / "lib.py").write_text(LIB)
    (tmp_path / "tests" / "test_a.py").write_text(TESTS)
    for i in range(25):                  # a chain through 25 files of the repository: the 20 deepest are kept
        nxt = f"from src.d{i + 1} import d{i + 1}\n    return d{i + 1}()" if i < 24 else "return {}['k']"
        (tmp_path / "src" / f"d{i}.py").write_text(f"def d{i}():\n    {nxt}\n")
    (tmp_path / "src" / "deep.py").write_text("from src.d0 import d0  # noqa\n")
    nodes = [f"tests/test_a.py::{n}" for n in ("test_swallowed", "test_chained", "test_context", "test_from_none",
                                               "test_long", "test_warns", "test_deep", "test_fixture_error",
                                               "test_cause_outside_except")]
    got, why = va.red_check(nodes, str(tmp_path), scfg, timeout_s=120, environment="argus")
    assert why is None, why
    sw, ch, cx, fn, lg, wn, dp, fx, co = (got[n] for n in nodes)
    assert all(r["assertion"] for r in (sw, ch, cx, fn, lg, wn, dp))
    assert "KeyError" in (sw.get("message") or "") and sw.get("repo_paths") == ["tests/test_a.py"]
    assert "KeyError" in (sw.get("message_names") or [])
    assert ch.get("repo_paths") == ["tests/test_a.py", "src/lib.py"] == cx.get("repo_paths")    # each file once
    assert co.get("repo_paths") == ["tests/test_a.py", "src/lib.py"]                           # __cause__ is followed
    assert fn.get("repo_paths") == ["tests/test_a.py"]                    # `from None`: the context is not followed
    assert len(lg.get("message") or "") == 500 and lg["message"].endswith("...") and "KeyError" not in lg["message"]
    assert "KeyError" in (lg.get("message_names") or [])                 # read from the whole message
    assert (wn.get("message") or "").startswith("assert 1 == 0")
    assert len(dp.get("repo_paths") or []) == 20 and dp["repo_paths"][-1] == "src/d24.py"
    assert "tests/test_a.py" not in dp["repo_paths"]                     # the shallowest file is the one left out
    assert fx["outcome"] == "error" and not fx["assertion"]
    from codetask import drafter as dt
    out = dt.swallowed_problems({"contract": {"scope": {"writable": ["src/lib.py"], "protected": ["tests/**"]}}},
                                {"baseline": {"t": {"status": "fail", "red_check": got, "output_tail": ""}}})
    assert sorted(n for n in nodes if any(n in p for p in out)) == sorted([nodes[0], nodes[3], nodes[4]])
