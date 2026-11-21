"""For the tests of `argus apply`: since SPEC_KARTU_SETUJU 5 an apply needs an `ok` patch-read note for the patch on disk. `read_ok` writes it through the
real command. It writes nothing only when the test has made the job one that cannot take a note (not REVIEW_READY, no package, a patch changed after the
review recorded it): that test meets its own refusal first. Any other refusal of the command is a real failure and is raised."""
import hashlib
from pathlib import Path

from router import job as rj
from router import patch_read as pr


def read_ok(env, sha=None, verdict="ok"):
    job = env.job()
    if job.data["state"] != rj.REVIEW_READY:
        return
    sid, stage = rj.last_agent(job)
    review = (stage or {}).get("review") or {}
    try:
        disk = hashlib.sha256((Path(review["dir"]) / "changes.patch").read_bytes()).hexdigest()
    except (KeyError, OSError):
        return
    if review.get("patch_sha256") != disk or (sha is not None and not disk.startswith(sha[:12])):
        return
    pr.record(job.id, disk[:12], verdict, "test note", "claude", "reader-a", deps=env.deps, jobs_dir=env.jobs)
    if verdict == "ok":                                                       # rev 3 (SPEC_KARTU_SETUJU 13.5): an ok is two readings by two ids
        pr.record(job.id, disk[:12], verdict, "test note", "claude", "reader-b", deps=env.deps, jobs_dir=env.jobs, second=True)


def read_pair(env, first, second, ids=("reader-a", "reader-b"), reader="claude"):
    """Both readings of the patch on disk, as `patch-read-run` leaves them (read_ok writes a single `concerns`, or two `ok`)."""
    job = env.job()
    sid, stage = rj.last_agent(job)
    disk = hashlib.sha256((Path(stage["review"]["dir"]) / "changes.patch").read_bytes()).hexdigest()
    pr.record(job.id, disk[:12], first, "first reading", reader, ids[0], deps=env.deps, jobs_dir=env.jobs)
    if second is not None:
        pr.record(job.id, disk[:12], second, "second reading", reader, ids[1], deps=env.deps, jobs_dir=env.jobs, second=True)
    return disk


def read_argus_pair(env, first, second, sev1=None, sev2=None):
    """The two readings of Argus's own pair (the ids `patch-read-run` writes), with the severity each says for a `concerns`."""
    from router import patch_read_run as prr
    job = env.job()
    sid, stage = rj.last_agent(job)
    disk = hashlib.sha256((Path(stage["review"]["dir"]) / "changes.patch").read_bytes()).hexdigest()
    pr.record(job.id, disk[:12], first, "first reading", "argus", prr.reader_id(prr.FIRST), deps=env.deps, jobs_dir=env.jobs, severity=sev1)
    if second is not None:
        pr.record(job.id, disk[:12], second, "second reading", "argus", prr.reader_id(prr.SECOND), deps=env.deps, jobs_dir=env.jobs, second=True, severity=sev2)
    return disk
