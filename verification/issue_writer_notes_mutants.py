"""Mutants for SPEC_ISSUE_WRITER amendment 2 (the writer's notes on the repository, carried to its later turns): each
guarantee broken alone; killed = a test failed. Usage: <this> <worktree> <python>"""
import subprocess
import sys
from pathlib import Path

WT, PY = Path(sys.argv[1]), sys.argv[2]
I, W = "router/issue.py", "codetask/issue_writer.py"
T = ["tests/test_issue_writer.py"]
M = [
    ("notes unchecked", W, '        why = text_problem(notes, "notes", NOTES_MAX)', "        why = None"),
    ("markers allowed", W, '        if "<<<" in notes or ">>>" in notes:', "        if False:"),
    ("notes not text taken", W, "    if notes is not None and not isinstance(notes, str):", "    if False:"),
    ("checked before the strip", W, "    notes = notes.strip() or None if isinstance(notes, str) else None",
     "    notes = (notes if notes.strip() else None) if isinstance(notes, str) else None"),
    ("notes not kept", I, '        job.data["repo_notes"] = w["notes"]\n', "        pass\n"),
    ("no notes erase the old", I, '    if w.get("notes"):                              # the writer',
     '    if True:                              # the writer'),
    ("notes not in the prompt", I, '"notes": job.data.get("repo_notes"),', '"notes": None,'),
    ("prompt drops the notes", W, '    if inputs.get("notes"):\n', '    if False:\n'),
    ("version kept", W, '"SubmitIssue": "3"}', '"SubmitIssue": "2"}'),
    ("not told to use them", W, '    "- Your notes from earlier turns, when the prompt has them, describe this same commit: use them and read a file "\n'
     '    "again only for a detail they lack. With every submit, leave in `notes` what a later turn would need (files, what "\n'
     '    "they hold, the tests that touch them, exact classes and texts), or nothing to keep the earlier notes.",\n', ""),
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
