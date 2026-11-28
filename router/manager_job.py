"""The manager job (docs/reviews/SPEC_CHAT_MANAGER_P1.md, rev 1): kind "manager", one job = one chat session = one confirmation.

  NEW -> OPEN -> ABANDONED;  NEW|OPEN -> BLOCKED (expired, or cannot be funded) -> ABANDONED

The chat starts it with `argus manager new --via ui --yes` (the card the human tapped is the confirmation) and sends each message with
`argus manager turn JOB --message-file F --via ui --key-file K --yes`. A turn is ONE model call (a second only to repair an unusable reply):
the model answers `{"say", "propose"}` (router/manager_route.py); `propose` is data kept in the job, nothing here turns it into a card, a token or a
confirmation. The session's money is its stage `m1`: every call writes the ledger `runs/<job>-m1/events.jsonl`, the one `rj.spent_nano` and the chat
read; the job's `max_usd` is fixed at creation and never topped up. There is no resume: a crash after the call leaves the money in the ledger.
"""
import calendar
import hashlib
import json
import math
import time
import unicodedata
from pathlib import Path

from langchain_core.messages import HumanMessage, SystemMessage

from harness.errors import LLMCallFailed, ReservationExhausted
from harness.events import EventLog
from harness.llm import LLMCaller, Reservation, is_truncated, reconcile_ledger
from models.registry import ModelRef, price_for
from router import job as rj
from router import manager_route as mr
from router import t3b_run as tr

KIND = "manager"
NEW, OPEN, BLOCKED, ABANDONED = rj.NEW, "OPEN", rj.BLOCKED, rj.ABANDONED
LEGAL = {(NEW, OPEN), (NEW, BLOCKED), (NEW, ABANDONED), (OPEN, BLOCKED), (OPEN, ABANDONED), (BLOCKED, ABANDONED)}
SID = "m1"
FIXED_SAY = "I could not form a usable proposal; please rephrase."
KEYS = ("role", "session_cap_usd", "turn_cap_usd", "max_output_tokens", "ttl_hours", "message_max", "context_chars", "keep_recent_turns", "summary_chars", "max_turns", "readable_repos")
CALLS_PER_TURN = 2
SYSTEM_MAX = 20000                   # the bound the settings enforce on the system prompt (the real one is about 7,500 characters)
FILE_MAX = 3 * 1024 * 1024           # a session file above this is not extended: the chat reads a job.json up to 4 MB (SPEC_FOREMAN_MEMORY rev 1.3)
RETRY_AFTER = 3                      # no new compaction while one of the last 3 foreman entries carries compaction_failed


def _finite(v, name, *, integer=False, hi=None):
    if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or v <= 0 or (integer and int(v) != v) or (hi is not None and v > hi):
        raise rj.Refused(f"config chat.manager.{name} must be a positive number{' (integer)' if integer else ''}{f' of at most {hi}' if hi else ''}")
    return int(v) if integer else float(v)


def _bounds_problem(out, cfg, role):
    """Why the checked numbers cannot work together, or None (a seam the tests of the runtime refusals switch off): the verbatim tail and a summary fit in half of the context, the
    system prompt is bounded, and a reply or a compaction at full context fits the turn cap with the caller's own token count."""
    if out["keep_recent_turns"] * (2 * mr.SAY_MAX + 40) + out["summary_chars"] > out["context_chars"] / 2:
        return "config chat.manager: keep_recent_turns turns of at most 4,040 characters plus summary_chars must stay within half of context_chars"
    try:
        sysmax = len(mr.system_prompt(_repos(cfg)))
    except OSError as e:
        return f"the capability sheet cannot be read: {e}"
    if sysmax > SYSTEM_MAX:
        return f"the foreman's system prompt is {sysmax} characters, above {SYSTEM_MAX}"
    scfg = rj.stage_config(cfg, out["session_cap_usd"])
    ref = ModelRef.parse(role["model"])
    reply_chars = out["context_chars"] + sysmax + out["message_max"] + 4096                  # the context, the system prompt, a message, and room for the steps block and a repair text
    for what, chars in (("a reply call", reply_chars), ("a compaction call", out["context_chars"] + sysmax + 1024)):
        worst = worst_usd(scfg, ref, chars, out["max_output_tokens"])
        if worst > out["turn_cap_usd"]:
            return f"config chat.manager: {what} at full context costs up to ${worst:.4f}, above turn_cap_usd"
    return None


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
           "context_chars": _finite(m["context_chars"], "context_chars", integer=True, hi=400000),
           "keep_recent_turns": _finite(m["keep_recent_turns"], "keep_recent_turns", integer=True, hi=40),
           "summary_chars": _finite(m["summary_chars"], "summary_chars", integer=True, hi=8000), "max_turns": _finite(m["max_turns"], "max_turns", integer=True, hi=200)}
    if not isinstance(out["role"], str) or out["role"] not in (cfg.get("roles") or {}):
        raise rj.Refused("config chat.manager.role must name a role in roles")
    r = cfg["roles"][out["role"]]
    if not isinstance(r, dict) or not isinstance(r.get("model"), str) or r.get("max_output_tokens") != out["max_output_tokens"]:
        raise rj.Refused("config roles.<chat.manager.role> must have a model and the same max_output_tokens as chat.manager")
    if out["turn_cap_usd"] > out["session_cap_usd"]:
        raise rj.Refused("config chat.manager.turn_cap_usd is above session_cap_usd")
    if out["summary_chars"] > out["max_output_tokens"]:
        raise rj.Refused("config chat.manager.summary_chars is above max_output_tokens")
    why = _bounds_problem(out, cfg, r)
    if why:
        raise rj.Refused(why)
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


def _ui_id_shape(job_id):
    return isinstance(job_id, str) and rj.JOB_ID.fullmatch(job_id) is not None


def _create(job_id, deps, m, role, jobs_dir, via, extra_inputs, conversation, created_note):
    """The one place a session job is made (the stage directory exists from the start: the chat reads a missing runs directory as an unknown cost)."""
    job = rj.Job(Path(jobs_dir) / job_id)
    if job.file.exists():
        raise rj.Refused(f"job {job_id} already exists")
    with job.lock():
        if job.data is not None:
            raise rj.Refused(f"job {job_id} already exists")
        job.data = {"job": job_id, "kind": KIND, "state": NEW, "created_at": deps.clock(), "max_usd": m["session_cap_usd"],
                    "inputs": {"role": m["role"], "model": role["model"], "readable_repos": [], **extra_inputs}, "conversation": conversation, "stages": {}, "log": []}
        job.note(deps, "created", via=via, **created_note)
        job.data["stages"][SID] = {"kind": "manager", "run_id": f"{job.id}-{SID}", "cap_usd": m["session_cap_usd"], "started_at": deps.clock()}
        (job.runs / f"{job.id}-{SID}").mkdir(parents=True, exist_ok=True)
        job.move(OPEN, deps)
    return job


def new(*, cfg, deps, jobs_dir=rj.JOBS, job_id=None, via=None, title=None, continue_from=None):
    """A new session job, OPEN. Only `via ui` (the chat's confirm is its one confirmation); the id must be the exact shape of a harness id (SPEC_CHAT_APP 12.10 item 9).
    SPEC_FOREMAN_TOPICS: `title` names a new topic (the session is its first); `continue_from` continues the topic of that previous session, whose newest turns and summary are carried
    into the new one as data (the head is built by this code, no model is called); the two are exclusive."""
    if via != "ui":
        raise rj.Refused("a manager session is started from the chat (--via ui); nothing was started")
    from . import research as rr
    why = rr.ui_job_id_problem(job_id, deps.clock())
    if why:
        raise rj.Refused(f"{why}; nothing was started")
    if title is not None and continue_from is not None:
        raise rj.Refused("a session names a new topic or continues one, not both; nothing was started")
    m = settings(cfg)
    role = cfg["roles"][m["role"]]
    if title is not None:
        bad = mr.title_problem(title)
        if bad:
            raise rj.Refused(f"{bad}; nothing was started")
        t = title.strip()
        return _create(job_id, deps, m, role, jobs_dir, via, {"topic": {"id": job_id, "title": t}}, [], {})
    if continue_from is None:
        return _create(job_id, deps, m, role, jobs_dir, via, {}, [], {})
    if not _ui_id_shape(continue_from):
        raise rj.Refused("the session to continue is not a job id; nothing was started")
    prev = rj.open_job(continue_from, jobs_dir)                      # refuses a missing job before any lock makes a directory
    with prev.lock():                                                 # every check happens under the previous session's lock, BEFORE the new job exists (a refusal leaves nothing behind)
        pd = prev.data
        if not isinstance(pd, dict) or pd.get("kind") != KIND or not _created_via_ui(prev):
            raise rj.Refused(f"job {continue_from} is not a foreman session started from the chat; nothing was started")
        pin = pd.get("inputs") if isinstance(pd.get("inputs"), dict) else {}
        if pin.get("continued_by"):
            raise rj.Refused(f"the topic was already continued ({pin['continued_by']}); nothing was started")
        try:
            spent = rj.spent_nano(prev)
        except (OSError, KeyError, TypeError, ValueError, rj.Refused):
            spent = None
        size = len(json.dumps(pd, indent=2, ensure_ascii=False).encode("utf-8"))
        verdict = can_take_turn(pd, spent, m, _epoch(deps.clock()), size)
        if verdict == "unknown":
            raise rj.Refused(f"session {continue_from}: its state or spend cannot be computed; nothing was started")
        if verdict == "yes":
            raise rj.Refused(f"session {continue_from} can still take a turn: write in it; nothing was started")
        topic = topic_of(pd, continue_from)
        text = carried_head(pd, m)
        head = {"from": "summary", "at": deps.clock(), "text": text, "covers": [0, 1], "usd": 0.0, "calls": 0, "carried": True,
                "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest()}
        job = _create(job_id, deps, m, role, jobs_dir, via, {"topic": {"id": topic["id"], "title": topic["title"]}, "continues": continue_from}, [head], {"continues": continue_from})
        pd.setdefault("inputs", {})["continued_by"] = job.id
        prev.data = pd
        prev.note(deps, "continued", to=job.id)
    return job


def _epoch(stamp):
    try:
        return calendar.timegm(time.strptime(stamp, "%Y-%m-%dT%H:%M:%SZ"))
    except (ValueError, TypeError):
        return None


def can_take_turn(data, spent_nano, m, now_s, size=None):
    """"yes", "no" or "unknown": whether a turn can be sent to this session now (one answer for the chat's reads, the page and the continuation). `no`: not a foreman session via the
    UI, not OPEN, older than ttl_hours (an expired session is still OPEN until a turn moves it to BLOCKED), less left than a turn's cap, the human turns used up, or a file above
    FILE_MAX (every turn would be refused). `unknown`: the age or the spend cannot be computed."""
    if not isinstance(data, dict) or data.get("kind") != KIND:
        return "no"
    if not any(isinstance(e, dict) and e.get("what") == "created" and e.get("via") == "ui" for e in data.get("log") or []):
        return "no"
    if data.get("state") != OPEN:
        return "no"
    created = _epoch(data.get("created_at"))
    if created is None or now_s is None:
        return "unknown"
    if now_s - created > m["ttl_hours"] * 3600:
        return "no"
    if spent_nano is None:
        return "unknown"
    try:
        left = (rj.to_nano(data["max_usd"]) - spent_nano) / 1e9
    except (KeyError, TypeError, ValueError, OverflowError):
        return "unknown"
    if left < m["turn_cap_usd"] - 1e-12:
        return "no"
    if sum(1 for e in data.get("conversation") or [] if isinstance(e, dict) and e.get("from") == "human") >= m["max_turns"]:
        return "no"
    if size is not None and size > FILE_MAX:
        return "no"
    return "yes"


def derived_title(data):
    """The title of a session that has none: the first 40 characters of the person's first message, cleaned, else "Foreman chat of <date>"."""
    for e in data.get("conversation") or []:
        if isinstance(e, dict) and e.get("from") == "human" and isinstance(e.get("text"), str):
            t = "".join(c for c in e["text"] if unicodedata.category(c)[0] != "C" and unicodedata.category(c) not in ("Zl", "Zp")).strip()
            if t:
                return t[:40]
    return "Foreman chat of " + str(data.get("created_at") or "")[:10]


def topic_of(data, job_id):
    """{id, title, legacy} of a session: its `inputs.topic`, or (a session from before topics) its own id and a title derived from its first message."""
    t = (data.get("inputs") or {}).get("topic") if isinstance(data.get("inputs"), dict) else None
    if isinstance(t, dict) and isinstance(t.get("id"), str) and isinstance(t.get("title"), str) and t["title"].strip():
        return {"id": t["id"], "title": t["title"], "legacy": False}
    return {"id": job_id, "title": derived_title(data), "legacy": True}


def carried_head(prev, m):
    """The text a continuation carries over (SPEC_FOREMAN_TOPICS rev 1 E8): the previous session's newest summary (a carried one only to its first `summary_chars`), then the last
    `keep_recent_turns` human turns with the replies as the context's own JSON lines; whole OLDEST lines are dropped until it fits `context_chars // 2`, never a cut inside a line."""
    conv = prev.get("conversation") or []
    _si, summary = _last_summary(conv)
    prior = ""
    if summary:
        prior = summary["text"][:m["summary_chars"]] if summary.get("carried") else summary["text"]
    k = _split_index(conv, m["keep_recent_turns"])
    lines = [_line(e) for e in conv[k:] if isinstance(e, dict) and e.get("from") in ("human", "manager")]
    head = (prior + "\n" if prior else "") + "Recent turns:\n"
    budget = m["context_chars"] // 2 - len(head)
    kept, size = [], 0
    for ln in reversed(lines):
        b = len(ln) + 1
        if size + b > budget:
            break
        kept.append(ln)
        size += b
    return head + "\n".join(reversed(kept))


def _age_s(job, now):
    try:
        return calendar.timegm(time.strptime(now, "%Y-%m-%dT%H:%M:%SZ")) - calendar.timegm(time.strptime(job.data["created_at"], "%Y-%m-%dT%H:%M:%SZ"))
    except (ValueError, TypeError, KeyError):
        return None


def _created_via_ui(job):
    return any(e.get("what") == "created" and e.get("via") == "ui" for e in job.data.get("log") or [] if isinstance(e, dict))


def _margin(scfg, ref):
    llm = scfg.get("llm") or {}
    return float((llm.get("input_margin_by_model") or {}).get(str(ref), llm.get("input_margin", 1.2)))


def est_tokens(chars, scfg, ref, messages=2):
    """The count `LLMCaller` makes of a prompt (harness.llm.heuristic_counter): (chars / 3 + 8 per message) x the model's margin; the foreman's reservation is made with the same count."""
    return int((chars / 3 + 8 * messages) * _margin(scfg, ref)) + 1


def worst_usd(scfg, ref, chars, max_output):
    p = price_for(scfg, ref)
    return est_tokens(chars, scfg, ref) * p["input"] / 1e6 + max_output * p["output"] / 1e6


def reservation(scfg, ref, chars, max_output, usd):
    return Reservation(tokens=est_tokens(chars, scfg, ref) + max_output + 2000, usd=usd)


def _last_summary(conversation):
    """(index, entry) of the newest summary entry, or (-1, None)."""
    for i in range(len(conversation) - 1, -1, -1):
        e = conversation[i]
        if isinstance(e, dict) and e.get("from") == "summary" and isinstance(e.get("text"), str):
            return i, e
    return -1, None


def _line(e):
    who = "user" if e.get("from") == "human" else "foreman"
    return json.dumps({who: str(e.get("say") if who == "foreman" else e.get("text"))[:mr.SAY_MAX]}, ensure_ascii=False)     # one JSON object a line: a newline in a text cannot forge the next line


def _covers_end(entry):
    c = entry.get("covers") if isinstance(entry, dict) else None
    return c[1] if isinstance(c, list) and len(c) == 2 and isinstance(c[1], int) and c[1] >= 0 else 0


def _context(conversation, limit):
    """Earlier turns as data, cut by code so that the text (a summary included) is at most `limit` characters, the newest lines kept: the newest summary (if any), then every
    entry after the range it replaces, as JSON lines. A summary entry is never a line; a proposal is not in a line; the model's own earlier words are data too."""
    si, summary = _last_summary(conversation)
    head = ""
    if summary:                                                     # a carried head (a continuation's) has its own label and is capped defensively at half of the limit
        text = summary["text"][:limit // 2] if summary.get("carried") else summary["text"]
        head = (mr.CARRIED_LABEL if summary.get("carried") else mr.SUMMARY_LABEL) + "\n" + text
    lines = [_line(e) for e in conversation[_covers_end(summary) if summary else 0:] if isinstance(e, dict) and e.get("from") in ("human", "manager")]
    budget = limit - len(head)
    out, size = [], 0
    for ln in reversed(lines):
        b = len(ln.encode("utf-8")) + 1
        if size + b > budget:
            break
        out.append(ln)
        size += b
    body = "\n".join(reversed(out))
    if head and body:
        return head + "\nEarlier turns:\n" + body
    return head or body or None


def _needs_compaction(conversation, m):
    """True when the (uncut) context is above `context_chars` and more than `keep_recent_turns` human turns follow the newest summary entry."""
    si, _ = _last_summary(conversation)
    humans = sum(1 for e in conversation[si + 1:] if isinstance(e, dict) and e.get("from") == "human")
    return humans > m["keep_recent_turns"] and len(_context(conversation, 10 ** 9) or "") > m["context_chars"]


def _split_index(conversation, keep):
    """k: the conversation index of the `keep`th human entry from the newest; everything from k on stays verbatim."""
    seen = 0
    for i in range(len(conversation) - 1, -1, -1):
        if isinstance(conversation[i], dict) and conversation[i].get("from") == "human":
            seen += 1
            if seen == keep:
                return i
    return 0


def _compaction_blocked(conversation):
    """True while one of the last RETRY_AFTER foreman entries carries compaction_failed: a failing compaction costs at most one extra call per RETRY_AFTER + 1 turns."""
    last = [e for e in conversation if isinstance(e, dict) and e.get("from") == "manager"][-RETRY_AFTER:]
    return any(e.get("compaction_failed") for e in last)


def _compact_inputs(conversation, k):
    """(old summary text or None, lines) to fold into the next summary: the lines of the entries from the old summary's range end up to k, the old summary entry itself skipped."""
    si, summary = _last_summary(conversation)
    start = _covers_end(summary) if summary else 0
    lines = [_line(e) for e in conversation[start:k] if isinstance(e, dict) and e.get("from") in ("human", "manager")]
    return (summary["text"] if summary else None), lines


def turn(job_id, message, *, cfg, deps, jobs_dir=rj.JOBS, steps=None):
    """One human message and the foreman's answer, under the job's lock. Returns the manager entry. Every refusal is a `Refused` with a sentence and nothing is called.
    `steps`: the jobs this session started, as parse_steps returns them (SPEC_CHAT_MANAGER_P4B): they join the context as facts from the harness; they are not kept in the job.
    SPEC_FOREMAN_MEMORY: when the earlier turns are longer than `context_chars` the code first folds the older ones into a summary entry (one extra call, its own charge); a failed
    compaction never blocks the turn: the context is then cut by code to `context_chars`."""
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
        if len(json.dumps(d, indent=2, ensure_ascii=False).encode("utf-8")) > FILE_MAX:           # as Job.save writes it
            raise rj.Refused("the session file is too large; start a new one; no turn was run")
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

        def fits(user, sysp=None):
            worst = worst_usd(scfg, ref, len(sysp if sysp is not None else system) + len(user), m["max_output_tokens"])
            return worst, worst <= m["turn_cap_usd"] + 1e-12 and worst <= left() + 1e-12

        def prompt():
            context = _context(d["conversation"], m["context_chars"])
            if steps:
                context = "Jobs this conversation started (facts from the harness):\n" + mr.steps_context(steps) + ("\nEarlier turns:\n" + context if context else "")
            return mr.user_prompt(message, context)

        user = prompt()
        worst, ok = fits(user)
        if not ok:
            raise rj.Refused(f"the session budget cannot fund another turn (worst case ${worst:.4f}, turn cap ${m['turn_cap_usd']:.2f}, left ${left():.4f}); no turn was run")
        want = _needs_compaction(d["conversation"], m) and not _compaction_blocked(d["conversation"])
        k = _split_index(d["conversation"], m["keep_recent_turns"]) if want else 0
        old_summary, fold = _compact_inputs(d["conversation"], k) if want else (None, [])
        cprompt = mr.compact_user_prompt(old_summary, fold, m["summary_chars"]) if want else ""
        cworst, cok = fits(cprompt, mr.COMPACT_INSTRUCTION) if want else (0.0, False)
        text = (f"manager turn on {ref}: one call (a second only if the reply is unusable), worst case ${worst:.4f} each, session cap ${d['max_usd']:.2f}; "
                "your message and the earlier turns go to the model provider; no repository content is sent")
        if want:
            text += f"; the earlier turns are first summarized by one more call (worst case ${cworst:.4f}) and the summary replaces them in the prompt"
        entry = {"from": "manager", "say": "", "propose": None, "usd": 0.0, "calls": 0}
        with rj.live(deps, scfg, [m["role"]], text, job=job):                                       # the key is taken first: a refusal here records no message
            caller = LLMCaller(scfg, m["role"], log, model=(deps.models or {}).get(m["role"]))
            if want:
                why_not = None
                if not cok:
                    why_not = "budget"
                elif not reconcile_ledger(log.read())[1]["usd_complete"]:
                    why_not = "ledger incomplete"
                elif cworst + worst > left() + 1e-12:
                    why_not = "budget"
                if why_not is None:
                    job.note(deps, "compaction_started", covers=[0, k])
                    b0 = reconcile_ledger(log.read())[1]["usd_nano"]
                    got_text, why_not = None, None
                    try:
                        creply = caller.call([SystemMessage(mr.COMPACT_INSTRUCTION), HumanMessage(cprompt)],
                                             reservation(scfg, ref, len(mr.COMPACT_INSTRUCTION) + len(cprompt), m["max_output_tokens"], cworst),
                                             meta={"node": "manager_compact", "task": SID, "iteration": len(d["conversation"]), "step": 0})
                        if is_truncated(creply):
                            why_not = "truncated"
                        else:
                            got_text = tr.text_of(creply).strip()
                            why_not = mr.summary_problem(got_text, m["summary_chars"]) and "unusable"
                    except (LLMCallFailed, ReservationExhausted) as e:
                        why_not = type(e).__name__
                    spent_c = round((reconcile_ledger(log.read())[1]["usd_nano"] - b0) / 1e9, 9)
                    if why_not is None:
                        d["conversation"].append({"from": "summary", "at": deps.clock(), "text": got_text, "covers": [0, k], "usd": spent_c, "calls": 1,
                                                  "sha256": hashlib.sha256(got_text.encode("utf-8")).hexdigest()})
                        job.note(deps, "compacted", covers=[0, k], chars=len(got_text))
                    else:
                        entry["compaction_usd"] = spent_c
                if why_not is not None:
                    entry["compaction_failed"] = why_not
                    job.note(deps, "compaction_failed", reason=why_not)
                user = prompt()                                                                         # the context after the compaction, or cut by code after a failure
            before = reconcile_ledger(log.read())[1]["usd_nano"]
            d["conversation"].append({"from": "human", "at": deps.clock(), "text": message})      # recorded BEFORE the call
            job.note(deps, "turn_started", turn=len([e for e in d["conversation"] if e.get("from") == "human"]))
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
                    reply = caller.call([SystemMessage(system), HumanMessage(u)], reservation(scfg, ref, len(system) + len(u), m["max_output_tokens"], worst),
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
