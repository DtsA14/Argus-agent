"""Mutants for T4a (SPEC_CHAT_T4A rev 1): `prd_approve` and `queue_go` of the chat, `queue go --via --reason-file`. Applied alone; killed = a test FAILED
(or the module did not even load: the pins and the imports are part of the guarantee). Usage: <this> <worktree> <python>"""
import subprocess
import sys
from pathlib import Path

WT, PY = Path(sys.argv[1]), sys.argv[2]
P, A, C, Q, R, S = "router/chat_plan.py", "router/chat_actions.py", "router/chat.py", "router/queue.py", "router/reason.py", "scripts/argus.py"
T = ["-rfEs", "tests/test_chat_plan.py", "tests/test_chat_actions.py", "tests/test_chat_prd_new.py", "tests/test_apply_cmd.py", "tests/test_queue.py", "tests/test_chat_money_inputs.py"]
# Result 2026-11-21: 54/55 killed; the one survivor, "the plan approval dir is the client's", is equivalent (a `dir` param is a 400 before the line is reached).
M = [
    ("an approved queue can be approved again", P, [('        if q.get("approved"):\n            raise self._no(409, "queue", f"queue {q[\'id\']} is already approved")\n        if not ok:', '        if not ok:')]),
    ("M8 accepts concerns", P, [('if i["read"] not in ("ok", "tidak_berlaku")]\n        if bad:', 'if i["read"] not in ("ok", "tidak_berlaku", "concerns")]\n        if bad:')]),
    ("M8 accepts one reading", P, [('if i["read"] not in ("ok", "tidak_berlaku")]\n        if bad:', 'if i["read"] not in ("ok", "tidak_berlaku", "one")]\n        if bad:')]),
    ("M8 accepts unreadable examples", P, [('if i["read"] not in ("ok", "tidak_berlaku")]\n        if bad:', 'if i["read"] not in ("ok", "tidak_berlaku", "tidak_terbaca")]\n        if bad:')]),
    ("M8 is not checked", P, [('        if bad:\n            raise self._no(409, "read"', '        if False:\n            raise self._no(409, "read"')]),
    ("any acknowledgement is enough", P, [('            if ack != ",".join(map(str, need_ack)):', '            if not ack:')]),
    ("an acknowledgement for nothing is accepted", P, [('        elif ack:\n            raise self._no(400, "form", "nothing to acknowledge")', '        elif False:\n            raise self._no(400, "form", "nothing to acknowledge")')]),
    ("no reason is needed when there is no reference", P, [('need_reason = ratio is None or ratio >= RATIO_REASON', 'need_reason = ratio is not None and ratio >= RATIO_REASON')]),
    ("the ratio threshold is strict", P, [('need_reason = ratio is None or ratio >= RATIO_REASON', 'need_reason = ratio is None or ratio > RATIO_REASON')]),
    ("a reason is accepted where none is needed", P, [('        elif reason is not None:\n            raise self._no(400, "form", "this plan needs no reason")', '        elif False:\n            raise self._no(400, "form", "this plan needs no reason")')]),
    ("the reason is not validated", P, [('reason = reason_rule.check(reason, "the reason", "nothing was approved")', 'reason = reason')]),
    ("the queue's directory is not compared", P, [('if os.path.realpath(p.get("dir") or "") != f["folder"] or not self.a.cards._same_jobs_dir(q):', 'if not self.a.cards._same_jobs_dir(q):')]),
    ("the queue's jobs dir is not compared", P, [('if os.path.realpath(p.get("dir") or "") != f["folder"] or not self.a.cards._same_jobs_dir(q):', 'if os.path.realpath(p.get("dir") or "") != f["folder"]:')]),
    ("a changed issue file is accepted", P, [('                        if hashlib.sha256(raw).hexdigest() != item["issue_sha256"]:\n                            ok = False\n                            break', '                        if False:\n                            ok = False\n                            break')]),
    ("the queue's issue count is not compared", P, [('or len(q["items"]) != f["n"]:', ':')]),
    ("the queue's money is not compared", P, [('if to_nano(q["max_usd"]) != to_nano(t["max_usd"]) or len(q["items"]) != f["n"]:', 'if len(q["items"]) != f["n"]:')]),
    ("a superseded folder is offered", P, [('            if files.pop("__superseded__"):', '            if files.pop("__superseded__") and False:')]),
    ("a stale plan is offered", P, [('            if not t.get("commit") or t.get("commit") != data["inputs"].get("commit"):', '            if False:')]),
    ("an unbound folder is offered", P, [('            if rp.folder_sha(files) != t["folder_sha"]:', '            if False:')]),
    ("the plan state is not required for the queue", P, [('        if f["data"].get("state") != pj.AWAITING_HUMAN:\n            raise self._no(409, "state", f"job {f[\'job\']} is {f[\'data\'].get(\'state\')}: a queue is started', '        if False:\n            raise self._no(409, "state", f"job {f[\'job\']} is {f[\'data\'].get(\'state\')}: a queue is started')]),
    ("a busy writer does not stop the queue", P, [('        if self.a.spawner.busy(f["job"]):\n            raise self._no(409, "busy", "the writer is still working on this job")\n        q, ok = self.queue_of(f)', '        q, ok = self.queue_of(f)')]),
    ("a busy writer does not stop the plan approval", P, [('        if a.spawner.busy(f["job"]):\n            raise self._no(409, "busy", "the writer is still working on this job")', '')]),
    ("an unfinished queue does not stop the plan approval", P, [('        other = self.unfinished_on(f["repo"])', '        other = None')]),
    ("the unfinished check asks rq.derive (git)", P, [('self.a.cards._derive(q)[0] not in ("DONE", "CLOSED")', 'rq.derive(q)[0] not in (rq.DONE, rq.CLOSED)')]),
    ("the plan approval dir is the client's", P, [('return card, {"job": f["job"], "dir": f["folder"], "sha": t["folder_sha"]}', 'return card, {"job": f["job"], "dir": params.get("dir", f["folder"]), "sha": t["folder_sha"]}')]),
    ("the CLI gets a short sha", P, [('tail = ["queue", "go", rp_["queue"], "--sha", rp_["sha"], "--via", "ui"]', 'tail = ["queue", "go", rp_["queue"], "--sha", rp_["sha"][:12], "--via", "ui"]')]),
    ("the CLI gets no --via", P, [('"--sha", rp_["sha"], "--via", "ui"]', '"--sha", rp_["sha"]]')]),
    ("the reason file is left behind", P, [('                reason_file.unlink(missing_ok=True)', '                pass')]),
    ("the CLI line is not scrubbed", P, [('(a_scrub(line)[:300]) or "the command failed"', '(line[:300]) or "the command failed"')]),
    ("a failed queue go is counted as pending", P, [('        a.pending.append((a.clock(), ("go", rp_["queue"]), float(card["queue_usd"])))\n        return {"job": rp_["job"], "queue": rp_["queue"], "done": True}', '        return {"job": rp_["job"], "queue": rp_["queue"], "done": True}')]),
    ("a terminal approval counts", P, [('if isinstance(ap, dict) and ap.get("via") == "ui":', 'if isinstance(ap, dict):')]),
    ("an approval outside 24 hours counts", P, [('                    if at < now - DAY:\n                        continue', '                    if False:\n                        continue')]),
    ("an approved queue is counted twice", P, [('                    total += usd\n                    seen.add(("go", name))', '                    total += usd')]),
    ("an unreadable queue is skipped in the exposure", P, [('raise self._no(503, "cap", f"the daily exposure cannot be computed (queue {name} could not be read)")', 'continue')]),
    ("an unreadable approval is skipped in the exposure", P, [('raise self._no(503, "cap", f"the daily exposure cannot be computed (queue {name}: the approval time cannot be read)") from None', 'continue')]),
    ("an unreadable amount is skipped in the exposure", P, [('raise self._no(503, "cap", f"the daily exposure cannot be computed (queue {name}: the money cannot be read)") from None', 'continue')]),
    ("the window edge is skipped", P, [('if at < now - DAY:', 'if at <= now - DAY:')]),
    ("negative money is accepted in the exposure", P, [('if not math.isfinite(usd) or usd <= 0:', 'if not math.isfinite(usd):')]),
    ("the audit net counts attempts", P, [('r.get("action") == "queue_go" and r.get("ok") == "confirm"', 'r.get("action") == "queue_go"')]),
    ("the audit net is dropped", A, [('        for job_id, usd, at in self.plans.audited(now):', '        for job_id, usd, at in []:')]),
    ("the audit net counts what the directory counted", A, [('            if ("go", job_id) not in seen and os.path.lexists(self.cards.queues_dir / job_id):', '            if os.path.lexists(self.cards.queues_dir / job_id):')]),
    ("the queue exposure is not added", A, [('        total += self.plans.exposure(now, seen)               # queues approved via the UI (SPEC_CHAT_T4A 4)', '')]),
    ("a queue card adds no exposure", A, [('        if card["action"] == "queue_go":\n            return float(card["queue_usd"])', '        if card["action"] == "queue_go":\n            return 0.0')]),
    ("the page state ignores the cap", P, [('            self.a.check_cap({"action": "queue_go", "queue_usd": float(q["max_usd"])})\n', '')]),
    ("the page state names only one need", P, [('"needs": (["ack"] if need_ack else []) + (["reason"] if need_reason else [])}', '"needs": (["ack"] if need_ack else (["reason"] if need_reason else []))}')]),
    ("the page state lets an unexpected file shape through as a 500", P, [('        except Exception:                                        # a file that does not have the shape', '        except ZeroDivisionError:                                # a file that does not have the shape')]),
    ("the reason goes to the audit as text", C, [('rec["reason_sha256"] = hashlib.sha256(card["reason"].encode()).hexdigest()', 'rec["reason"] = card["reason"]')]),
    ("the audit line has no queue", C, [('            rec.update(queue=card["queue"], usd=card["queue_usd"])', '            pass')]),
    ("queue go takes an unknown via", Q, [('    if via is not None and via not in rj.VIA:\n        raise Refused(f"via {via!r} is not one of', '    if False:\n        raise Refused(f"via {via!r} is not one of')]),
    ("queue go does not store via", Q, [('**({"via": via} if via else {}),\n                         **({"reason": reason} if reason else {})}', '**({"reason": reason} if reason else {})}')]),
    ("queue go does not store the reason", Q, [('**({"via": via} if via else {}),\n                         **({"reason": reason} if reason else {})}', '**({"via": via} if via else {})}')]),
    ("the CLI drops via", S, [("queues_dir=o.queues_dir, via=o.via,", "queues_dir=o.queues_dir, via=None,")]),
    ("the CLI reads a huge reason file", S, [("        if len(raw) > 4096:\n            raise ValueError(\"too long\")\n", "")]),
    ("a one-line reason may be too short", R, [("if not MIN <= len(t) <= MAX:", "if not len(t) <= MAX:")]),
    ("a reason may hold a key", R, [("    if stage_data.KEY.search(t.encode()) or stage_data.KEY.search(json.dumps(t).encode()):", "    if False:")]),
    ("an unknown action falls through to issue start", A, [('        if a == "issue_start":\n            argv', '        if True:\n            argv')]),
    ("the plan actions are not dispatched at execute", A, [('        if a in ("prd_approve", "queue_go"):                 # no model and no key', '        if False:                 # no model and no key')]),
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
    k = "FAILED tests/" in r.stdout or "FAILED" in last
    killed += k
    print("KILLED " if k else "SURVIVED", name, flush=True)
print(f"RESULT: {killed}/{len(M)} killed")
