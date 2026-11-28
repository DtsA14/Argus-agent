"""Mutants for SPEC_CHAT_JOB_APPROVE rev 1 (F35). Applied alone; killed = a test FAILED. Run in a throwaway worktree.
Usage: <this> <worktree> <python> [name-part ...]"""
import os
import subprocess
import sys
from pathlib import Path

WT, PY = Path(sys.argv[1]), sys.argv[2]
ONLY = sys.argv[3:]
B, A, C, J = "router/chat_t4b.py", "router/chat_actions.py", "router/chat.py", "router/chat_static/app.js"
T = ["tests/test_chat_job_approve.py", "tests/test_chat_t4b.py", "tests/test_chat_decide.py"]
TJ = ["tests/test_chat_ui_node.py", "tests/test_chat_ui.py", "-k", "approve"]
M = [
    ("standalone: truthy instead of is True", B, [('        if res.get("standalone") is not True:\n            raise self._no(409, "queue"', '        if not res.get("standalone"):\n            raise self._no(409, "queue"')], T),
    ("standalone: not required", B, [('        if res.get("standalone") is not True:\n            raise self._no(409, "queue"', '        if False:\n            raise self._no(409, "queue"')], T),
    ("standalone: chain without the chat queues dir", B, [('er.chain(SimpleNamespace(id=job_id, data=data), a.jobs_dir, a.cards.queues_dir)\n        if res.get("standalone") is not True', 'er.chain(SimpleNamespace(id=job_id, data=data), a.jobs_dir)\n        if res.get("standalone") is not True')], T),
    ("kind: not checked", B, [('        if data.get("kind") != "code":\n            raise self._no(409, "kind"', '        if False:\n            raise self._no(409, "kind"')], T),
    ("form: extra fields allowed", B, [('        if set(params) != {"job", "sha"}:', '        if not {"job", "sha"} <= set(params):')], T),
    ("sha: shape not checked", B, [('        if not self.SHA12.fullmatch(sha or ""):', '        if False:')], T),
    ("sha: not compared with the live one", B, [('        if sha != live or df["seen"][:12] != live:', '        if df["seen"][:12] != live:')], T),
    ("sha: the draft read by the helper is not compared", B, [('        if sha != live or df["seen"][:12] != live:', '        if sha != live:')], T),
    ("busy: not checked", B, [('        if a.spawner.busy(job_id):\n            raise self._no(409, "busy", "a run of this service is still working on this job")\n        a._need_key(False)\n        df =', '        a._need_key(False)\n        df =')], T),
    ("key: not needed", B, [('        a._need_key(False)\n        df = self.draft_facts(job_id)', '        df = self.draft_facts(job_id)')], T),
    ("helper: state check removed", B, [('        if job.data.get("state") != rj.AWAITING_APPROVAL:                # stricter than the CLI, which also takes DRAFT_FAILED\n            raise self._no(409, "state", f"job {job_id} is {job.data.get(\'state\')}, not AWAITING_APPROVAL")', '        pass')], T),
    ("helper: the already-approved check removed", B, [('            if (job.data.get("approval") or {}).get("draft_sha256") == seen:\n                raise self._no(409, "state", "this draft was already approved and its agent has run")', '            pass')], T),
    ("helper: the money check removed", B, [('            if cap < need:\n                raise self._no(409, "money", f"${cap:.4f} of the job cap is left for the agent, one attempt needs ${need:.2f}: approving would block the job")\n            advisories', '            advisories')], T),
    ("helper: the link check removed", B, [('            raise self._no(409, "state", "the job directory is reached through a link")\n        try:\n            job = rj.open_job(job_id, a.jobs_dir)', '            pass\n        try:\n            job = rj.open_job(job_id, a.jobs_dir)')], T),
    ("window: the via check removed", B, [('h.get("job") == job_id and h.get("via") == "ui" and', 'h.get("job") == job_id and')], T),
    ("window: the job match removed", B, [('h.get("job") == job_id and h.get("via") == "ui" and', 'h.get("via") == "ui" and')], T),
    ("window: the 24 hours not checked", B, [('and self.a_parse(h["at"]) >= now - DAY:', ':')], T),
    ("window: the card does not carry outside_window", B, [('                "outside_window": outside,\n', '')], T),
    ("window: always inside", B, [('        outside = not self._booked(job_id)', '        outside = False')], T),
    ("window: always outside", B, [('        outside = not self._booked(job_id)', '        outside = True')], T),
    ("money: an outside start adds nothing", B, [('        if card["action"] == "job_approve" and card.get("outside_window"):\n            return float(card["agent_cap_usd"])', '        if False:\n            return 0.0')], T),
    ("net: audited ignores job_approve", B, [('r.get("action") in ("queue_step", "job_approve") and', 'r.get("action") in ("queue_step",) and')], T),
    ("net: the audit record has no usd", C, [('        if action == "job_approve":                                       # SPEC_CHAT_JOB_APPROVE rev 1: the audit net of the daily cap reads usd (non-zero only for a start the cap does not book)\n            rec.update(usd=a.exposure_of(card))\n', '')], T),
    ("exec: the config is not passed", B, [('a.spawner.spawn(rp["job"], a.with_config(base + tail), None, action="job_approve")', 'a.spawner.spawn(rp["job"], base + tail, None, action="job_approve")')], T),
    ("exec: spawned under the queue id", B, [('a.spawner.spawn(rp["job"], a.with_config(base + tail), None, action="job_approve")', 'a.spawner.spawn(str(a.cards.queues_dir), a.with_config(base + tail), None, action="job_approve")')], T),
    ("exec: the short sha is passed", B, [('tail = ["approve", rp["job"], "--sha", rp["sha"], "--via", "ui"', 'tail = ["approve", rp["job"], "--sha", rp["sha"][:12], "--via", "ui"')], T),
    ("exec: no --yes", B, [('"--key-file", str(key), "--yes"]\n        a.spawner.spawn(rp["job"]', '"--key-file", str(key)]\n        a.spawner.spawn(rp["job"]')], T),
    ("route: job_approve goes through build_job", A, [('        if action in ("job_reject", "job_abandon"):\n            return self.build_job(action, params)', '        if action in ("job_reject", "job_abandon", "job_approve"):\n            return self.build_job(action, params)')], T),
    ("route: not dispatched", A, [('        if action == "job_approve":                           # SPEC_CHAT_JOB_APPROVE: a standalone code job\'s draft; not through build_job (that path skips the config on purpose)\n            return self.steps.build_job_approve(params)\n', '')], T),
    ("exposure: job_approve not routed to steps", A, [('        if card["action"] in ("queue_step", "draft_approve", "job_approve"):\n            return self.steps.exposure_of(card)', '        if card["action"] in ("queue_step", "draft_approve"):\n            return self.steps.exposure_of(card)')], T),
    ("row: any kind gets approve", A, [('            if data.get("kind") != "code" or state != rj.AWAITING_APPROVAL or self.spawner.busy(job_id):', '            if state != rj.AWAITING_APPROVAL or self.spawner.busy(job_id):')], T),
    ("row: a queue item gets approve", A, [('            return res.get("standalone") is True\n        except Exception:', '            return True\n        except Exception:')], T),
    ("row: a busy job gets approve", A, [(' or self.spawner.busy(job_id):\n                return False', ':\n                return False')], T),
    ("page: the approve button sends a reason", J, [('prepare({ action: "job_approve", job: r.id, sha: r.sha12 });', 'prepare({ action: "job_approve", job: r.id, sha: r.sha12, reason: why.value });')], TJ),
    ("page: the approve button sends no sha", J, [('prepare({ action: "job_approve", job: r.id, sha: r.sha12 });', 'prepare({ action: "job_approve", job: r.id });')], TJ),
    ("page: the button is open without a sha", J, [('        ap.disabled = !r.sha12;\n', '')], TJ),
    ("page: approve offered when the server did not allow it", J, [('      if (r.allowed.indexOf("approve") !== -1) {         // SPEC_CHAT_JOB_APPROVE', '      if (true) {         // SPEC_CHAT_JOB_APPROVE')], TJ),
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
        r = subprocess.run([PY, "-m", "pytest", "-x", "-q", "-n0", "-p", "no:cacheprovider", *tests], cwd=WT, capture_output=True, text=True, timeout=300,
                           env={**os.environ, "PYTHONPATH": f"{WT}:{WT}/scripts:{WT}/tests"})
        dead = r.returncode != 0
    except subprocess.TimeoutExpired:
        dead = True
    finally:
        p.write_text(orig)
    killed += dead
    print("killed " if dead else "SURVIVED", name, flush=True)
print(f"{killed}/{ran} killed")
