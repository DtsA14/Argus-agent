"""Scoreboard of Argus jobs, computed from `jobs/*/job.json` and the run ledgers (docs/reviews/FABLE_SCOREBOARD_DEFINITION.md).

Read only: it opens nothing for writing except the output file you name. One row per code job: its outcome, money (from the
run ledgers, the money record; `stages[*].usd` is only a cross-check), decisions, human wait (an upper bound) and judge verdict.
Issue jobs add their money to the code job they handed off to; research jobs are a separate money total.

    python scripts/scoreboard.py [--jobs DIR] [--out verification/scoreboard-<date>.json]
"""
import argparse
import json
import statistics
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from router.job import JOBS, runs_spent_nano  # noqa: E402

FAILED = {"DRAFT_FAILED", "AGENT_FAILED", "BLOCKED", "REVIEW_INVALID", "RESEARCH_FAILED", "RESEARCH_INCONCLUSIVE"}
DECISION_WHATS = {"retry", "redraft", "research_ok"}
MOVES = {"REJECTED", "ABANDONED", "APPLIED"}


def _time(text):
    try:
        return datetime.strptime(text, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return None


def _gap(later, earlier):
    a, b = _time(later), _time(earlier)
    return None if a is None or b is None or a < b else (a - b).total_seconds()


def outcome(data):
    """(category, detail) of a code job."""
    state = data.get("state")
    if state == "APPLIED":
        as_is = next((e.get("as_is") for e in reversed(data.get("log") or [])
                      if e.get("what") == "state" and e.get("new") == "APPLIED"), None)
        return ("applied_untouched" if as_is is True else "applied_changed" if as_is is False
                else "applied_not_compared"), None
    if state in ("REJECTED", "ABANDONED"):
        old = next((e.get("old") for e in reversed(data.get("log") or [])
                    if e.get("what") == "state" and e.get("new") == state), None)
        return state.lower(), old
    return ("failed" if state in FAILED else "open"), state


def decisions(data):
    log = data.get("log") or []
    n = sum(1 for e in log if e.get("what") in DECISION_WHATS or e.get("what") == "approved")
    return n + sum(1 for e in log if e.get("what") == "state" and e.get("new") in MOVES)


def human_wait(data):
    """{draft, review} in seconds, upper bounds (they include idle time); None where the fields are missing."""
    stages = data.get("stages") or {}
    approval = data.get("approval") or {}
    draft = None
    for stage in stages.values():
        if stage.get("kind") == "draft" and stage.get("draft_sha256") == approval.get("draft_sha256"):
            draft = _gap(approval.get("at"), stage.get("ended_at"))
    agents = [s for s in stages.values() if s.get("kind") == "agent" and s.get("ended_at")]
    end = next((e.get("at") for e in reversed(data.get("log") or [])
                if e.get("what") == "state" and e.get("new") in ("APPLIED", "REJECTED")), None)
    review = _gap(end, agents[-1]["ended_at"]) if agents and end else None
    return {"draft": draft, "review": review}


def judge(data):
    judges = [s for s in (data.get("stages") or {}).values() if s.get("kind") == "judge"]
    if not judges:
        return "no judge"
    last = judges[-1]
    return last.get("verdict") or ("cut off" if last.get("status") in (None, "") else str(last.get("status")))


def load(jobs_dir):
    jobs = []
    for path in sorted(Path(jobs_dir).glob("*/job.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if isinstance(data, dict) and isinstance(data.get("job"), str):
            jobs.append((path.parent, data))
    return jobs


def build(jobs_dir):
    jobs = load(jobs_dir)
    nano = {}
    for directory, data in jobs:
        nano[data["job"]] = runs_spent_nano(directory / "runs", data.get("stages"))
    issue_money, orphan_issue = Counter(), 0
    for _, data in jobs:
        if data.get("kind") == "issue":
            target = (data.get("handoff") or {}).get("job")
            if target in nano and any(d["job"] == target and d.get("kind") == "code" for _, d in jobs):
                issue_money[target] += nano[data["job"]]
            else:
                orphan_issue += nano[data["job"]]
    rows = []
    for directory, data in jobs:
        if data.get("kind") != "code":
            continue
        job = data["job"]
        category, detail = outcome(data)
        stage_usd = sum((s.get("usd") or 0) for s in (data.get("stages") or {}).values())
        rows.append({
            "job": job, "repo": (data.get("inputs") or {}).get("repo_name")
            or Path((data.get("inputs") or {}).get("repo") or "?").name,
            "created_at": data.get("created_at"), "state": data.get("state"), "outcome": category, "detail": detail,
            "usd_nano": nano[job], "issue_usd_nano": issue_money[job],
            "stage_usd_sum": round(stage_usd, 9), "decisions": decisions(data), "wait_s": human_wait(data),
            "judge": judge(data), "human_steered": bool(data.get("human_steered")),
        })
    research = sum(nano[d["job"]] for _, d in jobs if d.get("kind") == "research")
    kinds = Counter(d.get("kind") for _, d in jobs)
    counts = Counter(r["outcome"] for r in rows)
    applied = counts["applied_untouched"] + counts["applied_changed"] + counts["applied_not_compared"]
    code_total = sum(r["usd_nano"] + r["issue_usd_nano"] for r in rows)
    waits = [r["wait_s"][k] for r in rows for k in ("draft", "review") if r["wait_s"][k] is not None]
    judged = Counter(r["judge"] for r in rows)
    return {
        "jobs_dir": str(jobs_dir), "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "jobs_by_kind": dict(kinds), "code_jobs": len(rows), "outcomes": dict(counts),
        "applied": applied, "applied_share_of_code_jobs": round(applied / len(rows), 4) if rows else None,
        "applied_untouched_share": round(counts["applied_untouched"] / applied, 4) if applied else None,
        "usd_code_jobs": code_total / 1e9, "usd_research_jobs": research / 1e9, "usd_issue_jobs_unattached": orphan_issue / 1e9,
        "usd_per_applied_change": round(code_total / 1e9 / applied, 4) if applied else None,
        "decisions_per_code_job": round(sum(r["decisions"] for r in rows) / len(rows), 3) if rows else None,
        "human_wait_s_upper_bound": {"n": len(waits), "median": statistics.median(waits) if waits else None,
                                     "total": sum(waits) if waits else 0},
        "judge": dict(judged), "judge_coverage": round(1 - judged["no judge"] / len(rows), 4) if rows else None,
        "by_repo": {r: dict(Counter(x["outcome"] for x in rows if x["repo"] == r)) for r in sorted({x["repo"] for x in rows})},
        "ledger_vs_stage_usd": {"ledger": sum(r["usd_nano"] for r in rows) / 1e9, "job_json": sum(r["stage_usd_sum"] for r in rows)},
        "caveat": "applied_untouched means the applied commit equals the reviewed patch (as_is); it is not a success rate "
                  "and not 'mergeable untouched' (that needs grading by someone outside the loop). The denominator of "
                  "applied_share_of_code_jobs counts every code job, including open ones.",
        "rows": rows,
        "not_known": ["re-issues of one issue (jobs per applied change are by repo only)", "who decided (by is $USER)",
                      "minutes of attention (waits include idle time)", "Claude's token cost (outside the harness)",
                      "spend of stages cut off before their ledger was written (the ledger figure is used where it exists)"],
    }


def text(report):
    o = report["outcomes"]
    lines = [f"jobs by kind: {report['jobs_by_kind']}", f"code jobs: {report['code_jobs']}",
             "outcomes: " + ", ".join(f"{k} {v}" for k, v in sorted(o.items())),
             f"applied: {report['applied']} = {report['applied_share_of_code_jobs']} of code jobs; of those, as reviewed (as_is) "
             f"{report['applied_untouched_share']}",
             f"ledger vs job.json stage usd: {report['ledger_vs_stage_usd']}",
             "caveat: " + report["caveat"],
             f"money, code jobs (ledgers, issue jobs attached): ${report['usd_code_jobs']:.4f}; research ${report['usd_research_jobs']:.4f}",
             f"usd per applied change: {report['usd_per_applied_change']}",
             f"decisions per code job: {report['decisions_per_code_job']}",
             f"human wait upper bound: {report['human_wait_s_upper_bound']}",
             f"judge coverage: {report['judge_coverage']}  {report['judge']}"]
    return "\n".join(lines)


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--jobs", default=str(JOBS))
    p.add_argument("--out")
    args = p.parse_args(argv)
    report = build(args.jobs)
    print(text(report))
    if args.out:
        Path(args.out).write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(f"written: {args.out}")


if __name__ == "__main__":
    main()
