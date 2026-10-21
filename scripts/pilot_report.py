"""Report over code-task runs (M6 pilot 3): per run and in total, how many are DONE, what they cost, how many attempts they
took, and how long a human supervised them. One JSON object on stdout.

  python scripts/pilot_report.py RUN_DIR [RUN_DIR ...] [--supervision FILE.json]

The runs are read through evals.runlog (the files a run leaves behind). FILE.json maps a run id (the directory's name) to the
minutes of supervision (a number, 0 or more); a run it does not name has none (null, never 0).

Definitions (nothing is guessed from what the files do not hold):
  status          result.json's status, or NO_RESULT when the run has no result.json (it was never finished);
                  a NO_RESULT run is neither a success nor a failure
  done            status is DONE (the pilot's own verdict, agent-completed or not, is a human decision and not computed here)
  cost known      evals.score.cost_is_known on result.json (usd_billed present and usd_complete true); NO_RESULT: never
  cost_per_success  the cost of every run whose cost is known (failed runs included) divided by the number of DONE runs among
                  them; null when there is none. When some cost is unknown, cost_complete is false and the cost figures
                  cover only the runs whose cost is known (usd_unknown_runs says how many are left out)
Exit codes: 0 report printed, 2 refused (an argument is not a run directory, or the supervision file is not valid)."""
import argparse
import json
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from evals import runlog  # noqa: E402
from evals.score import cost_is_known  # noqa: E402


class Refused(Exception):
    pass


def load_supervision(path):
    if path is None:
        return {}
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        raise Refused(f"the supervision file {path} cannot be read: {e}")
    bad = isinstance(data, dict) and [k for k, v in data.items()
                                      if isinstance(v, bool) or not isinstance(v, (int, float)) or v < 0]
    if not isinstance(data, dict) or bad:
        raise Refused(f"the supervision file {path} must map run ids to minutes (a number, 0 or more)"
                      + (f"; not valid for {sorted(bad)}" if bad else ""))
    return data


def run_row(run_dir, supervision):
    run_dir = Path(run_dir)
    if not (run_dir / "events.jsonl").is_file():
        raise Refused(f"{run_dir} is not a run directory (no events.jsonl)")
    result = runlog.read_result(run_dir)
    events, skipped = runlog.read_events(run_dir)
    status = result["status"] if result else "NO_RESULT"
    return {"run_id": run_dir.name, "status": status, "done": status == "DONE",
            "attempts": result.get("attempts") if result else None,
            "llm_calls": result.get("llm_calls") if result else None,
            "usd_billed": result.get("usd_billed") if result else None,
            "cost_known": bool(result) and cost_is_known(result),
            "events_skipped": result["events_skipped"] if result and "events_skipped" in result else skipped,
            "supervision_minutes": supervision.get(run_dir.name)}


def summarize(rows):
    done = [r for r in rows if r["done"]]
    finished = [r for r in rows if r["status"] != "NO_RESULT"]
    known = [r for r in rows if r["cost_known"]]
    known_done = [r for r in known if r["done"]]
    total = sum(r["usd_billed"] for r in known)
    watched = [r["supervision_minutes"] for r in rows if r["supervision_minutes"] is not None]
    attempts = [r["attempts"] for r in done if r["attempts"] is not None]
    dist = {}
    for r in finished:
        if r["attempts"] is not None:
            dist[r["attempts"]] = dist.get(r["attempts"], 0) + 1
    return {
        "runs": len(rows), "done": len(done), "no_result": len(rows) - len(finished),
        "success_rate": round(len(done) / len(finished), 6) if finished else None,
        "usd_known_total": round(total, 6), "usd_unknown_runs": len(rows) - len(known),
        "cost_per_success": round(total / len(known_done), 6) if known_done else None,
        "cost_complete": len(known) == len(rows),
        "attempts": {"mean": round(statistics.mean(attempts), 6) if attempts else None,
                     "median": statistics.median(attempts) if attempts else None,
                     "distribution": {str(k): dist[k] for k in sorted(dist)}},
        "supervision_minutes": {"runs_with_data": len(watched), "total": round(sum(watched), 6) if watched else None,
                                "mean": round(statistics.mean(watched), 6) if watched else None},
        "events_skipped": sum(r["events_skipped"] for r in rows)}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("runs", nargs="+", metavar="RUN_DIR")
    ap.add_argument("--supervision", metavar="FILE.json")
    a = ap.parse_args(argv)
    try:
        supervision = load_supervision(a.supervision)
        rows = [run_row(r, supervision) for r in a.runs]
    except Refused as e:
        print(f"refused: {e}", file=sys.stderr)
        return 2
    print(json.dumps({"runs": rows, "summary": summarize(rows)}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
