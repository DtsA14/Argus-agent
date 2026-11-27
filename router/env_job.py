"""The env job (docs/reviews/SPEC_CHAT_PACKAGES.md rev 2, S2): kind "env", one job = one request for new npm packages in the environment of a registered Node
repository. No model and no money; the one networked step is a hardened container that asks npm for a candidate lock and for the registry's facts.

  NEW -> RESOLVING -> AWAITING_HUMAN (the report waits) | REFUSED (a gate said no) | FAILED
  AWAITING_HUMAN -> BUILDING -> READY | REFUSED | FAILED (S3);  NEW|RESOLVING|AWAITING_HUMAN -> ABANDONED

`argus env add --repo R --job-id J --packages-file F --via ui --yes` creates the job and resolves it, holding the job's lock for its whole run; a job in
RESOLVING or BUILDING whose lock nobody holds is a job whose process died, and the next read moves it to FAILED. Two locks: `jobs/.env.lock` while a
request is created (one live job, the day's count and the new name are decided under it), and the job's own lock for the run. The package lines travel in a
file and as JSON for a fixed script inside the container, never in a shell string; npm's own text is never shown (it is data: the harness keeps the
fixed sentences it classifies it into). Nothing here edits config.yaml, environments/ or any repository."""
import calendar
import fcntl
import hashlib
import json
import os
import re
import shutil
import subprocess
import time
from contextlib import contextmanager
from pathlib import Path

from router import env_packages as ep
from router import job as rj

KIND = "env"
NEW, ABANDONED = rj.NEW, rj.ABANDONED
RESOLVING, AWAITING_HUMAN, BUILDING, READY, REFUSED, FAILED = "RESOLVING", "AWAITING_HUMAN", "BUILDING", "READY", "REFUSED", "FAILED"
LEGAL = {(NEW, RESOLVING), (NEW, FAILED), (NEW, ABANDONED),
         (RESOLVING, AWAITING_HUMAN), (RESOLVING, REFUSED), (RESOLVING, FAILED), (RESOLVING, ABANDONED),
         (AWAITING_HUMAN, BUILDING), (AWAITING_HUMAN, ABANDONED),
         (BUILDING, READY), (BUILDING, REFUSED), (BUILDING, FAILED)}
LIVE = (NEW, RESOLVING, AWAITING_HUMAN, BUILDING)
KEYS = {"min_age_days": (1, 365), "max_new": (1, 1000), "new_package_days": (0, 3650), "max_per_day": (1, 20), "max_ready_images": (1, 20),
        "report_ttl_hours": (1, 168), "resolve_timeout_s": (30, 3600), "build_timeout_s": (60, 7200), "memory_mb": (256, 8192),
        "pids_limit": (32, 4096), "cpus": (1, 8), "tmp_mb": (64, 4096)}
PACKAGES_FILE_MAX = 4096
CANDIDATE_MAX = 20 * 1024 * 1024
LOG_MAX = 65536
BASE_IMAGE = re.compile(r"[a-z0-9._/-]+@sha256:[0-9a-f]{64}")
NPM_SENTENCES = (("ERESOLVE", "npm reports a peer-dependency conflict"),
                 ("ETARGET", "no version of that package is old enough or exists (a version published after the age cutoff is not offered)"),
                 ("E404", "npm found no such package or version"))
LS_PROBLEM = re.compile(r"\b(invalid|missing)\b")
SCRIPT_VERSION = 1

# The two scripts the container runs. They are fixed text, written into the job's directory by the harness, never built from a request: the package
# specs reach them as JSON data and npm is started with an argument list (no shell). Output goes to /out only.
RESOLVE_JS = r"""'use strict';
const fs = require('node:fs');
const { spawnSync } = require('node:child_process');
const req = JSON.parse(fs.readFileSync('/in/request.json', 'utf8'));
const cap = (s) => String(s || '').slice(0, 65536);
fs.mkdirSync('/tmp/w', { recursive: true });
for (const f of ['package.json', 'package-lock.json']) fs.copyFileSync('/in/' + f, '/tmp/w/' + f);
const common = ['--userconfig', '/in/npmrc', '--cache', '/tmp/c', '--no-audit', '--no-fund', '--ignore-scripts'];
const npm = (args) => spawnSync('npm', args, { cwd: '/tmp/w', encoding: 'utf8', maxBuffer: 8 * 1024 * 1024 });
const inst = npm(['install', '--package-lock-only', '--strict-peer-deps', '--save-exact', '--before=' + req.before, ...common, ...req.specs]);
fs.writeFileSync('/out/install.log', cap(inst.stdout) + cap(inst.stderr));
const status = { install_rc: inst.status, ls_rc: null };
if (inst.status === 0) {
  for (const f of ['package.json', 'package-lock.json']) fs.copyFileSync('/tmp/w/' + f, '/out/' + f);
  const ls = npm(['ls', '--all', '--package-lock-only', ...common]);
  fs.writeFileSync('/out/ls.log', cap(ls.stdout) + cap(ls.stderr));
  status.ls_rc = ls.status;
}
fs.writeFileSync('/out/status.json', JSON.stringify(status));
"""
VIEWS_JS = r"""'use strict';
const fs = require('node:fs');
const { spawnSync } = require('node:child_process');
const specs = JSON.parse(fs.readFileSync('/in/views.json', 'utf8'));
const out = {};
for (const s of specs) {
  const r = spawnSync('npm', ['view', s, '--json', '--userconfig', '/in/npmrc', '--cache', '/tmp/c'],
                      { cwd: '/tmp', encoding: 'utf8', timeout: 60000, maxBuffer: 16 * 1024 * 1024 });
  out[s] = { rc: r.status, out: String(r.stdout || '').slice(0, 1000000) };
}
fs.writeFileSync('/out/views.json', JSON.stringify(out));
"""
NPMRC = "registry=https://registry.npmjs.org/\nignore-scripts=true\naudit=false\nfund=false\nupdate-notifier=false\nstrict-peer-deps=true\n"


# ---- settings, ids, timing ----------------------------------------------------------------------------------------------

def settings(cfg):
    """config env_packages, checked (the only validator): exactly the KEYS, each a whole number in its range."""
    m = (cfg or {}).get("env_packages")
    if not isinstance(m, dict):
        raise rj.Refused("config env_packages is missing")
    miss = [k for k in KEYS if k not in m]
    if miss:
        raise rj.Refused(f"config env_packages lacks {', '.join(miss)}")
    extra = sorted(set(m) - set(KEYS))
    if extra:
        raise rj.Refused(f"config env_packages has unknown keys: {', '.join(map(str, extra))}")
    out = {}
    for k, (lo, hi) in KEYS.items():
        v = m[k]
        if isinstance(v, bool) or not isinstance(v, int) or not lo <= v <= hi:
            raise rj.Refused(f"config env_packages.{k} must be a whole number from {lo} to {hi}")
        out[k] = v
    return out


def _epoch(text):
    try:
        return calendar.timegm(time.strptime(text, "%Y-%m-%dT%H:%M:%SZ"))
    except (ValueError, TypeError):
        return None


def _created_via_ui(job):
    return any(e.get("what") == "created" and e.get("via") == "ui" for e in job.data.get("log") or [] if isinstance(e, dict))


def container_name(job_id, part=""):
    return f"argus-env-{job_id}{part}"


# ---- the locks -----------------------------------------------------------------------------------------------------------

@contextmanager
def creation_lock(jobs_dir):
    """`jobs/.env.lock`, exclusive and not waited for: while it is held a request is being created (the one-live-job check, the day's count, the new
    name and the job file are one decision). A second request is refused at once."""
    d = Path(jobs_dir)
    d.mkdir(parents=True, exist_ok=True)
    fd = os.open(d / ".env.lock", os.O_CREAT | os.O_RDWR, 0o600)
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            raise rj.Refused("another package request is being created; try again in a moment") from None
        yield
    finally:
        os.close(fd)


def env_jobs(jobs_dir):
    """[Job] of every readable env job in the directory, oldest first; unreadable ones are skipped."""
    out = []
    root = Path(jobs_dir)
    try:
        names = sorted(p.name for p in root.iterdir() if p.is_dir() and (p / "job.json").exists())
    except OSError:
        return out
    for n in names:
        try:
            job = rj.open_job(n, root)
        except (rj.Refused, OSError, ValueError, KeyError):
            continue
        if job.data.get("kind") == KIND:
            out.append(job)
    return out


# ---- recovery and expiry ------------------------------------------------------------------------------------------------

def _remove_containers(job_id, docker):
    for part in ("", "-v", "-b"):
        try:
            docker.remove(container_name(job_id, part))
        except Exception:      # noqa: BLE001  (a container that is not there is the normal case)
            pass


def settle(job, deps, cfg, *, docker=None):
    """Bring one env job's state up to date on a read: AWAITING_HUMAN older than report_ttl_hours becomes ABANDONED; a job in NEW, RESOLVING or BUILDING whose
    lock nobody holds is a job whose process died and becomes FAILED (its containers removed). A job whose lock is held is alive and is not touched.
    Returns the state. Never raises for a job that is busy or gone."""
    docker = docker or Docker()
    s = settings(cfg)
    state = job.data.get("state")
    if state == AWAITING_HUMAN:
        age, now = _epoch(job.data.get("created_at")), _epoch(deps.clock())
        try:
            at = max(_epoch(e.get("at")) or 0 for e in job.data.get("log") or [] if e.get("what") == "state" and e.get("new") == AWAITING_HUMAN)
        except ValueError:
            at = age
        if at is not None and now is not None and now - at > s["report_ttl_hours"] * 3600:
            try:
                with job.lock():
                    if job.data.get("state") == AWAITING_HUMAN:
                        job.move(ABANDONED, deps, reason="expired")
            except rj.JobBusy:
                pass
        return job.data.get("state")
    if state in (NEW, RESOLVING, BUILDING):
        try:
            with job.lock():
                job.data = rj.open_job(job.id, job.dir.parent).data
                if job.data.get("state") in (NEW, RESOLVING, BUILDING):
                    job.move(FAILED, deps, reason="the process that ran it is gone")
                    _remove_containers(job.id, docker)
        except rj.JobBusy:
            pass
    return job.data.get("state")


# ---- creating a request -------------------------------------------------------------------------------------------------

def _environments(cfg):
    return ((cfg.get("sandbox") or {}).get("environments")) or {}


def _environment_of(cfg, repo):
    """(environment, problem) of a registered repository, which must run vitest (a Node environment)."""
    repos = (cfg.get("issue_writer") or {}).get("repos") or {}
    r = repos.get(repo) if isinstance(repo, str) else None
    env = r.get("environment") if isinstance(r, dict) else None
    envs = _environments(cfg)
    if not isinstance(env, str) or not isinstance(envs.get(env), dict):
        return None, f"{repo!r} is not a registered repository with an environment"
    if envs[env].get("runner") != "vitest":
        return None, f"{repo!r} does not run on a Node environment (vitest)"
    return env, None


def _taken_names(root, cfg, jobs_dir):
    """The names an environment may not take: the folders of environments/, the configured environments, the pins in the checkout and the names reserved by env
    jobs that have not ended."""
    taken = set()
    try:
        taken |= {p.name for p in (Path(root) / "environments").iterdir() if p.is_dir()}
    except OSError:
        pass
    taken |= set(_environments(cfg))
    try:
        for p in Path(root).glob(".sandbox_image_*"):
            n = p.name[len(".sandbox_image_"):]
            for suffix in (".check.json", ".json"):
                if n.endswith(suffix):
                    n = n[:-len(suffix)]
            taken.add(n)
    except OSError:
        pass
    for j in env_jobs(jobs_dir):
        if j.data.get("state") in LIVE + (READY,) and isinstance(j.data.get("inputs", {}).get("name"), str):
            taken.add(j.data["inputs"]["name"])
    return taken


def _read_json(path, limit=CANDIDATE_MAX):
    raw = Path(path).read_bytes()
    if len(raw) > limit:
        raise rj.Refused(f"{Path(path).name} is larger than {limit} bytes")
    try:
        return json.loads(raw.decode("utf-8"), object_pairs_hook=_pairs), raw
    except (ValueError, UnicodeDecodeError):
        raise rj.Refused(f"{Path(path).name} is not valid JSON") from None


def _pairs(pairs):
    out = {}
    for k, v in pairs:
        if k in out:
            raise ValueError("duplicate key")
        out[k] = v
    return out


@contextmanager
def start(*, repo, job_id, text, cfg, deps, jobs_dir=rj.JOBS, via=None, root=None, docker=None):
    """Create a request and yield its job (state NEW) with the JOB lock held and the creation lock already released: the CLI resolves inside this `with`. The job lock is
    taken while the creation lock is still held, so no reader can find the new job without a holder. Every refusal is a `Refused` with a sentence and nothing was created."""
    if via != "ui":
        raise rj.Refused("a package request is started from the chat (--via ui); nothing was started")
    root = rj.ROOT if root is None else root                     # read at the call, so a test can point it elsewhere
    from . import research as rr
    why = rr.ui_job_id_problem(job_id, deps.clock())
    if why:
        raise rj.Refused(f"{why}; nothing was started")
    s = settings(cfg)
    env, problem = _environment_of(cfg, repo)
    if problem:
        raise rj.Refused(f"{problem}; nothing was started")
    items, problem = ep.parse_lines(text)
    if problem:
        raise rj.Refused(f"{problem}; nothing was started")
    definition = Path(root) / "environments" / env
    base = (definition / "base").read_text().strip() if (definition / "base").is_file() else ""
    if not BASE_IMAGE.fullmatch(base):
        raise rj.Refused(f"environments/{env}/base is not an image pinned by digest; nothing was started")
    try:
        old, _ = _read_json(definition / "package-lock.json")
    except (OSError, rj.Refused):
        raise rj.Refused(f"environments/{env} has no readable package-lock.json; nothing was started") from None
    problem = ep.refuse_locked(items, old)
    if problem:
        raise rj.Refused(f"{problem}; nothing was started")
    docker = docker or Docker()
    holder = None
    try:
        with creation_lock(jobs_dir):
            for j in env_jobs(jobs_dir):
                settle(j, deps, cfg, docker=docker)
            jobs = env_jobs(jobs_dir)
            live = [j for j in jobs if j.data.get("state") in LIVE]
            if live:
                raise rj.Refused(f"package request {live[0].id} is still {live[0].data['state']}: one at a time; nothing was started")
            today = [j for j in jobs if str(j.data.get("created_at", ""))[:10] == deps.clock()[:10]]
            if len(today) >= s["max_per_day"]:
                raise rj.Refused(f"{len(today)} package requests were made today (at most {s['max_per_day']}); nothing was started")
            adopted = set(_environments(cfg))
            unadopted = [j for j in jobs if j.data.get("state") == READY and j.data.get("inputs", {}).get("name") not in adopted]
            if len(unadopted) >= s["max_ready_images"]:
                raise rj.Refused(f"{len(unadopted)} built environments wait to be adopted (at most {s['max_ready_images']}); adopt or prune one first")
            name, problem = ep.next_env_name(env, _taken_names(root, cfg, jobs_dir))
            if problem:
                raise rj.Refused(f"{problem}; nothing was started")
            job = rj.Job(Path(jobs_dir) / job_id)
            if job.file.exists():
                raise rj.Refused(f"job {job_id} already exists")
            holder = job.lock()
            holder.__enter__()                                  # held until the caller's `with` ends
            if job.data is not None:
                raise rj.Refused(f"job {job_id} already exists")
            job.data = {"job": job_id, "kind": KIND, "state": NEW, "created_at": deps.clock(), "max_usd": 0.0,
                        "inputs": {"repo": repo, "base_environment": env, "name": name, "packages": items, "base_image": base},
                        "stages": {}, "log": []}
            job.note(deps, "created", via=via)
    except BaseException:
        if holder is not None:
            holder.__exit__(None, None, None)
        raise
    try:
        yield job
    finally:
        holder.__exit__(None, None, None)


class Docker:
    """The one place that starts a container: `run(argv, timeout_s)` returns (returncode, stdout, stderr) and raises `Timeout` after removing the container
    by name; `remove(name)` is `docker rm -f NAME`. Tests pass a fake with the same two methods."""
    class Timeout(Exception):
        pass

    def run(self, argv, timeout_s, name):
        try:
            r = subprocess.run(argv, capture_output=True, text=True, timeout=timeout_s)
        except subprocess.TimeoutExpired:
            self.remove(name)
            raise Docker.Timeout(name) from None
        return r.returncode, r.stdout, r.stderr

    def remove(self, name):
        subprocess.run(["docker", "rm", "-f", name], capture_output=True, text=True, timeout=60)


def resolve_argv(job_id, base, in_dir, out_dir, script, s, *, part="", uid=None, gid=None):
    """The docker command line of a resolve or views step: hardened, non-root, read-only root with a small /tmp, the definition and the request mounted read-only,
    one output directory writable, a fixed script, no shell. The registry is the only host the npmrc names."""
    uid = os.getuid() if uid is None else uid
    gid = os.getgid() if gid is None else gid
    return ["docker", "run", "--rm", "--name", container_name(job_id, part), "--label", "argus.env=1",
            "--user", f"{uid}:{gid}", "--cap-drop", "ALL", "--security-opt", "no-new-privileges", "--read-only",
            "--tmpfs", f"/tmp:rw,size={s['tmp_mb']}m,mode=1777",
            "--memory", f"{s['memory_mb']}m", "--memory-swap", f"{s['memory_mb']}m", "--cpus", str(s["cpus"]), "--pids-limit", str(s["pids_limit"]),
            "-e", "HOME=/tmp", "-e", "npm_config_update_notifier=false", "--log-driver", "none",
            "-v", f"{in_dir}:/in:ro", "-v", f"{out_dir}:/out",
            "--entrypoint", "node", base, f"/in/{script}"]


def _before(now_text, days):
    """The age cutoff npm is given: now minus `days`, as an ISO time."""
    t = _epoch(now_text) - days * 86400
    return time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime(t))


def _classify(log):
    """A fixed sentence for what npm said (its text is data and is never shown): the first known code in it, else a plain failure."""
    for code, sentence in NPM_SENTENCES:
        if code in log:
            return sentence
    return "npm could not resolve the request"


def _read_log(path):
    try:
        return Path(path).read_text(encoding="utf-8", errors="replace")[:LOG_MAX]
    except OSError:
        return ""


def _refuse(job, deps, blocks, report=None):
    job.data["report"] = report or {"status": "REFUSED", "blocks": list(blocks), "warns": [], "notes": [], "packages": [], "totals": {"new": 0, "direct": 0, "changed": 0, "flags": 0, "removed": 0}}
    job.save()
    job.move(REFUSED, deps, reason="a gate refused the request")
    return job.data["report"]


def resolve(job, cfg, deps, *, root=None, docker=None):
    """Run the resolve and views steps for a job in NEW, under its lock (the caller holds it), and leave it in AWAITING_HUMAN with the report, REFUSED with the blocks,
    or FAILED. The report is the pure function's (router/env_packages.py); the candidate files and their sha are kept in the job's directory."""
    docker = docker or Docker()
    root = rj.ROOT if root is None else root
    s = settings(cfg)
    d = job.data
    if d.get("kind") != KIND or d.get("state") != NEW:
        raise rj.Refused(f"job {job.id} is not a new package request")
    inp = d["inputs"]
    definition = Path(root) / "environments" / inp["base_environment"]
    work = job.dir / "resolve"
    if work.exists():
        shutil.rmtree(work)
    in_dir, out_dir = work / "in", work / "out"
    in_dir.mkdir(parents=True)
    out_dir.mkdir()
    for f in ("package.json", "package-lock.json"):
        shutil.copyfile(definition / f, in_dir / f)
    items = inp["packages"]
    specs = [f"{i['name']}@{i['version']}" if i["version"] else i["name"] for i in items]
    (in_dir / "npmrc").write_text(NPMRC)
    (in_dir / "resolve.js").write_text(RESOLVE_JS)
    (in_dir / "views.js").write_text(VIEWS_JS)
    (in_dir / "request.json").write_text(json.dumps({"specs": specs, "before": _before(deps.clock(), s["min_age_days"])}))
    job.move(RESOLVING, deps)
    t0 = time.monotonic()

    def left():
        return max(1, int(s["resolve_timeout_s"] - (time.monotonic() - t0)))

    try:
        rc, _, _ = docker.run(resolve_argv(job.id, inp["base_image"], in_dir, out_dir, "resolve.js", s), left(), container_name(job.id))
    except Docker.Timeout:
        job.move(FAILED, deps, reason=f"the resolve step took longer than {s['resolve_timeout_s']} s")
        return None
    except OSError:
        job.move(FAILED, deps, reason="docker could not be started")
        return None
    try:
        status = json.loads((out_dir / "status.json").read_text())
    except (OSError, ValueError):
        status = None
    if rc != 0 or not isinstance(status, dict):
        job.move(FAILED, deps, reason="the resolve container did not finish")
        return None
    install_log = _read_log(out_dir / "install.log")
    if status.get("install_rc") != 0:
        return _refuse(job, deps, [_classify(install_log)])
    if "ERESOLVE" in install_log:
        return _refuse(job, deps, ["npm reports a peer-dependency conflict"])
    if status.get("ls_rc") != 0 or LS_PROBLEM.search(_read_log(out_dir / "ls.log")):
        return _refuse(job, deps, ["npm ls finds an invalid or missing dependency in the candidate"])
    try:
        old, _ = _read_json(definition / "package-lock.json")
        new, raw = _read_json(out_dir / "package-lock.json")
        pkg, _ = _read_json(out_dir / "package.json")
    except (OSError, rj.Refused, ValueError):
        return _refuse(job, deps, ["the candidate lock cannot be read"])
    if not isinstance(new, dict) or not isinstance(pkg, dict):
        return _refuse(job, deps, ["the candidate lock cannot be read"])
    lim = {**ep.limits({"env_packages": s})}
    direct = _direct_names(definition)
    a = ep.analyse(old, new, items, direct)
    views = {}
    shape_ok = isinstance(new, dict) and isinstance(new.get("packages"), dict) and all(ep.key_name(k) for k in new["packages"] if k != "")
    wanted = sorted({f"{ep.key_name(k)}@{e.get('version')}" for k, e in a["new"].items() if isinstance(e, dict) and isinstance(e.get("version"), str)
                     and ep.LOCK_VERSION.fullmatch(e["version"])}) if shape_ok else []
    if shape_ok and 0 < len(wanted) <= lim["max_new"]:
        (in_dir / "views.json").write_text(json.dumps(wanted))
        vout = work / "views"
        vout.mkdir()
        try:
            rc, _, _ = docker.run(resolve_argv(job.id, inp["base_image"], in_dir, vout, "views.js", s, part="-v"), left(), container_name(job.id, "-v"))
        except Docker.Timeout:
            job.move(FAILED, deps, reason=f"the registry step took longer than {s['resolve_timeout_s']} s in all")
            return None
        except OSError:
            job.move(FAILED, deps, reason="docker could not be started")
            return None
        try:
            got = json.loads((vout / "views.json").read_text())
        except (OSError, ValueError):
            got = None
        if rc != 0 or not isinstance(got, dict):
            job.move(FAILED, deps, reason="the registry container did not finish")
            return None
        for spec in wanted:
            r = got.get(spec)
            views[spec] = ep.parse_view(r.get("out")) if isinstance(r, dict) and r.get("rc") == 0 else None
    now = _now(deps)
    report = ep.build_report(items, old, new, views, now, lim, direct)
    cand = job.dir / "candidate"
    cand.mkdir(exist_ok=True)
    (cand / "package-lock.json").write_bytes(raw)
    (cand / "package.json").write_text(json.dumps(pkg, indent=2) + "\n")
    job.data["candidate"] = {"lock_sha256": ep.lock_sha(raw), "package_sha256": ep.lock_sha(json.dumps(pkg, indent=2) + "\n"), "lock_bytes": len(raw)}
    job.data["report"] = report
    job.save()
    if report["status"] == "REFUSED":
        job.move(REFUSED, deps, reason="a gate refused the request")
    else:
        job.move(AWAITING_HUMAN, deps)
    return report


def _direct_names(definition):
    """The set of names the environment's own package.json depends on, or None (every name counts as direct) when it cannot be read."""
    try:
        pkg, _ = _read_json(Path(definition) / "package.json", 1024 * 1024)
        if not isinstance(pkg, dict):
            return None
        names = set()
        for field in ("dependencies", "devDependencies", "peerDependencies", "optionalDependencies"):
            v = pkg.get(field)
            if isinstance(v, dict):
                names |= {k for k in v if isinstance(k, str)}
            elif v is not None:
                return None
        return names
    except (OSError, rj.Refused, ValueError):
        return None


def _now(deps):
    from datetime import datetime, timezone
    return datetime.fromtimestamp(_epoch(deps.clock()), tz=timezone.utc)


# ---- ending a request by hand ---------------------------------------------------------------------------------------------

def abandon(job_id, *, cfg, deps, jobs_dir=rj.JOBS, via=None, docker=None):
    """The human ends a request that has not built anything (NEW, RESOLVING or AWAITING_HUMAN): the name and the one live slot are free again."""
    if via != "ui":
        raise rj.Refused("a package request is ended from the chat (--via ui); nothing was changed")
    job = rj.open_job(job_id, jobs_dir)
    with job.lock():
        if job.data.get("kind") != KIND:
            raise rj.Refused(f"job {job_id} is not a package request")
        if not _created_via_ui(job):
            raise rj.Refused(f"job {job_id} was not started from the chat; nothing was changed")
        if job.data["state"] not in (NEW, RESOLVING, AWAITING_HUMAN):
            raise rj.Refused(f"job {job_id} is {job.data['state']}: only a request that built nothing can be abandoned; nothing was changed")
        job.move(ABANDONED, deps, reason="ended by the human")
    _remove_containers(job_id, docker or Docker())
    return job


def status_lines(job):
    """The env job's lines for `argus status`: facts from the harness only; the report's strings are the harness's own sentences and shaped values."""
    d = job.data
    inp = d.get("inputs") or {}
    lines = [f"repository {inp.get('repo')}, environment {inp.get('base_environment')}, new environment {inp.get('name')}",
             "requested: " + ", ".join(f"{p['name']}@{p['version'] or '(newest old enough)'}" for p in inp.get("packages") or [])]
    r = d.get("report")
    if isinstance(r, dict):
        t = r.get("totals") or {}
        lines.append(f"report: {r.get('status')}, {t.get('new', 0)} new package(s), {t.get('changed', 0)} changed, {t.get('flags', 0)} flag-only, {t.get('removed', 0)} removed")
        lines += [f"  BLOCK {b}" for b in r.get("blocks") or []]
        lines += [f"  WARN {w}" for w in r.get("warns") or []]
        lines += [f"  NOTE {n}" for n in r.get("notes") or []]
        for p in r.get("packages") or []:
            lines.append(f"  {p['name']}@{p['version']} {'direct' if p.get('direct') else 'transitive'}, age {p.get('age_days')} days, license {p.get('license')}")
    c = d.get("candidate")
    if isinstance(c, dict):
        lines.append(f"candidate lock sha256 {c.get('lock_sha256')}")
    return lines
