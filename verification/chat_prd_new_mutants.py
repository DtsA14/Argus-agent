"""Mutants for P2a (SPEC_CHAT_MANAGER 15): `prd_new` from the chat, `prd new --via ui`, PRD exposure, the explicit execute dispatch.
Applied alone; killed = a test FAILED. Usage: <this> <worktree> <python>"""
import subprocess
import sys
from pathlib import Path

WT, PY = Path(sys.argv[1]), sys.argv[2]
A, P, S, J = "router/chat_actions.py", "router/prd_job.py", "scripts/argus.py", "router/chat_static/app.js"
T = ["-rfEs", "tests/test_chat_prd_new.py", "tests/test_chat_ui.py", "tests/test_chat_actions.py", "tests/test_chat_research.py", "tests/test_prd_writer.py"]
VIA_ENTRY = ('                        if isinstance(entry, dict) and entry.get("what") == "created" and entry.get("via") == "ui" \\\n'
             '                                and parse_time(entry["at"]) >= now - DAY:\n'
             '                            total += max(float(data["max_usd"]), pcap)')
M = [
    ("the PRD card takes extra fields", A, [('if set(params) - {"repo", "message"}:\n            raise Refusal(400, "form", "a PRD job', 'if False:\n            raise Refusal(400, "form", "a PRD job')]),
    ("the PRD repo is not checked", A, [('        if repo not in repos:\n            raise Refusal(400, "form", "that repository is not one the writer reads")\n        try:\n            why = pj.message_problem',
                                          '        if not repo:\n            raise Refusal(400, "form", "that repository is not one the writer reads")\n        try:\n            why = pj.message_problem')]),
    ("the PRD message is not scrubbed", A, [('if why is None and scrub(text) != text:\n                why = "the message holds', 'if False:\n                why = "the message holds')]),
    ("the PRD cap is the turn cap", A, [('cap = float(pj._settings(cfg)["max_usd"])', 'cap = float(pj._settings(cfg)["turn"]["cap_usd"])')]),
    ("the PRD preflight is dropped", A, [('pj._preflight(cfg, cap)\n            f = pj.screen_facts', 'f = pj.screen_facts')]),
    ("the PRD card does not need the writer key", A, [('        self._need_key(True)\n        card = {"action": "prd_new"', '        card = {"action": "prd_new"')]),
    ("the PRD argv has no --via", A, [('"prd", *args,\n            "--via", "ui", "--key-file"', '"prd", *args,\n            "--key-file"')]),
    ("the PRD argv has no --queues-dir", A, [('"--queues-dir", str(queues_dir), "prd", *args,', '"prd", *args,')]),
    ("the PRD run reads another queues directory", A, [('prd_cli(c, self.cards.queues_dir, key', 'prd_cli(c, rq.QUEUES, key')]),
    ("the PRD run gets the code key", A, [('key = self.key_file(a in ("issue_new", "issue_reply", "prd_new")', 'key = self.key_file(a in ("issue_new", "issue_reply")')]),
    ("the PRD confirm is not held as pending", A, [('action="prd", text=rp["message"])\n            self.pending.append((self.clock(), ("new", new_id), self.exposure_of(card)))', 'action="prd", text=rp["message"])')]),
    ("a PRD counts its own max_usd only", A, [('total += max(float(data["max_usd"]), pcap)', 'total += float(data["max_usd"])')]),
    ("a PRD without via counts", A, [(VIA_ENTRY, VIA_ENTRY.replace(' and entry.get("via") == "ui" \\\n                                and parse_time', ' \\\n                                and parse_time'))]),
    ("a PRD older than a day counts", A, [(VIA_ENTRY, VIA_ENTRY.replace('\\\n                                and parse_time(entry["at"]) >= now - DAY:', '\\\n                                and True:'))]),
    ("a PRD is counted twice", A, [('total += max(float(data["max_usd"]), pcap)\n                            seen.add(("new", n))', 'total += max(float(data["max_usd"]), pcap)')]),
    ("the audit net skips PRD jobs", A, [('(("research_new", rcap), ("prd_new", pcap))', '(("research_new", rcap),)')]),
    ("the audit net counts a PRD at the research cap", A, [('("prd_new", pcap))', '("prd_new", rcap))')]),
    ("a PRD card adds no exposure", A, [('if card["action"] in ("issue_new", "issue_start", "research_new", "prd_new"):', 'if card["action"] in ("issue_new", "issue_start", "research_new"):')]),
    ("an unknown action falls through to issue start", A, [('        if a == "issue_start":\n            argv', '        if True:\n            argv')]),
    ("the PRD job id is matched, not fully matched", P, [("rj.JOB_ID.fullmatch(job_id)", "rj.JOB_ID.match(job_id)")]),
    ("an unknown via is accepted", P, [("if via is not None and via not in rj.VIA:", "if False:")]),
    ("the id shape is checked only without via", P, [("if via is not None and job_id is not None:", "if via is not None and job_id is None:")]),
    ("via is not written to the created note", P, [('**({"via": via} if via else {}))\n        try:\n            try:\n                ri._pin_environment', '**{})\n        try:\n            try:\n                ri._pin_environment')]),
    ("the CLI drops via", S, [("refs=o.ref, via=o.via)", "refs=o.ref, via=None)")]),
    ("the screen's turn cap is the job cap", P, [('"turn_cap": float(s["turn"]["cap_usd"])', '"turn_cap": float(s["max_usd"])')]),
    ("the PRD form does not fill the repository list", J, [('formState(); loadIssues(); clear(stream);', 'formState(); clear(stream);')]),
    ("the repository list is hidden in PRD mode", J, [("repoSel.hidden = r || (!p && openIssue !== null);", "repoSel.hidden = r || openIssue !== null;")]),
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
        r = subprocess.run([PY, "-m", "pytest", "-x", "-q", "-p", "no:cacheprovider", "-n", "4", *T], cwd=WT, capture_output=True, text=True, timeout=900)
    finally:
        p.write_text(orig)
    last = (r.stdout.strip().splitlines() or [""])[-1]
    k = "FAILED tests/" in r.stdout and "error" not in last
    killed += k
    print("KILLED " if k else "SURVIVED", name, flush=True)
print(f"RESULT: {killed}/{len(M)} killed")
