"""Mutants for SPEC_GATE_RC_CLARIFICATIONS (D1, P1 and the recorded behaviour): each applied alone in a worktree, the detection tests run with -x;
killed = a test FAILED and pytest reported no error. Usage: <this> <worktree> <python>"""
import subprocess
import sys
from pathlib import Path

WT, PY = Path(sys.argv[1]), sys.argv[2]
T = ["-rfEs", "tests/test_gate_rc_clarifications.py", "tests/test_o2_comments.py", "tests/test_test_detection.py"]
TD, VD, RUN = "acceptance/testdetect.py", "acceptance/verdict.py", "codetask/run.py"
M = [
    ("D1 undone: detection patterns read raw lines", TD, [("target = view[n - 1]\n", "target = view[n - 1] if name in FORGERS else line\n")]),
    ("D1: view not used at all", TD, [("view = _code_view(text).split(\"\\n\") if py else lines", "view = lines")]),
    ("D1: JS narrowed too", TD, [("        py = PurePosixPath(path).suffix == \".py\"\n", "        py = True\n")]),
    ("D1: unsure file blanked instead of scanned wide", TD, [("    except Exception:\n        return _fallback(text, uncertain)\n\n\ndef _hits", "    except Exception:\n        return \"\\n\".join(\"\" for _ in text.split(\"\\n\"))\n\n\ndef _hits")]),
    ("P1 undone: the name alone exempts", TD, [("(is_test_file(path) and not _scanned_test_file(path, scope))", "is_test_file(path)")]),
    ("P1: protected ignored", TD, [(" and not matches(path, scope[\"protected\"])", "")]),
    ("P1: writable ignored (any scope scans)", TD, [("matches(path, scope[\"writable\"]) and", "True and")]),
    ("P1: protected only exempts, writable inverted", TD, [("scope is not None and matches(path, scope[\"writable\"])", "scope is not None and not matches(path, scope[\"writable\"])")]),
    ("P1: verdict does not pass the scope", VD, [("                                     contract[\"scope\"]))", "                                     None))")]),
    ("old file always read narrowed", TD, [("_hits(old, py and not wide)", "_hits(old, py)")]),
    ("blocked attempt no longer wins over a hit", RUN, [("        if v[\"outcome\"] == \"blocked\":\n            why =", "        if False:\n            why =")]),
]

if __name__ == "__main__":
    killed = 0
    for name, F, edits in M:
        p = WT / F
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
        fails = [line for line in r.stdout.splitlines() if line.startswith("FAILED tests/test_")][:1]
        k = bool(fails) and "error" not in last
        killed += k
        verdict = "KILLED " if k else "SKIPPED" if "skipped" in last and not fails else "ERROR  " if "error" in last else "SURVIVED"
        print(f"{verdict} {name}: {fails or last}", flush=True)
    print(f"RESULT: {killed}/{len(M)} killed")
