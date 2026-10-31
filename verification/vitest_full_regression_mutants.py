"""Mutants for SPEC_VITEST_FULL_REGRESSION (a vitest draft names every existing test file in a validation): each
applied alone in a worktree, the named tests run with -x; killed = a test failed (an error or a skip is not a kill; a
run with a skip is reported as SKIPPED). Usage: <this> <worktree> <python>"""
import subprocess
import sys
from pathlib import Path

WT, PY = Path(sys.argv[1]), sys.argv[2]
D, DR = "acceptance/draft.py", "codetask/drafter.py"
T = ["-rs", "tests/test_vitest_full_regression.py"]
M = [
    # F1 / G1, G5
    ("check removed", D, "    return problems + full_regression_problems(draft, contract, base_files)",
     "    return problems", T),
    ("missing file not refused", D, "            if f not in named:", "            if False:", T),
    ("only the first validation counts", D,
     'named = {f for v in contract["validation"] if kind(v) == "vitest" for f in v["args"][1:]}',
     'named = {f for v in contract["validation"][:1] if kind(v) == "vitest" for f in v["args"][1:]}', T),
    # G3
    ("new tests counted as old", D, '        if f in new or "node_modules" in f.split("/"):',
     '        if "node_modules" in f.split("/"):', T),
    # G4
    ("held to Python too", D, '    if draft_runners(draft["contract"]) != {"vitest"}:\n        return []',
     "    if False:\n        return []", T),
    # F1b / G7
    ("unrunnable test files not refused", D, '        elif VITEST_LIKE.search(f.rsplit("/", 1)[-1]):', "        elif False:", T),
    ("node_modules counted", D, '        if f in new or "node_modules" in f.split("/"):', "        if f in new:", T),
    # F3
    ("old prompt back", DR, '"- Name every existing test file (*.test.*) in a validation: the harness refuses a draft that leaves one out, "',
     '"- Keep a regression validation of existing tests when the change can break them. "', T),
    ("conflict marker dropped", DR, "`EXISTING TEST CONFLICT: <file>::<test name>`", "a note", T),
    # G6 (F2): an old file named only in a red validation must still pass on the baseline
    ("red validation may fail more than its new tests", D, '        if e.get("errors") or e.get("failures") != len(new):',
     '        if e.get("errors"):', T),
]

if __name__ == "__main__":
    killed = 0
    for name, f, old, new, tests in M:
        p = WT / f
        orig = p.read_text()
        assert orig.count(old) == 1, (name, orig.count(old))
        p.write_text(orig.replace(old, new, 1))
        try:
            r = subprocess.run([PY, "-m", "pytest", "-x", "-q", "-p", "no:cacheprovider", *tests], cwd=WT,
                               capture_output=True, text=True, timeout=1800)
        finally:
            p.write_text(orig)
        last = (r.stdout.strip().splitlines() or [""])[-1]
        k = "failed" in last
        killed += k
        fails = [line for line in r.stdout.splitlines() if line.startswith("FAILED")][:1]
        verdict = "KILLED " if k else "SKIPPED" if "skipped" in last else "SURVIVED"
        print(f"{verdict} {name}: {fails or last}", flush=True)
    print(f"RESULT: {killed}/{len(M)} killed")
