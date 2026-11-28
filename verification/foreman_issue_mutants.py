"""Mutants for SPEC_FOREMAN_ISSUE_ROUTE (F31, rev 1 section 10). Applied alone; killed = a test FAILED. Run in a throwaway worktree.
Usage: <this> <worktree> <python> [name-part ...]"""
import os
import subprocess
import sys
from pathlib import Path

WT, PY = Path(sys.argv[1]), sys.argv[2]
ONLY = sys.argv[3:]
R, E, A, J, SH = "router/manager_route.py", "router/route_eval.py", "router/chat_actions.py", "router/chat_static/app.js", "docs/CHAT_CAPABILITIES.md"
T = ["tests/test_manager_route.py", "tests/test_route_eval.py", "tests/test_manager_job.py", "tests/test_chat_manager_ui.py", "tests/test_chat_manager_proposal.py",
     "tests/test_chat_apply_reply.py"]
ISS = 'elif iw.text_problem(p["text"], "an issue text", hi):'
M = [
    ("issue is not in ROUTES", R, [('ROUTES = ("research", "prd", "issue", "ask", "none")', 'ROUTES = ("research", "prd", "ask", "none")')]),
    ("issue repo check dropped", R, [('out.append("an issue proposal names a registered repository")', 'pass')]),
    ("issue lower bound off by one", R, [('lo, hi = ISSUE_TEXT\n        if not lo <= len(text) <= hi:', 'lo, hi = ISSUE_TEXT\n        if not lo < len(text) <= hi:')]),
    ("issue upper bound off by one", R, [('lo, hi = ISSUE_TEXT\n        if not lo <= len(text) <= hi:', 'lo, hi = ISSUE_TEXT\n        if not lo <= len(text) < hi:')]),
    ("ISSUE_TEXT is research's 2000", R, [('ISSUE_TEXT = (20, 4000)', 'ISSUE_TEXT = (20, 2000)')]),
    ("issue text checked stripped, not raw", R, [(ISS, 'elif iw.text_problem(text, "an issue text", hi):'), ('out.append(iw.text_problem(p["text"], "an issue text", hi))', 'out.append(iw.text_problem(text, "an issue text", hi))')]),
    ("issue has no writer text check", R, [(ISS, 'elif False:')]),
    ("ROUTE_ACTION gains issue", A, [('ROUTE_ACTION = {"research": "research_new", "prd": "prd_new"}', 'ROUTE_ACTION = {"research": "research_new", "prd": "prd_new", "issue": "issue_new"}')]),
    ("issue_new may carry a source", A, [('if SOURCE_KEYS & set(params) and action not in ("research_new", "prd_new"):', 'if SOURCE_KEYS & set(params) and action not in ("research_new", "prd_new", "issue_new"):')]),
    ("page gives issue a Prepare button", J, [('      irow.appendChild(fill);', '      irow.appendChild(fill);\n      var pg = el("button", "go", "Prepare"); pg.type = "button"; pg.addEventListener("click", function () { prepare({ action: "issue_new", repo: p.repo, message: p.text }); }); irow.appendChild(pg);')]),
    ("page sets the source for issue and the filter is dropped", J, [('        setMode("issue");\n        message.value = p.text;', '        setMode("issue");\n        fromProposal = { job: mgr.job, turn: e.n };\n        message.value = p.text;'),
                                                                     ('body.action === "research_new" || body.action === "prd_new"', 'true')]),
    ("page fills only the text", J, [('if (listed) { repoSel.value = p.repo; }', 'if (listed) { }')]),
    ("page fills only the repo", J, [('        setMode("issue");\n        message.value = p.text;\n        grow();', '        setMode("issue");\n        grow();')]),
    ("page picks an unlisted repo blindly", J, [('if (listed) { repoSel.value = p.repo; }', 'if (true) { repoSel.value = p.repo; }')]),
    ("page says nothing about an unlisted repo", J, [('showNote("The proposed repository " + String(p.repo) + " is not in the list: choose one.")', '0')]),
    ("judge repo check stays prd-only", E, [('route in ("prd", "issue") and p["repo"] != case["repo"]', 'route == "prd" and p["repo"] != case["repo"]')]),
    ("judge forbid check removed", E, [('if p["repo"] in (case.get("forbid_repos") or []):', 'if False:')]),
    ("sheet changed without repin", SH, [('## Aturan rute\n', '## Aturan rute \n')]),
    ("instruction without the prd boundary", R, [('two or more separate changes, a feature with several parts, or a request that needs planning is "\n    "\\"prd\\", not \\"issue\\"; ', '')]),
    ("instruction text clause without issue", R, [('for prd and for issue the request, else empty', 'for prd the request, else empty')]),
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
        r = subprocess.run([PY, "-m", "pytest", "-x", "-q", "-p", "no:cacheprovider", "-n0", *T], cwd=WT, capture_output=True, text=True, timeout=300,
                           env={**os.environ, "PYTHONPATH": f"{WT}:{WT}/scripts:{WT}/tests"})
        dead = r.returncode != 0
    except subprocess.TimeoutExpired:
        dead = True
    finally:
        p.write_text(orig)
    killed += dead
    print("killed " if dead else "SURVIVED", name, flush=True)
print(f"{killed}/{ran} killed")
