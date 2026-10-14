import argparse
import sys
import time

from models.registry import ConfigError, apply_overrides, parse_overrides
from runner import RunExists, load_config, run_task


def main():
    ap = argparse.ArgumentParser(description="Agentic harness, milestone 1 (fake workers)")
    ap.add_argument("--goal", default="Analyze penjualan.csv: top 3 products, monthly trend, 2 recommendations -> laporan.md")
    ap.add_argument("--scenario", choices=["pass", "fail_then_pass", "never_pass", "flaky"], default="fail_then_pass")
    ap.add_argument("--run-id", default=time.strftime("r_%Y%m%d_%H%M%S"))
    ap.add_argument("--runs-dir", default="runs")
    ap.add_argument("--max-iter", type=int)
    ap.add_argument("--max-tokens", type=int)
    ap.add_argument("--crash-at", help="simulate a process crash (once) before this node starts")
    ap.add_argument("--resume", action="store_true", help="continue a run from its last checkpoint")
    ap.add_argument("--model", action="append", metavar="ROLE=PROVIDER:MODEL",
                    help="swap the model for a role this run, e.g. worker=deepseek:deepseek-flash")
    ap.add_argument("--quiet", action="store_true")
    a = ap.parse_args()

    try:
        cfg = apply_overrides(load_config(), parse_overrides(a.model))
    except ConfigError as e:
        sys.exit(f"config error: {e}")
    if a.max_iter:
        cfg["budget"]["max_iterations"] = a.max_iter
    if a.max_tokens:
        cfg["budget"]["max_tokens"] = a.max_tokens

    try:
        result = run_task(
            goal=a.goal, scenario=a.scenario, run_id=a.run_id, runs_dir=a.runs_dir,
            cfg=cfg, crash_at=a.crash_at, resume=a.resume, echo=not a.quiet,
        )
    except RunExists as e:
        sys.exit(f"error: {e}")
    print(f"\n=> {result['status']} | iterations={result['iteration']} | tokens={result['tokens_used']} "
          f"(spent {result['tokens_spent']}) | log: {a.runs_dir}/{a.run_id}/events.jsonl")
    sys.exit(0 if result["status"] == "DONE" else 2)


if __name__ == "__main__":
    main()
