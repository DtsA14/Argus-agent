"""One JSON report over several code-task run directories.

  PYTHONPATH=. python scripts/pilot_report.py RUN_DIR... [--supervision FILE]

FILE is a JSON object {run_id: minutes}. Runs are read only through evals/runlog.py. Exit 2 (one line on stderr, nothing on
stdout) when no run is given, an argument is not a run directory, or the supervision file is unreadable or invalid.
"""
import json
import math
import os
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from evals.runlog import read_events, read_result  # noqa: E402
from evals.score import cost_is_known  # noqa: E402


class Refused(Exception):
    pass


def parse_args(argv):
    dirs, sup, i = [], None, 0
    while i < len(argv):
        a = argv[i]
        if a == "--supervision":
            if i + 1 >= len(argv):
                raise Refused("supervision file: no path given after --supervision")
            sup = argv[i + 1]
            i += 2
            continue
        if a.startswith("--supervision="):
            sup = a.split("=", 1)[1]
        else:
            dirs.append(a)
        i += 1
    return dirs, sup


def load_supervision(path, run_ids):
    def bad(why):
        return Refused(f"supervision file {path}: {why}")
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        raise bad(f"unreadable ({type(e).__name__})")
    if not isinstance(data, dict):
        raise bad("not a JSON object")
    for key, v in data.items():
        if key not in run_ids:
            raise bad(f"{key!r} is not a given run")
        if isinstance(v, bool) or not isinstance(v, (int, float)):
            raise bad(f"{key!r}: minutes is not a number")
        try:
            ok = math.isfinite(v) and v >= 0
        except OverflowError:
            ok = False
        if not ok:
            raise bad(f"{key!r}: minutes must be finite and >= 0")
    return data


def build(argv):
    dirs, sup_path = parse_args(argv)
    if not dirs:
        raise Refused("no run directory given")
    for d in dirs:
        p = Path(d)
        if not p.is_dir() or not (p / "events.jsonl").is_file():
            raise Refused(f"{d}: not a run directory")
    ids = [os.path.basename(os.path.abspath(d)) for d in dirs]
    minutes = load_supervision(sup_path, set(ids)) if sup_path is not None else {}

    rows, known = [], []
    for d, run_id in zip(dirs, ids):
        try:
            _, skipped = read_events(d)
            result = read_result(d)
        except (OSError, ValueError) as e:
            raise Refused(f"{d}: not a run directory (unreadable: {type(e).__name__})")
        if result is None:
            status, ck = "NO_RESULT", False
            attempts = calls = usd = None
        else:
            status, ck = result.get("status"), cost_is_known(result)
            attempts, calls, usd = result.get("attempts"), result.get("llm_calls"), result.get("usd_billed")
        rows.append({"run_id": run_id, "status": status, "done": status == "DONE", "attempts": attempts,
                     "llm_calls": calls, "usd_billed": usd, "cost_known": ck, "events_skipped": skipped,
                     "supervision_minutes": minutes.get(run_id)})
        known.append(ck)

    total = len(rows)
    no_result = sum(r["status"] == "NO_RESULT" for r in rows)
    done = [r for r in rows if r["done"]]
    with_result = total - no_result
    nano = sum(round(r["usd_billed"] * 1e9) for r in rows if r["cost_known"])
    done_known = sum(r["done"] for r in rows if r["cost_known"])
    unknown = sum(not r["cost_known"] for r in rows)
    att = [r["attempts"] for r in done]
    dist = {}
    for r in rows:
        if r["status"] != "NO_RESULT":
            dist[r["attempts"]] = dist.get(r["attempts"], 0) + 1
    mins = [r["supervision_minutes"] for r in rows if r["supervision_minutes"] is not None]
    return {
        "runs": rows,
        "runs_total": total,
        "done": len(done),
        "no_result": no_result,
        "success_rate": round(len(done) / with_result, 4) if with_result else None,
        "usd_known_total": round(nano / 1e9, 6),
        "usd_unknown_runs": unknown,
        "cost_per_success": round(nano / 1e9 / done_known, 6) if done_known else None,
        "cost_complete": unknown == 0,
        "attempts": {"mean": round(statistics.mean(att), 3), "median": statistics.median(att)} if att else None,
        "attempts_distribution": {str(k): dist[k] for k in sorted(dist, key=lambda k: (k is None, k or 0))},
        "supervision": {"runs_with_data": len(mins), "total": sum(mins) if mins else None,
                        "mean": round(statistics.mean(mins), 2) if mins else None},
        "events_skipped": sum(r["events_skipped"] for r in rows),
    }


def main(argv):
    try:
        report = build(argv)
    except Refused as e:
        print(" ".join(str(e).splitlines()), file=sys.stderr)
        return 2
    sys.stdout.write(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
