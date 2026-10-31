"""Mutants for SPEC_CONFLICT_GATE (argus approve refuses a draft that flags EXISTING TEST CONFLICT): each applied alone in
a worktree, the named tests run with -x; killed = a test of tests/test_conflict_gate.py FAILED and pytest reported no
error (an import or fixture error, or a skip, is not a kill). Usage: <this> <worktree> <python>"""
import subprocess
import sys
from pathlib import Path

WT, PY = Path(sys.argv[1]), sys.argv[2]
J, D = "router/job.py", "acceptance/draft.py"
T = ["-rfEs", "tests/test_conflict_gate.py"]
GATE = """        refusal = _conflict_refusal(job, draft, "approved")
        if refusal:
            raise refusal
"""
CAP = """        text = _limits_text(job, "approve and run the agent", lines)
"""
WEB = """        if why:
            raise Refused(f"job {job.id}: {why}; nothing was approved")
"""
M = [
    # C1 / G1, G7
    ("gate removed", J, [(GATE, "")]),
    ("gate after the cap check", J, [(GATE, ""), (CAP, GATE + CAP)]),
    ("gate after the web check", J, [(GATE, ""), (WEB, WEB + GATE)]),
    # G2: which entries, where in them, how spelled
    ("only the first entry read", D, [('for u in draft.get("unverifiable") or [] if isinstance(u, str)',
                                       'for u in (draft.get("unverifiable") or [])[:1] if isinstance(u, str)')]),
    ("only at the start of an entry", D, [("isinstance(u, str) and CONFLICT_RE.search(u)]",
                                           "isinstance(u, str) and CONFLICT_RE.match(u)]")]),
    ("case-sensitive", D, [('conflicts?", re.IGNORECASE)', 'conflicts?")')]),
    ("exact spelling only", D, [('CONFLICT_RE = re.compile(r"existing[\\s_-]*tests?[\\s_-]*conflicts?", re.IGNORECASE)',
                                 'CONFLICT_RE = re.compile(r"EXISTING TEST CONFLICT")')]),
    # G4
    ("not checked for a failed redraft", J, [(GATE, GATE.replace("        if refusal:",
                                                                 '        if refusal and job.data["state"] == AWAITING_APPROVAL:'))]),
    # G5
    ("status without conflict lines", J, [('        out += [*conflict_lines(draft), f"draft {sha[:12]}',
                                           '        out += [f"draft {sha[:12]}')]),
    # every approve path, retry
    ("dr.approve does not check", D, [("    if conflict_entries(draft):            # SPEC_CONFLICT_GATE",
                                       "    if False:            # SPEC_CONFLICT_GATE")]),
    ("retry does not check", J, [('        refusal = _conflict_refusal(job, json.loads(_last_draft(job)[1].read_text(encoding="utf-8")), "retried")\n        if refusal:',
                                  '        refusal = _conflict_refusal(job, json.loads(_last_draft(job)[1].read_text(encoding="utf-8")), "retried")\n        if False:')]),
    # the marker is the drafter's
    ("marker text changed", D, [('CONFLICT = "EXISTING TEST CONFLICT"', 'CONFLICT = "EXISTING TEST CONFLICTS"')]),
]

if __name__ == "__main__":
    killed = 0
    for name, f, edits in M:
        p = WT / f
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
        fails = [line for line in r.stdout.splitlines() if line.startswith("FAILED tests/test_conflict_gate.py")][:1]
        k = bool(fails) and "error" not in last
        killed += k
        verdict = "KILLED " if k else "SKIPPED" if "skipped" in last else "ERROR  " if "error" in last else "SURVIVED"
        print(f"{verdict} {name}: {fails or last}", flush=True)
    print(f"RESULT: {killed}/{len(M)} killed")
