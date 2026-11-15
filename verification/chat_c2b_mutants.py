"""Mutants for SPEC_CHAT_APP C2b (router/chat_static/app.js, index.html): each applied alone in a worktree, tests/test_chat_ui.py runs with -x
(the sha pins of test_chat.py would kill any change by themselves and are not what is measured here);
killed = a test FAILED and pytest reported no error. Usage: <this> <worktree> <python>"""
import subprocess
import sys
from pathlib import Path

WT, PY = Path(sys.argv[1]), sys.argv[2]
T = ["-rfEs", "tests/test_chat_ui.py"]
J, H = "router/chat_static/app.js", "router/chat_static/index.html"
M = [
    ("confirm sends the whole card too", J, [("post(\"/api/confirm\", { token: prep.token })", "post(\"/api/confirm\", { token: prep.token, card: prep.card })")]),
    ("confirm sends the action too", J, [("post(\"/api/confirm\", { token: prep.token })", "post(\"/api/confirm\", { token: prep.token, action: prep.card.action })")]),
    ("confirm is armed at once", J, [("    ok.disabled = true;                                 // armed", "    ok.disabled = false;                                 // armed")]),
    ("confirm is armed after a hundredth of a second", J, [("Math.ceil((prep.min_delay_s || 1) * 1000) + 300", "10")]),
    ("confirm ignores the server's delay", J, [("Math.ceil((prep.min_delay_s || 1) * 1000)", "1000")]),
    ("a click on a disabled confirm still posts", J, [("      if (ok.disabled) { return; }\n", "")]),
    ("confirm is focused", J, [("    c.appendChild(row);\n    return c;", "    c.appendChild(row);\n    ok.focus();\n    return c;")]),
    ("confirm is a submit button", J, [("    ok.type = \"button\";", "    ok.type = \"submit\";")]),
    ("confirm is built inside the composer form", H, [("        <button id=\"prepare\" type=\"submit\">Siapkan issue baru</button>", "        <button id=\"prepare\" type=\"submit\">Siapkan issue baru</button><button>Konfirmasi</button>")]),
    ("the card is written as html", J, [("p.appendChild(document.createTextNode(String(value)));", "p.innerHTML = String(value);")]),
    ("every field of the card is shown by key", J, [("    LABELS.forEach(function (kv) {", "    Object.keys(card).forEach(function (k) { fact(c, k, card[k]); });\n    LABELS.forEach(function (kv) {")]),
    ("a third path is posted", J, [("post(\"/api/prepare\", body)", "post(\"/api/message\", body)")]),
    ("credentials are sent on a post", J, [("method: \"POST\", credentials: \"omit\"", "method: \"POST\", credentials: \"include\"")]),
    ("the issue chip is off", H, [("data-mode=\"issue\" aria-pressed=\"false\">", "data-mode=\"issue\" disabled aria-pressed=\"false\">")]),
    ("the composer is shown at the start", H, [("<form id=\"issue-form\" hidden autocomplete=\"off\">", "<form id=\"issue-form\" autocomplete=\"off\">")]),
    ("the message box is a one line input", H, [("<textarea id=\"message\" rows=\"3\"", "<input id=\"message\" rows=\"3\"")]),
    ("a start is prepared with a message of the page", J, [("{ action: \"issue_start\", job: d.id }", "{ action: \"issue_start\", job: d.id, action: \"issue_new\" }")]),
    ("a second link by the handoff", J, [("viewerLink(d.handoff ? VIEWER + d.handoff : null)", "viewerLink(d.handoff)")]),
    ("an autofocus on the composer", H, [("<textarea id=\"message\"", "<textarea autofocus id=\"message\"")]),
    ("the issue form is nested in the composer form", H, [("    <div id=\"dock\">", "    <form id=\"composer-outer\"><div id=\"dock\">"), ("    </div>\n  </main>", "    </div></form>\n  </main>")]),
    ("the script looks up an id the page lacks", H, [("<div id=\"slot\" role=\"status\" aria-live=\"polite\"></div>", "<div id=\"slot2\" role=\"status\" aria-live=\"polite\"></div>")]),
    ("a new card does not settle the old one", J, [("    if (pending) { pending.settle();", "    if (pending) { if (false) pending.settle();")]),
    ("a card is pushed into the stream", J, [("      slot.appendChild(c);\n      c.scrollIntoView", "      stream.insertBefore(c, stream.firstChild);\n      c.scrollIntoView")]),
    ("batal stays on after confirm", J, [("      no.disabled = true;                               // once sent", "      // once sent")]),
    ("a card with a confirm on its way is dropped", J, [("    if (pending && pending.sent) { return; }               // a confirm", "    // a confirm")]),
    ("a prepare is allowed while a confirm is on its way", J, [("    if (busy || (pending && pending.sent)) { return; }", "    if (busy) { return; }")]),
    ("a lost answer reads as a refusal", J, [("        if (e.answered) {", "        if (true) {")]),
    ("a lost answer does not reload the list", J, [("          no.disabled = false;\n          loadIssues();", "          no.disabled = false;")]),
    ("the open issue is set before the thread is read", J, [("      openIssue = id;\n      formState();\n      clear(stream);", "      formState();\n      clear(stream);"), ("  function showIssue(id) {\n", "  function showIssue(id) {\n    openIssue = id;\n")]),
    ("the repo select stays for a reply", J, [("    repoSel.hidden = openIssue !== null;\n", "")]),
    ("a late prepare lands in the new view", J, [("      if (mode !== ctx.mode || openIssue !== ctx.open) { return; }", "")]),
]

if __name__ == "__main__":
    killed = 0
    for name, F, edits in M:
        p = WT / F
        orig = p.read_text()
        text = orig
        for a, b in edits:
            assert text.count(a) == 1, (name, a[:50], text.count(a))
            text = text.replace(a, b, 1)
        p.write_text(text)
        try:
            r = subprocess.run([PY, "-m", "pytest", "-x", "-q", "-p", "no:cacheprovider", *T], cwd=WT,
                               capture_output=True, text=True, timeout=1800)
        finally:
            p.write_text(orig)
        last = (r.stdout.strip().splitlines() or [""])[-1]
        fails = [line for line in r.stdout.splitlines() if line.startswith("FAILED tests/test_")][:1]
        k = bool(fails) and "error" not in last
        killed += k
        verdict = "KILLED " if k else "SKIPPED" if "skipped" in last and not fails else "ERROR  " if "error" in last else "SURVIVED"
        print(f"{verdict} {name}: {fails or last}", flush=True)
    print(f"RESULT: {killed}/{len(M)} killed")
