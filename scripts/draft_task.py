"""Draft a task from an issue with a model (M6 W2b, docs/reviews/SPEC_W2B_DRAFTER.md). The drafter reads the intake
(read-only) and submits a W2a draft, checked at once (shape, scope, baseline red in the sandbox). It never approves:
a human reads runs/<id>/DRAFT_REVIEW.md and runs scripts/approve_draft.py.

  python scripts/draft_task.py --intake argus_p6 --issue-file issue.txt --max-usd 0.40 --run-id d1
  python scripts/draft_task.py --run-id d1 --resume
  python scripts/draft_task.py ... --crash-at drafter@after_llm                                   (crash tests)

A real model spends money, so a drafter model whose provider is not 'fake' needs ARGUS_LIVE=1. The run's cap is
min(budget.max_usd, --max-usd). Exit codes: 0 DRAFTED, 1 any other final status, 2 refused before starting,
42 a simulated crash.
"""
import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from approve_draft import sandbox_cfg  # noqa: E402  (scripts/ is on sys.path when this file runs)
from codetask.drafter import DRAFTED, run_drafter  # noqa: E402
from codetask.run import RunExists  # noqa: E402
from models.registry import ConfigError, ModelRef  # noqa: E402
from runner import load_config  # noqa: E402


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--run-id", required=True)
    ap.add_argument("--intake", help="the name of an intake in fixtures/repos (a new run)")
    ap.add_argument("--issue-file", help="the human's issue, at most 2000 characters (a new run)")
    ap.add_argument("--max-usd", type=float, help="the cap of this run (a new run)")
    ap.add_argument("--runs-dir", default=str(ROOT / "runs"))
    ap.add_argument("--config", help="config file (default: config.yaml)")
    ap.add_argument("--resume", action="store_true")
    ap.add_argument("--crash-at", help="simulate a hard crash once at this point (tests)")
    ap.add_argument("--quiet", action="store_true")
    a = ap.parse_args(argv)
    if not a.resume and not (a.intake and a.issue_file and a.max_usd):
        print("refused: a new run needs --intake, --issue-file and --max-usd", file=sys.stderr)
        return 2
    cfg = load_config(a.config)
    cfg["sandbox"] = sandbox_cfg(a.config)
    ref = ModelRef.parse(cfg["roles"][cfg["drafter"]["role"]]["model"])
    if ref.provider != "fake" and os.environ.get("ARGUS_LIVE") != "1":
        print(f"refused: the drafter model {ref} is real and spends money; set ARGUS_LIVE=1", file=sys.stderr)
        return 2
    try:
        issue = None if a.resume else Path(a.issue_file).read_text(encoding="utf-8").strip()
        r = run_drafter(run_id=a.run_id, runs_dir=a.runs_dir, cfg=cfg, intake_name=a.intake, issue=issue,
                        max_usd=a.max_usd, resume=a.resume, crash_at=a.crash_at, echo=not a.quiet)
    except (RunExists, ConfigError, OSError, ValueError) as e:
        print(f"refused: {e}", file=sys.stderr)
        return 2
    print(json.dumps({k: r[k] for k in ("status", "stop_reason", "blocked_reason", "drafting", "usd_billed",
                                        "llm_calls")}, ensure_ascii=False))
    return 0 if r["status"] == DRAFTED else 1


if __name__ == "__main__":
    sys.exit(main())
