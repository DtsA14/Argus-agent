"""Mutants for R1 reading `>>>` blocks with doctest (acceptance/repro.py, SPEC_REPRO_DOCTEST): each applied alone in a worktree,
tests/test_repro_doctest.py and tests/test_repro.py run with -x; killed = a test FAILED and pytest reported no error.
Usage: <this> <worktree> <python>"""
import subprocess
import sys
from pathlib import Path

WT, PY = Path(sys.argv[1]), sys.argv[2]
F = "acceptance/repro.py"
T = ["-rfEs", "tests/test_repro_doctest.py", "tests/test_repro.py"]
GATE = "    if _session(code):\n        try:"
M = [
    ("a session block is skipped again", [(GATE, "    if _session(code):\n        return \"an interactive session\"\n        try:")]),
    ("the expected output is run as code", [("return [ex.source for ex in", "return [ex.source + ex.want for ex in")]),
    ("exec mode instead of single", [("'<doctest>', 'single'", "'<doctest>', 'exec'")]),
    ("+SKIP ignored", [("if not ex.options.get(doctest.SKIP)]", "if True]")]),
    ("a fresh namespace per example", [("'single'), globals())", "'single'), {{}})")]),
    ("source joined as text, not repr", [("compile({src!r},", "compile({src},")]),
    ("a bare ... line skips a session block too", [(GATE, "    if any(ln.strip() == \"...\" for ln in lines):\n        return \"bare\"\n" + GATE)]),
    ("the $ check is dropped", [("    if any(ln.startswith(\"$ \") for ln in lines):\n        return \"a shell session, not a script\"\n", "")]),
    ("the bare ... check is dropped for scripts", [("    if any(ln.strip() == \"...\" for ln in lines):\n        return \"contains a bare ... line, not a script\"\n", "")]),
    ("the size limit is dropped", [("    if len(code.encode(\"utf-8\")) > MAX_CODE_BYTES:", "    if False:")]),
    ("a parser refusal is not caught", [("        except ValueError:\n            return \"doctest examples do not parse\"", "        except KeyError:\n            return \"doctest examples do not parse\"")]),
    ("no runnable example is not skipped", [("return None if _examples(code) else \"no runnable doctest example\"", "return None")]),
    ("an empty example is kept", [("if not ex.options.get(doctest.SKIP) and ex.source.strip()]", "if not ex.options.get(doctest.SKIP)]")]),
    ("the prelude is missing from a session program", [("        return PRELUDE + \"\".join(f\"exec(", "        return \"\".join(f\"exec(")]),
]

if __name__ == "__main__":
    killed = 0
    for name, edits in M:
        p = WT / F
        orig = p.read_text()
        text = orig
        for a, b in edits:
            assert text.count(a) == 1, (name, a[:60], text.count(a))
            text = text.replace(a, b, 1)
        p.write_text(text)
        try:
            r = subprocess.run([PY, "-m", "pytest", "-x", "-q", "-p", "no:cacheprovider", *T], cwd=WT,
                               capture_output=True, text=True, timeout=1800)
        finally:
            p.write_text(orig)
        last = (r.stdout.strip().splitlines() or [""])[-1]
        fails = [line for line in r.stdout.splitlines() if line.startswith("FAILED tests/test_")][:1]
        k = bool(fails) and "error" not in last
        killed += k
        verdict = "KILLED  " if k else "SKIPPED " if "skipped" in last and not fails else "ERROR   " if "error" in last else "SURVIVED"
        print(f"{verdict} {name}: {fails or last}", flush=True)
    print(f"RESULT: {killed}/{len(M)} killed")
