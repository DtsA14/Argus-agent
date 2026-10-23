"""argus: a code task as one job (router v0, docs/reviews/SPEC_ROUTER_V0.md).

  python scripts/argus.py code --repo ../target --commit HEAD --issue-file issue.txt [--max-usd 1.0] [--exclude docs]
  python scripts/argus.py list                            # every job: its id, state and money (read only)
  python scripts/argus.py status <job>
  python scripts/argus.py approve <job> --sha <first 12 of the draft sha, as status shows it> [--max-usd X]
  python scripts/argus.py reject <job> "why"
  python scripts/argus.py redraft <job>
  python scripts/argus.py resume <job>
  python scripts/argus.py abandon <job> "why"            # close a job that will not be continued

Every live stage shows its limits, asks [y/N], then asks for the API key (not shown; never an argument, never written).
Applying the review package's patch to the target repository stays with the human. Exit codes: 0 done, 1 the stage
ended without success, 2 refused.
"""
import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from approve_draft import sandbox_cfg  # noqa: E402  (scripts/ is on sys.path when this file runs)
from models.registry import ConfigError  # noqa: E402
from router import job as rj  # noqa: E402
from runner import load_config  # noqa: E402


def main(argv=None, deps=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--config")
    ap.add_argument("--jobs-dir", default=str(rj.JOBS))
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("code")
    c.add_argument("--repo", required=True)
    c.add_argument("--commit", required=True)
    g = c.add_mutually_exclusive_group(required=True)
    g.add_argument("--issue")
    g.add_argument("--issue-file")
    c.add_argument("--max-usd", type=float)
    c.add_argument("--exclude", action="append", default=[])
    sub.add_parser("list")
    for name in ("status", "redraft", "resume"):
        sub.add_parser(name).add_argument("job")
    a = sub.add_parser("approve")
    a.add_argument("job")
    a.add_argument("--sha", required=True)
    a.add_argument("--max-usd", type=float)
    a.add_argument("--max-iterations", type=int, default=3)
    a.add_argument("--reference-patch")
    for name in ("reject", "abandon"):
        r = sub.add_parser(name)
        r.add_argument("job")
        r.add_argument("reason")
    o = ap.parse_args(argv)
    deps = deps or rj.Deps()
    try:
        if o.cmd == "list":
            print(rj.list_jobs(jobs_dir=o.jobs_dir))
            return 0
        if o.cmd == "status":
            print(rj.status(o.job, jobs_dir=o.jobs_dir))
            return 0
        if o.cmd in ("reject", "abandon"):
            fn = rj.reject if o.cmd == "reject" else rj.abandon
            print(rj.status(fn(o.job, o.reason, deps=deps, jobs_dir=o.jobs_dir).id, jobs_dir=o.jobs_dir))
            return 0
        cfg = load_config(o.config)
        cfg["sandbox"] = sandbox_cfg(o.config)
        if o.cmd == "code":
            issue = o.issue if o.issue is not None else Path(o.issue_file).read_text(encoding="utf-8")
            job = rj.start_code(repo=o.repo, commit=o.commit, issue=issue, cfg=cfg, deps=deps, exclude=o.exclude,
                                max_usd=o.max_usd, jobs_dir=o.jobs_dir)
        elif o.cmd == "approve":
            job, _ = rj.approve(o.job, sha=o.sha, cfg=cfg, deps=deps, sandbox_cfg=cfg["sandbox"], max_usd=o.max_usd,
                                max_iterations=o.max_iterations, reference_patch=o.reference_patch, jobs_dir=o.jobs_dir)
        elif o.cmd == "redraft":
            job, _ = rj.redraft(o.job, cfg=cfg, deps=deps, jobs_dir=o.jobs_dir)
        else:
            job, _ = rj.resume(o.job, cfg=cfg, deps=deps, sandbox_cfg=cfg["sandbox"], jobs_dir=o.jobs_dir)
    except (rj.Refused, ConfigError, OSError) as e:
        print(f"refused: {e}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        job = getattr(o, "job", None)
        print("\ninterrupted. " + (f"Continue it with `argus resume {job}`; " if job else "")
              + "`argus status <job>` shows where it stopped. Do not start a new job for the same task.", file=sys.stderr)
        return 130
    print(rj.status(job.id, jobs_dir=o.jobs_dir))
    return 0 if job.data["state"] in (rj.AWAITING_APPROVAL, rj.REVIEW_READY) else 1


if __name__ == "__main__":
    sys.exit(main())
