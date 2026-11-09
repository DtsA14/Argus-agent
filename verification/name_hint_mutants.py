"""Mutants for the name hint on a required test that did not run (acceptance/validation.py named_like; 030 d1 and 031
d1 spent every submit on `<file>::<title>` for tests inside describe()): each alone; killed = a test failed.
Usage: <this> <worktree> <python>"""
import subprocess
import sys
from pathlib import Path

WT, PY = Path(sys.argv[1]), sys.argv[2]
V = "acceptance/validation.py"
T = ["tests/test_vitest_validation.py", "tests/test_pytest_validation.py", "-k", "name or not_collected"]
M = [
    ("no hint", V, '+ (named_like(t, parsed["tests"]) if st is None else ""))', ')'),
    ("any file", V, 'n.startswith(path + "::") and ', ''),
    ("bare suffix", V, 'n.endswith((" > " + title, "::" + title))', 'n.endswith(title)'),
    ("no vitest separator", V, '(" > " + title, "::" + title)', '("::" + title,)'),
    ("no pytest separator", V, '(" > " + title, "::" + title)', '(" > " + title,)'),
    ("no cap", V, "', '.join(near[:NAMED_LIKE])", "', '.join(near)"),
    ("no count of the rest", V, '{more})"', ')"'),
    ("title-less id hinted", V, '    if not title:\n        return ""\n', ''),
]

if __name__ == "__main__":
    killed = 0
    for name, f, old, new in M:
        p = WT / f
        orig = p.read_text()
        assert orig.count(old) == 1, (name, orig.count(old))
        p.write_text(orig.replace(old, new, 1))
        try:
            r = subprocess.run([PY, "-m", "pytest", "-x", "-q", "-p", "no:cacheprovider", *T], cwd=WT,
                               capture_output=True, text=True, timeout=300)
        finally:
            p.write_text(orig)
        last = (r.stdout.strip().splitlines() or [""])[-1]
        k = r.returncode == 1 and "failed" in last          # a test failed (not a collection or internal error)
        killed += k
        print(f"{'KILLED ' if k else 'SURVIVED'} {name}: {last}", flush=True)
    print(f"RESULT: {killed}/{len(M)} killed")
