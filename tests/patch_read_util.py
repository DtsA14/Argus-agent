"""For the tests of `argus apply`: since SPEC_KARTU_SETUJU 5 an apply needs an `ok` patch-read note for the patch on disk. `read_ok` writes it through the
real command; when the command refuses (a test that changed the patch, or a job that is not REVIEW_READY) it writes nothing, and the apply under test
meets its own refusal first."""
import hashlib
from pathlib import Path

from router import job as rj
from router import patch_read as pr


def read_ok(env, sha=None, verdict="ok"):
    try:
        job = env.job()
        d = Path(job.data["stages"]["a1"]["review"]["dir"])
        sha = sha or hashlib.sha256((d / "changes.patch").read_bytes()).hexdigest()
        pr.record(job.id, sha[:12], verdict, "test note", "claude", deps=env.deps, jobs_dir=env.jobs)
    except (rj.Refused, OSError, KeyError, ValueError):
        pass
