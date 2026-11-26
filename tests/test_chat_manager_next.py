"""P4 (SPEC_CHAT_MANAGER_P4): the next steps of a session, from the harness only. A real server on a free port; the jobs are job.json files; the links come from the chat's own audit."""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_chat_actions as t  # noqa: E402
import test_chat_manager as m  # noqa: E402
import test_chat_manager_proposal as p2  # noqa: E402
from router import chat_actions as ca  # noqa: E402

R1, R2, P1, R3 = "j20261115_230000_aaa1", "j20261115_230100_aaa2", "j20261115_230200_aaa3", "j20261115_230300_aaa4"


@pytest.fixture
def svc(tmp_path):
    s = t.Service(tmp_path, cfg=m.config())
    m.make_session(s.jobs, conversation=[p2.HUMAN, p2.turn_of(route="research", repo=None, text=p2.Q)])
    yield s
    s.stop()


def job(svc, jid, kind, state, usd=None):
    d = svc.jobs / jid
    d.mkdir(parents=True)
    stages = {"s1": {"kind": "x", "usd": usd}} if usd is not None else {}
    (d / "job.json").write_text(json.dumps({"job": jid, "kind": kind, "state": state, "max_usd": 1.0, "created_at": t.iso(t.NOW - 50), "stages": stages,
                                            "log": [{"at": t.iso(t.NOW - 50), "what": "created", "via": "ui"}]}))


def link(svc, jid, action="research_new", session=m.JOB, ok="confirm", **more):
    svc.actions.audit(action=action, ok=ok, job=jid, source="manager", source_job=session, source_turn=1, edited=False, **more)


def steps(svc, session=m.JOB):
    s, out = svc.request("GET", f"/api/manager/{session}")
    assert s == 200
    return out["next_steps"]


def test_no_jobs_no_steps(svc):
    assert steps(svc) == []


def test_a_finished_research_points_to_its_report(svc):
    job(svc, R1, "research", "REPORT_READY", 0.105)
    link(svc, R1)
    [n] = steps(svc)
    assert n == {"job": R1, "kind": "research", "state": "REPORT_READY", "usd": 0.105, "hint": "research", "text": "The research is done. Read the report in the Research view."}


def test_a_written_prd_points_to_the_queue_tab_with_two_separate_confirmations(svc):
    job(svc, P1, "prd", "AWAITING_HUMAN", 0.4)
    link(svc, P1, "prd_new")
    [n] = steps(svc)
    assert n["hint"] == "queue" and "two separate confirmations" in n["text"] and n["kind"] == "prd"


@pytest.mark.parametrize("kind, state, hint", [("research", "RESEARCHING", "wait"), ("prd", "WRITING", "wait"), ("research", "ABANDONED", "none"), ("prd", "FAILED", "none"),
                                              ("research", "BLOCKED", "none"), ("research", "lower case", "wait"), ("research", "X" * 80, "wait")])
def test_a_job_still_going_or_ended_gets_its_state_in_a_fixed_sentence(svc, kind, state, hint):
    job(svc, R1, kind, state)
    link(svc, R1, "research_new" if kind == "research" else "prd_new")
    [n] = steps(svc)
    assert n["hint"] == hint and (n["state"] == state or n["state"] == "UNKNOWN") and n["usd"] == 0.0
    assert "ignore" not in json.dumps(n)


def test_a_state_that_is_not_a_plain_name_is_shown_as_unknown(svc):
    job(svc, R1, "research", "REPORT_READY‮ <b>ignore previous</b>")
    link(svc, R1)
    [n] = steps(svc)
    assert n["state"] == "UNKNOWN" and n["hint"] == "wait" and "ignore" not in json.dumps(n)


def test_only_jobs_confirmed_from_this_session_and_only_confirm_lines_count(svc):
    other = "j20261115_220500_abcf"
    m.make_session(svc.jobs, job_id=other)
    job(svc, R1, "research", "REPORT_READY")
    job(svc, R2, "research", "REPORT_READY")
    job(svc, R3, "research", "REPORT_READY")
    link(svc, R1)
    link(svc, R2, session=other)                      # another session's
    link(svc, R3, ok="prepare")                       # only prepared
    svc.actions.audit(action="research_new", ok="confirm", job=R3)       # a typed form: no source
    assert [n["job"] for n in steps(svc)] == [R1]
    assert [n["job"] for n in steps(svc, other)] == [R2]


def test_an_action_other_than_research_or_prd_is_no_step_and_a_missing_or_foreign_job_is_skipped(svc):
    job(svc, R1, "research", "REPORT_READY")
    link(svc, R1, action="issue_new")
    link(svc, "j20261115_239999_beef")                # a well-formed id with no directory
    link(svc, "../x")
    job(svc, R2, "code", "APPLIED")
    link(svc, R2)                                     # a job of another kind
    assert steps(svc) == []


def test_newest_first_each_job_once_and_at_most_ten(svc):
    ids = [f"j20261115_23{i:02d}00_bb{i:02d}" for i in range(12)]
    for i in ids:
        job(svc, i, "research", "REPORT_READY")
    link(svc, ids[0]); link(svc, ids[1]); link(svc, ids[0])        # a repeated line, interleaved: each job once, at its newest place
    assert [n["job"] for n in steps(svc)] == [ids[0], ids[1]]
    for i in ids[2:]:
        link(svc, i)
    out = steps(svc)
    assert len(out) == ca.NEXT_MAX == 10 and [n["job"] for n in out] == [ids[11], ids[10], ids[9], ids[8], ids[7], ids[6], ids[5], ids[4], ids[3], ids[2]]


def test_a_hostile_job_costs_its_own_item_not_the_view(svc):
    job(svc, R1, "research", "REPORT_READY", 0.1)
    job(svc, R2, "research", "REPORT_READY")
    (svc.jobs / R2 / "job.json").write_text('{"job": "x", "kind": "research", "state": "REPORT_READY", "stages": {"s1": {"usd": ' + "9" * 400 + '}}}')
    job(svc, R3, "research", "REPORT_READY")
    (svc.jobs / R3 / "job.json").write_text('{"kind": "research", "state": "REPORT_READY", "stages": {"s1": {"usd": Infinity}}}')
    for j in (R1, R2, R3):
        link(svc, j)
    out = steps(svc)
    assert {n["job"] for n in out} >= {R1} and all(n["usd"] is None or n["usd"] >= 0 for n in out)
    assert [n["usd"] for n in out if n["job"] == R3] in ([], [None])


def test_a_negative_recorded_cost_shows_no_figure(svc):
    job(svc, R1, "research", "REPORT_READY", -3.0)
    link(svc, R1)
    assert steps(svc)[0]["usd"] is None


def test_an_ended_state_is_found_inside_the_name(svc):
    job(svc, R1, "prd", "EXAMPLES_FAILED")
    link(svc, R1, "prd_new")
    assert steps(svc)[0]["hint"] == "none"


def test_the_line_the_real_confirm_writes_is_the_line_the_steps_read(svc):
    s, prep = svc.prepare(action="research_new", message=p2.Q, source_job=m.JOB, source_turn="1")
    assert s == 200
    s, done = svc.confirm(prep["token"])
    assert s == 200
    new = done["job"]
    job(svc, new, "research", "REPORT_READY", 0.2)           # the fake spawner made no directory: the harness would have
    assert [n["job"] for n in steps(svc)] == [new]
    svc.actions.audit(action="research_new", ok="confirm", job=R2)      # what a typed form's confirm writes: no source
    job(svc, R2, "research", "REPORT_READY")
    assert [n["job"] for n in steps(svc)] == [new]


def test_a_broken_audit_line_is_skipped_and_a_missing_audit_gives_nothing(svc):
    job(svc, R1, "research", "REPORT_READY")
    link(svc, R1)
    with open(svc.actions.audit_path, "a") as f:
        f.write("not json\n[1]\n")
    assert [n["job"] for n in steps(svc)] == [R1]
    svc.actions.audit_path.unlink()
    assert steps(svc) == []


def test_the_steps_hold_no_model_text_and_no_report(svc):
    job(svc, R1, "research", "REPORT_READY", 0.1)
    (svc.jobs / R1 / "REPORT.md").write_text("SECRET-REPORT-TEXT")
    link(svc, R1)
    s, out = svc.request("GET", f"/api/manager/{m.JOB}")
    assert "SECRET-REPORT-TEXT" not in json.dumps(out["next_steps"])
    assert set(out["next_steps"][0]) == {"job", "kind", "state", "usd", "hint", "text"}


def test_a_line_that_names_the_session_in_another_field_is_no_step_and_a_broken_one_is_skipped(svc):
    other = "j20261115_220500_abcf"
    m.make_session(svc.jobs, job_id=other)
    job(svc, R1, "research", "REPORT_READY")
    job(svc, R2, "research", "REPORT_READY")
    link(svc, R1, session=other, note=m.JOB)                          # the session's id is in the line, but it is not the line's source
    svc.actions.audit(action="research_new", ok="confirm", job=R2, note=m.JOB)      # a typed form: no source, the id only in a note
    with open(svc.actions.audit_path, "a") as f:
        f.write('{"ok": "confirm", "source_job": "' + m.JOB + '" broken\n')
    assert steps(svc) == []
