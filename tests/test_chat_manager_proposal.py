"""P2b (SPEC_CHAT_MANAGER 13.5, 13.6): a form filled from the foreman's proposal. The proposal is data in the session; the form it fills is the human's own:
the same card, the same checks, the same confirm. What is new is only the claim of where the text came from, which the server checks and which the card, its digest
and the audit carry. A real server on a free port; the CLI is a recorder."""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_chat_actions as t  # noqa: E402
import test_chat_manager as m  # noqa: E402
from router import chat_actions as ca  # noqa: E402

REPOS = list(m.BASE["issue_writer"]["repos"])
REPO = REPOS[0]
OTHER = next(r for r in REPOS if r != REPO)
TEXT = "Tambah ringkasan mingguan di halaman Progress dan jelaskan alasannya."
WHY = "ALASAN-RAHASIA-MODEL"
Q = "Bandingkan tiga cara menyimpan data ringkasan mingguan di PWA."
HUMAN = {"from": "human", "at": "2026-11-15T21:59:00Z", "text": "ide"}


def turn_of(route="prd", repo=REPO, text=TEXT, why=WHY):
    return {"from": "manager", "at": "2026-11-15T21:59:30Z", "say": "ok", "propose": {"route": route, "repo": repo, "text": text, "why": why}, "usd": 0.0004, "calls": 1}


@pytest.fixture
def svc(tmp_path):
    s = t.Service(tmp_path, cfg=m.config())
    m.make_session(s.jobs, conversation=[HUMAN, "junk", turn_of(), {"from": "manager", "say": "hanya ngobrol", "propose": None, "usd": 0, "calls": 1}, {"from": "manager", "say": "x", "propose": {"route": "ask", "repo": None, "text": "t", "why": "w"}}])
    yield s
    s.stop()


def prep(svc, action="prd_new", **kw):
    body = {"action": action, "message": TEXT, "source_job": m.JOB, "source_turn": "2", **kw}
    if action == "prd_new":
        body.setdefault("repo", REPO)
    return svc.prepare(**body)


def test_a_prd_form_filled_from_a_proposal_gets_the_card_of_a_typed_one_plus_the_source(svc):
    s, out = prep(svc)
    s2, typed = svc.prepare(action="prd_new", repo=REPO, message=TEXT)
    assert s == s2 == 200
    c, c2 = out["card"], typed["card"]
    assert c["source"] == {"from": "manager", "job": m.JOB, "turn": 2, "edited": False} and c["source_note"] == ca.SOURCE_NOTE
    assert {k: v for k, v in c.items() if k not in ("source", "source_note")} == c2
    assert out["exposure_usd"] == typed["exposure_usd"]


def test_the_why_of_the_model_is_never_in_the_card(svc):
    s, out = prep(svc)
    assert s == 200 and WHY not in json.dumps(out) and "why" not in out["card"]


def test_the_source_changes_the_digest_so_the_token_is_bound_to_it(svc):
    a = prep(svc)[1]["card"]
    b = svc.prepare(action="prd_new", repo=REPO, message=TEXT)[1]["card"]
    assert svc.actions.digest(a) != svc.actions.digest(b)


@pytest.mark.parametrize("kw, edited", [({"message": TEXT + " Tambahkan juga grafik."}, True), ({"repo": OTHER}, True), ({}, False)])
def test_edited_is_computed_by_the_server_from_the_form_and_the_proposal(svc, kw, edited):
    s, out = prep(svc, **kw)
    assert s == 200 and out["card"]["source"]["edited"] is edited


def test_a_form_for_another_route_than_the_proposal_is_marked_edited(svc):
    s, out = prep(svc, action="research_new", message=Q)
    assert s == 200 and out["card"]["source"]["edited"] is True


def test_a_research_form_filled_from_a_research_proposal_is_not_edited(svc):
    m.make_session(svc.jobs, job_id=m.JOB2, conversation=[HUMAN, turn_of(route="research", repo=None, text=Q)])
    s, out = prep(svc, action="research_new", message=Q, source_job=m.JOB2, source_turn="1")
    assert s == 200 and out["card"]["source"] == {"from": "manager", "job": m.JOB2, "turn": 1, "edited": False} and "why" not in out["card"]


@pytest.mark.parametrize("kw", [
    {"source_job": "j20261115_220100_abce"},                      # no such session
    {"source_job": "../x"}, {"source_job": ""}, {"source_turn": "0"}, {"source_turn": "1"},       # a human turn, a junk entry
    {"source_turn": "3"}, {"source_turn": "4"},                   # no proposal; a proposal of route ask
    {"source_turn": "5"}, {"source_turn": "9"}, {"source_turn": "-1"}, {"source_turn": "1.0"}, {"source_turn": "0001"}, {"source_turn": "02"}, {"source_turn": " 2"}, {"source_turn": "2 "}, {"source_turn": "+2"}, {"source_turn": "١"}, {"source_turn": "1 "},
])
def test_a_source_that_is_not_a_foreman_proposal_is_refused_without_a_token(svc, kw):
    s, out = prep(svc, **kw)
    assert s in (400, 404) and "token" not in json.dumps(out)


def test_both_source_fields_or_none(svc):
    s, out = svc.prepare(action="prd_new", repo=REPO, message=TEXT, source_job=m.JOB)
    assert s == 400 and "token" not in json.dumps(out)
    s, out = svc.prepare(action="prd_new", repo=REPO, message=TEXT, source_turn="2")
    assert s == 400 and "token" not in json.dumps(out)


def test_a_job_that_is_not_a_session_is_no_source(svc):
    j = "j20261115_220200_abcf"
    m.make_session(svc.jobs, job_id=j, kind="prd", conversation=[HUMAN, turn_of()])
    s, out = prep(svc, source_job=j, source_turn="1")
    assert s == 404 and "token" not in json.dumps(out)


@pytest.mark.parametrize("body", [
    {"action": "issue_new", "repo": REPO, "message": TEXT}, {"action": "issue_reply", "job": m.JOB, "message": TEXT}, {"action": "issue_start", "job": m.JOB},
    {"action": "issue_abandon", "job": m.JOB}, {"action": "queue_go", "queue": "q"}, {"action": "prd_approve", "job": m.JOB}, {"action": "manager_new"},
    {"action": "job_reject", "job": m.JOB}])
def test_no_other_action_takes_a_source(svc, body):
    s, out = svc.prepare(**body, source_job=m.JOB, source_turn="2")
    assert s == 400 and "token" not in json.dumps(out) and "only a research or PRD job" in json.dumps(out)


def test_the_proposal_text_is_not_trusted_the_form_goes_through_the_actions_own_checks(svc):
    s, out = prep(svc, message="a‮b")
    assert s == 400 and "token" not in json.dumps(out)
    s, out = prep(svc, message="")
    assert s == 400
    s, out = prep(svc, repo="elsewhere")
    assert s == 400


def test_the_confirm_runs_what_the_card_showed_and_the_audit_names_the_source(svc):
    s, out = prep(svc, message=TEXT + " Dan grafik.")
    assert s == 200
    s, done = svc.confirm(out["token"])
    assert s == 200 and done["started"] is True
    lines = svc.audit()
    prepare_line = next(x for x in lines if x.get("ok") == "prepare")
    confirm_line = [x for x in lines if x.get("attempt") == "confirm"][0]
    assert prepare_line["source_job"] == m.JOB and prepare_line["source_turn"] == 2
    assert confirm_line["source"] == "manager" and confirm_line["source_job"] == m.JOB and confirm_line["source_turn"] == 2 and confirm_line["edited"] is True
    assert TEXT not in json.dumps(lines) and WHY not in json.dumps(lines)
    call = svc.spawner.calls[-1]
    assert "--message-file" in json.dumps(call, default=str) and WHY not in json.dumps(call, default=str)


def test_a_typed_form_has_no_source_in_audit_or_card(svc):
    s, out = svc.prepare(action="prd_new", repo=REPO, message=TEXT)
    assert "source" not in out["card"]
    svc.confirm(out["token"])
    assert all("source" not in x and "source_job" not in x for x in svc.audit())


def test_a_session_that_ended_still_has_its_proposals_readable_as_sources(svc):
    d = svc.jobs / m.JOB / "job.json"
    j = json.loads(d.read_text())
    j["state"] = "ABANDONED"
    d.write_text(json.dumps(j))
    assert prep(svc)[0] == 200


def test_the_read_route_gives_each_turn_its_index_for_the_form(svc):
    s, out = svc.request("GET", f"/api/manager/{m.JOB}")
    assert s == 200 and [e["n"] for e in out["conversation"]] == [0, 2, 3, 4]
    assert out["conversation"][1]["propose"]["route"] == "prd"
    assert prep(svc, source_turn=str(out["conversation"][1]["n"]))[0] == 200


def test_a_crlf_from_a_textarea_is_not_an_edit(svc):
    m.make_session(svc.jobs, job_id=m.JOB2, conversation=[HUMAN, turn_of(text="baris satu\nbaris dua")])
    s, out = prep(svc, message="baris satu\r\nbaris dua", source_job=m.JOB2, source_turn="1")
    assert s == 200 and out["card"]["source"]["edited"] is False


def test_the_audit_writes_only_an_id_and_a_number_of_the_clients_source(svc):
    svc.prepare(action="prd_new", repo=REPO, message=TEXT, source_job="x" * 150, source_turn="12345678")
    line = [x for x in svc.audit() if "source_job" in x]
    assert line == [] or all(x["source_job"] == "bad" and x["source_turn"] == -1 for x in line)


def test_a_session_rewritten_after_prepare_is_not_confirmed(svc):
    s, out = prep(svc)
    j = svc.jobs / m.JOB / "job.json"
    d = json.loads(j.read_text())
    d["conversation"][2]["propose"]["text"] = "teks lain sama sekali"
    j.write_text(json.dumps(d))
    s, body = svc.confirm(out["token"])
    assert s == 409 and svc.spawner.calls == [] and not any(x.get("ok") == "confirm" for x in svc.audit())
    s, out = prep(svc)
    d["conversation"] = d["conversation"][:2]
    j.write_text(json.dumps(d))
    s, body = svc.confirm(out["token"])
    assert s == 404 and svc.spawner.calls == []


def test_a_negative_index_does_not_reach_the_last_turn(svc):
    m.make_session(svc.jobs, job_id=m.JOB2, conversation=[HUMAN, turn_of()])
    assert prep(svc, source_job=m.JOB2, source_turn="1")[0] == 200
    for t_ in ("-1", "-2"):
        s, out = prep(svc, source_job=m.JOB2, source_turn=t_)
        assert s == 400 and "token" not in json.dumps(out)


def test_a_human_entry_with_a_proposal_shape_is_no_source(svc):
    m.make_session(svc.jobs, job_id=m.JOB2, conversation=[{**HUMAN, "propose": turn_of()["propose"]}])
    s, out = prep(svc, source_job=m.JOB2, source_turn="0")
    assert s == 404 and "token" not in json.dumps(out)


def test_the_route_alone_makes_a_form_edited(svc):
    s, out = prep(svc, action="research_new", message=TEXT)
    assert s == 200 and out["card"]["source"]["edited"] is True


def test_a_proposal_text_is_compared_as_the_card_would_show_it(svc):
    k = "sk-or-v1-" + "a" * 40
    m.make_session(svc.jobs, job_id=m.JOB2, conversation=[HUMAN, turn_of(text=TEXT + " \u200b" + "x")])
    s, out = prep(svc, message=ca.scrub(TEXT + " \u200b" + "x"), source_job=m.JOB2, source_turn="1")
    assert s == 200 and out["card"]["source"]["edited"] is False


def test_the_run_params_hold_the_form_and_nothing_of_the_source(svc):
    out = svc.actions.prepare("prd_new", {"repo": REPO, "message": TEXT, "source_job": m.JOB, "source_turn": "2"})[0]
    svc.clock.t += ca.MIN_DELAY + 0.1
    action, card, rp, digest = svc.actions.confirm(out["token"])
    assert rp == {"repo": REPO, "message": TEXT}
