"""Mutants for SPEC_APPLY_ACCEPT_CONCERNS (router/apply.py, router/patch_read.py, router/job.py, scripts/argus.py): each applied alone in a worktree;
killed = a test FAILED and pytest reported no error. Usage: <this> <worktree> <python> [name fragments]. Tests: the accept section of tests/test_apply_cmd.py
and the patch-read tests."""
import subprocess
import sys
from pathlib import Path

WT, PY = Path(sys.argv[1]), sys.argv[2]
ONLY = sys.argv[3:]
A, P, J, C = "router/apply.py", "router/patch_read.py", "router/job.py", "scripts/argus.py"
T = ["-rfEs", "tests/test_apply_cmd.py", "tests/test_patch_read.py", "-k", "accept or flag or reason or pair or concern or plain_commit or crash_after or cli_applies or reader or another_patch or other_checks"]


def off(cond):
    return (cond, cond[: len(cond) - len(cond.lstrip())] + "if False:")


M = [
    ("the flag chooses nothing: always require_ok", A, [("        if accept is None:\n            pr.require_ok(", "        if True:\n            pr.require_ok(")]),
    ("the flag skips the reader check altogether", A, [("            seen = pr.require_concerns_pair(job, rj.last_agent(job)[0], sha, reader)[1]", "            seen = []")]),
    ("an ok pair is accepted", P, [('    if kind == "ok":\n        raise rj.Refused(f"job {job.id}: both readers said ok: nothing to accept', '    if False:\n        raise rj.Refused(f"job {job.id}: both readers said ok: nothing to accept')]),
    ("one reading is accepted", P, [('    if kind == "one":\n        raise rj.Refused(f"job {job.id}: only one patch reading: --accept', '    if False:\n        raise rj.Refused(f"job {job.id}: only one patch reading: --accept')]),
    ("a missing note is accepted", P, [('    if kind == "none":\n        raise rj.Refused(f"job {job.id}: no patch-read note: someone reads the patch first', '    if False:\n        raise rj.Refused(f"job {job.id}: no patch-read note: someone reads the patch first')]),
    ("a stale or damaged note is accepted", P, [('    if kind in ("stale", "error"):', "    if False:")]),
    ("a damaged second reading is accepted", P, [("    if not _second_ok(sec) or _model_stale(sec) or _model_stale(rec):", "    if False:")]),
    ("a stale-template second reading is accepted", P, [("    if not _second_ok(sec) or _model_stale(sec) or _model_stale(rec):", "    if not _second_ok(sec):")]),
    ("the same reader twice is accepted", P, [("    if a is None or b is None or a == b:", "    if False:")]),
    ("a reader without an id is accepted", P, [("    if a is None or b is None or a == b:", "    if a == b:")]),
    ("the --reader filter is dropped", P, [("    if reader is not None and (rec[\"reader\"][\"kind\"] != reader or sec[\"reader\"][\"kind\"] != reader):", "    if False:")]),
    ("the --reader filter checks only the second", P, [("(rec[\"reader\"][\"kind\"] != reader or sec[\"reader\"][\"kind\"] != reader)", "(sec[\"reader\"][\"kind\"] != reader)")]),
    ("the raw first reading is overwritten by the second (merged)", P, [("        if raw_pair:", "        if False:")]),
    ("the reason is not validated before the job is opened", A, [("    reason = None if accept_concerns is None else _accepted_reason(accept_concerns)    # before anything is opened or locked\n    job = rj.open_job(job_id, jobs_dir)", "    reason = accept_concerns\n    job = rj.open_job(job_id, jobs_dir)")]),
    ("no minimum length", A, [("    if not 10 <= len(t) <= 500:", "    if not len(t) <= 500:")]),
    ("no maximum length", A, [("    if not 10 <= len(t) <= 500:", "    if not 10 <= len(t):")]),
    ("a long reason is cut, not refused", A, [("    t = ex.clean(text, 10_000)", "    t = ex.clean(text, 500)")]),
    ("control characters are turned into spaces", A, [('    if not isinstance(text, str) or any(unicodedata.category(c)[0] == "C" for c in text):', "    if not isinstance(text, str):")]),
    ("a key in the reason is accepted", A, [("    if stage_data.KEY.search(t.encode()) or stage_data.KEY.search(json.dumps(t).encode()):", "    if False:")]),
    ("the trailer is always written", A, [('+ (f"\\nAccepted-concerns: {accept}" if accept is not None else "")', '+ f"\\nAccepted-concerns: {accept}"')]),
    ("the trailer is never written", A, [('+ (f"\\nAccepted-concerns: {accept}" if accept is not None else "")', '+ ""')]),
    ("the acceptance is not recorded", A, [('        extra = {**extra, "accepted_concerns": accept, "accepted_findings": [list(f) for f in seen], "accepted_sha": sha}', "        pass")]),
    ("the findings are not recorded", A, [('"accepted_findings": [list(f) for f in seen], ', '"accepted_findings": [], ')]),
    ("the status prints no accepted concerns", J, [('        if isinstance(why.get("accepted_concerns"), str):', "        if False:")]),
    ("the CLI drops the flag", C, [("accept_concerns=o.accept_concerns)", "accept_concerns=None)")]),
    ("the rerun after a crash does not need the flag", A, [("        if accept is None:\n            pr.require_ok(job, rj.last_agent(job)[0], sha, reader)\n            seen = None", "        if accept is None:\n            seen = None")]),
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
            r = subprocess.run([PY, "-m", "pytest", "-x", "-q", "-p", "no:cacheprovider", "-n", "4", *T], cwd=WT, capture_output=True, text=True, timeout=1800)
        finally:
            p.write_text(orig)
        last = (r.stdout.strip().splitlines() or [""])[-1]
        fails = [line for line in r.stdout.splitlines() if line.startswith("FAILED tests/test_")][:1]
        k = bool(fails) and "error" not in last
        killed += k
        print(f"{'KILLED ' if k else 'ERROR  ' if 'error' in last else 'SURVIVED'} {name}: {fails or last}", flush=True)
    print(f"RESULT: {killed}/{ran} killed")
