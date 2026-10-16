"""Run a fixed series of single-task evals in a given order, one runs directory each, and stop at the first run that
ends BLOCKED or FAILED_BUDGET or that looks like a harness anomaly: run_eval exits nonzero (even with a report), writes
no report, or reports a task without a status. Nothing is retried.

  ARGUS_LIVE=1 python scripts/run_series.py --manifest evals/search_v1/manifest.json \
      --order c2,b3,a1 --task-prefix ledger_terms_ --out runs/search_live_1 --max-usd-per-run 0.50

Each entry is <variant><repeat>: "b3" runs task ledger_terms_b into <out>/<position>_b3. Every run goes through
scripts/run_eval.py with its own --max-total-usd, so a run can never spend more than max-usd-per-run. A runs directory
that already exists is refused by run_eval, so nothing is reused. In live mode run_eval exits 0 for every scored
outcome, FAILED_ACCEPTANCE included, so nonzero is never a result.

Arms (docs/reviews/DESIGN_BUDGET_45K.md): an entry may name an arm, "b3@45", run with that arm's config
(--arm-config 45=evals/budget_v1/config_45k.yaml). Either every entry names a mapped arm or none does.
--pairs makes consecutive entries pairs of the same cell in different arms (checked before anything runs).
--max-usd-series is an emergency cap enforced before starting work: a pair starts only if the series' spend plus
2 x max-usd-per-run fits under it, a single run only if spend plus max-usd-per-run does. The spend is the sum of each
finished run's ledger cost (report stats.usd_billed = result.json usd_billed = reconcile_ledger: actual cost of every
call, calls cut off by a crash at their worst case); a run whose cost is missing or incomplete stops the series rather
than counting as zero. So the cap never cuts a pair in half and is never exceeded. series.json records every pair as
complete, incomplete or not run."""
import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STOP = ("BLOCKED", "FAILED_BUDGET")


def run_eval(mode, manifest, task, runs, max_usd, config=None):
    """One eval run as a subprocess: (exit code, stdout, stderr)."""
    r = subprocess.run([sys.executable, "scripts/run_eval.py", "--mode", mode, "--manifest", manifest,
                        "--tasks", task, "--runs-dir", str(runs), "--max-total-usd", str(max_usd)]
                       + (["--config", str(config)] if config else []),
                       cwd=ROOT, capture_output=True, text=True)
    return r.returncode, r.stdout, r.stderr


def parse(entry):
    """'b3@45' -> ('b3', '45'); 'b3' -> ('b3', None)."""
    cell, _, arm = entry.partition("@")
    return cell, arm or None


def check(order, arm_configs, pairs):
    if len(set(order)) != len(order):
        raise ValueError("the order repeats an entry")
    arms = [parse(e)[1] for e in order]
    if any(arms) and not all(arms):
        raise ValueError("either every entry names an arm or none does")
    unknown = sorted({a for a in arms if a and a not in arm_configs})
    if unknown:
        raise ValueError(f"no --arm-config for arm(s) {unknown}")
    if pairs:
        if len(order) % 2:
            raise ValueError("--pairs needs an even number of entries")
        for first, second in zip(order[::2], order[1::2]):
            (c1, a1), (c2, a2) = parse(first), parse(second)
            if c1 != c2 or a1 == a2 or not a1:
                raise ValueError(f"{first},{second} is not a pair of one cell in two arms")


def run_series(order, *, manifest, task_prefix, out, max_usd, mode="live", run=run_eval, arm_configs=None,
               pairs=False, max_usd_series=None):
    """Run the entries in order; returns the series record that is also written to <out>/series.json."""
    arm_configs = arm_configs or {}
    check(order, arm_configs, pairs)
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    rows, stopped = [], None
    spent = lambda: sum(r["usd"] or 0 for r in rows)  # noqa: E731  the runs' ledgers, as their reports give them
    for pos, entry in enumerate(order, 1):
        first_of_pair = not pairs or pos % 2 == 1
        need = max_usd * (2 if pairs else 1)
        if max_usd_series is not None and first_of_pair and spent() + need > max_usd_series + 1e-9:
            stopped = {"entry": entry, "reason": f"series cap: spent ${spent():.4f} + ${need:.2f} for the next "
                                                 f"{'pair' if pairs else 'run'} > ${max_usd_series:.2f}"}
            print(f"STOP before {entry}: {stopped['reason']}")
            break
        cell, arm = parse(entry)
        task = task_prefix + cell[0]
        runs = out / f"{pos:02d}_{entry.replace('@', '_')}"
        code, stdout, stderr = run(mode, manifest, task, runs, max_usd, arm_configs.get(arm))
        print(stdout, end="")
        report = runs / "report.json"
        t = json.loads(report.read_text(encoding="utf-8"))["tasks"][0] if report.exists() else {}
        st = t.get("stats") or {}
        rows.append({"position": pos, "entry": entry, "arm": arm, "task": task, "exit_code": code,
                     "status": t.get("status"), "eval_pass": t.get("eval_pass"), "usd": st.get("usd_billed"),
                     "usd_complete": st.get("usd_complete")})
        if code != 0:
            stopped = {"entry": entry, "reason": f"run_eval exited {code}", "stderr": stderr[-2000:]}
        elif not report.exists():
            stopped = {"entry": entry, "reason": "no report"}
        elif t.get("not_run") or t.get("status") is None:
            stopped = {"entry": entry, "reason": "the task has no status"}
        elif t["status"] in STOP:
            stopped = {"entry": entry, "reason": t["status"]}
        elif st.get("usd_billed") is None or st.get("usd_complete") is not True:
            # the series cap adds up the runs' ledger costs; a cost it cannot know is never counted as zero
            stopped = {"entry": entry, "reason": "the run's cost is unknown (no complete ledger cost in its report)"}
        if stopped:
            print(f"STOP at {entry}: {stopped['reason']}")
            break
    record = {"order": order, "runs": rows, "stopped": stopped, "usd_spent": round(spent(), 6)}
    if pairs:   # a run that stopped the series (BLOCKED, FAILED_BUDGET, an anomaly) ran, but is no comparable result
        ran = {r["entry"] for r in rows}
        valid = ran - ({stopped["entry"]} if stopped else set())
        record["pairs"] = [{"entries": [a, b], "state": "complete" if {a, b} <= valid else
                            "incomplete" if {a, b} & ran else "not run"} for a, b in zip(order[::2], order[1::2])]
    (out / "series.json").write_text(json.dumps(record, indent=1), encoding="utf-8")
    print(f"ran {len(rows)} of {len(order)}; spent ${record['usd_spent']:.4f}")
    return record


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", required=True)
    ap.add_argument("--order", required=True, help="comma-separated <variant><repeat>[@<arm>], e.g. c2,b3,a1")
    ap.add_argument("--task-prefix", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--max-usd-per-run", type=float, required=True)
    ap.add_argument("--mode", default="live")
    ap.add_argument("--arm-config", action="append", default=[], help="<arm>=<config path>, e.g. 45=evals/...yaml")
    ap.add_argument("--pairs", action="store_true")
    ap.add_argument("--max-usd-series", type=float)
    a = ap.parse_args()
    try:
        arm_configs = dict(spec.split("=", 1) for spec in a.arm_config)
        record = run_series(a.order.split(","), manifest=a.manifest, task_prefix=a.task_prefix, out=a.out,
                            max_usd=a.max_usd_per_run, mode=a.mode, arm_configs=arm_configs, pairs=a.pairs,
                            max_usd_series=a.max_usd_series)
    except ValueError as e:
        sys.exit(f"refused: {e}")
    return 1 if record["stopped"] else 0


if __name__ == "__main__":
    sys.exit(main())
