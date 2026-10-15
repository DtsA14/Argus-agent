"""Run Eval Set v1 (docs/reviews/EVAL_SET_V1.md) and write a report.

  python scripts/run_eval.py --mode reference            # validate the benchmark: every reference must pass
  python scripts/run_eval.py --mode wrong                # validate the benchmark: no wrong script may pass
  ARGUS_LIVE=1 python scripts/run_eval.py --mode live --tasks fix_divide --max-total-usd 0.50

Validation always runs in the Docker sandbox (pinned image from ARGUS_SANDBOX_IMAGE or .sandbox_image). Live mode
spends money: it needs ARGUS_LIVE=1 and a total cap; a task starts only if its contract cap still fits under it.
Exit code 0 when the benchmark is valid (reference / wrong) or every task ran (live), 1 otherwise, 2 if refused.
"""
import argparse
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from evals.runner import MODES, run_eval  # noqa: E402
from runner import load_config  # noqa: E402


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--mode", choices=MODES, required=True)
    ap.add_argument("--manifest", default=str(ROOT / "evals" / "v1" / "manifest.json"))
    ap.add_argument("--tasks", help="comma-separated task ids (default: all)")
    ap.add_argument("--runs-dir", help="default: runs/eval_<mode>_<time>")
    ap.add_argument("--max-total-usd", type=float, help="live only, required: cap for the whole eval")
    ap.add_argument("--config")
    a = ap.parse_args(argv)

    if a.mode == "live":
        if os.environ.get("ARGUS_LIVE") != "1":
            print("refused: live mode spends money; set ARGUS_LIVE=1", file=sys.stderr)
            return 2
        if a.max_total_usd is None or not 0 < a.max_total_usd < float("inf"):
            print("refused: live mode needs a positive, finite --max-total-usd", file=sys.stderr)
            return 2
    if not os.environ.get("ARGUS_SANDBOX_IMAGE") and (ROOT / ".sandbox_image").exists():
        os.environ["ARGUS_SANDBOX_IMAGE"] = (ROOT / ".sandbox_image").read_text().strip()
    runs_dir = Path(a.runs_dir or ROOT / "runs" / time.strftime(f"eval_{a.mode}_%Y%m%d_%H%M%S"))
    if runs_dir.exists() and any(runs_dir.iterdir()):
        print(f"refused: {runs_dir} is not empty; results are never mixed", file=sys.stderr)
        return 2
    tasks = a.tasks.split(",") if a.tasks else None
    report = run_eval(a.manifest, a.mode, runs_dir, load_config(a.config), tasks=tasks,
                      max_total_usd=a.max_total_usd)
    runs_dir.mkdir(parents=True, exist_ok=True)
    (runs_dir / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding="utf-8")

    print(f"Eval {report['benchmark']} ({report['benchmark_sha256'][:12]}), mode {a.mode}, agent {report['agent']['commit'][:9]}"
          f"{' (dirty)' if report['agent']['dirty'] else ''}, model {report['agent']['model']}")
    for r in report["tasks"]:
        st = r.get("stats") or {}
        print(f"  {'PASS' if r['eval_pass'] else 'fail'}  {r['id']:<24} {r['category']:<14} {str(r['status']):<18} "
              f"expected {r['expected']:<18} ${st.get('usd_billed') or 0:.4f} calls {st.get('llm_calls')}"
              + (f"  benchmark {'ok' if r['benchmark_ok'] else 'BROKEN'}" if 'benchmark_ok' in r else "")
              + (f"  ({'; '.join(r['why'])})" if r["why"] else ""))
    t = report["summary"]["total"]
    print(f"eval pass {t['eval_pass']}/{t['tasks']}, acceptance {t['acceptance_pass']}/{t['positive']}, "
          f"${t['usd_total']} total")
    print(f"report: {runs_dir / 'report.json'}")
    if a.mode == "live":
        return 0 if not any(r.get("not_run") for r in report["tasks"]) else 1
    return 0 if report["benchmark_valid"] else 1


if __name__ == "__main__":
    sys.exit(main())
