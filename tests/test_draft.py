"""M6 W2a: a task draft is checked deterministically (contract, new tests, baseline red in the sandbox, the human's
reference patch green) and only an approved, ok report becomes a task: a record binding the intake, the added tests
and the contract, the contract, and the task repository. The sandbox checks run in the `argus` environment; without
it they are skipped with "SANDBOX NOT AVAILABLE", which scripts/verify.sh does not count as passing."""
import copy
import json
import os
import subprocess

import pytest

from acceptance import contract as ct
from acceptance import draft as dr
from acceptance import intake
from runner import load_config
from tools import sandbox as sb

BUGGY = "def total(prices, discount):\n    return sum(prices) - discount\n"
FIXED = "def total(prices, discount):\n    return max(sum(prices) - discount, 0)\n"
OLD_TEST = "from src.shop import total\n\n\ndef test_total_plain():\n    assert total([2, 3], 1) == 4\n"
NEW_TEST = "from src.shop import total\n\n\ndef test_total_never_negative():\n    assert total([1], 5) == 0\n"
NEW_NODE = "tests/test_new.py::test_total_never_negative"
OLD_NODE = "tests/test_old.py::test_total_plain"
SKIP_TEST = "import pytest\n\n\ndef test_skipped_here():\n    pytest.skip('not here')\n"


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
          "reference_patch": ref, "sandbox_cfg": scfg, "root": root, **over}
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
