"""The manager job (docs/reviews/SPEC_CHAT_MANAGER_P1.md, rev 1): kind "manager", one job = one chat session = one confirmation.

  NEW -> OPEN -> ABANDONED;  NEW|OPEN -> BLOCKED (expired, or cannot be funded) -> ABANDONED

The chat starts it with `argus manager new --via ui --yes` (the card the human tapped is the confirmation) and sends each message with
`argus manager turn JOB --message-file F --via ui --key-file K --yes`. A turn is ONE model call (a second only to repair an unusable reply):
the model answers `{"say", "propose"}` (router/manager_route.py); `propose` is data kept in the job, nothing here turns it into a card, a token or a
confirmation. The session's money is its stage `m1`: every call writes the ledger `runs/<job>-m1/events.jsonl`, the one `rj.spent_nano` and the chat
read; the job's `max_usd` is fixed at creation and never topped up. There is no resume: a crash after the call leaves the money in the ledger.
"""
import calendar
import json
import math
import time
import unicodedata
from pathlib import Path

from langchain_core.messages import HumanMessage, SystemMessage

from harness.errors import LLMCallFailed, ReservationExhausted
from harness.events import EventLog
from harness.llm import LLMCaller, is_truncated, reconcile_ledger
from models.registry import ModelRef
from router import job as rj
from router import manager_route as mr
from router import t3b_run as tr

KIND = "manager"
NEW, OPEN, BLOCKED, ABANDONED = rj.NEW, "OPEN", rj.BLOCKED, rj.ABANDONED
LEGAL = {(NEW, OPEN), (NEW, BLOCKED), (NEW, ABANDONED), (OPEN, BLOCKED), (OPEN, ABANDONED), (BLOCKED, ABANDONED)}
SID = "m1"
FIXED_SAY = "I could not form a usable proposal; please rephrase."
KEYS = ("role", "session_cap_usd", "turn_cap_usd", "max_output_tokens", "ttl_hours", "message_max", "summary_bytes", "max_turns", "readable_repos")
CALLS_PER_TURN = 2


def _finite(v, name, *, integer=False, hi=None):
    if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or v <= 0 or (integer and int(v) != v) or (hi is not None and v > hi):
        raise rj.Refused(f"config chat.manager.{name} must be a positive number{' (integer)' if integer else ''}{f' of at most {hi}' if hi else ''}")
    return int(v) if integer else float(v)


def settings(cfg):
    """chat.manager, checked (there is no other validator): every number finite and positive, the turn cap inside the session cap, the ttl below the 24 h exposure
    window, readable_repos empty (P1 reads no repository: K2), the role defined."""
    m = (cfg.get("chat") or {}).get("manager")
    if not isinstance(m, dict):
        raise rj.Refused("config chat.manager is missing")
    miss = [k for k in KEYS if k not in m]
    if miss:
        raise rj.Refused(f"config chat.manager lacks {', '.join(miss)}")
    extra = sorted(set(m) - set(KEYS))
    if extra:
        raise rj.Refused(f"config chat.manager has unknown keys: {', '.join(map(str, extra))}")
    out = {"role": m["role"],
           "session_cap_usd": _finite(m["session_cap_usd"], "session_cap_usd"), "turn_cap_usd": _finite(m["turn_cap_usd"], "turn_cap_usd"),
           "max_output_tokens": _finite(m["max_output_tokens"], "max_output_tokens", integer=True, hi=8000),
           "ttl_hours": _finite(m["ttl_hours"], "ttl_hours", hi=23), "message_max": _finite(m["message_max"], "message_max", integer=True, hi=mr.SAY_MAX),
           "summary_bytes": _finite(m["summary_bytes"], "summary_bytes", integer=True, hi=16384), "max_turns": _finite(m["max_turns"], "max_turns", integer=True, hi=200)}
    if not isinstance(out["role"], str) or out["role"] not in (cfg.get("roles") or {}):
        raise rj.Refused("config chat.manager.role must name a role in roles")
    r = cfg["roles"][out["role"]]
    if not isinstance(r, dict) or not isinstance(r.get("model"), str) or r.get("max_output_tokens") != out["max_output_tokens"]:
        raise rj.Refused("config roles.<chat.manager.role> must have a model and the same max_output_tokens as chat.manager")
    if out["turn_cap_usd"] > out["session_cap_usd"]:
        raise rj.Refused("config chat.manager.turn_cap_usd is above session_cap_usd")
    if m["readable_repos"] != []:
        raise rj.Refused("config chat.manager.readable_repos must be empty (P1 sends no repository content to the model)")
    out["readable_repos"] = []
    return out


def message_problem(m, text):
    """Why a message cannot be sent, or None: non-empty, within message_max, no control, format or surrogate character (a newline or tab is fine), no line or paragraph separator."""
    if not isinstance(text, str) or not text.strip():
        return "the message is empty"
    if len(text) > m["message_max"]:
        return f"the message is longer than {m['message_max']} characters"
    if not mr._clean(text) or any(unicodedata.category(c) in ("Zl", "Zp") for c in text):
        return "the message holds a control, format or separator character"
    return None


def _repos(cfg):
    return sorted(((cfg.get("issue_writer") or {}).get("repos") or {}))


def new(*, cfg, deps, jobs_dir=rj.JOBS, job_id=None, via=None):
    """A new session job, OPEN. Only `via ui` (the chat's confirm is its one confirmation); the id must be the exact shape of a harness id (SPEC_CHAT_APP 12.10 item 9)."""
    if via != "ui":
        raise rj.Refused("a manager session is started from the chat (--via ui); nothing was started")
    from . import research as rr
    why = rr.ui_job_id_problem(job_id, deps.clock())
    if why:
        raise rj.Refused(f"{why}; nothing was started")
    m = settings(cfg)
    role = cfg["roles"][m["role"]]
    job = rj.Job(Path(jobs_dir) / job_id)
    if job.file.exists():
        raise rj.Refused(f"job {job_id} already exists")
    with job.lock():
        if job.data is not None:
            raise rj.Refused(f"job {job_id} already exists")
        job.data = {"job": job_id, "kind": KIND, "state": NEW, "created_at": deps.clock(), "max_usd": m["session_cap_usd"],
                    "inputs": {"role": m["role"], "model": role["model"], "readable_repos": []}, "conversation": [], "stages": {}, "log": []}
        job.note(deps, "created", via=via)
        job.data["stages"][SID] = {"kind": "manager", "run_id": f"{job.id}-{SID}", "cap_usd": m["session_cap_usd"], "started_at": deps.clock()}
        (job.runs / f"{job.id}-{SID}").mkdir(parents=True, exist_ok=True)         # the chat reads a missing runs directory as an unknown cost: the stage's directory exists from the start
        job.move(OPEN, deps)
    return job


def _age_s(job, now):
    try:
        return calendar.timegm(time.strptime(now, "%Y-%m-%dT%H:%M:%SZ")) - calendar.timegm(time.strptime(job.data["created_at"], "%Y-%m-%dT%H:%M:%SZ"))
    except (ValueError, TypeError, KeyError):
        return None


def _created_via_ui(job):
    return any(e.get("what") == "created" and e.get("via") == "ui" for e in job.data.get("log") or [] if isinstance(e, dict))


def _context(conversation, limit):
    """Earlier turns as data, newest kept, cut by code to `limit` bytes; the model's own earlier words are data too."""
    lines = []
    for e in conversation:
        who = "user" if e.get("from") == "human" else "foreman"
        lines.append(json.dumps({who: str(e.get("say") if who == "foreman" else e.get("text"))[:mr.SAY_MAX]}, ensure_ascii=False))     # one JSON object a line: a newline in a text cannot forge the other side's label
    out, size = [], 0
    for ln in reversed(lines):
        b = len(ln.encode("utf-8")) + 1
        if size + b > limit:
            break
        out.append(ln)
        size += b
    return "\n".join(reversed(out)) or None


def turn(job_id, message, *, cfg, deps, jobs_dir=rj.JOBS):
    """One human message and the foreman's answer, under the job's lock. Returns the manager entry. Every refusal is a `Refused` with a sentence and nothing is called."""
    m = settings(cfg)
    job = rj.open_job(job_id, jobs_dir)
    with job.lock():
        d = job.data
        if d.get("kind") != KIND:
            raise rj.Refused(f"job {job_id} is not a manager session")
        if not _created_via_ui(job):
            raise rj.Refused(f"job {job_id} was not started from the chat; no turn was run")
        if d["state"] != OPEN:
            raise rj.Refused(f"job {job_id} is {d['state']}, not OPEN; no turn was run")
        age = _age_s(job, deps.clock())
        if age is None or age > m["ttl_hours"] * 3600:
            job.move(BLOCKED, deps, reason="expired")
            raise rj.Refused(f"session {job_id} has expired ({m['ttl_hours']:g} h); start a new one")
        why = message_problem(m, message)
        if why:
            raise rj.Refused(f"{why}; no turn was run")
        if sum(1 for e in d["conversation"] if e.get("from") == "human") >= m["max_turns"]:
            raise rj.Refused(f"the session has reached its {m['max_turns']} turns; start a new one")
        if not mr.sheet_ok():
            raise rj.Refused("the capability sheet is not the pinned one; no turn was run")
        repos = _repos(cfg)
        ref = ModelRef.parse(d["inputs"]["model"])
        scfg = rj.stage_config(cfg, max(0.0, (rj.to_nano(d["max_usd"]) - rj.spent_nano(job)) / 1e9))         # the run's own budget is what the session has left
        system = mr.system_prompt(repos)
        ledger = job.runs / d["stages"][SID]["run_id"] / "events.jsonl"
        ledger.parent.mkdir(parents=True, exist_ok=True)
        log = EventLog(ledger)

        def left():
            return (rj.to_nano(d["max_usd"]) - rj.spent_nano(job)) / 1e9

        def fits(user):
            worst = tr.worst_usd(scfg, ref, len(system) + len(user), m["max_output_tokens"])
            return worst, worst <= m["turn_cap_usd"] + 1e-12 and worst <= left() + 1e-12

        context = _context(d["conversation"], m["summary_bytes"])
        user = mr.user_prompt(message, context)
        worst, ok = fits(user)
        if not ok:
            raise rj.Refused(f"the session budget cannot fund another turn (worst case ${worst:.4f}, turn cap ${m['turn_cap_usd']:.2f}, left ${left():.4f}); no turn was run")
        text = (f"manager turn on {ref}: one call (a second only if the reply is unusable), worst case ${worst:.4f} each, session cap ${d['max_usd']:.2f}; "
                "your message and the earlier turns go to the model provider; no repository content is sent")
        entry = {"from": "manager", "say": "", "propose": None, "usd": 0.0, "calls": 0}
        with rj.live(deps, scfg, [m["role"]], text, job=job):                                       # the key is taken first: a refusal here records no message
            before = reconcile_ledger(log.read())[1]["usd_nano"]
            d["conversation"].append({"from": "human", "at": deps.clock(), "text": message})      # recorded BEFORE the call
            job.note(deps, "turn_started", turn=len([e for e in d["conversation"] if e.get("from") == "human"]))
            caller = LLMCaller(scfg, m["role"], log, model=(deps.models or {}).get(m["role"]))
            problem = None
            for attempt in range(CALLS_PER_TURN):
                if not reconcile_ledger(log.read())[1]["usd_complete"]:
                    entry["error"] = "ledger incomplete"
                    break
                u = user if problem is None else user + f"\n<problem>\nYour previous reply was not usable: {mr.frame_safe(problem)}. Reply again with ONE valid JSON object.\n</problem>"
                worst, ok = fits(u)
                if not ok:
                    entry["error"] = "the budget does not fund another call"
                    break
                try:
                    reply = caller.call([SystemMessage(system), HumanMessage(u)], tr.reservation(len(system) + len(u), m["max_output_tokens"], worst),
                                        meta={"node": "manager", "task": SID, "iteration": len(d["conversation"]), "step": attempt})
                except (LLMCallFailed, ReservationExhausted) as e:
                    entry["calls"] += 1
                    entry["error"] = type(e).__name__
                    break
                entry["calls"] += 1
                if is_truncated(reply):
                    problem = "the reply was cut at the output limit"
                    continue
                raw = tr.text_of(reply).strip()
                if not (raw.startswith("{") and raw.endswith("}")):          # a fenced block or words around the object are not accepted (the parser alone would find the object inside)
                    got, problem = None, "the reply must be the JSON object and nothing else"
                else:
                    got, problem = mr.parse_turn(raw)
                if got is not None:
                    bad = mr.proposal_problems(got, repos)
                    if bad:
                        got, problem = None, "; ".join(bad)
                if got is not None:
                    entry["say"], entry["propose"], problem = got["say"], got["propose"], None
                    break
            if problem is not None and not entry.get("error"):
                entry["say"], entry["propose"] = FIXED_SAY, None
        entry["usd"] = round((reconcile_ledger(log.read())[1]["usd_nano"] - before) / 1e9, 9)
        entry["at"] = deps.clock()
        d["conversation"].append(entry)
        job.note(deps, "turn_done", calls=entry["calls"])
        return entry


def status_lines(job):
    d = job.data
    n = sum(1 for e in d.get("conversation") or [] if e.get("from") == "human")
    last = next((e for e in reversed(d.get("conversation") or []) if e.get("from") == "manager"), None)
    out = [f"turns: {n}", f"session cap ${d['max_usd']:.2f}"]
    if last and last.get("say"):
        out.append("last answer (the model's words, not checked): " + rj.clean(last["say"][:200]))
    return out
