"""SPEC_CHAT_UI2 rev 2: who started a request, the repositories the writer read, the bundle heading, the plan cards. Real files, no model."""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_chat_plan as tp  # noqa: E402
import test_examples_read as ter  # noqa: E402
from router import chat_actions as ca  # noqa: E402
from router import request_by as rb  # noqa: E402

H40 = "a" * 40


def conv(*texts):
    return [{"from": "human", "text": t} for t in texts]


@pytest.mark.parametrize("log, first", [([{"what": "created", "via": "ui"}], "chat"), ([{"what": "created"}], "terminal"),
                                        ([], "terminal"), ([{"what": "note", "via": "ui"}], "terminal"), ([{"what": "created", "via": "cli"}], "terminal")])
def test_only_the_first_message_of_a_job_created_via_ui_is_chat(log, first):
    got = rb.human_messages({"log": log, "conversation": conv("a", "b")})
    assert [b for _t, b in got] == [first, "terminal"]


def test_a_conversation_that_does_not_open_with_the_human_has_no_chat_message():
    got = rb.human_messages({"log": [{"what": "created", "via": "ui"}], "conversation": [{"from": "writer", "text": "w"}, *conv("a")]})
    assert got == [("a", "terminal")]


def test_stop_turn_ends_the_list_at_that_writers_reply():
    d = {"conversation": [*conv("a"), {"from": "writer", "stage": "w1", "text": "x"}, *conv("b")]}
    assert rb.human_messages(d, stop_turn="w1") == [("a", "terminal")] and len(rb.human_messages(d)) == 2


@pytest.mark.parametrize("refs", [None, []])
def test_no_refs_is_none(refs):
    assert rb.ref_facts({}) is None and rb.ref_facts({"refs": refs}) is None


def ref(name="athena", commit=H40, **kw):
    return {"name": name, "commit": commit, "files": "f", "readme": None, **kw}


def test_good_refs_are_names_and_twelve_characters_of_the_commit():
    assert rb.ref_facts({"refs": [ref(), ref("ledger-cli", "b" * 40)]}) == [{"name": "athena", "commit12": "a" * 12}, {"name": "ledger-cli", "commit12": "b" * 12}]


@pytest.mark.parametrize("refs", [{"a": 1}, "x", [ref(), ref("b"), ref("c")], [ref(name="../x")], [ref(name="a b")], [ref(name="")], [ref(commit="a" * 39)],
                                  [ref(commit=H40 + "\n")], [ref(commit="A" * 40)], [ref(name=3)], [3], [{"name": "a"}], [ref(name="é")]])
def test_refs_that_are_not_the_frozen_shape_are_unreadable_not_an_error(refs):
    assert rb.ref_facts({"refs": refs}) == rb.UNREADABLE


def test_the_excerpt_drops_format_characters_and_cuts_by_code_points():
    assert rb.excerpt("a‮b​c", 10) == ("abc", False)
    text, cut = rb.excerpt("😀" * 500, 400)
    assert cut and len(text) == 400 and text == "😀" * 400
    assert rb.excerpt("x" * 400, 400) == ("x" * 400, False)


def test_the_prd_actions_of_the_chat_are_new_approve_and_reply():
    assert [a for a in ca.ACTIONS if a.startswith("prd_")] == ["prd_new", "prd_approve", "prd_reply"]          # prd_reply: SPEC_CHAT_APPLY_REPLY (F28)


# ---- the bundle ----------------------------------------------------------------------------------------------------

def edit(jobs, **fields):
    p = jobs / ter.PJOB / "job.json"
    data = json.loads(p.read_text())
    data.update(fields)
    p.write_text(json.dumps(data))


def test_the_bundle_names_who_started_each_request_and_the_template_warns_about_the_terminal(tmp_path):
    jobs = tmp_path / "jobs"
    jobs.mkdir()
    ter.make(jobs)
    edit(jobs, log=[{"what": "created", "via": "ui"}], conversation=[*conv("first rule"), {"from": "writer", "text": "w", "stage": "w1"}, *conv("second rule")])
    text = ter.bundle(jobs)[0]
    assert "=== DATA request 1 of 1: started in chat (recorded via ui) (verbatim)" in text or "DATA request: started in chat (recorded via ui) (verbatim)" in text
    assert "may be written by a Claude session" in text and "the human's words" not in text


def test_a_terminal_job_and_a_reply_get_the_terminal_label(tmp_path):
    jobs = tmp_path / "jobs"
    jobs.mkdir()
    ter.make(jobs)
    edit(jobs, log=[{"what": "created"}], conversation=[*conv("a"), {"from": "writer", "text": "w", "stage": "w0"}, *conv("b"), {"from": "writer", "text": "w", "stage": "w1"}])
    text = ter.bundle(jobs)[0]
    assert text.count("typed in the terminal (the human or a Claude session; not recorded which) (verbatim)") == 2
    assert "started in chat" not in text
    assert "DATA request 1 of 2: typed" in text and "DATA request 2 of 2: typed" in text


def test_the_label_is_part_of_the_bundle_hash(tmp_path):
    jobs = tmp_path / "jobs"
    jobs.mkdir()
    ter.make(jobs)
    edit(jobs, log=[], conversation=[*conv("a"), {"from": "writer", "text": "w", "stage": "w1"}])
    before = ter.bundle(jobs)[1]["bundle_sha256"]
    edit(jobs, log=[{"what": "created", "via": "ui"}])
    assert ter.bundle(jobs)[1]["bundle_sha256"] != before


# ---- the plan cards ------------------------------------------------------------------------------------------------

def patch_job(svc, **fields):
    p = svc.jobs / tp.PJOB / "job.json"
    data = json.loads(p.read_text())
    if "log" in fields:                                   # keep the entries the daily exposure reads; only the created entry is the test's
        fields["log"] = [e for e in data.get("log") or [] if e.get("what") != "created"] + fields["log"]
    data.update(fields)
    p.write_text(json.dumps(data))


def test_the_approve_card_carries_the_request_origin_the_count_and_the_refs(svc_ui2):
    s = svc_ui2
    tp.setup(s, queue=False)
    patch_job(s, log=[{"what": "created", "via": "ui"}], refs=[ref()], conversation=[*conv("bikin dua perubahan"), {"from": "writer", "text": "w", "stage": "w1"}, *conv("balasan")])
    status, out = tp.prep(s, "prd_approve")
    c = out["card"]
    assert status == 200 and c["request_by"] == "chat" and c["request_count"] == 2 and c["refs"] == [{"name": "athena", "commit12": "a" * 12}]
    assert c["request"] == "bikin dua perubahan" and c["request_cut"] is False


def test_a_long_request_is_cut_on_the_server_at_400_code_points(svc_ui2):
    s = svc_ui2
    tp.setup(s, queue=False)
    patch_job(s, conversation=conv("😀" * 900))
    c = tp.prep(s, "prd_approve")[1]["card"]
    assert c["request_cut"] is True and c["request"] == "😀" * 400 and c["request_by"] == "tidak_tercatat"


def test_bad_refs_leave_the_card_with_a_marker_not_a_409(svc_ui2):
    s = svc_ui2
    tp.setup(s, queue=False)
    patch_job(s, refs=[ref(name="../x")])
    status, out = tp.prep(s, "prd_approve")
    assert status == 200 and out["card"]["refs"] == rb.UNREADABLE
    patch_job(s, refs="nonsense")
    assert tp.prep(s, "prd_approve")[1]["card"]["refs"] == rb.UNREADABLE


def test_the_queue_go_card_carries_the_same_fields(svc_ui2):
    s = svc_ui2
    tp.setup(s, queue=True)
    patch_job(s, refs=[ref()])                            # not via ui: a chat-made job counts in the daily cap and needs a harness id
    status, out = tp.prep_go(s, ack="1,2")
    assert status == 200, out
    c = out["card"]
    assert c["request_by"] == "tidak_tercatat" and c["refs"] == [{"name": "athena", "commit12": "a" * 12}]
    assert c["request_count"] == 1 and c["request_cut"] is False and c["request"].startswith("bikin dua perubahan")


@pytest.fixture
def svc_ui2(tp_svc):
    return tp_svc


tp_svc = tp.svc
