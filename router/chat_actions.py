"""The chat's actions (docs/reviews/SPEC_CHAT_APP.md, sections 1.3, 3, 11, 12, 13; SPEC_CHAT_MANAGER 13): the issue writer, a PRD job typed by the human, research, and the reject or abandon of a job, in two steps.

  prepare  builds the confirmation card from harness data (repository, commit, environment, caps, the issue text itself) and
           keeps the prepared action in memory under a random token. Nothing is run and nothing is spent.
  confirm  takes the token only. The server rebuilds the card from live data and refuses when it is not the one that was shown
           (the digest differs), when the daily exposure would pass its cap, or when it comes less than MIN_DELAY after prepare.

The CLI does the work (`argus issue new|reply|start|abandon`, `argus prd new`, `argus research`, each with --via ui; `argus prd approve` and
`argus queue go` through router/chat_plan.py, which read the folder, the queue and the money themselves), as for the control service on 8711: its job lock, its
state gate and its sha check stay under it. This module holds no key (it passes a key file's path from its environment), runs
no model and keeps its own state and audit directory, not the control service's (11.10, 11.14).
"""
import calendar
import hashlib
import json
import os
import re
import secrets
import sys
import time
import unicodedata
from pathlib import Path

from router import example_gate as eg
from router import issue as ri
from router import queue as rq
from router.approve_cards import Approve
from router.approve_code import Install
from router.cards import Cards
from codetask.issue_writer import has_runner, text_problem
from harness.events import parse_lines
from models.registry import ConfigError
from research.stages import QUESTION_MAX, QUESTION_MIN
from router import job as rj
from router import prd_job as pj
from router.chat_plan import Plan
from router.chat_t4b import Steps
from router import research as rr
from router import stage_data as sd
from router.control import cli as control_cli
from router.control import ABANDON_DEFAULT, NOT_ABANDONABLE, REJECTABLE, Unreadable, allowed, draft_sha12, reason_problem, strip_refused
from router.control_issues import Spawner, issue_cli, normalize

STATE = Path.home() / ".local" / "state" / "argus-chat"
KEY_ENV = "ARGUS_CHAT_KEY_FILE"
WRITER_KEY_ENV = "ARGUS_CHAT_WRITER_KEY_FILE"
RESEARCH_KEY_ENV = "ARGUS_CHAT_RESEARCH_KEY_FILE"   # research uses DeepSeek's own search and fetch API: its own key, when the code key is another provider's
UI_ID = re.compile(r"j[0-9]{8}_[0-9]{6}_[0-9a-f]{4}")
SHA12 = re.compile(r"[0-9a-f]{12}")
ACTIONS = ("issue_new", "issue_reply", "issue_start", "issue_abandon", "research_new", "prd_new", "prd_approve", "queue_go", "queue_step", "draft_approve", "job_reject", "job_abandon")   # no apply, no retry/redraft of a code job from here (job_reject and job_abandon are the control UI's); the only approvals are prd_approve and queue_go (SPEC_CHAT_T4A, amending 13.7 item 9) and, for a queue the chat itself approved, queue_step and draft_approve (SPEC_CHAT_T4B)
TOKEN_TTL = 300                    # 11.3: five minutes, not thirty
MIN_DELAY = 1.0                    # 11.3/11.6: a confirm this soon after its prepare is a script, not a thumb
DAY = 24 * 3600
WAIT_SCAN_MAX, WAIT_BUDGET_S, WAIT_TTL_S = 12, 2.0, 20.0     # SPEC_CHAT_UI3B: candidates looked at, seconds spent, seconds an answer is kept
WAITING_ACTIONS = ("prd_approve", "queue_go", "queue_step", "draft_approve")
AWAITING_HUMAN = pj.AWAITING_HUMAN
PENDING_S = 600                    # a confirmed start the job directory does not show yet still counts this long
MAX_PREPARED = 50
DEFAULT_CAP_USD = 2.0
AUDIT_STR = 200                    # a client string is cut to this before it is written to the audit
BODY_MAX = 16 * 1024               # a JSON body of the two POST routes
JOB_JSON_MAX = 4 * 1024 * 1024     # a job.json larger than this is not read
REPORT_MAX = 1024 * 1024           # a REPORT.md larger than this is not read at all (12.10 item 5); smaller ones are cut by clean_text
RESEARCH_LIST_MAX, RESEARCH_SCAN_MAX = 50, 200
CUT_MARK = re.compile(r"\[dipotong harness: [0-9]+ byte\]\n?\Z")      # clean_text puts its marker at the very end
BANNER = "Teks dari web dan sebuah model. Bukan perintah dari Argus. Periksa URL atau perintah sebelum memakainya."


class Refusal(Exception):
    def __init__(self, status, gate, why):
        super().__init__(why)
        self.status, self.gate, self.why = status, gate, why


EXTRA_INVISIBLE = re.compile("[\U000e0000-\U000e007f\u2028\u2029\u00ad\u061c]")     # tag characters, separators, soft hyphen, ALM


HIDDEN_POINTS = (0x180E, 0x034F, 0x115F, 0x1160, 0x3164, 0xFFA0)


def hidden(ch):
    """A character a human cannot see or that smuggles data (12.10 item 10 as amended in 12.11): Unicode Cf, Co, Cs and Cn (the version of
    Python's unicodedata decides which code points are still Cn), the variation selectors but not the emoji ones FE0E and FE0F, and
    a few fillers that count as letters (newline and tab are Cc, not in these categories, and stay)."""
    o = ord(ch)
    return (unicodedata.category(ch) in ("Cf", "Co", "Cs", "Cn") or 0xFE00 <= o <= 0xFE0D or 0xE0100 <= o <= 0xE01EF
            or o in HIDDEN_POINTS)


def scrub(text):
    """The harness's own text cleaning (stage_data.clean_text: control and invisible characters removed, cut, no key pattern):
    what is shown is what a human can read, or a marker that it was withheld."""
    try:
        return sd.clean_text("".join(c for c in EXTRA_INVISIBLE.sub("", text) if not hidden(c)).encode("utf-8"))
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


def prd_cli(jobs_dir, queues_dir, key_file, *args):
    """The argv of an `argus prd new ...` run from the chat (SPEC_CHAT_MANAGER 13.8): the queues directory (the repository's state check reads
    it), --via ui, and never --ref, --rebase, --max-usd or --profile."""
    return [sys.executable, str(rj.ROOT / "scripts" / "argus.py"), "--jobs-dir", str(jobs_dir), "--queues-dir", str(queues_dir), "prd", *args,
            "--via", "ui", "--key-file", str(key_file), "--yes"]


def research_cli(jobs_dir, key_file, *args):
    """The argv of an `argus research ...` run: no --max-usd and no --profile (the config's), from the chat."""
    return [sys.executable, str(rj.ROOT / "scripts" / "argus.py"), "--jobs-dir", str(jobs_dir), "research", *args,
            "--via", "ui", "--key-file", str(key_file), "--yes"]


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
                 config_path=None, queues_dir=None):
        """cfg: the config as a dict, or a function that loads it. A function is called for every prepare and confirm, so the
        card shows what the CLI will read (it reads config.yaml on every run); config_path is passed to the CLI as --config."""
        self.jobs_dir, self._cfg, self.clock, self.environ = Path(jobs_dir), cfg, clock, environ
        self.cards = Cards(self.jobs_dir, Path(queues_dir) if queues_dir else rq.QUEUES, scrub)     # SPEC_CHAT_CARDS: read only
        self.approve = Approve(self.cards)                                                       # SPEC_KARTU_SETUJU: the plan card, read only
        self.approve_code = Install(self.approve)                                                # 5b: the install card, read only
        self.config_path = config_path
        self.plans = Plan(self, Refusal)                                                          # SPEC_CHAT_T4A: prd_approve and queue_go
        self.steps = Steps(self, Refusal)                                                         # SPEC_CHAT_T4B: queue_step and draft_approve
        self.state = Path(state)
        self.spawner = spawner or Spawner(self.state, clock)
        self.run = run or (lambda action, job_id, reason, sha="": control_cli(action, job_id, reason, sha, self.jobs_dir))
        self.last_exit = None                      # the exit code of the last CLI run of a job decision, for the audit line
        self.audit_path = self.state / "audit.jsonl"
        self._exposure_once = None                 # SPEC_CHAT_UI3B: set only inside waiting(): the exposure computed once for that request
        self._waiting_cache = None                 # (monotonic time, answer): the list of what waits, for WAIT_TTL_S
        self._cap_cache = None                     # the same, for cap_status()
        self.mono = time.monotonic
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

    def key_file(self, writer, research=False):
        """The key file a paid action is given: the writer's turns WRITER_KEY_ENV, research RESEARCH_KEY_ENV, each when set, else KEY_ENV (the code key)."""
        first = WRITER_KEY_ENV if writer else RESEARCH_KEY_ENV if research else None
        return (self.environ.get(first) if first else None) or self.environ.get(KEY_ENV) or None

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
        examples = self.cards.issue_examples(d, v.issue_raw)
        if v.issue_text is not None:          # with the examples on screen the block is not shown twice (SPEC_CHAT_CARDS 4.2): only when they show
            shown = eg.without_block(v.issue_text) if examples and examples.get("calls") else v.issue_text
            issue = {"text": scrub(shown), "sha12": v.issue_sha[:12]}
        return {"id": job_id, "state": d.get("state"), "busy": self.spawner.busy(job_id), "turn": v.turn,
                "repo": d["inputs"].get("repo_name"), "conversation": conv, "issue": issue,
                "examples": examples,
                "handoff": (d.get("handoff") or {}).get("job") if UI_ID.fullmatch(str((d.get("handoff") or {}).get("job"))) else None,
                "last_run": None if out is None else {"code": out["code"], "line": scrub(out["line"] or "")}}

    # ---- research jobs (12.4): read through directory fds, shown as text ----------------------------------------------------

    def _read_research(self, job_id, with_report):
        """(job.json dict, report) of a research job, or None. report: bytes, None (no REPORT.md) or a reason string (too large, not a
        regular file with one name, or unreadable). Everything is opened one name at a time in an already opened directory."""
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
                report = None
                if with_report and isinstance(data, dict) and data.get("kind") == "research":
                    try:
                        report = sd._read_at(jfd, "REPORT.md", single=True, limit=REPORT_MAX)
                    except FileNotFoundError:
                        report = None
                    except OSError:
                        report = "terlalu besar atau bukan berkas biasa: baca di terminal"
                spent = self._spent(jfd, job_id, data) if with_report and isinstance(data, dict) else None
            finally:
                os.close(jfd)
        except (OSError, ValueError):
            return None
        finally:
            os.close(sfd)
        if not isinstance(data, dict) or data.get("kind") != "research" or not isinstance(data.get("inputs"), dict):
            return None
        return data, report, spent

    @staticmethod
    def _spent(jfd, job_id, data):
        """USD the job's runs have spent, from their ledgers read by fd (no symlink, each at most JOB_JSON_MAX), or None when any of
        them cannot be read: an unknown cost is shown as unknown, never as 0."""
        stages = data.get("stages")
        if not isinstance(stages, dict) or not stages:
            return 0.0
        try:
            rfd = sd._open_dir("runs", jfd)
        except OSError:
            return None
        try:
            total = 0
            for name in sorted(stages):
                if not isinstance(name, str) or not sd.STAGE.match(name):
                    return None
                try:
                    run = sd._open_dir(f"{job_id}-{name}", rfd)
                except FileNotFoundError:
                    continue
                except OSError:
                    return None
                try:
                    try:
                        text = sd._read_at(run, "events.jsonl", limit=JOB_JSON_MAX).decode("utf-8", "replace")
                    except FileNotFoundError:
                        continue
                    total += sd.ledger_nano(parse_lines(text))
                finally:
                    os.close(run)
            return total / 1e9
        except (OSError, ValueError, KeyError, TypeError):
            return None
        finally:
            os.close(rfd)

    def research_thread(self, job_id):
        """What the chat shows of a research job (12.4, 12.10): state, cost, whether e1 checked it (from job.json), the report as
        scrubbed text under the harness's own banner. Before the job exists: starting or refused, from the spawner."""
        got = self._read_research(job_id, True)
        if got is None:
            if not UI_ID.fullmatch(job_id or "") or os.path.lexists(self.jobs_dir / job_id):
                return None                                # a directory that is not a readable research job is no "starting"
            if self.spawner.busy(job_id):
                return {"id": job_id, "state": "starting", "busy": True}
            out = self.spawner.outcome(job_id)
            if out is None:
                return None
            return {"id": job_id, "state": "refused", "busy": False, "line": scrub(out["line"] or "")}
        d, raw, spent = got
        state = d.get("state")
        busy = self.spawner.busy(job_id)
        e1 = (d.get("stages") or {}).get("e1") if isinstance(d.get("stages"), dict) else None
        e1 = e1 if isinstance(e1, dict) else {}
        counts = e1.get("counts") if isinstance(e1.get("counts"), dict) else {}
        report = None
        if isinstance(raw, str):
            report = {"withheld": raw}
        elif raw is not None:
            try:
                text = scrub(raw.decode("utf-8"))
            except UnicodeDecodeError:
                text = "[withheld by the harness: not valid UTF-8]"
            if text.startswith("[withheld by the harness"):
                report = {"withheld": f"{text} Baca di terminal: argus status {job_id}"}
            else:
                report = {"text": text, "cut": bool(CUT_MARK.search(text))}
        checked = state == rr.REPORT_READY and e1.get("status") == "CHECKED"
        q = d["inputs"].get("question")
        out = self.spawner.outcome(job_id)
        return {"id": job_id, "state": state, "busy": busy, "question": scrub(q)[:QUESTION_MAX] if isinstance(q, str) else "",
                "cap_usd": d.get("max_usd") if isinstance(d.get("max_usd"), (int, float)) and not isinstance(d.get("max_usd"), bool) else None, "spent_usd": spent,
                "checked": checked, "counts": {k: v for k, v in counts.items() if isinstance(v, int) and not isinstance(v, bool)},
                "stalled": state in rr.RUNNING and not busy, "banner": BANNER, "report": report,
                "last_run": None if out is None else {"code": out["code"], "line": scrub(out["line"] or "")}}

    def research_list(self):
        out, scanned = [], 0
        try:
            names = sorted((n for n in os.listdir(self.jobs_dir) if UI_ID.fullmatch(n)), reverse=True)
        except OSError:
            return {"research": []}
        for n in names:
            if scanned >= RESEARCH_SCAN_MAX or len(out) >= RESEARCH_LIST_MAX:
                break
            scanned += 1
            got = self._read_research(n, False)
            if got is None:
                continue
            d = got[0]
            q = d["inputs"].get("question")
            first = scrub(q.strip().splitlines()[0][:80]) if isinstance(q, str) and q.strip() else n
            out.append({"id": n, "state": d.get("state"), "title": first,
                        "busy": self.spawner.busy(n)})
        return {"research": out}

    def _repo_names(self):
        try:
            return sorted(str(r) for r in ((self.cfg.get("issue_writer") or {}).get("repos") or {}))
        except Refusal:
            return []                                  # an unreadable config offers no repository, it does not break the page

    def issues(self):
        out = []
        try:
            names = sorted((n for n in os.listdir(self.jobs_dir) if UI_ID.fullmatch(n)), reverse=True)[:200]
        except OSError:
            return {"issues": [], "repos": []}
        for n in names:
            v = self.read_issue(n)
            if v is None:
                continue
            conv = v.data.get("conversation") or []
            first = next((m.get("text") for m in conv if isinstance(m, dict) and m.get("from") == "human"), "") or ""
            out.append({"id": n, "state": v.data.get("state"), "repo": v.data["inputs"].get("repo_name"),
                        "title": scrub(first.strip().splitlines()[0][:80]) if first.strip() else n})
        return {"issues": out, "repos": self._repo_names()}

    # ---- the card ---------------------------------------------------------------------------------------------------

    def _need_key(self, writer, research=False):
        if self.key_file(writer, research) is None:
            first = WRITER_KEY_ENV if writer else RESEARCH_KEY_ENV if research else None
            raise Refusal(409, "key", f"{first} (or {KEY_ENV}) is not set for the service" if first else f"{KEY_ENV} is not set for the service")

    @staticmethod
    def runs_code(cfg, environment):
        """SPEC_EXAMPLE_GATE 4(1), D5: the writer's turn is no longer read-only where the environment runs examples; the card says so."""
        if not has_runner(cfg, environment):
            return {}
        return {"runs_code": "kode contoh buatan model dijalankan di sandbox (tanpa jaringan, repo hanya-baca); giliran ini tidak lagi hanya-baca"}

    def build(self, action, params):
        """(card, argv builder inputs) for an action, from live data; Refusal when it cannot be run."""
        if action not in ACTIONS:
            raise Refusal(404, "path", "no such action")
        if action in ("job_reject", "job_abandon"):
            return self.build_job(action, params)                # no config, no exposure: a broken config.yaml must not stop a reject (13.7 item 5)
        cfg = self.cfg
        if action == "research_new":
            return self.build_research(cfg, params)
        if action == "prd_new":
            return self.build_prd(cfg, params)
        if action == "prd_approve":
            return self.plans.build_approve(params)
        if action == "queue_go":
            return self.plans.build_go(params)
        if action == "queue_step":
            return self.steps.build_step(params)
        if action == "draft_approve":
            return self.steps.build_approve(params)
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
                    "turn_cap_usd": turn_cap, "job_cap_usd": float(w.get("max_usd") or 0),
                    **self.runs_code(cfg, repos[repo].get("environment"))}
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
                     "counted": self.created_from_ui_in_window(v), **self.runs_code(cfg, v.data["inputs"].get("environment"))},
                    {"job": v.id, "message": text})
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

    # ---- reject and abandon of a job (13): the control service's rules, in the chat's two steps ----------------------------------

    @staticmethod
    def _stage_usd(data):
        """The money a job's stages record in job.json, with no ledger read (the list's cost, 13.7 item 9); None when it is not readable."""
        stages = data.get("stages")
        if not isinstance(stages, dict):
            return None
        total = 0.0
        for st in stages.values():
            u = st.get("usd") if isinstance(st, dict) else None
            if isinstance(u, (int, float)) and not isinstance(u, bool):
                total += u
        return total

    def _read_data(self, job_id, ledgers=True):
        """(job.json dict, spent USD or None) of any job, through directory fds, or None (not an id, not there, not an object).
        ledgers=False: the cost is the stages' own usd of job.json and no ledger is opened."""
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
                spent = (self._spent(jfd, job_id, data) if ledgers else self._stage_usd(data)) if isinstance(data, dict) else None
            finally:
                os.close(jfd)
        except (OSError, ValueError):
            return None
        finally:
            os.close(sfd)
        return (data, spent) if isinstance(data, dict) else None

    RUN_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,80}")

    def _sha(self, job_id, data=None):
        """The sha12 of the job's last draft, "" when it has none, read through directory fds (13.7 item 9: no symlink at any step). Anything
        that goes wrong reading it is a refusal, never "no draft". Same pick and same hash as the control service's draft_sha12."""
        bad = Refusal(409, "draft", "the draft cannot be read")
        try:
            if data is None:
                got = self._read_data(job_id, ledgers=False)
                if got is None:
                    raise bad
                data = got[0]
            drafts = [st for st in data["stages"].values() if st["kind"] == "draft" and st.get("status") == "DRAFTED"]
            if not drafts:
                return ""
            run = drafts[-1]["run_id"]
            if not isinstance(run, str) or not self.RUN_NAME.fullmatch(run):
                raise bad
            sfd = os.open(self.jobs_dir, os.O_RDONLY | os.O_DIRECTORY)
            try:
                jfd = sd._open_dir(job_id, sfd)
                try:
                    rfd = sd._open_dir("runs", jfd)
                    try:
                        dfd = sd._open_dir(run, rfd)
                        try:
                            raw = sd._read_at(dfd, "draft.json", limit=JOB_JSON_MAX)
                        finally:
                            os.close(dfd)
                    finally:
                        os.close(rfd)
                finally:
                    os.close(jfd)
            finally:
                os.close(sfd)
            return rj.draft_sha_of(json.loads(raw))[:12]
        except Refusal:
            raise
        except Exception:
            raise bad from None

    def build_job(self, action, params):
        if set(params) - {"job", "sha", "reason"}:
            raise Refusal(400, "form", "a decision takes the job, the draft sha and the reason")
        job_id, sha = params.get("job"), params.get("sha")
        if not isinstance(job_id, str) or not UI_ID.fullmatch(job_id):
            raise Refusal(404, "path", "no such job")
        if not isinstance(sha, str) or not (sha == "" or SHA12.fullmatch(sha)):
            raise Refusal(400, "form", "the draft sha must be given: 12 hex characters, or empty when the card showed none")
        got = self._read_data(job_id)
        if got is None:
            raise Refusal(404, "path", "no such job")
        data, spent = got
        kind, state = data.get("kind"), data.get("state")
        if kind == "issue":
            raise Refusal(409, "kind", "an issue job is decided on the issue page")
        verb = "reject" if action == "job_reject" else "abandon"
        if verb not in allowed(state):
            raise Refusal(409, "state", f"job {job_id} is {state}: it cannot be {verb}ed now")
        if self.spawner.busy(job_id):
            raise Refusal(409, "busy", "a run of this service is still working on this job")
        live = self._sha(job_id, data)
        if sha != live:
            raise Refusal(409, "draft", "the draft changed since you read it: open the job again")
        reason = (params.get("reason") or "").strip(" ")
        why = reason_problem(reason, required=verb == "reject")
        if why:
            raise Refusal(400, "form", why)
        title = self._title(data)
        cap = data.get("max_usd")
        card = {"action": action, "title": "Reject the draft" if verb == "reject" else "Abandon the job", "job": job_id,
                "kind": kind if isinstance(kind, str) else None, "state": state, "sha12": live or None,
                "job_title": scrub(title) if isinstance(title, str) else None, "reason": reason,
                "spent_usd": None if spent is None else round(spent, 2),
                "cap_usd": cap if isinstance(cap, (int, float)) and not isinstance(cap, bool) else None}
        return card, {"job": job_id, "sha": live, "reason": reason, "verb": verb}

    @staticmethod
    def _title(data):
        try:
            return sd.job_title(data) if isinstance(data.get("kind"), str) else None
        except Exception:
            return None                                   # a title is a convenience: a malformed record must not break the list

    def decision_row(self, job_id, data, spent):
        state = data.get("state")
        try:
            sha, why = self._sha(job_id, data), None
        except Refusal as r:
            sha, why = "", r.why
        title = self._title(data)
        cap = data.get("max_usd")
        return {"id": job_id, "kind": data.get("kind") if isinstance(data.get("kind"), str) else None, "state": state,
                "title": scrub(title) if isinstance(title, str) else None, "sha12": sha or None, "draft_problem": why,
                "spent_usd": spent, "busy": self.spawner.busy(job_id),
                "cap_usd": cap if isinstance(cap, (int, float)) and not isinstance(cap, bool) else None,
                "allowed": [] if why else allowed(state)}

    def decisions(self):
        """Jobs waiting for a decision (state in REJECTABLE, any kind): at most 200 directories looked at, 50 rows (13.7 item 9), no ledger
        opened; a record that cannot be shown is counted in `skipped`, it never breaks the list."""
        rows, scanned, skipped = [], 0, 0
        try:
            names = sorted((n for n in os.listdir(self.jobs_dir) if UI_ID.fullmatch(n)), reverse=True)
        except OSError:
            return {"decisions": [], "capped": False, "skipped": 0}
        for n in names:
            if scanned >= RESEARCH_SCAN_MAX or len(rows) >= RESEARCH_LIST_MAX:
                return {"decisions": rows, "capped": True, "skipped": skipped}
            scanned += 1
            got = self._read_data(n, ledgers=False)
            try:
                if got is not None and got[0].get("state") in REJECTABLE and got[0].get("kind") != "issue":
                    rows.append(self.decision_row(n, *got))
            except Exception:
                skipped += 1
        return {"decisions": rows, "capped": False, "skipped": skipped}

    # ---- the daily cap, for the Cost tab (SPEC_CHAT_UI3C) -----------------------------------------------------------------------------

    def cap_status(self):
        """{cap_usd, booked_usd, unknown}: the daily cap and the exposure the cap counts (the full limit of every job a UI action started in the last 24 hours, not what
        they spent). The same numbers `check_cap` uses. Never raises: when the exposure cannot be computed, `booked_usd` is null and `unknown` is true (never 0). Kept WAIT_TTL_S seconds."""
        now = self.mono()
        cached = self._cap_cache
        if cached is not None and now - cached[0] < WAIT_TTL_S:
            return cached[1]
        try:
            cap = self.daily_cap()
            try:
                booked, unknown = round(float(self.exposure()), 6), False
            except Exception:
                booked, unknown = None, True
            out = {"cap_usd": cap, "booked_usd": booked, "unknown": unknown}
        except Exception:
            out = {"cap_usd": None, "booked_usd": None, "unknown": True}
        self._cap_cache = (now, out)
        return out

    # ---- what waits for the person (SPEC_CHAT_UI3B 1) --------------------------------------------------------------------

    def waiting(self):
        """{waiting, scanned, skipped, capped, cap_unknown}: the buttons the builders offer now (the plan's, the queue's money, a step, a draft), from the same
        `plans.state` and `steps.state` the cards use. Display only: prepare and confirm rebuild and re-check everything. Bounded: WAIT_SCAN_MAX candidates,
        WAIT_BUDGET_S seconds, the exposure computed once, the answer kept WAIT_TTL_S seconds. No reason text and no path is ever copied into a row.
        Never raises: whatever the files hold, the answer says it may be incomplete."""
        t0 = self.mono()
        cached = self._waiting_cache
        if cached is not None and t0 - cached[0] < WAIT_TTL_S:
            return cached[1]
        try:
            out = self._waiting_scan(t0)
        except Exception:
            out = {"waiting": [], "scanned": 0, "skipped": 0, "capped": True, "cap_unknown": False}
        finally:
            self._exposure_once = None
        self._waiting_cache = (t0, out)
        return out

    @staticmethod
    def _id_time(row_id):
        """The time written in a job or queue id as digits (j20261121_150231_cbce, q20261125T074538Z-310a), for one order over both; a forged created_at cannot move a row."""
        return re.sub(r"\D", "", str(row_id)[1:16])

    def _waiting_scan(self, t0):
        rows, skipped = [], 0
        qrows, qtrunc = self.cards._queue_rows()
        listing = self.cards.listing(queue_rows=(qrows, qtrunc))
        capped = not listing.get("rows") and bool(listing.get("truncated"))       # `listing` never raises: an unreadable directory comes back as no rows and truncated. The newest rows are looked at; older ones are weeks old and not a reason to warn.
        blocked = {r.get("prd_job") for r in qrows if r.get("prd_job") and r.get("state") in ("WAITING", "STOPPED", "DONE")}   # the plan is already a running or finished queue: no button to offer
        cands = [("plan", r) for r in listing.get("rows") or [] if r.get("kind") == "prd" and r.get("state") == AWAITING_HUMAN and r.get("id") not in blocked]
        cands += [("queue", r) for r in qrows if r.get("state") == "WAITING"]
        cands.sort(key=lambda c: self._id_time(c[1].get("id")), reverse=True)
        if len(cands) > WAIT_SCAN_MAX:
            cands, capped = cands[:WAIT_SCAN_MAX], True
        cap_unknown = False
        try:
            self._exposure_once = ("ok", self._exposure_scan())
        except Exception as e:                          # a Refusal, or a file the scan could not take (a RecursionError is not a ValueError): the exposure is unknown
            self._exposure_once = ("err", e if isinstance(e, Refusal) else Refusal(503, "cap", "the daily exposure cannot be computed"))
            cap_unknown = True
        for kind, r in cands:
            if self.mono() - t0 > WAIT_BUDGET_S:
                capped = True
                break
            try:
                if kind == "plan":
                    st = self.plans.state(r["id"])
                    job, item = None, None
                else:
                    st = self.steps.state(r["id"], with_job=True)
                    job, item = st.get("job"), st.get("item")
                action = st.get("action")
                if action not in WAITING_ACTIONS:
                    continue
                rows.append({"action": action, "card": "plan" if kind == "plan" else "queue", "id": r["id"], "job": job if isinstance(job, str) and UI_ID.fullmatch(job) else None,
                             "repo": r.get("repo") if isinstance(r.get("repo"), str) else None, "title": r.get("title") if isinstance(r.get("title"), str) else None,
                             "item": item if isinstance(item, int) and not isinstance(item, bool) else None})
            except Exception:
                skipped += 1
        return {"waiting": rows, "scanned": len(cands), "skipped": skipped, "capped": capped, "cap_unknown": cap_unknown}

    def decision(self, job_id):
        """One job for the Decide link: its row with what it allows; an issue job is only named, the page opens its thread."""
        got = self._read_data(job_id)
        if got is None:
            return None
        if got[0].get("kind") in ("issue", "prd"):          # a prd job is read only here: the writer's turns are started from the PRD form, its plan card is the Kartu tab (SPEC_PRD_WRITER D5, opened 2026-11-21)
            return {"id": job_id, "kind": got[0]["kind"], "state": got[0].get("state")}
        return self.decision_row(job_id, *got)

    def build_prd(self, cfg, params):
        """(card, run params) of a new PRD job typed by the human (SPEC_CHAT_MANAGER 13.8): exactly {repo, message}; the repo is one the
        writer reads; the text under the PRD writer's own limits and no key-like or invisible text; the facts from the one function the
        terminal's go-live screen reads (pj.screen_facts). No commit is shown: prepare runs no subprocess (11.10), the job freezes HEAD."""
        if set(params) - {"repo", "message"}:
            raise Refusal(400, "form", "a PRD job takes a repository and a message and nothing else")
        repo, text = params.get("repo"), normalize(params.get("message") or "")
        repos = (cfg.get("issue_writer") or {}).get("repos") or {}
        if repo not in repos:
            raise Refusal(400, "form", "that repository is not one the writer reads")
        try:
            why = pj.message_problem(cfg, text, first=True)
            if why is None and scrub(text) != text:
                why = "the message holds a key-like string or invisible characters"
            if why:
                raise Refusal(400, "form", why)
            cap = float(pj._settings(cfg)["max_usd"])
            pj._preflight(cfg, cap)
            f = pj.screen_facts(cfg, repos[repo].get("environment"))
        except rj.Refused as e:
            raise Refusal(409, "config", strip_refused(str(e))) from None
        except (KeyError, TypeError, ValueError, AttributeError, ConfigError):
            raise Refusal(409, "config", "the PRD writer's configuration is not complete") from None
        self._need_key(True)
        card = {"action": "prd_new", "title": "Ask the PRD writer", "repo": repo, "environment": repos[repo].get("environment"),
                "message": text, "commit": "HEAD when the job is created", "model": f["model"], "turn_cap_usd": f["turn_cap"],
                "job_cap_usd": cap,
                **({"runs_code": self.runs_code(cfg, repos[repo].get("environment"))["runs_code"]} if f["has_runner"] else {}),
                "data_sent": "the repository's files and this conversation go to the model provider; do not put secrets in the message"}
        return card, {"repo": repo, "message": text}

    def build_research(self, cfg, params):
        """(card, run params) of a new research job (12.2, 12.10 items 2, 7, 8, 12): everything the CLI's own go-live screen shows,
        from rr.screen_facts, the question under the issue message's text rules, the cap from the config exactly as `start` reads it."""
        if set(params) - {"message"}:
            raise Refusal(400, "form", "a research job takes the question and nothing else")
        rcfg = cfg.get("research_job")
        if not isinstance(rcfg, dict):
            raise Refusal(409, "config", "the config has no research job")
        q = normalize(params.get("message") or "")
        why = text_problem(q, "the question", QUESTION_MAX)
        if why is None and len(q.strip()) < QUESTION_MIN:
            why = f"the question has {len(q.strip())} characters, fewer than {QUESTION_MIN}"
        if why is None and scrub(q) != q:
            why = "the question holds a key-like string or invisible characters"
        if why:
            raise Refusal(400, "form", why)
        try:
            roles = rr.stage_roles(cfg, None)
            cap = float(rcfg.get("max_usd", 1.0))
            need = rr._need(rcfg)
            if not cap + 1e-9 >= need:
                raise rj.Refused(f"the research cap ${cap:.2f} is below the ${need:.2f} the stages need")
            scfg = rj.stage_config(cfg, cap)
            rr._preflight(cfg, roles, cap)
            keys = rj._needs_key(scfg, sorted(set(roles.values())), [rr._web_provider(cfg)])
            facts = rr.screen_facts(scfg, roles)
        except rj.Refused as e:
            raise Refusal(409, "config", strip_refused(str(e))) from None
        except (KeyError, TypeError, ValueError, AttributeError, ConfigError):
            raise Refusal(409, "config", "the research job's configuration is not complete") from None
        if [k[0] for k in keys] != ["deepseek"]:
            raise Refusal(409, "key", "this profile needs more than the one DeepSeek key the chat is given: start it from the terminal")
        self._need_key(False, research=True)
        try:
            models = ", ".join(f"{k} {facts['models'][k]}" for k in rr.STAGE_KINDS)
            c = facts["caps"]
            w = facts["web"]
            fallbacks = "; ".join(f"{k}: " + " -> ".join([facts["models"][k], *facts["fallbacks"][k]]) for k in rr.STAGE_KINDS
                                  if facts["fallbacks"][k])
            card = {"action": "research_new", "title": "Start a research job", "message": q,
                    "profile": rcfg.get("profile") or "default", "stage_models": models,
                    "stage_caps": f"planner ${c['planner']:.2f}, up to {facts['max_workers']} workers at ${c['worker']:.2f} each, "
                                  f"synthesis ${c['synthesis']:.2f}, checker ${c['checker']:.2f}",
                    "web": f"{w['provider']}: search ${w['search_usd']}, fetch ${w['fetch_usd']} per request, at most "
                           f"{w['max_searches']} searches and {w['max_fetches']} fetches per worker",
                    "data_sent": f"the question, the search queries and the URLs go to {w['provider']}, and the prompts to each "
                                 "stage's model provider; do not put secrets in the question",
                    "fallbacks": fallbacks or None,
                    "free_models": (", ".join(facts["free"]) + ": their providers may keep the prompts or train on them")
                    if facts["free"] else None, "job_cap_usd": cap, "facts": facts}
        except (KeyError, TypeError, ValueError):
            raise Refusal(409, "config", "the research job's configuration is not complete") from None
        return card, {"message": q}

    @staticmethod
    def digest(card):
        return hashlib.sha256(json.dumps(card, sort_keys=True, ensure_ascii=True).encode()).hexdigest()

    # ---- exposure (11.8): the full cap of every job a UI action started, from the moment it was confirmed ---------------

    def exposure(self):
        """The exposure of the last 24 hours. waiting() computes it once for its whole request and sets `_exposure_once` (and clears it in `finally`); every other caller gets
        the scan below, as before: prepare and confirm never see a remembered value."""
        once = self._exposure_once
        if once is not None:
            if once[0] == "ok":
                return once[1]
            raise once[1]
        return self._exposure_scan()

    def _exposure_scan(self):
        """USD of exposure in the last 24 hours: the writer, PRD and research jobs created via the UI (their max_usd, at least the configured cap of PRD and research) and the code jobs their
        starts made via the UI (the code cap), read from the job directories of any service, plus this service's own recent
        confirms the directories do not show yet. A job directory that cannot be read means the exposure is unknown: Refusal."""
        now = self.clock()
        total, seen = 0.0, set()
        rcap = self.research_cap()                 # read once: the config is loaded for every call
        pcap = self.prd_cap()
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
            if data.get("kind") == "research":
                try:
                    for entry in data.get("log") or []:
                        if isinstance(entry, dict) and entry.get("what") == "created" and entry.get("via") == "ui" \
                                and parse_time(entry["at"]) >= now - DAY:
                            total += max(float(data["max_usd"]), rcap)
                            seen.add(("new", n))
                except (KeyError, TypeError, ValueError):
                    raise unknown from None
                continue
            if data.get("kind") == "prd":                     # SPEC_CHAT_MANAGER 13.2: a PRD job started via the UI is exposure too
                try:
                    for entry in data.get("log") or []:
                        if isinstance(entry, dict) and entry.get("what") == "created" and entry.get("via") == "ui" \
                                and parse_time(entry["at"]) >= now - DAY:
                            total += max(float(data["max_usd"]), pcap)
                            seen.add(("new", n))
                except (KeyError, TypeError, ValueError):
                    raise unknown from None
                continue
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
        total += self.plans.exposure(now, seen)               # queues approved via the UI (SPEC_CHAT_T4A 4)
        total += self.steps.audited(now)                      # steps of a queue approved more than 24 hours ago: one job cap each (SPEC_CHAT_T4B 5, K4)
        for job_id, usd, at in self.plans.audited(now):       # the net under it: a `via` lost from the queue file
            if ("go", job_id) not in seen and os.path.lexists(self.cards.queues_dir / job_id):
                total += usd
                seen.add(("go", job_id))
        for action, cap in (("research_new", rcap), ("prd_new", pcap)):
            for job_id, at in self.audited_jobs(now, action):        # the net under the directory count: a `via` lost from the CLI
                if ("new", job_id) not in seen and (os.path.lexists(self.jobs_dir / job_id) or self.spawner.busy(job_id)):
                    total += cap
                    seen.add(("new", job_id))
        self.pending = [(at, key, usd) for at, key, usd in self.pending if now - at < PENDING_S]
        total += sum(usd for _, key, usd in self.pending if key not in seen)
        return total

    def research_cap(self):
        try:
            return float((self.cfg.get("research_job") or {}).get("max_usd", 1.0))
        except (TypeError, ValueError):
            raise Refusal(503, "cap", "the daily exposure cannot be computed (the research cap is not a number)") from None

    def prd_cap(self):
        try:
            return float((self.cfg.get("prd_writer") or {}).get("max_usd", 1.5))
        except (TypeError, ValueError):
            raise Refusal(503, "cap", "the daily exposure cannot be computed (the PRD cap is not a number)") from None

    def audited_jobs(self, now, action="research_new"):
        """(job id, time) of the jobs of this action (research, or a PRD) this chat started in the last 24 hours, from its own audit file."""
        try:
            with open(self.audit_path, "rb") as f:
                f.seek(0, os.SEEK_END)
                f.seek(max(0, f.tell() - (1 << 20)))
                raw = f.read()
        except FileNotFoundError:
            return []
        except OSError:
            raise Refusal(503, "cap", "the daily exposure cannot be computed (the audit cannot be read)") from None
        out = []
        for line in raw.decode("utf-8", "replace").splitlines():
            try:
                r = json.loads(line)
                if r.get("action") == action and r.get("ok") == "confirm" and UI_ID.fullmatch(str(r.get("job"))) \
                        and parse_time(r["at"]) >= now - DAY:
                    out.append((r["job"], parse_time(r["at"])))
            except (ValueError, KeyError, TypeError, AttributeError):
                continue
        return out

    def exposure_of(self, card):
        if card["action"] in ("issue_new", "issue_start", "research_new", "prd_new"):
            return float(card["job_cap_usd"])
        if card["action"] in ("queue_step", "draft_approve"):
            return self.steps.exposure_of(card)              # 0 inside the 24 hours of its queue's approval (that money is counted), else one job cap
        if card["action"] == "queue_go":
            return float(card["queue_usd"])                  # the money the queue is approved to spend; prd_approve spends none
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
        self._waiting_cache = None                 # what waits changes with every confirm
        self._cap_cache = None                     # and so does the booked money
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
        if a in ("job_reject", "job_abandon"):
            code, line = self.run(rp["verb"], rp["job"], rp["reason"] or ABANDON_DEFAULT, rp["sha"])
            self.last_exit = code if code is not None else "timeout"
            if code != 0:
                raise Refusal(409, "cli", strip_refused(line or "") or "the command failed")
            return {"job": rp["job"], "done": True}
        if a == "issue_abandon":
            code, line = self.run("abandon", rp["job"], rp["reason"] or "discarded from the phone")
            if code != 0:
                raise Refusal(409, "cli", strip_refused(line) or "the command failed")
            return {"job": rp["job"], "done": True}
        if a in ("prd_approve", "queue_go"):                 # no model and no key: the CLI approves what the card showed (SPEC_CHAT_T4A 5)
            return self.plans.execute(a, card, rp)
        if a in ("queue_step", "draft_approve"):
            return self.steps.execute(a, card, rp)
        key = self.key_file(a in ("issue_new", "issue_reply", "prd_new"), research=(a == "research_new"))
        c = self.jobs_dir
        if a == "research_new":
            new_id = rj.new_job_id()
            message = self.spawner.message_file(rp["message"])
            argv = self.with_config(research_cli(c, key, "--question-file", str(message), "--job-id", new_id))
            self.spawner.spawn(new_id, argv, message, action="research", text=rp["message"])
            self.pending.append((self.clock(), ("new", new_id), self.exposure_of(card)))
            return {"job": new_id, "started": True}
        if a == "prd_new":
            new_id = rj.new_job_id()
            message = self.spawner.message_file(rp["message"])
            argv = self.with_config(prd_cli(c, self.cards.queues_dir, key, "new", "--repo", rp["repo"], "--job-id", new_id,
                                            "--message-file", str(message)))
            self.spawner.spawn(new_id, argv, message, action="prd", text=rp["message"])
            self.pending.append((self.clock(), ("new", new_id), self.exposure_of(card)))
            return {"job": new_id, "started": True}
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
        if a == "issue_start":
            argv = self.with_config(issue_cli(c, key, "start", "--sha", rp["sha"]) + ["--", rp["job"]])
            self.spawner.spawn(rp["job"], argv, None, action="start")
            self.pending.append((self.clock(), ("start", rp["job"]), self.exposure_of(card)))
            return {"job": rp["job"], "started": True}
        raise Refusal(500, "action", "no such action is run here")     # SPEC_CHAT_MANAGER 13.9: an action without a branch never starts another one
