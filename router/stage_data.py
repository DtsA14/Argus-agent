"""Real Argus data for the staging container (docs/reviews/SPEC_STAGING_REAL_DATA.md, Atha 2026-10-30). No model.

  argus stage refresh   a new snapshot of jobs/: a projection through a field allowlist (A1), read consistently and
                        validated before it is published by an atomic symlink swap (A2); one refresh at a time (A3)
  argus stage monitor   refresh, then the smoke test of the live release against that snapshot; recorded in
                        monitor.jsonl; never starts, stops or replaces a container or the active snapshot (A5)
  argus stage report    /summary and /jobs of the live release, through its socket, as an escaped static HTML page and
                        a text summary in reports/ (0700, files 0600) (A4)

Layout under ~/argus-staging/data (host only: .refresh.lock and the .tmp-* builds; the container never sees them):
  pub/                         mounted read-only at /data in the container, and nothing else is
  pub/snap-<UTC>/manifest.json, pub/snap-<UTC>/jobs/<job>/job.json, .../jobs/<job>/runs/<run>/events.jsonl
  pub/jobs -> snap-<UTC>/jobs  (relative symlink; replaced with rename(), so a reader sees the old or the new one)
"""
import fcntl
import hashlib
import html
import json
import os
import re
import shutil
import stat
import time
from contextlib import contextmanager
from pathlib import Path

from harness.events import parse_lines
from harness.llm import reconcile_ledger

from . import job as rj

KEEP_SNAPSHOTS = 2
KEEP_REPORTS = 10
READ_TRIES = 3
LOCK_WAIT_S = 60                                          # a deploy's smoke test waits this long for a refresh

TIME = re.compile(r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(\.\d{1,6})?Z$")
JOB_ID = re.compile(r"^j[0-9a-z_]{1,40}$")
STAGE = re.compile(r"^[a-z][0-9]{1,3}$")
UPPER = re.compile(r"^[A-Z][A-Z_]{0,29}$")
LOWER = re.compile(r"^[a-z][a-z_]{0,39}$")
CALL_ID = re.compile(r"^[0-9a-z]{1,40}$")
MODEL = re.compile(r"^[a-z0-9_.-]{1,30}:[a-z0-9_.-]{1,60}$")
LOG_WHAT = {"created", "intaken", "state", "approved", "limits_shown", "confirmed", "confirmed_by_flag", "key_typed",
            "key_from_file", "retry", "redraft", "staged", "research_ok", "applied"}
# A second layer over the projection (A1): nothing like a key may be in what is published.
KEY = re.compile(rb"sk-ant-[A-Za-z0-9_-]{8,}|sk-[A-Za-z0-9_-]{20,}|(?i:api[_-]?key|secret|password|token)\"?\s*[:=]\s*\"")


class Excluded(Exception):
    """A job left out of the snapshot; the message names the field, never its value."""


class Refused(rj.Refused):
    pass


# ---- A1: the allowlist ---------------------------------------------------------------------------------------------

def _nonneg_int(v):
    return isinstance(v, int) and not isinstance(v, bool) and v >= 0


def _nonneg_num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool) and v >= 0 and v == v and v != float("inf")


def _pat(p):
    return lambda v: isinstance(v, str) and bool(p.match(v))


def _or_null(check):
    return lambda v: v is None or check(v)


JOB_FIELDS = {"job": _pat(JOB_ID), "kind": _pat(LOWER), "state": _pat(UPPER), "created_at": _pat(TIME),
              "max_usd": _nonneg_num}
STAGE_FIELDS = {"kind": _pat(LOWER), "run_id": None, "status": _or_null(_pat(UPPER)),   # run_id: checked with the job
                "started_at": _pat(TIME), "ended_at": _or_null(_pat(TIME)), "usd": _or_null(_nonneg_num)}
LOG_FIELDS = {"at": _pat(TIME), "what": lambda v: v in LOG_WHAT, "old": _pat(UPPER), "new": _pat(UPPER),
              "stage": _pat(STAGE)}
_CALL = {"call_id": _pat(CALL_ID), "model": _pat(MODEL), "node": _pat(LOWER), "role": _pat(LOWER),
         "ts": _nonneg_num}
EVENT_FIELDS = {
    "llm_call_started": {**_CALL, "worst_usd_nano": _or_null(_nonneg_int), "worst_tokens": _nonneg_int},
    "llm_call": {**_CALL, "status": _pat(LOWER), "usd_nano": _or_null(_nonneg_int), "tokens": _nonneg_int,
                 "input_tokens": _nonneg_int, "output_tokens": _nonneg_int, "cache_read": _or_null(_nonneg_int),
                 "est_input": _nonneg_int},
    "attempt_end": {"reason": _pat(LOWER), "steps": _nonneg_int, "node": _pat(LOWER), "ts": _nonneg_num},
}


def _pick(raw, fields, where):
    """The allowed fields of `raw` that it has, each checked; a wrong one excludes the job (Excluded)."""
    out = {}
    for name, check in fields.items():
        if name in raw:
            if check is not None and not check(raw[name]):
                raise Excluded(f"{where}.{name} is not allowed as it is")
            out[name] = raw[name]
    return out


def project_job(raw, job_id):
    """The published form of one job.json: only the allowlisted fields, every value checked (A1)."""
    if not isinstance(raw, dict):
        raise Excluded("job.json is not an object")
    out = _pick(raw, JOB_FIELDS, "job")
    if out.get("job", job_id) != job_id:
        raise Excluded("job.job is not its directory")
    stages = raw.get("stages", {})
    if not isinstance(stages, dict):
        raise Excluded("job.stages is not an object")
    out["stages"] = {}
    for name, stage in stages.items():
        if not (isinstance(name, str) and STAGE.match(name)) or not isinstance(stage, dict):
            raise Excluded("a stage name or stage is not allowed")
        s = _pick(stage, STAGE_FIELDS, f"stages.{name}")
        if "run_id" in s and s["run_id"] != f"{job_id}-{name}":
            raise Excluded(f"stages.{name}.run_id is not {job_id}-{name}")
        out["stages"][name] = s
    if "log" in raw:
        if not isinstance(raw["log"], list):
            raise Excluded("job.log is not a list")
        out["log"] = []
        for entry in raw["log"]:
            if not isinstance(entry, dict):
                raise Excluded("a log entry is not an object")
            out["log"].append(_pick(entry, LOG_FIELDS, "log"))
    return out


def project_events(text):
    """The published lines of one events.jsonl: the three ledger events only, their allowlisted fields checked. A line
    that is not JSON (a writer's cut last line) is left out; an allowed event with a wrong field excludes the job."""
    out = []
    for line in text.splitlines():
        try:
            e = json.loads(line)
        except ValueError:
            continue
        if not isinstance(e, dict) or e.get("event") not in EVENT_FIELDS:
            continue
        out.append({"event": e["event"], **_pick(e, EVENT_FIELDS[e["event"]], e["event"])})
    return out


def ledger_nano(events):
    """The harness's own cost of a ledger (router.job and the job cap use the same function)."""
    return reconcile_ledger(events)[1]["usd_nano"]


def _jsonl(events):
    return "".join(json.dumps(e, sort_keys=True) + "\n" for e in events)


# ---- A2: one job, read consistently ----------------------------------------------------------------------------------

_DIR = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW


def _open_dir(name, dir_fd=None):
    """A directory that is not a symlink, opened by its name in dir_fd (openat): a path swapped for a link after a
    check can never redirect a read, since every step is one name in an already opened directory."""
    return os.open(name, _DIR, dir_fd=dir_fd)


def _read_at(dir_fd, name):
    """The bytes of regular file `name` in dir_fd, never through a symlink (O_NOFOLLOW), or OSError."""
    fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=dir_fd)
    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            raise OSError(f"{name} is not a regular file")
        with os.fdopen(fd, "rb", closefd=False) as f:
            return f.read()
    finally:
        os.close(fd)


def read_job(source_fd, job_id):
    """(job.json bytes, {run: events bytes}) of jobs/<job_id>, read through directory fds, so that they belong
    together: job.json is read before and after its ledgers and must not change, and no ledger may shrink between two
    reads; otherwise tried again (READ_TRIES), then Excluded. Run directories that are not <job>-<stage>, symlinks, and
    anything that is not a regular file are not read."""
    jfd = _open_dir(job_id, source_fd)
    fds = [jfd]
    try:
        run_fds = {}
        try:
            rfd = _open_dir("runs", jfd)
            fds.append(rfd)
            for run in sorted(os.listdir(rfd)):
                if run.startswith(job_id + "-") and STAGE.match(run[len(job_id) + 1:]):
                    try:
                        run_fds[run] = _open_dir(run, rfd)
                        fds.append(run_fds[run])
                    except OSError:
                        continue                          # a symlink or not a directory: never read
        except FileNotFoundError:
            pass
        for _ in range(READ_TRIES):
            before = _read_at(jfd, "job.json")
            runs = {}
            for run, fd in run_fds.items():
                try:
                    runs[run] = _read_at(fd, "events.jsonl")
                except FileNotFoundError:
                    continue
            after = _read_at(jfd, "job.json")
            grew = all(len(_read_at(run_fds[r], "events.jsonl")) >= len(b) for r, b in runs.items())
            if before == after and grew:
                return before, runs
            time.sleep(0.2)
        raise Excluded("job.json or a ledger kept changing while it was read")
    finally:
        for fd in fds:
            os.close(fd)


# ---- A2/A3: refresh ----------------------------------------------------------------------------------------------------

@contextmanager
def refresh_lock(data, wait_s=0):
    """The one lock refresh, monitor and a deploy's smoke test share (A3). wait_s 0: Refused at once when busy."""
    data.mkdir(parents=True, exist_ok=True)
    fd = os.open(data / ".refresh.lock", os.O_RDWR | os.O_CREAT, 0o600)
    try:
        deadline = time.monotonic() + wait_s
        while True:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.monotonic() >= deadline:
                    raise Refused("busy: another refresh, monitor or smoke test holds the data lock") from None
                time.sleep(0.2)
        yield
    finally:
        os.close(fd)


def pub(data):
    """The published part of `data`: the only directory the container mounts (security review: the lock and the
    builds stay outside it, so a release can neither hold the lock nor read a snapshot before it is validated)."""
    return data / "pub"


def current(data):
    """The published snapshot directory `pub/jobs` points to, or None."""
    link = pub(data) / "jobs"
    if not link.is_symlink():
        return None
    target = os.readlink(link)
    if not re.fullmatch(r"snap-\d{8}T\d{6}Z(-\d+)?/jobs", target):
        return None
    snap = pub(data) / Path(target).parent
    return snap if (snap / "manifest.json").is_file() else None


def manifest(data):
    """The active snapshot's manifest, or None (no snapshot, or one whose manifest cannot be read)."""
    snap = current(data)
    try:
        man = json.loads((snap / "manifest.json").read_text(encoding="utf-8")) if snap else None
    except (OSError, ValueError):
        return None
    return man if isinstance(man, dict) and isinstance(man.get("jobs"), list) else None


def _writable(path):
    for p in [path, *Path(path).rglob("*")]:
        if not p.is_symlink():
            p.chmod(0o755 if p.is_dir() else 0o644)


def _read_only(path):
    for p in sorted(Path(path).rglob("*"), reverse=True):
        if not p.is_symlink():
            p.chmod(0o555 if p.is_dir() else 0o444)
    Path(path).chmod(0o555)


def _remove(path):
    if os.path.lexists(path):
        _writable(path)
        shutil.rmtree(path)


def build(source, tmp):
    """Project every job of `source` into tmp/jobs; the manifest of what was written. Nothing is published here."""
    jobs, excluded, total = {}, [], 0
    (tmp / "jobs").mkdir()
    source_fd = _open_dir(str(source))
    try:
        names = sorted(n for n in os.listdir(source_fd) if JOB_ID.match(n))
        for job_id in names:
            got = _one(source_fd, job_id, excluded)
            if got is None:
                continue
            job, runs, nano = got
            d = tmp / "jobs" / job_id
            (d / "runs").mkdir(parents=True)
            (d / "job.json").write_text(json.dumps(job, indent=1) + "\n", encoding="utf-8")   # stage order kept
            for run, events in runs.items():
                (d / "runs" / run).mkdir()
                (d / "runs" / run / "events.jsonl").write_text(_jsonl(events), encoding="utf-8")
            jobs[job_id], total = nano, total + nano
    finally:
        os.close(source_fd)
    return {"jobs": sorted(jobs), "cost_nano": total, "per_job": jobs, "excluded": excluded}


def _one(source_fd, job_id, excluded):
    """(projected job, {run: projected events}, nano) of one job, or None: not a job (not a directory, a symlink, no
    job.json), or excluded (noted in `excluded`, never with a value)."""
    try:
        jfd = _open_dir(job_id, source_fd)
    except OSError:
        return None
    try:
        os.stat("job.json", dir_fd=jfd, follow_symlinks=False)
    except FileNotFoundError:
        return None
    finally:
        os.close(jfd)
    try:
        raw_job, raw_runs = read_job(source_fd, job_id)
        try:
            job = project_job(json.loads(raw_job), job_id)
        except ValueError:
            raise Excluded("job.json is not JSON") from None
        runs, nano = {}, 0
        for run, raw in raw_runs.items():
            text = raw.decode("utf-8", "replace")
            events = project_events(text)
            try:
                same = ledger_nano(events) == ledger_nano(parse_lines(text))   # A2: the projection keeps the cost
            except (KeyError, TypeError, ValueError):
                raise Excluded(f"the ledger of {run} cannot be costed") from None
            if not same:
                raise Excluded(f"the cost of {run} changes in the projection")
            runs[run], nano = events, nano + ledger_nano(events)
    except Excluded as e:
        excluded.append({"job": job_id, "why": str(e)[:200]})
        return None
    except OSError as e:
        excluded.append({"job": job_id, "why": f"unreadable: {type(e).__name__}"})
        return None
    return job, runs, nano


def validate(tmp, man):
    """A2, before publication: every written file again through the allowlist (it must project to itself), the costs
    again from the written ledgers, the key scan over every byte, and nothing but the expected files. [] or problems."""
    problems, files = [], {}
    root = tmp / "jobs"
    for p in sorted(root.rglob("*")):
        rel = p.relative_to(root).as_posix()
        if p.is_symlink() or not (p.is_dir() or p.is_file()):
            problems.append(f"{rel} is not a plain file or directory")
        elif p.is_file():
            if not re.fullmatch(r"j[0-9a-z_]{1,40}/(job\.json|runs/j[0-9a-z_]{1,40}-[a-z][0-9]{1,3}/events\.jsonl)", rel):
                problems.append(f"{rel} is not a snapshot file")
            data = p.read_bytes()
            if KEY.search(data):
                problems.append(f"{rel} matches a key pattern")
            files[rel] = hashlib.sha256(data).hexdigest()
    for job_id, nano in man["per_job"].items():
        try:
            job = json.loads((root / job_id / "job.json").read_text(encoding="utf-8"))
            if project_job(job, job_id) != job:
                problems.append(f"{job_id}/job.json does not project to itself")
            got = 0
            for log in sorted((root / job_id / "runs").glob("*/events.jsonl")):
                events = [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines()]
                if project_events(log.read_text(encoding="utf-8")) != events:
                    problems.append(f"{job_id}/{log.parent.name} does not project to itself")
                got += ledger_nano(events)
            if got != nano:
                problems.append(f"{job_id}: cost {got} written, {nano} read")
        except (OSError, ValueError, Excluded) as e:
            problems.append(f"{job_id}: {type(e).__name__}: {str(e)[:120]}")
    if sorted(p.name for p in root.iterdir()) != man["jobs"]:
        problems.append("the job directories are not the manifest's jobs")
    man["files"] = files
    return problems


def refresh(source, data, *, clock=time.gmtime, held=False):
    """A2: build in a temporary directory, validate, publish with an atomic swap of the `jobs` symlink. Any failure
    removes the temporary directory and leaves `jobs` on the snapshot it was on. The new manifest, or Refused."""
    with (_nothing() if held else refresh_lock(data)):
        data.mkdir(parents=True, exist_ok=True)
        for old in data.glob(".tmp-*"):                   # left by a refresh that crashed
            _remove(old)
        stamp = time.strftime("%Y%m%dT%H%M%SZ", clock())
        tmp = data / f".tmp-{stamp}-{os.getpid()}"
        try:
            tmp.mkdir()
            man = build(source, tmp)
            problems = validate(tmp, man)
            if man["excluded"] and len(man["excluded"]) * 2 > len(man["excluded"]) + len(man["jobs"]):
                problems.append(f"{len(man['excluded'])} of {len(man['excluded']) + len(man['jobs'])} jobs excluded "
                                "(more than half: Argus's format changed, or the data is damaged)")
            if problems:
                raise Refused("the snapshot was not published: " + "; ".join(problems[:5]))
            man.update(at=time.strftime("%Y-%m-%dT%H:%M:%SZ", clock()))   # no host path: the container reads it
            (tmp / "manifest.json").write_text(json.dumps(man, indent=1, sort_keys=True) + "\n", encoding="utf-8")
            _read_only(tmp)
            tmp.chmod(0o755)                            # moving a directory to another parent rewrites its ".."
            out = pub(data)
            out.mkdir(exist_ok=True)
            name, n = f"snap-{stamp}", 1
            while os.path.lexists(out / name):
                name, n = f"snap-{stamp}-{n}", n + 1
            os.rename(tmp, out / name)
            (out / name).chmod(0o555)                   # before the link points to it
        except BaseException:
            _remove(tmp)
            raise
        link = out / f".jobs-{os.getpid()}"
        if os.path.lexists(link):
            os.unlink(link)
        os.symlink(f"{name}/jobs", link)
        os.replace(link, out / "jobs")                   # atomic: readers see the old snapshot or the new one
        live = current(data)
        snaps = sorted(p for p in out.glob("snap-*") if p.is_dir())
        for old in snaps[:-KEEP_SNAPSHOTS]:
            if old != live:
                _remove(old)
        return man


@contextmanager
def _nothing():
    yield


# ---- A5: monitor ------------------------------------------------------------------------------------------------------

def _append(path, rec):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        f.write(json.dumps(rec, sort_keys=True) + "\n")


def monitor(st, source, *, clock=time.gmtime, viewer=None):
    """Refresh, then smoke-test the live release against the active snapshot; one record in monitor.jsonl. Never a
    docker start, stop or rm, never state.json, never the active snapshot removed (A5). With `viewer`
    (SPEC_PWA_VIEWER S3), the viewer's live release is smoke-tested too, through the always-on proxy; its release is
    never changed, and a failed viewer smoke test fails the run. Returns the record."""
    rec = {"at": time.strftime("%Y-%m-%dT%H:%M:%SZ", clock())}
    try:
        with refresh_lock(st.data):
            try:
                rec["refresh"] = {"ok": True, "jobs": len(refresh(source, st.data, clock=clock, held=True)["jobs"])}
            except Exception as e:                    # noqa: BLE001  (A5: the last valid snapshot stays in use)
                rec["refresh"] = {"ok": False, "why": f"{type(e).__name__}: {str(e)[:300]}"}
            try:
                live = st.state()["live"]
            except rj.Refused as e:
                live, rec["why"] = None, str(e)[:300]
            rec["release"], rec["snapshot"] = live, (manifest(st.data) or {}).get("at")
            if live:
                results = st.smoke(live, held=True)
                rec["smoke"] = [list(r) for r in results]
                rec["ok"] = all(r[1] for r in results) and rec["refresh"]["ok"]
                if not all(r[1] for r in results) and st.state()["live"] != live:
                    rec["ok"], rec["why"] = None, "the live release changed during the smoke test"
            else:
                rec["ok"] = False
                rec.setdefault("why", "nothing is live")
            if viewer is not None:
                rec["viewer"] = _viewer_smoke(viewer)
                if rec["viewer"] and rec["viewer"]["ok"] is False and rec["ok"]:
                    rec["ok"] = False
    except Refused as e:                              # busy: another refresh or monitor; nothing was touched
        rec.update(ok=None, why=str(e)[:300])
    _append(st.base / "monitor.jsonl", rec)
    return rec


def _viewer_smoke(viewer):
    """{release, ok, smoke} of the viewer's live release (the data lock is held by monitor), or None: nothing live."""
    from . import stage_viewer as sv
    try:
        live = viewer.state()["live"]
    except rj.Refused as e:
        return {"release": None, "ok": False, "why": str(e)[:300]}
    if not live:
        return None
    try:
        with viewer.lock():                       # never between a viewer deploy's swap and its record
            live = viewer.state()["live"]
            results = sv.smoke(viewer, sv.PORT, held=True)
    except sv.Refused as e:
        return {"release": live, "ok": None, "why": str(e)[:300]}
    return {"release": live, "ok": all(r[1] for r in results), "smoke": [list(r) for r in results]}


def busy(rec):
    return rec.get("ok") is None and str(rec.get("why", "")).startswith("busy")


def monitor_summary(st):
    """(last monitor record or None, runs in a row that did not pass). A busy run counts as not passing: a lock held
    for longer than one run is a problem to see, never a quiet pass (security review). A run skipped because the live
    release changed during it counts as neither."""
    recs = [r for r in _records(st.base / "monitor.jsonl") if r.get("ok") is not None or busy(r)]
    failed = 0
    for r in reversed(recs):
        if r.get("ok"):
            break
        failed += 1
    return (recs[-1] if recs else None), failed


def _records(path):
    try:
        lines = Path(path).read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    out = []
    for line in lines:
        try:
            e = json.loads(line)
        except ValueError:
            continue
        if isinstance(e, dict):
            out.append(e)
    return out


# ---- A4: report --------------------------------------------------------------------------------------------------------

def _e(v):
    return html.escape("" if v is None else str(v), quote=True)


def report(st, get, *, clock=time.gmtime):
    """The live release's /summary and /jobs, through its socket, as an escaped static page and a text summary in
    reports/<UTC>/ (directories 0700, files 0600; the last KEEP_REPORTS kept). Returns the report directory."""
    from .stage import HOST
    live = st.state()["live"]
    if not live:
        raise Refused("nothing is live")
    sock = st.dir(live) / "sock" / "app.sock"
    peer = st.container_pid(live)
    if peer is None:
        raise Refused(f"the container of {live} is not running")
    out = {}
    for url in ("/summary", "/jobs"):
        status, body = get(sock, HOST, url, peer=peer)
        if status != 200:
            raise Refused(f"{url} answered {status}")
        out[url] = json.loads(body)
    summary, jobs = out["/summary"], out["/jobs"]
    if not isinstance(summary, dict) or not isinstance(jobs, list):
        raise Refused("unexpected answer shapes")
    stamp = time.strftime("%Y%m%dT%H%M%SZ", clock())
    reports = st.base / "reports"
    reports.mkdir(mode=0o700, parents=True, exist_ok=True)
    reports.chmod(0o700)
    d = reports / stamp
    d.mkdir(mode=0o700)
    rows = "".join(
        "<tr>" + "".join(f"<td>{_e(j.get(k)) if isinstance(j, dict) else ''}</td>"
                         for k in ("job", "state", "created_at", "stages", "cost_usd", "running")) + "</tr>\n"
        for j in jobs)
    page = (
        "<!DOCTYPE html>\n<html><head><meta charset=\"utf-8\">\n"
        "<meta http-equiv=\"Content-Security-Policy\" content=\"default-src 'none'; style-src 'unsafe-inline'\">\n"
        f"<title>argus-ledger staging {_e(stamp)}</title>\n"
        "<style>body{font:14px system-ui,sans-serif;margin:16px}table{border-collapse:collapse}"
        "td,th{border:1px solid #999;padding:2px 6px;text-align:left}</style></head><body>\n"
        f"<h1>argus-ledger staging</h1>\n<p>release {_e(live)}; snapshot {_e((manifest(st.data) or {}).get('at'))}; "
        f"report {_e(stamp)}</p>\n"
        f"<p>jobs {_e(summary.get('jobs'))}, cost ${_e(summary.get('cost_usd'))}, skipped {_e(summary.get('skipped'))}"
        "</p>\n<table><tr><th>job</th><th>state</th><th>created</th><th>stages</th><th>cost $</th><th>running</th></tr>\n"
        f"{rows}</table></body></html>\n")
    def plain(v, pattern=r"\d{1,12}(\.\d{1,12})?"):         # the app's values in a text file: digits or "?"
        return str(v) if isinstance(v, (int, str)) and not isinstance(v, bool) and re.fullmatch(pattern, str(v)) else "?"
    text = (f"release {live}\njobs {plain(summary.get('jobs'))}  cost ${plain(summary.get('cost_usd'))}  "
            f"skipped {plain(summary.get('skipped'))}\n")
    for name, content in (("report.html", page), ("summary.txt", text)):
        fd = os.open(d / name, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(content)
    for old in sorted(p for p in reports.iterdir() if p.is_dir())[:-KEEP_REPORTS]:
        shutil.rmtree(old)
    return d
