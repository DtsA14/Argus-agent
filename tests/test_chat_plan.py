"""SPEC_CHAT_T4A rev 1: the plan buttons of the chat, `prd_approve` and `queue_go`, and `argus queue go --via ui --reason-file`. Real files in a temporary jobs
and queues directory, a real server on a free port; the CLI is a recorder (Plan.run). No model."""
import copy
import hashlib
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_chat_actions as t  # noqa: E402
import test_chat_cards as tc  # noqa: E402
from router import chat_actions as ca  # noqa: E402
from router import chat_plan as cp  # noqa: E402
from router import job as rj  # noqa: E402
from router import prd as rp  # noqa: E402
from router import queue as rq  # noqa: E402

PJOB, QID = tc.PJOB, tc.QID
TWO = [tc.issue_text(title="One"), tc.issue_text(title="Two")]           # no example of new behaviour: both carry the machine's warning
OK_READ = ("ok", {"verdict": "ok", "reader": "r1", "reader2": "r2", "at": "2026-11-17T10:00:00Z", "sources": [], "note": "fine"})


class Svc(t.Service):
    pass


@pytest.fixture
def svc(tmp_path):
    s = t.Service(tmp_path, cfg={**copy.deepcopy(t.CFG), "chat": {"daily_cap_usd": 7.0}})
    s.queues = tmp_path / "queues"
    s.queues.mkdir()
    s.actions.cards.queues_dir = s.queues
    s.cli = []

    def fake(argv):
        s.cli.append(argv)
        if "approve" in argv:
            return 0, f"queue {QID} PENDING: 2 issues on athena, up to $2.00, from the PRD abc\napprove the list and the money: argus queue go {QID} --sha abc\n"
        return 0, "queue ok\n"
    s.actions.plans.run = fake
    yield s
    s.stop()


def setup(s, texts=TWO, queue=True, max_usd=2.0, reference=True, qkw=None, **turn):
    d, files = tc.write_prd(s.jobs, texts, [None] * len(texts), max_usd=max_usd, **turn)
    if reference:                                                         # three applied code jobs with a $1.00 cap: the usual cost is 1x
        for i, jid in enumerate(("j20261117_090000_aaa1", "j20261117_090100_aaa2", "j20261117_090200_aaa3")):
            tc.write_job(s.jobs, jid, kind="code", state="APPLIED", max_usd=1.0)
    q = None
    if queue:
        q = tc.write_queue(s, [(x, None) for x in texts], max_usd=max_usd, prd={"sha": rp.folder_sha(files), "dir": str(d / "prd-w1")}, **(qkw or {}))
    return d, files, q


def prep(s, action, **kw):
    return s.prepare(action=action, job=PJOB, **kw)


def approve_queue(s, **kw):
    """The queue as `queue go` leaves it."""
    p = s.queues / QID / "queue.json"
    q = json.loads(p.read_text())
    q["approved"] = {"sha": "x" * 64, "at": t.iso(kw.pop("at", t.NOW - 100)), **kw}
    p.write_text(json.dumps(q))


# ---- prd_approve -------------------------------------------------------------------------------------------------------------

def test_prd_approve_card_has_the_flags_first_and_runs_nothing(svc):
    setup(svc, queue=False)
    status, out = prep(svc, "prd_approve")
    assert status == 200 and svc.cli == [] and svc.spawner.calls == []
    c = out["card"]
    assert c["action"] == "prd_approve" and c["job"] == PJOB and c["folder_sha"] == json.loads((svc.jobs / PJOB / "job.json").read_text())["prd_turns"][0]["folder_sha"]
    assert len(c["flags"]) == 2 and all("no example" in f for f in c["flags"]) and out["exposure_usd"] == 0.0
    assert "no money" in c["money"] and c["request"].startswith("bikin dua perubahan")


@pytest.mark.parametrize("body", [{"queue": QID}, {"sha": "a" * 12}, {"dir": "/tmp"}, {"ack": "1"}, {"reason": "a long enough reason"}])
def test_prd_approve_takes_the_job_and_nothing_else(svc, body):
    setup(svc, queue=False)
    status, out = prep(svc, "prd_approve", **body)
    assert status == 400 and "token" not in out


@pytest.mark.parametrize("job,status", [("j20261117_100000_zzzz", 404), ("../x", 404), ("", 404)])
def test_prd_approve_of_no_such_job(svc, job, status):
    setup(svc, queue=False)
    assert svc.prepare(action="prd_approve", job=job)[0] == status


def test_prd_approve_is_refused_when_the_plan_is_not_ready(svc, tmp_path):
    setup(svc, queue=False)
    jp = svc.jobs / PJOB / "job.json"
    base = json.loads(jp.read_text())
    cases = [("state", {**base, "state": "WRITING"}), ("stale", {**base, "prd_turns": [{**base["prd_turns"][0], "commit": "d" * 40}]}),
             ("turn", {**base, "prd_turns": []}), ("money", {**base, "prd_turns": [{**base["prd_turns"][0], "max_usd": 0}]}),
             ("sha", {**base, "prd_turns": [{**base["prd_turns"][0], "folder_sha": "e" * 64}]})]
    for name, data in cases:
        jp.write_text(json.dumps(data))
        status, out = prep(svc, "prd_approve")
        assert status == 409 and "token" not in out, name
    jp.write_text(json.dumps(base))
    assert prep(svc, "prd_approve")[0] == 200
    (svc.jobs / PJOB / "prd-w1" / "SUPERSEDED").write_text("x")
    assert prep(svc, "prd_approve")[0] == 409


def test_prd_approve_is_refused_while_the_writer_works_or_a_queue_exists(svc):
    setup(svc, queue=False)
    svc.spawner.busy_ids.add(PJOB)
    assert prep(svc, "prd_approve")[0] == 409
    svc.spawner.busy_ids.clear()
    tc.write_queue(svc, [(x, None) for x in TWO], max_usd=2.0, repo="/secret/path", prd={"sha": "f" * 64, "dir": "/elsewhere"})   # another plan's queue, waiting, on this repository
    status, out = prep(svc, "prd_approve")
    assert status == 409 and "not finished" in out["refused"]
    (svc.queues / QID / "queue.json").unlink()
    setup(svc)                                                            # a queue made from this very plan
    status, out = prep(svc, "prd_approve")
    assert status == 409 and "already made" in out["refused"]


def test_prd_approve_confirm_runs_the_cli_with_the_full_sha_and_no_key(svc):
    setup(svc, queue=False)
    token = prep(svc, "prd_approve")[1]["token"]
    status, out = svc.confirm(token)
    assert status == 200 and out["queue"] == QID and out["done"] is True
    (argv,) = svc.cli
    i = argv.index("prd")
    sha = json.loads((svc.jobs / PJOB / "job.json").read_text())["prd_turns"][0]["folder_sha"]
    assert argv[i:i + 5] == ["prd", "approve", str(svc.jobs / PJOB / "prd-w1"), "--sha", sha] and len(sha) == 64
    assert "--key-file" not in argv and "--yes" not in argv and "--queues-dir" in argv
    assert svc.actions.exposure() == 0.0


def test_prd_approve_confirm_cli_refusal_is_a_409_with_a_scrubbed_line(svc):
    setup(svc, queue=False)
    svc.actions.plans.run = lambda argv: (2, "refused: BLOCK: path sk-ant-api03-" + "a" * 40 + " is bad; nothing was approved\n")
    token = prep(svc, "prd_approve")[1]["token"]
    status, out = svc.confirm(token)
    assert status == 409 and "sk-ant" not in json.dumps(out) and "executed" not in json.dumps(out)


def test_a_folder_replaced_between_card_and_confirm_is_refused(svc):
    setup(svc, queue=False)
    token = prep(svc, "prd_approve")[1]["token"]
    (svc.jobs / PJOB / "prd-w1" / "SUPERSEDED").write_text("x")
    status, out = svc.confirm(token)
    assert status == 409 and svc.cli == []


# ---- queue_go: the queue the card shows ------------------------------------------------------------------------------------------

def go_params(**kw):
    return {"ack": "1,2", "reason": None, **kw}


def prep_go(s, **kw):
    body = {"action": "queue_go", "job": PJOB, **kw}
    return s.prepare(**{k: v for k, v in body.items() if v is not None})


def test_queue_go_needs_the_queue_of_this_plan(svc):
    setup(svc, queue=False)
    status, out = prep_go(svc, ack="1,2")
    assert status == 409 and "approve the plan first" in out["refused"]
    setup(svc)
    assert prep_go(svc, ack="1,2")[0] == 200


@pytest.mark.parametrize("body", [{"queue": QID}, {"sha": "a" * 12}, {"repo": "athena"}, {"message": "x"}])
def test_queue_go_takes_no_queue_sha_or_money_from_the_client(svc, body):
    setup(svc)
    status, out = prep_go(svc, ack="1,2", **body)
    assert status == 400 and "token" not in out


def test_a_queue_from_an_older_turn_is_not_offered(svc):
    d, files, _ = setup(svc)
    jp = svc.jobs / PJOB / "job.json"
    data = json.loads(jp.read_text())
    files2 = {**files, "PRD.md": b"Goal: z.\nThe contract: y.\n"}
    f2 = d / "prd-w2"
    f2.mkdir()
    for name, raw in files2.items():
        (f2 / name).write_bytes(raw)
    (d / "prd-w1" / "SUPERSEDED").write_text("x")
    data["prd_turns"].append({**data["prd_turns"][0], "turn": "w2", "folder_sha": rp.folder_sha(files2)})
    jp.write_text(json.dumps(data))
    status, out = prep_go(svc, ack="1,2")
    assert status == 409 and "approve the plan first" in out["refused"]       # the queue is w1's: its sha is not the last turn's


def test_a_queue_that_is_not_the_plans_is_refused(svc):
    d, files, _ = setup(svc)
    qj = svc.queues / QID / "queue.json"
    q = json.loads(qj.read_text())
    for name, change in {"money": {"max_usd": 3.0}, "issues": {"items": q["items"][:1]}, "jobs dir": {"jobs_dir": "/elsewhere"}}.items():
        qj.write_text(json.dumps({**q, **change}))
        assert prep_go(svc, ack="1,2")[0] == 409, name
    qj.write_text(json.dumps(q))
    (svc.queues / QID / "issue-1.md").write_text("changed")
    status, out = prep_go(svc, ack="1,2")
    assert status == 409 and "changed" in out["refused"]


def test_a_closed_queue_is_ignored_and_an_approved_one_is_refused(svc):
    setup(svc)
    qj = svc.queues / QID / "queue.json"
    q = json.loads(qj.read_text())
    qj.write_text(json.dumps({**q, "closed": {"note": "x", "at": t.iso(t.NOW)}}))
    assert "approve the plan first" in prep_go(svc, ack="1,2")[1]["refused"]
    qj.write_text(json.dumps(q))
    approve_queue(svc)
    assert "already approved" in prep_go(svc, ack="1,2")[1]["refused"]


def test_two_queues_from_one_plan_are_refused(svc):
    d, files, _ = setup(svc)
    other = svc.queues / "q20261117T100500Z-abce"
    other.mkdir()
    for n, x in enumerate(TWO, 1):
        (other / f"issue-{n}.md").write_text(x)
    q = json.loads((svc.queues / QID / "queue.json").read_text())
    (other / "queue.json").write_text(json.dumps({**q, "id": other.name}))
    status, out = prep_go(svc, ack="1,2")
    assert status == 409 and "more than one" in out["refused"]


# ---- the machine's refusals: M8, the acknowledgement, the cost, the reason ----------------------------------------------------------

def test_the_numbers_need_two_agreeing_readings(svc, monkeypatch):
    from router import examples_read as er
    texts = [tc.issue_text(tc.SAME, tc.AFTER, title="One"), tc.issue_text(title="Two")]
    d, files = tc.write_prd(svc.jobs, texts, [tc.stored_for([tc.SAME, tc.AFTER]), None], max_usd=2.0)
    tc.write_queue(svc, [(x, None) for x in texts], max_usd=2.0, prd={"sha": rp.folder_sha(files), "dir": str(d / "prd-w1")})
    for kind in ("none", "one", "stale", "error", "concerns"):
        monkeypatch.setattr(er, "status", lambda *a, kind=kind: (kind, {"verdict": kind, "reader": "r", "at": "x", "sources": [], "note": ""}))
        status, out = prep_go(svc, ack="2", reason="the cost is as expected, checked")
        assert status == 409 and "two agreeing readings" in out["refused"], kind
    monkeypatch.setattr(er, "status", lambda *a: OK_READ)
    assert prep_go(svc, ack="2", reason="the cost is as expected, checked")[0] == 200


def test_the_acknowledgement_is_the_exact_set_of_items_without_a_new_example(svc):
    setup(svc)
    for ack in (None, "", "1", "2", "1,2,3", "2,1", "1;2"):
        status, out = prep_go(svc, ack=ack)
        assert status == 409, ack
    assert prep_go(svc, ack="1,2")[0] == 200


def test_an_acknowledgement_for_nothing_is_a_400(svc, monkeypatch):
    from router import examples_read as er
    texts = [tc.issue_text(tc.SAME, tc.AFTER, title="One")]
    d, files = tc.write_prd(svc.jobs, texts, [tc.stored_for([tc.SAME, tc.AFTER])], max_usd=1.0)
    for jid in ("j20261117_090000_aaa1", "j20261117_090100_aaa2", "j20261117_090200_aaa3"):
        tc.write_job(svc.jobs, jid, kind="code", state="APPLIED", max_usd=1.0)
    tc.write_queue(svc, [(texts[0], None)], max_usd=1.0, prd={"sha": rp.folder_sha(files), "dir": str(d / "prd-w1")})
    monkeypatch.setattr(er, "status", lambda *a: OK_READ)
    status, out = prep_go(svc, ack="1")
    assert status == 400
    assert prep_go(svc)[0] == 200


def test_a_cost_far_above_the_reference_or_without_one_needs_a_typed_reason(svc):
    setup(svc, texts=TWO[:1], max_usd=5.0)                                # 5.00 for 1 issue: 5x the usual 1.00
    status, out = prep_go(svc, ack="1")
    assert status == 409 and "type why" in out["refused"]
    for bad in ("short", "x" * 501, "key sk-ant-api03-" + "a" * 40 + " here", "tab\there is a long reason"):
        assert prep_go(svc, ack="1", reason=bad)[0] == 400, bad
    status, out = prep_go(svc, ack="1", reason="the owner asked for the larger queue")
    assert status == 200 and out["card"]["reason"] == "the owner asked for the larger queue" and any("cost" in f for f in out["card"]["flags"])


def test_no_reference_means_a_reason_is_required(svc):
    setup(svc, reference=False)
    assert prep_go(svc, ack="1,2")[0] == 409
    assert prep_go(svc, ack="1,2", reason="no reference yet, the first plans")[0] == 200


def test_a_reason_for_a_card_that_needs_none_is_a_400(svc):
    setup(svc)                                                            # 2.00 for 2 issues against 1.00: the usual cost
    assert prep_go(svc, ack="1,2", reason="not needed at all here")[0] == 400


def test_the_ratio_threshold_is_three_on_the_rounded_value(svc):
    setup(svc, max_usd=5.0)
    assert prep_go(svc, ack="1,2")[0] == 200                              # 5.00 for 2 issues: 2.5x, below three: no reason
    assert cp.RATIO_REASON == 3.0
    setup(svc, texts=TWO[:1], max_usd=3.0)                                # exactly 3.0x: asks for a reason
    assert prep_go(svc, ack="1")[0] == 409
    setup(svc, texts=TWO[:1], max_usd=2.9)
    assert prep_go(svc, ack="1")[0] == 200


# ---- queue_go: confirm, argv, audit -------------------------------------------------------------------------------------------------

def test_queue_go_runs_the_cli_with_the_full_list_sha_via_ui_and_no_key(svc):
    setup(svc)
    out = prep_go(svc, ack="1,2")[1]
    status, done = svc.confirm(out["token"])
    assert status == 200 and done["queue"] == QID
    (argv,) = svc.cli
    q = json.loads((svc.queues / QID / "queue.json").read_text())
    i = argv.index("queue")
    assert argv[i:i + 6] == ["queue", "go", QID, "--sha", rq.list_sha(q), "--via"] and argv[i + 6] == "ui" and len(rq.list_sha(q)) == 64
    assert "--key-file" not in argv and "--yes" not in argv and "--reason-file" not in argv


def test_the_reason_goes_to_the_cli_in_a_file_that_is_removed_and_the_audit_holds_only_its_hash(svc):
    setup(svc, texts=TWO[:1], max_usd=5.0)
    reason = "the owner asked for the larger queue"
    token = prep_go(svc, ack="1", reason=reason)[1]["token"]
    seen = {}

    def run(argv):
        j = argv.index("--reason-file")
        seen["file"] = Path(argv[j + 1])
        seen["text"] = seen["file"].read_text()
        return 0, "queue ok\n"
    svc.actions.plans.run = run
    assert svc.confirm(token)[0] == 200
    assert seen["text"] == reason and not seen["file"].exists()
    audit = (svc.actions.audit_path).read_text()
    assert reason not in audit and hashlib.sha256(reason.encode()).hexdigest() in audit
    lines = [json.loads(x) for x in audit.splitlines()]
    done = [x for x in lines if x.get("ok") == "confirm"][-1]
    assert done["action"] == "queue_go" and done["queue"] == QID and done["usd"] == 5.0


def test_a_cli_refusal_of_queue_go_is_a_409_and_counts_nothing_as_run(svc):
    setup(svc)
    token = prep_go(svc, ack="1,2")[1]["token"]
    svc.actions.plans.run = lambda argv: (2, f"refused: the list is abc, not the 'x' given; nothing was approved\n")
    status, out = svc.confirm(token)
    assert status == 409 and svc.actions.pending == []


def test_a_queue_approved_between_card_and_confirm_is_refused(svc):
    setup(svc)
    token = prep_go(svc, ack="1,2")[1]["token"]
    approve_queue(svc)
    assert svc.confirm(token)[0] == 409 and svc.cli == []


def test_the_card_changes_when_the_config_money_or_issues_change(svc):
    setup(svc)
    token = prep_go(svc, ack="1,2")[1]["token"]
    qj = svc.queues / QID / "queue.json"
    q = json.loads(qj.read_text())
    qj.write_text(json.dumps({**q, "job_cap_usd": 0.75}))
    assert svc.confirm(token)[0] == 409 and svc.cli == []


# ---- the daily cap ---------------------------------------------------------------------------------------------------------------------

def test_an_approved_queue_via_ui_counts_its_max_usd_inside_24_hours(svc):
    setup(svc)
    approve_queue(svc, via="ui")
    assert svc.actions.exposure() == pytest.approx(2.0)


def test_a_terminal_approval_a_late_one_and_no_approval_do_not_count_but_a_closed_queue_does(svc):
    setup(svc)
    approve_queue(svc)                                                    # no via: a terminal
    assert svc.actions.exposure() == 0.0
    approve_queue(svc, via="ui", at=t.NOW - 3600 * 30)                    # outside the window
    assert svc.actions.exposure() == 0.0
    approve_queue(svc, via="ui")
    qj = svc.queues / QID / "queue.json"
    q = json.loads(qj.read_text())
    qj.write_text(json.dumps({**q, "closed": {"note": "x", "at": t.iso(t.NOW)}}))
    assert svc.actions.exposure() == pytest.approx(2.0)


def test_a_damaged_queue_or_an_unreadable_approval_time_means_unknown(svc):
    setup(svc)
    (svc.queues / QID / "queue.json").write_text("{not json")
    with pytest.raises(ca.Refusal) as e:
        svc.actions.exposure()
    assert e.value.status == 503
    setup(svc)
    approve_queue(svc, via="ui", at=None)
    q = json.loads((svc.queues / QID / "queue.json").read_text())
    q["approved"]["at"] = "yesterday-ish"
    (svc.queues / QID / "queue.json").write_text(json.dumps(q))
    with pytest.raises(ca.Refusal):
        svc.actions.exposure()


def test_the_audit_net_counts_a_confirmed_queue_whose_via_is_missing_and_never_twice(svc):
    setup(svc)
    token = prep_go(svc, ack="1,2")[1]["token"]
    assert svc.confirm(token)[0] == 200
    svc.actions.pending.clear()                                           # what a restart forgets
    approve_queue(svc)                                                    # the CLI approved it but lost its via
    assert svc.actions.exposure() == pytest.approx(2.0)
    approve_queue(svc, via="ui")                                          # now the directory shows it: still counted once
    assert svc.actions.exposure() == pytest.approx(2.0)


def test_a_queue_is_refused_when_the_cap_would_be_passed_and_two_confirms_cannot_beat_it(tmp_path):
    s = t.Service(tmp_path, cfg={**copy.deepcopy(t.CFG), "chat": {"daily_cap_usd": 3.0}})
    try:
        s.queues = tmp_path / "queues"
        s.queues.mkdir()
        s.actions.cards.queues_dir = s.queues
        s.actions.plans.run = lambda argv: (0, "ok\n")
        setup(s)
        token = prep_go(s, ack="1,2")[1]["token"]
        assert prep_go(s, ack="1,2")[0] == 200
        assert s.confirm(token)[0] == 200
        assert s.actions.exposure() == pytest.approx(2.0)                  # counted from the confirm (pending), before the CLI showed anything
        with pytest.raises(ca.Refusal) as e:                               # a second queue of 2.0 would pass 3.0
            s.actions.check_cap({"action": "queue_go", "queue_usd": 2.0})
        assert e.value.status == 403
    finally:
        s.stop()


def test_the_page_state_offers_what_prepare_would_let_through(svc):
    setup(svc, queue=False)
    status, card = svc.request("GET", f"/api/approve/prd/{PJOB}")
    assert status == 200 and card["t4"]["action"] == "prd_approve"
    setup(svc)
    status, card = svc.request("GET", f"/api/approve/prd/{PJOB}")
    assert card["t4"]["action"] == "queue_go" and card["t4"]["needs"] == ["ack"]
    (svc.jobs / PJOB / "prd-w1" / "SUPERSEDED").write_text("x")
    assert svc.request("GET", f"/api/approve/prd/{PJOB}")[1]["t4"]["action"] is None


# ---- the CLI: queue go --via --reason-file ---------------------------------------------------------------------------------------------

def make_queue_for_cli(tmp_path):
    queues = tmp_path / "q"
    queues.mkdir()
    d = queues / QID
    d.mkdir()
    texts = ["Issue one is here and it is long enough"]
    (d / "issue-1.md").write_text(texts[0])
    q = {"id": QID, "repo": str(tmp_path), "name": "demo", "base_commit": "c" * 40, "jobs_dir": str(tmp_path / "jobs"), "max_usd": 1.0, "job_cap_usd": 1.0,
         "environment": "e", "items": [{"n": 1, "issue_sha256": hashlib.sha256(texts[0].encode()).hexdigest(), "job": None}]}
    (d / "queue.json").write_text(json.dumps(q))
    return queues, q


def deps():
    return rj.Deps(confirm=lambda x: True, get_key=lambda: "k", isatty=lambda: True, models={}, clock=lambda: "2026-11-21T12:00:00Z", echo=lambda s: None)


def test_queue_go_via_and_reason_are_stored_with_the_approval(tmp_path):
    queues, q = make_queue_for_cli(tmp_path)
    got = rq.go(QID, sha=rq.list_sha(q), deps=deps(), queues_dir=queues, via="ui", reason="  The owner accepts this cost.  ")
    assert got["approved"]["via"] == "ui" and got["approved"]["reason"] == "The owner accepts this cost." and got["approved"]["at"] == "2026-11-21T12:00:00Z"


def test_queue_go_without_via_or_reason_stores_neither(tmp_path):
    queues, q = make_queue_for_cli(tmp_path)
    got = rq.go(QID, sha=rq.list_sha(q), deps=deps(), queues_dir=queues)
    assert "via" not in got["approved"] and "reason" not in got["approved"]


@pytest.mark.parametrize("kw", [{"via": "elsewhere"}, {"reason": "short"}, {"reason": "key sk-ant-api03-" + "a" * 40 + " here"}, {"reason": "x" * 501},
                                {"reason": "tab\tcharacter in a long reason"}])
def test_a_bad_via_or_reason_approves_nothing(tmp_path, kw):
    queues, q = make_queue_for_cli(tmp_path)
    with pytest.raises(rq.Refused):
        rq.go(QID, sha=rq.list_sha(q), deps=deps(), queues_dir=queues, **kw)
    assert "approved" not in json.loads((queues / QID / "queue.json").read_text())


def test_the_cli_passes_via_and_the_reason_to_queue_go_and_refuses_a_key_file(monkeypatch, tmp_path):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
    import argus
    seen = {}
    monkeypatch.setattr(rq, "go", lambda qid, **kw: seen.update(kw) or {"id": QID})
    monkeypatch.setattr(rq, "status", lambda *a, **k: "status")
    f = tmp_path / "reason.txt"
    f.write_text("a reason that is long enough")
    base = ["--queues-dir", str(tmp_path), "queue", "go", QID, "--sha", "a" * 12]
    assert argus.main([*base, "--via", "ui", "--reason-file", str(f)]) == 0
    assert seen["via"] == "ui" and seen["reason"] == "a reason that is long enough"
    seen.clear()
    assert argus.main(base) == 0 and seen["via"] is None and seen["reason"] is None
    with pytest.raises(SystemExit) as e:
        argus.main([*base, "--key-file", "k"])
    assert e.value.code == 2


def test_the_reason_rule_is_one_rule_for_apply_and_queue_go():
    from router import apply as ap
    from router import reason as r
    for text in ("short", "x" * 501, "tab\there is long enough", "key sk-ant-api03-" + "a" * 40 + " is here"):
        with pytest.raises(rj.Refused):
            ap._accepted_reason(text)
        with pytest.raises(rj.Refused):
            r.check(text, "x")
    assert ap._accepted_reason("a perfectly good reason") == r.check("a perfectly good reason", "x")


def test_the_real_config_funds_a_prd_and_its_queue_in_one_day():
    from runner import load_config
    cfg = load_config(Path(__file__).resolve().parent.parent / "config.yaml")
    assert cfg["chat"]["daily_cap_usd"] >= float(cfg["prd_writer"]["max_usd"]) + rq.QUEUE_MAX_USD


# ---- review changes (Opus, 2026-11-21) ------------------------------------------------------------------------------------------------

def test_prd_approve_never_runs_git_to_find_an_unfinished_queue(svc, monkeypatch):
    from acceptance import intake
    setup(svc, queue=False)

    def boom(*a, **k):
        raise AssertionError("prepare ran git")
    monkeypatch.setattr(intake, "git", boom)
    tc.write_queue(svc, [(x, None) for x in TWO], max_usd=2.0, repo="/secret/path", approved={"sha": "x" * 64, "at": t.iso(t.NOW - 100)},
                   prd={"sha": "f" * 64, "dir": "/elsewhere"})              # approved, its next item has no job: `rq.derive` would run git for HEAD
    status, out = prep(svc, "prd_approve")
    assert status == 409 and "not finished" in out["refused"]
    assert svc.request("GET", f"/api/approve/prd/{PJOB}")[0] == 200


@pytest.mark.parametrize("state,busy", [("WRITING", False), ("WRITE_FAILED", False), ("AWAITING_HUMAN", True), ("ABANDONED", False)])
def test_queue_go_is_refused_while_the_plan_is_being_rewritten(svc, state, busy):
    setup(svc)
    jp = svc.jobs / PJOB / "job.json"
    data = json.loads(jp.read_text())
    jp.write_text(json.dumps({**data, "state": state}))
    if busy:
        svc.spawner.busy_ids.add(PJOB)
    status, out = prep_go(svc, ack="1,2")
    assert status == 409 and "token" not in out


def test_an_old_queue_approved_inside_the_window_counts_without_any_audit_line(svc):
    d, files, _ = setup(svc)
    old = svc.queues / "q20261110T100000Z-abcd"
    (svc.queues / QID).rename(old)
    q = json.loads((old / "queue.json").read_text())
    q["id"] = old.name
    q["approved"] = {"sha": "x" * 64, "at": t.iso(t.NOW - 100), "via": "ui"}
    (old / "queue.json").write_text(json.dumps(q))
    assert svc.actions.exposure() == pytest.approx(2.0)                   # named five days ago, approved a minute ago


@pytest.mark.parametrize("how", ["broken_block", "withheld"])
def test_examples_that_cannot_be_read_refuse_whatever_is_acknowledged(svc, how):
    texts = [tc.issue_text(tc.SAME, tc.AFTER, title="One").replace("```argus-examples", "```argus-examples json")] if how == "broken_block" else \
            [tc.issue_text({**tc.SAME, "setup": "from src.shop import total; k1 = 'sk-ant-'", "run": "'abcdefghij1234' and total([2, 3], 1)"}, title="One")]
    d, files = tc.write_prd(svc.jobs, texts, [tc.stored_for([tc.SAME])], max_usd=1.0)
    for jid in ("j20261117_090000_aaa1", "j20261117_090100_aaa2", "j20261117_090200_aaa3"):
        tc.write_job(svc.jobs, jid, kind="code", state="APPLIED", max_usd=1.0)
    tc.write_queue(svc, [(texts[0], None)], max_usd=1.0, prd={"sha": rp.folder_sha(files), "dir": str(d / "prd-w1")})
    status, out = prep_go(svc, ack="1")
    assert status == 409 and "cannot be read" in out["refused"]
    status, out = prep_go(svc)
    assert status == 409 and "cannot be read" in out["refused"]


def test_a_queue_with_the_right_sha_in_the_wrong_directory_is_refused(svc):
    setup(svc)
    qj = svc.queues / QID / "queue.json"
    q = json.loads(qj.read_text())
    qj.write_text(json.dumps({**q, "prd": {**q["prd"], "dir": str(svc.jobs / "elsewhere" / "prd-w1")}}))
    assert "approve the plan first" in prep_go(svc, ack="1,2")[1]["refused"]


def test_the_digest_holds_the_full_list_sha_and_the_queue_base_commit(svc):
    setup(svc)
    token = prep_go(svc, ack="1,2")[1]["token"]
    qj = svc.queues / QID / "queue.json"
    q = json.loads(qj.read_text())
    qj.write_text(json.dumps({**q, "base_commit": "d" * 40}))
    assert svc.confirm(token)[0] == 409 and svc.cli == []
    qj.write_text(json.dumps(q))
    token = prep_go(svc, ack="1,2")[1]["token"]
    qj.write_text(json.dumps({**q, "environment": "other_env"}))              # list_sha covers the environment: the card changed
    assert svc.confirm(token)[0] == 409 and svc.cli == []


def test_a_prd_approve_refusal_runs_nothing_and_the_audit_says_so(svc):
    setup(svc, queue=False)
    svc.actions.plans.run = lambda argv: (2, "refused: nothing was approved\n")
    token = prep(svc, "prd_approve")[1]["token"]
    assert svc.confirm(token)[0] == 409
    lines = [json.loads(x) for x in svc.actions.audit_path.read_text().splitlines()]
    assert not [x for x in lines if x.get("ok") == "confirm" and x.get("action") == "prd_approve"]
    assert [x for x in lines if x.get("attempt") == "confirm"]


def test_the_cli_refusal_of_queue_go_is_scrubbed(svc):
    setup(svc)
    token = prep_go(svc, ack="1,2")[1]["token"]
    svc.actions.plans.run = lambda argv: (2, "refused: the list sk-ant-api03-" + "a" * 40 + " is not the one\n")
    status, out = svc.confirm(token)
    assert status == 409 and "sk-ant" not in json.dumps(out)


def test_a_timed_out_queue_go_still_counts_its_money_as_pending(svc):
    setup(svc)
    token = prep_go(svc, ack="1,2")[1]["token"]
    svc.actions.plans.run = lambda argv: (None, "")
    assert svc.confirm(token)[0] == 409
    assert svc.actions.exposure() == pytest.approx(2.0)


def test_the_page_state_names_both_inputs_when_both_are_needed_and_the_cap(svc):
    setup(svc, texts=TWO[:1], max_usd=5.0)
    card = svc.request("GET", f"/api/approve/prd/{PJOB}")[1]
    assert card["t4"] == {"action": "queue_go", "why": None, "needs": ["ack", "reason"], "ack_items": [1]}
    svc.actions._cfg["chat"]["daily_cap_usd"] = 1.0                      # 5.00 would pass the cap: no button
    card = svc.request("GET", f"/api/approve/prd/{PJOB}")[1]
    assert card["t4"]["action"] is None and "daily cap" in card["t4"]["why"]


def test_the_page_state_survives_a_queue_file_without_the_shape_the_builders_read(svc):
    setup(svc)
    qj = svc.queues / QID / "queue.json"
    q = json.loads(qj.read_text())
    del q["environment"]                                                 # shape_ok does not require it, list_sha does
    qj.write_text(json.dumps(q))
    status, card = svc.request("GET", f"/api/approve/prd/{PJOB}")
    assert status == 200 and card["t4"]["action"] is None


def test_an_unreadable_queue_means_unknown_exposure_and_names_it(svc):
    setup(svc)
    approve_queue(svc, via="ui")
    qj = svc.queues / QID / "queue.json"
    q = json.loads(qj.read_text())
    for bad in (float("nan"), -5.0, "x"):
        qj.write_text(json.dumps({**q, "max_usd": bad}) if bad == bad else json.dumps({**q, "max_usd": 1}).replace("1", "NaN", 1))
        with pytest.raises(ca.Refusal) as e:
            svc.actions.exposure()
        assert e.value.status == 503 and QID in e.value.why


def test_two_real_queue_go_confirms_in_a_row_cannot_beat_the_cap(tmp_path):
    s = t.Service(tmp_path, cfg={**copy.deepcopy(t.CFG), "chat": {"daily_cap_usd": 3.0}})
    try:
        s.queues = tmp_path / "queues"
        s.queues.mkdir()
        s.actions.cards.queues_dir = s.queues
        s.actions.plans.run = lambda argv: (0, "ok\n")
        setup(s)
        a = prep_go(s, ack="1,2")[1]["token"]
        b = prep_go(s, ack="1,2")[1]["token"]                              # both prepared before either confirm: 2.0 each against 3.0
        assert s.confirm(a)[0] == 200
        status, out = s.confirm(b)
        assert status in (403, 409)
    finally:
        s.stop()


def test_the_reason_file_must_be_utf8_text_of_four_kilobytes_at_most(tmp_path):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
    import argus
    f = tmp_path / "r.txt"
    f.write_bytes(b"\xff\xfe not text at all, but long enough")
    with pytest.raises(rj.Refused):
        argus._read_reason_file(str(f))
    f.write_bytes(b"x" * 5000)
    with pytest.raises(rj.Refused):
        argus._read_reason_file(str(f))
    f.write_text("a reason that is long enough")
    assert argus._read_reason_file(str(f)) == "a reason that is long enough"


# ---- mutant survivors ---------------------------------------------------------------------------------------------------------------

def test_a_confirmed_queue_go_counts_from_pending_even_without_an_audit_line(svc):
    setup(svc)
    token = prep_go(svc, ack="1,2")[1]["token"]
    assert svc.confirm(token)[0] == 200
    svc.actions.audit_path.rename(svc.actions.audit_path.with_suffix(".gone"))     # the net is gone: only the pending list is left
    assert svc.actions.exposure() == pytest.approx(2.0)


def test_a_refused_queue_go_leaves_no_exposure_though_its_attempt_line_is_in_the_audit(svc):
    setup(svc)
    token = prep_go(svc, ack="1,2")[1]["token"]
    svc.actions.plans.run = lambda argv: (2, "refused: nothing was approved\n")
    assert svc.confirm(token)[0] == 409
    lines = [json.loads(x) for x in svc.actions.audit_path.read_text().splitlines()]
    assert [x for x in lines if x.get("attempt") == "confirm" and x.get("queue") == QID]        # the attempt is written before the run, with the queue
    assert svc.actions.exposure() == 0.0                                  # but only an `ok` line counts


def test_the_page_state_never_raises_whatever_a_builder_hits(svc, monkeypatch):
    setup(svc)

    def boom(job_id):
        raise KeyError("shape")
    monkeypatch.setattr(svc.actions.plans, "go_facts", boom)
    monkeypatch.setattr(svc.actions.plans, "build_approve", lambda params: (_ for _ in ()).throw(TypeError("shape")))
    status, card = svc.request("GET", f"/api/approve/prd/{PJOB}")
    assert status == 200 and card["t4"]["action"] is None
