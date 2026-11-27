"""Mutants for SPEC_CHAT_APPLY_REPLY PR1 (`--via ui` on apply, prd reply and patch-read-run; the actor recorded; one patch reading per job at a time).
Applied alone; killed = a test FAILED (or timed out). Run in a throwaway worktree, never in the live checkout.
Equivalent in behaviour (documented, not mutated further): removing the REVIEW_READY check inside the reader's lock (the bundle step refuses a job
without a package before it); `-k` selections below name every new test, so a renamed test shows as STALE or as a survivor.
Usage: <this> <worktree> <python> [name-part ...]"""
import os
import subprocess
import sys
from pathlib import Path

WT, PY = Path(sys.argv[1]), sys.argv[2]
ONLY = sys.argv[3:]
A, J, P, R, C = "router/apply.py", "router/job.py", "router/prd_job.py", "router/patch_read_run.py", "scripts/argus.py"
T_APPLY = ["tests/test_apply_cmd.py", "-k", "via or heals"]
T_ACTOR = ["tests/test_actor_record.py", "tests/test_apply_cmd.py", "-k", "actor or via or heals"]
T_READ = ["tests/test_patch_read_run.py"]
T_PRD = ["tests/test_prd_writer.py", "-k", "via or writing"]
NOTE = 'job.note(deps, "patch_read_run", sha12=sha[:12], cap_usd=cap_usd, actor=rj.actor(via), **({"via": via} if via else {}))'
M = [
    ("apply: via is not put in extra", A, [('    if via:\n        extra["via"] = via', '    if False:\n        extra["via"] = via')], T_APPLY),
    ("apply: via is put in extra only after the recovery check", A, [('    if via:\n        extra["via"] = via', '    if False:\n        extra["via"] = via'),
                                                                  ('        # SPEC_KARTU_SETUJU 5: an item of a PRD queue needs a fresh', '        if via:\n            extra["via"] = via\n        # SPEC_KARTU_SETUJU 5: an item of a PRD queue needs a fresh')], T_APPLY),
    ("apply: via is not validated", A, [('    if via is not None and via not in rj.VIA:', '    if False:')], T_APPLY),
    ("apply: via is not passed to _apply", A, [('accept=reason, via=via)', 'accept=reason)')], T_APPLY),
    ("record: the actor ignores via", J, [('by=os.environ.get("USER"), actor=actor(via),\n             **({"note": note} if note else {}), **({"examples_failed": failed} if failed else {}), **extra)', 'by=os.environ.get("USER"), actor=actor(),\n             **({"note": note} if note else {}), **({"examples_failed": failed} if failed else {}), **extra)')], T_APPLY),
    ("record: via is not a named parameter (it lands in the entry)", J, [('allow_failed_examples=(), via=None, **extra):', 'allow_failed_examples=(), **extra):'),
                                                                         ('by=os.environ.get("USER"), actor=actor(via),\n             **({"note": note} if note else {}), **({"examples_failed": failed} if failed else {}), **extra)', 'by=os.environ.get("USER"), actor=actor(extra.get("via")),\n             **({"note": note} if note else {}), **({"examples_failed": failed} if failed else {}), **extra)')], T_APPLY),
    ("actor: via wins over a Claude shell", J, [('    if os.environ.get("CLAUDECODE"):\n        return "claude"\n    return "ui" if via == "ui" else "terminal"',
                                                '    if via == "ui":\n        return "ui"\n    return "claude" if os.environ.get("CLAUDECODE") else "terminal"')], T_ACTOR),
    ("reader: no note", R, [(NOTE, 'pass')], T_READ),
    ("reader: the note ignores via for the actor", R, [(NOTE, NOTE.replace("actor=rj.actor(via)", "actor=rj.actor()"))], T_READ),
    ("reader: the note has no via field", R, [(NOTE, NOTE.replace(', **({"via": via} if via else {})', ''))], T_READ),
    ("reader: the note is written before live (even when live refuses)", R, [('    with rj.live(deps, plan[0][1], [pt.ROLE], msg):\n        with job.lock():',
                                                                              '    with job.lock():\n        ' + NOTE + '\n    with rj.live(deps, plan[0][1], [pt.ROLE], msg):\n        with job.lock():')], T_READ),
    ("reader: via is not validated", R, [('    if via is not None and via not in rj.VIA:', '    if False:')], T_READ),
    ("reader: no one-at-a-time lock", R, [('    with _one_run_at_a_time(job_id, jobs_dir):\n        return _run(', '    if True:\n        return _run(')], T_READ),
    ("reader: the lock fd is not closed", R, [('    finally:\n        os.close(fd)\n\n\ndef run(', '    finally:\n        pass\n\n\ndef run(')], T_READ),
    ("reader: the lock blocks instead of refusing", R, [('fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)', 'fcntl.flock(fd, fcntl.LOCK_EX)')], T_READ),
    ("reader: the lock is the job lock (the reading cannot be written)", R, [('    fd = os.open(job.dir / ".patch_read_run.lock", os.O_RDWR | os.O_CREAT, 0o600)', '    fd = os.open(job.dir / ".lock", os.O_RDWR | os.O_CREAT, 0o600)')], T_READ),
    ("cli: patch-read-run drops via", C, [('first=o.first, second=o.second, via=o.via)', 'first=o.first, second=o.second)')], T_READ),
    ("cli: prd reply drops via", C, [('rebase=o.rebase, via=o.via)', 'rebase=o.rebase)')], T_PRD),
    ("cli: apply drops via", C, [('accept_concerns=o.accept_concerns, via=o.via)', 'accept_concerns=o.accept_concerns)')], T_APPLY),
    ("prd reply: the move ignores via for the actor", P, [('actor=rj.actor(via), **({"via": via} if via else {}))', 'actor=rj.actor(), **({"via": via} if via else {}))')], T_PRD),
    ("prd reply: the move has no via field", P, [('actor=rj.actor(via), **({"via": via} if via else {}))', 'actor=rj.actor(via))')], T_PRD),
    ("prd reply: via is not validated", P, [('    if via is not None and via not in rj.VIA:\n        raise rj.Refused(f"via {via!r} is not one of {\', \'.join(rj.VIA)}; nothing was started")\n    job = rj.open_job(job_id, jobs_dir)\n    with job.lock():\n        if job.data.get("kind") != "prd":',
                                              '    job = rj.open_job(job_id, jobs_dir)\n    with job.lock():\n        if job.data.get("kind") != "prd":')], T_PRD),
]
killed = 0
ran = 0
for name, f, edits, tests in M:
    if ONLY and not any(o in name for o in ONLY):
        continue
    p = WT / f
    orig = p.read_text()
    text = orig
    if any(text.count(a) != 1 for a, _ in edits):
        print("STALE  ", name, [text.count(a) for a, _ in edits], flush=True)
        continue
    for a, b in edits:
        text = text.replace(a, b, 1)
    p.write_text(text)
    ran += 1
    try:
        r = subprocess.run([PY, "-m", "pytest", "-x", "-q", "-p", "no:cacheprovider", *tests], cwd=WT, capture_output=True, text=True, timeout=240,
                           env={**os.environ, "PYTHONPATH": f"{WT}:{WT}/scripts:{WT}/tests"})
        dead = r.returncode != 0
    except subprocess.TimeoutExpired:
        dead = True
    finally:
        p.write_text(orig)
    killed += dead
    print("killed " if dead else "SURVIVED", name, flush=True)
print(f"{killed}/{ran} killed")
