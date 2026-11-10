"""Mutants for SPEC_ISSUE_WRITER amendment 3 (an issue that clashes says so): each guarantee broken alone; killed = a
test failed. Usage: <this> <worktree> <python>"""
import subprocess
import sys
from pathlib import Path

WT, PY = Path(sys.argv[1]), sys.argv[2]
W = "codetask/issue_writer.py"
T = ["tests/test_issue_writer.py"]
M = [
    ("claim allowed", W, "        if UNCHANGED.search(issue):", "        if False:"),
    ("claim case-sensitive", W, 'UNCHANGED = re.compile(r"keeps? passing unchanged", re.IGNORECASE)',
     'UNCHANGED = re.compile(r"keeps? passing unchanged")'),
    ("only 'keep'", W, 'UNCHANGED = re.compile(r"keeps? passing unchanged", re.IGNORECASE)',
     'UNCHANGED = re.compile(r"keep passing unchanged", re.IGNORECASE)'),
    ("clash files not named", W, "        if missing:", "        if False:"),
    ("claim refused without clashes", W, "    if kept and isinstance(issue, str) and issue.strip():",
     "    if isinstance(issue, str) and issue.strip():"),
    ("version kept", W, '"SubmitIssue": "4"}', '"SubmitIssue": "3"}'),
    ("prompt still claims", W, "\"tests keep passing unchanged.' when nothing clashes. When something clashes, end it instead with 'A human loosens \"\n",
     "\"tests keep passing unchanged.' when nothing clashes. When something clashes, end it instead with 'A person loosens \"\n"),
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
