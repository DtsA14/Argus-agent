"""SPEC_CHAT_PACKAGES S0: scripts/check_env_image.py can check an environment that is not adopted yet, from a staged definition
folder (`--defs`), the pins and the check record of a job's directory (`--out`) and the config block of an existing environment
(`--like`). Without the options nothing changes. The options go together, are refused for a configured name, never take the
image from an inherited ARGUS_SANDBOX_IMAGE_<NAME>, and never write the record in the checkout. No Docker: the checks are stubbed."""
import importlib.util
import json
import os
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "check_env_image.py"
NEW = "bulking_node22_up1"
IMAGE = "sha256:" + "a" * 64
OTHER = "sha256:" + "b" * 64
VAR = f"ARGUS_SANDBOX_IMAGE_{NEW.upper()}"


def load(name="check_env_defs"):
    spec = importlib.util.spec_from_file_location(name, SCRIPT)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def base_cfg():
    return {"kind": "docker", "environments": {
        "bulking_node22": {"image": None, "runner": "vitest", "protected_required": True},
        "ledger_py312": {"image": None}}}


@pytest.fixture(autouse=True)
def the_checkout_records_are_untouched():
    """A test must never write a check record in the real checkout (an earlier draft of the first test did, and a fake pass for a fake image
    had to be replaced by a real check)."""
    def snap():
        return {p.name: p.read_bytes() for p in ROOT.glob(".sandbox_image_*.check.json")}
    before = snap()
    yield
    assert snap() == before


@pytest.fixture
def world(tmp_path, monkeypatch):
    """A module with ROOT in tmp_path, a stubbed sandbox config, a stubbed checker that records its calls."""
    m = load()
    root = tmp_path / "root"
    (root / "environments" / "bulking_node22").mkdir(parents=True)
    monkeypatch.setattr(m, "ROOT", root)
    cfg = base_cfg()
    import approve_draft
    monkeypatch.setattr(approve_draft, "sandbox_cfg", lambda *a, **k: cfg)
    calls = []
    verdict = {"ok": True}

    def run_checks(name, c, ws, **kw):
        calls.append({"name": name, "cfg": c, "kw": kw, "var": os.environ.get(VAR), "image": m.sb.environment_image(c, name)})
        return [("one", verdict["ok"], "x")]

    monkeypatch.setattr(m, "checker", lambda name, c: (ROOT / "fixtures" / "repos" / "vitest_demo", run_checks))
    monkeypatch.delenv(VAR, raising=False)
    defs, out = tmp_path / "defs", tmp_path / "out"
    (defs / NEW).mkdir(parents=True)
    out.mkdir()
    (out / f".sandbox_image_{NEW}").write_text(IMAGE + "\n")
    return m, root, cfg, calls, verdict, defs, out


def run(m, defs, out, like="bulking_node22", name=NEW, extra=()):
    args = [name]
    if defs is not None:
        args += ["--defs", str(defs)]
    if out is not None:
        args += ["--out", str(out)]
    if like is not None:
        args += ["--like", like]
    return m.main([*args, *extra])


def record(d):
    return Path(d) / f".sandbox_image_{NEW}.check.json"


# ---- without the options: as before ---------------------------------------------------------------------------------

def test_without_the_options_the_check_is_the_old_one(world, monkeypatch):
    m, root, cfg, calls, verdict, defs, out = world
    monkeypatch.setenv("ARGUS_SANDBOX_IMAGE_BULKING_NODE22", IMAGE)
    assert m.main(["bulking_node22"]) == 0
    assert calls[0]["kw"] == {}                                   # the old call: three positional arguments, no new keyword
    assert (root / ".sandbox_image_bulking_node22.check.json").exists()
    assert not record(out).exists()


def test_the_old_form_still_refuses_a_name_that_is_not_configured(world, capsys):
    m, root, cfg, calls, verdict, defs, out = world
    assert m.main([NEW]) == 2 and not calls
    assert not (root / f".sandbox_image_{NEW}.check.json").exists()


# ---- the options go together, and only for a name that is not configured --------------------------------------------

@pytest.mark.parametrize("keep", [("defs",), ("out",), ("like",), ("defs", "out"), ("defs", "like"), ("out", "like")])
def test_the_three_options_go_together(world, keep):
    m, root, cfg, calls, verdict, defs, out = world
    rc = run(m, defs if "defs" in keep else None, out if "out" in keep else None, like="bulking_node22" if "like" in keep else None)
    assert rc == 2 and not calls
    assert not record(out).exists() and not record(root).exists()


def test_a_configured_name_is_refused_with_the_options(world):
    m, root, cfg, calls, verdict, defs, out = world
    cfg["environments"][NEW] = {"image": OTHER, "runner": "vitest"}
    assert run(m, defs, out) == 2 and not calls
    assert not record(out).exists()


def test_an_unknown_like_is_refused(world):
    m, root, cfg, calls, verdict, defs, out = world
    assert run(m, defs, out, like="nope_node22") == 2 and not calls


def test_there_is_no_free_runner_option(world):
    m, root, cfg, calls, verdict, defs, out = world
    with pytest.raises(SystemExit):
        m.main([NEW, "--defs", str(defs), "--out", str(out), "--like", "bulking_node22", "--runner", "vitest"])


@pytest.mark.parametrize("bad", ["Bad-Name", "x" * 33, "", "a b"])
def test_a_name_outside_the_environment_shape_is_refused(world, bad):
    m, root, cfg, calls, verdict, defs, out = world
    assert run(m, defs, out, name=bad) == 2 and not calls


def test_a_missing_definition_folder_or_out_directory_is_refused(world, tmp_path):
    m, root, cfg, calls, verdict, defs, out = world
    assert run(m, tmp_path / "nodefs", out) == 2
    (defs / NEW).rmdir()
    assert run(m, defs, out) == 2
    (defs / NEW).mkdir()
    assert run(m, defs, tmp_path / "noout") == 2
    assert not calls


# ---- the image comes from the job's pin file, never from the environment ------------------------------------------

def test_the_image_is_the_pin_file_of_the_out_directory(world):
    m, root, cfg, calls, verdict, defs, out = world
    assert run(m, defs, out) == 0
    assert calls[0]["image"] == (IMAGE, None)


def test_an_inherited_image_variable_is_ignored(world, monkeypatch):
    m, root, cfg, calls, verdict, defs, out = world
    monkeypatch.setenv(VAR, OTHER)
    assert run(m, defs, out) == 0
    assert calls[0]["var"] is None                                # gone while the checks run
    assert calls[0]["image"] == (IMAGE, None)


@pytest.mark.parametrize("content", ["", "latest", "sha256:" + "a" * 63, "sha256:" + "A" * 64, IMAGE + "\nsha256:" + "b" * 64,
                                     "x" * 5000])
def test_a_pin_file_that_is_not_a_digest_is_refused(world, content):
    m, root, cfg, calls, verdict, defs, out = world
    (out / f".sandbox_image_{NEW}").write_text(content)
    assert run(m, defs, out) == 2 and not calls


def test_a_missing_or_linked_pin_file_is_refused(world, tmp_path):
    m, root, cfg, calls, verdict, defs, out = world
    pin = out / f".sandbox_image_{NEW}"
    real = tmp_path / "real"
    real.write_text(IMAGE)
    pin.unlink()
    assert run(m, defs, out) == 2                                 # missing
    pin.symlink_to(real)
    assert run(m, defs, out) == 2                                 # a link is not a pin
    assert not calls


def test_a_registry_prefixed_digest_is_accepted(world):
    m, root, cfg, calls, verdict, defs, out = world
    (out / f".sandbox_image_{NEW}").write_text("argus-sandbox-x@" + IMAGE)
    assert run(m, defs, out) == 0


# ---- the overlay: the block of the base, in memory, for this run only -------------------------------------------------

def test_the_overlay_copies_the_block_of_the_base_and_sets_the_image(world):
    m, root, cfg, calls, verdict, defs, out = world
    assert run(m, defs, out) == 0
    block = calls[0]["cfg"]["environments"][NEW]
    assert block == {"image": IMAGE, "runner": "vitest", "protected_required": True}


def test_the_overlay_does_not_leak_into_the_config_or_other_environments(world):
    m, root, cfg, calls, verdict, defs, out = world
    before = json.dumps(cfg, sort_keys=True)
    assert run(m, defs, out) == 0
    assert json.dumps(cfg, sort_keys=True) == before              # the stub's dict is untouched: the overlay is a copy
    seen = calls[0]["cfg"]["environments"]
    assert seen["bulking_node22"] == cfg["environments"]["bulking_node22"] and seen["ledger_py312"] == {"image": None}


def test_the_checks_get_the_staged_definition_and_the_out_directory(world):
    m, root, cfg, calls, verdict, defs, out = world
    assert run(m, defs, out) == 0
    assert Path(calls[0]["kw"]["defs"]) == defs.resolve() and Path(calls[0]["kw"]["out"]) == out.resolve()


# ---- the record is written under --out, and only on a pass ---------------------------------------------------------

def test_a_pass_writes_the_record_in_out_and_not_in_the_checkout(world):
    m, root, cfg, calls, verdict, defs, out = world
    assert run(m, defs, out) == 0
    rec = json.loads(record(out).read_text())
    assert rec["environment"] == NEW and rec["image"] == IMAGE and rec["result"] == "pass"
    assert not record(root).exists() and not list(root.glob(".sandbox_image_*"))


def test_a_failure_writes_no_record_and_removes_a_stale_one(world):
    m, root, cfg, calls, verdict, defs, out = world
    record(out).write_text("stale")
    verdict["ok"] = False
    assert run(m, defs, out) == 1
    assert not record(out).exists() and not record(root).exists()


def test_a_log_is_still_written_where_asked(world, tmp_path):
    m, root, cfg, calls, verdict, defs, out = world
    assert run(m, defs, out, extra=("--log", str(tmp_path / "log.txt"))) == 0
    assert "RESULT: PASS" in (tmp_path / "log.txt").read_text()


# ---- what the real checks read: the lock, the requirements and the build metadata ---------------------------------------

def test_locked_and_pinned_read_the_staged_definition(tmp_path):
    m = load("check_env_defs_read")
    d = tmp_path / "defs" / NEW
    d.mkdir(parents=True)
    (d / "package-lock.json").write_text(json.dumps({"packages": {"node_modules/vitest": {"version": "9.9.9"}}}))
    (d / "requirements.txt").write_text("pytest==9.0.1\n")
    assert m.locked(NEW, defs=tmp_path / "defs") == {"vitest": "9.9.9"}
    assert m.pinned(NEW, defs=tmp_path / "defs") == {"pytest": "9.0.1"}
    with pytest.raises(FileNotFoundError):
        m.locked(NEW)                                             # without defs it reads the checkout, where this name is not


def stub_vitest_world(m, monkeypatch):
    good = {"node": "22.23.4", "vitest": "3.1.4", "sh": False, "bash": False, "git": False, "npm": False}
    monkeypatch.setattr(m.va, "run_validation", lambda spec, wd, cfg, log=None: {
        "status": "pass", "reason": "", "evidence": {"tests_run": 1}})
    monkeypatch.setattr(m.sb, "run_command", lambda argv, workdir, cfg, **kw: {"stdout": "ARGUS-PROBE:" + json.dumps(good) + "\n"})
    monkeypatch.setattr(m.va, "parse_vitest", lambda out, nonce, files: {"tests": dict(m.VITEST_EXPECTED), "consistent": True})
    red = {"src/demo.test.jsx::fails by assertion": {"assertion": True, "outcome": "failed"},
           "src/demo.test.jsx::element not found": {"assertion": False, "outcome": "failed"}}
    monkeypatch.setattr(m.va, "red_check", lambda *a, **k: (red, None))


def test_the_versions_check_reads_the_lock_and_the_metadata_of_the_staged_definition(tmp_path, monkeypatch):
    m = load("check_env_defs_versions")
    root, defs, out = tmp_path / "root", tmp_path / "defs", tmp_path / "out"
    for d in (root / "environments" / NEW, defs / NEW, out):
        d.mkdir(parents=True)
    # the checkout holds a different lock and different metadata under the same name: reading there would give another verdict
    (root / "environments" / NEW / "package-lock.json").write_text(json.dumps({"packages": {"node_modules/vitest": {"version": "0.0.1"}}}))
    (root / f".sandbox_image_{NEW}.json").write_text(json.dumps({"node": "1.1.1"}))
    (defs / NEW / "package-lock.json").write_text(json.dumps({"packages": {"node_modules/vitest": {"version": "3.1.4"}}}))
    (out / f".sandbox_image_{NEW}.json").write_text(json.dumps({"node": "22.23.4"}))
    monkeypatch.setattr(m, "ROOT", root)
    stub_vitest_world(m, monkeypatch)
    results = {c: ok for c, ok, _ in m.vitest_checks(NEW, {}, "/nowhere", defs=defs, out=out)}
    assert results["versions"] is True and all(results.values())
    # and the old form reads the checkout, as before
    wrong = {c: ok for c, ok, _ in m.vitest_checks(NEW, {}, "/nowhere")}
    assert wrong["versions"] is False


@pytest.mark.parametrize("flip", ["lock", "meta"])
def test_the_staged_versions_check_fails_when_the_staged_definition_disagrees(tmp_path, monkeypatch, flip):
    m = load("check_env_defs_versions2")
    defs, out = tmp_path / "defs", tmp_path / "out"
    (defs / NEW).mkdir(parents=True)
    out.mkdir()
    (defs / NEW / "package-lock.json").write_text(json.dumps({"packages": {"node_modules/vitest": {"version": "4.0.0" if flip == "lock" else "3.1.4"}}}))
    (out / f".sandbox_image_{NEW}.json").write_text(json.dumps({"node": "22.1.0" if flip == "meta" else "22.23.4"}))
    stub_vitest_world(m, monkeypatch)
    results = {c: ok for c, ok, _ in m.vitest_checks(NEW, {}, "/nowhere", defs=defs, out=out)}
    assert results["versions"] is False and [c for c, ok in results.items() if not ok] == ["versions"]


def test_the_old_form_refuses_a_configured_name_without_a_definition_folder(world):
    m, root, cfg, calls, verdict, defs, out = world
    cfg["environments"]["ghost_node22"] = {"image": "sha256:" + "c" * 64, "runner": "vitest"}
    assert m.main(["ghost_node22"]) == 2 and not calls
    assert not (root / ".sandbox_image_ghost_node22.check.json").exists()


def stub_python_world(m, monkeypatch):
    probe = {"python": "3.12.5", "pytest": "9.0.1", "sh": False, "bash": False, "git": None, "pip": False}
    monkeypatch.setattr(m.va, "run_validation", lambda spec, wd, cfg, log=None: {"status": "pass", "reason": ""})
    monkeypatch.setattr(m.va, "pytest_run", lambda s, wd, cfg: ({"stdout": "x"}, {"canary": m.va.CANARY_WANTED, "canary_rc": 1}))
    monkeypatch.setattr(m.va, "parse_pytest", lambda out: {"tests": {"a": "ok"}, "consistent": True})
    red = {"tests/test_demo.py::test_fails": {"assertion": True}, "tests/test_demo.py::test_add": {"outcome": "passed"}}
    monkeypatch.setattr(m.va, "red_check", lambda *a, **k: (red, None))
    monkeypatch.setattr(m.va, "collect_nodes", lambda *a, **k: (["tests/test_demo.py::test_add"], None))
    monkeypatch.setattr(m.sb, "run_command", lambda argv, workdir, cfg, **kw: {"stdout": "ARGUS-PROBE:" + json.dumps(probe) + "\n"})


@pytest.mark.parametrize("flip", [None, "requirements", "meta"])
def test_a_python_environment_reads_the_staged_requirements_and_metadata(tmp_path, monkeypatch, flip):
    m = load("check_env_defs_python")
    root, defs, out = tmp_path / "root", tmp_path / "defs", tmp_path / "out"
    for d in (root / "environments" / NEW, defs / NEW, out):
        d.mkdir(parents=True)
    (root / "environments" / NEW / "requirements.txt").write_text("pytest==1.0.0\n")      # the checkout's own, different
    (root / f".sandbox_image_{NEW}.json").write_text(json.dumps({"python": "3.9"}))
    (defs / NEW / "requirements.txt").write_text("pytest==" + ("8.0.0" if flip == "requirements" else "9.0.1") + "\n")
    (out / f".sandbox_image_{NEW}.json").write_text(json.dumps({"python": "3.9" if flip == "meta" else "3.12"}))
    monkeypatch.setattr(m, "ROOT", root)
    stub_python_world(m, monkeypatch)
    results = {c: ok for c, ok, _ in m.checks(NEW, {}, "/nowhere", defs=defs, out=out)}
    bad = [c for c, ok in results.items() if not ok]
    assert bad == ([] if flip is None else ["versions"])
