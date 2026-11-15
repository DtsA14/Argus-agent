"""SPEC_PRD_QUEUE part A: issues in order on one repository, each on the commit the one before it was applied as.

  argus queue new     the repository (a name of issue_writer.repos), its commit, a money cap and the issues -> PENDING (nothing runs)
  argus queue go      the human approves the list and the money (its sha)
  argus queue step    at most one drafter run (the next issue's code job), or what waits for a human; never approve, apply or push
  argus queue status  read only
  argus queue close   the human closes a queue that is stuck (no job is touched)

The queue's status is never stored: it is derived from the items' job.json each time (PENDING, WAITING, STOPPED, DONE,
CLOSED). Stored are the repository, the commit, the money, the issues (their text, written once) and the approval.
Money: a job that can still spend counts at its whole cap, so the total never passes max_usd (a judge can still spend
on an APPLIED or REJECTED job, a failed one can be retried); only ABANDONED, BLOCKED and REVIEW_INVALID count what they spent.
"""
import fcntl
import hashlib
import json
import os
import re
import secrets
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from acceptance import intake
from harness.llm import to_nano

from . import issue as ri
from . import job as rj

QUEUES = rj.ROOT / "queues"
QUEUE_MAX_USD = 5.00            # D2 (Atha 2026-11-15): the ceiling of one queue's money
QUEUE_MAX_ITEMS = 8
QUEUE_ID = re.compile(r"^q[0-9]{8}T[0-9]{6}Z-[0-9a-f]{4}$")
PENDING, WAITING, STOPPED, DONE, CLOSED = "PENDING", "WAITING", "STOPPED", "DONE", "CLOSED"
RUNNING_NEXT = "NEXT"           # derive's answer when the next item can start (shown as WAITING for `step`)
FAILED = (rj.DRAFT_FAILED, rj.AGENT_FAILED, rj.REVIEW_INVALID, rj.BLOCKED, rj.REJECTED, rj.ABANDONED,
          rj.RESEARCH_INCONCLUSIVE, rj.RESEARCH_FAILED)
LIVE = (rj.NEW, rj.DRAFTING, rj.AWAITING_APPROVAL, rj.AGENT_RUNNING, rj.REVIEW_READY)
SPENT_ONLY = (rj.ABANDONED, rj.BLOCKED, rj.REVIEW_INVALID)      # states that cannot spend again (LEGAL, JUDGEABLE)


class Refused(rj.Refused):
    pass


def _sha(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _dir(queues_dir, qid):
    if not isinstance(qid, str) or not QUEUE_ID.fullmatch(qid):
        raise Refused(f"{qid!r} is not a queue id")
    return Path(queues_dir) / qid


def _save(d, q):
    tmp = d / "queue.json.tmp"
    tmp.write_text(json.dumps(q, indent=2, sort_keys=True), encoding="utf-8")
    os.replace(tmp, d / "queue.json")


@contextmanager
def _flock(path, what):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(path, os.O_RDWR | os.O_CREAT, 0o644)
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise Refused(f"{what} is in use by another command; nothing was changed") from None
        yield
    finally:
        os.close(fd)


@contextmanager
def _locked(queues_dir, qid):
    """The queue under its exclusive lock (refused at once if another command holds it): (dir, queue)."""
    d = _dir(queues_dir, qid)
    if not (d / "queue.json").is_file():
        raise Refused(f"no queue {qid!r}")
    with _flock(d / ".lock", f"queue {qid}"):
        yield d, _load(d, qid)


def _load(d, qid):
    try:
        q = json.loads((d / "queue.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raise Refused(f"no queue {qid!r}") from None
    try:
        ok = (isinstance(q, dict) and q["id"] == qid and isinstance(q["max_usd"], (int, float)) and isinstance(q["job_cap_usd"], (int, float))
              and all(isinstance(q[k], str) for k in ("repo", "name", "base_commit", "jobs_dir"))
              and isinstance(q["items"], list) and q["items"]
              and all(isinstance(i, dict) and isinstance(i.get("issue_sha256"), str) and isinstance(i.get("n"), int) for i in q["items"]))
    except KeyError:
        ok = False
    if not ok:
        raise Refused(f"queue {qid}: queue.json is damaged; nothing was changed")
    return q


def list_sha(q):
    """What the human approves: the repository, the commit, the money, the caps and the issues in order."""
    return _sha(json.dumps({"repo": q["repo"], "name": q["name"], "commit": q["base_commit"], "max_usd_nano": to_nano(q["max_usd"]),
                            "job_cap_nano": to_nano(q["job_cap_usd"]), "environment": q["environment"], "jobs_dir": q["jobs_dir"],
                            "issues": [i["issue_sha256"] for i in q["items"]]}, sort_keys=True))


def _issue_text(d, item):
    """The issue text exactly as written at `new`; a file that changed is refused."""
    try:
        text = (d / f"issue-{item['n']}.md").read_text(encoding="utf-8")
    except OSError:
        raise Refused(f"issue {item['n']}: its file is missing") from None
    if _sha(text) != item["issue_sha256"]:
        raise Refused(f"issue {item['n']}: its file is not the one the queue was made with")
    return text


# ---- new, go, close -------------------------------------------------------------------------------------------------

def new(*, repo, commit, max_usd, issues, cfg, deps, queues_dir=QUEUES, jobs_dir=rj.JOBS, queue_id=None):
    """A queue (PENDING). issues: the texts, in order. Nothing runs and no money is reserved before `go`."""
    path, environment = ri.repo_of(cfg, repo)
    real = Path(path).resolve()
    if real == rj.ROOT.resolve():
        raise Refused("the queue never runs on the Argus checkout")
    try:
        cap = float(ri._settings(cfg)["code_max_usd"])
    except (KeyError, TypeError, ValueError):
        cap = float("nan")
    if not (0 < cap <= ri.CODE_MAX_USD):
        raise Refused(f"issue_writer.code_max_usd must be a number more than 0 and at most ${ri.CODE_MAX_USD:.2f}")
    try:
        money = float(max_usd)
    except (TypeError, ValueError):
        money = float("nan")
    if not (0 < money <= QUEUE_MAX_USD):
        raise Refused(f"--max-usd must be more than 0 and at most ${QUEUE_MAX_USD:.2f}")
    if money < cap:
        raise Refused(f"--max-usd ${money:.2f} is less than one job's cap ${cap:.2f}; nothing could start")
    if not isinstance(issues, list) or not 1 <= len(issues) <= QUEUE_MAX_ITEMS:
        raise Refused(f"a queue has 1 to {QUEUE_MAX_ITEMS} issues")
    texts = []
    for n, t in enumerate(issues, 1):
        problem = None if isinstance(t, str) and t.strip() else "is empty"
        problem = problem or ri.message_problem(cfg, t, True)
        if problem:
            raise Refused(f"issue {n}: {problem}")
        texts.append(t.strip())
    try:
        full = intake.git(str(real), "rev-parse", "--verify", f"{commit}^{{commit}}").decode().strip()
        here = intake.git(str(real), "rev-parse", "HEAD").decode().strip()
    except intake.IntakeError as e:
        raise Refused(f"the repository: {e}") from None
    if full != here:
        raise Refused(f"--commit is {full[:12]} but the repository's HEAD is {here[:12]}: `argus apply` needs HEAD on the commit")
    qid = queue_id or "q" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + secrets.token_hex(2)
    d = _dir(queues_dir, qid)
    with _flock(Path(queues_dir) / ".new.lock", "the queues directory"):     # two `new` on one repository race
        for other in _all(queues_dir):
            if other["repo"] == str(real) and derive(other)[0] not in (DONE, CLOSED):
                raise Refused(f"queue {other['id']} on this repository is not finished (status {derive(other)[0].replace(RUNNING_NEXT, WAITING)}): "
                              "two queues would race for the same HEAD")
        if d.exists():
            raise Refused(f"queue {qid} already exists")
        d.mkdir(parents=True)
        for n, t in enumerate(texts, 1):
            (d / f"issue-{n}.md").write_text(t, encoding="utf-8")
        q = {"id": qid, "repo": str(real), "name": repo, "environment": environment, "base_commit": full, "max_usd": money,
             "job_cap_usd": cap, "jobs_dir": str(Path(jobs_dir).resolve()), "created_at": deps.clock(),
             "items": [{"n": n, "issue_sha256": _sha(t), "job": None} for n, t in enumerate(texts, 1)],
             "approved": None, "closed": None}
        _save(d, q)
    return q


def _all(queues_dir):
    out = []
    for p in sorted(Path(queues_dir).glob("q*/queue.json")) if Path(queues_dir).exists() else []:
        try:
            q = json.loads(p.read_text(encoding="utf-8"))
            if isinstance(q, dict) and QUEUE_ID.fullmatch(str(q.get("id", ""))):
                out.append(q)
        except (OSError, ValueError):
            continue
    return out


def go(qid, *, sha, deps, queues_dir=QUEUES):
    """The human approves the list and the money: sha is (12+ hex of) the list sha `new` printed."""
    with _locked(queues_dir, qid) as (d, q):
        if q.get("closed"):
            raise Refused(f"queue {qid} is closed")
        if q.get("approved"):
            raise Refused(f"queue {qid} is already approved")
        want = list_sha(q)
        sha = sha.strip().lower() if isinstance(sha, str) else sha
        if not isinstance(sha, str) or not rj.SHA_SEEN.fullmatch(sha) or not want.startswith(sha):
            raise Refused(f"the list is {want[:12]}, not the {sha!r} given; nothing was approved")
        for item in q["items"]:
            _issue_text(d, item)
        q["approved"] = {"sha": want, "at": deps.clock(), "by": os.environ.get("USER")}
        _save(d, q)
        return q


def close(qid, note, *, deps, queues_dir=QUEUES):
    """The human closes a queue that is stuck. No job is changed; a closed queue never steps."""
    with _locked(queues_dir, qid) as (d, q):
        if q.get("closed"):
            raise Refused(f"queue {qid} is already closed")
        q["closed"] = {"at": deps.clock(), "note": note, "by": os.environ.get("USER")}
        _save(d, q)
        return q


# ---- the derived state --------------------------------------------------------------------------------------------

def _applied_commit(job):
    for e in reversed(job.data.get("log") or []):
        if e.get("what") == "state" and e.get("new") == rj.APPLIED:
            return e.get("commit"), e.get("as_is")
    return None, None


def _open(item, jobs_dir):
    try:
        return rj.open_job(item["job"], jobs_dir)
    except rj.Refused:
        return None


def _bound(job, q, item, commit):
    """The job holds this queue's issue on this commit of this repository."""
    i = job.data.get("inputs") or {}
    return (isinstance(i.get("issue"), str) and _sha(i["issue"]) == item["issue_sha256"] and i.get("commit") == commit
            and i.get("repo") == q["repo"])


def derive(q, *, jobs_dir=None):
    """(status, detail, actions, forget, next): the queue's status from the jobs, nothing written. forget: the items whose recorded
    job is to be forgotten (missing, or ended without a stage); `step` does it, `status` only reads past it.
    actions: the lines for the human; the item to start is the first without a job (a dict under 'next')."""
    if q.get("closed"):
        return CLOSED, q["closed"].get("note") or "", [], [], None
    if not q.get("approved"):
        return PENDING, f"approve with `argus queue go {q['id']} --sha {list_sha(q)[:12]}`", [], [], None
    jobs_dir = q["jobs_dir"]                            # the queue's own: a step on another jobs directory cannot see its jobs
    commit, forget, committed = q["base_commit"], [], 0
    for item in q["items"]:
        job = _open(item, jobs_dir) if item["job"] else None
        if job is not None and not _bound(job, q, item, commit):
            return STOPPED, f"item {item['n']}: job {job.id} is not this queue's issue on commit {commit[:12]}", [], forget, None
        if item["job"] and (job is None or (not job.data.get("stages") and job.data["state"] in (rj.NEW, rj.ABANDONED, rj.BLOCKED))):
            if job is not None and job.data["state"] == rj.BLOCKED:     # it would be made again at every step
                return STOPPED, f"item {item['n']}: job {job.id} is BLOCKED before its first stage", [f"argus status {job.id}"], forget, None
            forget.append(item)                         # recorded, but never started (missing, NEW, or abandoned before its first stage)
            job = None
        if job is None:
            return _next(q, item, commit, committed, jobs_dir, forget)
        state = job.data["state"]
        committed += committed_nano(job)
        if state == rj.APPLIED:
            nxt, as_is = _applied_commit(job)
            if not nxt or as_is is not True:
                return STOPPED, f"item {item['n']}: job {job.id} is APPLIED but its commit is not recorded as the patch (as_is {as_is})", [], forget, None
            commit = nxt
            continue
        if state in FAILED:
            return STOPPED, f"item {item['n']}: job {job.id} is {state}", [f"argus status {job.id}"], forget, None
        if state == rj.AWAITING_APPROVAL:
            sha = rj.draft_sha(rj._last_draft(job)[1])[:12]
            return WAITING, f"item {item['n']}: draft of {job.id} waits for approval", [f"argus approve {job.id} --sha {sha}"], forget, None
        if state == rj.REVIEW_READY:
            return WAITING, f"item {item['n']}: review package of {job.id} waits to be read and applied", \
                [f"argus status {job.id}   (patch sha)", f"argus apply {job.id} --read-sha <patch sha>"], forget, None
        return WAITING, f"item {item['n']}: job {job.id} is {state}", [f"argus resume {job.id}"], forget, None
    return DONE, "", [], forget, None


def committed_nano(job):
    """What the job holds of the queue's money: what it spent if it cannot spend again, else its whole cap (nano)."""
    return rj.spent_nano(job) if job.data["state"] in SPENT_ONLY else to_nano(job.data["max_usd"])


def _next(q, item, commit, committed, jobs_dir, forget):
    """The first item without a started job: the status and the item to start, or why not."""
    # the money of the later items is none yet; committed counts the started ones
    left = to_nano(q["max_usd"]) - committed
    cap = to_nano(q["job_cap_usd"])
    if cap > left:
        return STOPPED, f"item {item['n']}: the money (${q['max_usd']:.2f}) leaves ${left / 1e9:.4f}, one job needs ${cap / 1e9:.2f}", [], forget, None
    try:
        here = intake.git(q["repo"], "rev-parse", "HEAD").decode().strip()
    except intake.IntakeError as e:
        return STOPPED, f"item {item['n']}: the repository: {e}", [], forget, None
    if here != commit:
        return STOPPED, f"item {item['n']}: HEAD moved ({here[:12]}, expected {commit[:12]})", [], forget, None
    return RUNNING_NEXT, f"item {item['n']} is next", [], forget, {"item": item, "commit": commit}


def status_lines(q, *, jobs_dir=None):
    status, detail, actions, _, nxt = derive(q)
    status = WAITING if status == RUNNING_NEXT else status
    head = f"queue {q['id']} {status} on {q['name']} ({len(q['items'])} issues, up to ${q['max_usd']:.2f}, ${q['job_cap_usd']:.2f} per job)"
    lines = [head, *([detail] if detail else []), *[f"  {a}" for a in actions]]
    if nxt:
        lines.append(f"  argus queue step {q['id']}   (starts it: one drafter run)")
    return "\n".join(lines)


def status(qid, *, queues_dir=QUEUES, jobs_dir=None):
    return status_lines(_load(_dir(queues_dir, qid), qid))


# ---- step ---------------------------------------------------------------------------------------------------------

def step(qid, *, cfg, deps, queues_dir=QUEUES, jobs_dir=rj.JOBS):
    """At most one drafter run. Returns the text for the human. Never approves, applies, pushes or merges."""
    with _locked(queues_dir, qid) as (d, q):
        if q.get("closed"):
            raise Refused(f"queue {qid} is closed")
        if not q.get("approved") or q["approved"].get("sha") != list_sha(q):
            raise Refused(f"queue {qid} is not approved, or its list changed since (approve with `argus queue go`); nothing was started")
        if Path(jobs_dir).resolve() != Path(q["jobs_dir"]):
            raise Refused(f"queue {qid} belongs to the jobs directory {q['jobs_dir']}, not {Path(jobs_dir).resolve()}; nothing was started")
        if not 0 < q["job_cap_usd"] <= ri.CODE_MAX_USD:
            raise Refused("the queue's job cap is more than issue_writer allows; nothing was started")
        for item in q["items"]:
            _issue_text(d, item)
        status, detail, actions, forget, nxt = derive(q)
        for item in forget:                             # B1: a job that ended before its first stage is not the item's
            job = _open(item, jobs_dir)
            if job is not None and job.data["state"] == rj.NEW:
                rj.abandon(job.id, "queue: the start did not reach its first stage", deps=deps, jobs_dir=jobs_dir)
            item["job"] = None
        if forget:
            _save(d, q)
        if nxt is None:
            return status_lines(q)
        item = nxt["item"]
        job_id = rj.new_job_id()
        item["job"], item["at"] = job_id, deps.clock()  # recorded before the job exists: a start cut off never starts a second one
        _save(d, q)
        try:
            rj.start_code(repo=q["repo"], commit=nxt["commit"], issue=_issue_text(d, item), cfg=cfg, deps=deps,
                          max_usd=q["job_cap_usd"], jobs_dir=jobs_dir, job_id=job_id,
                          environment=q["environment"])
        except rj.Refused:
            raise                                       # the id stays recorded: the next step settles it (forget, abandon NEW)
        return status_lines(q)
