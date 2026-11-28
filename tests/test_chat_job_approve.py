"""SPEC_CHAT_JOB_APPROVE rev 1: `job_approve`, the draft approval of a standalone code job from the chat. Real files, a real server, the spawner is a recorder."""
import hashlib
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_chat_actions as t  # noqa: E402
import test_chat_cards as tc  # noqa: E402
import test_chat_t4b as t4  # noqa: E402
from router import chat_actions as ca  # noqa: E402
from router import job as rj  # noqa: E402

svc = t4.svc
J1, TEXT, QID = t4.J1, t4.TEXT, t4.QID
GOLDEN_CARD = {"action": "draft_approve", "agent_cap_usd": 0.5, "agent_max_usd_config": 0.5, "attempt_usd": 0.018, "changed_tests": [], "changed_tests_n": 0,
               "draft_run": "d1-run", "flags": ["budget profile: default"], "item": 1, "job": J1,
               "item_text": "One\n\nA discount larger than the sum gives 0.\n\nNothing else changes: x\n\nTests: y\n\nEnvironment: pyenv",
               "money": "the agent runs inside the job cap the queue already holds; no new money. Tests and the contract are the drafter's (a model's), shown as it wrote them. The command re-checks the draft in the sandbox (`dr.check`) and the repository's HEAD; this card does not",
               "profile": "default", "queue": QID, "repo": "athena", "retry": False, "summary_note": "summary unavailable", "title": "Approve the draft (the agent starts)",
               "validations": [{"id": "v1", "must_pass": ["tests/test_a.py::test_x"]}], "writable": ["src/a.py", "tests/test_a.py"]}


def card_of(out):
    return json.dumps(out["card"], sort_keys=True)


def test_the_draft_approve_card_of_a_queue_item_is_unchanged_by_the_refactor(svc):
    t4.queue(svc, jobs=(J1, None))
    t4.awaiting(svc, J1, TEXT)
    status, out = t4.prep(svc, "draft_approve")
    assert status == 200
    c = {k: v for k, v in out["card"].items() if k not in ("list_sha", "approved_sha", "draft_sha")}
    assert c == GOLDEN_CARD and out["card"]["draft_sha"] == rj.draft_sha_of(t4.draft())


# ---- the action -----------------------------------------------------------------------------------------------------------------------

import copy  # noqa: E402

DAYS = 86400
ISSUE_JOB = "j20261115_222000_bbb1"


def standalone(s, job_id=J1, booked=True, at=None, **kw):
    """A code job in AWAITING_APPROVAL that is in no queue; booked: the issue job whose handoff made it, via the UI, 10 minutes ago (what the daily cap books)."""
    t4.awaiting(s, job_id, TEXT, **kw)
    if booked:
        t.make_issue(s.jobs, ISSUE_JOB, state="HANDED_OFF", handoff={"job": job_id, "at": t.iso(t.NOW - 600 if at is None else at), "via": "ui"})


def sha12(s, job_id=J1):
    return rj.draft_sha_of(json.loads((s.jobs / job_id / "runs" / "d1-run" / "draft.json").read_text()))[:12]


def approve(s, job_id=J1, **kw):
    return s.prepare(action="job_approve", job=job_id, sha=kw.pop("sha", sha12(s, job_id)), **kw)


def full_sha():
    return rj.draft_sha_of(t4.draft())


def test_a_standalone_job_gets_a_card_without_queue_fields_and_nothing_runs(svc):
    standalone(svc)
    status, out = approve(svc)
    c = out["card"]
    assert status == 200 and svc.spawner.calls == [] and out["exposure_usd"] == 0.0
    assert c["action"] == "job_approve" and c["job"] == J1 and c["sha12"] == full_sha()[:12] and c["draft_sha"] == full_sha() and c["outside_window"] is False
    assert not ({"queue", "item", "list_sha", "approved_sha"} & set(c))
    assert c["writable"] == ["src/a.py", "tests/test_a.py"] and c["validations"][0]["must_pass"] == ["tests/test_a.py::test_x"]
    assert c["agent_cap_usd"] > 0 and c["attempt_usd"] > 0 and "One" in c["item_text"] and "Nothing is applied" in c["money"]


def test_the_confirm_spawns_exactly_the_fixed_argv_keyed_by_the_job_and_audits_without_text(svc):
    standalone(svc)
    token = approve(svc)[1]["token"]
    status, out = svc.confirm(token)
    assert status == 200 and out == {"job": J1, "started": True}
    (call,) = svc.spawner.calls
    argv = call["argv"]
    i = argv.index("approve")
    assert call["job"] == J1 and call["action"] == "job_approve"
    assert argv[i:] == ["approve", J1, "--sha", full_sha(), "--via", "ui", "--key-file", t.KEY, "--yes"]
    assert "--queues-dir" in argv[:i] and "--jobs-dir" in argv[:i]
    for bad in ("--max-usd", "--web", "--reference-patch", "--max-iterations"):
        assert bad not in argv
    (rec,) = t4.audit_confirms(svc, "job_approve")
    assert rec["usd"] == 0.0 and rec["sha"] == full_sha()[:12] and rec["job"] == J1
    assert "One" not in svc.actions.audit_path.read_text()


def test_the_config_of_the_chat_is_passed_to_the_command(svc):
    standalone(svc)
    svc.actions.config_path = "/etc/argus-test.yaml"
    svc.confirm(approve(svc)[1]["token"])
    argv = svc.spawner.calls[0]["argv"]
    assert argv[argv.index("--config") + 1] == "/etc/argus-test.yaml" and argv.index("--config") < argv.index("approve")


@pytest.mark.parametrize("extra", [{"queue": t4.QID}, {"reason": "a long enough reason"}, {"message": "x"}, {"item": "1"}])
def test_the_approval_takes_the_job_and_the_sha_and_nothing_else(svc, extra):
    standalone(svc)
    status, out = approve(svc, **extra)
    assert status == 400 and "token" not in out and svc.spawner.calls == []


def test_a_missing_or_malformed_sha_is_refused(svc):
    standalone(svc)
    assert svc.prepare(action="job_approve", job=J1)[0] == 400
    for bad in ("", "abc", "G" * 12, "a" * 13, full_sha()):
        assert svc.prepare(action="job_approve", job=J1, sha=bad)[0] == 400


def test_a_draft_that_is_not_the_one_the_person_read_is_refused(svc):
    standalone(svc)
    status, out = approve(svc, sha="0" * 12)
    assert status == 409 and "changed since you read it" in out["refused"] and "token" not in out


def test_a_draft_that_changed_between_prepare_and_confirm_is_not_approved(svc):
    standalone(svc)
    token = approve(svc)[1]["token"]
    run = svc.jobs / J1 / "runs" / "d1-run" / "draft.json"
    d = t4.draft()
    d["contract"]["scope"]["writable"] = ["src/other.py"]
    run.write_text(json.dumps(d))
    status, _ = svc.confirm(token)
    assert status == 409 and svc.spawner.calls == []


def test_no_such_job_or_not_an_id(svc):
    standalone(svc)
    for job in ("j20261109_120000_ffff", "jfoo", "..", J1 + "\n"):
        assert svc.prepare(action="job_approve", job=job, sha="a" * 12)[0] in (404, 400)


@pytest.mark.parametrize("kind", ["issue", "research", "prd"])
def test_only_a_code_job_is_approved_here(svc, kind):
    standalone(svc)
    p = svc.jobs / J1 / "job.json"
    d = json.loads(p.read_text())
    d["kind"] = kind
    p.write_text(json.dumps(d))
    status, out = approve(svc)
    assert status == 409 and out.get("gate", "kind") and "token" not in out and svc.spawner.calls == []


@pytest.mark.parametrize("state", ["DRAFT_FAILED", "REVIEW_READY", "AGENT_RUNNING", "REJECTED", "APPLIED"])
def test_only_a_job_that_waits_for_approval_is_approved(svc, state):
    standalone(svc, state=state)
    assert approve(svc)[0] == 409 and svc.spawner.calls == []


def test_an_item_of_a_queue_is_not_approved_here(svc):
    t4.queue(svc, jobs=(J1, None))
    t4.awaiting(svc, J1, TEXT)
    status, out = approve(svc)
    assert status == 409 and "queue" in out["refused"] and "token" not in out


def test_a_queue_that_names_the_job_but_cannot_be_used_refuses(svc):
    d = t4.queue(svc, jobs=(J1, None))
    (d / "queue.json").write_text("{" + J1)                    # damaged, but it names the job
    t4.awaiting(svc, J1, TEXT)
    assert approve(svc)[0] == 409


def test_a_queues_directory_that_cannot_be_opened_is_not_standalone(svc, monkeypatch):
    standalone(svc)
    from router import cards
    monkeypatch.setattr(cards.Cards, "_queues_fd", lambda self: None)
    assert approve(svc)[0] == 409 and svc.spawner.calls == []


def test_a_job_is_refused_while_a_run_of_this_service_works_on_it(svc):
    standalone(svc)
    svc.spawner.busy_ids.add(J1)
    assert approve(svc)[0] == 409


def test_the_approval_needs_the_code_key(tmp_path):
    s = t.Service(tmp_path, cfg=t4.make_cfg(), environ={})
    s.queues = tmp_path / "queues"
    s.queues.mkdir()
    s.actions.cards.queues_dir = s.queues
    try:
        standalone(s)
        status, out = approve(s)
        assert status == 409 and "is not set" in out["refused"]
    finally:
        s.stop()


def test_a_draft_already_approved_is_refused(svc):
    standalone(svc, approval={"draft_sha256": full_sha(), "at": "t", "by": "x"})
    assert approve(svc)[0] == 409


def test_an_approval_that_would_block_the_job_is_refused(svc):
    standalone(svc, stage_usd=0.0)
    p = svc.jobs / J1 / "job.json"
    data = json.loads(p.read_text())
    data["max_usd"] = 0.0001                                   # less than one attempt is left
    p.write_text(json.dumps(data))
    status, out = approve(svc)
    assert status == 409 and "approving would block the job" in out["refused"]


def test_a_job_reached_through_a_link_is_refused(svc, tmp_path):
    standalone(svc)
    real = svc.jobs / J1
    moved = tmp_path / "elsewhere"
    real.rename(moved)
    real.symlink_to(moved)
    assert approve(svc)[0] in (404, 409) and svc.spawner.calls == []


# ---- the money ------------------------------------------------------------------------------------------------------------------------

def test_a_start_the_cap_still_books_adds_nothing(svc):
    standalone(svc)
    before = svc.actions.exposure()                                   # the handoff's booking: the code cap of the writer, counted once already
    out = approve(svc)[1]
    svc.confirm(out["token"])
    assert out["card"]["outside_window"] is False and before > 0 and svc.actions.exposure() == before


def test_a_job_born_in_the_terminal_counts_the_agent_cap(svc):
    standalone(svc, booked=False)
    status, out = approve(svc)
    c = out["card"]
    assert status == 200 and c["outside_window"] is True and out["exposure_usd"] == c["agent_cap_usd"] > 0
    before = svc.actions.exposure()
    svc.confirm(out["token"])
    assert svc.actions.exposure() == pytest.approx(before + c["agent_cap_usd"])
    (rec,) = t4.audit_confirms(svc, "job_approve")
    assert rec["usd"] == c["agent_cap_usd"]


@pytest.mark.parametrize("handoff", [
    {"job": "j20261115_100001_aaaa", "at": t.iso(t.NOW - 600), "via": "ui"},          # another job
    {"job": J1, "at": t.iso(t.NOW - 600), "via": "cli"},                              # from the terminal
    {"job": J1, "at": t.iso(t.NOW - DAYS - 60), "via": "ui"},                         # older than 24 hours
])
def test_a_handoff_that_does_not_book_this_job_leaves_it_outside(svc, handoff):
    t4.awaiting(svc, J1, TEXT)
    t.make_issue(svc.jobs, ISSUE_JOB, state="HANDED_OFF", handoff=handoff)
    assert approve(svc)[1]["card"]["outside_window"] is True


def test_the_window_closing_between_prepare_and_confirm_changes_the_card(svc):
    standalone(svc, at=t.NOW - DAYS + 5)
    token = approve(svc)[1]["token"]
    svc.clock.t += 10
    status, _ = svc.confirm(token)
    assert status == 409 and svc.spawner.calls == []


def test_an_outside_approval_is_refused_when_the_daily_cap_would_pass(tmp_path):
    s = t.Service(tmp_path, cfg=t4.make_cfg(daily_cap_usd=0.1))
    s.queues = tmp_path / "queues"
    s.queues.mkdir()
    s.actions.cards.queues_dir = s.queues
    try:
        standalone(s, booked=False)
        status, out = approve(s)
        assert status == 403 and "token" not in out and s.spawner.calls == []
    finally:
        s.stop()


def test_an_outside_approval_stays_counted_when_the_line_written_after_it_is_lost(svc):
    standalone(svc, booked=False)
    cap = approve(svc)[1]["card"]["agent_cap_usd"]
    svc.confirm(approve(svc)[1]["token"])
    lines = [json.loads(x) for x in svc.actions.audit_path.read_text().splitlines()]
    svc.actions.audit_path.write_text("".join(json.dumps(r) + "\n" for r in lines if r.get("ok") != "confirm"))
    assert svc.actions.exposure() == pytest.approx(cap)


def test_an_outside_approval_older_than_a_day_is_no_longer_counted(svc):
    standalone(svc, booked=False)
    svc.confirm(approve(svc)[1]["token"])
    svc.clock.t += DAYS + 60
    assert svc.actions.exposure() == 0.0


def test_a_confirmed_approval_line_with_no_valid_amount_is_a_refusal_not_zero(svc):
    standalone(svc, booked=False)
    svc.confirm(approve(svc)[1]["token"])
    lines = [json.loads(x) for x in svc.actions.audit_path.read_text().splitlines()]
    for r in lines:
        if r.get("action") == "job_approve" and r.get("attempt") == "confirm":
            r["usd"] = "x"
    svc.actions.audit_path.write_text("".join(json.dumps(r) + "\n" for r in lines))
    with pytest.raises(ca.Refusal) as e:
        svc.actions.exposure()
    assert e.value.status == 503


# ---- the Decisions row ----------------------------------------------------------------------------------------------------------------

def rows(s):
    return {r["id"]: r for r in s.request("GET", "/api/decisions")[1]["decisions"]}


def test_only_a_standalone_code_job_waiting_for_approval_has_the_approve_choice(svc):
    standalone(svc)
    assert "approve" in rows(svc)[J1]["allowed"]
    t4.queue(svc, jobs=("j20261117_110100_aaa2", None))
    t4.awaiting(svc, "j20261117_110100_aaa2", TEXT)
    assert "approve" not in rows(svc)["j20261117_110100_aaa2"]["allowed"]
    t4.awaiting(svc, "j20261117_110200_aaa3", TEXT, state="REVIEW_READY")
    assert "approve" not in rows(svc)["j20261117_110200_aaa3"]["allowed"]


def test_a_row_that_is_busy_or_whose_draft_cannot_be_read_has_no_approve_choice(svc):
    standalone(svc)
    svc.spawner.busy_ids.add(J1)
    assert "approve" not in rows(svc)[J1]["allowed"]
