"""Mutants for SPEC_CHAT_APPLY_REPLY PR3 (the reply box, the two install buttons, the "started, never recorded" mark). Applied alone; killed = a test FAILED.
Run in a throwaway worktree, never in the live checkout. The page's pinned hashes are not repinned: the mutants are judged by the node smoke and the text tests,
which do not start the server.
Usage: <this> <worktree> <python> [name-part ...]"""
import os
import subprocess
import sys
from pathlib import Path

WT, PY = Path(sys.argv[1]), sys.argv[2]
ONLY = sys.argv[3:]
J, S = "router/chat_static/app.js", "router/chat_apply.py"
T_JS = ["tests/test_chat_ui_node.py", "tests/test_chat_apply_reply.py", "-k", "reply_box or the_page or install_button_stays or remembers or t4b_page"]
T_PY = ["tests/test_chat_apply_reply.py", "-k", "started or button_to_offer or button_state"]
RDY = 'var ready = function () { p.disabled = !shown || !tick.checked || (why !== null && why.value.trim().length < 10); };'
M = [
    ("reply: the button starts open", J, [('    b.disabled = true;\n    ta.addEventListener("input"', '    b.disabled = false;\n    ta.addEventListener("input"')], T_JS),
    ("reply: an empty text opens the button", J, [('b.disabled = ta.value.trim().length === 0;', 'b.disabled = false;')], T_JS),
    ("reply: the box shows for any state", J, [('    if (d.state !== "AWAITING_HUMAN" && d.state !== "WRITE_FAILED") { return box; }\n', '')], T_JS),
    ("reply: the message is not what was typed", J, [('message: ta.value })', 'message: d.summary })')], T_JS),
    ("reply: a field is filled from the card", J, [('    ta.rows = 3;', '    ta.rows = 3;\n    ta.value = d.summary || "";')], T_JS),
    ("reader: the button sends a cap", J, [('prepare({ action: "patch_read_run", job: id })', 'prepare({ action: "patch_read_run", job: id, cap: 1 })')], T_JS),
    ("install: opens before the patch is shown", J, [(RDY, RDY.replace("!shown || ", ""))], T_JS),
    ("install: opens without the tick", J, [(RDY, RDY.replace("!tick.checked || ", ""))], T_JS),
    ("install: a reason of any length opens it", J, [(RDY, RDY.replace("< 10", "< 0"))], T_JS),
    ("install: the shown patch need not be the card's", J, [('x.sha12 === d.patch_sha12', 'true')], T_JS),
    ("install: a patch that is not text is drawn anyway", J, [('typeof x.text === "string" &&', '')], T_JS),
    ("install: the tick opens before the patch is shown", J, [('      tick.disabled = true;\n', '      tick.disabled = false;\n')], T_JS),
    ("install: sends no sha", J, [('job: id, sha: d.patch_sha12 };', 'job: id, sha: "" };')], T_JS),
    ("install: the reason is not sent", J, [('        if (why) { body.reason = why.value.trim(); }\n        prepare(body);\n      });\n      box.appendChild(p);\n      box.appendChild(el("p", "small", "One commit', '        prepare(body);\n      });\n      box.appendChild(p);\n      box.appendChild(el("p", "small", "One commit')], T_JS),
    ("install: the reason field is filled", J, [('        why.maxLength = 500;\n        why.autocomplete = "off";\n        why.placeholder = "A reader', '        why.maxLength = 500;\n        why.value = d.purpose;\n        why.autocomplete = "off";\n        why.placeholder = "A reader')], T_JS),
    ("install: no warning for a started apply", J, [('    if (a.started) {', '    if (false) {')], T_JS),
    ("install: the card does not remember it is open", J, [('    openCard = id;\n    openKind = "install";\n', '    openCard = id;\n')], T_JS),
    ("reply: the box is filled through the text argument", J, [('var ta = el("textarea", "reply");', 'var ta = el("textarea", "reply", d.summary);')], T_JS),
    ("reply: the box is not drawn", J, [('      stream.appendChild(replyBox(id, d));\n', '')], T_JS),
    ("install: the buttons are not drawn", J, [('      stream.appendChild(installActions(id, d, seq));\n', '')], T_JS),
    ("reply: a failed write cannot be answered", J, [(' && d.state !== "WRITE_FAILED"', '')], T_JS),
    ("install: the reason is not trimmed in ready", J, [(RDY, RDY.replace("why.value.trim()", "why.value"))], T_JS),
    ("install: the reason of one character opens it", J, [(RDY, RDY.replace("< 10", "< 1"))], T_JS),
    ("install: no word about the branch", J, [('the commit goes to a new branch argus/<job> and the checkout stays on that branch afterwards. ', '')], T_JS),
    ("confirm card: the install facts are not drawn", J, [('    if (applies) {\n      (card.files', '    if (false) {\n      (card.files')], T_JS),
    ("confirm card: the code_apply started text is wrong", J, [('It makes one commit in the repository on this machine: nothing is pushed', 'Nothing runs: nothing is pushed')], T_JS),
    ("state: no started mark", S, [('        out["started"] = self._started(job_id)', '        out["started"] = None')], T_PY),
    ("state: started ignores a recorded apply", S, [('            if d.get("state") == "APPLIED":\n                return None\n', '')], T_PY),
    ("state: started reads the first entry, not the last", S, [('            for e in reversed(d.get("log") or []):', '            for e in (d.get("log") or []):')], T_PY),
    ("state: a long time string is passed on", S, [('len(at) <= 40', 'True')], T_PY),
]
killed = ran = 0
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
