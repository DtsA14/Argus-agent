"""scripts/scoreboard.py: outcomes, money from the ledgers, decisions, human wait, judge, issue-job attachment."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import scoreboard as sb  # noqa: E402


def entry(what, at, **kw):
    return {"what": what, "at": at, **kw}


def make(tmp, name, *, kind="code", state="APPLIED", log=None, stages=None, approval=None, usd_nano=None, **extra):
    d = tmp / name
    (d / "runs").mkdir(parents=True)
    for stage in (stages or {}).values():
        if usd_nano is not None and stage.get("run_id") in usd_nano:
            run = d / "runs" / stage["run_id"]
            run.mkdir()
            n = usd_nano[stage["run_id"]]
            (run / "events.jsonl").write_text(
                json.dumps({"event": "llm_call_started", "call_id": "c1", "worst_usd_nano": n * 2}) + "\n"
                + json.dumps({"event": "llm_call", "call_id": "c1", "status": "ok", "usd_nano": n}) + "\n")
    data = {"job": name, "kind": kind, "state": state, "created_at": "2026-11-01T00:00:00Z", "log": log or [],
            "stages": stages or {}, "approval": approval, "inputs": {"repo_name": "app", "repo": "/x/app"}, **extra}
    (d / "job.json").write_text(json.dumps(data))
    return d


def applied_log(as_is):
    return [entry("state", "2026-11-01T00:10:00Z", old="REVIEW_READY", new="APPLIED", as_is=as_is)]


def test_outcome_categories():
    assert sb.outcome({"state": "APPLIED", "log": applied_log(True)})[0] == "applied_untouched"
    assert sb.outcome({"state": "APPLIED", "log": applied_log(False)})[0] == "applied_changed"
    assert sb.outcome({"state": "APPLIED", "log": applied_log(None)})[0] == "applied_not_compared"
    rej = {"state": "REJECTED", "log": [entry("state", "t", old="AWAITING_APPROVAL", new="REJECTED")]}
    assert sb.outcome(rej) == ("rejected", "AWAITING_APPROVAL")
    assert sb.outcome({"state": "ABANDONED", "log": [entry("state", "t", old="REVIEW_READY", new="ABANDONED")]}) == \
        ("abandoned", "REVIEW_READY")
    for failed in ("DRAFT_FAILED", "AGENT_FAILED", "BLOCKED", "REVIEW_INVALID"):
        assert sb.outcome({"state": failed}) == ("failed", failed)
    assert sb.outcome({"state": "REVIEW_READY"}) == ("open", "REVIEW_READY")


def test_decisions_count_an_approval_once_and_the_closing_move():
    log = [entry("limits_shown", "t"), entry("confirmed_by_flag", "t"), entry("approved", "t"),
           entry("retry", "t"), entry("redraft", "t"), entry("research_ok", "t"),
           entry("state", "t", new="AGENT_RUNNING")] + applied_log(True)
    assert sb.decisions({"log": log}) == 5       # approved, retry, redraft, research_ok, APPLIED


def test_human_wait_uses_the_draft_that_was_approved_and_none_when_fields_are_missing():
    data = {"approval": {"draft_sha256": "B", "at": "2026-11-01T00:05:00Z"},
            "stages": {"d1": {"kind": "draft", "draft_sha256": "A", "ended_at": "2026-11-01T00:00:00Z"},
                       "d2": {"kind": "draft", "draft_sha256": "B", "ended_at": "2026-11-01T00:03:00Z"},
                       "a1": {"kind": "agent", "ended_at": "2026-11-01T00:08:00Z"}},
            "log": applied_log(True)}
    assert sb.human_wait(data) == {"draft": 120.0, "review": 120.0}
    assert sb.human_wait({"stages": {}, "approval": None, "log": []}) == {"draft": None, "review": None}


def test_judge_values():
    assert sb.judge({"stages": {}}) == "no judge"
    assert sb.judge({"stages": {"j1": {"kind": "judge", "verdict": "BLOCK"}}}) == "BLOCK"
    assert sb.judge({"stages": {"j1": {"kind": "judge", "status": None}}}) == "cut off"


def test_report_money_comes_from_the_ledgers_and_issue_jobs_are_attached(tmp_path):
    stages = {"d1": {"kind": "draft", "run_id": "j1-d1", "usd": 99.0, "draft_sha256": "A", "ended_at": "2026-11-01T00:00:00Z"}}
    make(tmp_path, "j1", stages=stages, usd_nano={"j1-d1": 2_000_000_000}, log=applied_log(True),
         approval={"draft_sha256": "A", "at": "2026-11-01T00:01:00Z"})
    make(tmp_path, "j2", state="REJECTED", log=[entry("state", "t", old="AWAITING_APPROVAL", new="REJECTED")])
    make(tmp_path, "i1", kind="issue", state="HANDED_OFF", handoff={"job": "j1"},
         stages={"w1": {"kind": "write", "run_id": "i1-w1"}}, usd_nano={"i1-w1": 500_000_000})
    make(tmp_path, "r1", kind="research", state="REPORT_READY",
         stages={"p1": {"kind": "plan", "run_id": "r1-p1"}}, usd_nano={"r1-p1": 300_000_000})
    (tmp_path / "broken").mkdir()
    (tmp_path / "broken" / "job.json").write_text("{not json")
    r = sb.build(tmp_path)
    assert r["jobs_by_kind"] == {"code": 2, "issue": 1, "research": 1} and r["code_jobs"] == 2
    assert r["outcomes"] == {"applied_untouched": 1, "rejected": 1} and r["applied"] == 1
    assert r["applied_share_of_code_jobs"] == 0.5 and r["applied_untouched_share"] == 1.0
    assert r["usd_code_jobs"] == 2.5                      # ledger 2.0 (not the 99.0 in job.json) + the issue job's 0.5
    assert r["usd_research_jobs"] == 0.3 and r["usd_per_applied_change"] == 2.5
    row = {x["job"]: x for x in r["rows"]}["j1"]
    assert row["usd_nano"] == 2_000_000_000 and row["issue_usd_nano"] == 500_000_000 and row["judge"] == "no judge"
    assert row["wait_s"]["draft"] == 60.0 and r["judge_coverage"] == 0.0


def test_an_issue_job_without_a_known_code_job_is_counted_apart(tmp_path):
    make(tmp_path, "i1", kind="issue", state="HANDED_OFF", handoff={"job": "gone"},
         stages={"w1": {"kind": "write", "run_id": "i1-w1"}}, usd_nano={"i1-w1": 400_000_000})
    r = sb.build(tmp_path)
    assert r["usd_issue_jobs_unattached"] == 0.4 and r["code_jobs"] == 0 and r["applied_share_of_code_jobs"] is None


def test_main_writes_the_json_and_prints_the_caveat(tmp_path, capsys):
    make(tmp_path / "jobs", "j1", log=applied_log(True))
    out = tmp_path / "out.json"
    sb.main(["--jobs", str(tmp_path / "jobs"), "--out", str(out)])
    assert "not a success rate" in capsys.readouterr().out
    assert json.loads(out.read_text())["code_jobs"] == 1
