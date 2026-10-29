"""Router v0 (docs/reviews/SPEC_ROUTER_V0.md): a code task as one resumable job.

  argus code     a new job: intake of the target repository at a commit, then the drafter            -> AWAITING_APPROVAL
  argus approve  the human approves the draft they saw (its sha), then the agent and the review package -> REVIEW_READY
  argus reject / redraft / resume / status
  argus applied  the human applied the review package's patch in a commit of the target repository        -> APPLIED
                 (reject also closes a review package that will not be applied)                           -> REJECTED
  argus retry    the agent again on the approved contract (a new stage, told how the previous one ended)

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
import shlex
import stat
import unicodedata
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from acceptance import changed as ch
from acceptance import contract as ct
from acceptance import draft as dr
from acceptance import intake
from harness.events import parse_lines
from harness.llm import reconcile_ledger, to_nano
from tools.web import problem as web_problem

ROOT = Path(__file__).resolve().parent.parent
JOBS = ROOT / "jobs"
BASE, TASK = "base", "task"                 # the intake and the task inside a job's own root

NEW, DRAFTING, DRAFT_FAILED, AWAITING_APPROVAL = "NEW", "DRAFTING", "DRAFT_FAILED", "AWAITING_APPROVAL"
AGENT_RUNNING, AGENT_FAILED, REVIEW_READY, REVIEW_INVALID = "AGENT_RUNNING", "AGENT_FAILED", "REVIEW_READY", "REVIEW_INVALID"
REJECTED, BLOCKED, ABANDONED, APPLIED = "REJECTED", "BLOCKED", "ABANDONED", "APPLIED"
LEGAL = {(NEW, DRAFTING), (NEW, BLOCKED),
         (DRAFTING, AWAITING_APPROVAL), (DRAFTING, DRAFT_FAILED), (DRAFTING, BLOCKED),
         (DRAFT_FAILED, DRAFTING), (DRAFT_FAILED, REJECTED), (DRAFT_FAILED, BLOCKED),
         (DRAFT_FAILED, AGENT_RUNNING),           # an accepted draft stays approvable after a failed redraft
         (AWAITING_APPROVAL, AGENT_RUNNING), (AWAITING_APPROVAL, REJECTED), (AWAITING_APPROVAL, DRAFTING),
         (AWAITING_APPROVAL, BLOCKED),
         (AGENT_RUNNING, REVIEW_READY), (AGENT_RUNNING, REVIEW_INVALID), (AGENT_RUNNING, AGENT_FAILED),
         (AGENT_RUNNING, BLOCKED),
         (AGENT_FAILED, AGENT_RUNNING), (AGENT_FAILED, BLOCKED),
         (REVIEW_READY, APPLIED), (REVIEW_READY, REJECTED), (REVIEW_INVALID, REJECTED)} | \
        {(s, ABANDONED) for s in (NEW, DRAFTING, DRAFT_FAILED, AWAITING_APPROVAL, AGENT_RUNNING, AGENT_FAILED, BLOCKED)}
JOB_ID = re.compile(r"^j[0-9a-z_]{1,40}$")
KEY_SHAPE = {"anthropic": "sk-ant-"}
ANSI = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]|\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)?|\x1b[@-_]?")


def clean(text):
    """Text as it may be printed to a terminal (docs/reviews/SPEC_ROUTER_STATUS.md 2.4): parts of what the router prints
    come from a model (criteria, test nodes, writable paths, stop reasons), and a control character or an ANSI escape
    in them could garble or fake the screen. Escapes are dropped whole, every other control character becomes a space."""
    return "".join(" " if unicodedata.category(c) == "Cc" else c for c in ANSI.sub("", str(text)))


class Refused(Exception):
    """A command that cannot run; nothing was changed."""


class JobBusy(Refused):
    pass


def now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class Deps:
    """What a command needs from outside: the human (confirm, key, tty) and, in tests, models and the sandbox."""

    def __init__(self, *, confirm=None, get_key=None, isatty=None, models=None, validate=None, preflight=None,
                 env_preflight=None, clock=now, echo=print, red=None, key_file=None, assume_yes=False,
                 key_forbidden=(ROOT,)):
        import getpass
        import sys
        self.confirm = confirm or (lambda text: input(text + "\nLanjut? [y/N] ").strip().lower() == "y")
        self.get_key = get_key or (lambda: getpass.getpass("Type or paste the API key, then Enter (not shown): "))
        self.isatty = isatty or (lambda: sys.stdin.isatty())
        self.models, self.validate, self.preflight, self.env_preflight = models, validate, preflight, env_preflight
        self.clock, self.echo, self.red = clock, echo, red        # red: the W2a red check, injected by tests
        # docs/reviews/SPEC_ROUTER_KEY_FILE.md: the key from a 0600 file outside every repository (--key-file), and,
        # only with it, the [y/N] answered by the human in chat (--yes)
        self.key_file, self.assume_yes, self.key_forbidden = key_file, assume_yes, tuple(key_forbidden)


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


def check_problem(name, image, root=None):
    """Why environment `name` may not be used with `image`, or None (docs/reviews/SPEC_ENV_FROM_PYTHON_IMAGE.md 2.3): an
    environment defined in environments/NAME/ needs a passing scripts/check_env_image.py record for exactly that image.
    An environment without a definition there (argus, sympy) is not subject to it."""
    root = ROOT if root is None else root
    if not (Path(root) / "environments" / name).is_dir():
        return None
    rec = Path(root) / f".sandbox_image_{name}.check.json"
    try:
        r = json.loads(rec.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return f"sandbox environment {name!r} has not been checked: run scripts/check_env_image.py {name}"
    if not isinstance(r, dict) or r.get("result") != "pass" or r.get("environment") != name:
        return f"sandbox environment {name!r} did not pass its check ({rec.name})"
    if r.get("image") != image:
        return (f"sandbox environment {name!r} was checked with image {r.get('image')}, not {image}: run "
                f"scripts/check_env_image.py {name} again")
    return None


def environment_pin(cfg, name, root=None):
    """(image id, problem) of sandbox environment `name` as this config resolves it now (SPEC_SWE_PILOT 2.1, K4): an
    unknown name or one without an image is a problem, never another environment's or the default image; so is an
    environment from environments/ whose image has not passed its check (SPEC_ENV_FROM_PYTHON_IMAGE)."""
    from tools import sandbox as sb
    image, problem = sb.environment_image(cfg.get("sandbox") or {}, name)
    if problem:
        return None, problem
    if not image:
        return None, (f"sandbox environment {name!r} has no image (sandbox.environments.{name}.image, "
                      f"ARGUS_SANDBOX_IMAGE_{name.upper()} or .sandbox_image_{name}); it never falls back to another image")
    problem = check_problem(name, image, root)
    if problem:
        return None, problem
    return image, None


def environment_changed(job, cfg):
    """Why the job's pinned environment image is not the one this config resolves now, or None. A job from before
    --environment pins nothing (it ran on argus, as it always did)."""
    name = job.data["inputs"].get("environment")
    if name is None:
        return None
    now, problem = environment_pin(cfg, name)
    was = job.data.get("environment_image")
    if now == was:
        return None
    return (f"the image of sandbox environment {name!r} changed since the job started (was {was}, now "
            f"{now or problem}); an image is not rebuilt identically, so this job cannot continue: "
            f'argus abandon {job.id} "<why>"')


def _check_environment(job, cfg):
    why = environment_changed(job, cfg)
    if why:
        raise Refused(f"job {job.id}: {why}; nothing was changed")


def job_config(job, cfg):
    """The config of a job's stages: its drafter writes validations for the job's environment (SPEC_SWE_PILOT 2.1)."""
    name = job.data["inputs"].get("environment")
    if name is None:
        return cfg
    out = copy.deepcopy(cfg)
    out["drafter"]["environment"] = name
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


def _peak_lines(deps, cfg, roles):
    """SPEC_PEAK_EDGES P3: a warning per provider of the stage's models at (or within 30 minutes of) its peak price.
    Only shown: it neither refuses nor delays the stage."""
    from models.pricing import peak_line
    from models.registry import ModelRef, price_for, window_for
    try:
        now = datetime.strptime(deps.clock(), "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        now = datetime.now(timezone.utc)
    lines = []
    for ref in sorted({ModelRef.parse(cfg["roles"][role]["model"]) for role in roles}, key=str):
        line = peak_line(ref.provider, price_for(cfg, ref), window_for(cfg, ref.provider), now)
        if line and line not in lines:
            lines.append(line)
    return lines


def read_key_file(path, forbidden):
    """The key in a file the router may use (SPEC_ROUTER_KEY_FILE.md K2): a regular file (no symlink) of this user,
    readable by nobody else, outside every forbidden directory (repositories, jobs/). One newline at the end is
    dropped. A refusal never shows the file's content."""
    p = Path(path).expanduser()
    try:
        st = os.lstat(p)
    except OSError as e:
        raise Refused(f"--key-file {p} cannot be read: {e.strerror}") from None
    if stat.S_ISLNK(st.st_mode) or not stat.S_ISREG(st.st_mode):
        raise Refused(f"--key-file {p} is not a regular file")
    if st.st_uid != os.getuid():
        raise Refused(f"--key-file {p} is not owned by you")
    if st.st_mode & 0o077:
        raise Refused(f"--key-file {p} can be read by others (mode {oct(st.st_mode & 0o777)}): chmod 600 it")
    real = p.resolve()
    for root in forbidden:
        r = Path(root).expanduser().resolve()
        if real == r or r in real.parents:
            raise Refused(f"--key-file {p} is inside {r}: keep the key outside every repository and jobs/")
    try:
        data = p.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        raise Refused(f"--key-file {p} cannot be read as text") from None
    return data[:-1] if data.endswith("\n") else data


@contextmanager
def live(deps, cfg, roles, text, job=None):
    """Confirm, then take each key the stage's real models need (never an argument, never written, unset after).
    The key is typed in a terminal, or read from deps.key_file; only with a key file may deps.assume_yes replace the
    [y/N] (the human approved this run in chat), and the limits are then still printed and noted in the job."""
    keys = _needs_key(cfg, roles)
    if deps.assume_yes and not deps.key_file:
        raise Refused("--yes needs --key-file: without a key file the run is confirmed in the terminal")
    if keys and not deps.key_file and not deps.isatty():
        raise Refused("a live stage needs a terminal: the key is typed, never passed (or use --key-file)")
    if deps.key_file and len(keys) > 1:
        raise Refused(f"--key-file holds one key; this stage needs {len(keys)}")
    text = "\n".join([text, *_peak_lines(deps, cfg, roles)])
    # SPEC_ROUTER_STATUS.md 2.1: the human's decisions and their times, for the supervision measure
    if job is not None:
        job.note(deps, "limits_shown", screen=text)
    if deps.assume_yes:
        deps.echo(text + "\n(--yes: approved in chat; no [y/N] asked)")
        if job is not None:
            job.note(deps, "confirmed_by_flag", screen=text)
    else:
        ok = deps.confirm(text)
        if job is not None:
            job.note(deps, "confirmed" if ok else "not_confirmed")
        if not ok:
            raise Refused("not confirmed; nothing was started")
    forbidden = list(deps.key_forbidden) + ([job.dir.parent, job.data["inputs"]["repo"]] if job is not None else [])
    set_vars = []
    try:
        for var, kind in keys:
            if deps.key_file:
                key = read_key_file(deps.key_file, forbidden)
                if job is not None:
                    job.note(deps, "key_from_file", path=str(Path(deps.key_file).expanduser()))
            else:
                key = deps.get_key() or ""
            shape = KEY_SHAPE.get(kind)
            if not key:
                raise Refused("the key is empty; nothing was started")
            if re.search(r"\s", key):
                raise Refused("the key contains whitespace (pasted twice?); nothing was started")
            if shape and (not key.startswith(shape) or key[len(shape):].find(shape) != -1):
                raise Refused(f"the key does not look like one {kind} key; nothing was started")
            if not deps.key_file and job is not None:
                job.note(deps, "key_typed")             # only when: never the key, its length or its prefix
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
    return "\n".join([f"== {title} (job {job.id}) ==", *map(clean, lines),
                      f"job cap ${job.data['max_usd']:.2f}; spent ${spent:.4f}; left ${job.data['max_usd'] - spent:.4f}"])


# ---- commands ----------------------------------------------------------------------------------------------------

def running(job, what, run_id):
    """What the human sees while a stage runs (it prints nothing else): how long, and how to continue if it stops."""
    return (f"{what} running in {run_id} (usually 1-3 minutes; it prints nothing until it ends). Do not start "
            f"another job for this task: if this stops or the terminal closes, continue it with `argus resume {job.id}`.")


def new_job_id():
    return "j" + datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S") + "_" + secrets.token_hex(2)


def start_code(*, repo, commit, issue, cfg, deps, exclude=(), max_usd=None, jobs_dir=JOBS, job_id=None,
               environment=None):
    """A new job: intake, then the first drafter stage. Returns the job. environment: the sandbox environment its
    validations run in, with the image it resolves to now pinned for the whole job; None is the job as before
    (the drafter's configured environment, nothing pinned)."""
    if not isinstance(issue, str) or not issue.strip():
        raise Refused("the issue is empty")
    image = None
    if environment is not None:
        image, problem = environment_pin(cfg, environment)
        if problem:
            raise Refused(f"{problem}; no job was created")
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
                               "exclude": list(exclude), **({"environment": environment} if environment else {})},
                    **({"environment_image": image} if environment else {}),
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


NOTE_MAX = 1000                  # SPEC_DRAFT_CALL_PATH 2.4: characters of a reviewer's note to the drafter


def _draft(job, cfg, deps, n, note=None):
    """Start drafter stage n (its cap fixed now), or resume it with the cap it started with. note: a reviewer's note
    for a redraft, recorded with the stage when it starts (a resume takes the drafter run's own record)."""
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
    scfg = stage_config(job_config(job, cfg), cap)
    lim = drafter_settings(scfg)
    text = _limits_text(job, f"drafter stage {sid}" + (" (resume)" if resume else ""),
                        [f"model {scfg['roles'][scfg['drafter']['role']]['model']}; stage cap ${cap:.4f}; one attempt "
                         f"${lim['attempt_usd']:.2f}; {scfg['drafter']['max_submits']} submits",
                         f"overrides: {(cfg.get('router') or {}).get('overrides') or {}}"])
    with live(deps, scfg, [scfg["drafter"]["role"]], text, job=job):
        if not resume:
            job.data["stages"][sid] = {"kind": "draft", "run_id": f"{job.id}-{sid}", "cap_usd": cap,
                                       "started_at": deps.clock(), **({"note": note} if note else {})}
            if note:
                job.data["human_steered"] = True
            job.move(DRAFTING, deps, stage=sid)
        run_id = job.data["stages"][sid]["run_id"]
        again = (job.runs / run_id / "checkpoints.sqlite").exists()
        deps.echo(running(job, "drafter", run_id))
        r = run_drafter(run_id=run_id, runs_dir=job.runs, cfg=scfg, intake_name=BASE, issue=job.data["inputs"]["issue"],
                        max_usd=cap, resume=again, models=deps.models, validate=deps.validate,
                        preflight=deps.preflight, env_preflight=deps.env_preflight, root=job.root, red=deps.red,
                        note=job.data["stages"][sid].get("note"))
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


def _env(v):
    return f" (env {v['environment']})" if v.get("environment") else ""


def environment_lines(job):
    name, image = job.data["inputs"].get("environment"), job.data.get("environment_image")
    if name is None:
        return []
    return [f"environment {name}, image {str(image).split(':')[-1][:12]}"]


def changed_lines(job, draft):
    """W2a-ext K6: a draft that changes existing tests says so where it is approved, with the number of K3 warnings
    (computed here from the intake, not read from the drafter's report)."""
    tests = draft.get("changed_tests") or []
    if not tests:
        return []
    old = dr.old_tests(job.root / "fixtures" / "repos" / draft["base"], draft)
    warn = [w for t in tests if old.get(t["path"]) is not None
            for w in ch.warnings(t["path"], old[t["path"]], t["content"], t.get("removed", []))]
    return [f"changes {len(tests)} existing test file(s) ({', '.join(t['path'] for t in tests)}), {len(warn)} "
            "warning(s): read the diff in DRAFT_REVIEW.md"]


def call_path_lines(draft_path, draft):
    """SPEC_DRAFT_CALL_PATH 2.3: the approve screen says when the draft's failing baseline runs through files that are
    not writable (from the drafter's check report next to the draft)."""
    from codetask.drafter import call_path_warning
    try:
        report = json.loads((Path(draft_path).parent / "check_report.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    w = call_path_warning(draft, report)
    return [f"warning: {w}"] if w else []


def approve(job_id, *, sha, cfg, deps, sandbox_cfg=None, max_usd=None, max_iterations=3, reference_patch=None,
            jobs_dir=JOBS, web=False):
    """Approve the draft the human saw (sha, as status shows it), then run the agent and build the review package.
    web: the human grants ReadDocs (SPEC_WEB_TOOLS 3), refused for an environment off web.environments."""
    from codetask import run as ctrun
    job = open_job(job_id, jobs_dir)
    with job.lock():
        _check_environment(job, cfg)
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
        why = web_problem(cfg.get("web"), c) if web else None
        if why:
            raise Refused(f"job {job.id}: {why}; nothing was approved")
        profile = c.get("budget_profile")
        router = cfg.get("router") or {}
        by_profile = router.get("agent_max_usd") or {}
        want = float(max_usd if max_usd is not None else by_profile.get(profile, by_profile.get("default", 0.5)))
        cap = round(min(want, left_usd(job)), 6)
        acfg = stage_config(ctrun.apply_profile(cfg, profile) if profile else cfg, cap)
        need = ctrun.settings(acfg)["attempt_usd"]
        lines = [f"draft {seen[:12]} (from stage {st['run_id']})",
                 "writable: " + ", ".join(c["scope"]["writable"]),
                 *environment_lines(job),
                 *[f"validation {v['id']}{_env(v)}: {' '.join([v['executable'], *v['args']])}; required: "
                   + (", ".join(v.get("must_pass") or []) or "none") for v in c["validation"]],
                 *changed_lines(job, draft),
                 *call_path_lines(path, draft),
                 f"tools added: {c.get('tools') or 'none'}; profile {profile}; one attempt ${need:.2f}",
                 *([f"network: ReadDocs on {len(cfg['web']['hosts'])} allowlisted hosts "
                    f"({', '.join(sorted(cfg['web']['hosts']))}), granted by this approval"] if web else []),
                 f"agent cap ${cap:.4f}, {max_iterations} attempts; "
                 + ("reference patch given (proven)" if reference_patch else "no reference patch (unproven)")]
        if cap < need:
            job.move(BLOCKED, deps, reason=f"budget: ${cap:.4f} left for the agent, one attempt needs ${need:.2f}")
            raise Refused(f"job {job.id}: not enough of the job cap left for one agent attempt (BLOCKED)")
        text = _limits_text(job, "approve and run the agent", lines)
        with live(deps, acfg, [acfg["code_task"]["role"]], text, job=job):
            if draft_sha(path) != seen:                 # changed while the human was reading
                raise Refused("the draft changed after it was shown; nothing was approved")
            report = dr.check(draft, task=TASK, issue=job.data["inputs"]["issue"], max_usd=cap,
                              max_iterations=max_iterations, reference_patch=reference_patch,
                              sandbox_cfg=sandbox_cfg or acfg.get("sandbox") or {}, root=job.root,
                              profiles=sorted((cfg.get("code_task") or {}).get("profiles") or {}),
                              **({"validate": deps.validate} if deps.validate else {}),
                              **({"red": deps.red} if deps.red else {}), web=web)
            if not report["ok"]:
                raise Refused("the draft does not pass its check now: " + "; ".join(report["problems"]))
            record = dr.approve(report, draft, root=job.root)
            from codetask.agent import baseline_errors
            # SPEC_LOCATE_FROM_TRACEBACK 2.2: the red baseline of this check (the approved draft, just now), recorded
            # once; every agent stage's first attempt is told it, a resume included.
            job.data["approval"] = {"draft_sha256": seen, "contract_sha256": record["contract_sha256"], "task": TASK,
                                    "max_usd": cap, "max_iterations": max_iterations, "at": deps.clock(),
                                    "by": os.environ.get("USER"), "feasibility": record["feasibility"],
                                    "baseline": baseline_errors(report), "web": bool(web)}
            job.note(deps, "approved", draft=seen[:12], contract=record["contract_sha256"][:12])
            r = _agent(job, cfg, deps, sandbox_cfg)
    return job, r


def agent_stages(job):
    """The job's agent stages, a1, a2, ... in order."""
    return sorted((k for k, s in job.data["stages"].items() if s["kind"] == "agent"), key=lambda k: int(k[1:]))


def last_agent(job):
    sids = agent_stages(job)
    return (sids[-1], job.data["stages"][sids[-1]]) if sids else (None, None)


def _agent(job, cfg, deps, sandbox_cfg=None, resume=False, sid="a1", cap=None, carry=None):
    """An agent stage (a1 after approve, a2... after a retry), bound to the approved contract; then the review
    package. cap and carry are recorded when the stage starts; a resume uses what was recorded."""
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
    if sid not in job.data["stages"]:
        job.data["stages"][sid] = {"kind": "agent", "run_id": f"{job.id}-{sid}",
                                   "cap_usd": ap["max_usd"] if cap is None else cap, "started_at": deps.clock()}
        if carry is not None:
            job.data["stages"][sid]["carry"] = carry
        job.move(AGENT_RUNNING, deps, stage=sid)
    st = job.data["stages"][sid]
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    profile = contract.get("budget_profile")
    acfg = stage_config(cfg, st["cap_usd"])                 # the cap it started with, never recomputed
    again = (job.runs / st["run_id"] / "checkpoints.sqlite").exists()
    deps.echo(running(job, "agent", st["run_id"]))
    r = ctrun.run_code_task(contract_path=contract_path, run_id=st["run_id"], runs_dir=job.runs, cfg=acfg,
                            resume=again, models=deps.models, validate=deps.validate, preflight=deps.preflight,
                            env_preflight=deps.env_preflight, root=job.root, initial_feedback=stage_feedback(ap, st))
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


def stage_feedback(approval, stage):
    """What the first attempt of an agent stage is told: the approved draft's red baseline (SPEC_LOCATE_FROM_TRACEBACK
    2.2, absent in jobs approved before it) and, for a retry, the carry. Both recorded; nothing is recomputed."""
    fb = dict(stage.get("carry") or {})
    if approval.get("baseline"):
        fb["baseline"] = approval["baseline"]
    return fb or None


def resume(job_id, *, cfg, deps, sandbox_cfg=None, jobs_dir=JOBS):
    """Continue the stage a crash interrupted, with the cap it started with."""
    job = open_job(job_id, jobs_dir)
    with job.lock():
        _check_environment(job, cfg)
        state = job.data["state"]
        if state == DRAFTING:
            n = max(int(k[1:]) for k, s in job.data["stages"].items() if s["kind"] == "draft")
            return job, _draft(job, cfg, deps, n)
        if state == AGENT_RUNNING:
            from codetask.run import apply_profile
            sid, st = last_agent(job)
            contract = json.loads((job.root / "fixtures" / "contracts" / f"{job.data['approval']['task']}.json")
                                  .read_text(encoding="utf-8"))
            acfg = stage_config(apply_profile(cfg, contract["budget_profile"]) if contract.get("budget_profile")
                                else cfg, st["cap_usd"])
            text = _limits_text(job, "resume the agent", [f"agent stage {st['run_id']}; stage cap ${st['cap_usd']:.4f}"])
            with live(deps, acfg, [acfg["code_task"]["role"]], text, job=job):
                return job, _agent(job, cfg, deps, sandbox_cfg, resume=True, sid=sid)
        raise Refused(f"job {job.id} is {state}: nothing to resume")


def _wrote_from_verdict(run_dir, iteration):
    """A run from before attempts recorded `wrote`: whether its last verdict saw any file changed from the original."""
    v = json.loads((Path(run_dir) / f"verdict_{iteration}.json").read_text(encoding="utf-8"))
    for c in v["criteria"]:
        d = (c.get("evidence") or {}).get("diff")
        if isinstance(d, dict):
            return any(p != ct.SUMMARY for k in ("added", "modified", "removed") for p in d.get(k) or [])
    return None


def carry_from(job, sid):
    """SPEC_AGENT_CONTEXT_RETRY 2.4: how the last attempt of agent stage sid ended, from its run's committed result,
    for the first attempt of the next stage. A result that cannot be read refuses the retry (it must not start blind)."""
    from codetask.agent import stopped
    run_dir = job.runs / job.data["stages"][sid]["run_id"]
    try:
        a = dict(json.loads((run_dir / "result.json").read_text(encoding="utf-8"))["attempt"])
        if a.get("wrote") is None:
            a["wrote"] = _wrote_from_verdict(run_dir, a["iteration"])
    except (OSError, ValueError, TypeError, KeyError):
        raise Refused(f"the result of agent stage {sid} cannot be read: a retry would start without knowing how it "
                      "ended; nothing was started") from None
    return {"carried": True, "from": sid, "stopped": stopped(a)}


def retry(job_id, *, cfg, deps, sandbox_cfg=None, max_usd=None, jobs_dir=JOBS):
    """Run the agent again on the approved contract, as a new stage a<n+1> with its own cap (the lower of its profile
    and what is left of the job, recorded at start) and how the previous stage ended."""
    from codetask import run as ctrun
    job = open_job(job_id, jobs_dir)
    with job.lock():
        _check_environment(job, cfg)
        if job.data["state"] != AGENT_FAILED:
            raise Refused(f"job {job.id} is {job.data['state']}: only a job whose agent failed is retried")
        prev, _ = last_agent(job)
        sid = f"a{int(prev[1:]) + 1}"
        carry = carry_from(job, prev)
        contract = json.loads((job.root / "fixtures" / "contracts" / f"{job.data['approval']['task']}.json")
                              .read_text(encoding="utf-8"))
        profile = contract.get("budget_profile")
        web = "read_docs" in (contract.get("tools") or [])
        why = web_problem(cfg.get("web"), contract) if web else None
        if why:             # the approved grant is used again: checked against this config before anything is asked
            raise Refused(f"job {job.id}: {why}; nothing was retried")
        by_profile = (cfg.get("router") or {}).get("agent_max_usd") or {}
        want = float(max_usd if max_usd is not None else by_profile.get(profile, by_profile.get("default", 0.5)))
        cap = round(min(want, left_usd(job)), 6)
        acfg = stage_config(ctrun.apply_profile(cfg, profile) if profile else cfg, cap)
        need = ctrun.settings(acfg)["attempt_usd"]
        if cap < need:
            job.move(BLOCKED, deps, reason=f"budget: ${cap:.4f} left for the agent, one attempt needs ${need:.2f}")
            raise Refused(f"job {job.id}: not enough of the job cap left for one agent attempt (BLOCKED)")
        s = carry["stopped"]
        lines = [f"agent stage {sid} (retry of {prev}), approved contract {job.data['approval']['contract_sha256'][:12]}",
                 f"{prev} ended: {s['end']} after {s['steps']} steps"
                 + {True: ", files changed", False: ", no file changed"}.get(s["wrote"], ""),
                 f"profile {profile}; max input {ctrun.settings(acfg)['max_input_tokens']}; one attempt ${need:.2f}; "
                 f"agent cap ${cap:.4f}",
                 *([f"network: ReadDocs on {len(cfg['web']['hosts'])} allowlisted hosts "
                    f"({', '.join(sorted(cfg['web']['hosts']))}), granted at approve; this stage downloads again"]
                   if web else [])]
        text = _limits_text(job, "retry the agent", lines)
        with live(deps, acfg, [acfg["code_task"]["role"]], text, job=job):
            job.note(deps, "retry", stage=sid, by=os.environ.get("USER"))
            return job, _agent(job, cfg, deps, sandbox_cfg, sid=sid, cap=cap, carry=carry)


def redraft(job_id, *, cfg, deps, jobs_dir=JOBS, note=None):
    """A new drafter stage; note: the reviewer's note it is told (SPEC_DRAFT_CALL_PATH 2.4), which marks the job
    human-steered."""
    if note is not None:
        note = clean(note).strip()
        if not note:
            raise Refused("the note is empty; nothing was started")
        if len(note) > NOTE_MAX:
            raise Refused(f"the note has {len(note)} characters, more than {NOTE_MAX}; nothing was started")
    job = open_job(job_id, jobs_dir)
    with job.lock():
        _check_environment(job, cfg)
        if job.data["state"] not in (DRAFT_FAILED, AWAITING_APPROVAL):
            raise Refused(f"job {job.id} is {job.data['state']}: only a failed or unapproved draft is redrafted")
        n = 1 + max(int(k[1:]) for k, s in job.data["stages"].items() if s["kind"] == "draft")
        job.note(deps, "redraft", stage=f"d{n}", by=os.environ.get("USER"), **({"note": True} if note else {}))
        return job, _draft(job, cfg, deps, n, note=note)


def abandon(job_id, reason, *, deps, jobs_dir=JOBS):
    """Close a job that will not be continued (e.g. a stage stopped and a new job was started instead). It takes the
    lock, so a job whose stage is still running cannot be abandoned under it."""
    job = open_job(job_id, jobs_dir)
    with job.lock():
        if job.data["state"] in (REVIEW_READY, REVIEW_INVALID, REJECTED, ABANDONED, APPLIED):
            raise Refused(f"job {job.id} is {job.data['state']}: there is nothing to abandon")
        job.move(ABANDONED, deps, reason=reason, by=os.environ.get("USER"))
        return job


def reject(job_id, reason, *, deps, jobs_dir=JOBS):
    """Reject a draft waiting for approval, or a review package that will not be applied (its outcome, with why)."""
    job = open_job(job_id, jobs_dir)
    with job.lock():
        if job.data["state"] not in (AWAITING_APPROVAL, DRAFT_FAILED, REVIEW_READY, REVIEW_INVALID):
            raise Refused(f"job {job.id} is {job.data['state']}: only a draft waiting for approval or a review package "
                          "is rejected")
        job.move(REJECTED, deps, reason=reason, by=os.environ.get("USER"))
        return job


def patch_id(repo, diff):
    """git patch-id --stable of a diff: the same for the same changes whatever their line numbers and whitespace."""
    out = intake.git(repo, "patch-id", "--stable", data=diff).split()
    return out[0].decode() if out else None


def applied(job_id, commit, *, deps, jobs_dir=JOBS, note=None):
    """Record that the human applied the review package in `commit` of the target repository: the commit as git
    resolves it, the patch's sha256 as it is on disk now, and whether the commit's changes are the patch's as they
    are (git patch-id), so a patch rewritten before it was committed is told apart from one applied as it was."""
    job = open_job(job_id, jobs_dir)
    with job.lock():
        if job.data["state"] != REVIEW_READY:
            raise Refused(f"job {job.id} is {job.data['state']}: only a valid review package is applied")
        repo = job.data["inputs"]["repo"]
        patch = Path(last_agent(job)[1]["review"]["dir"]) / "changes.patch"
        try:
            sha = intake.git(repo, "rev-parse", "--verify", "--end-of-options", f"{commit}^{{commit}}").decode().strip()
            mine = patch_id(repo, patch.read_bytes())
            theirs = patch_id(repo, intake.git(repo, "show", "--no-color", "--no-ext-diff", "--format=", sha))
        except intake.IntakeError as e:
            raise Refused(f"job {job.id}: {e}") from None
        job.move(APPLIED, deps, commit=sha, patch_sha256=hashlib.sha256(patch.read_bytes()).hexdigest(),
                 as_is=None if mine is None or theirs is None else mine == theirs, by=os.environ.get("USER"),
                 **({"note": note} if note else {}))
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


def _why(job):
    """The log entry of the move into the job's current state (its reason, and who)."""
    moves = [e for e in job.data.get("log") or [] if e.get("what") == "state" and e.get("new") == job.data["state"]]
    return moves[-1] if moves else {}


def _agent_result(job):
    """What the last agent stage's result.json says (read only), as one line; unreadable is said, never raised."""
    _, st = last_agent(job)
    try:
        r = json.loads((job.runs / st["run_id"] / "result.json").read_text(encoding="utf-8"))
        failing = (r.get("verdict") or {}).get("failing") or []
        return (f"agent result: {r['status']}, {r.get('attempts')} attempt(s), failing: "
                + (", ".join(map(str, failing)) or "none"))
    except (OSError, ValueError, TypeError, KeyError, AttributeError):
        return "agent result: unreadable"


def _review_lines(job, rv):
    """Where the review package is and, when it is valid, how a human applies it (SPEC_ROUTER_STATUS.md 2.2): the
    patch's sha256 as it is on disk now, apply --check before apply, on a branch at the commit that was taken in."""
    d = Path(rv["dir"])
    patch = d / "changes.patch"
    out = [f"review package: {d} ({'valid' if rv['valid'] else 'NOT valid: ' + '; '.join(rv['problems'])})",
           f"  PR description: {d / 'PR.md'}"]
    if not rv["valid"]:
        return out
    try:
        sha = hashlib.sha256(patch.read_bytes()).hexdigest()
    except OSError:
        sha = "unreadable"
    repo, p, q = shlex.quote(job.data["inputs"]["repo"]), shlex.quote(str(patch)), shlex.quote
    return out + [f"  patch:          {patch} (sha256 {sha})",
                  "apply (by hand, in the target repository):",
                  f"  sha256sum {p}",
                  f"  git -C {repo} checkout -b {q(branch_name(job.id))} {q(job.data['intake']['commit'])}",
                  f"  git -C {repo} apply --check --whitespace=nowarn {p}",
                  f"  git -C {repo} apply --whitespace=nowarn {p}"]


def _attempt_lines(job):
    """SPEC_AGENT_CONTEXT_RETRY 2.5: how each attempt of each agent stage ended, from its run's events (read only)."""
    out = []
    for sid in agent_stages(job):
        log = job.runs / job.data["stages"][sid]["run_id"] / "events.jsonl"
        try:
            evs = parse_lines(log.read_text(encoding="utf-8", errors="replace"))      # a cut multibyte last line
        except OSError:
            continue
        wrote = {e.get("iteration"): e.get("wrote") for e in evs if e.get("event") == "attempt_summary"}
        parts = [f"{int(e.get('iteration', 0)) + 1} {e.get('reason')} after {e.get('steps')} steps"
                 + {True: ", files changed", False: ", no file changed"}.get(wrote.get(e.get("iteration")), "")
                 for e in evs if e.get("event") == "attempt_end"]
        if parts:
            out.append(f"  {sid} attempts: " + "; ".join(parts))
    return out


def _estimate_lines(job):
    """SPEC_ESTIMATE_REASONING E3: per stage whose ledger has estimate_miss events (billed input above the estimate it
    was reserved with), how many of its billed (ok) calls and the largest billed / estimated input. Read only."""
    out = []
    for sid, s in job.data["stages"].items():
        if not s.get("run_id"):
            continue
        try:
            evs = parse_lines((job.runs / s["run_id"] / "events.jsonl").read_text(encoding="utf-8", errors="replace"))
        except OSError:
            continue
        misses = [e for e in evs if e.get("event") == "estimate_miss"]
        if not misses:
            continue
        calls = sum(1 for e in evs if e.get("event") == "llm_call" and e.get("status") == "ok")      # billed input
        ratios = [e["input_tokens"] / e["est_input"] for e in misses
                  if isinstance(e.get("input_tokens"), int) and isinstance(e.get("est_input"), int) and e["est_input"] > 0]
        out.append(f"  {sid} estimate misses: {len(misses)} of {calls} calls"
                   + (f", max {max(ratios):.2f}" if ratios else ""))
    return out


def branch_name(job_id):
    return f"argus/{job_id}"


def status(job_id, *, jobs_dir=JOBS, cfg=None):
    """A read-only summary (no lock): state, money, stages, and the draft to approve with its sha. With cfg, also
    whether the job's pinned environment image is still the one the config resolves."""
    job = open_job(job_id, jobs_dir)
    d = job.data
    out = [f"job {job.id}: {d['state']}", f"repo {d['inputs']['repo']} at {d['inputs']['commit']}",
           *environment_lines(job), f"money: cap ${d['max_usd']:.2f}, spent ${spent_nano(job) / 1e9:.4f}"]
    changed = environment_changed(job, cfg) if cfg is not None else None
    if changed:
        out += [f"environment: {changed}", f'next: argus abandon {job.id} "<why>"']
    if d.get("human_steered"):                  # SPEC_DRAFT_CALL_PATH 2.4
        out.append("human-steered: a redraft was given a reviewer's note")
    for sid, s in d["stages"].items():
        out.append(f"  {sid} {s['kind']}: {s.get('status', 'running')} cap ${s['cap_usd']:.4f}"
                   + (f" spent ${s['usd']:.4f}" if s.get("usd") is not None else "")
                   + (f"; note: {s['note'][:80]}" + ("..." if len(s["note"]) > 80 else "") if s.get("note") else ""))
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
                *[f"validation {v['id']}{_env(v)}: {' '.join([v['executable'], *v['args']])}" for v in c["validation"]],
                *changed_lines(job, draft),
                *call_path_lines(path, draft),
                f"approve: argus approve {job.id} --sha {sha[:12]}"]
    out += _attempt_lines(job)
    out += _estimate_lines(job)
    if d["state"] in (REVIEW_READY, REVIEW_INVALID):
        out += _review_lines(job, last_agent(job)[1]["review"])
    if d["state"] == APPLIED:
        why = _why(job)
        as_is = {True: "the patch as it was", False: "changes that differ from the patch"}.get(why.get("as_is"),
                                                                                             "changes not compared")
        out.append(f"applied: commit {why.get('commit')} ({as_is})" + (f" (by {why['by']})" if why.get("by") else "")
                   + (f"; note: {why['note']}" if why.get("note") else ""))
    if d["state"] in (DRAFT_FAILED, AGENT_FAILED, BLOCKED, REJECTED, ABANDONED):
        why = _why(job)
        out.append(f"why: {why.get('reason') or 'not recorded'}" + (f" (by {why['by']})" if why.get("by") else ""))
        if d["state"] == AGENT_FAILED:
            out.append(_agent_result(job))
        nxt = {DRAFT_FAILED: [f"argus redraft {job.id}", f'argus reject {job.id} "<why>"'],
               AGENT_FAILED: [f"argus retry {job.id}", f'argus abandon {job.id} "<why>"'],
               BLOCKED: [f'argus abandon {job.id} "<why>"']}.get(d["state"])
        if nxt:
            out.append("next: " + "  |  ".join(nxt))
    return "\n".join(map(clean, out))
