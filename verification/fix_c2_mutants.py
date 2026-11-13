"""Mutants for FIX-C2 (runner.py and verdict files scrubbed, the terminal filter in every key-holding entry script, base64 of
user:key): each applied alone in a worktree, tests/test_fix_c_leaks.py and tests/test_fix_c.py run with -x; killed = a test of
those files FAILED and pytest reported no error (an import or fixture error, or a skip, is not a kill).
Usage: <this> <worktree> <python>"""
import subprocess
import sys
from pathlib import Path

WT, PY = Path(sys.argv[1]), sys.argv[2]
R, RN, RC = "harness/redact.py", "runner.py", "codetask/run.py"
T = ["-rfEs", "tests/test_fix_c_leaks.py", "tests/test_fix_c.py"]
INSTALL = "    _redact.install()                     # no registered key value reaches the terminal (FIX-C D7), chained tracebacks included\n"
M = [
    ("runner result.json not scrubbed", RN, [("json.dumps(scrub_value(result), ensure_ascii=False, indent=2)", "json.dumps(result, ensure_ascii=False, indent=2)")]),
    ("verdict file not scrubbed", RC, [("json.dumps(scrub_value(v), ensure_ascii=False, indent=2, default=str)", "json.dumps(v, ensure_ascii=False, indent=2, default=str)")]),
    ("base64: only the aligned form", R, [("    for pad in (0, 1, 2):", "    for pad in (0,):")]),
    ("base64: aligned form dropped", R, [("    for pad in (0, 1, 2):", "    for pad in (1, 2):")]),
    ("base64: shifted forms keep the filler group", R, [("out.add(enc[(4 if pad else 0):4 * groups])", "out.add(enc[0:4 * groups])")]),
    ("base64: one group too many (the unstable one)", R, [("out.add(enc[(4 if pad else 0):4 * groups])", "out.add(enc[(4 if pad else 0):4 * groups + 4])")]),
    ("base64: forms not registered", R, [("urllib.parse.quote(key, safe=\"\")} | _base64_forms(key)", "urllib.parse.quote(key, safe=\"\")}")]),
    ("main.py without the filter", "main.py", [(INSTALL, "")]),
    ("run_code_task.py without the filter", "scripts/run_code_task.py", [(INSTALL, "")]),
    ("draft_task.py without the filter", "scripts/draft_task.py", [(INSTALL, "")]),
    ("smoke_live.py without the filter", "scripts/smoke_live.py", [(INSTALL, "")]),
    ("filter named but never called", "scripts/approve_draft.py", [("    _redact.install()                     # no registered", "    _redact.uninstall()                     # no registered")]),
]

if __name__ == "__main__":
    killed = 0
    for name, f, edits in M:
        p = WT / f
        orig = p.read_text()
        text = orig
        for a, b in edits:
            assert text.count(a) == 1, (name, a[:50], text.count(a))
            text = text.replace(a, b, 1)
        p.write_text(text)
        try:
            r = subprocess.run([PY, "-m", "pytest", "-x", "-q", "-p", "no:cacheprovider", *T], cwd=WT,
                               capture_output=True, text=True, timeout=1800)
        finally:
            p.write_text(orig)
        last = (r.stdout.strip().splitlines() or [""])[-1]
        fails = [line for line in r.stdout.splitlines() if line.startswith("FAILED tests/test_fix_c")][:1]
        k = bool(fails) and "error" not in last
        killed += k
        verdict = "KILLED " if k else "SKIPPED" if "skipped" in last else "ERROR  " if "error" in last else "SURVIVED"
        print(f"{verdict} {name}: {fails or last}", flush=True)
    print(f"RESULT: {killed}/{len(M)} killed")
