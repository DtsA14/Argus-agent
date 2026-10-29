"""scripts/verify.sh runs the suite with pytest-xdist; conftest.py puts every test of a Docker-sandbox module in one
xdist group, so sandbox tests never run at the same time. These tests pin which modules that is and that the marker is
what --dist loadgroup reads."""
from pathlib import Path

import conftest

ROOT = Path(__file__).resolve().parent.parent
SANDBOX_MODULES = {"test_acceptance_sandbox.py", "test_auto_validation.py", "test_codetask_crash.py", "test_draft.py",
                   "test_env_from_base.py", "test_eval_sandbox.py", "test_pytest_sandbox.py", "test_review.py", "test_sandbox.py", "test_stage.py",
                   "test_swe_pilot.py"}


def test_every_module_that_uses_the_sandbox_and_only_those_is_grouped():
    grouped = {p.name for p in (ROOT / "tests").glob("test_*.py") if conftest.uses_sandbox(p)}
    assert grouped == SANDBOX_MODULES


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
