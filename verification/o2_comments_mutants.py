"""Mutants for the O2 comment/docstring narrowing (acceptance/testdetect.py): each applied alone in a worktree, tests/test_o2_comments.py and
tests/test_test_detection.py run with -x; killed = a test FAILED and pytest reported no error. Usage: <this> <worktree> <python>"""
import subprocess
import sys
from pathlib import Path

WT, PY = Path(sys.argv[1]), sys.argv[2]
F = "acceptance/testdetect.py"
T = ["-rfEs", "tests/test_o2_comments.py", "tests/test_test_detection.py"]
M = [
    ("no narrowing at all", [("view = _code_view(text).split(\"\\n\") if py else lines", "view = lines")]),
    ("comments not blanked", [("            if tok.type == tokenize.COMMENT:", "            if False:")]),
    ("docstrings not blanked", [("            if isinstance(node, ast.Expr) and", "            if False and isinstance(node, ast.Expr) and")]),
    ("f-string statements blanked too", [("isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):", "isinstance(node.value, (ast.Constant, ast.JoinedStr)):")]),
    ("ast byte columns used as characters", [("sc = len(lines[a].encode(\"utf-8\")[:node.col_offset].decode(\"utf-8\", \"ignore\"))      # ast columns are bytes", "sc = node.col_offset")]),
    ("bare carriage return not guarded", [("        if re.search(r\"\\r(?!\\n)\", text):\n            return text                              # Python counts a bare \\r as a line end, split(\"\\n\") does not\n", "")]),
    ("a file that does not parse is blanked", [("    except Exception:\n        return text\n\n\ndef _hits", "    except Exception:\n        return \"\\n\".join(\"\" for _ in text.split(\"\\n\"))\n\n\ndef _hits")]),
    ("whole line blanked from a comment", [("spans.append((tok.start[0] - 1, tok.start[1], tok.end[0] - 1, tok.end[1]))", "spans.append((tok.start[0] - 1, 0, tok.end[0] - 1, tok.end[1]))")]),
    ("pattern detection narrowed too", [("target = view[n - 1] if name in FORGERS else line", "target = view[n - 1]")]),
    ("javascript narrowed too", [("        py = PurePosixPath(path).suffix == \".py\"\n", "        py = True\n")]),
    ("no cutoff for a very long line", [("        if len(max(text.split(\"\\n\"), key=len)) > MAX_VIEW_LINE:", "        if False:")]),
    ("baseline scanned wide", [("for _, name, line in _hits(old, py))", "for _, name, line in _hits(old))")]),
]

if __name__ == "__main__":
    killed = 0
    for name, edits in M:
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
