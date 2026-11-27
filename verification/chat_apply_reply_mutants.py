"""Mutants for SPEC_CHAT_APPLY_REPLY PR2 (router/chat_apply.py, its wiring in chat_actions.py and chat.py, and the two changes of approve_code.py). Applied alone; killed = a test FAILED.
Run in a throwaway worktree, never in the live checkout. Not mutated (unchanged code, documented): the token of `prd_approve` after a `prd_reply` (its state check is
`chat_plan.build_approve`'s, which this PR does not touch); `Actions.exposure_of` falling back to 0.0 for an unknown action (recorded as a deviation in section 13); "the disk sha is not compared to the card's" in `patch_text` (equivalent: condition (g) of the card, which the check loop enforces, is exactly review == provenance == disk, so a card that passes the loop cannot have disk != full).
Usage: <this> <worktree> <python> [name-part ...]"""
import os
import subprocess
import sys
from pathlib import Path

WT, PY = Path(sys.argv[1]), sys.argv[2]
ONLY = sys.argv[3:]
C, A, H, AC = "router/chat_apply.py", "router/chat_actions.py", "router/chat.py", "router/approve_code.py"
T = ["tests/test_chat_apply_reply.py"]
T_AC = ["tests/test_chat_apply_reply.py", "tests/test_approve_code.py"]
M = [
    ("repo: compare names instead of the path", C, [('        if len(names) != 1:', '        if len(names) != 1 and False:')], T),
    ("repo: no expanduser", C, [('os.path.realpath(str(Path(str(r["path"])).expanduser()))', 'os.path.realpath(str(r["path"]))')], T),
    ("repo: Argus itself allowed", C, [('        if mine == ROOT_REAL or mine.startswith(ROOT_REAL + os.sep):', '        if False:')], T),
    ("repo: a subdirectory of Argus allowed", C, [(' or mine.startswith(ROOT_REAL + os.sep):', ':')], T),
    ("apply: the client sha is not compared", C, [('card.get("patch_sha12") != seen:', 'False:')], T),
    ("apply: the sha12 of the card is passed as read-sha", C, [('return out, {"job": job_id, "sha": full, "reason": reason}', 'return out, {"job": job_id, "sha": seen, "reason": reason}')], T),
    ("apply: the check loop is dropped", C, [('            if c.get("key") != "f" and c.get("ok") is False:', '            if False:')], T),
    ("apply: the loop skips another key than f", C, [('            if c.get("key") != "f" and c.get("ok") is False:', '            if c.get("key") != "g" and c.get("ok") is False:')], T),
    ("apply: a Claude reading is allowed", C, [('        if any(r.get("kind") != "argus" for r in readers):', '        if False:')], T),
    ("apply: concerns accepted without a reason", C, [('            if "reason" not in params:', '            if False:')], T),
    ("apply: the same reader twice accepted", C, [(' or ids[0] == ids[1]:', ':')], T),
    ("apply: a reason with two ok readings accepted", C, [('            if "reason" in params:\n                raise self._no(400, "form", "both readers were fine', '            if False:\n                raise self._no(400, "form", "both readers were fine')], T),
    ("apply: nit is not a final kind", C, [('FINAL_KINDS = ("ok", "nit")', 'FINAL_KINDS = ("ok",)')], T),
    ("apply: the scrub check is dropped", C, [('        if scrub(text) != text:', '        if False:')], T),
    ("apply: the size check is dropped", C, [('        if len(raw) > PATCH_TEXT_MAX:', '        if False:')], T),
    ("apply: the busy check is dropped", C, [('        if a.spawner.busy(job_id):\n            raise self._no(409, "busy", "a run is going on for this job")\n        branch, head, main', '        branch, head, main')], T),
    ("apply: the reason as two tokens", C, [('[f"--accept-concerns={rp[\'reason\']}"]', '["--accept-concerns", rp["reason"]]')], T),
    ("apply: the `--` before the job id is dropped", C, [('+ ["--", rp["job"]]\n            a.spawner.spawn(rp["job"], a.with_config(base + tail)', '+ [rp["job"]]\n            a.spawner.spawn(rp["job"], a.with_config(base + tail)')], T),
    ("apply: --via ui is dropped", C, [('"--reader", "argus", "--via", "ui"]', '"--reader", "argus"]')], T),
    ("apply: a key file is given", C, [('tail = ["apply", "--read-sha"', 'tail = ["--key-file", "x", "apply", "--read-sha"')], T),
    ("apply: the card has no sid", C, [('"sid": card.get("sid"), "patch_sha256": full,', '"patch_sha256": full,')], T),
    ("apply: the card has no full sha", C, [('"sid": card.get("sid"), "patch_sha256": full, "patch_read_kind": kind,', '"sid": card.get("sid"), "patch_read_kind": kind,')], T),
    ("apply: the card has no checks", C, [('"checks": [{"key": c.get("key"), "ok": c.get("ok")} for c in card.get("checks") or [] if isinstance(c, dict)],', '')], T),
    ("install: a None card passes as a card", C, [('        if card is None:                                      # None or an exception', '        if False:                                             # None or an exception')], T),
    ("install: any state is accepted", C, [('        if card.get("state") != "REVIEW_READY":', '        if False:')], T),
    ("reader: the per-day limit is three", C, [('READS_PER_DAY = 2 ', 'READS_PER_DAY = 3 ')], T),
    ("reader: the limit ignores the job", C, [('r.get("job") == job_id and parse_time', 'parse_time')], T),
    ("reader: the limit counts every action", C, [('r.get("action") == "patch_read_run" and r.get("attempt") == "confirm" and r.get("job")', 'r.get("attempt") == "confirm" and r.get("job")')], T),
    ("reader: the key is not required", C, [('        self._need_reader_key()\n        if self.reads_today', '        if self.reads_today')], T),
    ("reader: the code key before the reader key", C, [('return self.a.environ.get(READER_KEY_ENV) or self.a.environ.get(KEY_ENV) or None', 'return self.a.environ.get(KEY_ENV) or self.a.environ.get(READER_KEY_ENV) or None')], T),
    ("reader: a spent cap is allowed", C, [('        if remaining <= 1e-9:', '        if False:')], T),
    ("reader: a ledger without a price is allowed", C, [('        if not complete:', '        if False:')], T),
    ("reader: final readings are read again", C, [('        if self.final_readings(card):', '        if False:')], T),
    ("reader: the resume rule is dropped (a lone concerns is always offered)", C, [('            return not resume', '            return False')], T),
    ("reader: the cap has no upper clamp", C, [(' or not 0 < float(v) <= READ_CAP_MAX_USD:', ' or not 0 < float(v):')], T),
    ("reader: a bool cap is accepted", C, [('if isinstance(v, bool) or not isinstance(v, (int, float))', 'if not isinstance(v, (int, float))')], T),
    ("reader: the ledger is read through a link", C, [('                        raw = sd._read_at(jfd, LEDGER, limit=LEDGER_MAX)', '                        raw = open(os.path.join(str(self.a.jobs_dir), job_id, LEDGER), "rb").read()')], T),
    ("reader: the argv carries a cap from the card's text, not the config", C, [('"--cap-usd", repr(float(rp["cap"]))', '"--cap-usd", "5"')], T),
    ("money: a reading adds no exposure", C, [('            return float(card["remaining_usd"])', '            return 0.0')], T),
    ("money: a reply ignores `counted`", C, [('        if card["action"] == "prd_reply" and not card.get("counted"):', '        if card["action"] == "prd_reply":')], T),
    ("money: the audit net ignores prd_reply", C, [('r.get("action") in ("prd_reply", "patch_read_run") and r.get("attempt") == "confirm":', 'r.get("action") in ("patch_read_run",) and r.get("attempt") == "confirm":')], T),
    ("money: the audit net ignores the 24 hour window", C, [('                    if parse_time(r["at"]) >= now - DAY:\n                        total += finite_usd(r.get("usd") or 0)', '                    if True:\n                        total += finite_usd(r.get("usd") or 0)')], T),
    ("money: the audit net is not added to the exposure", A, [('        total += self.apply_reply.audited(now)', '        pass')], T),
    ("money: the confirm line has no usd", H, [('            rec.update(usd=a.exposure_of(card))\n            if card.get("reason"):', '            if card.get("reason"):')], T),
    ("reply: the state check is dropped", C, [('        if state not in pj.REPLYABLE:', '        if False:')], T),
    ("reply: WRITE_FAILED is not allowed", C, [('        if state not in pj.REPLYABLE:', '        if state != "AWAITING_HUMAN":')], T),
    ("reply: the busy check is dropped", C, [('        if a.spawner.busy(job_id):\n            raise self._no(409, "busy", "the writer is still working', '        if False:\n            raise self._no(409, "busy", "the writer is still working')], T),
    ("reply: the budget check is dropped", C, [('        if left + 1e-12 < turn_cap:', '        if False:')], T),
    ("reply: the repository state is not checked", C, [('            pj._repo_state(cfg, i["repo_name"], i["commit"], a.cards.queues_dir, a.jobs_dir)', '            pass')], T),
    ("reply: the key is not required", C, [('        a._need_key(True)\n        i = d.get', '        i = d.get')], T),
    ("reply: the message is not checked", C, [('        if why:\n            raise self._no(400, "form", why)\n        a._need_key(True)', '        a._need_key(True)')], T),
    ("reply: --rebase is passed", C, [('"reply", "--message-file", str(message))', '"reply", "--rebase", "--message-file", str(message))')], T),
    ("reply: the message goes in argv", C, [('"reply", "--message-file", str(message))', '"reply", "--message", rp["message"])')], T),
    ("wire: code_apply cannot carry a sha (the HTTP check)", H, [('and action != "code_apply":', ':')], T),
    ("wire: another action may carry a sha", H, [('if action in ACTIONS and not action.startswith("job_") and action != "code_apply":', 'if False:')], T),
    ("wire: the install route has no button state", H, [('                got["apply"] = a.apply_reply.state(m.group(1))', '                pass')], T),
    ("wire: the diff route is a POST route too", H, [('"/api/manager/turn": "manager_turn"}', '"/api/manager/turn": "manager_turn", "/api/diff": "prepare"}')], T),
    ("card: raw_pair is off", AC, [('rsha, raw_pair=True) if sid and rsha', 'rsha) if sid and rsha')], T_AC),
    ("card: the patch bytes land in the card", AC, [('            return (out, patch_bytes, disk_sha) if keep else out', '            out["_patch"] = patch_bytes.decode("utf-8", "replace") if patch_bytes else None\n            return (out, patch_bytes, disk_sha) if keep else out')], T_AC),
    ("state: the apply button without the builder", C, [('            self.build_apply({"job": job_id, "sha": card["patch_sha12"], **({} if k in FINAL_KINDS else {"reason": "x" * 10})}, have)\n', '')], T),
    ("state: the read button without the builder", C, [('                self.build_read({"job": job_id}, have)\n', '')], T),
]
killed = 0
ran = 0
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
