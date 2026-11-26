"""Mutants for CHAT-MANAGER P4b (SPEC_CHAT_MANAGER_P4B section 6): the foreman is told which jobs its session started. Applied alone; killed = a test FAILED.
Not mutated (equivalent in behaviour): reading the jobs file without a byte limit (the size check refuses the same file; the limit only bounds memory).
Usage: <this> <worktree> <python>"""
import subprocess
import sys
from pathlib import Path

WT, PY = Path(sys.argv[1]), sys.argv[2]
R, J, A, S, C = "router/manager_route.py", "router/manager_job.py", "router/chat_actions.py", "scripts/argus.py", "router/control_issues.py"
T = ["-rfEs", "tests/test_manager_steps.py", "tests/test_chat_manager.py", "tests/test_chat_manager_next.py", "tests/test_manager_job.py", "tests/test_manager_route.py"]
M = [
    ("the jobs file is not passed to the CLI", A, [('extra = ["--jobs-file", str(jobs)]', "extra = []")]),
    ("a jobs file is written when there are none", A, [("            if steps:                                       # P4b", "            if True:                                       # P4b")]),
    ("--jobs-file is placed after --yes", A, [('manager_cli(self.jobs_dir, "turn", job_id, "--message-file", str(path), *extra, key_file=key)', 'manager_cli(self.jobs_dir, "turn", job_id, "--message-file", str(path), key_file=key) + extra')]),
    ("the message and the jobs share one file", A, [("jobs = self.spawner.message_file(json.dumps(steps))", "jobs = path")]),
    ("only one file is removed by the spawner", C, [('            for f in (run["message"] if isinstance(run["message"], (list, tuple)) else [run["message"]]):', '            for f in ([run["message"][0]] if isinstance(run["message"], (list, tuple)) else [run["message"]]):')]),
    ("the files are left when the spawn fails", A, [("            for f in files:\n                Path(f).unlink(missing_ok=True)          # no run owns", "            for f in []:\n                Path(f).unlink(missing_ok=True)          # no run owns")]),
    ("the CLI ignores the file", S, [("steps, problem = mr_parse_steps(raw.decode(\"utf-8\"))", "steps, problem = None, None")]),
    ("the size limit is dropped", R, [('    if len(text.encode("utf-8")) > STEPS_FILE_MAX:\n        return None, "the jobs file is too large"\n', "")]),
    ("a duplicate key is accepted", R, [("        items = json.loads(text, object_pairs_hook=_no_dupes)", "        items = json.loads(text)")]),
    ("an extra key is accepted", R, [("if not isinstance(it, dict) or set(it) != STEP_KEYS:", "if not isinstance(it, dict) or not STEP_KEYS <= set(it):")]),
    ("a missing key is accepted", R, [("if not isinstance(it, dict) or set(it) != STEP_KEYS:", "if not isinstance(it, dict) or not set(it) <= STEP_KEYS:")]),
    ("the job id is not a full match", R, [("JOB_ID.fullmatch(it[\"job\"])", "JOB_ID.match(it[\"job\"])")]),
    ("the kind is not checked", R, [('it["kind"] in STEP_KINDS and ', "")]),
    ("the state shape is not checked", R, [(' and isinstance(it["state"], str) and STATE_SHAPE.fullmatch(it["state"])', "")]),
    ("a negative cost is accepted", R, [(" and math.isfinite(usd) and usd >= 0)))", " and math.isfinite(usd))))")]),
    ("a bool cost is accepted", R, [(" and not isinstance(usd, bool) and math.isfinite(usd)", " and math.isfinite(usd)")]),
    ("an overflow crashes", R, [("        except (OverflowError, TypeError):", "        except TypeError:")]),
    ("more than ten jobs are accepted", R, [("if not isinstance(items, list) or len(items) > STEPS_MAX:", "if not isinstance(items, list):")]),
    ("a bad file does not stop the turn", S, [('                if problem:\n                    raise rj.Refused(f"{problem}; no turn was run")', "                if False:\n                    pass")]),
    ("the sentences come from the file", R, [('"note": step_hint(it["kind"], it["state"])[1]}', '"note": it.get("note", "")}')]),
    ("a changed ended sentence", R, [('f"This {kind} job ended: {state}."', 'f"{kind} ended {state}"')]),
    ("a changed still-going sentence", R, [('f"This {kind} job is still going: {state}."', 'f"{kind} going {state}"')]),
    ("the block is placed after the user message", J, [('        user = mr.user_prompt(message, context)\n', '        user = mr.user_prompt(message, None) + "\\n" + str(context)\n')]),
    ("the block is stored in the job", J, [('"\\nEarlier turns:\\n" + context if context else "")\n', '"\\nEarlier turns:\\n" + context if context else "")\n            d["steps_seen"] = steps\n')]),
    ("the earlier-turns label is written without a conversation", J, [('("\\nEarlier turns:\\n" + context if context else "")', '("\\nEarlier turns:\\n" + (context or ""))')]),
    ("the steps are not in the context at all", J, [("        if steps:\n            context = ", "        if False:\n            context = ")]),
    ("the instruction sentence is dropped", R, [('"The context may list jobs this conversation started,', '"The context may say things,')]),
    ("the state pattern is case-insensitive", R, [('STATE_SHAPE = re.compile(r"[A-Z][A-Z_]{0,39}")', 'STATE_SHAPE = re.compile(r"[A-Z][A-Z_]{0,39}", re.I)')]),
    ("the job id takes any digit", R, [('JOB_ID = re.compile(r"j[0-9]{8}_[0-9]{6}_[0-9a-f]{4}")', 'JOB_ID = re.compile(r"j\\d{8}_\\d{6}_[0-9a-f]{4}")')]),
    ("the jobs reach the turn with the wrong order", A, [("steps = [{k: n[k] for k in sorted(mr.STEP_KEYS)} for n in self.next_steps(job_id)]", "steps = [{k: n[k] for k in sorted(mr.STEP_KEYS)} for n in reversed(self.next_steps(job_id))]")]),
    ("the page's sentences are its own copy", A, [("                hint, text = mr.step_hint(kind, state)\n", '                hint, text = mr.step_hint(kind, state)\n                text = text.replace("done", "finished")\n')]),
]
killed = 0
for name, f, edits in M:
    p = WT / f
    orig = p.read_text()
    text = orig
    if any(text.count(a) != 1 for a, _ in edits):
        print("STALE  ", name, flush=True)
        continue
    for a, b in edits:
        text = text.replace(a, b, 1)
    p.write_text(text)
    try:
        r = subprocess.run([PY, "-m", "pytest", "-x", "-q", "-p", "no:cacheprovider", *T], cwd=WT, capture_output=True, text=True, timeout=900,
                           env={**__import__("os").environ, "PYTHONPATH": f"{WT}:{WT}/scripts"})
    finally:
        p.write_text(orig)
    last = (r.stdout.strip().splitlines() or [""])[-1]
    k = "FAILED tests/" in r.stdout or "FAILED" in last or "error" in last.lower()
    killed += k
    print("KILLED " if k else "SURVIVED", name, flush=True)
print(f"RESULT: {killed}/{len(M)} killed")
