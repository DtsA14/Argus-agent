"""Run a fixed series of single-task evals in a given order, one runs directory each, and stop at the first run that
ends BLOCKED or FAILED_BUDGET or that looks like a harness anomaly: run_eval exits nonzero (even with a report), writes
no report, or reports a task without a status. Nothing is retried.

  ARGUS_LIVE=1 python scripts/run_series.py --manifest evals/search_v1/manifest.json \
      --order c2,b3,a1 --task-prefix ledger_terms_ --out runs/search_live_1 --max-usd-per-run 0.50

Each entry is <variant><repeat>: "b3" runs task ledger_terms_b into <out>/<position>_b3. Every run goes through
scripts/run_eval.py with its own --max-total-usd, so the whole series can never spend more than
len(order) x max-usd-per-run. A runs directory that already exists is refused by run_eval, so nothing is reused.
In live mode run_eval exits 0 for every scored outcome, FAILED_ACCEPTANCE included, so nonzero is never a result."""
import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STOP = ("BLOCKED", "FAILED_BUDGET")


def run_eval(mode, manifest, task, runs, max_usd):
    """One eval run as a subprocess: (exit code, stdout, stderr)."""
    r = subprocess.run([sys.executable, "scripts/run_eval.py", "--mode", mode, "--manifest", manifest,
                        "--tasks", task, "--runs-dir", str(runs), "--max-total-usd", str(max_usd)],
                       cwd=ROOT, capture_output=True, text=True)
    return r.returncode, r.stdout, r.stderr


def run_series(order, *, manifest, task_prefix, out, max_usd, mode="live", run=run_eval):
    """Run the entries in order; returns the series record that is also written to <out>/series.json."""
    if len(set(order)) != len(order):
        raise ValueError("the order repeats an entry")
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    rows, stopped = [], None
    for pos, entry in enumerate(order, 1):
        task = task_prefix + entry[0]
        runs = out / f"{pos:02d}_{entry}"
        code, stdout, stderr = run(mode, manifest, task, runs, max_usd)
        print(stdout, end="")
        report = runs / "report.json"
        t = json.loads(report.read_text(encoding="utf-8"))["tasks"][0] if report.exists() else {}
        rows.append({"position": pos, "entry": entry, "task": task, "exit_code": code, "status": t.get("status"),
                     "eval_pass": t.get("eval_pass"), "usd": (t.get("stats") or {}).get("usd_billed")})
        if code != 0:
            stopped = {"entry": entry, "reason": f"run_eval exited {code}", "stderr": stderr[-2000:]}
        elif not report.exists():
            stopped = {"entry": entry, "reason": "no report"}
        elif t.get("not_run") or t.get("status") is None:
            stopped = {"entry": entry, "reason": "the task has no status"}
        elif t["status"] in STOP:
            stopped = {"entry": entry, "reason": t["status"]}
        if stopped:
            print(f"STOP at {entry}: {stopped['reason']}")
            break
    record = {"order": order, "runs": rows, "stopped": stopped,
              "usd_spent": round(sum(r["usd"] or 0 for r in rows), 6)}
    (out / "series.json").write_text(json.dumps(record, indent=1), encoding="utf-8")
    print(f"ran {len(rows)} of {len(order)}; spent ${record['usd_spent']:.4f}")
    return record


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", required=True)
    ap.add_argument("--order", required=True, help="comma-separated <variant><repeat>, e.g. c2,b3,a1")
    ap.add_argument("--task-prefix", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--max-usd-per-run", type=float, required=True)
    ap.add_argument("--mode", default="live")
    a = ap.parse_args()
    try:
        record = run_series(a.order.split(","), manifest=a.manifest, task_prefix=a.task_prefix, out=a.out,
                            max_usd=a.max_usd_per_run, mode=a.mode)
    except ValueError as e:
        sys.exit(f"refused: {e}")
    return 1 if record["stopped"] else 0


if __name__ == "__main__":
    sys.exit(main())
