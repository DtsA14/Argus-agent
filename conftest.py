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
import inspect
from pathlib import Path

import pytest

SANDBOX_GROUP = "sandbox"
SANDBOX_TEXT = "SANDBOX NOT " "AVAILABLE"      # two literals: this file must not contain the phrase whole, or every fixture of it would be a sandbox one
_sandbox_modules = {}


def uses_sandbox(path):
    """Whether the file at `path` says it uses the Docker sandbox (it can skip with the message in SANDBOX_TEXT)."""
    path = str(path)
    if path not in _sandbox_modules:
        try:
            _sandbox_modules[path] = SANDBOX_TEXT in Path(path).read_text(encoding="utf-8")
        except OSError:
            _sandbox_modules[path] = False
    return _sandbox_modules[path]


def _fixture_files(item):
    """The files that define the fixtures in the closure of `item` (its own and the ones they need). Items that cannot say
    (no session, no fixture names: a doctest, a stand-in in a test) have none."""
    fm = getattr(getattr(item, "session", None), "_fixturemanager", None)
    if fm is None:
        return
    for name in getattr(item, "fixturenames", ()):
        for fd in fm.getfixturedefs(name, item) or ():
            try:
                func = inspect.unwrap(fd.func)      # a fixture wrapped with functools.wraps is defined where the original is
            except ValueError:
                func = fd.func
            f = getattr(getattr(func, "__code__", None), "co_filename", "")
            if f:
                yield f


@pytest.hookimpl(tryfirst=True)      # before xdist's own hook, which turns the marker into the node id's @group
def pytest_collection_modifyitems(config, items):
    # A test is a sandbox test when its module says so, or when a fixture it needs is defined in a file that does: a module
    # that imports `scfg` from another has no such text of its own and ran beside the sandbox group (SPEC_VERIFY_HARDENING).
    for item in items:
        if uses_sandbox(item.fspath) or any(uses_sandbox(f) for f in _fixture_files(item)):
            item.add_marker(pytest.mark.xdist_group(SANDBOX_GROUP))


def group_totals(reports):
    """{"sandbox": {seconds, tests}, "other": {...}} from test reports: every phase's duration is added, a test is counted by its
    call. A report of the sandbox group carries the `xdist_group` keyword; one that is not a test report counts for nothing."""
    out = {"sandbox": {"seconds": 0.0, "tests": 0}, "other": {"seconds": 0.0, "tests": 0}}
    for r in reports:
        g = out["sandbox" if "xdist_group" in (getattr(r, "keywords", None) or {}) else "other"]
        g["seconds"] += getattr(r, "duration", None) or 0.0
        g["tests"] += getattr(r, "when", None) == "call"
    return out


def format_group_totals(totals):
    s, o = totals["sandbox"], totals["other"]
    return ("durations by group (seconds, setup+call+teardown): "
            f"sandbox {s['seconds']:.1f} ({s['tests']} tests), other {o['seconds']:.1f} ({o['tests']} tests)")


def pytest_terminal_summary(terminalreporter):
    totals = group_totals(r for reports in terminalreporter.stats.values() for r in reports)
    if totals["sandbox"]["tests"] or totals["other"]["tests"]:
        terminalreporter.write_line(format_group_totals(totals))
