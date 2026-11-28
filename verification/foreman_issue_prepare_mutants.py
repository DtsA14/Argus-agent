"""Mutants for SPEC_FOREMAN_ISSUE_PREPARE (F44, rev 1 section 7). Applied alone; killed = a test FAILED. Run in a throwaway worktree.
Usage: <this> <worktree> <python> [name-part ...]"""
import os
import subprocess
import sys
from pathlib import Path

WT, PY = Path(sys.argv[1]), sys.argv[2]
ONLY = sys.argv[3:]
A, J, SH = "router/chat_actions.py", "router/chat_static/app.js", "docs/CHAT_CAPABILITIES.md"
T = ["tests/test_chat_manager_ui.py", "tests/test_chat_manager_proposal.py", "tests/test_chat_apply_reply.py", "tests/test_chat_manager_next.py", "tests/test_chat_ui.py",
     "tests/test_chat.py", "tests/test_manager_route.py"]
PRE = 'prepare({ action: "issue_new", repo: p.repo, message: p.text, source_job: mgr.job, source_turn: String(e.n) })'
M = [
    ("ROUTE_ACTION lacks issue", A, [(', "issue": "issue_new"}', '}')]),
    ("the build guard still refuses issue_new", A, [('action not in ("research_new", "prd_new", "issue_new"):', 'action not in ("research_new", "prd_new"):')]),
    ("the source is not put on the card", A, [('            if src:\n                card = {**card, "source": src, "source_note": SOURCE_NOTE}', '            if False:\n                card = {**card, "source": src, "source_note": SOURCE_NOTE}')]),
    ("edited ignores the repo for issue_new", A, [('action in ("prd_new", "issue_new") and p.get("repo")', 'action == "prd_new" and p.get("repo")')]),
    ("rp carries the source", A, [('card = {**card, "source": src, "source_note": SOURCE_NOTE}\n            return card, {"repo": repo, "message": text}', 'card = {**card, "source": src, "source_note": SOURCE_NOTE}\n            return card, {"repo": repo, "message": text, "source": src}')]),
    ("a non-session job is a source", A, [('d[0].get("kind") == "manager" else None', 'True else None')]),
    ("next_steps back on ROUTE_ACTION.values()", A, [('r.get("action") in ("research_new", "prd_new")):', 'r.get("action") in ROUTE_ACTION.values()):')]),
    ("the guard text is unchanged", A, [("only a research, PRD or issue form can start", "only a research or PRD job can start")]),
    ("the source refusal text is unchanged", A, [("the foreman proposed no research, PRD or issue job in that turn", "the foreman proposed no research or PRD job in that turn")]),
    ("page Prepare sends no source", J, [(PRE, 'prepare({ action: "issue_new", repo: p.repo, message: p.text })')]),
    ("page Prepare sends the wrong action", J, [(PRE, PRE.replace('"issue_new"', '"prd_new"'))]),
    ("page Prepare uses repoSel.value", J, [(PRE, PRE.replace("repo: p.repo", "repo: repoSel.value"))]),
    ("page Prepare is on without a repo", J, [("igo.disabled = !p.repo;", "igo.disabled = false;")]),
    ("page Edit first does not keep the source", J, [('        fromProposal = { job: job, turn: e.n };\n      });\n      irow.appendChild(igo);', '      });\n      irow.appendChild(igo);')]),
    ("page saves the session after the mode move", J, [('        var job = mgr.job;\n        setMode("issue");', '        setMode("issue");\n        var job = mgr.job;')]),
    ("prepare() filter without issue_new", J, [(' || body.action === "issue_new") && body.source_job === undefined', ') && body.source_job === undefined')]),
    ("prepare() filter as a prefix", J, [('|| body.action === "issue_new") && body.source_job', '|| body.action.indexOf("issue") === 0) && body.source_job')]),
    ("fromProposal not cleared on showIssue", J, [('    if (!keep) { fromProposal = null; }                // the person opened an issue: a form typed later is their own\n', '')]),
    ("fromProposal not cleared on back", J, [('openIssue = null; fromProposal = null; formState(); renderIssues();', 'openIssue = null; formState(); renderIssues();')]),
    ("sheet changed without repin", SH, [("Atha membaca kartunya dan mengonfirmasi sendiri.", "Atha membaca kartunya dan  mengonfirmasi sendiri.")]),
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
