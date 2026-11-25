"""The two step buttons of the chat (docs/reviews/SPEC_CHAT_T4B.md, rev 1): `queue_step` (= `argus queue step Q --item N --via ui`: one drafter run for the next item
of a queue the chat itself approved) and `draft_approve` (= `argus approve JOB --sha DRAFTSHA --via ui`: the human approves the draft, the agent starts). The client sends
only the queue id; the item, the job, the sha, the money and every argument are read from the harness here, through directory descriptors, and the card shows them. The CLI
keeps its own gates (sha, check, lock, HEAD, `dr.check`). Apply, reject, abandon and retry are not here.
"""
import hashlib
import json
import os
import stat

from router import issue as ri
from router import job as rj
from router import queue as rq
from router.cards import ISSUE_MAX, UI_ID, _read

DAY = 24 * 3600
AUDIT_NET_BYTES = 1 << 20
ACTIONS = ("queue_step", "draft_approve")


class Steps:
    """The two actions for one Actions (router.chat_actions): `a` gives the cards, the jobs and queues directories, the clock, the spawner, the config and the audit."""

    def __init__(self, a, refusal):
        self.a, self.Refusal = a, refusal

    def _no(self, status, gate, why):
        return self.Refusal(status, gate, why)

    # ---- reading the queue and its next item ------------------------------------------------------------------------

    def facts(self, params):
        """The queue the chat approved, its next item and what waits at it, or a Refusal. kind: "start" (no job yet: `queue_step`) or "approve" (the draft waits: `draft_approve`)."""
        if set(params) - {"queue"}:
            raise self._no(400, "form", "this step takes the queue and nothing else")
        qid = params.get("queue")
        c = self.a.cards
        if not isinstance(qid, str) or not rq.QUEUE_ID.fullmatch(qid):
            raise self._no(404, "path", "no such queue")
        qfd = c._queues_fd()
        if qfd is None:
            raise self._no(404, "path", "no such queue")
        try:
            got = c._queue_json(qfd, qid)
            if got is None:
                raise self._no(404, "path", "no such queue, or it cannot be read")
            q, dfd = got
            try:
                texts = {}
                for item in q["items"]:
                    try:
                        raw = _read(dfd, f"issue-{item['n']}.md", ISSUE_MAX)
                    except OSError:
                        raise self._no(409, "queue", "an issue file of the queue cannot be read") from None
                    if hashlib.sha256(raw).hexdigest() != item["issue_sha256"]:
                        raise self._no(409, "queue", "an issue file of the queue changed since the list was approved")
                    texts[item["n"]] = raw.decode("utf-8", "replace")
            finally:
                os.close(dfd)
        finally:
            os.close(qfd)
        if not c._same_jobs_dir(q):
            raise self._no(409, "queue", "the queue belongs to another jobs directory")
        if q.get("closed"):
            raise self._no(409, "queue", "the queue is closed")
        ap = q.get("approved")
        if not isinstance(ap, dict):
            raise self._no(409, "queue", "the queue is not approved")
        if ap.get("via") != "ui":
            raise self._no(409, "queue", "the queue was not approved from the chat: its steps stay in the terminal (so its money is in the daily cap)")
        try:
            if ap.get("sha") != rq.list_sha(q):
                raise self._no(409, "queue", "the list changed since it was approved")
            at = self.a_parse(ap["at"])
        except (KeyError, TypeError, ValueError):
            raise self._no(409, "queue", "the queue's approval cannot be read") from None
        if not 0 < float(q["job_cap_usd"]) <= ri.CODE_MAX_USD:
            raise self._no(409, "queue", "the queue's job cap is more than the code cap allows")
        state, _nxt, _facts = c._derive(q)
        if state != "WAITING":
            raise self._no(409, "state", f"the queue is {state}: nothing here can be started or approved")
        for item in q["items"]:                                     # the first item that is not applied is the one `derive` stopped at
            job, status = c._item_job(item.get("job")) if item.get("job") else (None, "missing")
            if status == "ok" and job.get("state") == "APPLIED":
                continue
            if status == "missing" or (status == "ok" and not job.get("stages") and job.get("state") in ("NEW", "ABANDONED")):
                return {"q": q, "item": item, "kind": "start", "job": None, "text": texts[item["n"]], "at": at}
            if status == "ok" and job.get("state") == "AWAITING_APPROVAL":
                return {"q": q, "item": item, "kind": "approve", "job": item["job"], "text": texts[item["n"]], "at": at}
            raise self._no(409, "state", f"item {item['n']} is not waiting for a start or a draft approval")
        raise self._no(409, "state", "every item is done")

    def a_parse(self, s):
        from router.chat_actions import parse_time
        return parse_time(s)

    def _busy(self, f):
        sp, qid = self.a.spawner, f["q"]["id"]
        if sp.busy(qid) or (f["job"] and sp.busy(f["job"])):
            raise self._no(409, "busy", "a step of this queue is still running")
        item = f["item"]
        if f["kind"] == "start" and item.get("job"):
            if sp.busy(item["job"]):
                raise self._no(409, "busy", "a step of this queue is still running")

    # ---- the cards ------------------------------------------------------------------------------------------------------

    def build_step(self, params):
        from router.chat_actions import scrub
        f = self.facts(params)
        if f["kind"] != "start":
            raise self._no(409, "state", f"item {f['item']['n']} has a draft waiting: approve it, there is nothing to start")
        self._busy(f)
        a = self.a
        a._need_key(False)
        q, item = f["q"], f["item"]
        cfg = a.cfg
        try:
            from codetask.drafter import drafter_settings
            cap = round(min(float((cfg.get("router") or {}).get("draft_max_usd", 0.75)), float(q["job_cap_usd"])), 6)
            need = drafter_settings(rj.stage_config(cfg, 1e9))["attempt_usd"]
        except (KeyError, TypeError, ValueError):
            raise self._no(409, "config", "the drafter's budget cannot be read from the config") from None
        if cap < need:
            raise self._no(409, "money", f"the job cap leaves ${cap:.4f} for the drafter, one attempt needs ${need:.2f}")
        in_window = f["at"] >= a.clock() - DAY
        retry = bool(item.get("retries")) and bool(item.get("retry_note"))
        flags = ["this item is a retry: the patch readers' findings go to its drafter as data"] if retry else []
        if not in_window:
            flags.append("the queue was approved more than 24 hours ago: this step counts one whole job cap in the daily cap")
        card = {"action": "queue_step", "title": "Start the issue (a drafter run)", "queue": q["id"], "item": item["n"], "job": None, "repo": scrub(str(q["name"])),
                "commit": str(q["base_commit"])[:12], "item_text": scrub(f["text"]), "flags": flags, "job_cap_usd": float(q["job_cap_usd"]),
                "queue_usd": float(q["max_usd"]), "list_sha": rq.list_sha(q), "approved_sha": q["approved"]["sha"], "outside_window": not in_window,
                "retry": retry, "drafter_cap_usd": cap,
                "money": "a drafter writes the tests and the contract; nothing is applied. You still approve the draft yourself. HEAD is checked by the command, not by this card"}
        return card, {"queue": q["id"], "item": item["n"]}

    def build_approve(self, params):
        from router.chat_actions import scrub
        f = self.facts(params)
        if f["kind"] != "approve":
            raise self._no(409, "state", f"item {f['item']['n']} has no draft waiting for approval")
        self._busy(f)
        a = self.a
        a._need_key(False)
        q, item = f["q"], f["item"]
        job_id = f["job"]
        if not UI_ID.fullmatch(job_id):
            raise self._no(409, "state", "the item's job is not one this button can read")
        root = os.path.realpath(a.jobs_dir)
        if os.path.realpath(os.path.join(root, job_id)) != os.path.join(root, job_id):
            raise self._no(409, "state", "the job directory is reached through a link")
        try:
            job = rj.open_job(job_id, a.jobs_dir)
        except rj.Refused as e:
            raise self._no(409, "state", str(e)[:200]) from None
        if job.data.get("state") != rj.AWAITING_APPROVAL:                # stricter than the CLI, which also takes DRAFT_FAILED
            raise self._no(409, "state", f"job {job_id} is {job.data.get('state')}, not AWAITING_APPROVAL")
        cfg = a.cfg
        try:
            st, path = rj._last_draft(job)
            if os.path.realpath(path) != os.path.join(root, job_id, "runs", st["run_id"], "draft.json"):
                raise self._no(409, "folder", "the draft is reached through a link")
            raw = _read_file(path)
            draft = json.loads(raw)
            seen = rj.draft_sha_of(draft)
            if (job.data.get("approval") or {}).get("draft_sha256") == seen:
                raise self._no(409, "state", "this draft was already approved and its agent has run")
            refusal = rj._conflict_refusal(job, draft, "approved")
            if refusal:
                raise self._no(409, "gate", str(refusal)[:300])
            why = rj.environment_changed(job, cfg)
            if why:
                raise self._no(409, "environment", why[:300])
            from codetask import run as ctrun
            c = draft["contract"]
            profile = c.get("budget_profile")
            by_profile = (cfg.get("router") or {}).get("agent_max_usd") or {}
            want = float(by_profile.get(profile, by_profile.get("default", 0.5)))
            cap = round(min(want, rj.left_usd(job)), 6)
            acfg = rj.stage_config(ctrun.apply_profile(cfg, profile) if profile else cfg, cap)
            need = ctrun.settings(acfg)["attempt_usd"]
            if cap < need:
                raise self._no(409, "money", f"${cap:.4f} of the job cap is left for the agent, one attempt needs ${need:.2f}: approving would block the job")
            advisories = [scrub(x)[:400] for x in (*rj.changed_lines(job, draft), *rj.leak_lines(job, draft))]
            valid = [{"id": scrub(str(v.get("id"))), "must_pass": [scrub(str(t)) for t in (v.get("must_pass") or [])][:50]} for v in c["validation"]][:20]
            writable = [scrub(str(w)) for w in c["scope"]["writable"]][:50]
        except self.Refusal:
            raise
        except (OSError, ValueError, KeyError, TypeError, AttributeError, RecursionError, rj.Refused) as e:
            raise self._no(409, "folder", f"the draft cannot be read for this card ({type(e).__name__})") from None
        flags = list(advisories)
        if profile in (None, "default"):
            flags.append("budget profile: default")
        extra = self._summary(draft, path, seen)
        card = {"action": "draft_approve", "title": "Approve the draft (the agent starts)", "queue": q["id"], "item": item["n"], "job": job_id, "repo": scrub(str(q["name"])),
                "item_text": scrub(f["text"]), "draft_sha": seen, "draft_run": st["run_id"], "writable": writable, "validations": valid, "profile": profile,
                "agent_cap_usd": cap, "attempt_usd": float(need), "flags": flags, "list_sha": rq.list_sha(q), "approved_sha": q["approved"]["sha"],
                "retry": bool(item.get("retries")) and bool(item.get("retry_note")), "agent_max_usd_config": want,
                "money": "the agent runs inside the job cap the queue already holds; no new money. Tests and the contract are the drafter's (a model's), shown as it wrote them. "
                         "The command re-checks the draft in the sandbox (`dr.check`) and the repository's HEAD; this card does not",
                **extra}
        return card, {"queue": q["id"], "job": job_id, "sha": seen, "item": item["n"]}

    SUMMARY_MAX = 1_000_000

    def _summary(self, draft, path, seen):
        """What the card adds (SPEC_CHAT_UI1 F17): the paths of the existing tests the draft changes (from the draft itself) and,
        from check_report.json of the same run, the plan, risks, warnings and the writer's unverifiable notes. All model text. Never
        raises: a report that is missing, linked, large, mismatched or hostile gives `summary_note` and the button stays."""
        from router.chat_actions import scrub
        out = {"changed_tests": [], "changed_tests_n": 0}
        try:
            ct = [x.get("path") for x in (draft.get("changed_tests") or []) if isinstance(x, dict) and isinstance(x.get("path"), str)]
            out["changed_tests"], out["changed_tests_n"] = [scrub(x)[:200] for x in ct[:40]], len(ct)
        except (AttributeError, TypeError):
            pass
        try:
            raw = _read_file(os.path.join(os.path.dirname(path), "check_report.json"))
            if len(raw) > self.SUMMARY_MAX:
                raise ValueError("large")
            rep = json.loads(raw)
            if not isinstance(rep, dict) or rep.get("draft_sha256") != seen:
                raise ValueError("report is not this draft's")
            from router import stage_data as sd
            s = sd.draft_summary(draft, rep, {})
            if sd._has_key(s):
                raise ValueError("key-like text")
            cut = lambda xs, n=500: [scrub(str(x))[:n] for x in (xs or [])][:50]
            out["plan"] = {k: cut(s["plan"].get(k), 300) for k in ("files", "steps", "risks")}
            out["warnings"], out["unverifiable"] = cut(s.get("warnings")), cut(s.get("unverifiable"))
            if not (rep.get("baseline") or {}):
                out["baseline_note"] = "no baseline recorded"
        except Exception:                                    # a hostile report must not take the card (and its button) away
            out["summary_note"] = "summary unavailable"
        return out

    # ---- the state of the button, for the queue card ----------------------------------------------------------------------

    def state(self, qid, with_job=False):
        """{action, item, why}: the button the queue card offers now, from the same builders the actions use (and the daily cap), so the page never offers what prepare refuses.
        Never raises. A queue the chat did not approve, a closed or pending one: no button and no sentence (the card already says its state)."""
        try:
            f = self.facts({"queue": qid})
            build, name = (self.build_step, "queue_step") if f["kind"] == "start" else (self.build_approve, "draft_approve")
            card, _ = build({"queue": qid})
            self.a.check_cap(card)
            return {"action": name, "item": card["item"], "why": None, **({"job": card.get("job")} if with_job else {})}
        except self.Refusal as e:
            return {"action": None, "item": None, "why": None if e.gate in ("queue", "path", "form") else e.why}
        except Exception:                                       # a file that does not have the shape: nothing is offered, the card is still shown
            return {"action": None, "item": None, "why": None}

    # ---- run ------------------------------------------------------------------------------------------------------------

    def execute(self, action, card, rp):
        import sys
        from router.control import ARGUS
        a = self.a
        key = a.key_file(False)
        base = [sys.executable, str(ARGUS), "--jobs-dir", str(a.jobs_dir), "--queues-dir", str(a.cards.queues_dir)]
        if action == "queue_step":
            tail = ["queue", "step", rp["queue"], "--item", str(rp["item"]), "--via", "ui", "--key-file", str(key), "--yes"]
        else:
            tail = ["approve", rp["job"], "--sha", rp["sha"], "--via", "ui", "--key-file", str(key), "--yes"]
        a.spawner.spawn(rp["queue"], a.with_config(base + tail), None, action=action)
        return {"queue": rp["queue"], "job": rp.get("job"), "started": True}

    # ---- exposure (SPEC_CHAT_T4B 5, K4 = A): a step of a queue whose approval is outside the 24 hours counts one job cap -------------------------------------

    def exposure_of(self, card):
        if card["action"] == "queue_step" and card.get("outside_window"):
            return float(card["job_cap_usd"])
        return 0.0

    def audited(self, now):
        """The usd of the steps this chat confirmed in the last 24 hours (the net: nothing else records them), from its audit file: the `attempt` line, written before the run starts
        and whose failure stops it (chat.py _confirm), never the `ok` line after it."""
        from router.chat_actions import finite_usd, parse_time
        try:
            with open(self.a.audit_path, "rb") as f:
                f.seek(0, os.SEEK_END)
                f.seek(max(0, f.tell() - AUDIT_NET_BYTES))
                raw = f.read()
        except FileNotFoundError:
            return 0.0
        except OSError:
            raise self._no(503, "cap", "the daily exposure cannot be computed (the audit cannot be read)") from None
        total = 0.0
        for line in raw.decode("utf-8", "replace").splitlines():
            try:
                r = json.loads(line)
                if r.get("action") == "queue_step" and r.get("attempt") == "confirm" and parse_time(r["at"]) >= now - DAY:
                    try:
                        total += finite_usd(r.get("usd") or 0)
                    except ValueError:                             # a confirmed step whose money cannot be read must not be skipped: that undercounts (F25)
                        raise self._no(503, "cap", "the daily exposure cannot be computed (a confirmed queue_step line of the audit has no valid amount)") from None
            except (ValueError, KeyError, TypeError, AttributeError):
                continue
        return total


def _read_file(path, limit=4 * 1024 * 1024):
    """A regular file, never a link, a FIFO or a device, at most `limit` bytes."""
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, "rb") as f:
        if not stat.S_ISREG(os.fstat(f.fileno()).st_mode):
            raise OSError("not a regular file")
        data = f.read(limit + 1)
    if len(data) > limit:
        raise OSError("too large")
    return data.decode("utf-8")
