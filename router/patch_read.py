"""The note of a patch reader (docs/reviews/SPEC_KARTU_SETUJU.md section 5, PR 3 of T3): before a patch is applied, someone says they read it. Today
that someone is a Claude session, and the note says so (`reader.kind: claude`): it is a statement, not a proof that the patch was read, and not a
human. `argus patch-read` writes `patch_read_<sid>.json` in the job directory, bound to (stage, patch sha256) like the examples audit; `argus apply`
refuses without an `ok` note for the very patch it applies, so the command line and the card (T3) cannot disagree.

Nothing here runs the patch, calls a model or writes to the log of the job (no new kind of `what`): the file is the whole record. Writing happens
under the job's lock, atomically (a temporary file, then a rename), and the text of the note is cleaned and cut."""
import hashlib
import json
import os
import re
import stat
from pathlib import Path

from codetask import examples as ex
from router import job as rj

VERDICTS = ("ok", "concerns")
READERS = ("claude",)
NOTE_MAX, ID_MAX, FILE_MAX = 500, 80, 16 * 1024
SID = re.compile(r"a[0-9]{1,3}")
SHA = re.compile(r"[0-9a-f]{64}")
AT = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(\.[0-9]+)?Z")
LABEL = "a statement of a Claude session, not a proof that the patch was read, and not a human"


def key(sid, patch_sha256):
    return hashlib.sha256(f"patch-read\n{sid}\n{patch_sha256}".encode("utf-8")).hexdigest()


def path(job_dir, sid):
    return Path(job_dir) / f"patch_read_{sid}.json"


def _refuse(job_id, why):
    raise rj.Refused(f"job {job_id}: {why}; nothing was written")


def record(job_id, sha, verdict, note, reader, reader_id=None, *, deps, jobs_dir=rj.JOBS):
    """Write the note for the patch of the job's last agent stage; Refused for anything that is not exactly that patch, with nothing written."""
    if verdict not in VERDICTS:
        _refuse(job_id, f"the verdict is one of {', '.join(VERDICTS)}")
    if reader not in READERS:
        _refuse(job_id, f"the reader is one of {', '.join(READERS)}")
    text = ex.clean(note, NOTE_MAX) if isinstance(note, str) else ""
    if not text:
        _refuse(job_id, "a note needs a text: what you read and what you found")
    rid = ex.clean(reader_id, ID_MAX) if isinstance(reader_id, str) and reader_id.strip() else None
    job = rj.open_job(job_id, jobs_dir)
    with job.lock():
        if job.data["state"] != rj.REVIEW_READY:
            _refuse(job_id, f"it is {job.data['state']}: only a job with a review package to apply takes a note")
        sid, stage = rj.last_agent(job)
        review = (stage or {}).get("review") or {}
        if not (isinstance(sid, str) and SID.fullmatch(sid) and review.get("dir")):
            _refuse(job_id, "there is no review package")
        review_dir = Path(review["dir"])
        try:
            patch = (review_dir / "changes.patch").read_bytes()
            prov = json.loads((review_dir / "provenance.json").read_text(encoding="utf-8"))
        except (OSError, ValueError) as e:
            _refuse(job_id, f"the review package cannot be read ({e})")
        full = hashlib.sha256(patch).hexdigest()
        if not (isinstance(sha, str) and len(sha) >= 12 and full.startswith(sha.lower())):
            _refuse(job_id, f"--sha is not the sha of the patch on disk ({full[:12]}...): read that patch and give its sha")
        if review.get("patch_sha256") != full or (prov.get("patch") or {}).get("sha256") != full:
            _refuse(job_id, "the patch on disk is not the one the review recorded (job.json and provenance.json must both name it)")
        rec = {"key": key(sid, full), "sid": sid, "patch_sha256": full, "verdict": verdict, "note": text,
               "reader": {"kind": reader, **({"id": rid} if rid else {})}, "at": deps.clock()}
        target = path(job.dir, sid)
        tmp = target.with_name(target.name + ".tmp")
        try:                                                  # a stale or planted name is removed, never followed
            os.unlink(tmp)
        except FileNotFoundError:
            pass
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o644)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(json.dumps(rec))
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, target)
    return rec


def load(job_dir, sid, patch_sha256):
    """('none', None) no note for this stage; ('stale', None) the note is for another patch; ('error', None) anything damaged;
    ('ok' | 'concerns', note). The file is read through a descriptor, never through a symlink, never past FILE_MAX."""
    if not (isinstance(sid, str) and SID.fullmatch(sid) and isinstance(patch_sha256, str) and SHA.fullmatch(patch_sha256)):
        return "error", None
    try:
        dfd = os.open(str(job_dir), os.O_RDONLY | os.O_DIRECTORY)
    except OSError:
        return "error", None
    try:
        fd = os.open(path(job_dir, sid).name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_NOCTTY, dir_fd=dfd)
    except FileNotFoundError:
        return "none", None
    except OSError:
        return "error", None
    finally:
        os.close(dfd)
    try:
        st = os.fstat(fd)
        if not stat.S_ISREG(st.st_mode) or st.st_size > FILE_MAX:
            return "error", None
        with os.fdopen(fd, "rb", closefd=False) as f:
            raw = f.read(FILE_MAX + 1)
    except OSError:
        return "error", None
    finally:
        os.close(fd)
    try:
        rec = json.loads(raw.decode("utf-8"))
        if not isinstance(rec, dict) or rec.get("sid") != sid:
            return "error", None
        if not isinstance(rec.get("patch_sha256"), str) or rec.get("key") != key(sid, rec["patch_sha256"]):
            return "error", None
        if (rec.get("verdict") not in VERDICTS or not isinstance(rec.get("note"), str) or not isinstance(rec.get("at"), str)
                or not isinstance(rec.get("reader"), dict) or rec["reader"].get("kind") not in READERS
                or not SHA.fullmatch(rec["patch_sha256"])):
            return "error", None
        rid = rec["reader"].get("id")
        if (not rec["note"] or ex.clean(rec["note"], NOTE_MAX) != rec["note"] or not AT.fullmatch(rec["at"])
                or (rid is not None and (not isinstance(rid, str) or ex.clean(rid, ID_MAX) != rid))):
            return "error", None                              # what is shown later is what `record` would have written: clean and short
    except (ValueError, UnicodeDecodeError, RecursionError, TypeError):
        return "error", None
    if rec["patch_sha256"] != patch_sha256:
        return "stale", None
    return rec["verdict"], rec


def require_ok(job, sid, sha, reader=None):
    """The note `argus apply` needs: Refused unless an `ok` note of this stage names exactly this patch. Returns the note."""
    kind, rec = load(job.dir, sid, sha)
    how = f"argus patch-read {job.id} --sha {sha[:12]} --verdict ok --note \"...\" --reader claude"
    if kind == "none":
        raise rj.Refused(f"job {job.id}: no patch-read note: someone reads the patch and writes the note first ({how})")
    if kind == "stale":
        raise rj.Refused(f"job {job.id}: the patch-read note is for another patch: read this one ({how})")
    if kind == "error":
        raise rj.Refused(f"job {job.id}: the patch-read note cannot be read: write it again ({how})")
    if kind == "concerns":
        raise rj.Refused(f"job {job.id}: the patch reader recorded concerns: {rec['note']}")
    if reader is not None and rec["reader"]["kind"] != reader:
        raise rj.Refused(f"job {job.id}: the patch-read note was written by {rec['reader']['kind']}, not by {reader} (--reader)")
    return rec
