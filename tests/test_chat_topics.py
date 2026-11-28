"""F47 phase C1 (SPEC_FOREMAN_TOPICS rev 1), the chat side: the `manager_new` card with a title or a topic, the digest, the audit, the links of a topic, `GET /api/topics`, the fields of
`read_manager`, and the steps across the sessions of one topic. A real server on a free port; the CLI is a recorder."""
import json
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_chat_actions as t  # noqa: E402
import test_chat_manager as m  # noqa: E402
from router import chat_actions as ca  # noqa: E402
from test_chat_manager_next import job, link, steps  # noqa: E402,F401

S1, S2, S3 = "j20261115_220000_aaa1", "j20261115_221000_aaa2", "j20261115_222000_aaa3"


@pytest.fixture
def svc(tmp_path):
    s = t.Service(tmp_path, cfg=m.config())
    yield s
    s.stop()


def sess(svc, jid, state="BLOCKED", continues=None, continued_by=None, title=None, conv=None, created=t.NOW - 5000, **kw):
    m.make_session(svc.jobs, jid, state=state, created=created, conversation=conv, **kw)
    p = svc.jobs / jid / "job.json"
    d = json.loads(p.read_text())
    if continues:
        d["inputs"]["continues"] = continues
    if continued_by:
        d["inputs"]["continued_by"] = continued_by
    if title:
        d["inputs"]["topic"] = {"id": jid, "title": title}
    p.write_text(json.dumps(d))


def prep(svc, **body):
    return svc.prepare(action="manager_new", **body)


# ---- the card -----------------------------------------------------------------------------------------------------

def test_the_plain_card_and_its_fields_are_what_they_were(svc):
    s, out = prep(svc)
    assert s == 200
    c = out["card"]
    assert set(c) == {"action", "title", "model", "job_cap_usd", "turn_cap_usd", "turn_note", "ttl_hours", "max_turns", "confirms", "data_sent"} and "topic_title" not in c


def test_a_title_makes_a_card_with_the_topic_title(svc):
    s, out = prep(svc, title="  ledger-cli: opsi --top ")
    assert s == 200 and out["card"]["topic_title"] == "ledger-cli: opsi --top" and "continues" not in out["card"]
    s2, other = prep(svc, title="ledger-cli: opsi --top")
    assert s2 == 200 and out["card"] == other["card"]


@pytest.mark.parametrize("body", [{"title": ""}, {"title": "   "}, {"title": "x" * 61}, {"title": "a\nb"}, {"title": "a\tb"}, {"title": "a b"}, {"title": "a​b"},
                                  {"title": "kunci sk-or-v1-abcdefghijklmnopqrstuvwxyz0123456789"}, {"title": "a", "topic": S1}, {"topic": "../x"}, {"topic": "nope"}, {"title": "a", "extra": "b"}, {"extra": "b"}])
def test_a_bad_body_is_refused_and_no_token_is_given(svc, body):
    s, out = prep(svc, **body)
    assert s == 400 and "token" not in json.dumps(out)


@pytest.mark.parametrize("action", ["issue_new", "research_new", "prd_new", "queue_go", "job_reject"])
def test_title_and_topic_belong_to_the_foreman_session_only(svc, action):
    for k in ("title", "topic"):
        s, out = svc.prepare(action=action, **{k: S1 if k == "topic" else "x"}, message="m", repo="ledger-cli")
        assert s == 400 and "token" not in json.dumps(out)


def test_confirm_starts_the_cli_with_the_title_in_a_file_never_in_argv(svc):
    s, out = prep(svc, title="Dexie atau idb")
    s2, done = svc.confirm(out["token"])
    assert s2 == 200 and done["started"] is True
    call = svc.spawner.calls[-1]
    argv = call["argv"]
    assert "--title-file" in argv and "Dexie atau idb" not in " ".join(argv) and not any(a.startswith("--continue-from") for a in argv) and argv[argv.index("new") + 1] == "--job-id"
    assert Path(argv[argv.index("--title-file") + 1]).read_text() == "Dexie atau idb" and call["action"] == "manager" and call["message"] is not None
    lines = svc.audit()
    assert all("Dexie" not in json.dumps(x) for x in lines) and not any("continues" in x for x in lines)


# ---- continuing ---------------------------------------------------------------------------------------------------

def test_a_topic_whose_session_can_take_no_more_turns_gets_a_continuation_card(svc):
    sess(svc, S1, title="Ekspor CSV")
    s, out = prep(svc, topic=S1)
    c = out["card"]
    assert s == 200 and c["continues"] == S1 and c["topic_title"] == "Ekspor CSV" and "no model is called" not in c["carried_note"] and "as data" in c["carried_note"]
    assert c["job_cap_usd"] == 0.2 and out["exposure_usd"] == 0.2                                  # a new session is booked as a session is


def test_confirming_a_continuation_runs_the_cli_with_the_session_and_audits_it(svc):
    sess(svc, S1, title="Ekspor CSV")
    s, out = prep(svc, topic=S1)
    s2, done = svc.confirm(out["token"])
    assert s2 == 200
    argv = svc.spawner.calls[-1]["argv"]
    assert f"--continue-from={S1}" in argv and "--title-file" not in argv and svc.spawner.calls[-1]["message"] is None
    lines = svc.audit()
    assert next(x for x in lines if x.get("ok") == "prepare")["topic"] == S1
    c = [x for x in lines if x.get("attempt") == "confirm"][-1]
    assert c["continues"] == S1 and c["action"] == "manager_new" and "Ekspor" not in json.dumps(lines)


@pytest.mark.parametrize("make,status,frag", [
    (lambda svc: None, 409, "no such topic"),
    (lambda svc: sess(svc, S1, state="OPEN"), 409, "still open"),
    (lambda svc: sess(svc, S1, continued_by=S2), 409, "no such topic|already continued|newest"),
    (lambda svc: sess(svc, S1, via=None), 409, "no such topic"),
    (lambda svc: sess(svc, S1, kind="issue"), 409, "no such topic")])
def test_a_continuation_that_may_not_start_is_refused_with_a_sentence_and_no_token(svc, make, status, frag):
    make(svc)
    s, out = prep(svc, topic=S1)
    import re
    assert s == status and "token" not in json.dumps(out) and re.search(frag, json.dumps(out))


def test_an_expired_or_spent_session_is_continuable_and_a_busy_or_unknown_one_is_not(svc):
    sess(svc, S1, state="OPEN", created=t.NOW - 13 * 3600)                                           # expired, still OPEN
    assert prep(svc, topic=S1)[0] == 200
    svc.spawner.busy_ids.add(S1)
    s, out = prep(svc, topic=S1)
    assert s == 409 and "busy" in json.dumps(out)
    svc.spawner.busy_ids.clear()
    sess(svc, S2, state="OPEN", created=t.NOW - 100)                                                 # not expired, so its spend decides
    import shutil
    shutil.rmtree(svc.jobs / S2 / "runs")                                                            # the spend cannot be computed
    s, out = prep(svc, topic=S2)
    assert s == 503 and "token" not in json.dumps(out)


def test_the_card_binds_the_resolved_session_a_newer_one_between_prepare_and_confirm_changes_it(svc):
    sess(svc, S1, title="T")
    s, out = prep(svc, topic=S1)
    assert s == 200 and out["card"]["continues"] == S1
    sess(svc, S2, continues=S1, title=None)                                                          # another tab continued the topic meanwhile
    p = svc.jobs / S1 / "job.json"
    d = json.loads(p.read_text())
    d["inputs"]["continued_by"] = S2
    p.write_text(json.dumps(d))
    s2, done = svc.confirm(out["token"])
    assert s2 in (404, 409, 403) and svc.spawner.calls == []
    s3, again = prep(svc, topic=S1)                                                                  # read fresh: the card now names the newer session, not a cached chain's end
    assert s3 == 200 and again["card"]["continues"] == S2


def test_a_planted_link_does_not_join_a_topic_and_only_a_reciprocal_link_counts(svc):
    sess(svc, S1, title="A", continued_by=S2)
    sess(svc, S2, continues=S1)
    sess(svc, S3, continues=S1)                                                                      # claims S1, but S1 does not link back
    assert [x["id"] for x in svc.actions.topic_sessions(S2)] == [S1, S2]
    assert [x["id"] for x in svc.actions.topic_sessions(S3)] == [S3]
    assert [x["id"] for x in svc.actions.topic_sessions(S1)] == [S1, S2]


# ---- reading ------------------------------------------------------------------------------------------------------

def test_read_manager_names_the_topic_and_gives_the_servers_answer_to_can_a_turn_be_sent(svc):
    sess(svc, S1, title="T1", continued_by=S2, conv=[{"from": "human", "at": t.iso(t.NOW), "text": "halo"}])
    sess(svc, S2, state="OPEN", continues=S1, created=t.NOW - 100, conv=[{"from": "summary", "at": t.iso(t.NOW), "text": "kepala", "covers": [0, 1], "usd": 0, "calls": 0, "carried": True, "sha256": "x"}])
    s, a = svc.request("GET", f"/api/manager/{S1}")
    s2, b = svc.request("GET", f"/api/manager/{S2}")
    assert s == s2 == 200
    assert a["topic"]["id"] == S1 and a["topic"]["title"] == "T1" and a["topic"]["newest"] == S2 and [x["id"] for x in a["topic"]["sessions"]] == [S1, S2] and a["can_take_turn"] is False
    assert b["can_take_turn"] is True and b["topic"]["newest"] == S2 and b["conversation"][0]["carried"] is True and b["conversation"][0]["from"] == "summary"
    assert a["topic"]["legacy"] is False


def test_a_session_from_before_topics_is_its_own_topic_with_a_title_from_its_first_message(svc):
    sess(svc, S1, conv=[{"from": "human", "at": t.iso(t.NOW), "text": "Bikin laporan bulanan ledger-cli yang panjang sekali judulnya"}])
    s, out = svc.request("GET", f"/api/manager/{S1}")
    assert out["topic"]["legacy"] is True and out["topic"]["id"] == S1 and out["topic"]["title"] == "Bikin laporan bulanan ledger-cli yang pa"
    top = svc.request("GET", "/api/topics")[1]["topics"][0]
    assert top["legacy"] is True and top["title"] == out["topic"]["title"]


def test_the_steps_of_the_sessions_of_a_topic_are_one_list_and_another_topic_is_not_in_it(svc):
    sess(svc, S1, title="T", continued_by=S2)
    sess(svc, S2, state="OPEN", continues=S1, created=t.NOW - 100)
    sess(svc, S3, state="OPEN", created=t.NOW - 100)
    job(svc, m.JOB, "research", "REPORT_READY")
    link(svc, m.JOB, session=S1)                                                                     # started from a turn of the FIRST session
    assert [n["job"] for n in steps(svc, S2)] == [m.JOB] and [n["job"] for n in steps(svc, S1)] == [m.JOB] and steps(svc, S3) == []


# ---- GET /api/topics ----------------------------------------------------------------------------------------------

def test_topics_are_listed_newest_first_one_row_per_chain_with_the_latest_session(svc):
    sess(svc, S1, title="Lama", created=t.NOW - 9000, conv=[{"from": "human", "at": t.iso(t.NOW - 8000), "text": "a"}])
    sess(svc, S2, title="Baru", continued_by=S3, created=t.NOW - 4000, conv=[{"from": "human", "at": t.iso(t.NOW - 3500), "text": "b"}])
    sess(svc, S3, state="OPEN", continues=S2, created=t.NOW - 100)
    s, out = svc.request("GET", "/api/topics")
    assert s == 200 and [x["title"] for x in out["topics"]] == ["Baru", "Lama"] and out["capped"] is False and out["unreadable"] == 0
    r = out["topics"][0]
    assert r["id"] == S2 and r["sessions"] == 2 and r["latest"]["id"] == S3 and r["latest"]["state"] == "OPEN" and r["latest"]["can_take_turn"] is True and r["updated_at"]
    assert out["topics"][1]["latest"]["can_take_turn"] is False


def test_the_list_is_capped_unreadable_sessions_are_counted_and_a_symlinked_directory_is_skipped(svc):
    for i in range(55):
        sess(svc, f"j20261115_22{i:02d}00_ab{i:02d}", title=f"T{i}", created=t.NOW - 7000 + i)
    bad = svc.jobs / "j20261115_235900_ffff"
    bad.mkdir()
    (bad / "job.json").write_text('{"job": "j20261115_235900_ffff", "kind": "manager", BROKEN')
    os.symlink(svc.jobs / "j20261115_220000_ab00", svc.jobs / "j20261115_235800_eeee")
    s, out = svc.request("GET", "/api/topics")
    assert len(out["topics"]) == 50 and out["capped"] is True and out["unreadable"] == 2


def test_a_job_that_is_not_a_foreman_session_or_not_via_the_ui_is_no_topic(svc):
    t.make_issue(svc.jobs, "j20261115_230000_beef")
    sess(svc, S1, via=None)
    sess(svc, S2, title="ok")
    assert [x["title"] for x in svc.request("GET", "/api/topics")[1]["topics"]] == ["ok"]


def test_a_planted_topic_field_cannot_join_another_topic(svc):
    sess(svc, S1, title="Asli")
    sess(svc, S2, title="Asli")                                                                      # the same title and a planted topic id of S1: still its own topic
    p = svc.jobs / S2 / "job.json"
    d = json.loads(p.read_text())
    d["inputs"]["topic"] = {"id": S1, "title": "Asli"}
    p.write_text(json.dumps(d))
    out = svc.request("GET", "/api/topics")[1]
    assert sorted(x["id"] for x in out["topics"]) == [S1, S2] and all(x["sessions"] == 1 for x in out["topics"])


def test_the_list_is_kept_a_few_seconds_and_dropped_when_a_session_is_confirmed(svc):
    sess(svc, S1, title="Satu")
    first = svc.request("GET", "/api/topics")[1]
    sess(svc, S2, title="Dua")
    assert svc.request("GET", "/api/topics")[1] == first                                              # cached
    s, out = prep(svc, title="Tiga")
    svc.confirm(out["token"])
    assert len(svc.request("GET", "/api/topics")[1]["topics"]) == 2                                  # dropped: the new session job is not in the directory yet, the two others are


def test_the_route_is_read_only(svc):
    assert svc.request("POST", "/api/topics", {})[0] in (404, 405)


def test_the_old_session_card_and_its_digest_are_unchanged_for_an_empty_body(svc):
    s, a = prep(svc)
    s2, b = prep(svc)
    assert s == s2 == 200 and a["card"] == b["card"] and ca.ACTIONS.count("manager_new") == 1
