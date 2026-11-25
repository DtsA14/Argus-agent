"""SPEC_CHAT_UI3B: `GET /api/waiting` and the queue rows' applied count. Real files in a temporary jobs and queues directory, a real server; no model."""
import json
import sys
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_chat_actions as t  # noqa: E402
import test_chat_cards as tc  # noqa: E402
import test_chat_plan as tp  # noqa: E402
import test_chat_t4b as t4  # noqa: E402
from router import chat_actions as ca  # noqa: E402

svc = t4.svc
plan_svc = tp.svc


def get(s):
    return s.request("GET", "/api/waiting")


def fresh(s):
    s.actions._waiting_cache = None


def test_nothing_waits_in_an_empty_directory(svc):
    st, body = get(svc)
    assert st == 200 and body["waiting"] == [] and body["capped"] is False and body["cap_unknown"] is False and body["skipped"] == 0


def test_an_approved_queue_with_nothing_started_offers_the_first_step(svc):
    t4.queue(svc)
    st, body = get(svc)
    assert st == 200 and [(r["action"], r["card"], r["id"], r["item"]) for r in body["waiting"]] == [("queue_step", "queue", t4.QID, 1)]
    assert body["waiting"][0]["repo"] == "athena" and body["waiting"][0]["job"] is None


def test_a_finished_draft_is_a_draft_row_that_names_its_code_job(svc):
    t4.waiting(svc)
    st, body = get(svc)
    assert [(r["action"], r["card"], r["id"], r["job"], r["item"]) for r in body["waiting"]] == [("draft_approve", "queue", t4.QID, t4.J1, 1)]


def test_a_queue_that_was_not_approved_from_the_chat_offers_nothing(svc):
    t4.queue(svc, via=None)
    assert get(svc)[1]["waiting"] == []


def test_a_closed_queue_offers_nothing(svc):
    t4.queue(svc, closed=True)
    assert get(svc)[1]["waiting"] == []


def test_no_reason_text_and_no_path_travels(svc):
    t4.waiting(svc)
    raw = json.dumps(get(svc)[1])
    assert "/secret/path" not in raw and '"why"' not in raw


def test_the_answer_is_kept_and_a_confirm_clears_it(svc):
    t4.queue(svc)
    first = get(svc)[1]
    assert len(first["waiting"]) == 1
    t4.queue(svc, via=None)                                              # the files changed, the answer is still the kept one
    assert get(svc)[1] == first
    with pytest.raises(ca.Refusal):
        svc.actions.confirm("no-such-token")
    assert svc.actions._waiting_cache is None                            # a confirm clears it
    assert get(svc)[1]["waiting"] == []


def test_the_kept_answer_expires(svc):
    t4.queue(svc)
    a = svc.actions
    get(svc)
    cache = a._waiting_cache
    a._waiting_cache = (cache[0] - ca.WAIT_TTL_S - 1, cache[1])
    t4.queue(svc, via=None)
    assert get(svc)[1]["waiting"] == []


def test_the_exposure_is_computed_once_per_request_and_never_left_behind(svc):
    t4.queue(svc, texts=(t4.TEXT, t4.TEXT2))
    a = svc.actions
    calls = []
    real = a._exposure_scan
    a._exposure_scan = lambda: calls.append(1) or real()
    fresh(svc)
    get(svc)
    assert len(calls) == 1 and a._exposure_once is None                     # one scan for the whole request; prepare and confirm see the live one again
    a.exposure()
    assert len(calls) == 2


def test_an_unknown_exposure_is_said_and_no_money_row_is_listed(svc):
    t4.queue(svc, at=t.NOW - 3 * 24 * 3600)                       # a step outside the 24 hours counts one job cap: it needs the exposure
    a = svc.actions
    a._exposure_scan = lambda: (_ for _ in ()).throw(ca.Refusal(503, "cap", "unknown"))
    fresh(svc)
    body = get(svc)[1]
    assert body["cap_unknown"] is True and body["waiting"] == [] and a._exposure_once is None


def test_a_slow_scan_stops_at_the_budget_and_says_so(svc):
    t4.waiting(svc)
    a = svc.actions
    ticks = iter([0.0] + [100.0] * 50)
    a.mono = lambda: next(ticks)
    fresh(svc)
    body = a.waiting()
    assert body["capped"] is True and body["waiting"] == []


def test_more_candidates_than_the_scan_limit_are_capped(svc, monkeypatch):
    monkeypatch.setattr(ca, "WAIT_SCAN_MAX", 1)
    t4.queue(svc)
    other = svc.queues / "q20261117T100500Z-bbbb"
    other.mkdir()
    q = json.loads((svc.queues / t4.QID / "queue.json").read_text())
    q["id"] = "q20261117T100500Z-bbbb"
    (other / "queue.json").write_text(json.dumps(q))
    for n in (1, 2):
        (other / f"issue-{n}.md").write_text((svc.queues / t4.QID / f"issue-{n}.md").read_text())
    body = get(svc)[1]
    assert body["capped"] is True and body["scanned"] == 1
    assert [r["id"] for r in body["waiting"]] == ["q20261117T100500Z-bbbb"]                 # the newest candidate is the one kept


def test_a_candidate_whose_builder_raises_is_counted_not_a_500(svc, monkeypatch):
    t4.queue(svc)
    monkeypatch.setattr(svc.actions.steps, "state", lambda qid, with_job=False: (_ for _ in ()).throw(RuntimeError("hostile file")))
    st, body = get(svc)
    assert st == 200 and body["waiting"] == [] and body["skipped"] == 1


def test_an_unreadable_jobs_directory_is_capped_not_nothing_waits(svc, monkeypatch):
    def boom(self_):
        raise OSError("gone")
    monkeypatch.setattr(type(svc.actions.cards), "_listing", lambda self, queue_rows=None: boom(self))      # `listing` swallows it and comes back with no rows and truncated
    st, body = get(svc)
    assert st == 200 and body["waiting"] == [] and body["capped"] is True


def test_a_scan_that_blows_up_anywhere_still_answers_200_and_says_it_may_be_incomplete(svc, monkeypatch):
    monkeypatch.setattr(svc.actions.cards, "_queue_rows", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("hostile")))
    st, body = get(svc)
    assert st == 200 and body["waiting"] == [] and body["capped"] is True and svc.actions._exposure_once is None


def test_a_job_file_that_is_nested_too_deep_for_the_exposure_scan_is_an_unknown_cap_not_a_dropped_answer(svc, monkeypatch):
    t4.queue(svc)

    def deep():
        raise RecursionError("maximum recursion depth exceeded")
    monkeypatch.setattr(svc.actions, "_exposure_scan", deep)
    st, body = get(svc)
    assert st == 200 and body["cap_unknown"] is True and svc.actions._exposure_once is None


def test_the_plan_row_is_still_listed_when_the_cap_is_unknown_because_it_spends_nothing(plan_svc, monkeypatch):
    tp.setup(plan_svc, queue=False)
    monkeypatch.setattr(plan_svc.actions, "_exposure_scan", lambda: (_ for _ in ()).throw(ca.Refusal(503, "cap", "unknown")))
    body = get(plan_svc)[1]
    assert body["cap_unknown"] is True and [r["action"] for r in body["waiting"]] == ["prd_approve"]


def test_the_candidates_are_ordered_by_the_time_in_the_id_not_by_a_field_a_file_can_forge():
    f = ca.Actions._id_time
    assert f("j20261121_150231_cbce") == "20261121150231" and f("q20261125T074538Z-310a") == "20261125074538"
    assert f("q20261125T074538Z-310a") > f("j20261121_150231_cbce") and f("") == ""


def test_the_route_needs_the_chat_actions_and_answers_no_other_method(svc):
    import test_chat as read_only
    ro = read_only.Service(svc.jobs)
    try:
        assert ro.request("GET", "/api/waiting")[0] == 404
        assert ro.request("POST", "/api/waiting", body=b"x")[0] in (400, 403, 404, 405, 421)
    finally:
        ro.stop()


# ---- the plan's rows ----------------------------------------------------------------------------------------------------------

def test_a_plan_that_waits_is_a_plan_row_and_opens_the_plan_card(plan_svc):
    tp.setup(plan_svc, queue=False)
    st, body = get(plan_svc)
    assert st == 200 and [(r["action"], r["card"], r["id"]) for r in body["waiting"]] == [("prd_approve", "plan", tc.PJOB)]
    assert body["waiting"][0]["repo"] == "athena" and body["waiting"][0]["title"].startswith("bikin dua perubahan")


def test_a_plan_with_a_pending_queue_offers_the_money_step_on_the_plan_card(plan_svc):
    tp.setup(plan_svc)
    body = get(plan_svc)[1]
    assert [(r["action"], r["card"], r["id"]) for r in body["waiting"]] == [("queue_go", "plan", tc.PJOB)]


def test_a_plan_whose_queue_runs_or_is_done_is_not_a_candidate(plan_svc):
    d, files, q = tp.setup(plan_svc)
    p = plan_svc.queues / tc.QID / "queue.json"
    data = json.loads(p.read_text())
    data["approved"] = {"sha": "x", "at": t.iso(t.NOW - 100), "by": "x", "via": "ui"}
    p.write_text(json.dumps(data))
    body = get(plan_svc)[1]
    assert all(r["action"] != "prd_approve" and r["action"] != "queue_go" for r in body["waiting"])


# ---- the queue rows' applied count ---------------------------------------------------------------------------------------------

def test_a_queue_row_counts_the_items_whose_card_shows_a_commit(svc):
    t4.queue(svc)
    rows_ = svc.request("GET", "/api/cards")[1]["rows"]
    q = [r for r in rows_ if r["kind"] == "queue"][0]
    assert q["items"] == 2 and q["applied_n"] == 0 and isinstance(q["applied_n"], int) and not isinstance(q["applied_n"], bool)


def test_a_row_never_carries_a_bool_item_or_a_job_that_is_not_a_job_id(svc, monkeypatch):
    t4.queue(svc)
    monkeypatch.setattr(svc.actions.steps, "state", lambda qid, with_job=False: {"action": "queue_step", "item": True, "job": "../etc/passwd", "why": None})
    row = get(svc)[1]["waiting"][0]
    assert row["item"] is None and row["job"] is None and row["action"] == "queue_step"


def test_a_plan_in_a_failed_write_is_not_a_candidate(plan_svc):
    tp.setup(plan_svc, queue=False)
    p = plan_svc.jobs / tc.PJOB / "job.json"
    data = json.loads(p.read_text())
    data["state"] = "WRITE_FAILED"
    p.write_text(json.dumps(data))
    body = get(plan_svc)[1]
    assert body["scanned"] == 0 and body["waiting"] == []


def test_a_queue_that_is_stopped_is_not_a_candidate(svc):
    t4.awaiting(svc, t4.J1, "another issue text")                        # a job that is not this queue item: the queue is stopped
    t4.queue(svc, jobs=(t4.J1, None))
    rows_ = svc.request("GET", "/api/cards")[1]["rows"]
    assert [r["state"] for r in rows_ if r["kind"] == "queue"] == ["STOPPED"]
    body = get(svc)[1]
    assert body["scanned"] == 0 and body["waiting"] == []


def test_the_plan_of_a_running_queue_is_not_counted_as_a_candidate(plan_svc):
    tp.setup(plan_svc)
    p = plan_svc.queues / tc.QID / "queue.json"
    data = json.loads(p.read_text())
    data["approved"] = {"sha": "x", "at": t.iso(t.NOW - 100), "by": "x", "via": "ui"}
    p.write_text(json.dumps(data))
    body = get(plan_svc)[1]
    assert body["scanned"] == 1                                                         # the queue only: its plan has no button to offer


# ---- the applied count -------------------------------------------------------------------------------------------------------

def applied_job(svc, job_id, text):
    jd = t4.awaiting(svc, job_id, text, state="APPLIED")
    p = jd / "job.json"
    data = json.loads(p.read_text())
    data["log"] = [{"what": "state", "new": "APPLIED", "commit": "a" * 40, "as_is": True}]
    p.write_text(json.dumps(data))
    return jd


def test_an_applied_item_is_counted(svc):
    applied_job(svc, t4.J1, t4.TEXT)
    t4.queue(svc, jobs=(t4.J1, None))
    q = [r for r in svc.request("GET", "/api/cards")[1]["rows"] if r["kind"] == "queue"][0]
    assert q["state"] == "WAITING" and q["items"] == 2 and q["applied_n"] == 1


def test_a_queue_with_too_many_items_has_no_state_and_no_count_never_zero_of_n(svc):
    texts = tuple(tc.issue_text(title=f"item {n}") for n in range(1, 23))
    t4.queue(svc, texts=texts, jobs=tuple(None for _ in texts))
    q = [r for r in svc.request("GET", "/api/cards")[1]["rows"] if r["kind"] == "queue"][0]
    assert q["state"] is None and q["applied_n"] is None


def test_the_plan_of_a_finished_queue_is_not_a_candidate(plan_svc, monkeypatch):
    tp.setup(plan_svc, queue=False)
    done = {"id": "q20261117T100400Z-abcd", "kind": "queue", "state": "DONE", "prd_job": tc.PJOB, "at": "2026-11-17T10:04:00Z", "repo": "athena", "title": "athena", "items": 2, "applied_n": 2}
    monkeypatch.setattr(plan_svc.actions.cards, "_queue_rows", lambda *a, **k: ([done], False))
    body = get(plan_svc)[1]
    assert body["scanned"] == 0 and body["waiting"] == []


def test_the_queues_are_read_and_derived_once_per_scan(svc):
    t4.queue(svc)
    calls = []
    real = svc.actions.cards._queue_rows
    svc.actions.cards._queue_rows = lambda *a, **k: calls.append(1) or real(*a, **k)
    fresh(svc)
    get(svc)
    assert len(calls) == 1
