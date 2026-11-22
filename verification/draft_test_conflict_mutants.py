"""Mutants for the draft_test_conflict stop and the redraft after it (nexus-lite pilot, 2026-11-22). Applied alone; killed = a test FAILED.
Usage: <this> <worktree> <python>"""
import subprocess
import sys
from pathlib import Path

WT, PY = Path(sys.argv[1]), sys.argv[2]
RUN, JOB, DR = "codetask/run.py", "router/job.py", "codetask/drafter.py"
T = ["-q", "-x", "-p", "no:cacheprovider", "tests/test_report_conflict.py"]
M = [
    ("a draft file that is not red also stops", RUN, [('if f in draft_files and f in red_files]', 'if f in draft_files]')]),
    ("any red reported file stops, draft or not", RUN, [('if f in draft_files and f in red_files]', 'if f in red_files]')]),
    ("red files are taken from the wrong layer", RUN, [('for c in v["criteria"] if c["layer"] == "C"\n', 'for c in v["criteria"] if c["layer"] != "C"\n')]),
    ("every unconfirmed report stops", RUN, [('if conf and conf.get("state") == "unconfirmed" and conf.get("draft_tests"):', 'if conf and conf.get("state") == "unconfirmed":')]),
    ("the stop is a BLOCKED, not a failed acceptance", RUN, [('return move(state, st.FAILED_ACCEPTANCE, verdict=summary, failures=history, **new_conflict,\n                        reason=DRAFT_TEST_CONFLICT', 'return move(state, st.BLOCKED, verdict=summary, failures=history, **new_conflict,\n                        reason=DRAFT_TEST_CONFLICT')]),
    ("the legal move AGENT_FAILED to DRAFTING is gone", JOB, [("         (AGENT_FAILED, DRAFTING),", "         ")]),
    ("a redraft of any failed agent is allowed", JOB, [('if job.data["state"] == AGENT_FAILED and _draft_test_conflict_note(job) is None:', 'if False:')]),
    ("the note helper accepts any stop reason", JOB, [('if not str(r.get("stop_reason") or "").startswith(DRAFT_TEST_CONFLICT):\n            return None', 'if False:\n            return None')]),
    ("the facts are not cut to the room left", JOB, [("return out[:max(room, 0)]", "return out")]),
    ("a too long human note is not refused", JOB, [("if room < NOTE_FACTS_MIN:", "if False:")]),
    ("failing nodes of other files reach the note", JOB, [('if str(n).split("::", 1)[0] in files][:3]', '][:3]')]),
    ("failure lines of other files reach the note", JOB, [('if any(f in ln for f in files) or ln.strip().startswith(("AssertionError", "FAIL "))]', 'if True]')]),
    ("words of a human do not mark the job human-steered", JOB, [('job.data["human_steered"] = True         # and a human\'s own words', 'pass')]),
    ("the conflict redraft always marks the job human-steered", JOB, [('if "Reviewer (human): " in note:', 'if True:')]),
    ("approve numbers the agent stage a1 again", JOB, [('sid=f"a{int(last[1:]) + 1}" if last else "a1")', 'sid="a1")')]),
    ("the task name is always task", JOB, [('return TASK if n == 1 else f"{TASK}{n}"', 'return TASK')]),
    ("a task name taken by a repository only is reused", JOB, [('for p in (job.root / "fixtures" / "repos" / t,', 'for p in (job.root / "fixtures" / "repos" / "never",')]),
    ("protected_changed reads the first record again", JOB, [('task = (job.data.get("approval") or {}).get("task") or TASK', 'task = TASK')]),
    ("an already approved draft can be approved again", JOB, [('if (job.data.get("approval") or {}).get("draft_sha256") == seen:', 'if False:')]),
    ("status never offers the redraft", JOB, [('redraftable = d["state"] == AGENT_FAILED and _draft_test_conflict_note(job) is not None', 'redraftable = False')]),
    ("the drafter prompt ignores the conflict label", DR, [('{"reader": READER_NOTE_LABEL, "conflict": CONFLICT_NOTE_LABEL}', '{"reader": READER_NOTE_LABEL}')]),
    ("the review file title ignores the conflict", DR, [('"## Facts from the harness after the agent reported unpassable tests (not a human)"', '"## Note from the reviewer (human-steered)"')]),
]
killed = 0
for name, f, edits in M:
    p = WT / f
    orig = p.read_text()
    text = orig
    if any(text.count(a) != 1 for a, _ in edits):
        print("STALE  ", name, [text.count(a) for a, _ in edits], flush=True)
        continue
    for a, b in edits:
        text = text.replace(a, b, 1)
    p.write_text(text)
    try:
        r = subprocess.run([PY, "-m", "pytest", *T], cwd=WT, capture_output=True, text=True, timeout=900)
    finally:
        p.write_text(orig)
    k = r.returncode != 0
    killed += k
    print("KILLED " if k else "SURVIVED", name, flush=True)
print(f"RESULT: {killed}/{len(M)} killed")
