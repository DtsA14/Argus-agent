"""Mutants for CHAT-MANAGER P4 (SPEC_CHAT_MANAGER_P4 section 6): the next steps of a session. Applied alone; killed = a test FAILED.
The pins are not in the test list. Not mutated (equivalent by design, two layers): the audit job id check (`_read_data` checks the shape too) and a NaN cost (`usd >= 0` is false for it). Usage: <this> <worktree> <python>"""
import subprocess
import sys
from pathlib import Path

WT, PY = Path(sys.argv[1]), sys.argv[2]
J, A = "router/chat_static/app.js", "router/chat_actions.py"
T = ["-rfEs", "tests/test_chat_manager_next.py", "tests/test_chat_manager_ui.py", "tests/test_chat_manager.py"]
COND = 'if not (r.get("ok") == "confirm" and r.get("source_job") == session and r.get("action") in ROUTE_ACTION.values()):'
M = [
    ("any ok counts (a prepare line)", A, [(COND, 'if not (r.get("source_job") == session and r.get("action") in ROUTE_ACTION.values()):')]),
    ("another session's job counts", A, [('r.get("source_job") == session and r.get("action") in ROUTE_ACTION.values()):', 'r.get("source_job") and r.get("action") in ROUTE_ACTION.values()):')]),
    ("a typed form counts", A, [('r.get("ok") == "confirm" and r.get("source_job") == session and r.get("action")', 'r.get("ok") == "confirm" and r.get("action")')]),
    ("an action other than research/prd counts", A, [('and r.get("action") in ROUTE_ACTION.values()):', "):")]),
    ("a job of another kind counts", A, [('got[0].get("kind") not in ("research", "prd")', "False")]),
    ("no limit of ten", A, [("                if len(out) >= NEXT_MAX:\n                    break\n", "")]),
    ("a job is listed twice", A, [("                if not isinstance(job, str) or not UI_ID.fullmatch(job) or job in seen:", "                if not isinstance(job, str) or not UI_ID.fullmatch(job):")]),
    ("oldest first", A, [('for line in reversed(raw.decode("utf-8", "replace").splitlines()):\n            try:\n                if session', 'for line in raw.decode("utf-8", "replace").splitlines():\n            try:\n                if session')]),
    ("the state is not checked against the shape", A, [('state = state if isinstance(state, str) and STATE_SHAPE.fullmatch(state) else "UNKNOWN"', 'state = str(state)')]),
    ("REPORT_READY maps to wait", A, [('if kind == "research" and state == "REPORT_READY":', 'if False:')]),
    ("AWAITING_HUMAN maps to wait", A, [('elif kind == "prd" and state == "AWAITING_HUMAN":', 'elif False:')]),
    ("an ended state maps to wait", A, [("                elif ENDED_STATE.search(state):", "                elif False:")]),
    ("the ended pattern is a full match", A, [("                elif ENDED_STATE.search(state):", "                elif ENDED_STATE.fullmatch(state):")]),
    ("a model's text in the item", A, [('"hint": hint, "text": text})', '"hint": hint, "text": text, "title": d.get("title")})')]),
    ("a bad audit line raises", A, [("            except (ValueError, KeyError, TypeError, AttributeError, ArithmeticError):      # one hostile", "            except (KeyError, TypeError, AttributeError, ArithmeticError):      # one hostile")]),
    ("a huge number takes the view down", A, [("TypeError, AttributeError, ArithmeticError):      # one hostile", "TypeError, AttributeError):      # one hostile")]),
    ("an infinite cost is shown", A, [(" and math.isfinite(usd) and usd >= 0 else None", " and usd >= 0 else None")]),
    ("a negative cost is shown", A, [(" and math.isfinite(usd) and usd >= 0 else None", " and math.isfinite(usd) else None")]),
    ("next_steps is missing from the read route", A, [(' "next_steps": self.next_steps(job_id),', "")]),
    ("the box shows with no items", J, [("if (Array.isArray(d.next_steps) && d.next_steps.length) {", "if (true) {")]),
    ("the box takes a non-array", J, [("if (Array.isArray(d.next_steps) && d.next_steps.length) {", "if (d.next_steps && d.next_steps.length) {")]),
    ("the box prepares", J, [('r.addEventListener("click", function () { setMode("research"); showResearch(n.job); });', 'r.addEventListener("click", function () { prepare({ action: "research_new", message: n.text }); });')]),
    ("the report button does not move", J, [('setMode("research"); showResearch(n.job);', "showResearch(n.job);")]),
    ("the queue button does not move", J, [('q.addEventListener("click", function () { setMode("cards"); });', 'q.addEventListener("click", function () { });')]),
    ("the report is opened before the mode changes", J, [('setMode("research"); showResearch(n.job);', 'showResearch(n.job); setMode("research");')]),
    ("the sentence goes in as markup", J, [('p.appendChild(document.createTextNode(String(n.text)));', 'p.innerHTML = String(n.text);')]),
    ("the money line has no figure", J, [('(typeof n.usd === "number" ? " · " + usd(n.usd) : "")', '""')]),
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
