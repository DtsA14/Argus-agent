"""Mutants for SANDBOX-SPLIT (conftest.py, tests/grouplist_plugin.py, scripts/verify.sh, scripts/precheck.sh; SPEC_SANDBOX_SPLIT): each applied
alone in a worktree, the grouping tests run with -x; killed = a test FAILED and pytest reported no error.
Usage: <this> <worktree> <python>   (--check: only count the patterns; --only <text>: only the mutants whose name has the text)"""
import os
import subprocess
import sys
from pathlib import Path

CF, GP, VS, PC = "conftest.py", "tests/grouplist_plugin.py", "scripts/verify.sh", "scripts/precheck.sh"
T = ["-rfEs", "tests/test_sandbox_split.py", "tests/test_xdist_groups.py"]
M = [
    ("the default is one group", [(CF, 'environ.get(GROUPS_ENV, "2")', 'environ.get(GROUPS_ENV, "1")')]),
    ("three is accepted", [(CF, 'if value not in ("1", "2"):', 'if value not in ("1", "2", "3"):')]),
    ("an empty value is accepted", [(CF, 'if value not in ("1", "2"):', 'if value and value not in ("1", "2"):')]),
    ("an unreadable value is read as one", [(CF, 'raise pytest.UsageError(f"{GROUPS_ENV} must be 1 or 2, not {value!r}")', 'return 1')]),
    ("one group is never used", [(CF, "    if count == 1:\n        return SANDBOX_GROUP", "    if False:\n        return SANDBOX_GROUP")]),
    ("draft goes to b and the rest to a", [(CF, "return GROUP_DRAFT if Path(str(item.fspath)).name == DRAFT_MODULE else GROUP_REST",
                                           "return GROUP_DRAFT if Path(str(item.fspath)).name != DRAFT_MODULE else GROUP_REST")]),
    ("a test that uses a fixture of draft follows draft", [(CF, "return GROUP_DRAFT if Path(str(item.fspath)).name == DRAFT_MODULE else GROUP_REST",
                                                           "return GROUP_DRAFT if Path(str(item.fspath)).name == DRAFT_MODULE or any(Path(f).name == DRAFT_MODULE for f in _fixture_files(item)) else GROUP_REST")]),
    ("the group names are swapped", [(CF, 'GROUP_DRAFT, GROUP_REST = "sandbox_a", "sandbox_b"', 'GROUP_DRAFT, GROUP_REST = "sandbox_b", "sandbox_a"')]),
    ("the draft module is another name", [(CF, 'DRAFT_MODULE = "test_draft.py"', 'DRAFT_MODULE = "test_drafts.py"')]),
    ("everything sandbox is in a", [(CF, "else GROUP_REST", "else GROUP_DRAFT")]),
    ("a non-sandbox test is grouped", [(CF, "    if not (uses_sandbox(item.fspath) or any(uses_sandbox(f) for f in _fixture_files(item))):\n        return None",
                                       "    if False:\n        return None")]),
    ("the wall is the last start to the first stop", [(CF, 'w["first"], w["last"] = min(w["first"], start), max(w["last"], stop)', 'w["first"], w["last"] = max(w["first"], start), min(w["last"], stop)')]),
    ("the group is found anywhere in the id", [(CF, 'node.endswith("@" + g)', '("@" + g) in node')]),
    ("every phase counts as a test", [(CF, 'w["tests"] += getattr(r, "when", None) == "call"', 'w["tests"] += 1')]),
    ("the walls line is never printed", [(CF, "    if walls:\n        terminalreporter.write_line(format_group_walls", "    if False:\n        terminalreporter.write_line(format_group_walls")]),
    ("the walls line names a fixed setting", [(CF, "format_group_walls(walls, sandbox_group_count())", "format_group_walls(walls, 1)")]),
    ("the worker writes the times too", [(CF, 'if not path or _is_worker or getattr(report, "when", None) != "call":', 'if not path or getattr(report, "when", None) != "call":')]),
    ("every phase is timestamped", [(CF, 'getattr(report, "when", None) != "call":\n        return\n    line', 'getattr(report, "when", None) == "never":\n        return\n    line')]),
    ("times are written without the variable", [(CF, 'path = os.environ.get(TIMES_ENV)\n    if not path or', 'path = os.environ.get(TIMES_ENV) or "/tmp/argus_times_mutant.jsonl"\n    if not path or')]),
    ("the times are in milliseconds", [(CF, '"start": report.start, "stop": report.stop}', '"start": report.start * 1000, "stop": report.stop * 1000}')]),
    ("the names are not written", [(GP, 'if os.environ.get("GROUPNAMES_OUT"):', "if False:")]),
    ("verify.sh turns the reordering off", [(VS, '--dist loadgroup "${PYTEST_EXTRA[@]}"', '--dist loadgroup --no-loadscope-reorder "${PYTEST_EXTRA[@]}"')]),
    ("verify.sh does not print the setting", [(VS, 'echo "VERIFY_SANDBOX_GROUPS=', 'echo "SETTING=')]),
    ("verify.sh does not print the xdist version", [(VS, 'echo "xdist: ', 'echo "x: ')]),
    ("the precheck does not print the setting", [(PC, 'echo "sandbox groups: ${VERIFY_SANDBOX_GROUPS:-2} (VERIFY_SANDBOX_GROUPS)"', ':')]),
]

if __name__ == "__main__":
    WT, PY = Path(sys.argv[1]), sys.argv[2]
    check_only = "--check" in sys.argv
    killed = 0
    only = sys.argv[sys.argv.index("--only") + 1] if "--only" in sys.argv else ""
    todo = [m for m in M if only in m[0]]
    for name, edits in todo:
        originals, texts = {}, {}
        for f, a, b in edits:
            texts.setdefault(f, (WT / f).read_text())
            originals.setdefault(f, texts[f])
            assert texts[f].count(a) == 1, (name, a[:70], texts[f].count(a))
            texts[f] = texts[f].replace(a, b, 1)
        if check_only:
            continue
        for f, t in texts.items():
            (WT / f).write_text(t)
        try:
            r = subprocess.run([PY, "-m", "pytest", "-x", "-q", "-p", "no:cacheprovider", *T], cwd=WT,
                               capture_output=True, text=True, timeout=1800, env=os.environ)
        finally:
            for f, t in originals.items():
                (WT / f).write_text(t)
        last = (r.stdout.strip().splitlines() or [""])[-1]
        fails = [line for line in r.stdout.splitlines() if line.startswith("FAILED tests/test_")][:1]
        k = bool(fails) and "error" not in last
        killed += k
        verdict = "KILLED  " if k else "SKIPPED " if "skipped" in last and not fails else "ERROR   " if "error" in last else "SURVIVED"
        print(f"{verdict} {name}: {fails or last}", flush=True)
    print("patterns ok" if check_only else f"RESULT: {killed}/{len(todo)} killed")
