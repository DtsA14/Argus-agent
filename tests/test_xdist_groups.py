"""scripts/verify.sh runs the suite with pytest-xdist; conftest.py puts every test of a Docker-sandbox module, and every test that
uses a fixture defined in such a module, in one xdist group, so sandbox tests never run at the same time. These tests pin which
modules that is, computed from a real collection (not from the text rule the grouping itself uses: a module that imports the
fixture of another is grouped by the fixture and has no such text), and that the marker is what --dist loadgroup reads."""
import json
import os
import subprocess
import sys
from pathlib import Path

import conftest

ROOT = Path(__file__).resolve().parent.parent
SANDBOX_MODULES = {"test_acceptance_sandbox.py", "test_auto_validation.py", "test_codetask_crash.py", "test_draft.py",
                   "test_env_from_base.py", "test_eval_sandbox.py", "test_pytest_sandbox.py", "test_review.py", "test_sandbox.py", "test_stage.py",
                   "test_stage_viewer.py", "test_swe_pilot.py", "test_vitest_sandbox.py", "test_env_node.py",
                   "test_vitest_full_regression.py", "test_vf_forger.py", "test_red_caught.py"}


def collected_groups(tmp_path):
    out = tmp_path / "groups.json"
    r = subprocess.run([sys.executable, "-m", "pytest", "--collect-only", "-q", "-p", "no:cacheprovider", "-o", "addopts=",
                        "-p", "grouplist_plugin", str(ROOT / "tests")], cwd=ROOT, capture_output=True, text=True, timeout=300,
                       env={**os.environ, "GROUPLIST_OUT": str(out), "PYTHONPATH": str(ROOT / "tests")})
    assert r.returncode == 0, r.stdout[-800:] + r.stderr[-800:]
    return json.loads(out.read_text())


def test_every_module_that_uses_the_sandbox_and_only_those_is_grouped(tmp_path):
    groups = collected_groups(tmp_path)
    by_module = {}
    for node, grouped in groups.items():
        by_module.setdefault(node.split("::", 1)[0].rsplit("/", 1)[-1], set()).add(grouped)
    assert {m for m, g in by_module.items() if True in g} == SANDBOX_MODULES
    for m in SANDBOX_MODULES:                                          # a module that says so is grouped whole
        if conftest.uses_sandbox(ROOT / "tests" / m):
            assert by_module[m] == {True}, m


def test_the_hook_marks_sandbox_items_with_the_loadgroup_marker():
    class Item:
        def __init__(self, path):
            self.fspath, self.markers = path, []

        def add_marker(self, m):
            self.markers.append(m)
    items = [Item(ROOT / "tests" / "test_draft.py"), Item(ROOT / "tests" / "test_codetask.py")]
    conftest.pytest_collection_modifyitems(None, items)
    assert [(m.name, m.args) for m in items[0].markers] == [("xdist_group", ("sandbox",))]
    assert items[1].markers == []


def test_the_hook_runs_before_xdist_reads_the_groups():
    # xdist's worker hook appends "@<group>" to each node id from the xdist_group markers; a marker added after it is
    # ignored and the sandbox tests run at the same time (3 runs on 2026-10-22: 3 to 6 failures each).
    opts = getattr(conftest.pytest_collection_modifyitems, "pytest_impl", None) or {}
    assert opts.get("tryfirst") is True


def test_verify_sh_runs_the_suite_with_loadgroup():
    text = (ROOT / "scripts" / "verify.sh").read_text(encoding="utf-8")
    assert '-n "$WORKERS" --dist loadgroup' in text
    req = (ROOT / "requirements.txt").read_text(encoding="utf-8")
    assert "pytest-xdist==" in req
