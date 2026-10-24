"""docs/reviews/SPEC_SWE_PILOT.md: a job's sandbox environment (pinned image, fail closed), the per-environment image
build, scripts/swe_grade.py (SWE-bench style grading), and that the official tests are never visible to the drafter
or the agent (intake takes the commit's tree only; the sandbox mounts the workspace only).

The router tests use test_router's scripted models and injected validation. The grader tests use a small git
repository whose later commits hold the fix and the official tests, and a local pytest as the validation; one test
grades in the real sandbox (the argus environment, which scripts/verify.sh builds)."""
import copy
import hashlib
import json
import os
import subprocess
import sys
import uuid
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_codetask as tc  # noqa: E402
import test_draft as tdr  # noqa: E402
import test_router as tr  # noqa: E402

from acceptance import contract as ct  # noqa: E402
from acceptance import intake  # noqa: E402
from acceptance.workspace import snapshot  # noqa: E402
from codetask import status as st  # noqa: E402
from router import job as rj  # noqa: E402
from tools import sandbox as sb  # noqa: E402

pytestmark = pytest.mark.skipif(sys.platform == "win32", reason="flock, the path jail and the sandbox need posix")

ROOT = Path(__file__).resolve().parent.parent
IMG = "sha256:" + "e" * 64
OTHER = "sha256:" + "f" * 64


@pytest.fixture(autouse=True)
def no_image_overrides(monkeypatch):
    """The machine's image overrides (verify.sh sets them) must not decide these tests; some set them on purpose."""
    for var in ("ARGUS_SANDBOX_IMAGE", "ARGUS_SANDBOX_IMAGE_ARGUS", "ARGUS_SANDBOX_IMAGE_SYMPY"):
        monkeypatch.delenv(var, raising=False)


def env_config(image=IMG):
    c = tr.cfg()
    c["sandbox"] = {**c["sandbox"], "environments": {"argus": {"image": "sha256:" + "b" * 64},
                                                     "sympy": {"image": image}}}
    return c


# ---- 2.1 the job's environment -------------------------------------------------------------------------------------

def test_a_job_records_its_environment_and_image_and_its_drafter_writes_for_it(tmp_path):
    e = tr.Env(tmp_path, config=env_config())
    job = e.code(environment="sympy")
    assert job.data["inputs"]["environment"] == "sympy" and job.data["environment_image"] == IMG
    draft = json.loads((job.runs / "jtest-d1" / "draft.json").read_text())
    assert {v.get("environment") for v in draft["contract"]["validation"]} == {"sympy"}
    text = rj.status("jtest", jobs_dir=e.jobs, cfg=e.cfg)
    assert "environment sympy, image eeeeeeeeeeee" in text and "validation target (env sympy):" in text
    assert "changed since the job started" not in text


def test_without_an_environment_a_job_is_as_before(tmp_path):
    e = tr.Env(tmp_path, config=env_config())
    job = e.code()
    assert "environment" not in job.data["inputs"] and "environment_image" not in job.data
    draft = json.loads((job.runs / "jtest-d1" / "draft.json").read_text())
    assert {v.get("environment") for v in draft["contract"]["validation"]} == {"argus"}     # config.yaml's drafter


@pytest.mark.parametrize("name, image, why", [("nosuch", IMG, "unknown sandbox environment"),
                                              ("sympy", None, "has no image")])
def test_an_unknown_environment_or_one_without_an_image_creates_no_job(tmp_path, monkeypatch, name, image, why):
    monkeypatch.setenv("ARGUS_SANDBOX_IMAGE", OTHER)              # usable images that must never stand in for it
    monkeypatch.setenv("ARGUS_SANDBOX_IMAGE_ARGUS", OTHER)
    e = tr.Env(tmp_path, config=env_config(image))
    with pytest.raises(rj.Refused, match=why):
        e.code(environment=name)
    assert not (e.jobs / "jtest").exists() and e.drafter.calls == []


def test_an_environment_without_an_image_never_runs_on_another_image(monkeypatch):
    monkeypatch.setenv("ARGUS_SANDBOX_IMAGE", OTHER)
    monkeypatch.setenv("ARGUS_SANDBOX_IMAGE_ARGUS", OTHER)
    cfg = {"kind": "docker", "image": OTHER, "environments": {"argus": {"image": OTHER}, "sympy": {"image": None}}}
    assert sb.environment_image(cfg, "sympy") == (None, None) and sb.settings({**cfg, "environment": "sympy"})["image"] is None
    ok, why = sb.status({**cfg, "environment": "sympy"})
    assert not ok and "has no image configured" in why
    image, problem = rj.environment_pin({"sandbox": cfg}, "sympy")
    assert image is None and "never falls back" in problem
    monkeypatch.setenv("ARGUS_SANDBOX_IMAGE_SYMPY", IMG)                # only its own variable gives it an image
    assert rj.environment_pin({"sandbox": cfg}, "sympy") == (IMG, None)


def test_a_rebuilt_image_stops_the_job_with_both_ids_and_suggests_abandon(tmp_path, monkeypatch):
    e = tr.Env(tmp_path, config=env_config())
    e.code(environment="sympy")
    sha = e.sha()
    e.cfg = env_config(OTHER)                                      # the image was rebuilt: a new id
    job = e.job()
    before = job.file.read_bytes()
    calls = [
        lambda: rj.approve("jtest", sha=sha, cfg=e.cfg, deps=e.deps, sandbox_cfg={}, jobs_dir=e.jobs),
        lambda: rj.redraft("jtest", cfg=e.cfg, deps=e.deps, jobs_dir=e.jobs),
        lambda: rj.resume("jtest", cfg=e.cfg, deps=e.deps, jobs_dir=e.jobs),
        lambda: rj.retry("jtest", cfg=e.cfg, deps=e.deps, jobs_dir=e.jobs),
    ]
    for c in calls:
        with pytest.raises(rj.Refused, match=f"was {IMG}, now {OTHER}"):
            c()
    assert job.file.read_bytes() == before and e.coder.calls == [] and len(e.drafter.calls) == 1
    text = rj.status("jtest", jobs_dir=e.jobs, cfg=e.cfg)
    assert "changed since the job started" in text and 'next: argus abandon jtest "<why>"' in text
    assert rj.abandon("jtest", "image rebuilt", deps=e.deps, jobs_dir=e.jobs).data["state"] == rj.ABANDONED


def test_the_approve_screen_names_the_environment_of_each_validation(tmp_path):
    e = tr.Env(tmp_path, config=env_config())
    e.code(environment="sympy")
    e.approve()
    screen = [c for c in e.confirms if "approve and run the agent" in c][0]
    assert "environment sympy, image eeeeeeeeeeee" in screen and "validation target (env sympy):" in screen


def test_the_cli_passes_the_environment(tmp_path, monkeypatch):
    import importlib.util
    spec = importlib.util.spec_from_file_location("argus_cli_e", ROOT / "scripts" / "argus.py")
    cli = importlib.util.module_from_spec(spec)
    monkeypatch.syspath_prepend(str(ROOT / "scripts"))
    spec.loader.exec_module(cli)
    got = {}
    monkeypatch.setattr(rj, "start_code", lambda **kw: got.update(kw) or (_ for _ in ()).throw(rj.Refused("stop")))
    rc = cli.main(["code", "--repo", str(tmp_path), "--commit", "HEAD", "--issue", "x", "--environment", "sympy"],
                  deps=rj.Deps())
    assert rc == 2 and got["environment"] == "sympy"
    cli.main(["code", "--repo", str(tmp_path), "--commit", "HEAD", "--issue", "x"], deps=rj.Deps())
    assert got["environment"] is None


# ---- setup_problems for an environment other than argus (draft check and setup, #180) -------------------------------

def test_the_draft_check_refuses_an_unconfigured_environment_and_takes_a_configured_one(tmp_path):
    d = copy.deepcopy(tdr.DRAFT)
    for v in d["contract"]["validation"]:
        v["environment"] = "sympy"
    r = tdr.run_check(tdr.make_root(tmp_path / "a"), None, {"environments": {"argus": {}}}, draft=d)
    assert not r["ok"] and r["problems"] == ["contract: unknown sandbox environment(s) ['sympy'] (configured: ['argus'])"]
    c = tdr.dr.build_contract(d, task="t", workspace="fixtures/repos/t", issue="i", max_usd=0.5, max_iterations=2)
    assert not [p for p in ct.setup_problems(c, {}, profiles=None, environments_configured={"sympy": {}})
                if "sandbox environment" in p]


def test_setup_blocks_an_unconfigured_environment_and_runs_a_configured_one(tmp_path):
    (tmp_path / "a").mkdir()
    (tmp_path / "b").mkdir()
    r, model, _ = tc.run(tmp_path / "a", [tc.WRITE, tc.FINISH], contract=tc.with_environment("sympy"),
                         config=tc.env_cfg())
    assert r["status"] == st.BLOCKED and "unknown sandbox environment(s) ['sympy']" in r["stop_reason"]
    assert len(model.calls) == 0
    c = tc.env_cfg()
    c["sandbox"]["environments"]["sympy"] = {"image": IMG}
    path = tmp_path / "b" / "contract.json"
    path.write_text(json.dumps(tc.with_environment("sympy")))
    seen = []
    model = tc.StrictScriptedChatModel(script=[tc.WRITE, tc.FINISH])
    r = tc.run_code_task(contract_path=path, run_id="t", runs_dir=tmp_path / "b" / "runs", cfg=c,
                         models={"coder": model}, validate=tc.fake_validate, preflight=lambda: (True, "ok"),
                         env_preflight=lambda name: seen.append(name) or (True, "ok"))
    assert r["status"] == st.DONE and seen == ["sympy"]


# ---- 2.2 the image build script ------------------------------------------------------------------------------------

def test_the_argus_build_script_is_the_environment_script_with_argus():
    text = (ROOT / "scripts" / "build_argus_sandbox_image.sh").read_text()
    assert 'exec bash scripts/build_env_sandbox_image.sh argus "${1:-.venv-verify}" requirements.txt' in text
    env = (ROOT / "scripts" / "build_env_sandbox_image.sh").read_text()
    for must in ('"argus-sandbox-$NAME:py$VER"', '".sandbox_image_$NAME"', "--mtime='2026-01-01 00:00:00Z'"):
        assert must in env, must
    bad = subprocess.run(["bash", str(ROOT / "scripts" / "build_env_sandbox_image.sh"), "../x", "v"],
                         capture_output=True, text=True)
    assert bad.returncode != 0 and "lower-case" in bad.stderr


# ---- the grader ----------------------------------------------------------------------------------------------------

def git(repo, *args):
    return subprocess.run(["git", "-C", str(repo), "-c", "user.name=t", "-c", "user.email=t@t", *args],
                          check=True, capture_output=True, text=True).stdout


BUGGY = "def inc(x):\n    return x\n"
FIXED = "def inc(x):\n    return x + 1\n"
OLD_TESTS = "from pkg.calc import inc\n\n\ndef test_ok():\n    assert inc(0) in (0, 1)\n"
NEW_TESTS = OLD_TESTS + "\n\ndef test_inc():\n    assert inc(1) == 2\n"


@pytest.fixture
def swe(tmp_path):
    """A repository whose later commits hold the maintainers' fix and the official tests (as SWE-bench's do), and an
    instance directory made from them."""
    repo = tmp_path / "repo"
    (repo / "pkg").mkdir(parents=True)
    (repo / "tests").mkdir()
    (repo / "pkg" / "__init__.py").write_text("")
    (repo / "pkg" / "calc.py").write_text(BUGGY)
    (repo / "tests" / "test_calc.py").write_text(OLD_TESTS)
    (repo / "conftest.py").write_text("")
    git(tmp_path, "init", "-q", str(repo))
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "base")
    base = git(repo, "rev-parse", "HEAD").strip()
    (repo / "pkg" / "calc.py").write_text(FIXED)
    (repo / "ANSWER_FROM_THE_FUTURE.txt").write_text("the fix is x + 1\n")
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "fix")
    fix = git(repo, "rev-parse", "HEAD").strip()
    (repo / "tests" / "test_calc.py").write_text(NEW_TESTS)
    git(repo, "commit", "-qam", "tests")
    inst = tmp_path / "inst"
    inst.mkdir()
    (inst / "base_commit.txt").write_text(base)
    (inst / "patch.diff").write_text(git(repo, "diff", base, fix, "--", "pkg"))
    (inst / "test_patch.diff").write_text(git(repo, "diff", fix, "HEAD", "--", "tests"))
    (inst / "FAIL_TO_PASS.txt").write_text(json.dumps(["test_inc"]))
    (inst / "PASS_TO_PASS.txt").write_text(json.dumps(["test_ok"]))
    return {"repo": repo, "inst": inst, "base": base, "tmp": tmp_path}


def review_of(tmp, patch_text, approved=()):
    d = tmp / f"review_{uuid.uuid4().hex[:6]}"
    d.mkdir()
    (d / "changes.patch").write_text(patch_text)
    sha = hashlib.sha256(patch_text.encode()).hexdigest()
    files = [{"path": p, "change": "A", "approved_test": True} for p in approved]
    (d / "provenance.json").write_text(json.dumps({"patch": {"sha256": sha, "files": files}}))
    return d, sha


def local_pytest(spec, workspace, sandbox_cfg, log=None):
    """A validation without the sandbox: pytest in the workspace, each required node ok or FAIL."""
    r = subprocess.run([sys.executable, "-m", "pytest", "-q", "-rA", "-p", "no:cacheprovider", *spec["args"][2:]],
                       cwd=workspace, capture_output=True, text=True)
    passed = {l.split()[1] for l in r.stdout.splitlines() if l.startswith("PASSED ")}
    must = {n: "ok" if n in passed else "FAIL" for n in spec["must_pass"]}
    ok = r.returncode == 0
    return {"id": f"validation:{spec['id']}", "status": "pass" if ok else "fail", "reason": "",
            "evidence": {"must_pass": must, "tests_run": len(passed), "failures": 0 if ok else 1, "errors": 0,
                         "skipped": 0, "exit_code": r.returncode}}


def grader():
    import importlib.util
    spec = importlib.util.spec_from_file_location("swe_grade_t", ROOT / "scripts" / "swe_grade.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def grade(swe, review, sha, validate=local_pytest, environment="argus", sandbox=None):
    m = grader()
    out = swe["tmp"] / f"grade_{uuid.uuid4().hex[:6]}.json"
    rc = m.main(["--instance", str(swe["inst"]), "--repo", str(swe["repo"]), "--review", str(review), "--sha", sha,
                 "--environment", environment, "--out", str(out)], validate=validate,
                sandbox=sandbox or {"environments": {"argus": {"image": IMG}}})
    return rc, (json.loads(out.read_text()) if out.exists() else None)


def test_the_maintainers_fix_resolves_and_no_fix_does_not(swe):
    rc, g = grade(swe, *review_of(swe["tmp"], (swe["inst"] / "patch.diff").read_text()))
    assert rc == 0 and g["resolved"] is True
    assert g["FAIL_TO_PASS"] == {"test_inc": "pass"} and g["PASS_TO_PASS"] == {"test_ok": "pass"}
    assert g["test_files"] == ["tests/test_calc.py"] and g["base_commit"] == swe["base"]
    rc, g = grade(swe, *review_of(swe["tmp"], ""))
    assert rc == 0 and g["resolved"] is False and g["FAIL_TO_PASS"] == {"test_inc": "fail"}


def test_only_the_reviewed_patch_is_graded(swe):
    calls = []
    d, sha = review_of(swe["tmp"], (swe["inst"] / "patch.diff").read_text())
    rc, g = grade(swe, d, "0" * 64, validate=lambda *a, **k: calls.append(a))
    assert rc == 2 and g is None and calls == []
    prov = json.loads((d / "provenance.json").read_text())
    prov["patch"]["sha256"] = "1" * 64                                  # the file is not the package's patch
    (d / "provenance.json").write_text(json.dumps(prov))
    rc, g = grade(swe, d, sha, validate=lambda *a, **k: calls.append(a))
    assert rc == 2 and g is None and calls == []


def test_the_official_tests_win_over_the_agents_changes_to_the_same_file(swe):
    # the agent "fixed" nothing but rewrote the test file so that its own test passes
    weak = OLD_TESTS + "\n\ndef test_inc():\n    assert inc(1) == 1\n"
    work = swe["tmp"] / "work"
    subprocess.run(["git", "clone", "-q", str(swe["repo"]), str(work)], check=True)
    git(work, "checkout", "-q", swe["base"])
    (work / "tests" / "test_calc.py").write_text(weak)
    patch = git(work, "diff")
    rc, g = grade(swe, *review_of(swe["tmp"], patch))
    assert rc == 0 and g["resolved"] is False and g["FAIL_TO_PASS"] == {"test_inc": "fail"}


def test_a_failing_pass_to_pass_test_means_not_resolved(swe):
    work = swe["tmp"] / "work2"
    subprocess.run(["git", "clone", "-q", str(swe["repo"]), str(work)], check=True)
    git(work, "checkout", "-q", swe["base"])
    (work / "pkg" / "calc.py").write_text("def inc(x):\n    return x + 1 if x else 5\n")    # test_ok breaks
    rc, g = grade(swe, *review_of(swe["tmp"], git(work, "diff")))
    assert rc == 0 and g["resolved"] is False
    assert g["FAIL_TO_PASS"] == {"test_inc": "pass"} and g["PASS_TO_PASS"] == {"test_ok": "fail"}


def test_a_missing_or_ambiguous_name_is_not_passing(swe):
    fix = (swe["inst"] / "patch.diff").read_text()
    (swe["inst"] / "PASS_TO_PASS.txt").write_text(json.dumps(["test_ok", "test_nowhere"]))
    rc, g = grade(swe, *review_of(swe["tmp"], fix))
    assert rc == 0 and g["resolved"] is False and g["PASS_TO_PASS"] == {"test_ok": "pass", "test_nowhere": "missing"}
    # the same name defined in two of test_patch's files: ambiguous, never guessed
    tp = (swe["inst"] / "test_patch.diff").read_text()
    other = ("diff --git a/tests/test_more.py b/tests/test_more.py\nnew file mode 100644\n--- /dev/null\n"
             "+++ b/tests/test_more.py\n@@ -0,0 +1,2 @@\n+def test_inc():\n+    assert True\n")
    (swe["inst"] / "test_patch.diff").write_text(tp + other)
    (swe["inst"] / "PASS_TO_PASS.txt").write_text(json.dumps(["test_ok"]))
    rc, g = grade(swe, *review_of(swe["tmp"], fix))
    assert rc == 0 and g["resolved"] is False and g["FAIL_TO_PASS"] == {"test_inc": "missing"}


def test_the_approved_tests_are_also_run_on_the_maintainers_fix(swe):
    work = swe["tmp"] / "work3"
    subprocess.run(["git", "clone", "-q", str(swe["repo"]), str(work)], check=True)
    git(work, "checkout", "-q", swe["base"])
    (work / "pkg" / "calc.py").write_text(FIXED)
    (work / "tests" / "test_drafted.py").write_text("from pkg.calc import inc\n\n\ndef test_two():\n"
                                                    "    assert inc(2) == 3\n")
    git(work, "add", "-A")
    rc, g = grade(swe, *review_of(swe["tmp"], git(work, "diff", "--cached"), approved=["tests/test_drafted.py"]))
    assert rc == 0 and g["resolved"] is True
    assert g["drafter_tests_on_reference"] == {"files": ["tests/test_drafted.py"], "status": "pass", "tests_run": 1,
                                               "failures": 0, "errors": 0}


def sandbox_or_skip(monkeypatch):
    """The sandbox config as approve_draft builds it, with the image overrides set through monkeypatch (so they end
    with the test) from the git-ignored image files when the environment does not set them."""
    for var, f in (("ARGUS_SANDBOX_IMAGE", ".sandbox_image"), ("ARGUS_SANDBOX_IMAGE_ARGUS", ".sandbox_image_argus")):
        value = os.environ.get(var) or ((ROOT / f).read_text().strip() if (ROOT / f).exists() else None)
        if value:
            monkeypatch.setenv(var, value)
    sys.path.insert(0, str(ROOT / "scripts"))
    from approve_draft import sandbox_cfg
    c = sandbox_cfg()
    ok, why = sb.status({**c, "environment": "argus"})
    if not ok:
        pytest.skip(f"SANDBOX NOT AVAILABLE: {why}")
    return c


def test_the_grader_in_the_real_sandbox(swe, monkeypatch):
    c = sandbox_or_skip(monkeypatch)
    from acceptance.validation import run_validation
    rc, g = grade(swe, *review_of(swe["tmp"], (swe["inst"] / "patch.diff").read_text()), validate=run_validation,
                  sandbox=c)
    assert rc == 0 and g["resolved"] is True and g["image"] == sb.environment_image(c, "argus")[0]


# ---- 2.4 the official tests are not visible --------------------------------------------------------------------------

def test_an_intake_holds_the_commits_tree_only(swe):
    root = swe["tmp"] / "root"
    rec = intake.intake(swe["repo"], swe["base"], "demo", root=root)
    snap = snapshot(root / "fixtures" / "repos" / "demo")
    assert rec["commit"] == swe["base"] and not [p for p in snap if p == ".git" or p.startswith(".git/")]
    assert "ANSWER_FROM_THE_FUTURE.txt" not in snap and (root / "fixtures" / "repos" / "demo" / "pkg" / "calc.py"
                                                         ).read_text() == BUGGY
    assert sorted(snap) == sorted(git(swe["repo"], "ls-tree", "-r", "--name-only", swe["base"]).split())


def test_nothing_of_the_host_but_the_workspace_is_visible_in_the_sandbox(tmp_path, monkeypatch):
    c = sandbox_or_skip(monkeypatch)
    marker = f"swe_marker_{uuid.uuid4().hex}"
    host = tmp_path / "swe"                                   # like ~/swe: the dataset, test_patch, a clone with .git
    (host / "inst").mkdir(parents=True)
    (host / "inst" / marker).write_text("test_patch")
    subprocess.run(["git", "init", "-q", str(host / "clone")], check=True)
    ws = tmp_path / "ws"
    (ws / "tests").mkdir(parents=True)
    (ws / "conftest.py").write_text("")
    (ws / "tests" / "test_hidden.py").write_text(f'''import os


def test_the_host_is_not_visible():
    assert os.path.isdir("/workspace/tests")
    found, seen = [], 0
    for root, dirs, files in os.walk("/"):
        if root in ("/proc", "/sys", "/dev"):
            dirs[:] = []
            continue
        seen += len(files)
        if ".git" in dirs or ".git" in files:
            found.append(os.path.join(root, ".git"))
        if {marker!r} in files or {marker!r} in dirs or "swe" in dirs and root == {str(tmp_path)!r}:
            found.append(root)
    assert seen > 100 and found == []
''')
    from acceptance.validation import run_validation
    spec = {"id": "hidden", "executable": "python", "args": ["-m", "pytest", "tests/test_hidden.py"], "timeout_s": 120,
            "min_tests": 1, "max_skipped": 0, "must_pass": ["tests/test_hidden.py::test_the_host_is_not_visible"],
            "environment": "argus"}
    v = run_validation(spec, str(ws), c)
    assert v["status"] == "pass", v["reason"]
