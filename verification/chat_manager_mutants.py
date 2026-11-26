"""Mutants for CHAT-MANAGER P1 (SPEC_CHAT_MANAGER_P1 rev 1): the manager job, the turn route, the session card, the exposure. Applied alone; killed = a test FAILED.
Usage: <this> <worktree> <python>"""
import subprocess
import sys
from pathlib import Path

WT, PY = Path(sys.argv[1]), sys.argv[2]
J, A, C, R, S, D = "router/manager_job.py", "router/chat_actions.py", "router/chat.py", "router/manager_route.py", "scripts/argus.py", "router/job.py"
T = ["-rfEs", "tests/test_manager_job.py", "tests/test_chat_manager.py", "tests/test_manager_route.py"]
M = [
    ("a turn ignores the via check", J, [("        if not _created_via_ui(job):\n            raise", "        if False:\n            raise")]),
    ("a turn ignores the state", J, [('        if d["state"] != OPEN:\n            raise', '        if False:\n            raise')]),
    ("a turn ignores expiry", J, [('if age is None or age > m["ttl_hours"] * 3600:', 'if False:')]),
    ("an expired session is not blocked", J, [('            job.move(BLOCKED, deps, reason="expired")\n', '')]),
    ("the message check is dropped", J, [("        why = message_problem(m, message)\n        if why:\n            raise rj.Refused(f\"{why}; no turn was run\")", "        pass")]),
    ("line separators pass", J, [('any(unicodedata.category(c) in ("Zl", "Zp") for c in text)', 'False')]),
    ("the turn limit is ignored", J, [('>= m["max_turns"]:', '>= 10 ** 9:')]),
    ("the sheet pin is not checked", J, [("        if not mr.sheet_ok():\n            raise", "        if False:\n            raise")]),
    ("the budget check is dropped", J, [('        if not ok:\n            raise rj.Refused(f"the session budget cannot fund another turn', '        if False:\n            raise rj.Refused(f"the session budget cannot fund another turn')]),
    ("the turn cap is not part of the fit", J, [('return worst, worst <= m["turn_cap_usd"] + 1e-12 and worst <= left() + 1e-12', 'return worst, worst <= left() + 1e-12')]),
    ("the left budget is not part of the fit", J, [('return worst, worst <= m["turn_cap_usd"] + 1e-12 and worst <= left() + 1e-12', 'return worst, worst <= m["turn_cap_usd"] + 1e-12')]),
    ("the human message is recorded after the call", J, [('            d["conversation"].append({"from": "human", "at": deps.clock(), "text": message})      # recorded BEFORE the call\n', '')]),
    ("the key is taken after the message is recorded", J, [("        with rj.live(deps, scfg, [m[\"role\"]], text, job=job):", "        d[\"conversation\"].append({\"from\": \"human\", \"at\": deps.clock(), \"text\": message}); job.save()\n        with rj.live(deps, scfg, [m[\"role\"]], text, job=job):")]),
    ("the retry is unbounded", J, [("CALLS_PER_TURN = 2", "CALLS_PER_TURN = 5")]),
    ("no retry", J, [("CALLS_PER_TURN = 2", "CALLS_PER_TURN = 1")]),
    ("a second failure invents a proposal", J, [('entry["say"], entry["propose"] = FIXED_SAY, None', 'entry["say"], entry["propose"] = FIXED_SAY, {"route": "none", "repo": None, "text": "", "why": "x"}')]),
    ("a fenced reply is accepted", J, [('if not (raw.startswith("{") and raw.endswith("}")):', 'if False:')]),
    ("a truncated reply is accepted", J, [("                if is_truncated(reply):", "                if False:")]),
    ("an incomplete ledger does not stop the turn", J, [('if not reconcile_ledger(log.read())[1]["usd_complete"]:', 'if False:')]),
    ("the proposal is not validated", J, [("                    bad = mr.proposal_problems(got, repos)", "                    bad = []")]),
    ("readable_repos is ignored", J, [('    if m["readable_repos"] != []:', '    if False:')]),
    ("unknown config keys are accepted", J, [("    if extra:\n        raise", "    if False:\n        raise")]),
    ("the output limit may differ from the role", J, [('or r.get("max_output_tokens") != out["max_output_tokens"]:', ':')]),
    ("the context is not cut", J, [("        if size + b > limit:\n            break", "        if False:\n            break")]),
    ("a context label can be forged", J, [('json.dumps({who: str(e.get("say") if who == "foreman" else e.get("text"))[:mr.SAY_MAX]}, ensure_ascii=False)', 'f"{who}: " + str(e.get("say") if who == "foreman" else e.get("text"))[:mr.SAY_MAX]')]),
    ("the run directory is not made", J, [('        (job.runs / f"{job.id}-{SID}").mkdir(parents=True, exist_ok=True)', '        pass')]),
    ("a session can start from the terminal", J, [('    if via != "ui":\n        raise', '    if False:\n        raise')]),
    ("the ui id shape is not checked", J, [("    why = rr.ui_job_id_problem(job_id, deps.clock())\n    if why:", "    why = None\n    if why:")]),
    ("a frame tag is not neutralised", R, [('return FRAME_TAG.sub(lambda m: "&lt;" + m.group(0)[1:], str(text))', 'return str(text)')]),
    ("the closing tag only", R, [('FRAME_TAG = re.compile(r"<\\s*/?\\s*(', 'FRAME_TAG = re.compile(r"<\\s*/\\s*(')]),
    ("the CLI turn prints the model text", S, [('print(f"turn done: {entry[\'calls\']} call(s), ${entry[\'usd\']:.4f}"', 'print(f"turn done: {entry[\'say\']} {entry[\'calls\']} call(s), ${entry[\'usd\']:.4f}"')]),
    ("the CLI new takes no yes", S, [('mn.add_argument("--yes", action="store_true", required=True,', 'mn.add_argument("--yes", action="store_true",')]),
    ("the route accepts extra fields", C, [('if set(body) != {"session", "message"} or', 'if not {"session", "message"} <= set(body) or')]),
    ("the audit line comes after the run starts", C, [('        if not self._audit(a, **rec, attempt="manager_turn"):\n            raise Refusal(503, "audit", "the audit could not be written: nothing was run")\n        out = a.manager_turn_start(body["session"], body["message"])', '        out = a.manager_turn_start(body["session"], body["message"])\n        if not self._audit(a, **rec, attempt="manager_turn"):\n            raise Refusal(503, "audit", "the audit could not be written: nothing was run")')]),
    ("the turn route is not in POST_ROUTES", C, [(', "/api/manager/turn": "manager_turn"}', '}')]),
    ("the turn is not checked by the route", C, [('        a.manager_turn_check(body["session"], body["message"])\n', '')]),
    ("the route ignores a busy session", A, [('        if self.spawner.busy(job_id):\n            raise Refusal(409, "busy", "the foreman', '        if False:\n            raise Refusal(409, "busy", "the foreman')]),
    ("the route ignores expiry", A, [('        if age > m["ttl_hours"] * 3600:', '        if False:')]),
    ("the route ignores the via", A, [('        if not any(isinstance(e, dict) and e.get("what") == "created" and e.get("via") == "ui" for e in d.get("log") or []):\n            raise Refusal(409, "job", "this session was not started from the chat")', "        pass")]),
    ("the route ignores the remaining budget", A, [('        if max_usd - spent + 1e-12 < m["turn_cap_usd"]:', '        if False:')]),
    ("the message is put in argv", A, [('"--message-file", str(path), key_file=key))', '"--message-file", str(path), "--message", message, key_file=key))')]),
    ("the manager key slot is ignored", A, [("            return self.environ.get(MANAGER_KEY_ENV) or self.environ.get(WRITER_KEY_ENV) or self.environ.get(KEY_ENV) or None", "            return self.environ.get(WRITER_KEY_ENV) or self.environ.get(KEY_ENV) or None")]),
    ("manager_new is not in ACTIONS", A, [('"research_new", "prd_new", "manager_new", "prd_approve",', '"research_new", "prd_new", "prd_approve",')]),
    ("exposure ignores a session", A, [('            if data.get("kind") == "manager":                 # SPEC_CHAT_MANAGER_P1 10.6', '            if False:                 # SPEC_CHAT_MANAGER_P1 10.6')]),
    ("exposure counts a session past 24 hours", A, [('                            total += max(finite_usd(data["max_usd"]), mcap)', '                            total += max(finite_usd(data["max_usd"]), mcap)\n                    if True:\n                        total += 0.0 if False else mcap')]),
    ("the audit net misses manager_new", A, [('("prd_new", pcap), ("manager_new", mcap)):', '("prd_new", pcap)):')]),
    ("exposure_of ignores manager_new", A, [('"research_new", "prd_new", "manager_new"):\n            return float(card["job_cap_usd"])', '"research_new", "prd_new"):\n            return float(card["job_cap_usd"])')]),
    ("a confirmed session adds no pending money", A, [('            self.spawner.spawn(new_id, argv, None, action="manager")\n            self.pending.append((self.clock(), ("new", new_id), self.exposure_of(card)))', '            self.spawner.spawn(new_id, argv, None, action="manager")')]),
    ("the session card takes fields", A, [('        if params:\n            raise Refusal(400, "form", "a foreman session takes no fields")', "")]),
    ("the session card needs no key", A, [("        self._need_key(False, manager=True)\n        card = {\"action\": \"manager_new\"", "        card = {\"action\": \"manager_new\"")]),
    ("the decision offers a session", A, [('if got[0].get("kind") in ("issue", "prd", "manager"):', 'if got[0].get("kind") in ("issue", "prd"):')]),
    ("a session is resumable", D, [('        if job.data.get("kind") == "manager":\n            raise Refused(f"job {job.id}: a manager session is not resumed', '        if False:\n            raise Refused(f"job {job.id}: a manager session is not resumed')]),
    ("the log kinds are not published", "router/stage_data.py", [(', "turn_started", "turn_done"}', '}')]),
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
