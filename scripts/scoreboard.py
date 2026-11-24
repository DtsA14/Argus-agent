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

from router.job import ACTORS, JOBS, runs_spent_nano  # noqa: E402

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


def staged(data):
    """True when the job's log has the entry a staging deploy writes (router/stage.py, stage_viewer.py)."""
    return any(e.get("what") == "staged" for e in data.get("log") or [])


def applied_by(data):
    """"command" when `argus apply` recorded the apply (method=apply, since 2026-11-15), "unknown" for an applied job without it (by hand, or before the
    command), None when the job was not applied."""
    if data.get("state") != "APPLIED":
        return None
    entry = next((e for e in reversed(data.get("log") or []) if e.get("what") == "state" and e.get("new") == "APPLIED"), {})
    return "command" if entry.get("method") == "apply" else "unknown"


def hands_off(data):
    """True when nothing beyond the approval and the closing APPLIED is in the job's decisions (no retry, redraft or research ok), nobody steered it
    (`human_steered`), and the applied commit is the reviewed patch (as_is). A NECESSARY condition for "without Claude", not a sufficient one: who approved,
    applied and deployed is not recorded (`by` is $USER), so a job that is True here may still have had Claude do each of those by hand."""
    category, _ = outcome(data)
    return category == "applied_untouched" and not data.get("human_steered") and decisions(data) == 2


def actor_class(data):
    """SPEC_ACTOR_RECORD: for one code job, "with_claude" (a decision record of the job says "claude"), "unknown" (it was applied and its approval or its APPLIED record has no valid actor:
    a job from before the field), "without_claude" (hands off, applied by `argus apply`, and the approval and the APPLIED record both say "ui" or "terminal") or "other" (open,
    failed, rejected, abandoned, applied with changes or by hand with no Claude on record: no claim either way). The approval is read from `data["approval"]`, the other records
    from the log. Decisions upstream of the job (the queue's `go`, `prd approve`, `issue start`) and the staging deploy are NOT looked at."""
    log = data.get("log") or []
    approval = (data.get("approval") or {}).get("actor")
    applied_entry = next((e for e in reversed(log) if e.get("what") == "state" and e.get("new") == "APPLIED"), {})
    seen = [a for a in (approval, (data.get("research_ok") or {}).get("actor"), applied_entry.get("actor"),
                        *(e.get("actor") for e in log if e.get("what") in DECISION_WHATS or (e.get("what") == "state" and e.get("new") in MOVES))) if a is not None]
    if "claude" in seen:
        return "with_claude"
    if data.get("state") == "APPLIED" and (approval not in ACTORS or applied_entry.get("actor") not in ACTORS):
        return "unknown"
    if hands_off(data) and applied_by(data) == "command" and data.get("state") == "APPLIED" and all(a in ("ui", "terminal") for a in seen):
        return "without_claude"
    return "other"


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
            "staged": staged(data), "applied_by": applied_by(data), "hands_off": hands_off(data), "actor_class": actor_class(data),
        })
    research = sum(nano[d["job"]] for _, d in jobs if d.get("kind") == "research")
    prd = sum(nano[d["job"]] for _, d in jobs if d.get("kind") == "prd")           # SPEC_PRD_WRITER: its own total
    kinds = Counter(d.get("kind") for _, d in jobs)
    counts = Counter(r["outcome"] for r in rows)
    applied = counts["applied_untouched"] + counts["applied_changed"] + counts["applied_not_compared"]
    code_total = sum(r["usd_nano"] + r["issue_usd_nano"] for r in rows)
    waits = [r["wait_s"][k] for r in rows for k in ("draft", "review") if r["wait_s"][k] is not None]
    judged = Counter(r["judge"] for r in rows)
    n_staged = sum(1 for r in rows if r["staged"])
    n_hands = sum(1 for r in rows if r["hands_off"])
    n_hands_staged = sum(1 for r in rows if r["hands_off"] and r["staged"])
    n_command = sum(1 for r in rows if r["applied_by"] == "command")
    actors = Counter(r["actor_class"] for r in rows)
    n_without_staged = sum(1 for r in rows if r["actor_class"] == "without_claude" and r["staged"])
    return {
        "jobs_dir": str(jobs_dir), "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "jobs_by_kind": dict(kinds), "code_jobs": len(rows), "outcomes": dict(counts),
        "staged": n_staged, "staged_share_of_code_jobs": round(n_staged / len(rows), 4) if rows else None,
        "hands_off_applied": n_hands, "hands_off_staged": n_hands_staged,
        "hands_off_to_staging_upper_bound": round(n_hands_staged / len(rows), 4) if rows else None,
        "actor_classes": {k: actors.get(k, 0) for k in ("without_claude", "with_claude", "unknown", "other")},
        "without_claude_share_of_code_jobs": round(actors["without_claude"] / len(rows), 4) if rows else None,
        "without_claude_and_staged": n_without_staged,
        "actor_meaning": "SPEC_ACTOR_RECORD: per code job, from the `actor` of its decision records (claude = a Claude Code session ran the command, `ui` = the chat, `terminal` = any other shell). "
                         "without_claude = hands off, applied by `argus apply`, approval and APPLIED both ui or terminal; with_claude = any record says claude; unknown = applied with no "
                         "actor on its approval or APPLIED record (before 2026-11-24); other = no claim (open, failed, rejected, abandoned, changed or applied by hand). The staging deploy "
                         "and decisions upstream of the job (queue go, prd approve, issue start) are not covered, and a command that the human typed with `!` inside a Claude session reads as claude.",
        "applied_by_command": n_command, "applied_by_command_share_of_applied": round(n_command / applied, 4) if applied else None,
        "hands_off_meaning": "hands_off_to_staging_upper_bound = code jobs that reached staging with no retry, redraft, research ok or steering and applied as reviewed, "
                             "over all code jobs. It is an UPPER BOUND of 'to staging without Claude', not 'without Claude': who approved, applied and deployed is "
                             "not recorded, so a job inside it may still have had Claude do each step by hand; a job outside it certainly needed an extra decision. "
                             "It becomes exact only when approve is possible from the chat (via=ui) and apply records method=apply (argus apply, from 2026-11-15).",
        "applied": applied, "applied_share_of_code_jobs": round(applied / len(rows), 4) if rows else None,
        "applied_untouched_share": round(counts["applied_untouched"] / applied, 4) if applied else None,
        "usd_code_jobs": code_total / 1e9, "usd_research_jobs": research / 1e9, "usd_prd_jobs": prd / 1e9, "usd_issue_jobs_unattached": orphan_issue / 1e9,
        "usd_per_applied_change": round(code_total / 1e9 / applied, 4) if applied else None,
        "decisions_per_code_job": round(sum(r["decisions"] for r in rows) / len(rows), 3) if rows else None,
        "human_wait_s_upper_bound": {"n": len(waits), "median": statistics.median(waits) if waits else None,
                                     "total": sum(waits) if waits else 0},
        "judge": dict(judged), "judge_coverage": round(1 - judged["no judge"] / len(rows), 4) if rows else None,
        "by_repo": {r: dict(Counter(x["outcome"] for x in rows if x["repo"] == r)) for r in sorted({x["repo"] for x in rows})},
        "ledger_vs_stage_usd": {"ledger": sum(r["usd_nano"] for r in rows) / 1e9, "job_json": sum(r["stage_usd_sum"] for r in rows)},
        "caveat": "applied_untouched means the applied commit equals the reviewed patch (as_is); it is not a success rate "
                  "and not 'mergeable untouched' (that needs grading by someone outside the loop). The denominator of "
                  "applied_share_of_code_jobs counts every code job, including open ones. hands_off_to_staging_upper_bound is an upper bound "
                  "(see hands_off_meaning), not the share of work done without Claude.",
        "rows": rows,
        "not_known": ["re-issues of one issue (jobs per applied change are by repo only)",
                      "who decided (by is $USER): the hands-off figure is an upper bound of 'without Claude' for that reason",
                      "minutes of attention (waits include idle time)", "Claude's token cost (outside the harness)",
                      "spend of stages cut off before their ledger was written (the ledger figure is used where it exists)"],
    }


def text(report):
    o = report["outcomes"]
    lines = [f"jobs by kind: {report['jobs_by_kind']}", f"code jobs: {report['code_jobs']}",
             "outcomes: " + ", ".join(f"{k} {v}" for k, v in sorted(o.items())),
             f"applied: {report['applied']} = {report['applied_share_of_code_jobs']} of code jobs; of those, as reviewed (as_is) "
             f"{report['applied_untouched_share']}",
             f"staged: {report['staged']} = {report['staged_share_of_code_jobs']} of code jobs; applied by `argus apply`: {report['applied_by_command']}",
             f"actors (SPEC_ACTOR_RECORD; deploy and upstream decisions not covered): {report['actor_classes']}; without Claude and staged: {report['without_claude_and_staged']} of {report['code_jobs']}",
             f"hands off to staging (UPPER BOUND of 'without Claude'): {report['hands_off_staged']} of {report['code_jobs']} = "
             f"{report['hands_off_to_staging_upper_bound']} (hands off and applied: {report['hands_off_applied']})",
             f"ledger vs job.json stage usd: {report['ledger_vs_stage_usd']}",
             "caveat: " + report["caveat"],
             f"money, code jobs (ledgers, issue jobs attached): ${report['usd_code_jobs']:.4f}; research ${report['usd_research_jobs']:.4f}; prd writer ${report['usd_prd_jobs']:.4f}",
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
