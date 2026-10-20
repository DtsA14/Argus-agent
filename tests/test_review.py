"""M6 W3: the review package of a DONE run. Built without a model and, here, without a sandbox: runs are put together
by hand (a real intake of a small git repository, a real verdict from acceptance.verdict.evaluate, a validation that
reads the tree it is given), so every failure mode of the package can be provoked and checked. The end-to-end path
through run_code_task with a scripted model is at the bottom (it needs the VM, like tests/test_codetask.py)."""
import copy
import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from acceptance import contract as ct
from acceptance import intake
from acceptance.verdict import evaluate
from acceptance.workspace import digest, snapshot
from codetask import frozen, review

POSIX = pytest.mark.skipif(os.name != "posix", reason="executable bits exist on posix only")

BUGGY = "def total(prices, discount):\n    return sum(prices) - discount\n"
FIXED = "def total(prices, discount):\n    return max(sum(prices) - discount, 0)\n"
OLD_TEST = "from src.shop import total\n\n\ndef test_total_plain():\n    assert total([2, 3], 1) == 4\n"
NEW_TEST = "from src.shop import total\n\n\ndef test_total_never_negative():\n    assert total([1], 5) == 0\n"
OLD_NODE = "tests/test_old.py::test_total_plain"

BASE = {"src/shop.py": BUGGY.encode(), "src/extra.py": b"EXTRA = 1\n", "tests/test_old.py": OLD_TEST.encode(),
        "conftest.py": b"", "notes/readme.txt": b"one\ntwo\n", ".gitattributes": b"*.txt text eol=crlf\n",
        ".gitignore": b"*.log\n", "tools/run.sh": b"#!/bin/sh\necho hi\n"}

CONTRACT = {"contract": "fix_shop", "version": 1,
            "inputs": {"workspace": "fixtures/repos/shop", "issue": "The total can go negative.\nFloor it at 0."},
            "scope": {"writable": ["src/**", "notes/**", "tools/**"], "protected": ["tests/**", "conftest.py"]},
            "artifacts": [{"path": "SUMMARY.json", "type": "json", "schema": "claims_v2"}],
            "validation": [{"id": "target", "executable": "python", "args": ["-m", "pytest", "tests/test_old.py"],
                            "timeout_s": 60, "min_tests": 1, "max_skipped": 0, "must_pass": [OLD_NODE]}],
            "judge": [], "limits": {"max_usd": 0.5, "max_iterations": 3}}
CLAIMS = {"claims": [{"claim": "issue_fixed", "evidence": "validation:target"},
                     {"claim": "file_changed", "path": "src/shop.py"}],
          "summary": "floored at 0. ``` | <b>not</b> evidence"}


def git(repo, *args):
    env = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@x", "GIT_COMMITTER_NAME": "t",
           "GIT_COMMITTER_EMAIL": "t@x", "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1"}
    return subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, env=env, text=True).stdout


def make_repo(path, files):
    for p, data in files.items():
        (path / p).parent.mkdir(parents=True, exist_ok=True)
        (path / p).write_bytes(data)
    git(path.parent, "init", "-q", str(path))
    git(path, "add", "-A")
    if "tools/run.sh" in files and os.name == "posix":
        git(path, "update-index", "--chmod=+x", "tools/run.sh")
    git(path, "commit", "-qm", "base")


def fake_validate(spec, workspace, sandbox_cfg, log=None):
    """Stands in for the sandbox and reads the tree it is given: it passes only when the bug is fixed."""
    fixed = (Path(workspace) / "src" / "shop.py").read_text() == FIXED
    must = {n: "ok" if fixed else "FAIL" for n in spec.get("must_pass", [])}
    return {"id": f"validation:{spec['id']}", "layer": "C", "status": "pass" if fixed else "fail",
            "reason": "" if fixed else "exit code 1", "evidence": {"must_pass": must, "tests_run": 3, "outcome":
                                                                 "OK" if fixed else "FAILED", "skipped": 0,
                                                                 "failures": 0 if fixed else 1, "errors": 0}}


class Project:
    def __init__(self, tmp_path):
        self.root, self.repo, self.n = tmp_path / "proj", tmp_path / "shop_repo", 0
        self.root.mkdir()
        make_repo(self.repo, BASE)
        self.record = intake.intake(self.repo, "HEAD", "shop", root=self.root)

    def task(self, name="shoptask", tests=None, unverifiable=("the message reads well",)):
        """An approved task by hand: the intake plus new tests, and a record of kind task."""
        tests = tests or {"tests/test_new.py": NEW_TEST}
        src, dest = self.root / "fixtures" / "repos" / "shop", self.root / "fixtures" / "repos" / name
        shutil.copytree(src, dest)
        added = {}
        for p, text in tests.items():
            (dest / p).parent.mkdir(parents=True, exist_ok=True)
            (dest / p).write_bytes(text.encode())
            added[p] = hashlib.sha256(text.encode()).hexdigest()
        snap = snapshot(dest)
        rec = {**self.record, "kind": "task", "name": name, "added": added, "files": len(snap),
               "snapshot_sha256": digest(snap), "unverifiable": list(unverifiable),
               "base": {k: self.record[k] for k in ("name", "commit", "tree", "snapshot_sha256")}}
        (self.root / "fixtures" / "intake" / f"{name}.json").write_text(json.dumps(rec), encoding="utf-8")
        return rec

    def run(self, *, writes=None, deletes=(), workspace="shop", status="DONE", contract=None, verdict_contract=None,
            claims=CLAIMS, events=True, post=None, validate=None, scfg=None):
        """A finished run: the workspace after the agent, the frozen contract, a real verdict and result.json."""
        self.n += 1
        run_dir = self.root / "runs" / f"r{self.n}"
        ws, pristine = run_dir / "workspace", self.root / "fixtures" / "repos" / workspace
        shutil.copytree(pristine, ws, ignore=shutil.ignore_patterns("__pycache__"))
        for p, data in (writes or {}).items():
            (ws / p).parent.mkdir(parents=True, exist_ok=True)
            (ws / p).write_bytes(data if isinstance(data, bytes) else data.encode())
        for p in deletes:
            (ws / p).unlink()
        if post:
            post(ws)
        if claims is not None:
            (ws / "SUMMARY.json").write_text(json.dumps(claims), encoding="utf-8")
        contract = copy.deepcopy(contract or CONTRACT)
        contract["inputs"]["workspace"] = f"fixtures/repos/{workspace}"
        sha = frozen.freeze_to(run_dir, contract)
        before = snapshot(pristine, skip_cache=True)
        verdict = evaluate(verdict_contract or contract, str(ws), before, scfg or {}, None, run=validate or fake_validate)
        (run_dir / "verdict_0.json").write_text(json.dumps(verdict), encoding="utf-8")
        result = {"status": status, "stop_reason": "all criteria passed", "contract_sha": sha, "run_id": run_dir.name,
                  "verdict": {"iteration": 0, "outcome": verdict["outcome"], "failing": [],
                              "workspace_digest": verdict["workspace_digest"]},
                  "attempts": 1, "provenance": {"input": {"workspace": f"fixtures/repos/{workspace}",
                                                          "snapshot_sha256": digest(before), "intake": None},
                                                "argus": {"commit": "a" * 40, "dirty": False}}}
        (run_dir / "result.json").write_text(json.dumps(result), encoding="utf-8")
        if events:
            lines = [{"event": "llm_call_started", "call_id": "c1", "model": "fake:scripted", "worst_tokens": 100,
                      "worst_usd_nano": 5000},
                     {"event": "llm_call", "call_id": "c1", "status": "ok", "tokens": 80, "usd_nano": 3000}]
            (run_dir / "events.jsonl").write_text("".join(json.dumps(e) + "\n" for e in lines), encoding="utf-8")
        return run_dir

    def build(self, run_dir, **kw):
        kw = {"repo": self.repo, "sandbox_cfg": {}, "root": self.root, "validate": fake_validate, **kw}
        return review.build(run_dir, **kw)


@pytest.fixture
def proj(tmp_path):
    return Project(tmp_path)


FIX = {"src/shop.py": FIXED}


def prov(run_dir):
    return json.loads((run_dir / "review" / "provenance.json").read_text(encoding="utf-8"))


def failed_checks(run_dir):
    return [c["id"] for c in prov(run_dir)["checks"] if not c["ok"]]


def apply_to_clean_checkout(proj, run_dir, tmp_path):
    """What a reviewer does: a checkout of the base commit, then git apply."""
    co = tmp_path / "checkout"
    git(proj.repo, "worktree", "add", "-q", "--detach", str(co), proj.record["commit"])
    git(co, "apply", "--whitespace=nowarn", str(run_dir / "review" / "changes.patch"))
    return co


# ---- the package of a good run ----------------------------------------------------------------------------------

def test_a_done_run_gets_a_complete_valid_package(proj):
    run_dir = proj.run(writes=FIX)
    out = proj.build(run_dir)
    assert out["valid"] and out["problems"] == []
    assert sorted(p.name for p in (run_dir / "review").iterdir()) == sorted(review.FILES)
    p = prov(run_dir)
    assert p["valid"] and all(c["ok"] for c in p["checks"])
    assert [c["id"] for c in p["checks"]] == ["contract_frozen", "verdict_passed", "input_unchanged", "base_commit",
                                              "changes_in_scope", "changes_match_verdict", "patch_made",
                                              "patch_applies", "final_state_identical", "revalidation_matches"]
    assert p["base"]["commit"] == proj.record["commit"] and p["base"]["tree"] == proj.record["tree"]
    assert p["argus"] == {"commit": "a" * 40, "dirty": False} and p["models"] == ["fake:scripted"]
    assert p["cost"]["calls"] == 1 and p["cost"]["usd_nano"] == 3000 and p["cost"]["usd_complete"]
    assert p["contract"]["sha256"] == json.loads((run_dir / "result.json").read_text())["contract_sha"]
    assert p["patch"]["files"] == [{"path": "src/shop.py", "change": "M", "approved_test": False}]
    assert p["patch"]["sha256"] == hashlib.sha256((run_dir / "review" / "changes.patch").read_bytes()).hexdigest()
    assert p["validation_fresh"] == {"target": "pass"}
    assert "NOT READY" not in (run_dir / "review" / "PR.md").read_text()


def test_the_patch_applies_to_a_clean_checkout_and_gives_exactly_the_agents_files(proj, tmp_path):
    run_dir = proj.run(writes=FIX)
    proj.build(run_dir)
    co = apply_to_clean_checkout(proj, run_dir, tmp_path)
    assert (co / "src" / "shop.py").read_text() == FIXED
    assert not (co / "SUMMARY.json").exists()
    assert "SUMMARY" not in (run_dir / "review" / "changes.patch").read_text()


def test_building_twice_gives_the_same_bytes(proj):
    run_dir = proj.run(writes=FIX)
    proj.build(run_dir)
    first = {f: (run_dir / "review" / f).read_bytes() for f in review.FILES}
    shutil.rmtree(run_dir / "review")
    proj.build(run_dir)
    assert {f: (run_dir / "review" / f).read_bytes() for f in review.FILES} == first


def test_new_changed_deleted_ignored_binary_and_crlf_files_all_reach_the_patch(proj, tmp_path):
    crlf = b"one\r\ntwo\r\nthree\r\n"
    run_dir = proj.run(writes={**FIX, "src/new.py": "NEW = 1\n", "src/out.log": "ignored by .gitignore\n",
                               "src/blob.bin": bytes([0, 255, 1, 2, 0, 10, 13]), "notes/readme.txt": crlf,
                               "notes/deep/er/file.txt": "x\n"}, deletes=["src/extra.py"])
    out = proj.build(run_dir)
    assert out["valid"], out["problems"]
    changes = {f["path"]: f["change"] for f in prov(run_dir)["patch"]["files"]}
    assert changes == {"src/shop.py": "M", "src/new.py": "A", "src/out.log": "A", "src/blob.bin": "A",
                       "notes/readme.txt": "M", "notes/deep/er/file.txt": "A", "src/extra.py": "D"}
    co = apply_to_clean_checkout(proj, run_dir, tmp_path)
    assert (co / "src" / "blob.bin").read_bytes() == bytes([0, 255, 1, 2, 0, 10, 13])
    assert (co / "notes" / "readme.txt").read_bytes() == crlf and not (co / "src" / "extra.py").exists()


def test_a_deleted_directory_with_all_its_files_is_in_the_patch(proj):
    run_dir = proj.run(writes=FIX, deletes=["src/extra.py"])
    assert proj.build(run_dir)["valid"]
    assert {"path": "src/extra.py", "change": "D", "approved_test": False} in prov(run_dir)["patch"]["files"]


@POSIX
def test_an_executable_file_keeps_its_mode_and_a_new_executable_file_gets_one(proj, tmp_path):
    def post(ws):
        (ws / "tools" / "new.sh").write_text("#!/bin/sh\n")
        os.chmod(ws / "tools" / "new.sh", 0o755)
    run_dir = proj.run(writes={**FIX, "tools/run.sh": "#!/bin/sh\necho changed\n"}, post=post)
    out = proj.build(run_dir)
    assert out["valid"], out["problems"]
    co = apply_to_clean_checkout(proj, run_dir, tmp_path)
    assert os.stat(co / "tools" / "run.sh").st_mode & 0o100 and os.stat(co / "tools" / "new.sh").st_mode & 0o100
    assert not os.stat(co / "src" / "shop.py").st_mode & 0o100


@POSIX
def test_a_mode_change_alone_is_refused_because_the_verdict_cannot_see_it(proj):
    run_dir = proj.run(writes=FIX, post=lambda ws: os.chmod(ws / "src" / "extra.py", 0o755))
    out = proj.build(run_dir)
    assert not out["valid"] and "changes_match_verdict" in failed_checks(run_dir)


def test_the_agent_summary_cannot_close_its_fence_or_add_table_cells(proj):
    claims = {"claims": CLAIMS["claims"], "summary": "x\n`````\n## injected | cell\n<script>alert(1)</script>"}
    run_dir = proj.run(writes=FIX, claims=claims)
    proj.build(run_dir)
    text = (run_dir / "review" / "claims.md").read_text()
    start = text.index("## Agent's summary")
    block = text[start:]
    opening = next(l for l in block.splitlines() if l.startswith("`"))
    assert len(opening) > 5 and block.count(opening) == 2          # the fence is longer than any run inside
    assert "not evidence" in text.lower()


def test_what_was_never_verified_is_listed_and_never_a_criterion(proj):
    proj.task()
    run_dir = proj.run(writes=FIX, workspace="shoptask")
    proj.build(run_dir)
    claims_md = (run_dir / "review" / "claims.md").read_text()
    assert "Not verified automatically" in claims_md and "the message reads well" in claims_md
    assert "the message reads well" in (run_dir / "review" / "PR.md").read_text()
    assert "message reads well" not in (run_dir / "review" / "tests.md").read_text()


def test_the_tests_file_shows_the_verdict_and_the_fresh_result_per_required_test(proj):
    run_dir = proj.run(writes=FIX)
    proj.build(run_dir)
    text = (run_dir / "review" / "tests.md").read_text()
    assert "validation:target" in text and f"`{OLD_NODE}`" in text and "| status | pass | pass |" in text


# ---- an approved task: the new tests are part of the pull request ----------------------------------------------

def test_a_tasks_approved_tests_are_in_the_patch_as_new_files_and_marked(proj, tmp_path):
    proj.task()
    run_dir = proj.run(writes=FIX, workspace="shoptask")
    out = proj.build(run_dir)
    assert out["valid"], out["problems"]
    assert {"path": "tests/test_new.py", "change": "A", "approved_test": True} in prov(run_dir)["patch"]["files"]
    co = apply_to_clean_checkout(proj, run_dir, tmp_path)
    assert (co / "tests" / "test_new.py").read_text() == NEW_TEST


def test_a_task_record_that_does_not_match_the_input_is_refused(proj):
    rec = proj.task()
    rec["added"]["tests/test_new.py"] = "0" * 64
    (proj.root / "fixtures" / "intake" / "shoptask.json").write_text(json.dumps(rec), encoding="utf-8")
    run_dir = proj.run(writes=FIX, workspace="shoptask")
    assert not proj.build(run_dir)["valid"]
    assert failed_checks(run_dir)[0] in ("input_unchanged", "base_commit")


def test_a_new_test_that_already_exists_in_the_base_commit_is_refused(proj):
    proj.task(tests={"tests/test_old.py": OLD_TEST})
    # the "new" test is the existing file: input = base, not base + new tests
    run_dir = proj.run(writes=FIX, workspace="shoptask")
    assert not proj.build(run_dir)["valid"] and "base_commit" in failed_checks(run_dir)


# ---- refusals: nothing is built, or the package says NOT READY ---------------------------------------------------

@pytest.mark.parametrize("status", ["RUNNING", "BLOCKED", "FAILED_ACCEPTANCE", "FAILED_BUDGET"])
def test_a_run_that_is_not_done_gets_no_package(proj, status):
    run_dir = proj.run(writes=FIX, status=status)
    with pytest.raises(review.ReviewError, match="not DONE"):
        proj.build(run_dir)
    assert not (run_dir / "review").exists()


def test_a_package_is_never_overwritten_and_a_failed_build_leaves_nothing_behind(proj, monkeypatch):
    run_dir = proj.run(writes=FIX)
    proj.build(run_dir)
    before = (run_dir / "review" / "PR.md").read_bytes()
    with pytest.raises(review.ReviewError, match="already exists"):
        proj.build(run_dir)
    assert (run_dir / "review" / "PR.md").read_bytes() == before
    other = proj.run(writes=FIX)
    monkeypatch.setattr(review, "render_pr", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")))
    with pytest.raises(RuntimeError):
        proj.build(other)
    assert not (other / "review").exists() and not list(other.glob(".review-*"))


def test_a_verdict_that_did_not_pass_is_not_packaged_as_ready(proj):
    run_dir = proj.run(writes={})                                      # the bug is still there: the verdict fails
    out = proj.build(run_dir)
    assert not out["valid"] and failed_checks(run_dir) == ["verdict_passed"]
    assert (run_dir / "review" / "PR.md").read_text().startswith("> **NOT READY")
    assert not (run_dir / "review" / "changes.patch").exists()


def test_a_workspace_changed_after_the_verdict_is_refused(proj):
    run_dir = proj.run(writes=FIX)
    (run_dir / "workspace" / "src" / "shop.py").write_text(FIXED + "# sneaked in\n")
    assert not proj.build(run_dir)["valid"] and "verdict_passed" in failed_checks(run_dir)


def test_a_frozen_contract_changed_after_the_run_is_refused(proj):
    run_dir = proj.run(writes=FIX)
    c = json.loads((run_dir / "contract.json").read_text())
    c["limits"]["max_usd"] = 5
    (run_dir / "contract.json").write_text(json.dumps(c))
    assert not proj.build(run_dir)["valid"] and failed_checks(run_dir) == ["contract_frozen"]


def test_an_input_changed_since_the_run_started_is_refused(proj):
    run_dir = proj.run(writes=FIX)
    (proj.root / "fixtures" / "repos" / "shop" / "src" / "shop.py").write_text(BUGGY + "# edited\n")
    assert not proj.build(run_dir)["valid"] and "input_unchanged" in failed_checks(run_dir)


def test_an_input_without_an_intake_record_has_no_base_commit_and_is_refused(proj):
    (proj.root / "fixtures" / "intake" / "shop.json").unlink()
    run_dir = proj.run(writes=FIX)
    out = proj.build(run_dir)
    assert not out["valid"] and "intake" in out["problems"][0]


def test_a_repository_without_the_base_commit_is_refused(proj, tmp_path):
    other = tmp_path / "other"
    make_repo(other, {"a.txt": b"a\n"})
    run_dir = proj.run(writes=FIX)
    assert not proj.build(run_dir, repo=other)["valid"] and "base_commit" in failed_checks(run_dir)


def test_a_repository_whose_commit_is_not_the_intake_tree_is_refused(proj):
    run_dir = proj.run(writes=FIX)
    rec_path = proj.root / "fixtures" / "intake" / "shop.json"
    rec = json.loads(rec_path.read_text())
    rec["tree"] = "f" * 40
    rec_path.write_text(json.dumps(rec))
    assert not proj.build(run_dir)["valid"] and "base_commit" in failed_checks(run_dir)


@pytest.mark.parametrize("path, why", [("tests/test_old.py", "protected"), ("conftest.py", "protected"),
                                       ("README.md", "outside the writable scope")])
def test_a_change_outside_the_scope_is_refused_even_if_the_verdict_says_pass(proj, path, why):
    # the verdict is reached under a permissive contract, then the run's own frozen contract is the strict one
    loose = copy.deepcopy(CONTRACT)
    loose["scope"] = {"writable": ["**"], "protected": ["conftest.py"]}
    if path == "conftest.py":
        loose["scope"]["protected"] = ["tests/**"]
    run_dir = proj.run(writes={**FIX, path: "# changed\n"}, verdict_contract=loose)
    out = proj.build(run_dir)
    assert not out["valid"] and "changes_in_scope" in failed_checks(run_dir)
    assert why in " ".join(out["problems"])


def test_a_change_to_an_approved_test_is_refused(proj):
    proj.task()
    loose = copy.deepcopy(CONTRACT)
    loose["scope"] = {"writable": ["**"], "protected": ["conftest.py"]}
    run_dir = proj.run(writes={**FIX, "tests/test_new.py": "def test_new():\n    pass\n"}, workspace="shoptask",
                       verdict_contract=loose)
    assert not proj.build(run_dir)["valid"] and "changes_in_scope" in failed_checks(run_dir)


def test_a_path_the_intake_excluded_is_refused(proj, tmp_path):
    repo = tmp_path / "ex_repo"
    make_repo(repo, {**BASE, "verification/log.txt": b"big\n"})
    p2 = Project.__new__(Project)
    p2.root, p2.repo, p2.n = tmp_path / "proj2", repo, 0
    p2.root.mkdir()
    p2.record = intake.intake(repo, "HEAD", "shop", exclude=["verification"], root=p2.root)
    loose = copy.deepcopy(CONTRACT)
    loose["scope"]["writable"] = ["**"]
    run_dir = p2.run(writes={**FIX, "verification/log.txt": "forged\n"}, verdict_contract=loose, contract=loose)
    assert not p2.build(run_dir)["valid"] and "changes_in_scope" in failed_checks(run_dir)


def test_a_workspace_that_changed_nothing_is_not_a_package(proj):
    always = lambda spec, ws, cfg, log=None: {**fake_validate(spec, ws, cfg), "status": "pass"}   # noqa: E731
    run_dir = proj.run(writes={}, claims={"claims": [], "summary": "nothing"}, validate=always)
    assert not proj.build(run_dir, validate=always)["valid"] and "has_changes" in failed_checks(run_dir)


def test_a_verdict_that_lists_other_files_than_the_workspace_differs_by_is_refused(proj):
    run_dir = proj.run(writes={**FIX, "src/new.py": "N = 1\n"})
    v = json.loads((run_dir / "verdict_0.json").read_text())
    for c in v["criteria"]:
        if c["id"] == "scope:protected":
            c["evidence"]["diff"]["added"] = [p for p in c["evidence"]["diff"]["added"] if p != "src/new.py"]
    (run_dir / "verdict_0.json").write_text(json.dumps(v))
    assert not proj.build(run_dir)["valid"] and "changes_match_verdict" in failed_checks(run_dir)


def test_a_workspace_with_a_git_directory_is_refused_and_does_not_touch_the_mirror(proj):
    loose = copy.deepcopy(CONTRACT)
    loose["scope"]["writable"] = ["**"]
    run_dir = proj.run(writes={**FIX, ".git/config": "[core]\n"}, contract=loose, verdict_contract=loose)
    assert not proj.build(run_dir)["valid"] and "changes_in_scope" in failed_checks(run_dir)


# ---- the patch is verified, not trusted ----------------------------------------------------------------------------

def bad_mirror(base_dir, final_dir, work):
    """A mirror that overwrites but never deletes: a file the agent removed stays in the patched tree."""
    repo = Path(work) / "bad"
    shutil.copytree(base_dir, repo)
    git(repo.parent, "init", "-q", str(repo))
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "base")
    shutil.copytree(final_dir, repo, dirs_exist_ok=True, ignore=shutil.ignore_patterns("SUMMARY.json"))
    git(repo, "add", "-A")
    return git(repo, "diff", "--cached", "--binary", "--full-index").encode()


def test_a_patch_that_forgets_a_deleted_file_is_caught_by_the_whole_tree_comparison(proj, monkeypatch):
    monkeypatch.setattr(review, "make_patch", bad_mirror)
    run_dir = proj.run(writes=FIX, deletes=["src/extra.py"])
    out = proj.build(run_dir)
    assert not out["valid"] and "final_state_identical" in failed_checks(run_dir)
    assert "src/extra.py" in " ".join(out["problems"])


def test_a_patch_that_does_not_apply_is_refused(proj, monkeypatch):
    monkeypatch.setattr(review, "make_patch", lambda *a: b"diff --git a/x b/x\n--- a/x\n+++ b/x\n@@ -1 +1 @@\n-a\n+b\n")
    run_dir = proj.run(writes=FIX)
    assert not proj.build(run_dir)["valid"] and "patch_applies" in failed_checks(run_dir)


def test_a_patch_that_changes_a_file_the_agent_did_not_is_caught(proj, monkeypatch):
    real = review.make_patch

    def extra(base_dir, final_dir, work):
        patch = real(base_dir, final_dir, work).decode()
        patch += ("diff --git a/src/extra.py b/src/extra.py\n--- a/src/extra.py\n+++ b/src/extra.py\n@@ -1 +1 @@\n"
                  "-EXTRA = 1\n+EXTRA = 2\n")
        return patch.encode()
    monkeypatch.setattr(review, "make_patch", extra)
    run_dir = proj.run(writes=FIX)
    assert not proj.build(run_dir)["valid"] and "final_state_identical" in failed_checks(run_dir)


def test_every_validation_is_run_again_on_the_patched_tree_not_on_the_runs_workspace(proj):
    run_dir = proj.run(writes=FIX)
    seen = []

    def spy(spec, workspace, cfg, log=None):
        seen.append((Path(workspace), (Path(workspace) / "SUMMARY.json").exists(),
                     (Path(workspace) / ".git").exists()))
        return fake_validate(spec, workspace, cfg, log)
    proj.build(run_dir, validate=spy)
    assert len(seen) == 1 and seen[0][0] != run_dir / "workspace" and seen[0][1:] == (False, False)


def test_a_fresh_result_that_differs_from_the_verdict_is_refused(proj):
    run_dir = proj.run(writes=FIX)

    def other(spec, workspace, cfg, log=None):
        v = fake_validate(spec, workspace, cfg, log)
        v["evidence"]["tests_run"] = 2
        return v
    out = proj.build(run_dir, validate=other)
    assert not out["valid"] and failed_checks(run_dir) == ["revalidation_matches"] and "tests_run" in out["problems"][0]


def test_a_validation_that_fails_or_is_blocked_fresh_is_refused(proj):
    for status in ("fail", "blocked"):
        run_dir = proj.run(writes=FIX)
        out = proj.build(run_dir, validate=lambda spec, ws, cfg, log=None, s=status:
                         {"id": "validation:target", "layer": "C", "status": s, "reason": "sandbox unavailable",
                          "evidence": {}})
        assert not out["valid"] and failed_checks(run_dir) == ["revalidation_matches"]
        assert (run_dir / "review" / "PR.md").read_text().startswith("> **NOT READY")


# ---- the script ----------------------------------------------------------------------------------------------------

def test_the_script_builds_a_package_and_exits_by_validity(proj, tmp_path, monkeypatch, capsys):
    pytest.importorskip("langgraph", reason="the script loads the config through runner.py; the VM runs this")
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
    import build_review
    monkeypatch.setattr(build_review, "ROOT", proj.root)
    run_dir = proj.run(writes=FIX)
    rc = build_review.main(["--run", str(run_dir), "--repo", str(proj.repo)], validate=fake_validate)
    assert rc == 0 and (run_dir / "review" / "PR.md").exists()
    assert json.loads(capsys.readouterr().out)["valid"] is True
    assert build_review.main(["--run", str(run_dir), "--repo", str(proj.repo)], validate=fake_validate) == 2


# ---- end to end: a scripted model works on an approved task, then the package is built --------------------------
# (needs langgraph and the path jail, so these run on the VM like tests/test_codetask.py)

def call(name, args, id):
    from models.fake import reply
    return reply(tool_calls=[{"name": name, "args": args, "id": id}], input_tokens=500, output_tokens=60)


@pytest.fixture
def vm():
    pytest.importorskip("langgraph", reason="the run needs langgraph; the VM runs this")
    if sys.platform == "win32":
        pytest.skip("the path jail needs openat; the VM runs these")


def e2e(proj, monkeypatch, tmp_path, script):
    from codetask import run as run_module
    from models.fake import StrictScriptedChatModel
    from runner import load_config
    monkeypatch.setattr(run_module, "ROOT", proj.root)
    contract = copy.deepcopy(CONTRACT)
    contract["inputs"]["workspace"] = "fixtures/repos/shoptask"
    rec = proj.task()
    rec["contract_sha256"] = ct.freeze(contract)[1]
    (proj.root / "fixtures" / "intake" / "shoptask.json").write_text(json.dumps(rec), encoding="utf-8")
    path = tmp_path / "contract.json"
    path.write_text(json.dumps(contract), encoding="utf-8")
    cfg = load_config()
    cfg["roles"]["coder"]["model"] = "fake:scripted"
    model = StrictScriptedChatModel(script=list(script))
    result = run_module.run_code_task(contract_path=path, run_id="e2e", runs_dir=tmp_path / "runs", cfg=cfg,
                                      models={"coder": model}, validate=fake_validate,
                                      preflight=lambda: (True, "ok"))
    return result, tmp_path / "runs" / "e2e"


def test_end_to_end_a_scripted_fix_of_an_approved_task_becomes_a_valid_package(vm, proj, monkeypatch, tmp_path):
    write = call("WriteFile", {"path": "src/shop.py", "content": FIXED}, "w1")
    finish = call("Finish", {"claims": CLAIMS["claims"], "summary": "floored at zero"}, "f1")
    result, run_dir = e2e(proj, monkeypatch, tmp_path, [write, finish])
    assert result["status"] == "DONE"
    out = proj.build(run_dir)
    assert out["valid"], out["problems"]
    p = prov(run_dir)
    assert p["models"] == ["fake:scripted"] and p["cost"]["usd"] == pytest.approx(result["usd_billed"])
    assert p["cost"]["calls"] == result["llm_calls"] == 2
    assert p["input"]["intake"]["kind"] == "task" and p["base"]["commit"] == proj.record["commit"]
    assert {(f["path"], f["change"], f["approved_test"]) for f in p["patch"]["files"]} == {
        ("src/shop.py", "M", False), ("tests/test_new.py", "A", True)}
    assert "floored at zero" in (run_dir / "review" / "claims.md").read_text()


def test_end_to_end_an_attempt_to_change_an_approved_test_gets_no_package(vm, proj, monkeypatch, tmp_path):
    bad = call("WriteFile", {"path": "tests/test_new.py", "content": "def test_new():\n    pass\n"}, "b1")
    lazy = call("Finish", {"claims": CLAIMS["claims"], "summary": "done"}, "f1")
    result, run_dir = e2e(proj, monkeypatch, tmp_path, [bad, lazy, lazy])
    assert result["status"] == "FAILED_ACCEPTANCE"
    assert (run_dir / "workspace" / "tests" / "test_new.py").read_text() == NEW_TEST      # the write was refused
    with pytest.raises(review.ReviewError, match="not DONE"):
        proj.build(run_dir)
    assert not (run_dir / "review").exists()


# ---- with the real sandbox (environment argus; skipped, and not counted as passing, without it) ---------------------

@pytest.fixture
def scfg():
    pytest.importorskip("langgraph", reason="SANDBOX NOT AVAILABLE: the config is loaded through runner.py")
    from runner import load_config
    from tools import sandbox as sb
    c = {**(load_config().get("sandbox") or {}), "kind": "docker"}
    ok, why = sb.status({**c, "environment": "argus"})
    if not ok:
        pytest.skip(f"SANDBOX NOT AVAILABLE: {why}")
    return c


def real_contract():
    c = copy.deepcopy(CONTRACT)
    c["validation"] = [
        {"id": "target", "executable": "python", "args": ["-m", "pytest", "tests/test_new.py"], "timeout_s": 120,
         "min_tests": 1, "max_skipped": 0, "must_pass": ["tests/test_new.py::test_total_never_negative"],
         "environment": "argus"},
        {"id": "regression", "executable": "python", "args": ["-m", "pytest", "tests/test_old.py"], "timeout_s": 120,
         "min_tests": 1, "max_skipped": 0, "must_pass": [OLD_NODE], "environment": "argus"}]
    return c


def test_with_the_real_sandbox_a_fixed_task_is_a_valid_package_and_the_fresh_runs_repeat_the_verdict(proj, scfg):
    from acceptance.validation import run_validation
    proj.task()
    run_dir = proj.run(writes=FIX, workspace="shoptask", contract=real_contract(), scfg=scfg,
                       validate=lambda spec, ws, cfg, log=None: run_validation(spec, ws, cfg, log))
    out = proj.build(run_dir, validate=run_validation, sandbox_cfg=scfg)
    assert out["valid"], out["problems"]
    assert prov(run_dir)["validation_fresh"] == {"target": "pass", "regression": "pass"}
    text = (run_dir / "review" / "tests.md").read_text()
    assert "`tests/test_new.py::test_total_never_negative`" in text and "| ok | ok |" in text
