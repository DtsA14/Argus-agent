"""Mutants for the drafter's refusal of a new vitest test that cannot load its module (nexus-lite pilot, 2026-11-22). Applied alone;
killed = a test FAILED. Usage: <this> <worktree> <python>"""
import subprocess
import sys
from pathlib import Path

WT, PY = Path(sys.argv[1]), sys.argv[2]
F = "codetask/drafter.py"
T = ["-q", "-p", "no:cacheprovider", "tests/test_vitest_validation.py"]
M = [
    ("the check is never called", [('        problems += unresolvable_imports(args.get("new_tests"))', '        pass')]),
    ("the check also runs for pytest", [('    if vitest:\n        problems += unresolvable_imports', '    if True:\n        problems += unresolvable_imports')]),
    ("either alone refuses", [('if DYNAMIC_IMPORT.search(code) and BUILT_SPECIFIER.search(code)', 'if DYNAMIC_IMPORT.search(code) or BUILT_SPECIFIER.search(code)')]),
    ("import( without a space only", [('DYNAMIC_IMPORT = re.compile(r"\\bimport\\s*\\(")', 'DYNAMIC_IMPORT = re.compile(r"\\bimport\\(")')]),
    ("static import counts as dynamic", [('DYNAMIC_IMPORT = re.compile(r"\\bimport\\s*\\(")', 'DYNAMIC_IMPORT = re.compile(r"\\bimport\\b")')]),
    ("new URL alone (any argument)", [('\\([^)]*import\\.meta\\.url"', '\\("')]),
    ("import.meta.resolve not caught", [('r"|import\\.meta\\.resolve\\b|\\blocation', 'r"|\\blocation')]),
    ("location not caught", [('|\\blocation\\.(?:origin|href)\\b")', '")')]),
    ("globalThis.URL not caught", [('(?:(?:globalThis|window|self)\\.)?URL', 'URL')]),
    ("comments are not stripped", [('code = LINE_COMMENT.sub("", BLOCK_COMMENT.sub("", text))', 'code = text')]),
    ("block comments only", [('LINE_COMMENT.sub("", BLOCK_COMMENT.sub("", text))', 'BLOCK_COMMENT.sub("", text)')]),
    ("line comments only", [('LINE_COMMENT.sub("", BLOCK_COMMENT.sub("", text))', 'LINE_COMMENT.sub("", text)')]),
    ("earlier problems are replaced", [('        problems += unresolvable_imports(args.get("new_tests"))', '        problems = unresolvable_imports(args.get("new_tests"))')]),
    ("the wrong field is read", [('text = t.get("content") if isinstance(t, dict) else None\n        if not isinstance', 'text = t.get("append") if isinstance(t, dict) else None\n        if not isinstance')]),
    ("the message loses the working form", [('`await import(/* @vite-ignore */ SPEC)` inside "\n                       "try/catch', '`await import(SPEC)` inside "\n                       "try/catch')]),
    ("the prompt loses the not-found filter", [("Cannot find module/.test(String(e && e.message))) return null;", "x/.test(String(e && e.message))) return null;")]),
    ("the prompt rule is deleted", [('NEVER build "\n    "the specifier with new URL', 'never build "\n    "the specifier with new URL')]),
]
killed = 0
for name, edits in M:
    p = WT / F
    orig = p.read_text()
    text = orig
    if any(text.count(a) != 1 for a, _ in edits):
        print("STALE  ", name, [text.count(a) for a, _ in edits], flush=True)
        continue
    for a, b in edits:
        text = text.replace(a, b, 1)
    p.write_text(text)
    try:
        r = subprocess.run([PY, "-m", "pytest", *T], cwd=WT, capture_output=True, text=True, timeout=600)
    finally:
        p.write_text(orig)
    k = r.returncode != 0
    killed += k
    print("KILLED " if k else "SURVIVED", name, flush=True)
print(f"RESULT: {killed}/{len(M)} killed")
