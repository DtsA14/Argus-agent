"""Mutants for VERIFY-HARDENING (scripts/precheck.sh, scripts/precheck_select.py, scripts/verify.sh, scripts/verify_at.sh, conftest.py,
tests/sandbox_scope.py; SPEC_VERIFY_HARDENING): each applied alone in a worktree, the tests below run with -x; killed = a test FAILED and
pytest reported no error. Needs the image pins in the environment (the scope test uses the sandbox).
Usage: <this> <worktree> <python>   (--check: only count the patterns)"""
import os
import subprocess
import sys
from pathlib import Path

S, V, VA, C, PC, SC, X = ("scripts/precheck_select.py", "scripts/verify.sh", "scripts/verify_at.sh", "conftest.py", "scripts/precheck.sh",
                          "tests/sandbox_scope.py", None)
T = ["-rfEs", "tests/test_verify_hardening.py", "tests/test_xdist_groups.py", "tests/test_verify_at.py",
     "tests/test_sandbox.py::test_the_scope_helpers_see_only_the_containers_of_their_own_token"]
M = [
    # which tests the pre-check picks
    ("the fixed set is dropped", [(S, "out = {t for t in FIXED if t in existing}", "out = set()")]),
    ("a fixed test that does not exist is invented", [(S, "out = {t for t in FIXED if t in existing}", "out = set(FIXED)")]),
    ("a touched test module need not exist", [(S, 'if path in existing and p.name.startswith("test_"):', 'if p.name.startswith("test_"):')]),
    ("a touched test module is not selected", [(S, 'if path in existing and p.name.startswith("test_"):', "if False:")]),
    ("a touched source module is matched by substring", [(S, 'out |= {t for t in existing if Path(t).name.startswith(f"test_{p.stem}")}', 'out |= {t for t in existing if p.stem in Path(t).name}')]),
    ("a touched source module selects nothing", [(S, 'out |= {t for t in existing if Path(t).name.startswith(f"test_{p.stem}")}', "pass")]),
    ("a file that is not python is considered", [(S, 'if p.suffix != ".py":', "if False:")]),
    # the pre-check script
    ("the base is not checked", [(PC, 'if ! git rev-parse --verify -q "$BASE^{commit}" >/dev/null; then', "if false; then")]),
    ("untracked files are not seen", [(PC, "git -c core.quotePath=false ls-files --others --exclude-standard;", "true;")]),
    ("the metadata of a pin is exported as a pin", [(PC, "*.json) continue ;;", "*.json) : ;;")]),
    ("the plain pin is not exported", [(PC, 'if [ -f .sandbox_image ]; then', "if false; then")]),
    ("the pin variable keeps its case", [(PC, "| tr 'a-z' 'A-Z')", "| cat)")]),
    ("the scheduling of verify.sh is not used", [(PC, "ARGS=(-q -rs -p no:cacheprovider -n 4 --dist loadgroup)", "ARGS=(-q -rs -p no:cacheprovider -n 1)")]),
    # the durations and the opt-in fail-fast
    ("only the top 25 durations", [(V, "--durations=0 --durations-min=1.0", "--durations=25")]),
    ("fail-fast is not passed on", [(V, ' "${PYTEST_EXTRA[@]}" 2>&1', " 2>&1")]),
    ("fail-fast stops at one whatever it is told", [(V, '--maxfail="$VERIFY_MAXFAIL"', "--maxfail=1")]),
    ("fail-fast is not said in the log", [(V, 'echo "maxfail: $VERIFY_MAXFAIL (a failing run stops early: not a full run)"', "true")]),
    # the group totals
    ("the sandbox keyword is another one", [(C, '"xdist_group" in (getattr(r, "keywords", None) or {})', '"sandbox" in (getattr(r, "keywords", None) or {})')]),
    ("a duration replaces the sum", [(C, 'g["seconds"] += getattr(r, "duration", None) or 0.0', 'g["seconds"] = getattr(r, "duration", None) or 0.0')]),
    ("a test is counted by its setup", [(C, 'g["tests"] += getattr(r, "when", None) == "call"', 'g["tests"] += getattr(r, "when", None) == "setup"')]),
    ("the totals have two decimals", [(C, "sandbox {s['seconds']:.1f}", "sandbox {s['seconds']:.2f}")]),
    ("only passed reports are totalled", [(C, "for reports in terminalreporter.stats.values() for r in reports", "for r in terminalreporter.stats.get('passed', [])")]),
    # grouping by fixture
    ("the fixtures are not looked at", [(C, "if uses_sandbox(item.fspath) or any(uses_sandbox(f) for f in _fixture_files(item)):", "if uses_sandbox(item.fspath):")]),
    ("only the direct fixtures are looked at", [(C, 'for name in getattr(item, "fixturenames", ()):', 'for name in getattr(getattr(item, "_fixtureinfo", None), "argnames", ()):')]),
    ("the conftest file counts as a sandbox file", [(C, 'SANDBOX_TEXT = "SANDBOX NOT " "AVAILABLE"', 'SANDBOX_TEXT = "SANDBOX_TEXT"')]),
    # a signal and the worktree
    ("a signal does not kill the grandchildren", [(VA, 'do echo "$c"; descendants "$c"; done', 'do echo "$c"; done')]),
    ("only the term signal is handled", [(VA, "trap on_signal INT TERM", "trap on_signal TERM")]),
    ("the listed descendants are not killed", [(VA, '    kill $all 2>/dev/null || true\n', "    :\n")]),
    # the review's findings
    ("the group is not killed", [(VA, 'kill -TERM -- "-$vpid" 2>/dev/null || true', "true")]),
    ("verify.sh does not run in its own group", [(VA, "exec setsid -w bash scripts/verify.sh", "exec bash scripts/verify.sh")]),
    ("a wrapped fixture is not unwrapped", [(C, "func = inspect.unwrap(fd.func)", "func = fd.func")]),
    ("non-ascii paths are quoted", [(PC, "git -c core.quotePath=false diff --name-only", "git diff --name-only")]),
    ("untracked non-ascii paths are quoted", [(PC, "git -c core.quotePath=false ls-files", "git ls-files")]),
    ("the tests are split on spaces", [(PC, 'exec "$PY" -m pytest "${ARGS[@]}" "${tests[@]}"', 'exec "$PY" -m pytest "${ARGS[@]}" ${tests[*]}')]),
    ("an empty selection runs on", [(PC, 'if [ "${#tests[@]}" -eq 0 ] || [ -z "${tests[0]}" ]; then', "if false; then")]),
    # the scope helper
    ("the scope filter is dropped", [(SC, '"--filter", "label=argus.sandbox=1",\n                        "--filter", f"label=argus.test={token}"]', '"--filter", "label=argus.sandbox=1"]')]),
    ("removing a token's containers does nothing", [(SC, 'subprocess.run(["docker", "rm", "-f", *found], capture_output=True)', "pass")]),
]

if __name__ == "__main__":
    WT, PY = Path(sys.argv[1]), sys.argv[2]
    check_only = "--check" in sys.argv
    killed = 0
    for name, edits in M:
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
    print("patterns ok" if check_only else f"RESULT: {killed}/{len(M)} killed")
