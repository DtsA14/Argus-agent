"""Mutants for SPEC_ISSUE_WRITER amendment 3 (an issue that clashes says so): each guarantee broken alone; killed = a
test failed. Usage: <this> <worktree> <python>"""
import subprocess
import sys
from pathlib import Path

WT, PY = Path(sys.argv[1]), sys.argv[2]
W = "codetask/issue_writer.py"
T = ["tests/test_issue_writer.py"]
M = [
    ("claim allowed", W, "        if kept and UNCHANGED.search(unchanged_paragraph(issue)):", "        if False:"),
    ("claim searched in the whole issue", W, "        if kept and UNCHANGED.search(unchanged_paragraph(issue)):",
     "        if kept and UNCHANGED.search(issue):"),
    ("claim refused without clashes", W, "        if kept and UNCHANGED.search(unchanged_paragraph(issue)):",
     "        if UNCHANGED.search(unchanged_paragraph(issue)):"),
    ("claim case-sensitive", W, '"without\\s+(?:any\\s+)?changes?)", re.IGNORECASE)', '"without\\s+(?:any\\s+)?changes?)")'),
    ("only 'keep'", W, 'r"\\b(?:keeps?|continues?\\s+to|still)', 'r"\\b(?:keeps?)'),
    ("paragraph runs past its end", W, "        elif inside and not ln.strip():\n            break\n", ""),
    ("no clash list", W, "    if not clashes:\n        return issue\n", "    return issue\n"),
    ("list after the environment line", W, 'lines[:-1] + [""] + block + [lines[-1]]', 'lines + [""] + block'),
    ("list without its why", W, '+ f": {c[\'why\']}"', '+ ""'),
    ("stored without the list", W, '"issue": None if only else final + "\\n",', '"issue": None if only else issue.strip() + "\\n",'),
    ("no length check with the list", W, "        if len(final) > MAX_ISSUE - 1:", "        if False:"),
    ("version kept", W, '"SubmitIssue": "4"}', '"SubmitIssue": "3"}'),
    ("prompt still asks the model to write it", W, '"passing: the harness adds to the issue the list of your clashes',
     '"passing: write in the issue the list of your clashes'),
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
