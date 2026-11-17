"""A job of kind "prd" (docs/reviews/SPEC_PRD_WRITER.md section 4): a conversation with the PRD writer.

  argus prd new --repo NAME --message-file F     a job, the human's first message, then the writer's turn w1
  argus prd reply JOB --message-file F [--rebase]  the human's next message, then the next turn
  (status, abandon, resume are the ordinary `argus status|abandon|resume`; the folder is checked and approved by the
  ordinary `argus prd check|approve`, which this module never calls and never bypasses)

  NEW -> WRITING (wN) -> AWAITING_HUMAN -> WRITING (reply) -> ... ; WRITING -> WRITE_FAILED (a reply tries again)
  BLOCKED when a turn cannot be funded, the repository's state refuses it or the provider fails; every state but
  ABANDONED -> ABANDONED. There is no HANDED_OFF and no "approved": `argus prd approve` makes a queue from a folder and
  leaves the job as it is (it can still be replied to, until a queue is waiting on the repository).

Every turn's folder is jobs/<id>/prd-wN/ (PRD.md, issues.json, issue-N.md: the bytes the gate checked), written as
prd-wN.part and renamed, so a crash never leaves half a folder and a resume writes the same one. A folder a later turn or
an abandon replaces gets a file SUPERSEDED: `argus prd approve` refuses a folder with a file it does not know.
"""
import hashlib
import os
import shutil
from pathlib import Path

from acceptance import intake
from codetask import issue_writer as iw
from codetask import prd_writer as pw

from . import issue as ri
from . import job as rj
from . import prd as rp
from . import queue as rq

NEW, WRITING, AWAITING_HUMAN, WRITE_FAILED = rj.NEW, ri.WRITING, ri.AWAITING_HUMAN, ri.WRITE_FAILED
BLOCKED, ABANDONED = rj.BLOCKED, rj.ABANDONED
SECTION = "prd_writer"          # the config section that holds the writer's role, caps and limits
LEGAL = {(NEW, WRITING), (NEW, BLOCKED), (WRITING, AWAITING_HUMAN), (WRITING, WRITE_FAILED), (WRITING, BLOCKED),
         (AWAITING_HUMAN, WRITING), (WRITE_FAILED, WRITING)} | \
        {(s, ABANDONED) for s in (NEW, WRITING, AWAITING_HUMAN, WRITE_FAILED, BLOCKED)}
REPLYABLE = (AWAITING_HUMAN, WRITE_FAILED)
MARK = "SUPERSEDED"


def _settings(cfg):
    return ri._settings(cfg, SECTION)


def message_problem(cfg, text, first):
    return iw.text_problem(text, "the message", int(_settings(cfg)["message_max" if first else "reply_max"]))


def _preflight(cfg, cap):
    ri._preflight(cfg, cap, SECTION)


def _repo_state(cfg, repo_name, commit, queues_dir, jobs_dir):
    """The repository's side of a queue made from this PRD, checked with the queue's own validator and a placeholder issue,
    before any model call: HEAD is still the frozen commit, no unfinished queue on the repository, the config holds. Raises
    Refused. The model cannot fix any of this, so it is never sent to it (SPEC_PRD_WRITER 3.5)."""
    cap = float(ri._settings(cfg)["code_max_usd"])
    rq.validate_new(repo=repo_name, commit=commit, max_usd=cap, issues=["preflight"], cfg=cfg, queues_dir=queues_dir,
                    jobs_dir=jobs_dir)


def max_usd_for(cfg, n):
    """The queue's money a PRD of n issues proposes: n jobs' caps, at most the queue ceiling. The harness sets it."""
    return min(rq.QUEUE_MAX_USD, n * float(ri._settings(cfg)["code_max_usd"]))


def _valid(job):
    """The job.json of a PRD job holds what this module writes, in the types it writes (SPEC_PRD_WRITER 4.7); a damaged one
    is Refused, never half-read. (No job kind checks its keys today: this one does.)"""
    d = job.data
    i = d.get("inputs")
    ok = (isinstance(i, dict) and all(isinstance(i.get(k), str) for k in ("repo", "repo_name", "commit", "environment"))
          and isinstance(d.get("conversation"), list) and isinstance(d.get("stages"), dict)
          and isinstance(d.get("prd_turns", []), list)
          and all(isinstance(t, dict) and isinstance(t.get("turn"), str) and isinstance(t.get("folder_sha"), str)
                  and isinstance(t.get("items"), int) for t in d.get("prd_turns", []))
          and (d.get("repo_notes") is None or isinstance(d.get("repo_notes"), str)))
    if not ok:
        raise rj.Refused(f"job {job.id}: job.json is not a PRD job's (a key is missing or of the wrong type); nothing was started")


def _screen(job, cfg, what):
    s = _settings(cfg)
    i = job.data["inputs"]
    return "\n".join([
        f"PRD writer: {what} for job {job.id}",
        f"repository {i['repo_name']} at {i['commit'][:12]} (read-only copy), environment {i['environment']}",
        f"model {cfg['roles'][s['role']]['model']}; turn cap ${float(s['turn']['cap_usd']):.2f}; "
        f"job cap ${job.data['max_usd']:.2f}, spent ${rj.spent_nano(job) / 1e9:.4f}",
        "the repository's files and the conversation go to the model provider",
        *(["example code written by the model RUNS in the sandbox (RunExample and the gate of the first issue: no network, the "
           f"repository read-only, image {str(job.data.get('environment_image'))[:19]}); the turn is no longer read-only"]
          if iw.has_runner(cfg, i["environment"]) else [])])


def new(*, repo, message, cfg, deps, jobs_dir=rj.JOBS, queues_dir=rq.QUEUES, job_id=None):
    """A new PRD job with the human's first message, then the writer's first turn. Returns the job."""
    s = _settings(cfg)
    path, env = ri.repo_of(cfg, repo)
    why = message_problem(cfg, message, first=True)
    if why:
        raise rj.Refused(f"{why}; nothing was started")
    cap = float(s["max_usd"])
    _preflight(cfg, cap)
    try:
        commit = intake.git(path, "rev-parse", "--verify", "HEAD^{commit}").decode().strip()
    except intake.IntakeError as e:
        raise rj.Refused(f"repository {repo}: {e}; nothing was started") from e
    _repo_state(cfg, repo, commit, queues_dir, jobs_dir)
    job_id = job_id or rj.new_job_id()
    if not rj.JOB_ID.match(job_id):
        raise rj.Refused(f"{job_id!r} is not a job id")
    job = rj.Job(Path(jobs_dir) / job_id)
    if job.file.exists():
        raise rj.Refused(f"job {job_id} already exists")
    with job.lock():
        if job.data is not None:
            raise rj.Refused(f"job {job_id} already exists")
        job.data = {"job": job_id, "kind": "prd", "state": NEW, "created_at": deps.clock(), "max_usd": cap,
                    "inputs": {"repo": path, "repo_name": repo, "commit": commit, "environment": env},
                    "conversation": [{"from": "human", "at": deps.clock(), "text": message.strip()}],
                    "stages": {}, "log": [], "prd_turns": [], "queues_dir": str(queues_dir)}
        job.note(deps, "created", by=os.environ.get("USER"))
        try:
            ri._pin_environment(job, cfg)
            with rj.live(deps, rj.stage_config(cfg, float(s["turn"]["cap_usd"])), [s["role"]],
                         _screen(job, cfg, "first turn"), job=job):
                job.move(WRITING, deps, stage=ri._next_sid(job))
                _turn(job, cfg, deps, queues_dir)
        except rj.Refused:
            if job.data["state"] == NEW:
                job.move(ABANDONED, deps, reason="not started: not confirmed or no key")
            raise
    return job


def reply(job_id, message, *, cfg, deps, jobs_dir=rj.JOBS, queues_dir=rq.QUEUES, rebase=False):
    """The human's next message, recorded before its turn starts, then the writer's next turn. rebase: the commit is frozen
    again at the repository's HEAD now, the notes (about the old commit) are dropped and the whole gate runs again."""
    job = rj.open_job(job_id, jobs_dir)
    with job.lock():
        if job.data.get("kind") != "prd":
            raise rj.Refused(f"job {job.id} is not a PRD job; nothing was started")
        _valid(job)
        if job.data["state"] not in REPLYABLE:
            raise rj.Refused(f"job {job.id} is {job.data['state']}: a reply is taken when the writer waits for the human "
                             "(AWAITING_HUMAN) or its last turn failed (WRITE_FAILED)")
        why = message_problem(cfg, message, first=False)
        if why:
            raise rj.Refused(f"{why}; nothing was started")
        _preflight(cfg, job.data["max_usd"])
        i = job.data["inputs"]
        commit = i["commit"]
        if rebase:
            try:
                commit = intake.git(i["repo"], "rev-parse", "--verify", "HEAD^{commit}").decode().strip()
            except intake.IntakeError as e:
                raise rj.Refused(f"repository {i['repo_name']}: {e}; nothing was started") from e
        _repo_state(cfg, i["repo_name"], commit, queues_dir, Path(jobs_dir))
        s = _settings(cfg)
        left = rj.left_usd(job)
        if left + 1e-12 < float(s["turn"]["cap_usd"]):
            raise rj.Refused(f"job {job.id}: ${left:.4f} of the job cap is left, less than one turn "
                             f"(${float(s['turn']['cap_usd']):.2f}); nothing was started")
        ri._pin_environment(job, cfg)
        with rj.live(deps, rj.stage_config(cfg, float(s["turn"]["cap_usd"])), [s["role"]],
                     _screen(job, cfg, "next turn"), job=job):
            if rebase:
                i["commit"] = commit
                job.data["repo_notes"] = None
            job.data["conversation"].append({"from": "human", "at": deps.clock(), "text": message.strip()})
            job.move(WRITING, deps, stage=ri._next_sid(job), by=os.environ.get("USER"))
            if rebase:
                mark_superseded(job)            # the folders of the old commit can no longer be the one to check
            job.data["queues_dir"] = str(queues_dir)
            _turn(job, cfg, deps, queues_dir)
    return job


def resume(job, cfg, deps, queues_dir=None):
    """Continue the turn a crash interrupted (the caller holds the job's lock)."""
    if job.data["state"] != WRITING:
        raise rj.Refused(f"job {job.id}: {job.data['state']}: nothing to resume")
    _valid(job)
    s = _settings(cfg)
    queues = Path(queues_dir or job.data.get("queues_dir") or rq.QUEUES)     # the directory `new` and `reply` were given
    _preflight(cfg, job.data["max_usd"])
    i = job.data["inputs"]
    _repo_state(cfg, i["repo_name"], i["commit"], queues, job.dir.parent)    # before the key, the confirmation and the money
    ri._pin_environment(job, cfg)
    with rj.live(deps, rj.stage_config(cfg, float(s["turn"]["cap_usd"])), [s["role"]],
                 _screen(job, cfg, "resume the turn"), job=job):
        _turn(job, cfg, deps, queues)
    return job


def folder_of(job, sid):
    return job.dir / f"prd-{sid}"


def _write_folder(job, sid, files):
    """prd-<sid>/ from the checked bytes: written aside and renamed, so a crash leaves no half folder and a resume (which
    runs this again with the same bytes) leaves exactly one."""
    final, part = folder_of(job, sid), job.dir / f"prd-{sid}.part"
    for p in (part, final):
        if p.exists():
            shutil.rmtree(p)
    part.mkdir()
    for name, data in files.items():
        (part / name).write_bytes(data)
    os.replace(part, final)


def mark_superseded(job, keep=None):
    """A file SUPERSEDED in every folder of the job but `keep`: read_folder refuses a folder with a file it does not know,
    so `argus prd approve` refuses these (B1 itself is unchanged)."""
    for d in sorted(job.dir.glob("prd-w*")):
        if d.is_dir() and not d.name.endswith(".part") and d.name != (f"prd-{keep}" if keep else None) \
                and not (d / MARK).exists():
            (d / MARK).write_text("a later turn or an abandon replaced this folder: do not approve it\n")


def _previous(job):
    """{prd_md, issues} of the job's last folder, as the writer wrote it, or None."""
    turns = job.data.get("prd_turns") or []
    if not turns:
        return None
    d = folder_of(job, turns[-1]["turn"])
    try:
        n = turns[-1]["items"]
        return {"prd_md": (d / "PRD.md").read_text("utf-8"),
                "issues": [(d / f"issue-{k}.md").read_text("utf-8") for k in range(1, n + 1)],
                "stale": turns[-1].get("commit") != job.data["inputs"]["commit"]}
    except (OSError, UnicodeDecodeError):
        return None


def _turn(job, cfg, deps, queues_dir):
    """The writer's turn wN under the job's lock: funded from what the job's ledgers leave, then its result."""
    s = _settings(cfg)
    sid = ri._next_sid(job)
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
    i = job.data["inputs"]
    inputs = {"repo": i["repo_name"], "commit": i["commit"], "environment": i["environment"],
              "conversation": [{"from": m["from"], "text": m["text"]} for m in job.data["conversation"]],
              "previous": _previous(job), "notes": job.data.get("repo_notes"), "max_usd": st["cap_usd"]}
    try:
        source = ri._snapshot(job.runs / run_id, i["repo"], i["commit"])
    except (intake.IntakeError, OSError) as e:
        st.update(ended_at=deps.clock(), status=iw.BLOCKED, usd=0.0)
        job.move(BLOCKED, deps, stage=sid, reason=f"the repository cannot be copied: {e}")
        return
    jobs_dir = job.dir.parent

    def finish(result):
        files = pw.folder_files(result, repo=i["repo_name"], commit=i["commit"],
                                max_usd=max_usd_for(cfg, len(result["items"])))
        found, parsed = rp.check(files, cfg=cfg, queues_dir=queues_dir, jobs_dir=jobs_dir)
        blocks = [t for level, t in found if level == rp.BLOCK]
        if not blocks:
            return [], None
        if parsed is None or parsed["valid"] is None:
            try:
                _repo_state(cfg, i["repo_name"], i["commit"], queues_dir, jobs_dir)
            except rj.Refused as e:
                return [], str(e)
        return blocks, None

    deps.echo(rj.running(job, f"PRD writer {sid}", run_id))
    scfg = rj.stage_config(cfg, st["cap_usd"])
    r = pw.run_prd_writer(run_id=run_id, runs_dir=job.runs, cfg=scfg, inputs=inputs, resume=again, models=deps.models,
                          prepare=lambda run_dir: source, finish=finish,
                          item_max=int(ri._settings(cfg)["message_max"]), example_runner=deps.example_runner)
    deps.echo(f"{sid} finished: {r.get('status')} (${r.get('usd_billed', 0):.4f})")
    st.update(ended_at=deps.clock(), status=r.get("status"), usd=r.get("usd_billed"), rejections=r.get("rejections") or {})
    if r.get("status") != iw.WRITTEN:
        job.move(BLOCKED if r.get("status") == iw.BLOCKED else WRITE_FAILED, deps, stage=sid,
                 reason=r.get("stop_reason"))
        return
    w = r["written"]
    if w.get("notes"):
        job.data["repo_notes"] = w["notes"]
    if not w["items"]:                              # a reply only: the last folder (if any) stays the one to check
        job.data["conversation"].append({"from": "writer", "at": deps.clock(), "stage": sid, "text": w["reply"],
                                         "questions": w["questions"]})
        job.move(AWAITING_HUMAN, deps, stage=sid)
        return
    files = pw.folder_files(w, repo=i["repo_name"], commit=i["commit"], max_usd=max_usd_for(cfg, len(w["items"])))
    found, _ = rp.check(files, cfg=cfg, queues_dir=queues_dir, jobs_dir=jobs_dir)
    blocks = [t for level, t in found if level == rp.BLOCK]
    if blocks:      # a replayed accept (resume) is not gated again: the folder is checked once more before it is written
        try:
            _repo_state(cfg, i["repo_name"], i["commit"], queues_dir, jobs_dir)
            job.move(WRITE_FAILED, deps, stage=sid, reason="the folder no longer passes the check: " + "; ".join(blocks)[:300])
        except rj.Refused as e:
            job.move(BLOCKED, deps, stage=sid, reason=str(e)[:300])
        return
    sha = rp.folder_sha(files)
    _write_folder(job, sid, files)
    turn = {"turn": sid, "folder_sha": sha, "commit": i["commit"], "items": len(w["items"]), "submits": r.get("submits"),
            "rejections": r.get("rejections") or {}, "max_usd": max_usd_for(cfg, len(w["items"])),
            "touches": [it["touches"] for it in w["items"]], "creates": [it["creates"] for it in w["items"]],
            "clashes": [it["clashes"] for it in w["items"]],
            "examples": [it.get("examples") for it in w["items"]],          # the cards' data (T2): per item, what each example did
            "warnings": [t for level, t in found if level == rp.WARN]}
    job.data["prd_turns"] = [t for t in job.data.get("prd_turns", []) if t["turn"] != sid] + [turn]
    mark_superseded(job, keep=sid)
    job.data["conversation"].append({"from": "writer", "at": deps.clock(), "stage": sid, "text": w["reply"],
                                     "folder_sha": sha, "questions": w["questions"]})
    job.move(AWAITING_HUMAN, deps, stage=sid)


def status_lines(job):
    """The PRD job for `argus status`: the last reply, the folder with the line that checks it, what the writer named."""
    d = job.data
    i = d.get("inputs") or {}
    out = [f"repository {i.get('repo_name')} at {str(i.get('commit'))[:12]}, environment {i.get('environment')}; "
           f"{len(ri._turns(job))} turn(s)"]
    queues = Path(d.get("queues_dir") or rq.QUEUES)
    writer = [m for m in d.get("conversation") or [] if m["from"] == "writer"]
    if writer:
        out.append("last reply: " + writer[-1]["text"])
    turns = d.get("prd_turns") or []
    here = job.dir.resolve()
    if turns and turns[-1].get("commit") != i.get("commit"):
        out.append("no folder for this commit yet (the repository was rebased after the last folder): reply to write one")
    elif turns:
        t = turns[-1]
        folder = folder_of(job, t["turn"]).resolve()
        out += [f"folder {t['folder_sha'][:12]}: {folder} ({t['items']} issue(s), {t.get('submits')} submit(s); "
                f"rejections {t.get('rejections') or {}}); proposed queue money ${t.get('max_usd', 0):.2f}",
                f"read: {folder}/PRD.md and issue-1.md ... issue-{t['items']}.md",
                f"check it: argus prd check {folder}"]
        for n, (touch, make, clash) in enumerate(zip(t["touches"], t["creates"], t["clashes"]), 1):
            title = ""
            try:
                title = (folder / f"issue-{n}.md").read_text("utf-8").split("\n", 1)[0]
            except OSError:
                pass
            out.append(f"  issue {n} {title!r}: touches {touch}; creates {make}; {len(clash)} clash(es)"
                       + "".join(f"\n    clash {c['file']} line {c['line']}: {c['why']}" for c in clash)
                       + "".join(f"\n    {line}" for line in ri.example_lines((t.get("examples") or [None] * n)[n - 1])))
        out += [f"  warning: {w}" for w in t.get("warnings") or []]
    if turns:
        try:
            for q in rq._all(queues):
                p = (q.get("prd") or {}).get("dir")
                if p and Path(p).resolve().parent == here:
                    out.append(f"  queue {q['id']} was made from {Path(p).name}")
        except OSError:
            pass
    if writer and writer[-1].get("questions"):
        out += [f"question: {q}" for q in writer[-1]["questions"]]
    return out
