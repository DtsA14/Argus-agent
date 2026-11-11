"""Mutants for 'a clash is a test that WILL fail' (2026-11-11: the viewer title issue listed every line shown as a
clash): each guarantee broken alone; killed = a test failed. Usage: <this> <worktree> <python>"""
import subprocess
import sys
from pathlib import Path

WT, PY = Path(sys.argv[1]), sys.argv[2]
W = "codetask/issue_writer.py"
T = ["tests/test_issue_writer.py"]
M = [
    ("rejection asks for every line", W,
     '"file(s). They are not clashes by themselves: read them, and put in clashes only a test that WILL fail with "',
     '"file(s); read the lines your change may break and put each in clashes; only a test that WILL fail with "'),
    ("rejection silent on passing lines", W, '; a line that keeps "\n           f"passing needs nothing. Then',
     '. "\n           f"Then'),
    ("prompt silent on maybe clashes", W,
     ' A test that only might "\n    "fail, or would fail only with data it does not have (e.g. a field its fixtures lack), is no clash: leave it out.",',
     '",'),
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
                               capture_output=True, text=True, timeout=900)
        finally:
            p.write_text(orig)
        last = (r.stdout.strip().splitlines() or [""])[-1]
        k = r.returncode == 1 and "failed" in last          # a test failed (not a collection or internal error)
        killed += k
        print(f"{'KILLED ' if k else 'SURVIVED'} {name}: {last}", flush=True)
    print(f"RESULT: {killed}/{len(M)} killed")
