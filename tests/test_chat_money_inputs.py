"""F25: every money number the daily cap reads from a file or the config is a finite, non-negative number, or the exposure is unknown and the cap refuses (fail closed).
Before: a NaN `max_usd` made `used + extra > cap` false for ever, a negative one lowered the exposure, an infinite cap switched the cap off, a huge integer raised OverflowError."""
import json
import math
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_chat_actions as t  # noqa: E402
from router import chat_actions as ca  # noqa: E402

svc = t.svc
NOW = t.NOW
BAD = [float("nan"), float("inf"), float("-inf"), -0.5, -1e-9, True, "nan", "inf", "-1", "abc", [], {}, 10 ** 400]


def raw_job(svc, job_id, kind, max_usd, via="ui", created=None):
    """A job file whose max_usd is written as given (json.dumps writes NaN, Infinity and huge integers as the real files can hold them)."""
    d = svc.jobs / job_id
    d.mkdir(parents=True)
    at = t.iso(NOW - 600 if created is None else created)
    (d / "job.json").write_text(json.dumps({"job": job_id, "kind": kind, "state": "AWAITING_HUMAN", "max_usd": max_usd, "created_at": at,
                                            "inputs": {"repo_name": "athena"}, "log": [{"at": at, "what": "created", "via": via}]}))


FALSY = ([], {})                                                                 # absent or empty counts as no money, as it always did (`max_usd or 0`)


@pytest.mark.parametrize("bad", BAD, ids=lambda b: repr(b)[:12])
@pytest.mark.parametrize("kind", ["issue", "research", "prd"])
def test_a_bad_max_usd_in_a_job_started_from_the_ui_makes_the_exposure_unknown_and_the_cap_refuses(svc, kind, bad):
    if kind == "issue" and bad in FALSY:
        pytest.skip("an empty value is no money for an issue job")
    raw_job(svc, "j20261115_200000_aaaa", kind, bad)
    with pytest.raises(ca.Refusal) as e:
        svc.actions.exposure()
    assert e.value.status == 503 and e.value.gate == "cap"
    with pytest.raises(ca.Refusal):
        svc.actions.check_cap({"action": "issue_new", "job_cap_usd": 0.5})                   # the cap refuses a paid action; it never lets it through


@pytest.mark.parametrize("good", [0, 0.0, 0.5, 1, "0.25"])
def test_a_good_max_usd_still_counts(svc, good):
    raw_job(svc, "j20261115_200000_aaaa", "issue", good)
    assert svc.actions.exposure() == pytest.approx(float(good))


def test_a_bad_max_usd_in_a_job_not_from_the_ui_or_outside_the_window_is_not_read(svc):
    raw_job(svc, "j20261115_200000_aaaa", "issue", float("nan"), via="cli")
    raw_job(svc, "j20261110_200000_bbbb", "issue", float("nan"), created=NOW - 9 * 24 * 3600)
    assert svc.actions.exposure() == 0.0


@pytest.mark.parametrize("bad", [float("inf"), float("nan"), -1.0, True, "7", None, 10 ** 400])
def test_a_cap_that_is_not_a_finite_non_negative_number_is_the_default(svc, bad, monkeypatch):
    monkeypatch.setitem(svc.actions.cfg, "chat", {"daily_cap_usd": bad})
    assert svc.actions.daily_cap() == ca.DEFAULT_CAP_USD


def test_a_float_or_integer_cap_is_kept(svc, monkeypatch):
    for v in (0, 3, 7.25):
        monkeypatch.setitem(svc.actions.cfg, "chat", {"daily_cap_usd": v})
        assert svc.actions.daily_cap() == float(v)


@pytest.mark.parametrize("section", ["research_job", "prd_writer"])
@pytest.mark.parametrize("bad", [float("nan"), float("inf"), -1.0])
def test_a_research_or_prd_cap_that_is_not_finite_makes_the_exposure_unknown(svc, section, bad, monkeypatch):
    monkeypatch.setitem(svc.actions.cfg, section, {"max_usd": bad})
    with pytest.raises(ca.Refusal) as e:
        svc.actions.exposure()
    assert e.value.status == 503


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), -1.0])
def test_an_amount_a_card_adds_that_is_not_a_finite_number_is_refused(svc, bad):
    with pytest.raises(ca.Refusal) as e:
        svc.actions.check_cap({"action": "issue_new", "job_cap_usd": bad})
    assert e.value.status == 403 and e.value.gate == "cap"


def test_a_sum_that_is_not_a_finite_number_is_unknown_whatever_fed_it(svc, monkeypatch):
    monkeypatch.setattr(svc.actions.plans, "exposure", lambda now, seen: float("nan"))
    with pytest.raises(ca.Refusal):
        svc.actions.exposure()
    monkeypatch.setattr(svc.actions.plans, "exposure", lambda now, seen: -5.0)
    with pytest.raises(ca.Refusal):
        svc.actions.exposure()


def test_the_cap_still_refuses_what_passes_it_and_allows_what_fits(svc, monkeypatch):
    monkeypatch.setitem(svc.actions.cfg, "chat", {"daily_cap_usd": 7.0})
    raw_job(svc, "j20261115_200000_aaaa", "issue", 6.8)
    svc.actions.check_cap({"action": "issue_new", "job_cap_usd": 0.2})                                 # 6.8 + 0.2 = 7.0: fits
    with pytest.raises(ca.Refusal):
        svc.actions.check_cap({"action": "issue_new", "job_cap_usd": 0.3})


def test_the_cost_tab_says_unknown_for_a_bad_number_not_zero(svc):
    raw_job(svc, "j20261115_200000_aaaa", "issue", float("nan"))
    st, body = svc.request("GET", "/api/cap")
    assert st == 200 and body["booked_usd"] is None and body["unknown"] is True


def test_finite_usd_itself():
    assert ca.finite_usd(0) == 0.0 and ca.finite_usd("1.5") == 1.5 and ca.finite_usd(2) == 2.0
    for bad in BAD:
        with pytest.raises(ValueError):
            ca.finite_usd(bad)
    assert not any(math.isnan(ca.finite_usd(x)) for x in (0, 1))


# ---- the queues' money ---------------------------------------------------------------------------------------------------------

def test_a_queue_approved_via_the_ui_with_a_bad_amount_makes_the_exposure_unknown_and_never_an_overflow(tmp_path):
    s = t.Service(tmp_path, cfg={**t.CFG, "chat": {"daily_cap_usd": 7.0}})
    s.queues = tmp_path / "queues"
    s.queues.mkdir()
    s.actions.cards.queues_dir = s.queues
    try:
        for n, bad in enumerate([float("nan"), float("inf"), -3.0, 0, 10 ** 400, "x", None]):
            qid = f"q20261115T10{n:02d}00Z-aaa{n}"
            d = s.queues / qid
            d.mkdir()
            (d / "queue.json").write_text(json.dumps({"id": qid, "repo": "/secret/path", "name": "athena", "base_commit": "c" * 40, "jobs_dir": str(s.jobs),
                                                      "max_usd": bad, "job_cap_usd": 0.5, "items": [],
                                                      "approved": {"sha": "x", "at": t.iso(NOW - 100), "by": "x", "via": "ui"}}))
            with pytest.raises(ca.Refusal) as e:
                s.actions.exposure()
            assert e.value.status == 503
            (d / "queue.json").unlink()
            d.rmdir()
    finally:
        s.stop()
