"""The three chat actions of docs/reviews/SPEC_CHAT_APPLY_REPLY.md (rev 1, section 12 binds): `prd_reply` (= `argus prd reply JOB --message-file F --via ui`), `patch_read_run`
(= `argus patch-read-run JOB --cap-usd C --via ui`) and `code_apply` (= `argus apply JOB --read-sha SHA --reader argus --via ui [--accept-concerns=REASON]`).

The client sends the job id and nothing that picks anything: the message of a reply, the reason of an accepted concern, and for `code_apply` the sha12 it was shown, which is only an
equality check (a patch that changed since the human saw it is a 409), never a selector. The full sha, the repository, the cap, the readers and every option are read from the
harness here, through the directory descriptors of the install card (one read of the patch: what is shown, hashed and applied is one file). The CLI keeps its own gates (apply refuses
a dirty tree, a protected file, a stale reading...), and its refusal is shown as it is; this module does not copy them. The foreman cannot start any of these (`ROUTE_ACTION` lists
research and prd only). Nothing here pushes, opens a pull request, merges or deploys.
"""
import hashlib
import json
import os
import re
import sys
from pathlib import Path
from types import SimpleNamespace

from router import job as rj
from router import prd_job as pj
from router import reason as rreason
from router import stage_data as sd
from router.cards import UI_ID

ACTIONS = ("prd_reply", "patch_read_run", "code_apply")
DAY = 24 * 3600
AUDIT_NET_BYTES = 1 << 20
READS_PER_DAY = 2                                   # SPEC_CHAT_APPLY_REPLY K5: a belt over the job's total cap, which already makes a re-run buy nothing
DEFAULT_READ_CAP_USD = 0.20
READ_CAP_MAX_USD = 2.0                              # `patch_read_run.run` refuses a cap above 2
PATCH_TEXT_MAX = 512 * 1024                         # a patch the page cannot show whole is not applied from here (SPEC_CHAT_APPLY_REPLY 12 F7)
SHA12 = re.compile(r"[0-9a-f]{12}")
SHA64 = re.compile(r"[0-9a-f]{64}")
FINAL_KINDS = ("ok", "nit")
LEDGER_MAX = 4 * 1024 * 1024
GIT_TIMEOUT_S = 5                                   # a hung repository must not stall the single-threaded chat (the CLI has its own, longer one)


class ApplyReply:
    """The three actions for one Actions (router.chat_actions): `a` gives the cards, the jobs and queues directories, the clock, the spawner, the config and the audit."""

    def __init__(self, a, refusal):
        self.a, self.Refusal = a, refusal

    def _no(self, status, gate, why):
        return self.Refusal(status, gate, why)

    # ---- the key of the readers --------------------------------------------------------------------------------------------

    def reader_key(self):
        """ARGUS_CHAT_READER_KEY_FILE, else the code key, else None. Both readers are OpenRouter models, so one OpenRouter key file is enough; the code key is one on this machine
        (the service unit sets it to the OpenRouter key). If it were another provider's, the CLI would refuse the run and the page would say so."""
        from router.chat_actions import KEY_ENV, READER_KEY_ENV
        return self.a.environ.get(READER_KEY_ENV) or self.a.environ.get(KEY_ENV) or None

    def _need_reader_key(self):
        from router.chat_actions import KEY_ENV, READER_KEY_ENV
        if self.reader_key() is None:
            raise self._no(409, "key", f"{READER_KEY_ENV} (or {KEY_ENV}) is not set for the service")

    # ---- prd_reply (F28) --------------------------------------------------------------------------------------------------

    def build_prd_reply(self, params):
        from router.chat_actions import ConfigError, normalize, strip_refused, finite_usd
        a = self.a
        if set(params) != {"job", "message"}:
            raise self._no(400, "form", "a reply to the PRD writer takes the job and the message and nothing else")
        job_id = params["job"]
        got = a._read_data(job_id)
        if got is None or got[0].get("kind") != "prd":
            raise self._no(404, "path", "no such PRD job")
        d, spent = got
        state = d.get("state")
        if state not in pj.REPLYABLE:
            raise self._no(409, "state", f"job {job_id} is {state}: it cannot take a reply")
        if a.spawner.busy(job_id):
            raise self._no(409, "busy", "the writer is still working on this job")
        text = normalize(params["message"])
        cfg = a.cfg
        try:
            why = pj.message_problem(cfg, text, first=False)
            turn_cap = float(pj._settings(cfg)["turn"]["cap_usd"])
        except (rj.Refused, KeyError, TypeError, ValueError, AttributeError, ConfigError):
            raise self._no(409, "config", "the PRD writer's configuration is not complete") from None
        if why:
            raise self._no(400, "form", why)
        a._need_key(True)
        i = d.get("inputs") if isinstance(d.get("inputs"), dict) else {}
        try:
            left = finite_usd(d["max_usd"]) - (0.0 if spent is None else float(spent))
        except (KeyError, TypeError, ValueError):
            raise self._no(503, "cap", "the job's budget cannot be read") from None
        if left + 1e-12 < turn_cap:
            raise self._no(409, "cap", f"${left:.4f} of the job cap is left, less than one turn (${turn_cap:.2f})")
        try:                                                 # the repository's side, as the CLI checks it before any model call: nothing is started then, so nothing is spent
            pj._repo_state(cfg, i["repo_name"], i["commit"], a.cards.queues_dir, a.jobs_dir)
        except rj.Refused as e:
            raise self._no(409, "repo", strip_refused(str(e))) from None
        except Exception:
            raise self._no(409, "repo", "the repository's state cannot be checked now") from None
        counted = a.created_from_ui_in_window(SimpleNamespace(data=d))
        card = {"action": "prd_reply", "title": "Reply to the PRD writer", "job": job_id, "repo": i.get("repo_name"), "state": state, "message": text,
                "turn_cap_usd": turn_cap, "left_usd": round(left, 6), "counted": counted,
                "note": "the writer writes the plan again: the plan shown now is replaced, and an approval of it that waits lapses (its folder changes)",
                **a.runs_code(cfg, i.get("environment"))}
        return card, {"job": job_id, "message": text}

    # ---- the install card, once ---------------------------------------------------------------------------------------------

    def _install(self, job_id):
        if not isinstance(job_id, str) or not UI_ID.fullmatch(job_id):
            raise self._no(404, "path", "no such job")
        card, raw, disk_sha = self.a.approve_code.code_with_patch(job_id)
        if card is None:                                      # None or an exception inside the card is a refusal, never a pass
            raise self._no(404, "path", "no install card for this job, or it cannot be read")
        if card.get("state") != "REVIEW_READY":
            raise self._no(409, "state", f"job {job_id} is {card.get('state')}: only a REVIEW_READY job's patch is read or applied")
        return card, raw, disk_sha

    @staticmethod
    def _second(card):
        pr_ = card.get("patch_read")
        return pr_.get("second") if isinstance(pr_, dict) and isinstance(pr_.get("second"), dict) else None

    def final_readings(self, card):
        """True when `patch-read-run` would read nothing, decided as the run decides (`patch_read_run._run`): `ok` or `nit` stand; a `concerns` stands unless it is the first reader's own
        reading with no second (then only the second is asked, `resume`)."""
        from router import patch_read_run as prr
        k = card.get("patch_read_kind")
        if k in FINAL_KINDS:
            return True
        if k == "concerns":
            pr_ = card.get("patch_read") if isinstance(card.get("patch_read"), dict) else {}
            r = pr_.get("reader") if isinstance(pr_.get("reader"), dict) else {}
            resume = r.get("kind") == "argus" and r.get("id") == prr.reader_id(prr.FIRST) and self._second(card) is None
            return not resume
        return False

    # ---- patch_read_run -----------------------------------------------------------------------------------------------------

    def read_cap(self):
        v = (self.a.cfg.get("chat") or {}).get("patch_read_cap_usd", DEFAULT_READ_CAP_USD)
        try:
            if isinstance(v, bool) or not isinstance(v, (int, float)) or not 0 < float(v) <= READ_CAP_MAX_USD:       # NaN fails the comparison; a huge integer raises OverflowError
                return DEFAULT_READ_CAP_USD
            return float(v)
        except (OverflowError, ValueError):
            return DEFAULT_READ_CAP_USD

    def _billed(self, job_id):
        """The patch readings' ledger of the job, as the run itself counts it (`reconcile_ledger`); (usd, complete). Read through the job's directory descriptor, never through a link."""
        from harness.llm import reconcile_ledger
        from router.patch_read_run import LEDGER
        try:
            sfd = os.open(self.a.jobs_dir, os.O_RDONLY | os.O_DIRECTORY)
            try:
                jfd = sd._open_dir(job_id, sfd)
                try:
                    try:
                        raw = sd._read_at(jfd, LEDGER, limit=LEDGER_MAX)
                    except FileNotFoundError:
                        return 0.0, True
                finally:
                    os.close(jfd)
            finally:
                os.close(sfd)
            totals = reconcile_ledger([json.loads(ln) for ln in raw.decode("utf-8").splitlines() if ln.strip()])[1]
            return float(totals["usd"]), bool(totals["usd_complete"])
        except Exception:
            raise self._no(503, "cap", "the patch readings' ledger cannot be read") from None

    def reads_today(self, job_id, now):
        """How many `patch_read_run` this chat confirmed for the job in the last 24 hours, from its audit file (the `attempt` line, written before the run starts)."""
        from router.chat_actions import parse_time
        n = 0
        for r in self._audit_lines():
            try:
                if r.get("action") == "patch_read_run" and r.get("attempt") == "confirm" and r.get("job") == job_id and parse_time(r["at"]) >= now - DAY:
                    n += 1
            except (KeyError, TypeError, ValueError, AttributeError):
                continue
        return n

    def _audit_lines(self):
        try:
            with open(self.a.audit_path, "rb") as f:
                f.seek(0, os.SEEK_END)
                f.seek(max(0, f.tell() - AUDIT_NET_BYTES))
                raw = f.read()
        except FileNotFoundError:
            return []
        except OSError:
            raise self._no(503, "cap", "the audit cannot be read") from None
        out = []
        for line in raw.decode("utf-8", "replace").splitlines():
            try:
                r = json.loads(line)
            except ValueError:
                continue
            if isinstance(r, dict):
                out.append(r)
        return out

    def build_read(self, params, have=None):
        a = self.a
        if set(params) != {"job"}:
            raise self._no(400, "form", "running the patch readers takes the job and nothing else")
        card, _raw, _disk = have if have is not None else self._install(params["job"])
        job_id = params["job"]
        if self.final_readings(card):
            raise self._no(409, "read", "this patch already has its final readings: nothing is read again")
        if not card.get("patch_sha256"):
            raise self._no(409, "read", "the patch has no sha in its review package")
        if a.spawner.busy(job_id):
            raise self._no(409, "busy", "a run is going on for this job")
        self._need_reader_key()
        if self.reads_today(job_id, a.clock()) >= READS_PER_DAY:
            raise self._no(409, "limit", f"the readers were run {READS_PER_DAY} times for this job in the last 24 hours")
        cap = self.read_cap()
        billed, complete = self._billed(job_id)
        if not complete:
            raise self._no(409, "cap", "the patch readings' ledger is not complete (a call without a price): read from the terminal")
        remaining = cap - billed
        if remaining <= 1e-9:
            raise self._no(409, "cap", f"the cap of this job's patch readings (${cap:.2f}) is spent")
        from router import patch_read_run as prr
        return ({"action": "patch_read_run", "title": "Run the two patch readers", "job": job_id, "sha12": card["patch_sha12"], "patch_sha256": card["patch_sha256"], "sid": card.get("sid"),
                 "readers": [prr.reader_id(prr.FIRST), prr.reader_id(prr.SECOND)], "cap_usd": cap, "billed_usd": round(billed, 6), "remaining_usd": round(remaining, 6),
                 "note": "two models (not a person) read the patch; what they say is not proof that it is right. The run stops by itself when a call would pass the cap, and a reading that "
                         "already stands is not read again"},
                {"job": job_id, "cap": cap})

    # ---- code_apply ---------------------------------------------------------------------------------------------------------

    def _repo_ok(self, job_id):
        """(name, realpath) of the registered repository the job's `inputs.repo` is (a code job records the resolved path, not the name: the registry is searched by path, `~` expanded, both
        sides through realpath, exactly one entry), and never the checkout of Argus."""
        from router.chat_actions import ROOT_REAL
        got = self.a._read_data(job_id, ledgers=False)
        if got is None:
            raise self._no(404, "path", "no such job")
        i = got[0].get("inputs") if isinstance(got[0].get("inputs"), dict) else {}
        try:
            mine = os.path.realpath(str(i.get("repo")))
            regs = self.a.repos()
            names = [n for n, r in regs.items() if isinstance(r, dict) and r.get("path") and os.path.realpath(str(Path(str(r["path"])).expanduser())) == mine] if isinstance(regs, dict) else []
        except (TypeError, ValueError, OSError, RuntimeError):
            raise self._no(409, "repo", "the job's repository cannot be read") from None
        if len(names) != 1:
            raise self._no(409, "repo", "the job's repository is not exactly one of the registered repositories")
        if mine == ROOT_REAL or mine.startswith(ROOT_REAL + os.sep):
            raise self._no(409, "repo", "this repository is Argus itself: apply from the terminal")
        return names[0], mine

    def _git_state(self, repo):
        """(branch, head, main_line) read-only, for the card; (None, None, None) when git cannot answer in a few seconds (the CLI decides; this is information). The main line is the one
        `apply._is_main_line` means: main, master, or the branch origin's HEAD points at."""
        try:
            from router import apply as ra
            branch = ra.run_git(repo, "symbolic-ref", "--short", "-q", "HEAD", ok=(0, 1), timeout=GIT_TIMEOUT_S).decode().strip() or None
            head = ra.run_git(repo, "rev-parse", "HEAD", timeout=GIT_TIMEOUT_S).decode().strip()
            if branch is None:
                return None, head, None
            main = branch in ("main", "master") or ra.run_git(repo, "symbolic-ref", "-q", "refs/remotes/origin/HEAD", ok=(0, 1), timeout=GIT_TIMEOUT_S).decode().strip() == f"refs/remotes/origin/{branch}"
            return branch, head, main
        except Exception:
            return None, None, None

    def patch_text(self, job_id, have=None):
        """(sha256, text, why) of the patch as the install card read it: text only when it is whole, small enough and the scrubber changes nothing in it (SPEC_CHAT_APPLY_REPLY 12 F7).
        have: the (card, bytes, disk sha) already read by the caller, so one request builds the card once."""
        from router.chat_actions import scrub
        card, raw, disk = have if have is not None else self._install(job_id)
        full = card.get("patch_sha256")
        if not (isinstance(full, str) and SHA64.fullmatch(full)) or disk != full or raw is None:
            return full, None, "the review, the provenance and the patch on the disk do not name the same patch"
        if len(raw) > PATCH_TEXT_MAX:
            return full, None, "the patch is too large to read here"
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            return full, None, "the patch is not plain text (binary content): read it from the terminal"
        if scrub(text) != text:
            return full, None, "the patch holds characters the page cannot show as they are (hidden, bidirectional or key-like): read it from the terminal"
        return full, text, None

    def build_apply(self, params, have=None):
        a = self.a
        keys = set(params)
        if not {"job", "sha"} <= keys or keys - {"job", "sha", "reason"}:
            raise self._no(400, "form", "an apply takes the job, the sha12 you were shown and, for a concern, your reason")
        job_id, seen = params["job"], params["sha"]
        have = have if have is not None else self._install(job_id)
        card, _raw, disk = have
        if not isinstance(seen, str) or not SHA12.fullmatch(seen) or card.get("patch_sha12") != seen:
            raise self._no(409, "sha", "the patch changed since you saw it: open the card again")
        full = card.get("patch_sha256")
        for c in card.get("checks") or []:
            if c.get("key") != "f" and c.get("ok") is False:
                raise self._no(409, "check", f"({c.get('key')}) {c.get('label')}: {c.get('why')}")
        kind = card.get("patch_read_kind")
        pr_ = card.get("patch_read") if isinstance(card.get("patch_read"), dict) else {}
        sec = self._second(card)
        readers = [r for r in ((pr_.get("reader") or {}), ((sec or {}).get("reader") or {})) if r]
        if any(r.get("kind") != "argus" for r in readers):
            raise self._no(409, "read", "a patch reading was written by a Claude session: apply from the terminal")
        reason = None
        if kind in FINAL_KINDS:
            if "reason" in params:
                raise self._no(400, "form", "both readers were fine: there is nothing to accept, so no reason")
        elif kind == "concerns" and sec is not None:
            ids = [(r.get("kind"), r.get("id")) for r in readers]
            if len(readers) != 2 or None in [r.get("id") for r in readers] or ids[0] == ids[1]:
                raise self._no(409, "read", "the two readings are not by two different readers")
            if "reason" not in params:
                raise self._no(400, "form", "a reader said concerns: write the reason you accept it (10 to 500 characters)")
            try:
                reason = rreason.check(params["reason"], "the reason")
            except rj.Refused as e:
                from router.chat_actions import strip_refused
                raise self._no(400, "form", strip_refused(str(e))) from None
        else:
            raise self._no(409, "read", "the patch has no two final readings yet: run the two readers first")
        name, repo = self._repo_ok(job_id)
        full2, text, why = self.patch_text(job_id, have)
        if text is None:
            raise self._no(409, "diff", why)
        if full2 != full:
            raise self._no(409, "sha", "the patch changed while the card was made: open the card again")
        if a.spawner.busy(job_id):
            raise self._no(409, "busy", "a run is going on for this job")
        branch, head, main = self._git_state(repo)
        files = [{"path": f.get("path"), "marks": f.get("marks")} for f in (card.get("files") or []) if isinstance(f, dict)]
        out = {"action": "code_apply", "title": "Put the patch into the repository", "job": job_id, "sha12": seen, "repo": name, "repo_realpath_sha256": hashlib.sha256(repo.encode()).hexdigest(), "branch": branch, "head": head,
               "target_branch": (f"argus/{job_id}" if main else branch if branch else None), "detached_note": None if branch else "the repository is not on a branch (or git did not answer): the command refuses a detached HEAD",
               "sid": card.get("sid"), "patch_sha256": full, "patch_read_kind": kind, "checks": [{"key": c.get("key"), "ok": c.get("ok")} for c in card.get("checks") or [] if isinstance(c, dict)],
               "files": files, "scope_marks": card.get("scope_marks"), "patch_read": pr_, "patch_read_label": card.get("patch_read_label"),
               "declaration": f"I have read the patch {seen}. This is a statement, not a proof that it was read",
               "note": "one commit in the repository on this machine; not pushed, not deployed. The command checks the rest (clean tree, protected files, HEAD, the readings) and says why when it refuses",
               **({"accepted_concerns": True, "reason": reason} if reason else {})}
        return out, {"job": job_id, "sha": full, "reason": reason}

    # ---- the button the install card offers, from the same builders (so the page never offers what prepare refuses) -------------

    def state(self, job_id):
        """{action, why}: the button the install card offers now. Never raises. The card is built once and handed to the builders."""
        try:
            have = self._install(job_id)
            card = have[0]
            if not self.final_readings(card):
                self.build_read({"job": job_id}, have)
                return {"action": "patch_read_run", "why": None}
            k = card.get("patch_read_kind")
            self.build_apply({"job": job_id, "sha": card["patch_sha12"], **({} if k in FINAL_KINDS else {"reason": "x" * 10})}, have)
            return {"action": "code_apply", "why": None, "needs_reason": k not in FINAL_KINDS}
        except self.Refusal as e:
            return {"action": None, "why": e.why if e.gate in ("cap", "limit", "key", "busy", "check", "read", "diff", "repo") else None}
        except Exception:
            return {"action": None, "why": None}

    # ---- run -----------------------------------------------------------------------------------------------------------------

    def execute(self, action, card, rp):
        from router.chat_actions import prd_cli
        a = self.a
        base = [sys.executable, str(rj.ROOT / "scripts" / "argus.py"), "--jobs-dir", str(a.jobs_dir), "--queues-dir", str(a.cards.queues_dir)]
        if action == "prd_reply":
            key = a.key_file(True)
            message = a.spawner.message_file(rp["message"])
            argv = a.with_config(prd_cli(a.jobs_dir, a.cards.queues_dir, key, "reply", "--message-file", str(message)) + ["--", rp["job"]])
            a.spawner.spawn(rp["job"], argv, message, action="prd_reply", text=rp["message"])
        elif action == "patch_read_run":
            argv = a.with_config(base + ["patch-read-run", "--cap-usd", repr(float(rp["cap"])), "--via", "ui", "--key-file", str(self.reader_key()), "--yes", "--", rp["job"]])
            a.spawner.spawn(rp["job"], argv, None, action="patch_read_run")
        else:
            tail = ["apply", "--read-sha", rp["sha"], "--reader", "argus", "--via", "ui"] + ([f"--accept-concerns={rp['reason']}"] if rp.get("reason") else []) + ["--", rp["job"]]
            a.spawner.spawn(rp["job"], a.with_config(base + tail), None, action="code_apply")
        return {"job": rp["job"], "started": True}

    # ---- exposure (SPEC_CHAT_APPLY_REPLY 12 F3): the money these two actions can spend, counted from the audit, not from a list that forgets after 10 minutes ---------------

    @staticmethod
    def exposure_of(card):
        if card["action"] == "patch_read_run":
            return float(card["remaining_usd"])
        if card["action"] == "prd_reply" and not card.get("counted"):
            return float(card["turn_cap_usd"])
        return 0.0

    def audited(self, now):
        """The usd of the replies and readings this chat confirmed in the last 24 hours: the `attempt` line, written before the run starts and whose failure stops it (chat.py _confirm).
        Only the last 1 MiB of the audit file is read."""
        from router.chat_actions import finite_usd, parse_time
        total = 0.0
        for r in self._audit_lines():
            try:
                if r.get("action") in ("prd_reply", "patch_read_run") and r.get("attempt") == "confirm":
                    if parse_time(r["at"]) >= now - DAY:
                        total += finite_usd(r.get("usd") or 0)
            except (KeyError, TypeError, AttributeError):
                continue
            except ValueError:                                   # a confirmed line whose time or money cannot be read must not be skipped: that undercounts
                raise self._no(503, "cap", "the daily exposure cannot be computed (a confirmed reply or reading line of the audit has no valid time or amount)") from None
        return total
