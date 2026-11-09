"""Mutants for the issue writer PR 1 (docs/reviews/SPEC_ISSUE_WRITER.md 3-5, 8): each guarantee broken alone; killed =
a test failed. Usage: <this> <worktree> <python>"""
import subprocess
import sys
from pathlib import Path

WT, PY = Path(sys.argv[1]), sys.argv[2]
I, W, J = "router/issue.py", "codetask/issue_writer.py", "router/job.py"
T = ["tests/test_issue_writer.py"]
KIND = '        if job.data.get("kind") != "issue":\n            raise rj.Refused(f"job {job.id} is not an issue job; nothing was started")\n'
REPLY_GATE = '        if job.data["state"] not in REPLYABLE:'
START_GATE = '        if job.data["state"] != AWAITING_HUMAN:\n            raise rj.Refused(f"job {job.id} is {job.data[\'state\']}: an issue is started'
APPEND ='            job.data["conversation"].append({"from": "human", "at": deps.clock(), "text": message.strip()})\n'
M = [
    ("any repository", I, "    if not isinstance(name, str) or name not in repos:", "    if not isinstance(name, str):"),
    ("first message unchecked", I, "    why = message_problem(cfg, message, first=True)",
     "    why = None"),
    ("reply unchecked", I, "        why = message_problem(cfg, message, first=False)", "        why = None"),
    ("reply limit is the first limit", I, 'int(_settings(cfg)["message_max" if first else "reply_max"])',
     'int(_settings(cfg)["message_max"])'),
    ("reply in any state", I, '        if job.data["state"] not in REPLYABLE:', "        if False:"),
    ("reply to any kind", I, KIND + REPLY_GATE, "        if False:" + KIND[len('        if job.data.get("kind") != "issue":'):]
     + REPLY_GATE),
    ("start for any kind", I, KIND + START_GATE, "        if False:" + KIND[len('        if job.data.get("kind") != "issue":'):]
     + START_GATE),
    ("start any issue", I, "        if not isinstance(sha, str) or not rj.SHA_SEEN.fullmatch(sha) or not seen.startswith(sha):",
     "        if False:"),
    ("start a short sha", I, "        if not isinstance(sha, str) or not rj.SHA_SEEN.fullmatch(sha) or not seen.startswith(sha):",
     "        if not isinstance(sha, str) or not seen.startswith(sha):"),
    ("start a changed issue file", I, '        if text is None or seen != job.data.get("issue_sha256"):', "        if text is None:"),
    ("start in any state", I, START_GATE, START_GATE.replace("if job.data[\"state\"] != AWAITING_HUMAN:", "if False:")),
    ("any code cap", I, "        if not (0 < cap <= CODE_MAX_USD):", "        if False:"),
    ("start on HEAD", I, 'rj.start_code(repo=i["repo"], commit=i["commit"],', 'rj.start_code(repo=i["repo"], commit="HEAD",'),
    ("handoff recorded after the start", I, '        job.save()\n        i = job.data["inputs"]\n        try:',
     '        i = job.data["inputs"]\n        try:'),
    ("second code job after a crash", I, "        if handed is not None:                      # a start cut off",
     "        if False:                      # a start cut off"),
    ("an unstarted code job counts", I, '    if code.data.get("state") == rj.ABANDONED and not code.data.get("stages"):',
     "    if False:"),
    ("a made code job forgotten", I, '            if handed is None:\n                job.data.pop("handoff", None)',
     '            if True:\n                job.data.pop("handoff", None)'),
    ("handed off abandonable", I, "{(s, ABANDONED) for s in (NEW, WRITING, AWAITING_HUMAN, WRITE_FAILED, BLOCKED)}",
     "{(s, ABANDONED) for s in (NEW, WRITING, AWAITING_HUMAN, WRITE_FAILED, BLOCKED, HANDED_OFF)}"),
    ("turn cap above the job cap", I, "    if not (math.isfinite(cap) and cap + 1e-9 >= turn):", "    if False:"),
    ("unfunded reply taken", I, '        if left + 1e-12 < float(s["turn"]["cap_usd"]):        # before the limits',
     "        if False:  # before the limits"),
    ("unfunded turn run", I, "        if left + 1e-12 < cap:", "        if False:"),
    ("turn end saved early", I, '    st.update(ended_at=deps.clock(), status=r.get("status"), usd=r.get("usd_billed"))\n',
     '    st.update(ended_at=deps.clock(), status=r.get("status"), usd=r.get("usd_billed"))\n    job.save()\n'),
    ("copy refusal unhandled", I, "    except (intake.IntakeError, OSError) as e:", "    except ZeroDivisionError as e:"),
    ("message after the turn", I, APPEND + "            job.move(WRITING", "            job.move(WRITING"),
    ("live repository", I, '        source = _snapshot(job.runs / run_id, i["repo"], i["commit"])',
     '        source = _snapshot(job.runs / run_id, i["repo"], "HEAD")'),
    ("no previous issue", I, '"previous_issue": previous,', '"previous_issue": None,'),
    ("failed turn final", I, "(AWAITING_HUMAN, WRITING), (WRITE_FAILED, WRITING),", "(AWAITING_HUMAN, WRITING),"),
    ("unknown log entry", I, '        job.note(deps, "stage_started", stage=sid)', '        job.note(deps, "turn_started", stage=sid)'),
    ("not confirmed kept", I, '                job.move(ABANDONED, deps, reason="not started: not confirmed or no key")',
     "                pass"),
    ("control characters", W, '        if unicodedata.category(c)[0] == "C" or unicodedata.category(c) in ("Zl", "Zp"):',
     '        if unicodedata.category(c) == "Cc":'),
    ("newline anywhere", W, '        if c in "\\n\\t" and newlines:', '        if c in "\\n\\t":'),
    ("tabs refused", W, '        if c in "\\n\\t" and newlines:', '        if c == "\\n" and newlines:'),
    ("issue may exceed a code job", W, 'text_problem(issue.strip() if isinstance(issue, str) else issue, "issue", MAX_ISSUE - 1)',
     'text_problem(issue.strip() if isinstance(issue, str) else issue, "issue", MAX_ISSUE)'),
    ("no length limit", W, "    if len(text) > hi:", "    if False:"),
    ("no title rule", W, "        if not title or len(title) > TITLE_MAX:", "        if False:"),
    ("no Tests rule", W, "        if not any(TESTS.match(ln) for ln in lines[1:]):", "        if False:"),
    ("Tests prefix only", W, "        if not any(TESTS.match(ln) for ln in lines[1:]):",
     '        if not any(ln.startswith("Tests") for ln in lines[1:]):'),
    ("no Nothing-else rule", W, '        if not any(ln.startswith("Nothing else changes") for ln in lines[1:]):', "        if False:"),
    ("environment anywhere", W, '        if lines[-1].strip() != f"Environment: {environment}":',
     '        if f"Environment: {environment}" not in issue:'),
    ("clash outside", W, "        if target is None or root not in target.parents or not target.is_file():",
     "        if target is None or not target.is_file():"),
    ("clash not a file", W, "        if target is None or root not in target.parents or not target.is_file():",
     "        if target is None or root not in target.parents:"),
    ("bool line", W, "        if not isinstance(line, int) or isinstance(line, bool) or line < 0:",
     "        if not isinstance(line, int) or line < 0:"),
    ("too many clashes", W, "    if not isinstance(clashes, list) or len(clashes) > CLASHES_MAX:",
     "    if not isinstance(clashes, list):"),
    ("too many questions", W, "    if not isinstance(questions, list) or len(questions) > QUESTIONS_MAX:",
     "    if not isinstance(questions, list):"),
    ("multi-line question", W, '        w = text_problem(q, f"question {i}", WHY_MAX, newlines=False)',
     '        w = text_problem(q, f"question {i}", WHY_MAX)'),
    ("a writing tool", W, "tools=[ListFiles, SearchFiles, ReadFile, SubmitIssue]",
     'tools=[ListFiles, SearchFiles, ReadFile, SubmitIssue, __import__("codetask.tools", fromlist=["x"]).WriteFile]'),
    ("nothing to spend", W, '        if lim["attempt_usd"] <= 0:', "        if False:"),
    ("issue resume as code", J, '        if job.data.get("kind") == "issue":\n            from router import issue\n'
     "            return job, issue.resume(job, cfg, deps)\n", ""),
]
# Equivalent, not listed: refusing an issue job in `argus judge` by its kind. An issue job never reaches a judgeable
# state (router/issue.py LEGAL has none of them), so the state check refuses it either way (tested).

if __name__ == "__main__":
    killed = 0
    for name, f, old, new in M:
        p = WT / f
        orig = p.read_text()
        assert orig.count(old) == 1, (name, orig.count(old))
        p.write_text(orig.replace(old, new, 1))
        try:
            r = subprocess.run([PY, "-m", "pytest", "-x", "-q", "-p", "no:cacheprovider", *T], cwd=WT,
                               capture_output=True, text=True, timeout=600)
        finally:
            p.write_text(orig)
        last = (r.stdout.strip().splitlines() or [""])[-1]
        k = r.returncode == 1 and "failed" in last          # a test failed (not a collection or internal error)
        killed += k
        print(f"{'KILLED ' if k else 'SURVIVED'} {name}: {last}", flush=True)
    print(f"RESULT: {killed}/{len(M)} killed")
