# Presence of this file puts the project root on sys.path for pytest.

# fixtures/repos/ holds input repositories for general tasks; their tests fail on purpose (the bug the agent must
# fix) and run only inside the sandbox, through acceptance/validation.py. runs/ (git-ignored) holds the workspaces of
# real runs, copies of those repositories: collecting them broke verify.sh once live runs existed on the VM.
collect_ignore = ["fixtures", "runs", "pilots"]   # pilots: target tests that fail until the agent fixes them

# scripts/verify.sh runs the suite with pytest-xdist (-n 4 --dist loadgroup). Every test of a module that uses the Docker
# sandbox goes to one group, so sandbox tests never run at the same time (they share the daemon, the images and the
# VM's CPUs); all other tests are spread over the workers. A sandbox module is one that skips with "SANDBOX NOT
# AVAILABLE" (the skip verify.sh counts as a failure), so a new sandbox module is grouped without being listed here.
# Measured 2026-10-22 on the VM: the non-sandbox tests with verify.sh's settings, 327 s serial, 121 s with -n 4, the
# same 1,201 passed and 90 skipped.
from pathlib import Path

import pytest

SANDBOX_GROUP = "sandbox"
_sandbox_modules = {}


def uses_sandbox(path):
    """Whether the test module at `path` uses the Docker sandbox (it can skip with SANDBOX NOT AVAILABLE)."""
    path = str(path)
    if path not in _sandbox_modules:
        try:
            _sandbox_modules[path] = "SANDBOX NOT AVAILABLE" in Path(path).read_text(encoding="utf-8")
        except OSError:
            _sandbox_modules[path] = False
    return _sandbox_modules[path]


@pytest.hookimpl(tryfirst=True)      # before xdist's own hook, which turns the marker into the node id's @group
def pytest_collection_modifyitems(config, items):
    for item in items:
        if uses_sandbox(item.fspath):
            item.add_marker(pytest.mark.xdist_group(SANDBOX_GROUP))
