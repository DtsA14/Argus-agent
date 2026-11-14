"""The chat's actions, C2a (docs/reviews/SPEC_CHAT_APP.md, sections 1.3, 3 and 11): the issue writer, in two steps.

  prepare  builds the confirmation card from harness data (repository, commit, environment, caps, the issue text itself) and
           keeps the prepared action in memory under a random token. Nothing is run and nothing is spent.
  confirm  takes the token only. The server rebuilds the card from live data and refuses when it is not the one that was shown
           (the digest differs), when the daily exposure would pass its cap, or when it comes less than MIN_DELAY after prepare.

The CLI does the work (`argus issue new|reply|start|abandon --via ui`), as for the control service on 8711: its job lock, its
state gate and its sha check stay under it. This module holds no key (it passes a key file's path from its environment), runs
no model and keeps its own state and audit directory, not the control service's (11.10, 11.14).
"""
import calendar
import hashlib
import json
import os
import re
import secrets
import time
from pathlib import Path

from router import issue as ri
from router import job as rj
from router import stage_data as sd
from router.control import cli as control_cli
from router.control import reason_problem, strip_refused
from router.control_issues import Spawner, issue_cli, normalize

STATE = Path.home() / ".local" / "state" / "argus-chat"
KEY_ENV = "ARGUS_CHAT_KEY_FILE"
WRITER_KEY_ENV = "ARGUS_CHAT_WRITER_KEY_FILE"
UI_ID = re.compile(r"j[0-9]{8}_[0-9]{6}_[0-9a-f]{4}")
SHA12 = re.compile(r"[0-9a-f]{12}")
ACTIONS = ("issue_new", "issue_reply", "issue_start", "issue_abandon")
TOKEN_TTL = 300                    # 11.3: five minutes, not thirty
MIN_DELAY = 1.0                    # 11.3/11.6: a confirm this soon after its prepare is a script, not a thumb
DAY = 24 * 3600
PENDING_S = 600                    # a confirmed start the job directory does not show yet still counts this long
MAX_PREPARED = 50
DEFAULT_CAP_USD = 2.0
AUDIT_STR = 200                    # a client string is cut to this before it is written to the audit
BODY_MAX = 16 * 1024               # a JSON body of the two POST routes
JOB_JSON_MAX = 4 * 1024 * 1024     # a job.json larger than this is not read


class Refusal(Exception):
    def __init__(self, status, gate, why):
        super().__init__(why)
        self.status, self.gate, self.why = status, gate, why


EXTRA_INVISIBLE = re.compile("[\U000e0000-\U000e007f\u2028\u2029\u00ad\u061c]")     # tag characters, separators, soft hyphen, ALM


def scrub(text):
    """The harness's own text cleaning (stage_data.clean_text: control and invisible characters removed, cut, no key pattern):
    what is shown is what a human can read, or a marker that it was withheld."""
    try:
        return sd.clean_text(EXTRA_INVISIBLE.sub("", text).encode("utf-8"))
    except sd.Excluded as e:
        return f"[withheld by the harness: {e}]"


def parse_time(s):
    return calendar.timegm(time.strptime(s, "%Y-%m-%dT%H:%M:%SZ"))


def strict_json(raw):
    """A JSON object whose keys are all different (json.loads keeps the last of two), else ValueError."""
    def pairs(items):
        keys = [k for k, _ in items]
        if len(keys) != len(set(keys)):
            raise ValueError("a key was sent twice")
        return dict(items)
    d = json.loads(raw.decode("utf-8"), object_pairs_hook=pairs)
    if not isinstance(d, dict):
        raise ValueError("not an object")
    return d


class IssueView:
    """One issue job as read for the chat: its job.json and its last issue text, through directory fds (never a symlink)."""

    def __init__(self, job_id, data, issue_raw):
        self.id, self.data, self.issue_raw = job_id, data, issue_raw

    @property
    def issue_text(self):
        return None if self.issue_raw is None else self.issue_raw.decode("utf-8", "replace")

    @property
    def issue_sha(self):
        return None if self.issue_raw is None else hashlib.sha256(self.issue_raw).hexdigest()

    @property
    def turn(self):
        return len(self.data.get("conversation") or [])


class Actions:
    def __init__(self, jobs_dir, cfg, *, state=STATE, clock=time.time, environ=os.environ, spawner=None, run=None,
                 config_path=None):
        """cfg: the config as a dict, or a function that loads it. A function is called for every prepare and confirm, so the
        card shows what the CLI will read (it reads config.yaml on every run); config_path is passed to the CLI as --config."""
        self.jobs_dir, self._cfg, self.clock, self.environ = Path(jobs_dir), cfg, clock, environ
        self.config_path = config_path
        self.state = Path(state)
        self.spawner = spawner or Spawner(self.state, clock)
        self.run = run or (lambda action, job_id, reason: control_cli(action, job_id, reason, "", self.jobs_dir))
        self.audit_path = self.state / "audit.jsonl"
        self.prepared = {}                         # token -> the prepared action
        self.pending = []                          # (at, ("new"|"start", job id), usd): confirms the job directories may not show yet

    # ---- settings -------------------------------------------------------------------------------------------------

    @property
    def cfg(self):
        try:
            c = self._cfg() if callable(self._cfg) else self._cfg
        except (OSError, ValueError):
            raise Refusal(503, "config", "the config cannot be read") from None
        if not isinstance(c, dict):
            raise Refusal(503, "config", "the config cannot be read")
        return c

    @property
    def writer(self):
        return self.cfg.get("issue_writer") or {}

    def repos(self):
        return self.writer.get("repos") or {}

    def daily_cap(self):
        v = (self.cfg.get("chat") or {}).get("daily_cap_usd", DEFAULT_CAP_USD)
        return float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) and v >= 0 else DEFAULT_CAP_USD

    def key_file(self, writer):
        return (self.environ.get(WRITER_KEY_ENV) if writer else None) or self.environ.get(KEY_ENV) or None

    # ---- audit (11.14): one line per prepare and per confirm, the token and the text never in it --------------------------

    def audit(self, **rec):
        self.state.mkdir(parents=True, exist_ok=True)
        rec = {"at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(self.clock())), **rec}
        with open(self.audit_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, sort_keys=True) + "\n")

    # ---- reading ----------------------------------------------------------------------------------------------------

    def read_issue(self, job_id):
        """The IssueView of an issue job, or None (not a job id, not there, not an issue job, a symlink, too large)."""
        if not UI_ID.fullmatch(job_id or ""):
            return None
        try:
            sfd = os.open(self.jobs_dir, os.O_RDONLY | os.O_DIRECTORY)
        except OSError:
            return None
        try:
            jfd = sd._open_dir(job_id, sfd)
            try:
                data = json.loads(sd._read_at(jfd, "job.json", limit=JOB_JSON_MAX))
                try:
                    raw = sd._read_at(jfd, ri.ISSUE, single=True, limit=sd.TEXT_MAX)
                except FileNotFoundError:
                    raw = None
            finally:
                os.close(jfd)
        except (OSError, ValueError):
            return None
        finally:
            os.close(sfd)
        if not isinstance(data, dict) or data.get("kind") != "issue" or not isinstance(data.get("inputs"), dict):
            return None
        return IssueView(job_id, data, raw)

    def thread(self, job_id):
        """What the chat shows of an issue job: the conversation and the issue, scrubbed, and where the writer is."""
        v = self.read_issue(job_id)
        if v is None:
            return None
        d = v.data
        out = self.spawner.outcome(job_id)
        conv = []
        for m in d.get("conversation") or []:
            if isinstance(m, dict) and isinstance(m.get("text"), str):
                conv.append({"from": "human" if m.get("from") == "human" else "writer", "text": scrub(m["text"]),
                             "questions": [scrub(q) for q in (m.get("questions") or []) if isinstance(q, str)][:10],
                             "clashes": [{"file": scrub(str(c.get("file"))), "line": c.get("line"), "why": scrub(str(c.get("why")))}
                                         for c in (m.get("clashes") or []) if isinstance(c, dict)][:10]})
        issue = None
        if v.issue_text is not None:
            issue = {"text": scrub(v.issue_text), "sha12": v.issue_sha[:12]}
        return {"id": job_id, "state": d.get("state"), "busy": self.spawner.busy(job_id), "turn": v.turn,
                "repo": d["inputs"].get("repo_name"), "conversation": conv, "issue": issue,
                "handoff": (d.get("handoff") or {}).get("job") if UI_ID.fullmatch(str((d.get("handoff") or {}).get("job"))) else None,
                "last_run": None if out is None else {"code": out["code"], "line": scrub(out["line"] or "")}}

    def issues(self):
        out = []
        try:
            names = sorted((n for n in os.listdir(self.jobs_dir) if UI_ID.fullmatch(n)), reverse=True)[:200]
        except OSError:
            return {"issues": []}
        for n in names:
            v = self.read_issue(n)
            if v is None:
                continue
            conv = v.data.get("conversation") or []
            first = next((m.get("text") for m in conv if isinstance(m, dict) and m.get("from") == "human"), "") or ""
            out.append({"id": n, "state": v.data.get("state"), "repo": v.data["inputs"].get("repo_name"),
                        "title": scrub(first.strip().splitlines()[0][:80]) if first.strip() else n})
        return {"issues": out}

    # ---- the card ---------------------------------------------------------------------------------------------------

    def _need_key(self, writer):
        if self.key_file(writer) is None:
            raise Refusal(409, "key", f"{WRITER_KEY_ENV if writer else KEY_ENV} (or {KEY_ENV}) is not set for the service")

    def build(self, action, params):
        """(card, argv builder inputs) for an action, from live data; Refusal when it cannot be run."""
        if action not in ACTIONS:
            raise Refusal(404, "path", "no such action")
        cfg = self.cfg
        w = cfg.get("issue_writer") or {}
        if not w:
            raise Refusal(409, "config", "the config has no issue writer")
        repos = w.get("repos") or {}
        turn_cap = float((w.get("turn") or {}).get("cap_usd") or 0)
        if action == "issue_new":
            repo, text = params.get("repo"), normalize(params.get("message") or "")
            if repo not in repos:
                raise Refusal(400, "form", "that repository is not one the writer reads")
            why = ri.message_problem(cfg, text, first=True)
            if why:
                raise Refusal(400, "form", why)
            self._need_key(True)
            card = {"action": action, "title": "Ask the writer", "repo": repo,
                    "environment": repos[repo].get("environment"), "message": text,
                    "turn_cap_usd": turn_cap, "job_cap_usd": float(w.get("max_usd") or 0)}
            return card, {"repo": repo, "message": text}
        v = self.read_issue(params.get("job"))
        if v is None:
            raise Refusal(404, "path", "no such issue job")
        state, busy = v.data.get("state"), self.spawner.busy(v.id)
        base = {"action": action, "job": v.id, "repo": v.data["inputs"].get("repo_name"), "state": state, "turn": v.turn,
                "sha12": (v.issue_sha or "")[:12]}
        if busy:
            raise Refusal(409, "busy", "the writer is still working on this job")
        if action == "issue_reply":
            text = normalize(params.get("message") or "")
            if state not in ri.REPLYABLE:
                raise Refusal(409, "state", f"job {v.id} is {state}: it cannot take a reply")
            why = ri.message_problem(cfg, text, first=False)
            if why:
                raise Refusal(400, "form", why)
            self._need_key(True)
            return ({**base, "title": "Reply to the writer", "message": text, "turn_cap_usd": turn_cap,
                     "counted": self.created_from_ui_in_window(v)}, {"job": v.id, "message": text})
        if action == "issue_start":
            if state != ri.AWAITING_HUMAN or v.issue_text is None:
                raise Refusal(409, "state", f"job {v.id} is {state}: an issue is started when the writer waits for the human")
            self._need_key(False)
            if scrub(v.issue_text) != v.issue_text:
                raise Refusal(409, "issue", "the issue holds text the card cannot show as it is (a key-like string or invisible "
                                            "characters): read it and start it from the terminal")
            i = v.data["inputs"]
            first = v.issue_text.strip().splitlines()[0] if v.issue_text.strip() else ""
            return ({**base, "title": "Start a code job", "issue_title": scrub(first), "issue_text": scrub(v.issue_text),
                     "commit": str(i.get("commit"))[:12], "environment": i.get("environment"),
                     "job_cap_usd": float(w.get("code_max_usd") or 0)}, {"job": v.id, "sha": v.issue_sha[:12]})
        reason = (params.get("reason") or "").strip(" ")
        why = reason_problem(reason, required=False)
        if why:
            raise Refusal(400, "form", why)
        if state in (rj.ABANDONED, ri.HANDED_OFF, ri.WRITING):
            raise Refusal(409, "state", f"job {v.id} is {state}: it cannot be discarded now")
        return {**base, "title": "Discard the issue", "reason": reason}, {"job": v.id, "reason": reason}

    @staticmethod
    def digest(card):
        return hashlib.sha256(json.dumps(card, sort_keys=True, ensure_ascii=True).encode()).hexdigest()

    # ---- exposure (11.8): the full cap of every job a UI action started, from the moment it was confirmed ---------------

    def exposure(self):
        """USD of exposure in the last 24 hours: the writer jobs created via the UI (their max_usd) and the code jobs their
        starts made via the UI (the code cap), read from the job directories of any service, plus this service's own recent
        confirms the directories do not show yet. A job directory that cannot be read means the exposure is unknown: Refusal."""
        now = self.clock()
        total, seen = 0.0, set()
        try:
            names = sorted((n for n in os.listdir(self.jobs_dir) if UI_ID.fullmatch(n)), reverse=True)
        except OSError:
            names = []
        unknown = Refusal(503, "cap", "the daily exposure cannot be computed (a job could not be read)")
        for n in names:
            try:
                named = calendar.timegm(time.strptime(n[1:16], "%Y%m%d_%H%M%S"))
            except ValueError:
                continue                           # an id shape with an impossible date is no job this harness made
            if named < now - 2 * DAY:
                break                              # job ids sort by time: nothing older can be inside the window
            try:
                sfd = os.open(self.jobs_dir, os.O_RDONLY | os.O_DIRECTORY)
                try:
                    jfd = sd._open_dir(n, sfd)
                    try:
                        data = json.loads(sd._read_at(jfd, "job.json", limit=JOB_JSON_MAX))
                    finally:
                        os.close(jfd)
                finally:
                    os.close(sfd)
            except FileNotFoundError:
                continue
            except (OSError, ValueError):
                raise unknown from None
            if not isinstance(data, dict):
                raise unknown
            if data.get("kind") != "issue":
                continue
            try:
                for entry in data.get("log") or []:
                    if isinstance(entry, dict) and entry.get("what") == "created" and entry.get("via") == "ui" \
                            and parse_time(entry["at"]) >= now - DAY:
                        total += float(data.get("max_usd") or 0)
                        seen.add(("new", n))
                h = data.get("handoff")
                if isinstance(h, dict) and h.get("via") == "ui" and parse_time(h["at"]) >= now - DAY:
                    total += float(self.writer.get("code_max_usd") or 0)
                    seen.add(("start", n))
            except (KeyError, TypeError, ValueError):
                raise unknown from None
        self.pending = [(at, key, usd) for at, key, usd in self.pending if now - at < PENDING_S]
        total += sum(usd for _, key, usd in self.pending if key not in seen)
        return total

    def exposure_of(self, card):
        if card["action"] in ("issue_new", "issue_start"):
            return float(card["job_cap_usd"])
        if card["action"] == "issue_reply" and not card.get("counted"):
            return float(card["turn_cap_usd"])           # a paid turn on a job whose creation the 24 hours do not hold
        return 0.0

    def created_from_ui_in_window(self, v):
        """True when this issue job's own max_usd is already in exposure(): created via the UI in the last 24 hours."""
        try:
            return any(isinstance(e, dict) and e.get("what") == "created" and e.get("via") == "ui"
                       and parse_time(e["at"]) >= self.clock() - DAY for e in v.data.get("log") or [])
        except (KeyError, TypeError, ValueError):
            return False

    def check_cap(self, card):
        extra = self.exposure_of(card)
        if extra:
            used = self.exposure()
            if used + extra > self.daily_cap() + 1e-9:
                raise Refusal(403, "cap", f"the daily cap would be passed (${used:.2f} of ${self.daily_cap():.2f} in use, "
                                          f"this adds ${extra:.2f})")

    # ---- prepare and confirm ----------------------------------------------------------------------------------------

    def prepare(self, action, params):
        """(body, digest): the card and the token, nothing run, nothing spent."""
        card, run_params = self.build(action, params)
        now = self.clock()
        self.prepared = {t: p for t, p in self.prepared.items() if now - p["issued"] <= TOKEN_TTL}
        while len(self.prepared) >= MAX_PREPARED:
            self.prepared.pop(next(iter(self.prepared)))
        self.check_cap(card)                       # 3: refuse at prepare too, not only after the human tapped
        token = secrets.token_urlsafe(32)
        self.prepared[token] = {"action": action, "params": params, "digest": self.digest(card), "issued": now}
        return {"token": token, "card": card, "expires_s": TOKEN_TTL, "min_delay_s": MIN_DELAY,
                "exposure_usd": self.exposure_of(card)}, self.digest(card)

    def confirm(self, token):
        """(action, card, run params, digest) of a confirmed action, or Refusal. A token is spent by the first confirm that is not too soon."""
        now = self.clock()
        p = self.prepared.get(token) if isinstance(token, str) else None
        if p is None or now - p["issued"] > TOKEN_TTL:
            self.prepared.pop(token, None) if isinstance(token, str) else None
            raise Refusal(403, "token", "no such prepared action, or it expired: prepare it again")
        if now - p["issued"] < MIN_DELAY:
            raise Refusal(429, "delay", "confirmed too soon after the card was shown")
        del self.prepared[token]                   # spent: once
        card, run_params = self.build(p["action"], p["params"])
        if self.digest(card) != p["digest"]:
            raise Refusal(409, "card", "what the card showed changed since it was prepared: prepare it again")
        self.check_cap(card)                       # and again now, with what other confirms and services added meanwhile
        return p["action"], card, run_params, self.digest(card)

    def with_config(self, argv):
        """The argv with --config before the subcommand when the chat was started with one (the CLI then reads the same file)."""
        return argv[:2] + ["--config", str(self.config_path)] + argv[2:] if self.config_path else argv

    def execute(self, action, card, rp):
        """Start the confirmed action; returns the body. The CLI is the real gate."""
        a = action
        if a == "issue_abandon":
            code, line = self.run("abandon", rp["job"], rp["reason"] or "discarded from the phone")
            if code != 0:
                raise Refusal(409, "cli", strip_refused(line) or "the command failed")
            return {"job": rp["job"], "done": True}
        key = self.key_file(a in ("issue_new", "issue_reply"))
        c = self.jobs_dir
        if a == "issue_new":
            new_id = rj.new_job_id()
            message = self.spawner.message_file(rp["message"])
            argv = self.with_config(issue_cli(c, key, "new", "--repo", rp["repo"], "--job-id", new_id, "--message-file", str(message)))
            self.spawner.spawn(new_id, argv, message, action="new", text=rp["message"])
            self.pending.append((self.clock(), ("new", new_id), self.exposure_of(card)))
            return {"job": new_id, "started": True}
        if a == "issue_reply":
            message = self.spawner.message_file(rp["message"])
            argv = self.with_config(issue_cli(c, key, "reply", "--message-file", str(message)) + ["--", rp["job"]])
            self.spawner.spawn(rp["job"], argv, message, action="reply", text=rp["message"])
            if self.exposure_of(card):
                self.pending.append((self.clock(), ("reply", rp["job"], self.clock()), self.exposure_of(card)))
            return {"job": rp["job"], "started": True}
        argv = self.with_config(issue_cli(c, key, "start", "--sha", rp["sha"]) + ["--", rp["job"]])
        self.spawner.spawn(rp["job"], argv, None, action="start")
        self.pending.append((self.clock(), ("start", rp["job"]), self.exposure_of(card)))
        return {"job": rp["job"], "started": True}
