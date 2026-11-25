"""SPEC_CHAT_UI3C: `GET /api/cap`, the daily cap and the exposure it counts, for the Cost tab. Real files, a real server; no model."""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_chat as read_only  # noqa: E402
import test_chat_actions as t  # noqa: E402
from router import chat_actions as ca  # noqa: E402

svc = t.svc
NOW = t.NOW


def cap(s):
    return s.request("GET", "/api/cap")


def test_nothing_booked_in_an_empty_directory_and_the_cap_is_the_configured_one(svc):
    st, body = cap(svc)
    assert st == 200 and body == {"cap_usd": svc.actions.daily_cap(), "booked_usd": 0.0, "unknown": False}


def test_the_booked_money_is_what_the_cap_counts_not_what_the_jobs_spent(svc):
    for i, j in enumerate(["j20261115_100000_aaaa", "j20261115_110000_aaaa", "j20261115_120000_aaaa"]):
        t.make_issue(svc.jobs, j, created=NOW - 3600 * (i + 1))
    t.make_issue(svc.jobs, "j20261113_100000_aaaa", created=NOW - 3600 * 60)                  # two days ago: not counted
    t.make_issue(svc.jobs, "j20261115_130000_aaaa", created=NOW - 3600, via="cli")              # not from the UI
    body = cap(svc)[1]
    assert body["booked_usd"] == pytest.approx(1.5) and body["unknown"] is False and body["booked_usd"] == pytest.approx(svc.actions.exposure())


def test_an_unknown_exposure_is_null_and_unknown_never_zero(svc, monkeypatch):
    monkeypatch.setattr(svc.actions, "_exposure_scan", lambda: (_ for _ in ()).throw(ca.Refusal(503, "cap", "unknown")))
    body = cap(svc)[1]
    assert body["booked_usd"] is None and body["unknown"] is True and body["cap_usd"] == svc.actions.daily_cap()


def test_a_file_the_scan_cannot_take_is_an_unknown_cap_not_a_dropped_answer(svc, monkeypatch):
    monkeypatch.setattr(svc.actions, "_exposure_scan", lambda: (_ for _ in ()).throw(RecursionError("deep")))
    st, body = cap(svc)
    assert st == 200 and body["booked_usd"] is None and body["unknown"] is True


def test_a_broken_cap_setting_still_answers(svc, monkeypatch):
    monkeypatch.setattr(svc.actions, "daily_cap", lambda: (_ for _ in ()).throw(ValueError("config")))
    st, body = cap(svc)
    assert st == 200 and body == {"cap_usd": None, "booked_usd": None, "unknown": True}


def test_the_answer_is_kept_for_a_while_and_every_confirm_clears_it(svc):
    first = cap(svc)[1]
    t.make_issue(svc.jobs, "j20261115_100000_aaaa", created=NOW - 3600)
    assert cap(svc)[1] == first                                                              # kept
    with pytest.raises(ca.Refusal):
        svc.actions.confirm("no-such-token")
    assert svc.actions._cap_cache is None
    assert cap(svc)[1]["booked_usd"] == pytest.approx(0.5)


def test_the_kept_answer_expires(svc):
    cap(svc)
    a = svc.actions
    old = a._cap_cache
    a._cap_cache = (old[0] - ca.WAIT_TTL_S - 1, old[1])
    t.make_issue(svc.jobs, "j20261115_100000_aaaa", created=NOW - 3600)
    assert cap(svc)[1]["booked_usd"] == pytest.approx(0.5)


def test_the_cap_never_leaves_a_remembered_exposure_for_prepare(svc):
    cap(svc)
    assert svc.actions._exposure_once is None
    t.make_issue(svc.jobs, "j20261115_100000_aaaa", created=NOW - 3600)
    assert svc.actions.exposure() == pytest.approx(0.5)                                       # the live scan, not the kept answer


def test_no_path_and_no_text_of_a_job_travels(svc):
    t.make_issue(svc.jobs, "j20261115_100000_aaaa", created=NOW - 3600)
    raw = json.dumps(cap(svc)[1])
    assert "/secret" not in raw and set(json.loads(raw)) == {"cap_usd", "booked_usd", "unknown"}


def test_the_route_needs_the_chat_actions(svc):
    ro = read_only.Service(svc.jobs)
    try:
        assert ro.request("GET", "/api/cap")[0] == 404
    finally:
        ro.stop()
