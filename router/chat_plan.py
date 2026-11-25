"""The plan buttons of the chat (docs/reviews/SPEC_CHAT_T4A.md, rev 1 section 10): `prd_approve` (= `argus prd approve DIR --sha S`, no money) and `queue_go`
(= `argus queue go Q --sha S --via ui`, the money). Neither takes a model or a key. The client sends only the PRD job's id (and, when a machine flag asks
for it, `ack` and `reason`): the folder, the queue, the shas and the money are read from the harness here, through directory descriptors, and the card
shows them; the CLI keeps its own gates (sha, check, lock). The machine flags refuse on the server at prepare and again at confirm, never only in a page.
"""
import hashlib
import json
import math
import os
import re
import subprocess
import sys
import time

from harness.llm import to_nano
from router import job as rj
from router import prd as rp
from router import prd_job as pj
from router import queue as rq
from router import reason as reason_rule
from router.cards import ISSUE_MAX, ITEMS_MAX, QUEUE_MAX, TURN, UI_ID, _open_dir, _read
from router.control import ARGUS, CLI_TIMEOUT, strip_refused

PLAN_TIMEOUT = 30                  # the two commands read files and write one; the chat's server is single threaded, so a stuck run must not hold it for CLI_TIMEOUT
RATIO_REASON = 3.0                 # the shown, rounded ratio from here asks for a typed reason (SPEC_KARTU_SETUJU M1)
NEW_QUEUE = re.compile(r"queue (q[0-9]{8}T[0-9]{6}Z-[0-9a-f]{4}) PENDING")
SHA64 = re.compile(r"[0-9a-f]{64}")
DAY = 24 * 3600
AUDIT_NET_BYTES = 1 << 20


class Plan:
    """The two actions for one Actions (router.chat_actions): `a` gives the cards, the jobs and queues directories, the clock, the spawner and the audit."""

    def __init__(self, a, refusal):
        self.a, self.Refusal = a, refusal

    # ---- reading the PRD job and its queue -----------------------------------------------------------------------

    def _no(self, status, gate, why):
        return self.Refusal(status, gate, why)

    def facts(self, job_id):
        """What the last turn of a PRD job says, from the job directory: its folder, bound to its recorded sha, not superseded, not stale."""
        a = self.a
        c = a.cards
        if not isinstance(job_id, str) or not UI_ID.fullmatch(job_id):
            raise self._no(404, "path", "no such PRD job")
        d = c._job_dir(job_id)
        if d is None:
            raise self._no(404, "path", "no such PRD job")
        sfd, jfd = d
        try:
            data = c._job_json(jfd)
            if data is None or data.get("kind") != "prd" or not isinstance(data.get("inputs"), dict):
                raise self._no(404, "path", "no such PRD job")
            turns = [t for t in data.get("prd_turns") or [] if isinstance(t, dict)]
            if not turns:
                raise self._no(409, "state", "the writer has not written a folder yet")
            t = turns[-1]
            n = t.get("items")
            if not (isinstance(t.get("turn"), str) and TURN.fullmatch(t["turn"]) and isinstance(t.get("folder_sha"), str)
                    and SHA64.fullmatch(t["folder_sha"]) and isinstance(n, int) and not isinstance(n, bool) and 0 < n <= ITEMS_MAX):
                raise self._no(409, "state", "the last turn's record is not one this button can read")
            mx = t.get("max_usd")
            if isinstance(mx, bool) or not isinstance(mx, (int, float)) or not math.isfinite(mx) or mx <= 0:
                raise self._no(409, "state", "the plan proposes no money this button can read")
            if not t.get("commit") or t.get("commit") != data["inputs"].get("commit"):
                raise self._no(409, "stale", "the plan was written for a commit the job no longer has: ask the writer again (the terminal, `prd reply --rebase`)")
            files, why = c._folder(jfd, t["turn"], n)
            if files is None:
                raise self._no(409, "folder", why or "the folder cannot be read")
            if files.pop("__superseded__"):
                raise self._no(409, "superseded", "a later turn replaced this folder")
            if rp.folder_sha(files) != t["folder_sha"]:
                raise self._no(409, "folder", "the folder is not the one the turn recorded")
            root = os.path.realpath(a.jobs_dir)
            folder = os.path.join(root, job_id, f"prd-{t['turn']}")
            if os.path.realpath(folder) != folder:
                raise self._no(409, "folder", "the folder is reached through a link")
            return {"job": job_id, "data": data, "turn": t, "n": n, "folder": folder, "repo": data["inputs"].get("repo")}
        finally:
            os.close(jfd)
            os.close(sfd)

    def queues(self):
        """[(q, texts_ok)] of the queues directory, each read through descriptors; one that cannot be read is an error (never skipped)."""
        c = self.a.cards
        qfd = c._queues_fd()
        if qfd is None:
            return []
        out = []
        try:
            for name in sorted(os.listdir(qfd)):
                if not rq.QUEUE_ID.fullmatch(name):
                    continue
                got = c._queue_json(qfd, name)
                if got is None:
                    raise self._no(503, "queue", f"queue {name} cannot be read (damaged or half written): close or remove it from the terminal")
                q, dfd = got
                try:
                    ok = True
                    for item in q["items"]:
                        n = item["n"]
                        try:
                            raw = _read(dfd, f"issue-{n}.md", ISSUE_MAX)
                        except OSError:
                            ok = False
                            break
                        if hashlib.sha256(raw).hexdigest() != item["issue_sha256"]:
                            ok = False
                            break
                finally:
                    os.close(dfd)
                out.append((q, ok))
        finally:
            os.close(qfd)
        return out

    def unfinished_on(self, repo):
        for q, _ok in self.queues():
            try:
                if q["repo"] == os.path.realpath(repo) and self.a.cards._derive(q)[0] not in ("DONE", "CLOSED"):    # fd reads, no git (11.10, 11.13); too many items: not done
                    return q["id"]
            except (OSError, ValueError, KeyError, TypeError):
                raise self._no(503, "queue", f"queue {q.get('id')} on this repository cannot be read") from None
        return None

    def queue_of(self, f):
        """The one PENDING queue made from exactly this folder, or None."""
        found = []
        for q, ok in self.queues():
            p = q.get("prd") or {}
            if q.get("closed") or p.get("sha") != f["turn"]["folder_sha"]:        # a closed queue does not stand in the way of a new one
                continue
            if os.path.realpath(p.get("dir") or "") != f["folder"] or not self.a.cards._same_jobs_dir(q):
                continue
            found.append((q, ok))
        if len(found) > 1:
            raise self._no(409, "queue", "more than one queue was made from this plan: close the extra one from the terminal")
        return found[0] if found else (None, False)

    # ---- the facts the cards are made of -------------------------------------------------------------------------

    def card_facts(self, f):
        """The plan card as the page shows it (router.approve_cards), reduced to what the confirm card holds: nothing that changes with time."""
        c = self.a.approve.plan(f["job"])
        if not c:
            raise self._no(409, "card", "the plan card cannot be read")
        items = []
        for it in c["items"]:
            dr = it.get("domain_read") or {}
            read, accepted = dr.get("kind"), None
            if read == "concerns":                                  # SPEC_CHAT_T4A_ACCEPTED: a human's written acceptance of these very concerns (two readers, this bundle) counts like apply's, and is shown as it is
                from router import examples_read as er
                acc = er.accepted_for(self.a.jobs_dir, f["job"], it["n"])
                if acc is not None:
                    read, accepted = "accepted", a_scrub(str(acc.get("reason")))[:300]
            items.append({"n": it["n"], "title": it["title"], "calls": it["counts"]["calls"], "warning": bool(it.get("warning")),
                          "read": read, **({"accepted": accepted} if accepted is not None else {})})
        return {"request": c.get("request"), "summary": c.get("summary"), "items": items, "cost": c["cost"]}

    @staticmethod
    def ratio_of(each, reference):
        cost = {"proposed_each": each, "reference": reference}
        from router.approve_cards import Approve
        Approve._ratio(cost)
        return cost.get("ratio"), cost.get("ratio_text")

    # ---- build (prepare and confirm both) --------------------------------------------------------------------------

    def build_approve(self, params):
        a = self.a
        if set(params) - {"job"}:
            raise self._no(400, "form", "approving a plan takes the PRD job and nothing else")
        f = self.facts(params.get("job"))
        if f["data"].get("state") != pj.AWAITING_HUMAN:
            raise self._no(409, "state", f"job {f['job']} is {f['data'].get('state')}: a plan is approved when the writer waits for the human")
        if a.spawner.busy(f["job"]):
            raise self._no(409, "busy", "the writer is still working on this job")
        q, _ok = self.queue_of(f)
        if q is not None:
            raise self._no(409, "queue", f"queue {q['id']} was already made from this plan")
        other = self.unfinished_on(f["repo"])
        if other:
            raise self._no(409, "queue", f"queue {other} on this repository is not finished")
        cf = self.card_facts(f)
        t = f["turn"]
        card = {"action": "prd_approve", "title": "Approve the plan", "job": f["job"], "repo": f["data"]["inputs"].get("repo_name"),
                "flags": self.flags(cf, None), "request": cf["request"], "summary": cf["summary"], "issues": cf["items"],
                "queue_usd": float(t["max_usd"]), "folder_sha": t["folder_sha"], "commit": str(t.get("commit"))[:12],
                "money": "no money is spent by this step: it makes a PENDING queue; the money is the next step"}
        return card, {"job": f["job"], "dir": f["folder"], "sha": t["folder_sha"]}

    def go_facts(self, job_id):
        """Everything `queue_go` needs from the harness, or a Refusal: the PRD job waits for the human, the one open queue made from exactly this plan, its
        shape, and M8 (every item with calls has two agreeing readings; unreadable examples refuse). Returns the facts and what the human must still give."""
        f = self.facts(job_id)
        if f["data"].get("state") != pj.AWAITING_HUMAN:
            raise self._no(409, "state", f"job {f['job']} is {f['data'].get('state')}: a queue is started for a plan the writer is not rewriting")
        if self.a.spawner.busy(f["job"]):
            raise self._no(409, "busy", "the writer is still working on this job")
        q, ok = self.queue_of(f)
        if q is None:
            raise self._no(409, "queue", "no queue was made from this plan: approve the plan first")
        t = f["turn"]
        try:
            rq.list_sha(q)                                       # the list the CLI will check the sha of: a queue file without its parts is no queue to approve
        except (KeyError, TypeError, ValueError):
            raise self._no(409, "queue", f"queue {q['id']} is damaged (its list cannot be hashed): close it from the terminal") from None
        if q.get("approved"):
            raise self._no(409, "queue", f"queue {q['id']} is already approved")
        if not ok:
            raise self._no(409, "queue", "an issue file of the queue changed since the plan")
        if to_nano(q["max_usd"]) != to_nano(t["max_usd"]) or len(q["items"]) != f["n"]:
            raise self._no(409, "queue", "the queue is not the plan's: its money or its issues differ")
        cf = self.card_facts(f)
        bad = [i["n"] for i in cf["items"] if i["read"] not in ("ok", "tidak_berlaku", "accepted")]
        if bad:
            raise self._no(409, "read", "the numbers of issue " + ", ".join(map(str, bad)) + " have no two agreeing readings (`ok`) yet, or cannot be read; if both readers' concerns are fine with you, accept them in writing in the terminal (argus examples-accept)")
        need_ack = [i["n"] for i in cf["items"] if i["warning"]]
        each = float(q["max_usd"]) / len(q["items"])
        ratio, ratio_text = self.ratio_of(each, cf["cost"].get("reference"))
        need_reason = ratio is None or ratio >= RATIO_REASON
        return f, q, cf, need_ack, need_reason, ratio_text

    def build_go(self, params):
        if set(params) - {"job", "ack", "reason"}:
            raise self._no(400, "form", "starting a queue takes the PRD job, the acknowledgement and a reason, and nothing else")
        f, q, cf, need_ack, need_reason, ratio_text = self.go_facts(params.get("job"))
        ack = params.get("ack")
        if need_ack:
            if ack != ",".join(map(str, need_ack)):
                raise self._no(409, "ack", "issue " + ", ".join(map(str, need_ack)) + " has no example of new behaviour: tick it to accept")
        elif ack:
            raise self._no(400, "form", "nothing to acknowledge")
        reason = params.get("reason")
        if need_reason:
            if reason is None:
                raise self._no(409, "reason", "the cost is " + (ratio_text or "without a reference to compare with") + ": type why you accept it")
            try:
                reason = reason_rule.check(reason, "the reason", "nothing was approved")
            except rj.Refused as e:
                raise self._no(400, "form", str(e)) from None
        elif reason is not None:
            raise self._no(400, "form", "this plan needs no reason")
        card = {"action": "queue_go", "title": "Start the queue (the money)", "job": f["job"], "queue": q["id"], "repo": q["name"],
                "commit": q["base_commit"][:12], "flags": self.flags(cf, ratio_text, need_ack, bool(need_reason)), "request": cf["request"],
                "summary": cf["summary"], "issues": cf["items"], "queue_usd": float(q["max_usd"]), "job_cap_usd": float(q["job_cap_usd"]),
                "list_sha": rq.list_sha(q), "ratio_text": ratio_text, "ack": ack or None,
                "reason": reason if need_reason else None, "money": "approves up to this much for the queue; nothing runs yet"}
        return card, {"job": f["job"], "queue": q["id"], "sha": rq.list_sha(q), "reason": reason if need_reason else None}

    @staticmethod
    def flags(cf, ratio_text, need_ack=(), need_reason=False):
        """The machine's marks, in the words the card shows first (T3 light: a green line must never hide a red one)."""
        out = []
        for i in cf["items"]:
            if i["warning"]:
                out.append(f"issue {i['n']}: no example of the new behaviour; the machine cannot check its numbers")
            if i["read"] == "accepted":
                out.append(f"issue {i['n']}: the readers' concerns about the numbers were accepted in writing, they are not an ok: {i['accepted']}")
            elif i["read"] not in ("ok", "tidak_berlaku"):
                out.append(f"issue {i['n']}: the numbers have no two agreeing readings, or cannot be read")
        if ratio_text:
            out.append("cost: " + ratio_text + (" (a reason is required)" if need_reason else ""))
        elif need_reason:
            out.append("cost: no reference to compare with (a reason is required)")
        return out

    # ---- the state of the buttons, for the page --------------------------------------------------------------------

    def state(self, job_id):
        """{action, why, needs}: the button the plan card offers now, from the same builders the actions use, so the page never offers what prepare refuses
        (including the daily cap). Never raises: the plan card must stay readable whatever the files say."""
        try:
            try:
                self.build_approve({"job": job_id})
                return {"action": "prd_approve", "why": None, "needs": [], "ack_items": []}
            except self.Refusal as e:
                if e.gate not in ("queue", "state", "busy"):
                    return {"action": None, "why": e.why, "needs": [], "ack_items": []}
            f, q, cf, need_ack, need_reason, _ratio = self.go_facts(job_id)
            self.a.check_cap({"action": "queue_go", "queue_usd": float(q["max_usd"])})
            return {"action": "queue_go", "why": None, "needs": (["ack"] if need_ack else []) + (["reason"] if need_reason else []), "ack_items": [int(n) for n in need_ack]}
        except self.Refusal as e:
            return {"action": None, "why": e.why, "needs": [], "ack_items": []}
        except Exception:                                        # a file that does not have the shape: nothing is offered, the card is still shown
            return {"action": None, "why": "the plan's files cannot be read for a button", "needs": [], "ack_items": []}

    # ---- run ---------------------------------------------------------------------------------------------------------

    def run(self, argv):
        try:
            r = subprocess.run(argv, capture_output=True, text=True, timeout=min(PLAN_TIMEOUT, CLI_TIMEOUT), cwd=rj.ROOT, stdin=subprocess.DEVNULL)
        except subprocess.TimeoutExpired:
            return None, ""
        return r.returncode, (r.stdout if r.returncode == 0 else (r.stderr or r.stdout)) or ""

    def execute(self, action, card, rp_):
        a = self.a
        base = [sys.executable, str(ARGUS), "--jobs-dir", str(a.jobs_dir), "--queues-dir", str(a.cards.queues_dir)]
        if action == "prd_approve":
            tail = ["prd", "approve", rp_["dir"], "--sha", rp_["sha"]]
            reason_file = None
        else:
            tail = ["queue", "go", rp_["queue"], "--sha", rp_["sha"], "--via", "ui"]
            reason_file = a.spawner.message_file(rp_["reason"]) if rp_.get("reason") else None
            if reason_file is not None:
                tail += ["--reason-file", str(reason_file)]
        try:
            code, out = self.run(a.with_config(base + tail))
        finally:
            if reason_file is not None:
                reason_file.unlink(missing_ok=True)
        a.last_exit = code if code is not None else "timeout"
        if code is None and action == "queue_go":                 # the CLI may have approved before it was cut: the money counts until a directory says otherwise
            a.pending.append((a.clock(), ("go", rp_["queue"]), float(card["queue_usd"])))
        lines = [ln.strip() for ln in out.splitlines() if ln.strip()]
        if code != 0:
            line = strip_refused(lines[-1] if lines else "")
            raise self.Refusal(409, "cli", (a_scrub(line)[:300]) or "the command failed")
        if action == "prd_approve":
            m = NEW_QUEUE.search(out)
            return {"job": rp_["job"], "queue": m.group(1) if m else None, "done": True}
        a.pending.append((a.clock(), ("go", rp_["queue"]), float(card["queue_usd"])))
        return {"job": rp_["job"], "queue": rp_["queue"], "done": True}

    # ---- exposure of an approved queue (SPEC_CHAT_T4A 4, 10 item 6) ------------------------------------------------

    def exposure(self, now, seen):
        """USD of the queues approved via the UI in the last 24 hours (their max_usd), read from the queue directories; an unreadable queue, or an
        approval via the UI whose time cannot be read, means the exposure is unknown (the caller refuses). Queues older than two days are not opened."""
        total = 0.0
        c = self.a.cards
        qfd = c._queues_fd()
        if qfd is None:
            return 0.0
        try:
            for name in sorted(os.listdir(qfd), reverse=True):
                if not rq.QUEUE_ID.fullmatch(name):
                    continue                                     # no skip by the queue's own age: it may be approved days after it was made
                got = c._queue_json(qfd, name)
                if got is None:
                    raise self._no(503, "cap", f"the daily exposure cannot be computed (queue {name} could not be read)")
                q, dfd = got
                os.close(dfd)
                ap = q.get("approved")
                if isinstance(ap, dict) and ap.get("via") == "ui":
                    try:
                        at = self.a_parse(ap["at"])
                        usd = float(q["max_usd"])
                        if not math.isfinite(usd) or usd <= 0:
                            raise ValueError("money")
                    except (KeyError, TypeError, ValueError):
                        raise self._no(503, "cap", f"the daily exposure cannot be computed (queue {name}: the approval time or the money cannot be read)") from None
                    if at >= now - DAY:
                        total += usd
                        seen.add(("go", name))
        finally:
            os.close(qfd)
        return total

    def a_parse(self, s):
        from router.chat_actions import parse_time
        return parse_time(s)

    def audited(self, now):
        """(queue id, usd, time) of the queues this chat approved in the last 24 hours, from its audit file: the net under the directory count."""
        from router.chat_actions import parse_time
        try:
            with open(self.a.audit_path, "rb") as f:
                f.seek(0, os.SEEK_END)
                f.seek(max(0, f.tell() - AUDIT_NET_BYTES))
                raw = f.read()
        except FileNotFoundError:
            return []
        except OSError:
            raise self._no(503, "cap", "the daily exposure cannot be computed (the audit cannot be read)") from None
        out = []
        for line in raw.decode("utf-8", "replace").splitlines():
            try:
                r = json.loads(line)
                if r.get("action") == "queue_go" and r.get("ok") == "confirm" and rq.QUEUE_ID.fullmatch(str(r.get("queue"))) \
                        and parse_time(r["at"]) >= now - DAY:
                    out.append((r["queue"], float(r["usd"]), parse_time(r["at"])))
            except (ValueError, KeyError, TypeError, AttributeError):
                continue
        return out


def a_scrub(text):
    from router.chat_actions import scrub
    return scrub(text)
