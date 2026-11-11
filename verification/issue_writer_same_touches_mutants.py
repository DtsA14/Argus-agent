"""Mutants for the same-touches fix (2026-11-11: the first ledger turn changed its touches and ran out of submits): each
guarantee broken alone; killed = a test failed. Usage: <this> <worktree> <python>"""
import subprocess
import sys
from pathlib import Path

WT, PY = Path(sys.argv[1]), sys.argv[2]
W = "codetask/issue_writer.py"
T = ["tests/test_issue_writer.py"]
M = [
    ("rejection silent on touches", W, 'f"clash), then submit again with clash_check \\"{code}\\" and the SAME touches (other touches give another "\n           "list and another code):"]',
     'f"clash), then submit again with clash_check \\"{code}\\":"]'),
    ("prompt silent on touches", W, 'and submit again with that code and exactly the same touches (changing the "\n    "touches changes the list and its code).",',
     'and submit again with that code.",'),
    ("schema silent on touches", W, ' Send it with exactly "\n                                                     "the touches that list was made from.")',
     '")'),
    ("four submits", "config.yaml", "max_steps: 20, max_submits: 6}", "max_steps: 20, max_submits: 4}"),
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
