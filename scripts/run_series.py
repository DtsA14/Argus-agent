"""Run a fixed series of single-task evals in a given order, one runs directory each, and stop at the first run that
ends BLOCKED or FAILED_BUDGET or that the eval itself cannot score (a harness anomaly). Nothing is retried.

  ARGUS_LIVE=1 python scripts/run_series.py --manifest evals/search_v1/manifest.json \
      --order c2,b3,a1 --task-prefix ledger_terms_ --out runs/search_live_1 --max-usd-per-run 0.50

Each entry is <variant><repeat>: "b3" runs task ledger_terms_b into <out>/<position>_b3. Every run goes through
scripts/run_eval.py with its own --max-total-usd, so the whole series can never spend more than
len(order) x max-usd-per-run. A runs directory that already exists is refused by run_eval, so nothing is reused."""
import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STOP = ("BLOCKED", "FAILED_BUDGET")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", required=True)
    ap.add_argument("--order", required=True, help="comma-separated <variant><repeat>, e.g. c2,b3,a1")
    ap.add_argument("--task-prefix", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--max-usd-per-run", type=float, required=True)
    ap.add_argument("--mode", default="live")
    a = ap.parse_args()
    order = a.order.split(",")
    if len(set(order)) != len(order):
        sys.exit("refused: the order repeats an entry")
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    rows = []
    for pos, entry in enumerate(order, 1):
        task = a.task_prefix + entry[0]
        runs = out / f"{pos:02d}_{entry}"
        r = subprocess.run([sys.executable, "scripts/run_eval.py", "--mode", a.mode, "--manifest", a.manifest,
                            "--tasks", task, "--runs-dir", str(runs), "--max-total-usd", str(a.max_usd_per_run)],
                           cwd=ROOT, capture_output=True, text=True)
        print(r.stdout, end="")
        report = runs / "report.json"
        if not report.exists():
            print(f"STOP at {entry}: no report (exit {r.returncode})\n{r.stderr[-2000:]}")
            break
        t = json.loads(report.read_text(encoding="utf-8"))["tasks"][0]
        rows.append({"position": pos, "entry": entry, "task": task, "status": t.get("status"),
                     "eval_pass": t.get("eval_pass"), "usd": (t.get("stats") or {}).get("usd_billed")})
        if t.get("status") in STOP or t.get("status") is None or t.get("not_run"):
            print(f"STOP at {entry}: {t.get('status')}")
            break
    (out / "series.json").write_text(json.dumps({"order": order, "runs": rows}, indent=1), encoding="utf-8")
    spent = sum(r["usd"] or 0 for r in rows)
    print(f"ran {len(rows)} of {len(order)}; spent ${spent:.4f}")


if __name__ == "__main__":
    main()
