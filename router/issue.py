"""A job of kind "issue" (docs/reviews/SPEC_ISSUE_WRITER.md section 3): a conversation with the issue writer.

  argus issue new --repo NAME --message-file F     a job, the human's first message, then the writer's turn w1
  argus issue reply JOB --message-file F           the human's next message, then the next turn
  argus issue start JOB --sha SHA                  a code job (`argus code`) from the last issue, the one the human saw

  NEW -> WRITING (wN) -> AWAITING_HUMAN -> WRITING (reply) -> ... ; WRITING -> WRITE_FAILED (a reply tries again)
  AWAITING_HUMAN -> HANDED_OFF (start: a code job exists from the issue; the issue job ends there)
  BLOCKED when a turn cannot be funded or the provider fails; every state but HANDED_OFF -> ABANDONED.

The repository is frozen when the job is made (its path and the commit HEAD is then); every turn's read tools see a copy
of that commit's tracked files, never the live repository. A human message is in job.json before its turn starts, so a
crash never loses it; a resume continues the turn that was interrupted. The job's ledgers fund every turn: a turn starts
only when what is left of the job cap funds its whole cap. job.json's log uses only the entries the public snapshot
allows (router/stage_data.py LOG_WHAT); the conversation and the issue are never published.
"""
import hashlib
import json
import math
import os
import shutil
from pathlib import Path

from acceptance import intake
from codetask import issue_writer as iw
from codetask.drafter import _write

from . import job as rj

WRITING, AWAITING_HUMAN, WRITE_FAILED, HANDED_OFF = "WRITING", "AWAITING_HUMAN", "WRITE_FAILED", "HANDED_OFF"
NEW, BLOCKED, ABANDONED = rj.NEW, rj.BLOCKED, rj.ABANDONED
LEGAL = {(NEW, WRITING), (NEW, BLOCKED), (WRITING, AWAITING_HUMAN), (WRITING, WRITE_FAILED), (WRITING, BLOCKED),
         (AWAITING_HUMAN, WRITING), (WRITE_FAILED, WRITING), (AWAITING_HUMAN, HANDED_OFF)} | \
        {(s, ABANDONED) for s in (NEW, WRITING, AWAITING_HUMAN, WRITE_FAILED, BLOCKED)}
REPLYABLE = (AWAITING_HUMAN, WRITE_FAILED)
ISSUE = "issue.txt"
CODE_MAX_USD = 1.00             # K3: a code job started from an issue job never has a larger cap (checked on the config)



def _settings(cfg):
    if "issue_writer" not in cfg:
        raise rj.Refused("the config has no issue_writer section; nothing was started")
    return cfg["issue_writer"]


def repo_of(cfg, name):
    """(path, environment) of a repository the writer may read (K2), or Refused: never a path from the caller."""
    repos = _settings(cfg).get("repos") or {}
    if not isinstance(name, str) or name not in repos:
        raise rj.Refused(f"repository {name!r} is not one of issue_writer.repos ({', '.join(sorted(repos))}); "
                         "nothing was started")
    r = repos[name]
    return str(Path(r["path"]).expanduser()), r["environment"]


def message_problem(cfg, text, first):
    hi = int(_settings(cfg)["message_max" if first else "reply_max"])
    return iw.text_problem(text, "the message", hi)


def _preflight(cfg, cap):
    """The writer's model is priced and allowed, its limits hold for it, and a whole turn fits the job cap: checked
    before anything is created or paid."""
    from harness.llm import check_priced
    from models import gateway
    from models.registry import ConfigError, ModelRef
    s = _settings(cfg)
    role = s["role"]
    if role not in cfg.get("roles", {}):
        raise rj.Refused(f"issue_writer.role {role!r} is not in the config; nothing was started")
    turn = float(s["turn"]["cap_usd"])
    if not (math.isfinite(cap) and cap + 1e-9 >= turn):
        raise rj.Refused(f"the job cap ${cap:.2f} does not fund one turn (${turn:.2f}); nothing was started")
    scfg = rj.stage_config(cfg, turn)
    try:
        ref = ModelRef.parse(scfg["roles"][role]["model"])
        check_priced(scfg, ref, f"issue writer (role {role!r})")
        gateway.check_use(scfg, role, ref)
        iw.settings(scfg)
    except (ConfigError, KeyError, ValueError) as e:
        raise rj.Refused(f"issue writer (role {role!r}): {e}; nothing was started") from e


def _screen(job, cfg, what):
    s = _settings(cfg)
    i = job.data["inputs"]
    return "\n".join([
        f"issue writer: {what} for job {job.id}",
        f"repository {i['repo_name']} at {i['commit'][:12]} (read-only copy), environment {i['environment']}",
        f"model {cfg['roles'][s['role']]['model']}; turn cap ${float(s['turn']['cap_usd']):.2f}; "
        f"job cap ${job.data['max_usd']:.2f}, spent ${rj.spent_nano(job) / 1e9:.4f}",
        "the repository's files and the conversation go to the model provider"])


def new(*, repo, message, cfg, deps, jobs_dir=rj.JOBS, job_id=None, via=None):
    """A new issue job with the human's first message, then the writer's first turn. Returns the job."""
    s = _settings(cfg)
    path, env = repo_of(cfg, repo)
    why = message_problem(cfg, message, first=True)
    if why:
        raise rj.Refused(f"{why}; nothing was started")
    if via is not None and via not in rj.VIA:
        raise rj.Refused(f"via {via!r} is not one of {', '.join(rj.VIA)}; nothing was started")
    cap = float(s["max_usd"])
    _preflight(cfg, cap)
    try:
        commit = intake.git(path, "rev-parse", "--verify", "HEAD^{commit}").decode().strip()
    except intake.IntakeError as e:
        raise rj.Refused(f"repository {repo}: {e}; nothing was started") from e
    job_id = job_id or rj.new_job_id()
    if not rj.JOB_ID.match(job_id):
        raise rj.Refused(f"{job_id!r} is not a job id")
    job = rj.Job(Path(jobs_dir) / job_id)
    if job.file.exists():
        raise rj.Refused(f"job {job_id} already exists")
    with job.lock():
        job.data = {"job": job_id, "kind": "issue", "state": NEW, "created_at": deps.clock(), "max_usd": cap,
                    "inputs": {"repo": path, "repo_name": repo, "commit": commit, "environment": env},
                    "conversation": [{"from": "human", "at": deps.clock(), "text": message.strip()}],
                    "stages": {}, "log": []}
        job.note(deps, "created", by=os.environ.get("USER"), **({"via": via} if via else {}))
        try:
            with rj.live(deps, rj.stage_config(cfg, float(s["turn"]["cap_usd"])), [s["role"]],
                         _screen(job, cfg, "first turn"), job=job):
                job.move(WRITING, deps, stage=_next_sid(job))
                _turn(job, cfg, deps)
        except rj.Refused:
            if job.data["state"] == NEW:
                job.move(ABANDONED, deps, reason="not started: not confirmed or no key")
            raise
    return job


def reply(job_id, message, *, cfg, deps, jobs_dir=rj.JOBS, via=None):
    """The human's next message, recorded before its turn starts, then the writer's next turn. Returns the job."""
    job = rj.open_job(job_id, jobs_dir)
    with job.lock():
        if job.data.get("kind") != "issue":
            raise rj.Refused(f"job {job.id} is not an issue job; nothing was started")
        if job.data["state"] not in REPLYABLE:
            raise rj.Refused(f"job {job.id} is {job.data['state']}: a reply is taken when the writer waits for the human "
                             "(AWAITING_HUMAN) or its last turn failed (WRITE_FAILED)")
        why = message_problem(cfg, message, first=False)
        if why:
            raise rj.Refused(f"{why}; nothing was started")
        if via is not None and via not in rj.VIA:
            raise rj.Refused(f"via {via!r} is not one of {', '.join(rj.VIA)}; nothing was started")
        _preflight(cfg, job.data["max_usd"])
        s = _settings(cfg)
        left = rj.left_usd(job)
        if left + 1e-12 < float(s["turn"]["cap_usd"]):        # before the limits, the confirmation and the key
            raise rj.Refused(f"job {job.id}: ${left:.4f} of the job cap is left, less than one turn "
                             f"(${float(s['turn']['cap_usd']):.2f}); nothing was started")
        with rj.live(deps, rj.stage_config(cfg, float(s["turn"]["cap_usd"])), [s["role"]],
                     _screen(job, cfg, "next turn"), job=job):
            job.data["conversation"].append({"from": "human", "at": deps.clock(), "text": message.strip()})
            job.move(WRITING, deps, stage=_next_sid(job), by=os.environ.get("USER"), **({"via": via} if via else {}))
            _turn(job, cfg, deps)
    return job


def resume(job, cfg, deps):
    """Continue the turn a crash interrupted (the caller holds the job's lock)."""
    if job.data["state"] != WRITING:
        raise rj.Refused(f"job {job.id} is {job.data['state']}: nothing to resume")
    s = _settings(cfg)
    _preflight(cfg, job.data["max_usd"])
    with rj.live(deps, rj.stage_config(cfg, float(s["turn"]["cap_usd"])), [s["role"]],
                 _screen(job, cfg, "resume the turn"), job=job):
        _turn(job, cfg, deps)
    return job


def _turns(job):
    return sorted((k for k, v in job.data["stages"].items() if v["kind"] == "write"), key=lambda k: int(k[1:]))


def _next_sid(job):
    """The turn the job is in: the last one when it has not ended (a resume), else the next."""
    t = _turns(job)
    if t and job.data["stages"][t[-1]].get("status") is None:
        return t[-1]
    return f"w{len(t) + 1}"


def last_issue(job):
    """(text, sha256) of the job's last written issue, or (None, None)."""
    p = job.dir / ISSUE
    if not p.exists():
        return None, None
    raw = p.read_bytes()
    return raw.decode("utf-8"), hashlib.sha256(raw).hexdigest()


def _snapshot(run_dir, repo, commit):
    """The turn's read-only view: the frozen commit's tracked files, written once into <run>/source (a resume finds it).
    IntakeError for a commit that is not plain files (a symlink, a submodule)."""
    source = Path(run_dir) / "source"
    if not source.is_dir():
        part = Path(run_dir) / "source.part"
        if part.exists():
            shutil.rmtree(part)
        part.mkdir(parents=True)
        intake.write_tree(repo, commit, part, ())
        os.replace(part, source)
    return source


def _turn(job, cfg, deps):
    """The writer's turn wN under the job's lock: funded from what the job's ledgers leave, then its result."""
    s = _settings(cfg)
    sid = _next_sid(job)
    st = job.data["stages"].get(sid)
    if st is None:
        cap = round(float(s["turn"]["cap_usd"]), 6)
        left = rj.left_usd(job)
        if left + 1e-12 < cap:
            job.move(BLOCKED, deps, stage=sid, reason=f"budget: ${left:.4f} left for {sid}, its cap is ${cap:.2f}")
            return
        job.data["stages"][sid] = {"kind": "write", "run_id": f"{job.id}-{sid}", "cap_usd": cap,
                                   "started_at": deps.clock()}
        job.note(deps, "stage_started", stage=sid)
        st = job.data["stages"][sid]
    run_id = st["run_id"]
    again = (job.runs / run_id / "checkpoints.sqlite").exists()
    previous, _ = last_issue(job)
    i = job.data["inputs"]
    inputs = {"repo": i["repo_name"], "commit": i["commit"], "environment": i["environment"],
              "conversation": [{"from": m["from"], "text": m["text"]} for m in job.data["conversation"]],
              "previous_issue": previous, "max_usd": st["cap_usd"]}
    try:
        source = _snapshot(job.runs / run_id, i["repo"], i["commit"])
    except (intake.IntakeError, OSError) as e:
        # Before any model call: a commit the copy refuses (a symlink, a submodule) would fail every resume the same way
        st.update(ended_at=deps.clock(), status=iw.BLOCKED, usd=0.0)
        job.move(BLOCKED, deps, stage=sid, reason=f"the repository cannot be copied: {e}")
        return
    deps.echo(rj.running(job, f"issue writer {sid}", run_id))
    scfg = rj.stage_config(cfg, st["cap_usd"])
    r = iw.run_writer(run_id=run_id, runs_dir=job.runs, cfg=scfg, inputs=inputs, resume=again, models=deps.models,
                      prepare=lambda run_dir: source)
    deps.echo(f"{sid} finished: {r.get('status')} (${r.get('usd_billed', 0):.4f})")
    # The turn's end is ONE save (the move): the stage's status, the issue and the reply together. A crash before it
    # leaves the stage open, and a resume replays the run from its committed result, never buying a turn again.
    st.update(ended_at=deps.clock(), status=r.get("status"), usd=r.get("usd_billed"))
    if r.get("status") != iw.WRITTEN:
        job.move(BLOCKED if r.get("status") == iw.BLOCKED else WRITE_FAILED, deps, stage=sid,
                 reason=r.get("stop_reason"))
        return
    w = r["written"]
    _write(job.runs / run_id / ISSUE, w["issue"])
    _write(job.dir / ISSUE, w["issue"])
    sha = hashlib.sha256(w["issue"].encode("utf-8")).hexdigest()
    job.data["conversation"].append({"from": "writer", "at": deps.clock(), "stage": sid, "text": w["reply"],
                                     "issue_sha256": sha, "clashes": w["clashes"], "questions": w["questions"]})
    job.data["issue_sha256"] = sha
    job.move(AWAITING_HUMAN, deps, stage=sid)


def start(job_id, *, sha, cfg, deps, jobs_dir=rj.JOBS, via=None):
    """A code job from the job's last issue, the one the human saw (sha: 12+ hex of its sha256), on the frozen commit and
    the repository's environment, with issue_writer.code_max_usd. The code job's id is recorded before it is started,
    so a start cut off by a crash never starts a second one: the next start finds it and hands off to it. Returns
    (issue job, code job)."""
    job = rj.open_job(job_id, jobs_dir)
    with job.lock():
        if job.data.get("kind") != "issue":
            raise rj.Refused(f"job {job.id} is not an issue job; nothing was started")
        if job.data["state"] != AWAITING_HUMAN:
            raise rj.Refused(f"job {job.id} is {job.data['state']}: an issue is started when the writer waits for the "
                             "human (AWAITING_HUMAN)")
        if via is not None and via not in rj.VIA:
            raise rj.Refused(f"via {via!r} is not one of {', '.join(rj.VIA)}; nothing was started")
        text, seen = last_issue(job)
        if text is None or seen != job.data.get("issue_sha256"):
            raise rj.Refused(f"job {job.id}: the issue file is missing or is not the one the writer wrote; nothing was "
                             "started")
        if not isinstance(sha, str) or not rj.SHA_SEEN.fullmatch(sha) or not seen.startswith(sha):
            raise rj.Refused(f"the issue is {seen[:12]}, not the {sha!r} given: start the issue status shows (at least "
                             "its first 12 characters); nothing was started")
        cap = float(_settings(cfg)["code_max_usd"])
        if not (0 < cap <= CODE_MAX_USD):
            raise rj.Refused(f"issue_writer.code_max_usd must be more than 0 and at most ${CODE_MAX_USD:.2f}; nothing "
                             "was started")
        handed = _handed(job, jobs_dir)
        if handed is not None:                      # a start cut off after the code job was made: hand off to it
            job.move(HANDED_OFF, deps, reason=f"code job {handed.id}")
            return job, handed
        code_id = rj.new_job_id()
        job.data["handoff"] = {"job": code_id, "issue_sha256": seen, "at": deps.clock(),
                               **({"via": via} if via else {})}
        job.save()
        i = job.data["inputs"]
        try:
            rj.start_code(repo=i["repo"], commit=i["commit"], issue=text, cfg=cfg, deps=deps, max_usd=cap,
                          jobs_dir=jobs_dir, job_id=code_id, environment=i["environment"])
        except rj.Refused:
            handed = _handed(job, jobs_dir)
            if handed is None:
                job.data.pop("handoff", None)
                job.save()
            else:
                job.move(HANDED_OFF, deps, reason=f"code job {handed.id}")
            raise
        job.move(HANDED_OFF, deps, reason=f"code job {code_id}")
        return job, rj.open_job(code_id, jobs_dir)


def _handed(job, jobs_dir):
    """The code job the issue was handed to, when one was made and not abandoned before it started; else None."""
    h = job.data.get("handoff")
    if not h:
        return None
    try:
        code = rj.open_job(h["job"], jobs_dir)
    except rj.Refused:
        return None
    if code.data.get("state") == rj.ABANDONED and not code.data.get("stages"):
        return None
    return code


def moved(job):
    """How many commits the repository's HEAD is past the frozen commit (0 when it is that commit), or None when that
    cannot be told (the commit is not an ancestor any more, or git fails)."""
    i = job.data["inputs"]
    try:
        out = intake.git(i["repo"], "rev-list", "--count", f"{i['commit']}..HEAD").decode().strip()
        intake.git(i["repo"], "merge-base", "--is-ancestor", i["commit"], "HEAD")
        return int(out)
    except (intake.IntakeError, ValueError):
        return None


def status_lines(job):
    """The issue job for `argus status`: the last reply, the issue file, the clashes and questions, what comes next."""
    d = job.data
    out = [f"repository {d['inputs']['repo_name']} at {d['inputs']['commit'][:12]}, environment "
           f"{d['inputs']['environment']}; {len(_turns(job))} turn(s)"]
    writer = [m for m in d.get("conversation") or [] if m["from"] == "writer"]
    if writer:
        last = writer[-1]
        out += [f"issue {str(d.get('issue_sha256'))[:12]}: {job.dir / ISSUE}", f"reply ({last['stage']}): {last['text']}"]
        out += [f"clash: {c['file']}:{c['line']} {c['why']}" for c in last["clashes"]]
        out += [f"question: {q}" for q in last["questions"]]
    if d.get("handoff"):
        out.append(f"handed off to code job {d['handoff']['job']}: argus status {d['handoff']['job']}")
    if d["state"] == AWAITING_HUMAN:
        n = moved(job)
        if n is None or n > 0:
            out.append("the repository moved since the issue was written: "
                       + (f"{n} commit(s)" if n is not None else "the frozen commit is no longer below HEAD")
                       + "; start still uses the frozen commit")
        out.append(f"next: argus issue start {job.id} --sha {str(d.get('issue_sha256'))[:12]}")
    if d["state"] in REPLYABLE:
        out.append(f"next: argus issue reply {job.id} --message-file <file>  |  argus abandon {job.id} \"<why>\"")
    return out
