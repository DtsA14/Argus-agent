"""Router v0 (docs/reviews/SPEC_ROUTER_V0.md): a code task as one resumable job.

  argus code     a new job: intake of the target repository at a commit, then the drafter            -> AWAITING_APPROVAL
  argus approve  the human approves the draft they saw (its sha), then the agent and the review package -> REVIEW_READY
  argus reject / redraft / resume / status

A job lives in jobs/<id>/: job.json (state, inputs, stages, approval, the human's decisions with their times), its own
root (root/fixtures/...: the intake, the approved task and contract, never the Argus checkout's fixtures) and the stage
runs (runs/<id>-d1, -d2, ..., -a1). The router calls no model itself: every model call is a stage run's (run_drafter,
run_code_task), with their reservations and ledgers.

Money: a job has one cap. Before a stage starts, its cap is min(the stage's cap, the job cap minus everything the
stages' ledgers show spent, calls cut off by a crash at their worst case); a stage that cannot fund one attempt is not
started (BLOCKED). The cap is recorded in job.json when the stage starts and a resume uses that number: the run already
counts its own spend from its ledger, so recomputing it from what is left of the job would count that spend twice.

Concurrency: every command that changes a job holds an exclusive flock on jobs/<id>/.lock for as long as it runs,
stage included; a second one is refused at once, before it changes anything. status only reads.

Approval is bound to the draft the human saw: status shows the draft's sha256, approve must be given it, shows it again
with the writable files and validations before [y/N], and refuses a draft that differs; the contract sha it approves
is recorded and the agent's stage refuses a contract that differs from it.
"""
import copy
import hashlib
import json
import os
import re
import secrets
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from acceptance import contract as ct
from acceptance import draft as dr
from acceptance import intake
from harness.events import parse_lines
from harness.llm import reconcile_ledger, to_nano

ROOT = Path(__file__).resolve().parent.parent
JOBS = ROOT / "jobs"
BASE, TASK = "base", "task"                 # the intake and the task inside a job's own root

NEW, DRAFTING, DRAFT_FAILED, AWAITING_APPROVAL = "NEW", "DRAFTING", "DRAFT_FAILED", "AWAITING_APPROVAL"
AGENT_RUNNING, AGENT_FAILED, REVIEW_READY, REVIEW_INVALID = "AGENT_RUNNING", "AGENT_FAILED", "REVIEW_READY", "REVIEW_INVALID"
REJECTED, BLOCKED, ABANDONED = "REJECTED", "BLOCKED", "ABANDONED"
LEGAL = {(NEW, DRAFTING), (NEW, BLOCKED),
         (DRAFTING, AWAITING_APPROVAL), (DRAFTING, DRAFT_FAILED), (DRAFTING, BLOCKED),
         (DRAFT_FAILED, DRAFTING), (DRAFT_FAILED, REJECTED), (DRAFT_FAILED, BLOCKED),
         (DRAFT_FAILED, AGENT_RUNNING),           # an accepted draft stays approvable after a failed redraft
         (AWAITING_APPROVAL, AGENT_RUNNING), (AWAITING_APPROVAL, REJECTED), (AWAITING_APPROVAL, DRAFTING),
         (AWAITING_APPROVAL, BLOCKED),
         (AGENT_RUNNING, REVIEW_READY), (AGENT_RUNNING, REVIEW_INVALID), (AGENT_RUNNING, AGENT_FAILED),
         (AGENT_RUNNING, BLOCKED)} | \
        {(s, ABANDONED) for s in (NEW, DRAFTING, DRAFT_FAILED, AWAITING_APPROVAL, AGENT_RUNNING, AGENT_FAILED, BLOCKED)}
JOB_ID = re.compile(r"^j[0-9a-z_]{1,40}$")
KEY_SHAPE = {"anthropic": "sk-ant-"}


class Refused(Exception):
    """A command that cannot run; nothing was changed."""


class JobBusy(Refused):
    pass


def now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class Deps:
    """What a command needs from outside: the human (confirm, key, tty) and, in tests, models and the sandbox."""

    def __init__(self, *, confirm=None, get_key=None, isatty=None, models=None, validate=None, preflight=None,
                 env_preflight=None, clock=now, echo=print):
        import getpass
        import sys
        self.confirm = confirm or (lambda text: input(text + "\nLanjut? [y/N] ").strip().lower() == "y")
        self.get_key = get_key or (lambda: getpass.getpass("Type or paste the API key, then Enter (not shown): "))
        self.isatty = isatty or (lambda: sys.stdin.isatty())
        self.models, self.validate, self.preflight, self.env_preflight = models, validate, preflight, env_preflight
        self.clock, self.echo = clock, echo


# ---- the job file and its lock -----------------------------------------------------------------------------------

class Job:
    def __init__(self, path):
        self.dir = Path(path)
        self.file = self.dir / "job.json"
        self.root = self.dir / "root"
        self.runs = self.dir / "runs"
        self.data = json.loads(self.file.read_text(encoding="utf-8")) if self.file.exists() else None

    @property
    def id(self):
        return self.data["job"]

    def save(self):
        tmp = self.file.with_name(".job.json.part")
        tmp.write_text(json.dumps(self.data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        os.replace(tmp, self.file)

    def move(self, new, deps, **why):
        old = self.data["state"]
        if (old, new) not in LEGAL:
            raise Refused(f"job {self.id}: {old} -> {new} is not a legal transition")
        self.data["state"] = new
        self.note(deps, "state", old=old, new=new, **why)

    def note(self, deps, what, **detail):
        self.data.setdefault("log", []).append({"at": deps.clock(), "what": what, **detail})
        self.save()

    @contextmanager
    def lock(self):
        """An exclusive lock for a command that changes the job; refused at once if another command holds it."""
        import fcntl
        self.dir.mkdir(parents=True, exist_ok=True)
        fd = os.open(self.dir / ".lock", os.O_RDWR | os.O_CREAT, 0o644)
        try:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                raise JobBusy(f"job {self.dir.name} is in use by another command (it runs a stage or changes the job); "
                              "nothing was changed") from None
            self.data = json.loads(self.file.read_text(encoding="utf-8")) if self.file.exists() else None
            yield self
        finally:
            os.close(fd)                 # also releases the lock; a crashed process releases it the same way


def open_job(job_id, jobs_dir=JOBS):
    if not JOB_ID.match(job_id or ""):
        raise Refused(f"{job_id!r} is not a job id")
    job = Job(Path(jobs_dir) / job_id)
    if job.data is None:
        raise Refused(f"no job {job_id!r} in {jobs_dir}")
    return job


# ---- money -------------------------------------------------------------------------------------------------------

def runs_spent_nano(runs, stages):
    """What the given stage runs have spent, from their ledgers (cut-off calls at their worst case). Read only: an
    EventLog would repair a log's cut last line, and a stage may be writing that log at this moment. A run is counted
    only as a stage of the job: the router records a stage before its run starts, so no run of a job is left out.
    (Router pilot #2's thinking agent; it replaces pilot #1's agent change that also counted unrecorded run
    directories, so status and list could differ. Atha, 2026-10-23.)"""
    total = 0
    for stage in (stages or {}).values():
        log = Path(runs) / stage["run_id"] / "events.jsonl"
        if log.exists():
            total += reconcile_ledger(parse_lines(log.read_text(encoding="utf-8")))[1]["usd_nano"]
    return total


def spent_nano(job):
    """Everything the job's stage runs have spent: the number status, list and the job cap all use."""
    return runs_spent_nano(job.runs, job.data.get("stages"))


def left_usd(job):
    return (to_nano(job.data["max_usd"]) - spent_nano(job)) / 1e9


def _set(cfg, dotted, value):
    node = cfg
    *path, last = dotted.split(".")
    for k in path:
        node = node[k]
    node[last] = value


def stage_config(cfg, cap):
    """The config a stage runs with: the router's overrides, and the stage's cap as the run's budget.max_usd."""
    out = copy.deepcopy(cfg)
    for k, v in ((cfg.get("router") or {}).get("overrides") or {}).items():
        _set(out, k, v)
    out["budget"]["max_usd"] = cap
    return out


def draft_sha(path):
    return hashlib.sha256(ct.canonical(json.loads(Path(path).read_text(encoding="utf-8"))).encode()).hexdigest()


# ---- live stages: the human confirms, then types the key -----------------------------------------------------------

def _needs_key(cfg, roles):
    from models.registry import ModelRef
    out = []
    for role in roles:
        ref = ModelRef.parse(cfg["roles"][role]["model"])
        prov = (cfg.get("providers") or {}).get(ref.provider) or {}
        if prov.get("kind") != "fake":
            out.append((prov.get("api_key_env"), prov.get("kind")))
    return sorted(set(out))


@contextmanager
def live(deps, cfg, roles, text):
    """Confirm, then take each key the stage's real models need (never an argument, never written, unset after)."""
    keys = _needs_key(cfg, roles)
    if keys and not deps.isatty():
        raise Refused("a live stage needs a terminal: the key is typed, never passed")
    if not deps.confirm(text):
        raise Refused("not confirmed; nothing was started")
    set_vars = []
    try:
        for var, kind in keys:
            key = deps.get_key() or ""
            shape = KEY_SHAPE.get(kind)
            if not key:
                raise Refused("the key is empty; nothing was started")
            if re.search(r"\s", key):
                raise Refused("the key contains whitespace (pasted twice?); nothing was started")
            if shape and (not key.startswith(shape) or key[len(shape):].find(shape) != -1):
                raise Refused(f"the key does not look like one {kind} key; nothing was started")
            os.environ[var] = key
            set_vars.append(var)
        if keys:
            os.environ["ARGUS_LIVE"] = "1"
        yield bool(keys)
    finally:
        for var in set_vars + (["ARGUS_LIVE"] if keys else []):
            os.environ.pop(var, None)


def _limits_text(job, title, lines):
    spent = spent_nano(job) / 1e9
    return "\n".join([f"== {title} (job {job.id}) ==", *lines,
                      f"job cap ${job.data['max_usd']:.2f}; spent ${spent:.4f}; left ${job.data['max_usd'] - spent:.4f}"])


# ---- commands ----------------------------------------------------------------------------------------------------

def running(job, what, run_id):
    """What the human sees while a stage runs (it prints nothing else): how long, and how to continue if it stops."""
    return (f"{what} running in {run_id} (usually 1-3 minutes; it prints nothing until it ends). Do not start "
            f"another job for this task: if this stops or the terminal closes, continue it with `argus resume {job.id}`.")


def new_job_id():
    return "j" + datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S") + "_" + secrets.token_hex(2)


def start_code(*, repo, commit, issue, cfg, deps, exclude=(), max_usd=None, jobs_dir=JOBS, job_id=None):
    """A new job: intake, then the first drafter stage. Returns the job."""
    if not isinstance(issue, str) or not issue.strip():
        raise Refused("the issue is empty")
    job_id = job_id or new_job_id()
    if not JOB_ID.match(job_id):
        raise Refused(f"{job_id!r} is not a job id")
    job = Job(Path(jobs_dir) / job_id)
    if job.file.exists():
        raise Refused(f"job {job_id} already exists")
    router = cfg.get("router") or {}
    cap = float(max_usd if max_usd is not None else router.get("job_max_usd", 1.0))
    if not cap > 0:
        raise Refused("the job cap must be positive")
    with job.lock():
        job.data = {"job": job_id, "kind": "code", "state": NEW, "created_at": deps.clock(), "max_usd": cap,
                    "inputs": {"repo": str(Path(repo).resolve()), "commit": commit, "issue": issue.strip(),
                               "exclude": list(exclude)},
                    "stages": {}, "approval": None, "log": []}
        job.note(deps, "created", by=os.environ.get("USER"))
        try:
            rec = intake.intake(repo, commit, BASE, exclude=exclude, root=job.root)
        except intake.IntakeError as e:
            job.move(BLOCKED, deps, reason=f"intake: {e}")
            raise Refused(f"intake failed: {e}") from e
        job.data["intake"] = {k: rec[k] for k in ("commit", "tree", "files", "snapshot_sha256")}
        job.note(deps, "intaken", files=rec["files"])
        _draft(job, cfg, deps, 1)
    return job


def _draft(job, cfg, deps, n):
    """Start drafter stage n (its cap fixed now), or resume it with the cap it started with."""
    from codetask.drafter import DRAFTED, drafter_settings, run_drafter
    sid = f"d{n}"
    stage = job.data["stages"].get(sid)
    resume = stage is not None
    if not resume:
        cap = round(min(float((cfg.get("router") or {}).get("draft_max_usd", 0.75)), left_usd(job)), 6)
        need = drafter_settings(stage_config(cfg, 1e9))["attempt_usd"]
        if cap < need:
            job.move(BLOCKED, deps, reason=f"budget: ${cap:.4f} left for the drafter, one attempt needs ${need:.2f}")
            raise Refused(f"job {job.id}: not enough of the job cap left for a drafter (BLOCKED)")
    else:
        cap = stage["cap_usd"]                            # the cap it started with, never recomputed
    scfg = stage_config(cfg, cap)
    lim = drafter_settings(scfg)
    text = _limits_text(job, f"drafter stage {sid}" + (" (resume)" if resume else ""),
                        [f"model {scfg['roles'][scfg['drafter']['role']]['model']}; stage cap ${cap:.4f}; one attempt "
                         f"${lim['attempt_usd']:.2f}; {scfg['drafter']['max_submits']} submits",
                         f"overrides: {(cfg.get('router') or {}).get('overrides') or {}}"])
    with live(deps, scfg, [scfg["drafter"]["role"]], text):
        if not resume:
            job.data["stages"][sid] = {"kind": "draft", "run_id": f"{job.id}-{sid}", "cap_usd": cap,
                                       "started_at": deps.clock()}
            job.move(DRAFTING, deps, stage=sid)
        run_id = job.data["stages"][sid]["run_id"]
        again = (job.runs / run_id / "checkpoints.sqlite").exists()
        deps.echo(running(job, "drafter", run_id))
        r = run_drafter(run_id=run_id, runs_dir=job.runs, cfg=scfg, intake_name=BASE, issue=job.data["inputs"]["issue"],
                        max_usd=cap, resume=again, models=deps.models, validate=deps.validate,
                        preflight=deps.preflight, env_preflight=deps.env_preflight, root=job.root)
    st = job.data["stages"][sid]
    st.update(ended_at=deps.clock(), status=r["status"], usd=r["usd_billed"])
    deps.echo(f"drafter finished: {r['status']} (${r['usd_billed']:.4f})")
    if r["status"] == DRAFTED:
        st["draft_sha256"] = draft_sha(job.runs / run_id / "draft.json")
        job.move(AWAITING_APPROVAL, deps, stage=sid)
    else:
        job.move(DRAFT_FAILED, deps, stage=sid, reason=r.get("stop_reason"))
    return r


def _last_draft(job):
    drafts = [s for s in job.data["stages"].values() if s["kind"] == "draft" and s.get("status") == "DRAFTED"]
    if not drafts:
        raise Refused(f"job {job.id} has no draft")
    st = drafts[-1]
    return st, job.runs / st["run_id"] / "draft.json"


def approve(job_id, *, sha, cfg, deps, sandbox_cfg=None, max_usd=None, max_iterations=3, reference_patch=None,
            jobs_dir=JOBS):
    """Approve the draft the human saw (sha, as status shows it), then run the agent and build the review package."""
    from codetask import run as ctrun
    job = open_job(job_id, jobs_dir)
    with job.lock():
        # Router pilot #1: a redraft that failed after a draft was accepted left the job DRAFT_FAILED, and the good
        # draft could no longer be approved. A redraft is an extra attempt, not a rejection: the last accepted draft
        # stays approvable (bound to its sha as always); reject says no.
        if job.data["state"] not in (AWAITING_APPROVAL, DRAFT_FAILED):
            raise Refused(f"job {job.id} is {job.data['state']}, not AWAITING_APPROVAL")
        st, path = _last_draft(job)
        seen = draft_sha(path)
        if not sha or not seen.startswith(sha) or len(sha) < 12:
            raise Refused(f"the draft is {seen[:12]}, not the {sha!r} given: approve the draft status shows "
                          "(at least its first 12 characters)")
        draft = json.loads(path.read_text(encoding="utf-8"))
        c = draft["contract"]
        profile = c.get("budget_profile")
        router = cfg.get("router") or {}
        by_profile = router.get("agent_max_usd") or {}
        want = float(max_usd if max_usd is not None else by_profile.get(profile, by_profile.get("default", 0.5)))
        cap = round(min(want, left_usd(job)), 6)
        acfg = stage_config(ctrun.apply_profile(cfg, profile) if profile else cfg, cap)
        need = ctrun.settings(acfg)["attempt_usd"]
        lines = [f"draft {seen[:12]} (from stage {st['run_id']})",
                 "writable: " + ", ".join(c["scope"]["writable"]),
                 *[f"validation {v['id']}: {' '.join([v['executable'], *v['args']])}; required: "
                   + (", ".join(v.get("must_pass") or []) or "none") for v in c["validation"]],
                 f"tools added: {c.get('tools') or 'none'}; profile {profile}; one attempt ${need:.2f}",
                 f"agent cap ${cap:.4f}, {max_iterations} attempts; "
                 + ("reference patch given (proven)" if reference_patch else "no reference patch (unproven)")]
        if cap < need:
            job.move(BLOCKED, deps, reason=f"budget: ${cap:.4f} left for the agent, one attempt needs ${need:.2f}")
            raise Refused(f"job {job.id}: not enough of the job cap left for one agent attempt (BLOCKED)")
        text = _limits_text(job, "approve and run the agent", lines)
        with live(deps, acfg, [acfg["code_task"]["role"]], text):
            if draft_sha(path) != seen:                 # changed while the human was reading
                raise Refused("the draft changed after it was shown; nothing was approved")
            report = dr.check(draft, task=TASK, issue=job.data["inputs"]["issue"], max_usd=cap,
                              max_iterations=max_iterations, reference_patch=reference_patch,
                              sandbox_cfg=sandbox_cfg or acfg.get("sandbox") or {}, root=job.root,
                              **({"validate": deps.validate} if deps.validate else {}))
            if not report["ok"]:
                raise Refused("the draft does not pass its check now: " + "; ".join(report["problems"]))
            record = dr.approve(report, draft, root=job.root)
            job.data["approval"] = {"draft_sha256": seen, "contract_sha256": record["contract_sha256"], "task": TASK,
                                    "max_usd": cap, "max_iterations": max_iterations, "at": deps.clock(),
                                    "by": os.environ.get("USER"), "feasibility": record["feasibility"]}
            job.note(deps, "approved", draft=seen[:12], contract=record["contract_sha256"][:12])
            r = _agent(job, cfg, deps, sandbox_cfg)
    return job, r


def _agent(job, cfg, deps, sandbox_cfg=None, resume=False):
    """The agent stage, bound to the approved contract; then the review package."""
    from codetask import review
    from codetask import run as ctrun
    ap = job.data["approval"]
    contract_path = job.root / "fixtures" / "contracts" / f"{ap['task']}.json"
    try:
        _, sha = ct.freeze(json.loads(contract_path.read_text(encoding="utf-8")))
    except (OSError, ValueError, ct.ContractError) as e:
        sha = f"unreadable: {e}"
    if sha != ap["contract_sha256"]:
        job.move(BLOCKED, deps, reason="contract_changed: the contract differs from the approved one")
        raise Refused(f"job {job.id}: the contract is not the one approved (BLOCKED)")
    sid = "a1"
    if sid not in job.data["stages"]:
        job.data["stages"][sid] = {"kind": "agent", "run_id": f"{job.id}-{sid}", "cap_usd": ap["max_usd"],
                                   "started_at": deps.clock()}
        job.move(AGENT_RUNNING, deps, stage=sid)
    st = job.data["stages"][sid]
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    profile = contract.get("budget_profile")
    acfg = stage_config(cfg, st["cap_usd"])                 # the cap it started with, never recomputed
    again = (job.runs / st["run_id"] / "checkpoints.sqlite").exists()
    deps.echo(running(job, "agent", st["run_id"]))
    r = ctrun.run_code_task(contract_path=contract_path, run_id=st["run_id"], runs_dir=job.runs, cfg=acfg,
                            resume=again, models=deps.models, validate=deps.validate, preflight=deps.preflight,
                            env_preflight=deps.env_preflight, root=job.root)
    st.update(ended_at=deps.clock(), status=r["status"], usd=r["usd_billed"], profile=profile)
    deps.echo(f"agent finished: {r['status']} (${r['usd_billed']:.4f})")
    if r["status"] != "DONE":
        job.move(AGENT_FAILED, deps, stage=sid, reason=r.get("stop_reason"))
        return r
    kw = {"validate": deps.validate} if deps.validate else {}
    out = review.build(job.runs / st["run_id"], repo=job.data["inputs"]["repo"],
                       sandbox_cfg=sandbox_cfg or acfg.get("sandbox") or {}, root=job.root, **kw)
    st["review"] = {"valid": out["valid"], "problems": out["problems"], "dir": str(out["dir"])}
    job.move(REVIEW_READY if out["valid"] else REVIEW_INVALID, deps, stage=sid)
    return r


def resume(job_id, *, cfg, deps, sandbox_cfg=None, jobs_dir=JOBS):
    """Continue the stage a crash interrupted, with the cap it started with."""
    job = open_job(job_id, jobs_dir)
    with job.lock():
        state = job.data["state"]
        if state == DRAFTING:
            n = max(int(k[1:]) for k, s in job.data["stages"].items() if s["kind"] == "draft")
            return job, _draft(job, cfg, deps, n)
        if state == AGENT_RUNNING:
            from codetask.run import apply_profile
            st = job.data["stages"]["a1"]
            contract = json.loads((job.root / "fixtures" / "contracts" / f"{job.data['approval']['task']}.json")
                                  .read_text(encoding="utf-8"))
            acfg = stage_config(apply_profile(cfg, contract["budget_profile"]) if contract.get("budget_profile")
                                else cfg, st["cap_usd"])
            text = _limits_text(job, "resume the agent", [f"agent stage {st['run_id']}; stage cap ${st['cap_usd']:.4f}"])
            with live(deps, acfg, [acfg["code_task"]["role"]], text):
                return job, _agent(job, cfg, deps, sandbox_cfg, resume=True)
        raise Refused(f"job {job.id} is {state}: nothing to resume")


def redraft(job_id, *, cfg, deps, jobs_dir=JOBS):
    job = open_job(job_id, jobs_dir)
    with job.lock():
        if job.data["state"] not in (DRAFT_FAILED, AWAITING_APPROVAL):
            raise Refused(f"job {job.id} is {job.data['state']}: only a failed or unapproved draft is redrafted")
        n = 1 + max(int(k[1:]) for k, s in job.data["stages"].items() if s["kind"] == "draft")
        job.note(deps, "redraft", stage=f"d{n}", by=os.environ.get("USER"))
        return job, _draft(job, cfg, deps, n)


def abandon(job_id, reason, *, deps, jobs_dir=JOBS):
    """Close a job that will not be continued (e.g. a stage stopped and a new job was started instead). It takes the
    lock, so a job whose stage is still running cannot be abandoned under it."""
    job = open_job(job_id, jobs_dir)
    with job.lock():
        if job.data["state"] in (REVIEW_READY, REVIEW_INVALID, REJECTED, ABANDONED):
            raise Refused(f"job {job.id} is {job.data['state']}: there is nothing to abandon")
        job.move(ABANDONED, deps, reason=reason, by=os.environ.get("USER"))
        return job


def reject(job_id, reason, *, deps, jobs_dir=JOBS):
    job = open_job(job_id, jobs_dir)
    with job.lock():
        if job.data["state"] not in (AWAITING_APPROVAL, DRAFT_FAILED):
            raise Refused(f"job {job.id} is {job.data['state']}: only a draft waiting for approval is rejected")
        job.move(REJECTED, deps, reason=reason, by=os.environ.get("USER"))
        return job


def _job_line(path):
    """One job, as a line: its id, state and money; or "<directory> unreadable" if its job.json cannot be read."""
    try:
        data = json.loads((path / "job.json").read_text(encoding="utf-8"))
        state, cap = data["state"], float(data["max_usd"])
    except (OSError, ValueError, TypeError, KeyError):
        return f"{path.name} unreadable"
    return f"{path.name} {state} spent ${runs_spent_nano(path / 'runs', data.get('stages')) / 1e9:.4f} of ${cap:.2f}"


def list_jobs(*, jobs_dir=JOBS):
    """Every job in the jobs directory, one line per job sorted by job id: read only, no lock, nothing changed."""
    root = Path(jobs_dir)
    try:
        entries = sorted(root.iterdir(), key=lambda p: p.name)
    except OSError:
        return "no jobs"
    lines = [_job_line(p) for p in entries if p.is_dir() and (p / "job.json").exists()]
    return "\n".join(lines) if lines else "no jobs"


def status(job_id, *, jobs_dir=JOBS):
    """A read-only summary (no lock): state, money, stages, and the draft to approve with its sha."""
    job = open_job(job_id, jobs_dir)
    d = job.data
    out = [f"job {job.id}: {d['state']}", f"repo {d['inputs']['repo']} at {d['inputs']['commit']}",
           f"money: cap ${d['max_usd']:.2f}, spent ${spent_nano(job) / 1e9:.4f}"]
    for sid, s in d["stages"].items():
        out.append(f"  {sid} {s['kind']}: {s.get('status', 'running')} cap ${s['cap_usd']:.4f}"
                   + (f" spent ${s['usd']:.4f}" if s.get("usd") is not None else ""))
    accepted = any(s["kind"] == "draft" and s.get("status") == "DRAFTED" for s in d["stages"].values())
    if d["state"] == AWAITING_APPROVAL or (d["state"] == DRAFT_FAILED and accepted):
        st, path = _last_draft(job)
        sha = draft_sha(path)
        draft = json.loads(path.read_text(encoding="utf-8"))
        c = draft["contract"]
        if d["state"] == DRAFT_FAILED:
            out.append(f"the latest redraft failed; the last accepted draft is from {st['run_id']}")
        out += [f"draft {sha[:12]} ({job.runs / st['run_id'] / 'DRAFT_REVIEW.md'})",
                "writable: " + ", ".join(c["scope"]["writable"]),
                *[f"validation {v['id']}: {' '.join([v['executable'], *v['args']])}" for v in c["validation"]],
                f"approve: argus approve {job.id} --sha {sha[:12]}"]
    if d["state"] in (REVIEW_READY, REVIEW_INVALID):
        rv = d["stages"]["a1"]["review"]
        out.append(f"review package: {rv['dir']} ({'valid' if rv['valid'] else 'NOT valid: ' + '; '.join(rv['problems'])})")
    return "\n".join(out)
