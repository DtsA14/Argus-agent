"""Mutants for SPEC_FOREMAN_TOPICS (F47 phase C1, rev 1). Applied alone; killed = a test FAILED. Run in a throwaway worktree.
Usage: <this> <worktree> <python> [name-part ...]"""
import os
import subprocess
import sys
from pathlib import Path

WT, PY = Path(sys.argv[1]), sys.argv[2]
ONLY = sys.argv[3:]
R, J, A, C, S = "router/manager_route.py", "router/manager_job.py", "router/chat_actions.py", "router/chat.py", "router/stage_data.py"
T = ["tests/test_foreman_topics.py", "tests/test_chat_topics.py", "tests/test_chat_manager.py", "tests/test_manager_job.py", "tests/test_foreman_memory.py", "tests/test_chat.py"]
M = [
    ("the title bound is off by one", R, [("    if len(t) > TITLE_MAX:", "    if len(t) >= TITLE_MAX:")]),
    ("a newline is allowed in a title", R, [('    if any(unicodedata.category(c)[0] == "C" or unicodedata.category(c) in ("Zl", "Zp") for c in t):', '    if any(unicodedata.category(c) in ("Zl", "Zp") for c in t):')]),
    ("a title and a continuation are both accepted", J, [("    if title is not None and continue_from is not None:", "    if False:")]),
    ("a session that can still take a turn is continued", J, [('        if verdict == "yes":\n            raise rj.Refused(f"session {continue_from} can still take a turn', '        if False:\n            raise rj.Refused(f"session {continue_from} can still take a turn')]),
    ("a session already continued is continued again", J, [('        if pin.get("continued_by"):', "        if False:")]),
    ("an unknown verdict is continuable", J, [('        if verdict == "unknown":\n            raise rj.Refused(f"session {continue_from}: its state or spend', '        if False:\n            raise rj.Refused(f"session {continue_from}: its state or spend')]),
    ("an unreadable spend is read as zero", J, [("        except (OSError, KeyError, TypeError, ValueError, rj.Refused):\n            spent = None", "        except (OSError, KeyError, TypeError, ValueError, rj.Refused):\n            spent = 0")]),
    ("the head carries the proposals", J, [('    lines = [_line(e) for e in conv[k:] if isinstance(e, dict) and e.get("from") in ("human", "manager")]\n    head = (prior', '    lines = [json.dumps(e, ensure_ascii=False) for e in conv[k:] if isinstance(e, dict) and e.get("from") in ("human", "manager")]\n    head = (prior')]),
    ("the head is not cut", J, [("        b = len(ln) + 1\n        if size + b > budget:\n            break\n        kept.append(ln)", "        b = len(ln) + 1\n        if size + b > budget:\n            pass\n        kept.append(ln)")]),
    ("the head is a human turn", J, [('head = {"from": "summary", "at": deps.clock(), "text": text,', 'head = {"from": "human", "at": deps.clock(), "text": text,')]),
    ("the carried head has the summary label", J, [('(mr.CARRIED_LABEL if summary.get("carried") else mr.SUMMARY_LABEL)', "mr.SUMMARY_LABEL")]),
    ("the checks run after the directory exists", J, [("    if not _ui_id_shape(continue_from):", "    (Path(jobs_dir) / job_id).mkdir(parents=True, exist_ok=True)\n    if not _ui_id_shape(continue_from):")]),
    ("can_take_turn ignores the budget", J, [('    if left < m["turn_cap_usd"] - 1e-12:\n        return "no"', '    if False:\n        return "no"')]),
    ("can_take_turn ignores the age", J, [('    if now_s - created > m["ttl_hours"] * 3600:\n        return "no"', '    if False:\n        return "no"')]),
    ("can_take_turn compares the age with >=", J, [('    if now_s - created > m["ttl_hours"] * 3600:', '    if now_s - created >= m["ttl_hours"] * 3600:')]),
    ("can_take_turn ignores the turn count", J, [('if isinstance(e, dict) and e.get("from") == "human") >= m["max_turns"]:\n        return "no"\n    if size', 'if isinstance(e, dict) and e.get("from") == "human") >= 10 ** 9:\n        return "no"\n    if size')]),
    ("can_take_turn ignores the file size", J, [("    if size is not None and size > FILE_MAX:\n        return \"no\"\n    return \"yes\"", "    return \"yes\"")]),
    ("can_take_turn reads an unknown spend as yes", J, [('    if spent_nano is None:\n        return "unknown"', '    if spent_nano is None:\n        return "yes"')]),
    ("a session without a topic has no id", J, [('return {"id": job_id, "title": derived_title(data), "legacy": True}', 'return {"id": "", "title": derived_title(data), "legacy": True}')]),
    ("the continued note is not a published kind", S, [(', "compaction_failed", "continued"}', ', "compaction_failed"}')]),
    ("a title is accepted on any action", A, [('        if {"title", "topic"} & set(params) and action != "manager_new":', "        if False:")]),
    ("a topic id is not checked", A, [('            if not isinstance(tid, str) or not UI_ID.fullmatch(tid):', "            if not isinstance(tid, str):")]),
    ("the card does not hold the resolved session", A, [('            card["continues"] = continues', "            pass")]),
    ("a link need not be reciprocal", A, [('            if pi is None or pi["continued_by"] != cur["id"]:', "            if pi is None:")]),
    ("the continuation reads a cached chain", A, [("        chain = self.topic_sessions(topic_id, fresh=True)\n        if not chain:\n            raise Refusal(409, \"topic\", \"no such topic\")", "        chain = self.topic_sessions(topic_id, fresh=False)\n        if not chain:\n            raise Refusal(409, \"topic\", \"no such topic\")")]),
    ("a busy session is continued", A, [('        if self.spawner.busy(newest):', "        if False:")]),
    ("an unknown verdict is continuable by the chat", A, [('        if verdict == "unknown":\n            raise Refusal(503, "topic"', '        if False:\n            raise Refusal(503, "topic"')]),
    ("the topics are not newest first", A, [("rows.sort(key=lambda r: (-r[0], r[1]), reverse=False)", "rows.sort(key=lambda r: (r[0], r[1]), reverse=False)")]),
    ("the topics are not capped", A, [("        for upd, root, chain in rows[:TOPICS_MAX]:", "        for upd, root, chain in rows:")]),
    ("a symlinked job directory is followed", A, [("                        jfd = sd._open_dir(n, sfd)\n                        try:\n                            fd = os.open(\"job.json\"", "                        jfd = os.open(os.path.join(self.jobs_dir, n), os.O_RDONLY | os.O_DIRECTORY)\n                        try:\n                            fd = os.open(\"job.json\"")]),
    ("the steps read only the latest session", A, [('        sessions = [x["id"] for x in self.topic_sessions(session)] or [session]', "        sessions = [session]")]),
    ("the topics cache is not dropped on a confirm", A, [("            self._chain_cache.clear()\n            self._topics_cache = None", "            self._chain_cache.clear()")]),
    ("the title goes by argv", A, [('                args += ["--title-file", str(tfile)]', "                args += [f\"--title={rp['title']}\"]")]),
    ("the title is written to the audit", C, [('        if card.get("continues"):                                         # SPEC_FOREMAN_TOPICS', '        if card.get("topic_title"):\n            rec["title"] = card["topic_title"]\n        if card.get("continues"):                                         # SPEC_FOREMAN_TOPICS')]),
]
killed = ran = 0
for name, f, edits in M:
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
        r = subprocess.run([PY, "-m", "pytest", "-x", "-q", "-p", "no:cacheprovider", "-n0", *T], cwd=WT, capture_output=True, text=True, timeout=400,
                           env={**os.environ, "PYTHONPATH": f"{WT}:{WT}/scripts:{WT}/tests"})
        dead = r.returncode != 0
    except subprocess.TimeoutExpired:
        dead = True
    finally:
        p.write_text(orig)
    killed += dead
    print("killed " if dead else "SURVIVED", name, flush=True)
print(f"{killed}/{ran} killed")
