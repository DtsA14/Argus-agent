# Presence of this file puts the project root on sys.path for pytest.

# fixtures/repos/ holds input repositories for general tasks; their tests fail on purpose (the bug the agent must
# fix) and run only inside the sandbox, through acceptance/validation.py. runs/ (git-ignored) holds the workspaces of
# real runs, copies of those repositories: collecting them broke verify.sh once live runs existed on the VM.
collect_ignore = ["fixtures", "runs", "pilots"]   # pilots: target tests that fail until the agent fixes them

# scripts/verify.sh runs the suite with pytest-xdist (-n 4 --dist loadgroup). Every test of a module that uses the Docker
# sandbox goes to a serial group (two since SPEC_SANDBOX_SPLIT, see below), so the sandbox tests of one group never run at the same
# time (they share the daemon, the images and the VM's CPUs); all other tests are spread over the workers. A sandbox module is one that skips with "SANDBOX NOT
# AVAILABLE" (the skip verify.sh counts as a failure), so a new sandbox module is grouped without being listed here.
# Measured 2026-10-22 on the VM: the non-sandbox tests with verify.sh's settings, 327 s serial, 121 s with -n 4, the
# same 1,201 passed and 90 skipped.
import inspect
import json
import os
import sys
from pathlib import Path

import pytest

# SPEC_SANDBOX_SPLIT: the sandbox tests run in two serial groups, `sandbox_a` (the tests defined in tests/test_draft.py) and
# `sandbox_b` (every other sandbox test); VERIFY_SANDBOX_GROUPS=1 puts them all in the one group `sandbox` again. The two groups start
# together on two workers because xdist's loadscope reordering (on by default; verify.sh must not turn it off) hands the largest
# units out first, one per worker.
SANDBOX_GROUP = "sandbox"
GROUP_DRAFT, GROUP_REST = "sandbox_a", "sandbox_b"
DRAFT_MODULE = "test_draft.py"
GROUPS_ENV = "VERIFY_SANDBOX_GROUPS"
TIMES_ENV = "ARGUS_TEST_TIMES"       # a file the observer reads: one JSON line {nodeid, start, stop} per test call
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


def sandbox_group_count(environ=None):
    """1 or 2, from VERIFY_SANDBOX_GROUPS (2 when unset); anything else stops the run instead of being guessed."""
    environ = os.environ if environ is None else environ
    value = environ.get(GROUPS_ENV, "2")
    if value not in ("1", "2"):
        raise pytest.UsageError(f"{GROUPS_ENV} must be 1 or 2, not {value!r}")
    return int(value)


def sandbox_group_of(item, count):
    """The xdist group of a test, or None when it is not a sandbox test. A sandbox test is one whose module says so or that needs a
    fixture defined in a file that does. With two groups the tests defined in test_draft.py are in `sandbox_a` and every other in
    `sandbox_b` (also a test of another module that uses a fixture of test_draft)."""
    if not (uses_sandbox(item.fspath) or any(uses_sandbox(f) for f in _fixture_files(item))):
        return None
    if count == 1:
        return SANDBOX_GROUP
    return GROUP_DRAFT if Path(str(item.fspath)).name == DRAFT_MODULE else GROUP_REST


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
    count = sandbox_group_count()
    for item in items:
        group = sandbox_group_of(item, count)
        if group:
            item.add_marker(pytest.mark.xdist_group(group))


_is_worker = False
_times_failed = False


def pytest_configure(config):
    global _is_worker
    _is_worker = hasattr(config, "workerinput")
    sandbox_group_count()      # a bad VERIFY_SANDBOX_GROUPS stops the run here, before any test


def pytest_runtest_logreport(report):
    """With ARGUS_TEST_TIMES set, append when each phase of each test (setup, call, teardown) started and stopped (epoch seconds), once,
    on the controller: a container killed during a fixture's setup or teardown falls in the window of its own test. A file that cannot
    be written is reported once on stderr and never ends the run."""
    global _times_failed
    path = os.environ.get(TIMES_ENV)
    when = getattr(report, "when", None)
    if not path or _is_worker or _times_failed or when not in ("setup", "call", "teardown"):
        return
    line = json.dumps({"nodeid": report.nodeid, "when": when, "start": report.start, "stop": report.stop}) + "\n"
    try:
        fd = os.open(path, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o644)
        try:
            os.write(fd, line.encode("utf-8"))
        finally:
            os.close(fd)
    except OSError as e:
        _times_failed = True
        print(f"conftest: {TIMES_ENV} {path!r} cannot be written ({e}); times are not recorded", file=sys.stderr)


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


def group_walls(reports):
    """{group: {seconds, tests, offset}} for the sandbox groups: wall seconds = the first start to the last stop of the group's reports,
    tests counted by their call, offset = seconds from the first start of any report to the group's first start (two groups that
    overlap both start near 0). The group is the suffix of the node id that xdist adds ("...@sandbox_a"), matched whole."""
    spans, run_first = {}, None
    for r in reports:
        start, stop = getattr(r, "start", None), getattr(r, "stop", None)
        if start is None or stop is None:
            continue
        run_first = start if run_first is None else min(run_first, start)
        node = getattr(r, "nodeid", "") or ""
        group = next((g for g in (GROUP_DRAFT, GROUP_REST, SANDBOX_GROUP) if node.endswith("@" + g)), None)
        if group is None:
            continue
        w = spans.setdefault(group, {"first": start, "last": stop, "tests": 0})
        w["first"], w["last"] = min(w["first"], start), max(w["last"], stop)
        w["tests"] += getattr(r, "when", None) == "call"
    return {g: {"seconds": w["last"] - w["first"], "tests": w["tests"], "offset": w["first"] - run_first} for g, w in spans.items()}


def format_group_walls(walls, count):
    parts = ", ".join(f"{g} {walls[g]['seconds']:.1f} ({walls[g]['tests']} tests, starts +{walls[g]['offset']:.1f})" for g in sorted(walls))
    return f"sandbox groups: {count} ({GROUPS_ENV}); wall seconds: {parts}"


def pytest_terminal_summary(terminalreporter):
    reports = [r for reports in terminalreporter.stats.values() for r in reports]
    totals = group_totals(reports)
    if totals["sandbox"]["tests"] or totals["other"]["tests"]:
        terminalreporter.write_line(format_group_totals(totals))
    walls = group_walls(reports)
    if walls:
        terminalreporter.write_line(format_group_walls(walls, sandbox_group_count()))
