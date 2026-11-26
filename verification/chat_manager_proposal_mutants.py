"""Mutants for CHAT-MANAGER P2B (SPEC_CHAT_MANAGER_P2B section 6): the source of a form filled from the foreman's proposal. Applied alone; killed = a test FAILED.
Usage: <this> <worktree> <python>"""
import subprocess
import sys
from pathlib import Path

WT, PY = Path(sys.argv[1]), sys.argv[2]
A, C = "router/chat_actions.py", "router/chat.py"
T = ["-rfEs", "tests/test_chat_manager_proposal.py", "tests/test_chat_manager.py"]
GUARD = '        if SOURCE_KEYS & set(params) and action not in ("research_new", "prd_new"):\n            raise Refusal(400, "form", "only a research or PRD job can start from the foreman\'s proposal")\n'
M = [
    ("any action takes a source", A, [(GUARD, "")]),
    ("the turn pattern is loose", A, [('re.fullmatch(r"0|[1-9][0-9]{0,2}", turn)', 're.fullmatch(r"-?[0-9 ]{1,4}", turn)')]),
    ("the kind is not checked", A, [('d is not None and d[0].get("kind") == "manager" else None', 'd is not None else None')]),
    ("a human turn is a source", A, [('isinstance(e, dict) and e.get("from") == "manager" else None', 'isinstance(e, dict) else None')]),
    ("a turn without a proposal is a source", A, [('        if not isinstance(p, dict) or p.get("route") not in ROUTE_ACTION:', '        if False:')]),
    ("a route outside research/prd is a source", A, [('p.get("route") not in ROUTE_ACTION:', 'not p.get("route"):')]),
    ("off by one on the turn index", A, [("isinstance(conv, list) and i < len(conv)", "isinstance(conv, list) and i <= len(conv)")]),
    ("the card has no source", A, [('return ({**card, "source": src, "source_note": SOURCE_NOTE} if src else card), rp', "return card, rp")]),
    ("the card has no note", A, [('{**card, "source": src, "source_note": SOURCE_NOTE}', '{**card, "source": src}')]),
    ("edited is always false", A, [("        edited = (not same_route", "        edited = False and (not same_route")]),
    ("edited ignores the route", A, [("        edited = (not same_route or ", "        edited = (")]),
    ("edited ignores the text", A, [('normalize(scrub(str(p.get("text") or ""))) != normalize(rest.get("message") or "")', "False")]),
    ("edited ignores the repo", A, [('or (action == "prd_new" and p.get("repo") != rest.get("repo")))', ")")]),
    ("edited compares without normalize", A, [('normalize(scrub(str(p.get("text") or ""))) != normalize(rest.get("message") or "")', 'scrub(str(p.get("text") or "")) != (rest.get("message") or "")')]),
    ("edited compares without scrub", A, [('normalize(scrub(str(p.get("text") or "")))', 'normalize(str(p.get("text") or ""))')]),
    ("the why goes into the card", A, [('"source": src, "source_note": SOURCE_NOTE}', '"source": src, "source_note": SOURCE_NOTE, "why": src and 1}')]),
    ("the source goes into the run params", A, [('return ({**card, "source": src, "source_note": SOURCE_NOTE} if src else card), rp', 'return ({**card, "source": src, "source_note": SOURCE_NOTE} if src else card), {**rp, "source": src}')]),
    ("the source keys are not stripped", A, [("rest = {k: v for k, v in params.items() if k not in SOURCE_KEYS}", "rest = dict(params)")]),
    ("the source keys are not params", C, [(', "queue", "source_job", "source_turn"}', ', "queue"}')]),
    ("the prepare audit has no source", C, [('        if "source_job" in params:', '        if False:')]),
    ("the prepare audit writes the raw job", C, [('params["source_job"] if UI_ID.fullmatch(params["source_job"]) else "bad"', 'params["source_job"]')]),
    ("the confirm audit has no source", C, [('        if card.get("source"):', '        if False:')]),
    ("the confirm audit has no edited", C, [(', edited=card["source"]["edited"])', ")")]),
    ("the read route has no index", A, [('out.append({"from": "manager", "n": n, ', 'out.append({"from": "manager", ')]),
    ("the index counts the kept entries", A, [("        for n, e in enumerate(d.get(\"conversation\") or []):\n            if not isinstance(e, dict):\n                continue", "        for e in d.get(\"conversation\") or []:\n            if not isinstance(e, dict):\n                continue\n            n = len(out)")]),
    ("the state must be open", A, [("        d = self._read_data(job, ledgers=False)\n        conv", '        d = self._read_data(job, ledgers=False)\n        if d is not None and d[0].get("state") != "OPEN":\n            d = None\n        conv')]),
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
