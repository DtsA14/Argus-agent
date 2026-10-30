"""The Node environment pwa_node22 (docs/reviews/SPEC_PWA_VIEWER.md E): scripts/build_env_node.sh refuses an unpinned
definition before docker is called; the committed definition is pinned; every check of scripts/check_env_image.py for a
vitest environment fails when its condition does not hold; and in the real sandbox, a build has no shell, npm or git,
two builds have the same rootfs, and the image passes every check. The Docker tests are skipped with "SANDBOX NOT
AVAILABLE" without Docker, which scripts/verify.sh does not count as passing."""
import importlib.util
import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
BUILD = ROOT / "scripts" / "build_env_node.sh"
DIGEST = "node@sha256:" + "a" * 64
PKG = {"name": "x", "private": True, "dependencies": {"react": "19.1.0"}}
ENTRY = {"version": "19.1.0", "resolved": "https://registry.npmjs.org/react/-/react-19.1.0.tgz",
         "integrity": "sha512-abc"}


def lock(**entry):
    return {"lockfileVersion": 3, "packages": {"": {"name": "x"}, "node_modules/react": {**ENTRY, **entry}}}


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def build(tmp_path, name, base=DIGEST, pkg=PKG, lck=None):
    defs = tmp_path / "defs"
    if base is not None:
        (defs / name).mkdir(parents=True, exist_ok=True)
        (defs / name / "base").write_text(base + "\n")
        (defs / name / "package.json").write_text(json.dumps(pkg))
        (defs / name / "package-lock.json").write_text(json.dumps(lck if lck is not None else lock()))
    fake = tmp_path / "bin"
    fake.mkdir(exist_ok=True)
    (fake / "docker").write_text(f"#!/bin/sh\necho called >> {tmp_path / 'docker_called'}\nexit 1\n")
    (fake / "docker").chmod(0o755)
    env = {**os.environ, "PATH": f"{fake}:{os.environ['PATH']}", "ARGUS_ENV_DEFS": str(defs),
           "ARGUS_ENV_OUT": str(tmp_path / "out")}
    (tmp_path / "out").mkdir(exist_ok=True)
    return subprocess.run(["bash", str(BUILD), name, str(tmp_path / "cache")], env=env, capture_output=True, text=True)


@pytest.mark.parametrize("name, base, pkg, lck, why", [
    ("../x", DIGEST, PKG, None, "lower-case"),
    ("nodef", None, PKG, None, "no definition"),
    ("tagged", "node:22-bookworm-slim", PKG, None, "pinned by digest"),
    ("range", DIGEST, {**PKG, "dependencies": {"react": "^19.1.0"}}, None, "exact versions"),
    ("dev", DIGEST, {**PKG, "devDependencies": {"vitest": "latest"}}, None, "exact versions"),
    ("nohash", DIGEST, PKG, lock(integrity=""), "sha512"),
    ("sha1", DIGEST, PKG, lock(integrity="sha1-abc"), "sha512"),
    ("elsewhere", DIGEST, PKG, lock(resolved="https://example.com/react.tgz"), "sha512"),
    ("git", DIGEST, PKG, lock(resolved="git+ssh://git@github.com/x/react.git"), "sha512"),
    ("v2", DIGEST, PKG, {**lock(), "lockfileVersion": 2}, "lockfile v3"),
])
def test_an_unpinned_definition_is_refused_before_docker(tmp_path, name, base, pkg, lck, why):
    r = build(tmp_path, name, base, pkg, lck)
    assert r.returncode != 0 and why in r.stderr, r.stderr
    assert not (tmp_path / "docker_called").exists()


def test_a_pinned_definition_gets_to_docker(tmp_path):
    r = build(tmp_path, "fine")
    assert r.returncode != 0 and (tmp_path / "docker_called").exists()       # the fake docker fails; it was called


def test_the_pwa_node22_definition_is_pinned():
    d = ROOT / "environments" / "pwa_node22"
    assert (d / "base").read_text().strip() == \
        "node@sha256:4b150b48b4116e2a22f2c39cc27025fbf4f153e2078fd3b14d159fdb5c7279da"
    pkg, lck = json.loads((d / "package.json").read_text()), json.loads((d / "package-lock.json").read_text())
    assert pkg["devDependencies"]["vitest"] == "3.1.4" and pkg["dependencies"]["react"] == "19.1.0"
    entries = {k: v for k, v in lck["packages"].items() if k}
    assert entries and all(v["integrity"].startswith("sha512-") for v in entries.values())
    assert lck["packages"][""]["devDependencies"] == pkg["devDependencies"]   # the lock is of this package.json


def test_the_vitest_demo_needs_only_packages_of_the_environment():
    """SPEC_PWA_VIEWER E1 for the fixture: what it declares is exactly in the lock."""
    m = load("check_env_lock", ROOT / "scripts" / "check_env_image.py")
    have = m.locked("pwa_node22")
    pkg = json.loads((ROOT / "fixtures" / "repos" / "vitest_demo" / "package.json").read_text())
    for section in ("dependencies", "devDependencies"):
        for name, version in pkg[section].items():
            assert have.get(name) == version, name


def test_a_vitest_environment_is_checked_on_the_vitest_demo_and_others_as_before():
    m = load("check_env_pick", ROOT / "scripts" / "check_env_image.py")
    envs = {"environments": {"pwa_node22": {"runner": "vitest"}, "ledger_py312": {"image": None}}}
    assert m.checker("pwa_node22", envs) == (m.VITEST_DEMO, m.vitest_checks)
    assert m.checker("ledger_py312", envs) == (m.DEMO, m.checks)


# ---- every vitest check fails alone when its condition does not hold -----------------------------------------------

GOOD_PROBE = {"node": "22.23.4", "vitest": "3.1.4", "sh": False, "bash": False, "git": False, "npm": False}


@pytest.mark.parametrize("flip, check", [
    ("isolation", "isolation"), ("classification", "classification"), ("inconsistent", "classification"),
    ("include", "only the requested file"), ("red", "red check"), ("red_other", "red check"),
    ("sh", "no shell, git or npm"), ("git", "no shell, git or npm"), ("npm", "no shell, git or npm"),
    ("node", "versions"), ("vitest", "versions"),
])
def test_each_vitest_check_fails_when_its_condition_does_not_hold(monkeypatch, tmp_path, flip, check):
    m = load("check_env_v", ROOT / "scripts" / "check_env_image.py")
    (tmp_path / ".sandbox_image_pwa_node22.json").write_text(json.dumps({"node": "22.23.4"}))
    monkeypatch.setattr(m, "ROOT", tmp_path)
    monkeypatch.setattr(m, "locked", lambda name: {"vitest": "3.1.4"})

    def run_validation(spec, wd, cfg, log=None):
        bad = (flip == "isolation" and "src/isolation.test.js" in spec["args"]) or \
            (flip == "include" and "src/sum.test.js" in spec["args"])
        return {"status": "fail" if bad else "pass", "reason": "x" if bad else "",
                "evidence": {"tests_run": 2 if flip == "include" else 1}}

    def run_command(argv, workdir, cfg, **kw):
        if argv[:2] == ["node", "-e"]:
            probe = dict(GOOD_PROBE)
            if flip in ("sh", "git", "npm"):
                probe[flip] = True
            if flip == "node":
                probe["node"] = "22.1.0"
            if flip == "vitest":
                probe["vitest"] = "3.2.0"
            return {"stdout": "ARGUS-PROBE:" + json.dumps(probe) + "\n"}
        return {"stdout": ""}

    def parse(out, nonce, files):
        tests = dict(m.VITEST_EXPECTED)
        if flip == "classification":
            tests["src/demo.test.jsx::fails in code"] = "ok"
        return {"tests": tests, "consistent": flip != "inconsistent"}

    red = {"src/demo.test.jsx::fails by assertion": {"assertion": flip != "red", "outcome": "failed"},
           "src/demo.test.jsx::element not found": {"assertion": flip == "red_other", "outcome": "failed"}}
    monkeypatch.setattr(m.va, "run_validation", run_validation)
    monkeypatch.setattr(m.sb, "run_command", run_command)
    monkeypatch.setattr(m.va, "parse_vitest", parse)
    monkeypatch.setattr(m.va, "red_check", lambda *a, **k: (red, None))
    results = {c: ok for c, ok, _ in m.vitest_checks("pwa_node22", {}, "/nowhere")}
    assert results[check] is False and [c for c, ok in results.items() if not ok] == [check]


# ---- the real build ------------------------------------------------------------------------------------------------

@pytest.fixture(scope="module")
def cfg():
    from runner import load_config
    from tools import sandbox as sb
    c = {**(load_config().get("sandbox") or {}), "kind": "docker"}
    ok, reason = sb.status({**c, "environment": "pwa_node22"})
    if not ok or shutil.which("docker") is None:
        pytest.skip(f"SANDBOX NOT AVAILABLE: {reason}")
    return c


def test_the_pwa_node22_image_passes_every_check(cfg, tmp_path):
    m = load("check_env_real", ROOT / "scripts" / "check_env_image.py")
    ws = tmp_path / "ws"
    shutil.copytree(m.VITEST_DEMO, ws)
    results = m.vitest_checks("pwa_node22", cfg, str(ws))
    assert all(ok for _, ok, _ in results), results


def test_a_build_has_no_shell_git_or_npm_and_two_builds_have_the_same_rootfs(cfg, tmp_path):
    env = {**os.environ, "ARGUS_ENV_OUT": str(tmp_path)}
    rootfs, images = [], []
    for _ in range(2):
        r = subprocess.run(["bash", str(BUILD), "pwa_node22"], env=env, capture_output=True, text=True, timeout=900)
        assert r.returncode == 0, r.stderr[-2000:]
        meta = json.loads((tmp_path / ".sandbox_image_pwa_node22.json").read_text())
        rootfs.append(meta["rootfs"])
        images.append((tmp_path / ".sandbox_image_pwa_node22").read_text().strip())
    assert rootfs[0] == rootfs[1] and meta["node"] == "22.23.4"
    out = subprocess.run(["docker", "run", "--rm", "--network", "none", "--entrypoint", "node", images[1], "-e",
                          "const fs=require('node:fs');console.log(JSON.stringify(['/bin/sh','/bin/bash','/usr/bin/git',"
                          "'/usr/local/bin/npm','/usr/local/lib/node_modules/npm'].map(p=>fs.existsSync(p))))"],
                         capture_output=True, text=True, timeout=120)
    assert json.loads(out.stdout) == [False] * 5
    for image in set(images):           # this test's own builds; the environment's image (.sandbox_image_*) is another id
        subprocess.run(["docker", "rmi", image], capture_output=True)
