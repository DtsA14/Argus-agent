"""docs/reviews/SPEC_ENV_FROM_PYTHON_IMAGE.md: environments built from an official Python image. The build refuses a definition
that is not pinned (name, base digest, exact hashed requirements) before docker is called; an environment from
environments/ is used by the router and the grader only with a passing check record for exactly the image they resolve; the
check writes that record only when every check passes; and, in the real sandbox, the sympy_py39 image has no shell, git or
pip, runs Python 3.9 with the pinned pytest, and classifies pytest_demo the way the argus environment does. The sandbox tests
skip with "SANDBOX NOT AVAILABLE" without Docker or the images (scripts/verify.sh builds both and counts a skip as failing)."""
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_router as tr  # noqa: E402

from router import job as rj  # noqa: E402
from tools import sandbox as sb  # noqa: E402

pytestmark = pytest.mark.skipif(sys.platform == "win32", reason="the build script and the sandbox need posix")

ROOT = Path(__file__).resolve().parent.parent
BUILD = ROOT / "scripts" / "build_env_from_base.sh"
DIGEST = "python@sha256:" + "a" * 64
REQ = "pytest==8.4.2 --hash=sha256:" + "b" * 64 + "\n"
IMG = "sha256:" + "c" * 64
OTHER = "sha256:" + "d" * 64


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


# ---- the build refuses an unpinned definition before docker is called ----------------------------------------------

def build(tmp_path, name, base=DIGEST, reqs=REQ):
    defs = tmp_path / "defs"
    if base is not None:
        (defs / name).mkdir(parents=True, exist_ok=True)
        (defs / name / "base").write_text(base + "\n")
        (defs / name / "requirements.txt").write_text(reqs)
    fake = tmp_path / "bin"
    fake.mkdir(exist_ok=True)
    (fake / "docker").write_text(f"#!/bin/sh\necho called >> {tmp_path / 'docker_called'}\nexit 1\n")
    (fake / "docker").chmod(0o755)
    env = {**os.environ, "PATH": f"{fake}:{os.environ['PATH']}", "ARGUS_ENV_DEFS": str(defs),
           "ARGUS_ENV_OUT": str(tmp_path / "out")}
    (tmp_path / "out").mkdir(exist_ok=True)
    return subprocess.run(["bash", str(BUILD), name, str(tmp_path / "cache")], env=env, capture_output=True, text=True)


@pytest.mark.parametrize("name, base, reqs, why", [
    ("../x", DIGEST, REQ, "lower-case"),
    ("Py39", DIGEST, REQ, "lower-case"),
    ("nodef", None, REQ, "no definition"),
    ("tagged", "python:3.9-slim", REQ, "pinned by digest"),
    ("short", "python@sha256:abc", REQ, "pinned by digest"),
    ("nohash", DIGEST, "pytest==8.4.2\n", "--hash=sha256"),
    ("range", DIGEST, "pytest>=8 --hash=sha256:" + "b" * 64 + "\n", "--hash=sha256"),
    ("onebad", DIGEST, REQ + "mpmath==1.3.0\n", "--hash=sha256"),
])
def test_an_unpinned_definition_is_refused_before_docker(tmp_path, name, base, reqs, why):
    r = build(tmp_path, name, base, reqs)
    assert r.returncode != 0 and why in r.stderr, r.stderr
    assert not (tmp_path / "docker_called").exists()


def test_a_pinned_definition_gets_to_docker(tmp_path):
    r = build(tmp_path, "fine")
    assert r.returncode != 0 and (tmp_path / "docker_called").exists()       # the fake docker fails; it was called


def test_the_sympy_py39_definition_is_pinned():
    d = ROOT / "environments" / "sympy_py39"
    assert (d / "base").read_text().strip() == \
        "python@sha256:2d97f6910b16bd338d3060f261f53f144965f755599aab1acda1e13cf1731b1b"
    lines = [l for l in (d / "requirements.txt").read_text().splitlines() if l.strip()]
    assert lines and all(l.split()[0].count("==") == 1 and l.split()[1].startswith("--hash=sha256:") for l in lines)
    assert "pytest==8.4.2" in [l.split()[0] for l in lines] and "mpmath==1.3.0" in [l.split()[0] for l in lines]


# ---- the check gates the router and the grader ---------------------------------------------------------------------

def defined(root, name="sympy_py39", record=None):
    (root / "environments" / name).mkdir(parents=True, exist_ok=True)
    if record is not None:
        (root / f".sandbox_image_{name}.check.json").write_text(json.dumps(record))
    return root


PASS = {"environment": "sympy_py39", "image": IMG, "result": "pass"}


@pytest.mark.parametrize("record, why", [
    (None, "has not been checked"),
    ({**PASS, "result": "fail"}, "did not pass"),
    ({**PASS, "environment": "other"}, "did not pass"),
    ({**PASS, "image": OTHER}, "was checked with image"),
])
def test_an_unchecked_or_differently_checked_image_is_not_usable(tmp_path, monkeypatch, record, why):
    monkeypatch.delenv("ARGUS_SANDBOX_IMAGE_SYMPY_PY39", raising=False)    # verify.sh sets it; these use their own image
    root = defined(tmp_path, record=record)
    assert why in (rj.check_problem("sympy_py39", IMG, root) or "")
    cfg = {"sandbox": {"environments": {"sympy_py39": {"image": IMG}}}}
    image, problem = rj.environment_pin(cfg, "sympy_py39", root)
    assert image is None and why in problem


def test_a_passing_record_for_that_image_is_usable_and_an_undefined_environment_is_not_gated(tmp_path, monkeypatch):
    monkeypatch.delenv("ARGUS_SANDBOX_IMAGE_SYMPY_PY39", raising=False)
    root = defined(tmp_path, record=PASS)
    assert rj.check_problem("sympy_py39", IMG, root) is None
    assert rj.environment_pin({"sandbox": {"environments": {"sympy_py39": {"image": IMG}}}}, "sympy_py39", root) == \
        (IMG, None)
    assert rj.check_problem("sympy", IMG, root) is None                     # not in environments/: as before


def test_a_job_on_an_unchecked_environment_is_not_created(tmp_path, monkeypatch):
    monkeypatch.delenv("ARGUS_SANDBOX_IMAGE_SYMPY_PY39", raising=False)
    root = defined(tmp_path / "root")
    monkeypatch.setattr(rj, "ROOT", root)
    c = tr.cfg()
    c["sandbox"] = {**c["sandbox"], "environments": {"argus": {"image": OTHER}, "sympy_py39": {"image": IMG}}}
    e = tr.Env(tmp_path, config=c)
    with pytest.raises(rj.Refused, match="has not been checked"):
        e.code(environment="sympy_py39")
    assert not (e.jobs / "jtest").exists() and e.drafter.calls == []


def test_the_grader_refuses_an_unchecked_environment(tmp_path, monkeypatch):
    monkeypatch.delenv("ARGUS_SANDBOX_IMAGE_SYMPY_PY39", raising=False)
    g = load("swe_grade_env", ROOT / "scripts" / "swe_grade.py")
    root = defined(tmp_path / "root")
    called = []
    with pytest.raises(g.Refused, match="has not been checked"):
        g.grade(instance=tmp_path, repo=tmp_path, review=tmp_path, sha="0" * 64, environment="sympy_py39",
                sandbox_cfg={"environments": {"sympy_py39": {"image": IMG}}},
                validate=lambda *a, **k: called.append(a), root=root)
    assert called == []


def test_the_check_writes_its_record_only_when_every_check_passes(tmp_path, monkeypatch):
    monkeypatch.delenv("ARGUS_SANDBOX_IMAGE_SYMPY_PY39", raising=False)
    m = load("check_env_t", ROOT / "scripts" / "check_env_image.py")
    monkeypatch.syspath_prepend(str(ROOT / "scripts"))
    import approve_draft
    monkeypatch.setattr(approve_draft, "sandbox_cfg", lambda: {"environments": {"sympy_py39": {"image": IMG}}})
    monkeypatch.setattr(m, "record_path", lambda name, root=None: tmp_path / "check.json")
    for results, rc in (([("a", True, ""), ("b", False, "no")], 1), ([("a", True, ""), ("b", True, "")], 0)):
        monkeypatch.setattr(m, "checks", lambda name, cfg, wd, r=results: r)
        assert m.main(["sympy_py39"]) == rc
        assert (tmp_path / "check.json").exists() == (rc == 0)
    rec = json.loads((tmp_path / "check.json").read_text())
    assert rec["image"] == IMG and rec["result"] == "pass" and rec["environment"] == "sympy_py39"


# ---- the real image ------------------------------------------------------------------------------------------------

@pytest.fixture(scope="module")
def cfg():
    sys.path.insert(0, str(ROOT / "scripts"))
    from approve_draft import sandbox_cfg
    c = sandbox_cfg()
    for name in ("argus", "sympy_py39"):
        ok, why = sb.status({**c, "environment": name})
        if not ok:
            pytest.skip(f"SANDBOX NOT AVAILABLE: {name}: {why}")
    return c


def test_the_sympy_py39_image_passes_every_check(cfg, tmp_path):
    import shutil
    m = load("check_env_r", ROOT / "scripts" / "check_env_image.py")
    ws = tmp_path / "ws"
    shutil.copytree(ROOT / "fixtures" / "repos" / "pytest_demo", ws)
    results = m.checks("sympy_py39", cfg, str(ws))
    assert [c for c, ok, _ in results] == ["isolation", "classification like argus", "red check", "collection",
                                           "no shell, git or pip", "versions"]
    assert all(ok for _, ok, _ in results), results


def test_a_build_has_no_shell_git_or_pip_and_two_builds_have_the_same_rootfs(cfg, tmp_path, monkeypatch):
    out, rootfs = tmp_path / "out", []
    out.mkdir()
    env = {**os.environ, "ARGUS_ENV_OUT": str(out)}
    for _ in range(2):
        r = subprocess.run(["bash", str(BUILD), "sympy_py39"], env=env, capture_output=True, text=True, timeout=900)
        assert r.returncode == 0, r.stderr[-800:]
        rootfs.append(json.loads((out / ".sandbox_image_sympy_py39.json").read_text())["rootfs"])
    assert rootfs[0] == rootfs[1]
    image = (out / ".sandbox_image_sympy_py39").read_text().strip()
    m = load("check_env_b", ROOT / "scripts" / "check_env_image.py")
    run = {**cfg, "environments": {**cfg["environments"], "sympy_py39": {"image": image}}}
    monkeypatch.delenv("ARGUS_SANDBOX_IMAGE_SYMPY_PY39", raising=False)     # this build's image, not verify's
    r = sb.run_command(["python3", "-I", "-B", "-c", m.PROBE], workdir=str(tmp_path),
                       cfg={**run, "environment": "sympy_py39", "timeout_s": 60})
    line = next(l for l in r["stdout"].splitlines() if l.startswith("ARGUS-PROBE:"))
    probe = json.loads(line[len("ARGUS-PROBE:"):])
    assert probe["python"].startswith("3.9.") and probe["pytest"] == "8.4.2"
    assert (probe["sh"], probe["bash"], probe["git"], probe["pip"]) == (False, False, None, False)


GOOD_PROBE = {"python": "3.9.25", "pytest": "8.4.2", "sh": False, "bash": False, "git": None, "pip": False}


@pytest.mark.parametrize("flip, check", [
    ("isolation", "isolation"), ("classification", "classification like argus"), ("inconsistent", "classification like argus"),
    ("red", "red check"), ("collection", "collection"), ("sh", "no shell, git or pip"), ("git", "no shell, git or pip"),
    ("pip", "no shell, git or pip"), ("pytest", "versions"), ("python", "versions"),
])
def test_each_check_fails_when_its_condition_does_not_hold(monkeypatch, flip, check):
    m = load("check_env_u", ROOT / "scripts" / "check_env_image.py")
    demo = {"tests/test_demo.py::test_add": "ok", "tests/test_demo.py::test_fails": "FAIL"}

    def run_validation(spec, wd, cfg, log=None):
        return {"status": "fail" if flip == "isolation" else "pass", "reason": "x" if flip == "isolation" else ""}

    def run_command(argv, workdir, cfg, **kw):
        if "-c" in argv:
            probe = dict(GOOD_PROBE)
            if flip in ("sh", "pip"):
                probe[flip] = True
            if flip == "git":
                probe["git"] = "/usr/bin/git"
            if flip == "pytest":
                probe["pytest"] = "9.1.1"
            if flip == "python":
                probe["python"] = "3.12.3"
            return {"stdout": "ARGUS-PROBE:" + json.dumps(probe) + "\n"}
        return {"stdout": cfg["environment"]}

    def parse(out):
        tests = dict(demo)
        if out == "sympy_py39" and flip == "classification":
            tests["tests/test_demo.py::test_fails"] = "ERROR"
        return {"tests": tests, "consistent": not (out == "sympy_py39" and flip == "inconsistent")}

    red = {"tests/test_demo.py::test_fails": {"assertion": flip != "red", "outcome": "failed"},
           "tests/test_demo.py::test_add": {"outcome": "passed"}}
    monkeypatch.setattr(m.va, "run_validation", run_validation)
    monkeypatch.setattr(m.sb, "run_command", run_command)
    monkeypatch.setattr(m.va, "parse_pytest", parse)
    monkeypatch.setattr(m.va, "red_check", lambda *a, **k: (red, None))
    monkeypatch.setattr(m.va, "collect_nodes", lambda *a, **k: (set() if flip == "collection" else
                                                                 {"tests/test_demo.py::test_add"}, None))
    results = {c: ok for c, ok, _ in m.checks("sympy_py39", {}, "/nowhere")}
    assert results[check] is False and [c for c, ok in results.items() if not ok] == [check]
