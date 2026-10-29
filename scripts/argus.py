"""argus: a code task as one job (router v0, docs/reviews/SPEC_ROUTER_V0.md).

  python scripts/argus.py code --repo ../target --commit HEAD --issue-file issue.txt [--max-usd 1.0] [--exclude docs]
  python scripts/argus.py list                            # every job: its id, state and money (read only)
  python scripts/argus.py status <job>
  python scripts/argus.py approve <job> --sha <first 12 of the draft sha, as status shows it> [--max-usd X]
  python scripts/argus.py reject <job> "why"             # a draft, or a review package that will not be applied
  python scripts/argus.py applied <job> --commit <sha>   # the review package was applied in that commit of the repo
  python scripts/argus.py redraft <job>
  python scripts/argus.py resume <job>
  python scripts/argus.py retry <job> [--max-usd X]      # after AGENT_FAILED: the agent again, as a new stage
  python scripts/argus.py abandon <job> "why"            # close a job that will not be continued

Every live stage shows its limits, asks [y/N], then asks for the API key (not shown; never an argument, never written).
Without a terminal (docs/reviews/SPEC_ROUTER_KEY_FILE.md): --key-file PATH reads the key from a 0600 file of yours
outside every repository and jobs/, and --yes (only with --key-file) skips the [y/N] for a run the human approved in
chat; the limits are still printed. Both go after the command:
  python scripts/argus.py approve <job> --sha <sha> --key-file ~/.config/argus/deepseek_key --yes
Applying the review package's patch to the target repository stays with the human. Exit codes: 0 done, 1 the stage
ended without success, 2 refused.
"""
import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from approve_draft import sandbox_cfg  # noqa: E402  (scripts/ is on sys.path when this file runs)
from acceptance import intake  # noqa: E402
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
    c.add_argument("--environment", help="the sandbox environment of the job's validations (its image is pinned for "
                   "the whole job); without it, the drafter's configured one, nothing pinned")
    c.add_argument("--research", action="store_true", help="start with the research stage r1: read-only tools and ReadDocs "
                   "(granted by this confirmation; needs --environment in web.environments); docs/reviews/SPEC_RESEARCH_STAGE.md")
    sub.add_parser("list")
    sub.add_parser("status").add_argument("job")
    sub.add_parser("resume").add_argument("job")
    d = sub.add_parser("redraft")
    d.add_argument("job")
    d.add_argument("--note", help="a note for the drafter from the reviewer of the previous draft (at most 1000 "
                   "characters; the job is then marked human-steered)")
    a = sub.add_parser("approve")
    a.add_argument("job")
    a.add_argument("--sha", required=True)
    a.add_argument("--max-usd", type=float)
    a.add_argument("--max-iterations", type=int, default=3)
    a.add_argument("--reference-patch")
    a.add_argument("--web", action="store_true", help="grant the agent ReadDocs (documentation pages from the hosts in "
                   "config web.hosts); refused for an environment off web.environments")
    q = sub.add_parser("research-ok")
    q.add_argument("job")
    q.add_argument("--sha", required=True, help="the handoff sha status shows (at least 12 characters)")
    t = sub.add_parser("retry")
    t.add_argument("job")
    t.add_argument("--max-usd", type=float)
    p = sub.add_parser("applied")
    p.add_argument("job")
    p.add_argument("--commit", required=True, help="the commit of the target repository the patch was applied in")
    p.add_argument("--note")
    g = sub.add_parser("stage", help="staging v0 (docs/reviews/SPEC_STAGING_V0.md): deploy | rollback | status")
    gs = g.add_subparsers(dest="stage_cmd", required=True)
    gd = gs.add_parser("deploy")
    gd.add_argument("job")
    for p_ in (gd, gs.add_parser("rollback")):
        p_.add_argument("--yes", action="store_true", help="the deployment was approved in chat (\"go live\")")
    gs.add_parser("status")
    for name in ("reject", "abandon"):
        r = sub.add_parser(name)
        r.add_argument("job")
        r.add_argument("reason")
    for name, p in sub.choices.items():
        if name in ("code", "approve", "redraft", "resume", "retry", "research-ok"):   # the live commands
            p.add_argument("--key-file", help="read the API key from this 0600 file instead of typing it")
            p.add_argument("--yes", action="store_true", help="only with --key-file: the run was approved in chat")
    o = ap.parse_args(argv)
    deps = deps or rj.Deps()
    if o.cmd == "stage":
        from router import stage as sg
        try:
            if o.stage_cmd == "status":
                print(sg.status())
                return 0
            deps.assume_yes = o.yes                      # no key is involved: --yes alone is the approval in chat
            cfg = load_config(o.config)
            cfg["sandbox"] = sandbox_cfg(o.config)
            if o.stage_cmd == "deploy":
                sg.deploy(o.job, cfg=cfg, deps=deps, jobs_dir=o.jobs_dir)
            else:
                sg.rollback(cfg=cfg, deps=deps)
        except (rj.Refused, ConfigError, OSError, intake.IntakeError, subprocess.TimeoutExpired) as e:
            print(f"refused: {type(e).__name__ + ': ' if not isinstance(e, rj.Refused) else ''}{e}", file=sys.stderr)
            print(sg.status())
            return 2
        print(sg.status())
        return 0
    if getattr(o, "key_file", None) or getattr(o, "yes", False):
        deps.key_file, deps.assume_yes = o.key_file, o.yes
        deps.key_forbidden = (rj.ROOT, Path(o.jobs_dir)) + ((Path(o.repo),) if getattr(o, "repo", None) else ())
    try:
        if o.cmd == "list":
            print(rj.list_jobs(jobs_dir=o.jobs_dir))
            return 0
        if o.cmd == "status":
            try:
                cfg = load_config(o.config)
                cfg["sandbox"] = sandbox_cfg(o.config)
            except (ConfigError, OSError):
                cfg = None                    # status still reads the job; the image comparison is left out
            print(rj.status(o.job, jobs_dir=o.jobs_dir, cfg=cfg))
            return 0
        if o.cmd in ("reject", "abandon"):
            fn = rj.reject if o.cmd == "reject" else rj.abandon
            print(rj.status(fn(o.job, o.reason, deps=deps, jobs_dir=o.jobs_dir).id, jobs_dir=o.jobs_dir))
            return 0
        if o.cmd == "applied":
            print(rj.status(rj.applied(o.job, o.commit, deps=deps, jobs_dir=o.jobs_dir, note=o.note).id,
                            jobs_dir=o.jobs_dir))
            return 0
        cfg = load_config(o.config)
        cfg["sandbox"] = sandbox_cfg(o.config)
        if o.cmd == "code":
            issue = o.issue if o.issue is not None else Path(o.issue_file).read_text(encoding="utf-8")
            job = rj.start_code(repo=o.repo, commit=o.commit, issue=issue, cfg=cfg, deps=deps, exclude=o.exclude,
                                max_usd=o.max_usd, jobs_dir=o.jobs_dir, environment=o.environment, research=o.research)
        elif o.cmd == "research-ok":
            job, _ = rj.research_ok(o.job, sha=o.sha, cfg=cfg, deps=deps, jobs_dir=o.jobs_dir)
        elif o.cmd == "approve":
            job, _ = rj.approve(o.job, sha=o.sha, cfg=cfg, deps=deps, sandbox_cfg=cfg["sandbox"], max_usd=o.max_usd,
                                max_iterations=o.max_iterations, reference_patch=o.reference_patch, jobs_dir=o.jobs_dir,
                                web=o.web)
        elif o.cmd == "retry":
            job, _ = rj.retry(o.job, cfg=cfg, deps=deps, sandbox_cfg=cfg["sandbox"], max_usd=o.max_usd,
                              jobs_dir=o.jobs_dir)
        elif o.cmd == "redraft":
            job, _ = rj.redraft(o.job, cfg=cfg, deps=deps, jobs_dir=o.jobs_dir, note=o.note)
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
    print(rj.status(job.id, jobs_dir=o.jobs_dir, cfg=cfg))
    return 0 if job.data["state"] in (rj.AWAITING_APPROVAL, rj.REVIEW_READY, rj.AWAITING_RESEARCH_REVIEW) else 1


if __name__ == "__main__":
    sys.exit(main())
