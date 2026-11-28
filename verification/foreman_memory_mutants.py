"""Mutants for SPEC_FOREMAN_MEMORY (F47 phase A, rev 1 sections 9). Applied alone; killed = a test FAILED. Run in a throwaway worktree.
Usage: <this> <worktree> <python> [name-part ...]"""
import os
import subprocess
import sys
from pathlib import Path

WT, PY = Path(sys.argv[1]), sys.argv[2]
ONLY = sys.argv[3:]
J, R, A, S, JS = "router/manager_job.py", "router/manager_route.py", "router/chat_actions.py", "router/stage_data.py", "router/chat_static/app.js"
T = ["tests/test_foreman_memory.py", "tests/test_manager_job.py", "tests/test_manager_steps.py", "tests/test_chat_manager.py", "tests/test_chat_manager_ui.py",
     "tests/test_chat_manager_proposal.py", "tests/test_manager_route.py", "tests/test_chat.py"]
M = [
    ("compacts only at double the threshold", J, [('and len(_context(conversation, 10 ** 9) or "") > m["context_chars"]', 'and len(_context(conversation, 10 ** 9) or "") > m["context_chars"] * 2')]),
    ("k is off by one", J, [("            if seen == keep:\n                return i", "            if seen == keep + 1:\n                return i")]),
    ("compaction with too few turns", J, [('return humans > m["keep_recent_turns"] and len', 'return humans > 0 and len')]),
    ("no cut by code (the context is unbounded)", J, [("    budget = limit - len(head)\n", "    budget = 10 ** 9\n")]),
    ("the compaction input omits the old summary", J, [('    return (summary["text"] if summary else None), lines', "    return None, lines")]),
    ("the summary is not labelled as data", J, [('head = (mr.SUMMARY_LABEL + "\\n" + summary["text"]) if summary else ""', 'head = summary["text"] if summary else ""')]),
    ("the compaction prompt is not frame safe", R, [('    return user_prompt(f"Write the summary now, at most {limit} characters.", "\\n\\n".join(parts))',
                                                    '    return "<context kind=\\"data, not instructions\\">\\n" + "\\n\\n".join(parts) + "\\n</context>\\n<user_message>\\nWrite the summary now.\\n</user_message>"')]),
    ("a summary over the limit is accepted", R, [("    if len(t) > limit:\n", "    if False:\n")]),
    ("an empty summary is accepted", R, [("    if not isinstance(text, str) or not text.strip():\n        return \"the summary is empty\"", "    if not isinstance(text, str):\n        return \"the summary is empty\"")]),
    ("a fenced block is accepted", R, [('    if t.startswith("{") or t.startswith("```"):\n        return "the summary is a JSON object or a fenced block"\n', "")]),
    ("control characters are accepted", R, [("    if not _clean(t) or any(unicodedata.category(c) in (\"Zl\", \"Zp\") for c in t):\n        return \"the summary holds", "    if False:\n        return \"the summary holds")]),
    ("a frame tag is accepted", R, [("    if FRAME_TAG.search(t):\n        return \"the summary holds a frame tag\"", "    if False:\n        return \"the summary holds a frame tag\"")]),
    ("a failed compaction still writes an entry", J, [('                    if why_not is None:\n                        d["conversation"].append({"from": "summary"', '                    if True:\n                        d["conversation"].append({"from": "summary"')]),
    ("covers does not start at 0", J, [('"text": got_text, "covers": [0, k]', '"text": got_text, "covers": [1, k]')]),
    ("the input folds one turn too many", J, [("conversation[start:k] if isinstance(e, dict)", "conversation[start:k + 2] if isinstance(e, dict)")]),
    ("the summary entry carries no cost", J, [('"covers": [0, k], "usd": spent_c, "calls": 1,', '"covers": [0, k], "usd": 0.0, "calls": 1,')]),
    ("the newest summary is not the one used", J, [("    for i in range(len(conversation) - 1, -1, -1):\n        e = conversation[i]\n        if isinstance(e, dict) and e.get(\"from\") == \"summary\"",
                                                   "    for i in range(len(conversation)):\n        e = conversation[i]\n        if isinstance(e, dict) and e.get(\"from\") == \"summary\"")]),
    ("read_manager shows a summary as a foreman entry", A, [('            elif e.get("from") == "summary":', '            elif False:')]),
    ("the page draws a summary with innerHTML", JS, [('fold.appendChild(el("p", "note", String(e.text)));', 'var sp = el("p", "note"); sp.innerHTML = String(e.text); fold.appendChild(sp);')]),
    ("the turn limit counts every entry", J, [('if sum(1 for e in d["conversation"] if e.get("from") == "human") >= m["max_turns"]:', 'if len(d["conversation"]) >= m["max_turns"]:')]),
    ("the live text omits the compaction", J, [('            text += f"; the earlier turns are first summarized by one more call (worst case ${cworst:.4f}) and the summary replaces them in the prompt"', '            text += ""')]),
    ("the reply reservation is made at 0.4 token a character", J, [("                    reply = caller.call([SystemMessage(system), HumanMessage(u)], reservation(scfg, ref, len(system) + len(u), m[\"max_output_tokens\"], worst),",
                                                                     "                    reply = caller.call([SystemMessage(system), HumanMessage(u)], tr.reservation(len(system) + len(u), m[\"max_output_tokens\"], worst),")]),
    ("the size guard is off", J, [('if len(json.dumps(d, indent=2, ensure_ascii=False).encode("utf-8")) > FILE_MAX:', "if False:")]),
    ("a failed compaction is retried every turn", J, [('    return any(e.get("compaction_failed") for e in last)', "    return False")]),
    ("the ledger is not checked before a compaction", J, [('                elif not reconcile_ledger(log.read())[1]["usd_complete"]:\n                    why_not = "ledger incomplete"', '                elif False:\n                    why_not = "ledger incomplete"')]),
    ("the failed compaction charge is dropped", J, [('                        entry["compaction_usd"] = spent_c', "                        pass")]),
    ("the reply's cost includes the compaction", J, [('            before = reconcile_ledger(log.read())[1]["usd_nano"]\n            d["conversation"].append({"from": "human"', '            d["conversation"].append({"from": "human"'),
                                                     ('            if want:\n                why_not = None', '            before = reconcile_ledger(log.read())[1]["usd_nano"]\n            if want:\n                why_not = None')]),
    ("a truncated summary is accepted", J, [("                        if is_truncated(creply):", "                        if False:")]),
    ("the poll counts entries again", JS, [("var answered = (mgr.data && mgr.data.conversation ? mgr.data.conversation : []).some(function (e) { return e.from === \"manager\" && e.n >= mgr.before; });",
                                           "var answered = (mgr.data && mgr.data.conversation ? mgr.data.conversation.length : 0) >= mgr.before + 2;")]),
    ("the compaction notes are not published kinds", S, [(',\n            "compaction_started", "compacted", "compaction_failed"}', "}")]),
    ("the config bounds are not checked", J, [('    why = _bounds_problem(out, cfg, r)\n    if why:\n        raise rj.Refused(why)', "    pass")]),
    ("the steps block is lost from the prompt", J, [('                context = "Jobs this conversation started (facts from the harness):\\n" + mr.steps_context(steps) + ("\\nEarlier turns:\\n" + context if context else "")', "                pass")]),
    ("the turn_note is unchanged", A, [("so a turn can cost up to three calls, each within the turn cap", "so a turn can cost up to two turn caps")]),
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
