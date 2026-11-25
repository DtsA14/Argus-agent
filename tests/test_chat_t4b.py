"""SPEC_CHAT_T4B rev 1 (PR2): `queue_step` and `draft_approve` of the chat. Real files in a temporary jobs and queues directory, a real server on a free port; the
spawner is a recorder (no process starts), the real config supplies the code task and the budgets. No model."""
import copy
import hashlib
import json
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_chat_actions as t  # noqa: E402
import test_chat_cards as tc  # noqa: E402
from router import chat_actions as ca  # noqa: E402
from router import job as rj  # noqa: E402
from router import queue as rq  # noqa: E402
from runner import load_config  # noqa: E402

QID = tc.QID
J1, J2 = "j20261117_110000_aaa1", "j20261117_110100_aaa2"
TEXT = tc.issue_text(title="One")
TEXT2 = tc.issue_text(title="Two")


def make_cfg(**chat):
    base = load_config()
    cfg = copy.deepcopy(base)
    cfg["issue_writer"] = copy.deepcopy(t.CFG["issue_writer"])
    cfg["chat"] = {"daily_cap_usd": 7.0, **chat}
    return cfg


@pytest.fixture
def svc(tmp_path):
    s = t.Service(tmp_path, cfg=make_cfg())
    s.queues = tmp_path / "queues"
    s.queues.mkdir()
    s.actions.cards.queues_dir = s.queues
    real = s.spawner.spawn

    def spawn(job_id, *a, **kw):                               # a real spawner is busy for the job until the process ends
        real(job_id, *a, **kw)
        s.spawner.busy_ids.add(job_id)
    s.spawner.spawn = spawn
    yield s
    s.stop()


def queue(s, texts=(TEXT, TEXT2), jobs=(None, None), via="ui", at=None, closed=None, **kw):
    """A queue as `queue go` leaves it (its list sha is the real one), the items' jobs as given."""
    d, _ = tc.write_queue(s, list(zip(texts, jobs)), max_usd=3.0, job_cap_usd=1.0, **kw)
    p = d / "queue.json"
    q = json.loads(p.read_text())
    q["approved"] = {"sha": rq.list_sha(q), "at": t.iso(t.NOW - 100 if at is None else at), "by": "x", **({"via": via} if via else {})}
    if closed:
        q["closed"] = {"at": "t", "note": "x"}
    p.write_text(json.dumps(q))
    return d


def draft(unverifiable=None, **contract):
    return {"base": "base", "contract": {"scope": {"writable": ["src/a.py", "tests/test_a.py"]}, "budget_profile": "default",
                                         "validation": [{"id": "v1", "executable": "pytest", "args": ["-q"], "must_pass": ["tests/test_a.py::test_x"]}], **contract},
            **({"unverifiable": unverifiable} if unverifiable else {})}


def awaiting(s, job_id=J1, text=TEXT, d=None, state="AWAITING_APPROVAL", approval=None, stage_usd=0.05):
    """A code job whose drafter finished: the draft.json on disk, its stage recorded."""
    d = d or draft()
    jd = tc.write_job(s.jobs, job_id, kind="code", state=state, max_usd=1.0, approval=approval,
                      inputs={"repo": "/secret/path", "repo_name": "athena", "commit": "c" * 40, "issue": text},
                      stages={"d1": {"kind": "draft", "status": "DRAFTED", "run_id": "d1-run", "usd": stage_usd}})
    run = jd / "runs" / "d1-run"
    run.mkdir(parents=True)
    (run / "draft.json").write_text(json.dumps(d))
    return jd


def prep(s, action, **kw):
    return s.prepare(action=action, queue=QID, **kw)


def audit_confirms(s, action):
    return [r for r in s.audit() if r.get("action") == action and r.get("ok") == "confirm"]


# ---- queue_step ----------------------------------------------------------------------------------------------------------------

def test_a_step_card_shows_the_item_the_cap_and_what_will_happen_and_runs_nothing(svc):
    queue(svc)
    status, out = prep(svc, "queue_step")
    assert status == 200 and svc.spawner.calls == []
    c = out["card"]
    assert c["action"] == "queue_step" and c["queue"] == QID and c["item"] == 1 and c["job_cap_usd"] == 1.0 and c["queue_usd"] == 3.0
    assert "One" in c["item_text"] and "request" not in c
    assert "approve the draft yourself" in c["money"] and out["exposure_usd"] == 0.0 and c["outside_window"] is False


def test_a_step_confirm_spawns_exactly_the_fixed_argv_keyed_by_the_queue(svc):
    queue(svc)
    token = prep(svc, "queue_step")[1]["token"]
    status, out = svc.confirm(token)
    assert status == 200 and out["started"] is True and out["queue"] == QID
    (call,) = svc.spawner.calls
    argv = call["argv"]
    i = argv.index("queue")
    assert call["job"] == QID and call["action"] == "queue_step"
    assert argv[i:] == ["queue", "step", QID, "--item", "1", "--via", "ui", "--key-file", t.KEY, "--yes"]
    for bad in ("--sha", "--max-usd", "--web", "--reference-patch", "--max-iterations", "--job-id"):
        assert bad not in argv
    assert "--queues-dir" in argv and "--jobs-dir" in argv


def test_a_second_confirm_of_the_same_token_starts_nothing_more(svc):
    queue(svc)
    token = prep(svc, "queue_step")[1]["token"]
    assert svc.confirm(token)[0] == 200
    assert svc.confirm(token)[0] == 403
    assert len(svc.spawner.calls) == 1


@pytest.mark.parametrize("body", [{"job": J1}, {"sha": "a" * 12}, {"item": "2"}, {"message": "x"}, {"reason": "a long enough reason"}, {"ack": "1"}])
def test_a_step_takes_the_queue_and_nothing_else(svc, body):
    queue(svc)
    status, out = prep(svc, "queue_step", **body)
    assert status == 400 and "token" not in out


def test_an_unknown_field_is_refused_by_the_page_layer_too(svc):
    queue(svc)
    status, out = svc.request("POST", "/api/prepare", {"action": "queue_step", "queue": QID, "max_usd": "9"})
    assert status == 400 and svc.spawner.calls == []


@pytest.mark.parametrize("qid", ["", "q1", "../x", "q20261117T100400Z-zzzz", None])
def test_a_step_of_no_such_queue(svc, qid):
    queue(svc)
    status, _ = svc.request("POST", "/api/prepare", {"action": "queue_step", **({"queue": qid} if qid is not None else {})})
    assert status in (400, 404)


def test_a_queue_that_was_not_approved_from_the_chat_has_no_step(svc):
    queue(svc, via=None)
    status, out = prep(svc, "queue_step")
    assert status == 409 and "not approved from the chat" in out["refused"] and "token" not in out


@pytest.mark.parametrize("what", ["closed", "pending", "list_changed", "jobs_dir"])
def test_a_queue_that_is_closed_pending_changed_or_on_another_jobs_dir_has_no_step(svc, what):
    d = queue(svc, closed=(what == "closed"))
    p = d / "queue.json"
    q = json.loads(p.read_text())
    if what == "pending":
        q.pop("approved")
    if what == "list_changed":
        q["approved"]["sha"] = "0" * 64
    if what == "jobs_dir":
        q["jobs_dir"] = "/elsewhere"
    p.write_text(json.dumps(q))
    status, out = prep(svc, "queue_step")
    assert status == 409 and "token" not in out


def test_an_issue_file_changed_after_the_list_was_approved_has_no_step(svc):
    d = queue(svc)
    (d / "issue-1.md").write_text("changed")
    assert prep(svc, "queue_step")[0] == 409


def test_a_step_is_refused_while_a_step_of_the_queue_runs(svc):
    queue(svc)
    svc.spawner.busy_ids.add(QID)
    assert prep(svc, "queue_step")[0] == 409


def test_a_step_is_refused_for_a_new_job_without_a_stage_that_is_busy(svc):
    queue(svc, jobs=(J1, None))
    tc.write_job(svc.jobs, J1, kind="code", state="NEW", stages={}, inputs={"repo": "/secret/path", "repo_name": "athena", "commit": "c" * 40, "issue": TEXT})
    svc.spawner.busy_ids.add(J1)
    assert prep(svc, "queue_step")[0] == 409


def test_the_card_is_bound_to_the_queue_and_the_item_it_showed(svc):
    d = queue(svc)
    token = prep(svc, "queue_step")[1]["token"]
    p = d / "queue.json"
    q = json.loads(p.read_text())
    q["closed"] = {"at": "t", "note": "x"}
    p.write_text(json.dumps(q))
    status, _ = svc.confirm(token)
    assert status == 409 and svc.spawner.calls == []


def test_the_item_moving_between_prepare_and_confirm_refuses_the_confirm(svc):
    queue(svc)
    token = prep(svc, "queue_step")[1]["token"]
    awaiting(svc, J1, TEXT)                                    # another command started item 1 meanwhile
    p = svc.queues / QID / "queue.json"
    q = json.loads(p.read_text())
    q["items"][0]["job"] = J1
    p.write_text(json.dumps(q))
    status, _ = svc.confirm(token)
    assert status == 409 and svc.spawner.calls == []


def test_a_step_needs_the_code_key(tmp_path):
    s = t.Service(tmp_path, cfg=make_cfg(), environ={})
    s.queues = tmp_path / "queues"
    s.queues.mkdir()
    s.actions.cards.queues_dir = s.queues
    try:
        queue(s)
        status, out = prep(s, "queue_step")
        assert status == 409 and "is not set" in out["refused"]
    finally:
        s.stop()


def test_a_retried_item_says_the_readers_findings_go_to_the_drafter(svc):
    d = queue(svc)
    p = d / "queue.json"
    q = json.loads(p.read_text())
    q["items"][0]["retries"] = [{"job": J2, "spent_nano": 0, "findings": "x", "at": "t", "by": "x"}]
    q["items"][0]["retry_note"] = "findings"
    p.write_text(json.dumps(q))
    c = prep(svc, "queue_step")[1]["card"]
    assert c["retry"] is True and any("readers' findings" in f for f in c["flags"])


# ---- the money (K4 = A) ----------------------------------------------------------------------------------------------------------

def test_a_step_inside_the_24_hours_of_the_approval_adds_nothing(svc):
    queue(svc, at=t.NOW - 3600)
    status, out = prep(svc, "queue_step")
    assert status == 200 and out["exposure_usd"] == 0.0 and out["card"]["outside_window"] is False
    svc.confirm(out["token"])
    (rec,) = audit_confirms(svc, "queue_step")
    assert rec["usd"] == 0.0 and rec["queue"] == QID and rec["item"] == 1


def test_a_step_of_a_queue_approved_more_than_a_day_ago_counts_one_job_cap(svc):
    queue(svc, at=t.NOW - 2 * 86400)
    status, out = prep(svc, "queue_step")
    assert status == 200 and out["exposure_usd"] == 1.0 and out["card"]["outside_window"] is True
    assert any("daily cap" in f for f in out["card"]["flags"])
    assert svc.confirm(out["token"])[0] == 200
    (rec,) = audit_confirms(svc, "queue_step")
    assert rec["usd"] == 1.0 and rec["action"] == "queue_step"
    assert svc.actions.exposure() == 1.0                          # the audit net keeps it counted after the process is gone


def test_a_step_outside_the_window_is_refused_when_the_daily_cap_would_pass(tmp_path):
    s = t.Service(tmp_path, cfg=make_cfg(daily_cap_usd=0.5))
    s.queues = tmp_path / "queues"
    s.queues.mkdir()
    s.actions.cards.queues_dir = s.queues
    try:
        queue(s, at=t.NOW - 2 * 86400)
        status, out = prep(s, "queue_step")
        assert status == 403 and "token" not in out and s.spawner.calls == []
    finally:
        s.stop()


def test_a_step_outside_the_window_counts_with_the_other_exposure(svc):
    queue(svc, at=t.NOW - 2 * 86400)
    svc.confirm(prep(svc, "queue_step")[1]["token"])
    assert svc.actions.check_cap({"action": "queue_step", "job_cap_usd": 1.0, "outside_window": True}) is None
    svc.actions.cfg["chat"]["daily_cap_usd"] = 1.5
    with pytest.raises(ca.Refusal):
        svc.actions.check_cap({"action": "queue_step", "job_cap_usd": 1.0, "outside_window": True})


def test_the_audit_of_a_step_has_its_own_action_and_no_text(svc):
    queue(svc)
    svc.confirm(prep(svc, "queue_step")[1]["token"])
    assert audit_confirms(svc, "queue_go") == [] and len(audit_confirms(svc, "queue_step")) == 1
    raw = svc.actions.audit_path.read_text()
    assert "One" not in raw and "request" not in raw


# ---- draft_approve ------------------------------------------------------------------------------------------------------------------

def waiting(svc, **kw):
    queue(svc, jobs=(J1, None))
    awaiting(svc, J1, TEXT, **kw)


def test_a_draft_card_shows_the_full_sha_the_files_the_tests_and_the_caps_and_runs_nothing(svc):
    waiting(svc)
    status, out = prep(svc, "draft_approve")
    assert status == 200 and svc.spawner.calls == []
    c = out["card"]
    sha = rj.draft_sha_of(draft())
    assert c["action"] == "draft_approve" and c["job"] == J1 and c["item"] == 1 and c["draft_sha"] == sha and len(sha) == 64
    assert c["writable"] == ["src/a.py", "tests/test_a.py"] and c["validations"][0]["must_pass"] == ["tests/test_a.py::test_x"]
    assert c["agent_cap_usd"] > 0 and c["attempt_usd"] > 0 and out["exposure_usd"] == 0.0 and "profile: default" in " ".join(c["flags"])


def test_a_draft_confirm_spawns_exactly_the_fixed_argv_with_the_full_sha(svc):
    waiting(svc)
    token = prep(svc, "draft_approve")[1]["token"]
    status, out = svc.confirm(token)
    assert status == 200 and out["started"] is True and out["job"] == J1
    (call,) = svc.spawner.calls
    argv = call["argv"]
    i = argv.index("approve")
    assert call["job"] == QID and call["action"] == "draft_approve"
    assert argv[i:] == ["approve", J1, "--sha", rj.draft_sha_of(draft()), "--via", "ui", "--key-file", t.KEY, "--yes"]
    for bad in ("--max-usd", "--web", "--reference-patch", "--max-iterations"):
        assert bad not in argv
    (rec,) = audit_confirms(svc, "draft_approve")
    assert rec["usd"] == 0.0 and rec["sha"] == rj.draft_sha_of(draft())[:12] and rec["queue"] == QID


def test_a_draft_that_changed_between_prepare_and_confirm_is_not_approved(svc):
    waiting(svc)
    token = prep(svc, "draft_approve")[1]["token"]
    run = svc.jobs / J1 / "runs" / "d1-run"
    (run / "draft.json").write_text(json.dumps({**draft(), "base": "other"}))      # a byte the card does not show but the sha does
    status, _ = svc.confirm(token)
    assert status == 409 and svc.spawner.calls == []


def test_a_second_confirm_of_a_draft_starts_one_agent(svc):
    waiting(svc)
    token = prep(svc, "draft_approve")[1]["token"]
    assert svc.confirm(token)[0] == 200 and svc.confirm(token)[0] == 403
    assert len(svc.spawner.calls) == 1


def test_a_draft_flagged_by_the_gate_is_refused_on_the_server(svc):
    waiting(svc, d=draft(unverifiable=["existing test conflicts with the new rule"]))
    status, out = prep(svc, "draft_approve")
    assert status == 409 and "token" not in out and "conflict" in out["refused"]


@pytest.mark.parametrize("state", ["DRAFT_FAILED", "REVIEW_READY", "AGENT_RUNNING", "REJECTED"])
def test_only_a_job_that_waits_for_approval_is_approved_from_the_chat(svc, state):
    queue(svc, jobs=(J1, None))
    awaiting(svc, J1, TEXT, state=state)
    status, out = prep(svc, "draft_approve")
    assert status == 409 and "token" not in out


def test_a_draft_already_approved_is_refused(svc):
    waiting(svc, approval={"draft_sha256": rj.draft_sha_of(draft())})
    assert prep(svc, "draft_approve")[0] == 409


def test_an_approval_that_would_block_the_job_is_refused_before_the_tap(svc):
    waiting(svc, stage_usd=0.0)
    p = svc.jobs / J1 / "job.json"
    data = json.loads(p.read_text())
    data["max_usd"] = 0.0001                                   # less than one attempt is left
    p.write_text(json.dumps(data))
    status, out = prep(svc, "draft_approve")
    assert status == 409 and "block" in out["refused"] and json.loads(p.read_text())["state"] == "AWAITING_APPROVAL"


def test_a_step_card_for_an_item_that_has_a_draft_and_a_draft_card_for_an_item_that_has_none_are_refused(svc):
    waiting(svc)
    assert prep(svc, "queue_step")[0] == 409
    (svc.queues / QID / "queue.json").unlink()
    queue(svc)
    assert prep(svc, "draft_approve")[0] == 409


def test_the_draft_card_for_a_queue_approved_from_the_terminal_is_refused(svc):
    queue(svc, jobs=(J1, None), via=None)
    awaiting(svc, J1, TEXT)
    assert prep(svc, "draft_approve")[0] == 409


def test_a_draft_job_reached_through_a_link_is_refused(svc, tmp_path):
    queue(svc, jobs=(J1, None))
    real = tmp_path / "real"
    real.mkdir()
    awaiting(svc, J1, TEXT)
    (svc.jobs / J1).rename(real / J1)
    (svc.jobs / J1).symlink_to(real / J1)
    assert prep(svc, "draft_approve")[0] == 409


def test_a_draft_file_that_is_a_link_or_not_a_regular_file_is_refused(svc, tmp_path):
    waiting(svc)
    run = svc.jobs / J1 / "runs" / "d1-run"
    (tmp_path / "elsewhere.json").write_text(json.dumps(draft()))
    (run / "draft.json").unlink()
    (run / "draft.json").symlink_to(tmp_path / "elsewhere.json")
    assert prep(svc, "draft_approve")[0] == 409
    (run / "draft.json").unlink()
    import os
    os.mkfifo(run / "draft.json")
    assert prep(svc, "draft_approve")[0] == 409                 # and the server is not hung by it


def test_a_runs_directory_that_is_a_link_is_refused(svc, tmp_path):
    waiting(svc)
    runs = svc.jobs / J1 / "runs"
    runs.rename(tmp_path / "runs_elsewhere")
    runs.symlink_to(tmp_path / "runs_elsewhere")
    assert prep(svc, "draft_approve")[0] == 409


def test_a_config_change_between_prepare_and_confirm_refuses_the_confirm(svc):
    waiting(svc)
    token = prep(svc, "draft_approve")[1]["token"]
    svc.actions.cfg["router"]["agent_max_usd"] = {"default": 0.40, "large_usd": 0.75}
    status, _ = svc.confirm(token)
    assert status == 409 and svc.spawner.calls == []


def test_an_environment_that_changed_since_the_job_started_is_refused(svc):
    queue(svc, jobs=(J1, None))
    jd = awaiting(svc, J1, TEXT)
    p = jd / "job.json"
    data = json.loads(p.read_text())
    data["inputs"]["environment"] = "athena_py312"
    data["environment_image"] = "sha256:" + "1" * 64
    p.write_text(json.dumps(data))
    status, out = prep(svc, "draft_approve")
    assert status == 409 and "token" not in out


def test_a_drafter_that_cannot_afford_one_attempt_is_refused_at_the_step(svc):
    queue(svc)
    svc.actions.cfg["router"]["draft_max_usd"] = 0.0001
    status, out = prep(svc, "queue_step")
    assert status == 409 and "drafter" in out["refused"] and "token" not in out


def test_the_window_closing_between_prepare_and_confirm_changes_the_card(svc):
    queue(svc, at=t.NOW - 86400 + 5)                           # five seconds inside the 24 hours at prepare
    token = prep(svc, "queue_step")[1]["token"]
    svc.clock.t += 10
    status, _ = svc.confirm(token)
    assert status == 409 and svc.spawner.calls == []


def test_a_draft_approval_adds_nothing_even_when_its_queue_is_old(svc):
    queue(svc, jobs=(J1, None), at=t.NOW - 5 * 86400)
    awaiting(svc, J1, TEXT)
    status, out = prep(svc, "draft_approve")
    assert status == 200 and out["exposure_usd"] == 0.0
    svc.confirm(out["token"])
    assert svc.actions.exposure() == 0.0


def test_the_code_key_is_the_slot_even_when_a_writer_key_is_set(svc):
    svc.actions.environ[ca.WRITER_KEY_ENV] = "/keys/writer.key"
    svc.actions.environ[ca.RESEARCH_KEY_ENV] = "/keys/research.key"
    queue(svc)
    svc.confirm(prep(svc, "queue_step")[1]["token"])
    assert t.KEY in svc.spawner.calls[0]["argv"] and "/keys/writer.key" not in svc.spawner.calls[0]["argv"] and "/keys/research.key" not in svc.spawner.calls[0]["argv"]


def test_a_draft_of_a_queue_on_another_jobs_directory_is_refused(svc):
    d = queue(svc, jobs=(J1, None))
    awaiting(svc, J1, TEXT)
    p = d / "queue.json"
    q = json.loads(p.read_text())
    q["jobs_dir"] = "/elsewhere"
    p.write_text(json.dumps(q))
    assert prep(svc, "draft_approve")[0] == 409


def test_two_prepares_and_two_confirms_start_one_agent(svc):
    waiting(svc)
    a, b = prep(svc, "draft_approve")[1]["token"], prep(svc, "draft_approve")[1]["token"]
    assert svc.confirm(a)[0] == 200
    assert svc.confirm(b)[0] == 409                              # the queue is busy now
    assert len(svc.spawner.calls) == 1


def test_a_step_stays_counted_when_the_line_written_after_it_is_lost(svc):
    queue(svc, at=t.NOW - 2 * 86400)
    svc.confirm(prep(svc, "queue_step")[1]["token"])
    lines = [json.loads(x) for x in svc.actions.audit_path.read_text().splitlines()]
    svc.actions.audit_path.write_text("".join(json.dumps(r) + "\n" for r in lines if r.get("ok") != "confirm"))
    assert svc.actions.exposure() == 1.0


def test_a_step_older_than_a_day_is_no_longer_counted(svc):
    queue(svc, at=t.NOW - 2 * 86400)
    svc.confirm(prep(svc, "queue_step")[1]["token"])
    svc.clock.t += 86400 + 60
    assert svc.actions.exposure() == 0.0


# ---- what stays out -------------------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("action", ["apply", "queue_retry", "queue_close", "draft_reject", "job_apply", "redraft", "agent_retry", "pr_merge"])
def test_apply_retry_close_redraft_and_the_rest_are_not_actions_of_the_chat(svc, action):
    waiting(svc)
    status, out = prep(svc, action)
    assert status == 404 and "token" not in out


def test_the_action_list_has_exactly_the_two_new_approvals_and_no_apply():
    assert set(ca.ACTIONS) >= {"queue_step", "draft_approve"}
    assert not any("apply" in a or "retry" in a or "redraft" in a for a in ca.ACTIONS)




def test_a_queue_on_another_jobs_directory_is_refused_even_when_its_approval_names_that_list(svc):
    d = queue(svc)
    p = d / "queue.json"
    q = json.loads(p.read_text())
    q["jobs_dir"] = "/elsewhere"
    q["approved"]["sha"] = rq.list_sha(q)                      # the approval matches the changed list: only the directory check can refuse it
    p.write_text(json.dumps(q))
    status, out = prep(svc, "queue_step")
    assert status == 409 and "jobs directory" in out["refused"]


# ---- the queue card's button (PR3) --------------------------------------------------------------------------------------------------

def card_t4b(s):
    status, got = s.request("GET", f"/api/cards/queue/{QID}")
    assert status == 200
    return got["t4b"]


def test_the_queue_card_offers_the_step_for_a_queue_the_chat_approved(svc):
    queue(svc)
    assert card_t4b(svc) == {"action": "queue_step", "item": 1, "why": None}


def test_the_queue_card_offers_the_draft_approval_when_a_draft_waits(svc):
    waiting(svc)
    assert card_t4b(svc) == {"action": "draft_approve", "item": 1, "why": None}


def test_the_queue_card_offers_nothing_and_says_nothing_for_a_queue_approved_from_the_terminal(svc):
    queue(svc, via=None)
    assert card_t4b(svc) == {"action": None, "item": None, "why": None}


def test_the_queue_card_says_why_while_a_step_runs_and_when_the_cap_is_passed(tmp_path):
    s = t.Service(tmp_path, cfg=make_cfg(daily_cap_usd=0.5))
    s.queues = tmp_path / "queues"
    s.queues.mkdir()
    s.actions.cards.queues_dir = s.queues
    try:
        queue(s)
        s.spawner.busy_ids.add(QID)
        got = card_t4b(s)
        assert got["action"] is None and "still running" in got["why"]
        s.spawner.busy_ids.clear()
        queue(s, at=t.NOW - 2 * 86400)
        got = card_t4b(s)
        assert got["action"] is None and "daily cap" in got["why"]
    finally:
        s.stop()


def test_the_button_never_offers_what_prepare_refuses(svc):
    waiting(svc, d=draft(unverifiable=["existing test conflicts with the new rule"]))
    got = card_t4b(svc)
    assert got["action"] is None and "conflict" in got["why"] and prep(svc, "draft_approve")[0] == 409


def test_the_page_sends_only_the_queue_id_and_has_no_apply_button():
    js = (Path(__file__).resolve().parent.parent / "router" / "chat_static" / "app.js").read_text()
    assert "prepare({ action: t4b.action, queue: id })" in js
    assert "Mulai issue" in js and "Setujui draf issue" in js
    assert "apply" not in js.lower().replace("apply is still done from the terminal", "").replace("nothing is applied yet", "").replace("apply (belum", "")


# ---- SPEC_CHAT_UI1 F17: the draft card shows the plan, the writer's notes and the tests the draft changes -------------------------

def rich(**kw):
    d = draft(**kw)
    d["contract"]["scope"]["protected"] = ["README.md"]
    d.update({"new_tests": [], "plan": {"files": ["src/a.py"], "steps": ["do the thing"], "risks": ["it may break b"]}, "for_human": "one sentence",
              "changed_tests": [{"path": "tests/test_old.py", "content": "x"}], "unverifiable": ["the page stays unchanged"]})
    return d


def write_report(jd, d, **over):
    rep = {"draft_sha256": rj.draft_sha_of(d), "baseline": {"v1": {"must_pass": {}}}}
    rep.update(over)
    (jd / "runs" / "d1-run" / "check_report.json").write_text(json.dumps(rep))


def card_of(svc, d, report=True, **over):
    queue(svc, jobs=(J1, None))
    jd = awaiting(svc, J1, TEXT, d=d)
    if report:
        write_report(jd, d, **over)
    status, out = prep(svc, "draft_approve")
    assert status == 200, (out, json.dumps(svc.audit()[-1:]))
    return out["card"], jd


def test_the_draft_card_shows_plan_risks_unverifiable_notes_and_the_tests_it_changes(svc):
    c, _ = card_of(svc, rich())
    assert c["plan"] == {"files": ["src/a.py"], "steps": ["do the thing"], "risks": ["it may break b"]}
    assert c["unverifiable"] == ["the page stays unchanged"] and "summary_note" not in c
    assert any("looks like a test path" in w for w in c["warnings"]) and any("tests/test_a.py" in w for w in c["warnings"])   # the fixture writes tests/test_a.py, which the scope warns about
    assert c["changed_tests"] == ["tests/test_old.py"] and c["changed_tests_n"] == 1


def test_without_a_baseline_the_card_says_so(svc):
    c, _ = card_of(svc, rich(), baseline={})
    assert c["baseline_note"] == "no baseline recorded"


@pytest.mark.parametrize("how", ["missing", "other_draft", "huge", "link", "not_json", "list", "hostile_baseline", "key"])
def test_a_report_that_is_missing_linked_large_mismatched_or_hostile_leaves_the_button_and_says_so(svc, how, tmp_path):
    d = rich()
    queue(svc, jobs=(J1, None))
    jd = awaiting(svc, J1, TEXT, d=d)
    f = jd / "runs" / "d1-run" / "check_report.json"
    if how == "other_draft":
        write_report(jd, d, draft_sha256="0" * 64)
    elif how == "huge":
        f.write_text(json.dumps({"draft_sha256": rj.draft_sha_of(d), "pad": "x" * 1_100_000}))
    elif how == "link":
        (tmp_path / "elsewhere.json").write_text(json.dumps({"draft_sha256": rj.draft_sha_of(d)}))
        os.symlink(tmp_path / "elsewhere.json", f)
    elif how == "not_json":
        f.write_text("{not json")
    elif how == "list":
        f.write_text("[]")
    elif how == "hostile_baseline":
        write_report(jd, d, baseline={"v1": "not a dict", "v2": [1]})
    elif how == "key":
        d["plan"]["steps"] = ["use sk-or-v1-" + "a" * 40]
        (jd / "runs" / "d1-run" / "draft.json").write_text(json.dumps(d))
        write_report(jd, d)
    status, out = prep(svc, "draft_approve")
    c = out["card"]
    assert status == 200 and c["action"] == "draft_approve" and c["draft_sha"]
    assert c["summary_note"] == "summary unavailable" and "plan" not in c and c["changed_tests"] == ["tests/test_old.py"]
    assert card_t4b(svc)["action"] == "draft_approve"


def test_the_summary_strings_are_scrubbed_and_cut(svc):
    d = rich()
    d["plan"]["steps"] = ["a" * 900] + [f"step {i}" for i in range(80)]
    c, _ = card_of(svc, d)
    assert len(c["plan"]["steps"]) <= 50 and all(len(s) <= 300 for s in c["plan"]["steps"])


def test_many_changed_tests_are_counted_and_cut(svc):
    d = rich()
    d["changed_tests"] = [{"path": f"tests/t{i}.py", "content": "x"} for i in range(60)]
    c, _ = card_of(svc, d)
    assert len(c["changed_tests"]) == 40 and c["changed_tests_n"] == 60


def test_the_card_does_not_write_the_environment(svc):
    before = dict(os.environ)
    card_of(svc, rich())
    assert dict(os.environ) == before
