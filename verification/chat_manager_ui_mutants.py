"""Mutants for CHAT-MANAGER P3 (SPEC_CHAT_MANAGER_P3 section 5): the foreman on the page. Applied alone; killed = a test FAILED.
The pins are not in the test list (a changed file would fail them for the wrong reason). Usage: <this> <worktree> <python>"""
import subprocess
import sys
from pathlib import Path

WT, PY = Path(sys.argv[1]), sys.argv[2]
J, A, H = "router/chat_static/app.js", "router/chat_actions.py", "router/chat_static/index.html"
T = ["-rfEs", "tests/test_chat_manager_ui.py", "tests/test_chat_ui.py", "tests/test_chat_manager.py"]
M = [
    ("the turn body gets an extra key", J, [("{ session: job, message: text }", "{ session: job, message: text, action: 1 }")]),
    ("a turn is sent into a non-open session", J, [('mgr.data.state !== "OPEN") { showNote', 'false) { showNote')]),
    ("a turn is sent into a busy session", J, [("if (mgr.data.busy || mgr.timer || mgr.sending)", "if (false)")]),
    ("an empty message is sent", J, [("    if (!text.trim()) { return; }\n    var job = mgr.job", "    var job = mgr.job")]),
    ("a refused turn clears the box", J, [("      if (e.answered) { mgr.stuck = true; renderManager(); }", '      message.value = "";\n      if (e.answered) { mgr.stuck = true; renderManager(); }')]),
    ("a proposal button posts to confirm", J, [("      prepare(body);\n    });\n    var edit", '      post("/api/confirm", { token: "x" });\n    });\n    var edit')]),
    ("source_turn is not a string", J, [("body.source_turn = String(e.n);", "body.source_turn = e.n;")]),
    ("the source is never sent from a proposal button", J, [("      body.source_job = mgr.job;\n", "")]),
    ("the source is added to every action", J, [('if (fromProposal && (body.action === "research_new" || body.action === "prd_new") && body.source_job === undefined)', "if (fromProposal && body.source_job === undefined)")]),
    ("setMode does not clear the source", J, [("    cardSeq++;\n    fromProposal = null;\n    mgrStop();", "    cardSeq++;\n    mgrStop();")]),
    ("the reason is dropped from the box", J, [('    say(b, "model", "reason (written by the model)", p.why, "say");\n', "")]),
    ("the model label is dropped", J, [('"foreman (a model, not Argus)"', '"foreman"')]),
    ("a PRD Prepare is on without a repo", J, [('var ready = p.route === "research" || !!p.repo;', "var ready = true;")]),
    ("Edit first does not remember the source", J, [("      fromProposal = { job: job, turn: e.n };\n", "")]),
    ("the foreman mode is missing from setChrome", J, [('var inChat = mode === "status" || mode === "issue" || mode === "prd" || mode === "research" || mode === "manager";', 'var inChat = mode === "status" || mode === "issue" || mode === "prd" || mode === "research";')]),
    ("maxLength stays 6000", J, [("message.maxLength = f ? 2000 : 6000;", "message.maxLength = 6000;")]),
    ("the poll never stops", J, [("if (mgr.left <= 0 || (mgr.data && !mgr.data.busy && n >= mgr.before + 2)) { mgr.timer = null; return; }", "if (false) { mgr.timer = null; return; }")]),
    ("the poll stops one answer early", J, [("n >= mgr.before + 2", "n >= mgr.before + 1")]),
    ("ask and none get a Prepare button", J, [('if (p.route === "ask") { b.appendChild(el("p", "note", "The foreman is waiting for your answer.")); return b; }', "")]),
    ("an unknown route gets a button", J, [('if (p.route !== "research" && p.route !== "prd") {', 'if (p.route === "none") {')]),
    ("the budget shows the maximum only", J, [('usd(Math.max(0, d.max_usd - d.spent_usd)) + " of " + usd(d.max_usd)', 'usd(d.max_usd) + " of " + usd(d.max_usd)')]),
    ("the Started-from fact is dropped", J, [('    if (card.source) { fact(c, "Started from"', '    if (false) { fact(c, "Started from"')]),
    ("the session search is unbounded", J, [("if (mgr.expect > 0) { mgr.expect--;", "if (mgr.expect > 0) {")]),
    ("the source stays after a confirm", J, [("        fromProposal = null;                            // the source belongs", "        // the source belongs")]),
    ("no new-session offer for an expired session", J, [("d.expires_in_s === 0 || ", "")]),
    ("no new-session offer for a used-up budget", J, [("d.max_usd - d.spent_usd < d.turn_cap_usd", "false")]),
    ("no new-session offer after a refusal", J, [("mgr.stuck || ", "")]),
    ("a turn answered after leaving still clears the box", J, [("      if (mode !== \"manager\" || epoch !== mgr.epoch) { return; }        // the person moved on", "      if (false) { return; }        // the person moved on")]),
    ("no in-flight guard", J, [("    mgr.sending = true;\n", "")]),
    ("no session search after Confirm", J, [('if (body.action === "manager_new") { mgr.expect = 12; loadManager(); }', 'if (body.action === "manager_new") { loadManager(); }')]),
    ("loadManager has no seq check", J, [('      if (mode !== "manager" || my !== mgr.seq) { return; }\n      var open', '      if (mode !== "manager") { return; }\n      var open')]),
    ("the Started note says issue list", J, [('card.action === "manager_new" ? "The session is being made;', 'card.action === "x" ? "The session is being made;')]),
    ("the plus menu lacks the foreman", H, [('        <button type="button" role="menuitem" data-mode="manager">Foreman</button>\n', "")]),
    ("the read route gives no turn cap", A, [('"turn_cap_usd": turn_cap, "max_turns": max_turns,', "")]),
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
