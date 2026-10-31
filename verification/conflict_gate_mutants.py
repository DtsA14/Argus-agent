"""Mutants for SPEC_CONFLICT_GATE (argus approve refuses a draft that flags EXISTING TEST CONFLICT): each applied alone in
a worktree, the named tests run with -x; killed = a test failed (an error or a skip is not a kill; a run with a skip is
reported as SKIPPED). Usage: <this> <worktree> <python>"""
import subprocess
import sys
from pathlib import Path

WT, PY = Path(sys.argv[1]), sys.argv[2]
J = "router/job.py"
T = ["-rs", "tests/test_conflict_gate.py"]
GATE = """        flagged = conflict_lines(draft)
        if flagged:
            raise Refused("""
BLOCK = """        flagged = conflict_lines(draft)
        if flagged:
            raise Refused(f"job {job.id}: the draft flags a conflict with an existing test ({flagged[0][10:310]}); "
                          "change that test by a commit of yours, then abandon this job and start a new one; nothing "
                          "was approved")
"""
CAP = """        text = _limits_text(job, "approve and run the agent", lines)
"""
M = [
    # C1 / G1, G7
    ("gate removed", J, GATE, """        flagged = conflict_lines(draft)
        if False:
            raise Refused(""", T),
    # G2
    ("only the first entry read", J, 'for u in draft.get("unverifiable") or [] if isinstance(u, str) and CONFLICT in u]',
     'for u in (draft.get("unverifiable") or [])[:1] if isinstance(u, str) and CONFLICT in u]', T),
    ("only at the start of an entry", J, "if isinstance(u, str) and CONFLICT in u]", "if isinstance(u, str) and u.startswith(CONFLICT)]", T),
    # G3: the gate moved below the cap check (a flagged draft with too small a cap would be moved to BLOCKED first)
    ("gate after the cap check", J, [(BLOCK, ""), (CAP, CAP + BLOCK)], None, T),
    # G4: not for DRAFT_FAILED
    ("not checked for a failed redraft", J, GATE, """        flagged = conflict_lines(draft)
        if flagged and job.data["state"] == AWAITING_APPROVAL:
            raise Refused(""", T),
    # G5
    ("status without conflict lines", J, """        out += [*conflict_lines(draft), f"draft {sha[:12]}""", """        out += [f"draft {sha[:12]}""", T),
    ("marker text changed", J, 'CONFLICT = "EXISTING TEST CONFLICT"', 'CONFLICT = "EXISTING TEST CONFLICTS"', T),
]
if __name__ == "__main__":
    killed = 0
    for name, f, old, new, tests in M:
        p = WT / f
        orig = p.read_text()
        text = orig
        for a, b in (old if isinstance(old, list) else [(old, new)]):
            assert text.count(a) == 1, (name, a[:40], text.count(a))
            text = text.replace(a, b, 1)
        p.write_text(text)
        try:
            r = subprocess.run([PY, "-m", "pytest", "-x", "-q", "-p", "no:cacheprovider", *tests], cwd=WT,
                               capture_output=True, text=True, timeout=1800)
        finally:
            p.write_text(orig)
        last = (r.stdout.strip().splitlines() or [""])[-1]
        k = "failed" in last
        killed += k
        fails = [line for line in r.stdout.splitlines() if line.startswith("FAILED")][:1]
        verdict = "KILLED " if k else "SKIPPED" if "skipped" in last else "SURVIVED"
        print(f"{verdict} {name}: {fails or last}", flush=True)
    print(f"RESULT: {killed}/{len(M)} killed")
