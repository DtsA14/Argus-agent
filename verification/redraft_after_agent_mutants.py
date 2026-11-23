"""Mutants for SPEC_REDRAFT_AFTER_AGENT (router/job.py): each applied alone in a worktree; killed = a test FAILED and pytest reported no error.
The list is the reviewer's (Opus, 2026-11-23) cut to the ones that are one edit. Usage: <this> <worktree> <python> [name fragments]."""
import subprocess
import sys
from pathlib import Path

WT, PY = Path(sys.argv[1]), sys.argv[2]
ONLY = sys.argv[3:]
J = "router/job.py"
T = ["-rfEs", "-n", "4", "tests/test_redraft_after_agent.py", "tests/test_report_conflict.py", "tests/test_router.py"]
M = [
    ("a confirmed old-test conflict is redrafted", J, [('if r.get("blocked_reason") == "test_conflict":', 'if r.get("blocked_reason") == "x":')]),
    ("a test_detection stop is redrafted", J, [('if str(r.get("stop_reason") or "").startswith("test_detection"):', "if False:")]),
    ("an integrity stop is redrafted", J, [('if r.get("blocked_reason") in ("contract_changed", "invalid_contract"):', "if False:")]),
    ("no fallback to the log for a detection stop", J, [('        if why.startswith("test_detection"):', "        if False:")]),
    ("no fallback to the log for a confirmed conflict", J, [('        if "the harness confirmed its shape" in why:', "        if False:")]),
    ("AGENT_RUNNING is not a redraftable state", J, [("(DRAFT_FAILED, AWAITING_APPROVAL, AGENT_FAILED, AGENT_RUNNING):\n            raise Refused(f\"job {job.id} is {job.data['state']}: only a failed or unapproved draft is redrafted, or a job whose agent failed",
                                                   "(DRAFT_FAILED, AWAITING_APPROVAL, AGENT_FAILED):\n            raise Refused(f\"job {job.id} is {job.data['state']}: only a failed or unapproved draft is redrafted, or a job whose agent failed")]),
    ("a stopped agent needs no note", J, [('            if note is None:\n                raise Refused(f"job {job.id} is AGENT_RUNNING and nothing runs it', '            if False:\n                raise Refused(f"job {job.id} is AGENT_RUNNING and nothing runs it')]),
    ("a finished run is redrafted under a stopped stage", J, [("            if _last_result(job) is not None:        # the run finished", "            if False:        # the run finished")]),
    ("a failed agent needs no note", J, [('            if note is None:\n                raise Refused(f"job {job.id} is AGENT_FAILED: a redraft after an agent that failed needs a note', '            if False:\n                raise Refused(f"job {job.id} is AGENT_FAILED: a redraft after an agent that failed needs a note')]),
    ("the refusal kinds are not checked", J, [("            why = _redraft_refusal(job)\n            if why is not None:", "            why = _redraft_refusal(job)\n            if False:")]),
    ("the stage is not marked interrupted", J, [('status="INTERRUPTED", usd=', "status=None, usd=")]),
    ("the interrupted stage forgets its spend", J, [("usd=runs_spent_nano(job.runs, {sid: stage}) / 1e9)", "usd=0.0)")]),
    ("the stage is not moved to AGENT_FAILED", J, [('                job.move(AGENT_FAILED, deps, stage=sid, reason="interrupted: the agent\'s process stopped before it finished; the draft is redone by a human")', "                pass")]),
    ("the callback is never called", J, [("            if before_move is not None:\n                before_move()", "            if False:\n                before_move()")]),
    ("the stage is closed before the confirmation", J, [("        return job, _draft(job, cfg, deps, n, note=note, note_by=note_by, before_move=before_move, warn=warn)",
                                                       "        if before_move:\n            before_move()\n        return job, _draft(job, cfg, deps, n, note=note, note_by=note_by, before_move=None, warn=warn)")]),
    ("the log does not say interrupted_agent", J, [('**({"after": "interrupted_agent"} if interrupted else {}))', "**({}))")]),
    ("the warning is not shown", J, [("*environment_lines(job), *([warn] if warn else [])])", "*environment_lines(job)])")]),
    ("the warning never fires", J, [("    if left - cap >= need:\n        return None", "    if True:\n        return None")]),
    ("status offers redraft after a refused kind", J, [("may_redraft = (d[\"state\"] == AGENT_FAILED and not redraftable and _redraft_refusal(job) is None", "may_redraft = (d[\"state\"] == AGENT_FAILED and not redraftable")]),
    ("status offers a retry after a killed agent", J, [("if _killed and may_redraft", "if False and may_redraft")]),
    ("status suggests redraft after an infrastructure stop", J, [('not in ("sandbox_unavailable", "provider_failed"))', "not in ())")]),
]

if __name__ == "__main__":
    killed = ran = 0
    for name, F, edits in M:
        if ONLY and not any(o in name for o in ONLY):
            continue
        p = WT / F
        orig = p.read_text()
        text = orig
        stale = [a[:70] for a, _ in edits if text.count(a) != 1]
        if stale:
            print(f"STALE   {name}: {stale}", flush=True)
            continue
        for a, b in edits:
            text = text.replace(a, b, 1)
        p.write_text(text)
        ran += 1
        try:
            r = subprocess.run([PY, "-m", "pytest", "-x", "-q", "-p", "no:cacheprovider", *T], cwd=WT, capture_output=True, text=True, timeout=900)
        finally:
            p.write_text(orig)
        last = (r.stdout.strip().splitlines() or [""])[-1]
        fails = [line for line in r.stdout.splitlines() if line.startswith("FAILED tests/test_")][:1]
        k = bool(fails) and "error" not in last
        killed += k
        print(f"{'KILLED ' if k else 'ERROR  ' if 'error' in last else 'SURVIVED'} {name}: {fails or last}", flush=True)
    print(f"RESULT: {killed}/{ran} killed")
