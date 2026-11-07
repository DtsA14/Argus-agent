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
  .../jobs/<job>/draft/meta.json, review.md, judge.md: the review of the job's latest draft stage and its latest judge
                               verdict (SPEC_CONTROL_UI D1), only when that stage's draft.json hashes to its draft_sha256
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
# provider:model, an OpenRouter model as vendor/name with an optional :variant (#357: the judge and research jobs
# use openrouter:z-ai/glm-5.3, openrouter:nvidia/...:free; 36 of 112 jobs were left out before)
MODEL = re.compile(r"^[a-z0-9_.-]{1,30}:[a-z0-9][a-z0-9_.-]{0,59}(/[a-z0-9][a-z0-9_.-]{0,79})?(:[a-z0-9][a-z0-9_.-]{0,19})?$")
LOG_WHAT = {"created", "intaken", "state", "approved", "limits_shown", "confirmed", "confirmed_by_flag", "key_typed",
            "key_from_file", "retry", "redraft", "staged", "research_ok", "applied", "stage_started"}
# A second layer over the projection (A1): nothing like a key may be in what is published.
KEY = re.compile(rb"sk-ant-[A-Za-z0-9_-]{8,}|sk-[A-Za-z0-9_-]{20,}|(?i:api[_-]?key|secret|password|token)\"?\s*[:=]\s*\"")


# SPEC_CONTROL_UI D1: the draft review files. Control characters other than \n and \t are removed (C0, DEL, C1), and
# so are the invisible format characters that make text read otherwise than it is (bidi overrides and isolates,
# zero-width characters, BOM: review of PR #357), since a human approves what the page shows.
TEXT_MAX = 256 * 1024
MARK_ROOM = 64                                            # the cut text and its marker stay within TEXT_MAX
LIST_MAX = 50
CONTROL = re.compile("[\x00-\x08\x0b-\x1f\x7f-\x9f\u200b-\u200f\u202a-\u202e\u2060-\u2069\ufeff]")
READ_MAX = 16 * 1024 * 1024                               # a source file larger than this is not read at all
SHA = re.compile(r"^[0-9a-f]{64}$")
JUDGE_FILE = re.compile(r"^JUDGE-j([0-9]{1,3})\.md$")
DRAFT_FILES = ("meta.json", "review.md", "judge.md")


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


def _read_at(dir_fd, name, single=False, limit=None):
    """The bytes of regular file `name` in dir_fd, never through a symlink (O_NOFOLLOW), or OSError. single: the file
    has no other name (D1, F1: no hardlink brings another file in); limit: at most this many bytes (else OSError)."""
    fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=dir_fd)
    try:
        st = os.fstat(fd)
        if not stat.S_ISREG(st.st_mode) or (single and st.st_nlink != 1):
            raise OSError(f"{name} is not a regular file" + (" with one name" if single else ""))
        if limit is not None and st.st_size > limit:
            raise OSError(f"{name} is larger than {limit} bytes")
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


# ---- D1 (SPEC_CONTROL_UI 3): the latest draft's review, read-only ----------------------------------------------------

def _read_single(dir_fd, name):
    return _read_at(dir_fd, name, single=True, limit=READ_MAX)


def clean_text(raw):
    """D1 for one file: valid UTF-8 (else Excluded), control characters other than \\n and \\t removed, cut at a line
    end with the marker `[dipotong harness: N byte]` to stay within TEXT_MAX, and no key pattern (else Excluded)."""
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        raise Excluded("not valid UTF-8") from None
    data = CONTROL.sub("", text).encode("utf-8")
    if len(data) > TEXT_MAX:
        cut = data[:TEXT_MAX - MARK_ROOM]
        cut = cut[:cut.rfind(b"\n") + 1] if b"\n" in cut else cut
        kept = cut.decode("utf-8", "ignore")              # a character cut in two is dropped, and counted
        text = kept + f"[dipotong harness: {len(data) - len(kept.encode('utf-8'))} byte]\n"
    else:
        text = data.decode("utf-8")
    if KEY.search(text.encode("utf-8")):
        raise Excluded("matches a key pattern")
    return text


def _short(v, limit):
    """One summary string: control characters removed, whitespace collapsed, cut to `limit` as cell() does in
    DRAFT_REVIEW.md (without its table escaping: this is JSON)."""
    t = " ".join(CONTROL.sub("", str(v if v is not None else "")).split())
    return t if len(t) <= limit else t[:limit - 3] + "..."


def _list(items, limit, mark=None):
    """At most LIST_MAX items; more: the first LIST_MAX - 1 and a marker naming how many were left out."""
    items = list(items or [])
    if len(items) <= LIST_MAX:
        return [_short(i, limit) for i in items] if mark is None else items
    kept, left = items[:LIST_MAX - 1], len(items) - (LIST_MAX - 1)
    marker = f"[dipotong harness: {left}]"
    return ([_short(i, limit) for i in kept] + [marker]) if mark is None else kept + [mark(marker)]


def _strings(v):
    """Every string inside a JSON value: the key scan reads each one as it is, not as JSON escapes it (`\\"`)."""
    if isinstance(v, str):
        yield v
    elif isinstance(v, dict):
        for x in v.values():
            yield from _strings(x)
    elif isinstance(v, list):
        for x in v:
            yield from _strings(x)


def _lists(v):
    if isinstance(v, list):
        yield v
        for x in v:
            yield from _lists(x)
    elif isinstance(v, dict):
        for x in v.values():
            yield from _lists(x)


def _has_key(v):
    return any(KEY.search(t.encode("utf-8")) for t in _strings(v))


def _money(v):
    return v if _nonneg_num(v) else None


def draft_summary(draft, report, stage):
    """Amendment 1: what the approve page is built from, from draft.json and check_report.json of one stage, with the
    functions DRAFT_REVIEW.md is rendered with (codetask.drafter), never from the markdown."""
    from acceptance import draft as dr
    from codetask import drafter as cd
    c, p = draft["contract"], draft["plan"]
    paths, red = dr.red_paths(draft), []
    for v in c["validation"]:
        b = (report.get("baseline") or {}).get(v.get("id")) or {}
        for n in v.get("must_pass") or []:
            if n.split("::", 1)[0] not in paths:
                continue
            line = cd.red_lines(b, [n])[0]
            red.append({"validation": _short(v.get("id"), 160), "test": _short(n, 300),
                        "status": _short((b.get("must_pass") or {}).get(n), 40),
                        "reason": _short(line[len(n) + 2:] if line.startswith(n + ": ") else line, 500)})
    warn = cd.warnings(draft) + [w for w in [cd.call_path_warning(draft, report)] if w]
    return {"draft_sha256": report["draft_sha256"],
            "cost": {"usd": _money(stage.get("usd")), "cap_usd": _money(stage.get("cap_usd"))},
            "conflicts": _list(dr.conflict_entries(draft), 500),
            "red": _list(red, None, mark=lambda m: {"validation": "", "test": m, "status": "", "reason": ""}),
            "plan": {"files": _list(p["files"], 160), "steps": _list(p["steps"], 500), "risks": _list(p["risks"], 500)},
            "scope": {"writable": _list(c["scope"]["writable"], 160), "protected": _list(c["scope"]["protected"], 160)},
            "warnings": _list(warn, 500), "unverifiable": _list(draft.get("unverifiable"), 500)}


def _latest(stages, kind):
    names = [n for n, s in stages.items() if isinstance(n, str) and STAGE.match(n) and isinstance(s, dict)
             and s.get("kind") == kind]
    return max(names, key=lambda n: int(n[1:])) if names else None


def _judge_of(stages, sha):
    """JUDGE-jN.md of the latest judge stage that judged the draft with this sha (its stage records draft_sha256), or
    None: a verdict on an earlier draft is never shown beside a later one (review of PR #357)."""
    judged = {n: s for n, s in stages.items() if isinstance(n, str) and STAGE.match(n) and isinstance(s, dict)
              and s.get("kind") == "judge" and s.get("draft_sha256") == sha}
    return f"JUDGE-{max(judged, key=lambda n: int(n[1:]))}.md" if judged else None


def draft_view(source_fd, job_id, raw):
    """({file: text} for jobs/<job>/draft/, [why something was left out]) of one job (D1). The review, the summary and
    the sha come from the latest draft stage's own directory: its draft.json, hashed canonically again, must equal the
    stage's draft_sha256 in job.json, and check_report.json must name that sha too (F1b, F6); otherwise nothing of that
    stage is published. Files are read by name in opened directories, never through a link (F1)."""
    stages = raw.get("stages") if isinstance(raw, dict) else None
    sid = _latest(stages, "draft") if isinstance(stages, dict) else None
    if sid is None:
        return {}, []
    stage, why = stages[sid], []
    want = stage.get("draft_sha256")
    if not (isinstance(want, str) and SHA.match(want)):
        return {}, [f"{sid}: the stage has no draft_sha256 (nothing to review)"]
    fds = []
    try:
        try:
            fds.append(_open_dir(job_id, source_fd))
            fds.append(_open_dir("runs", fds[0]))
            fds.append(_open_dir(f"{job_id}-{sid}", fds[1]))
            draft = json.loads(_read_single(fds[2], "draft.json"))
            sha = rj.draft_sha_of(draft)
        except (OSError, ValueError, TypeError):
            return {}, [f"{sid}: draft.json cannot be read"]
        if sha != want:
            return {}, [f"{sid}: draft.json does not hash to the stage's draft_sha256"]
        meta = {"stage": sid, "draft_sha256": sha, "review": None, "summary": None, "judge": None}
        files = {}
        try:
            files["review.md"] = clean_text(_read_single(fds[2], "DRAFT_REVIEW.md"))
            meta["review"] = {"sha256": hashlib.sha256(files["review.md"].encode("utf-8")).hexdigest()}
        except (OSError, Excluded) as e:
            why.append(f"{sid}: DRAFT_REVIEW.md not published: {e if isinstance(e, Excluded) else 'unreadable'}")
        try:
            report = json.loads(_read_single(fds[2], "check_report.json"))
            if not isinstance(report, dict) or report.get("draft_sha256") != sha:
                raise Excluded("check_report.json is for another draft")
            summary = draft_summary(draft, report, stage)
            if _has_key(summary):
                raise Excluded("matches a key pattern")
            meta["summary"] = summary
        except Excluded as e:
            why.append(f"{sid}: summary not published: {e}")
        except Exception as e:                        # noqa: BLE001  (only the summary is lost, not the review)
            why.append(f"{sid}: summary not published: {type(e).__name__}")
        judge = _judge_of(stages, sha)
        if judge:
            try:
                files["judge.md"] = clean_text(_read_single(fds[0], judge))
                meta["judge"] = {"file": judge, "sha256": hashlib.sha256(files["judge.md"].encode("utf-8")).hexdigest()}
            except (OSError, Excluded) as e:
                why.append(f"{judge} not published: {e if isinstance(e, Excluded) else 'unreadable'}")
        files["meta.json"] = json.dumps(meta, indent=1, ensure_ascii=False) + "\n"
        return files, why
    finally:
        for fd in fds:
            os.close(fd)


META_KEYS = {"stage", "draft_sha256", "review", "summary", "judge"}


def draft_problems(job_dir, job):
    """validate() for jobs/<job>/draft: the meta names a draft stage of the published job and the sha of each text it
    lists, each text follows D1 (UTF-8, no control characters, within TEXT_MAX), and no text is there unlisted."""
    d = job_dir / "draft"
    if not d.exists():
        return []
    problems, names = [], sorted(p.name for p in d.iterdir())
    if "meta.json" not in names:
        return ["no meta.json"]
    try:
        meta = json.loads((d / "meta.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return ["meta.json is not JSON"]
    if not isinstance(meta, dict) or set(meta) != META_KEYS:
        return ["meta.json has other fields"]
    stage = meta["stage"] if isinstance(meta["stage"], str) and STAGE.match(meta["stage"]) else None
    if stage is None or ((job.get("stages") or {}).get(stage) or {}).get("kind") != "draft":
        problems.append("meta.json names no draft stage of the job")
    judge = meta["judge"]
    if judge is not None and not (isinstance(judge, dict) and isinstance(judge.get("file"), str)
                                  and JUDGE_FILE.match(judge["file"])):
        problems.append("meta.json names no judge file")
    if any(CONTROL.search(t) for t in _strings(meta)):
        problems.append("meta.json has control characters")
    if any(len(v) > LIST_MAX for v in _lists(meta["summary"])):
        problems.append("the summary has a list longer than the limit")
    if not (isinstance(meta["draft_sha256"], str) and SHA.match(meta["draft_sha256"])):
        problems.append("meta.json has no draft sha")
    if meta["summary"] is not None and (not isinstance(meta["summary"], dict)
                                        or meta["summary"].get("draft_sha256") != meta["draft_sha256"]):
        problems.append("the summary is for another draft")
    if _has_key(meta):
        problems.append("meta.json matches a key pattern")
    for name, key in (("review.md", "review"), ("judge.md", "judge")):
        listed = meta[key]
        if (name in names) != (listed is not None):
            problems.append(f"{name} and meta.json disagree")
            continue
        if listed is None:
            continue
        raw = (d / name).read_bytes()
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            problems.append(f"{name} is not UTF-8")
            continue
        if CONTROL.search(text) or len(raw) > TEXT_MAX:
            problems.append(f"{name} has control characters or is too large")
        if not isinstance(listed, dict) or listed.get("sha256") != hashlib.sha256(raw).hexdigest():
            problems.append(f"{name} does not match its sha in meta.json")
    if set(names) - set(DRAFT_FILES):
        problems.append("draft/ holds other files")
    return problems


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
    jobs, excluded, withheld, total = {}, [], [], 0
    (tmp / "jobs").mkdir()
    source_fd = _open_dir(str(source))
    try:
        names = sorted(n for n in os.listdir(source_fd) if JOB_ID.match(n))
        for job_id in names:
            got = _one(source_fd, job_id, excluded, withheld)
            if got is None:
                continue
            job, runs, nano, files = got
            d = tmp / "jobs" / job_id
            (d / "runs").mkdir(parents=True)
            (d / "job.json").write_text(json.dumps(job, indent=1) + "\n", encoding="utf-8")   # stage order kept
            for run, events in runs.items():
                (d / "runs" / run).mkdir()
                (d / "runs" / run / "events.jsonl").write_text(_jsonl(events), encoding="utf-8")
            if files:
                (d / "draft").mkdir()
                for name, text in files.items():
                    (d / "draft" / name).write_text(text, encoding="utf-8")
            jobs[job_id], total = nano, total + nano
    finally:
        os.close(source_fd)
    return {"jobs": sorted(jobs), "cost_nano": total, "per_job": jobs, "excluded": excluded, "withheld": withheld}


def _one(source_fd, job_id, excluded, withheld):
    """(projected job, {run: projected events}, nano, {draft file: text}) of one job, or None: not a job (not a
    directory, a symlink, no job.json), or excluded (noted in `excluded`, never with a value). A draft file left out is
    noted in `withheld`; the job is published all the same."""
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
    try:
        files, why = draft_view(source_fd, job_id, json.loads(raw_job))
    except Exception as e:                            # noqa: BLE001  (the job is published without its draft)
        files, why = {}, [f"draft not published: {type(e).__name__}"]
    withheld.extend({"job": job_id, "why": w[:200]} for w in why)
    return job, runs, nano, files


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
            if not re.fullmatch(r"j[0-9a-z_]{1,40}/(job\.json|runs/j[0-9a-z_]{1,40}-[a-z][0-9]{1,3}/events\.jsonl"
                                r"|draft/(meta\.json|review\.md|judge\.md))", rel):
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
            try:
                problems += [f"{job_id}/draft: {p}" for p in draft_problems(root / job_id, job)]
            except Exception as e:                    # noqa: BLE001  (a malformed draft/ is a problem, not a crash)
                problems.append(f"{job_id}/draft: {type(e).__name__}")
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
