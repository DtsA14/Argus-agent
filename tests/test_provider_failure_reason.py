"""PENDING_PRIORITAS 2 (NEXUS-lite pilot, stage 4 issue 3): a provider failure shows its HTTP status and what it usually means, never the provider's own
text; and a gateway answer that refused the call before any model ran (401, 402, 429) is not charged. Scripted fake model: no network, no cost."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_drafter as td  # noqa: E402
from test_drafter import root  # noqa: E402,F401  (the fixture)

from codetask import drafter as dt  # noqa: E402
from harness.errors import LLMCallFailed
from harness.llm import GATEWAY_REFUSED, provider_failure_reason
from models.fake import FakeHTTPError, reply
from tests.test_codetask import run, st
from tests.test_rate_limit_retry import GATEWAY, MSGS, ledger, make, res


# ---- the sentence ---------------------------------------------------------------------------------------------------------------

def test_no_status_keeps_the_plain_sentence():
    for status in (None, "402", 402.0, True, False):
        assert provider_failure_reason(status) == "the model provider failed"


def test_a_402_names_the_key_limit_and_the_balance():
    text = provider_failure_reason(402)
    assert text.startswith("the model provider failed (HTTP 402: ")
    assert "credit limit of the API key" in text and "account balance" in text


@pytest.mark.parametrize("status,word", [(401, "refused"), (403, "may not use"), (404, "not found"), (408, "timed out"),
                                         (429, "rate limiting"), (500, "its side"), (503, "its side"), (599, "its side")])
def test_each_known_status_has_its_own_fixed_words(status, word):
    text = provider_failure_reason(status)
    assert text.startswith(f"the model provider failed (HTTP {status}: ") and word in text


@pytest.mark.parametrize("status", [400, 418, 499, 600, 0, -1])
def test_an_unlisted_status_shows_only_the_number(status):
    assert provider_failure_reason(status) == f"the model provider failed (HTTP {status})"


def test_the_providers_own_text_is_never_in_the_sentence():
    # the sentence is built from the status alone: there is no parameter that could carry the provider's words
    assert "secret-in-the-body" not in provider_failure_reason(402)


# ---- the bill -------------------------------------------------------------------------------------------------------------------

def test_the_refused_statuses_are_exactly_401_402_429():
    assert tuple(GATEWAY_REFUSED) == (401, 402, 429)


@pytest.mark.parametrize("status", [401, 402])
def test_a_gateway_refusal_before_any_model_ran_is_not_charged(tmp_path, status):
    """SPEC_GATEWAY_REFUSED_FREE (Atha 2026-11-23, "429 ya"): 401 and 402 are booked like a 429, as nothing."""
    caller, fake, _, log = make(tmp_path, [FakeHTTPError(status, "refused"), reply()], model_ref=GATEWAY)
    r = res()
    with pytest.raises(LLMCallFailed) as e:
        caller.call(MSGS, r)
    done = [x for x in ledger(log) if x["event"] == "llm_call"]
    assert len(done) == 1 and len(fake.calls) == 1                       # not retried
    assert done[0]["charged"] == "none" and done[0]["usd_nano"] == 0 and done[0]["tokens"] == 0
    assert done[0]["delivery"] == "received" and done[0]["http_status"] == status
    assert r.used_usd == 0 and r.used_tokens == 0
    assert e.value.__cause__.status_code == status


@pytest.mark.parametrize("status", [403, 404, 500])
def test_a_gateway_answer_that_may_have_run_the_model_is_still_charged_worst_case(tmp_path, status):
    caller, _, _, log = make(tmp_path, [FakeHTTPError(status), FakeHTTPError(status), FakeHTTPError(status), reply()], model_ref=GATEWAY)
    with pytest.raises(LLMCallFailed):
        caller.call(MSGS, res())
    first = [x for x in ledger(log) if x["event"] == "llm_call"][0]
    assert first["charged"] == "worst_case" and first["usd_nano"] > 0


@pytest.mark.parametrize("status", [401, 402])
def test_a_direct_provider_refusal_stays_worst_case(tmp_path, status):
    caller, _, _, log = make(tmp_path, [FakeHTTPError(status), reply()])
    assert caller.gateway is None
    with pytest.raises(LLMCallFailed):
        caller.call(MSGS, res())
    first = [x for x in ledger(log) if x["event"] == "llm_call"][0]
    assert first["charged"] == "worst_case" and first["usd_nano"] > 0 and first["tokens"] > 0


# ---- the status reaches the human -----------------------------------------------------------------------------------------------

def test_the_agent_attempt_keeps_the_status_and_the_run_reason_shows_it(tmp_path):
    r, model, d = run(tmp_path, [FakeHTTPError(402, "only afford 5294 tokens")])
    assert r["status"] == st.BLOCKED and r["blocked_reason"] == "provider_failed"
    assert "HTTP 402" in r["stop_reason"] and "credit limit" in r["stop_reason"] and r["stop_reason"].endswith("during the attempt")
    assert "5294" not in r["stop_reason"]                                      # the provider's text stays out of the sentence


def test_a_failure_without_a_status_keeps_the_old_sentence(tmp_path):
    from tests.test_codetask import timeout
    r, model, d = run(tmp_path, [timeout(), timeout(), timeout()])
    assert r["status"] == st.BLOCKED and r["blocked_reason"] == "provider_failed"
    assert r["stop_reason"] == "the model provider failed during the attempt"


def test_the_drafter_blocks_with_the_status_in_its_reason(root, tmp_path):  # noqa: F811
    r, model, d = td.run(root, tmp_path, [FakeHTTPError(402, "only afford 5294 tokens")])
    assert r["status"] == dt.BLOCKED and r["blocked_reason"] == "provider_failed"
    assert "HTTP 402" in r["stop_reason"] and "5294" not in r["stop_reason"]


# ---- the review of the billing change (Opus, 2026-11-23): gaps it named -------------------------------------------------------------

class OnlyResponse(Exception):
    """An SDK error that carries its status only on `.response` (no `.status_code`)."""

    def __init__(self, status):
        super().__init__(f"HTTP {status}")
        self.response = type("Resp", (), {"headers": {}, "status_code": status})()


class StringStatus(Exception):
    def __init__(self, status):
        super().__init__("odd")
        self.status_code = status


@pytest.mark.parametrize("status", [401, 402])
def test_a_refused_call_still_writes_its_started_event_with_a_worst_case_before_the_final_row(tmp_path, status):
    caller, _, _, log = make(tmp_path, [FakeHTTPError(status), reply()], model_ref=GATEWAY)
    with pytest.raises(LLMCallFailed):
        caller.call(MSGS, res())
    rows = ledger(log)
    assert [r["event"] for r in rows] == ["llm_call_started", "llm_call"] and rows[0]["worst_usd_nano"] > 0 and rows[1]["usd_nano"] == 0


def test_a_status_carried_only_on_the_response_is_read(tmp_path):
    caller, _, _, log = make(tmp_path, [OnlyResponse(402), reply()], model_ref=GATEWAY)
    with pytest.raises(LLMCallFailed):
        caller.call(MSGS, res())
    row = [x for x in ledger(log) if x["event"] == "llm_call"][0]
    assert row["charged"] == "none" and row["http_status"] == 402


@pytest.mark.parametrize("status", ["402", 402.0, "401"])
def test_a_status_that_is_not_an_int_is_not_a_refusal_and_stays_worst_case(tmp_path, status):
    caller, _, _, log = make(tmp_path, [StringStatus(status), StringStatus(status), StringStatus(status), reply()], model_ref=GATEWAY)
    with pytest.raises(LLMCallFailed):
        caller.call(MSGS, res())
    row = [x for x in ledger(log) if x["event"] == "llm_call"][0]
    assert row["charged"] == "worst_case" and row["usd_nano"] > 0


@pytest.mark.parametrize("status", [401, 402])
def test_a_free_gateway_model_is_also_not_charged_for_a_refusal(tmp_path, status):
    caller, fake, _, log = make(tmp_path, [FakeHTTPError(status), reply()], model_ref="openrouter:nvidia/nemotron-3.5-lightning:free")
    with pytest.raises(LLMCallFailed):
        caller.call(MSGS, res())
    row = [x for x in ledger(log) if x["event"] == "llm_call"][0]
    assert row["charged"] == "none" and row["usd_nano"] == 0 and len(fake.calls) == 1


def test_a_transient_gateway_status_408_is_still_worst_case_on_every_attempt(tmp_path):
    caller, fake, _, log = make(tmp_path, [FakeHTTPError(408)] * 3 + [reply()], model_ref=GATEWAY)
    with pytest.raises(LLMCallFailed):
        caller.call(MSGS, res())
    rows = [x for x in ledger(log) if x["event"] == "llm_call"]
    assert len(rows) >= 2 and all(r["charged"] == "worst_case" and r["usd_nano"] > 0 for r in rows)


def test_a_zero_charge_refusal_is_a_priced_call_in_the_reconciled_ledger(tmp_path):
    from harness.events import EventLog
    from harness.llm import reconcile_ledger
    caller, _, _, log = make(tmp_path, [FakeHTTPError(402), reply()], model_ref=GATEWAY)
    with pytest.raises(LLMCallFailed):
        caller.call(MSGS, res())
    records, totals = reconcile_ledger(EventLog(log).read())
    assert totals["usd_complete"] is True and totals["usd"] == 0 and records[0]["status"] == "error"


class Mixed(Exception):
    """`.status_code` and `.response.status_code` disagree (the SDK sets both from one response, so this is theoretical): `.status_code` wins."""

    def __init__(self, own, response):
        super().__init__("mixed")
        self.status_code = own
        self.response = type("Resp", (), {"headers": {}, "status_code": response})()


@pytest.mark.parametrize("own,response,free", [(402, 500, True), (500, 402, False)])
def test_the_status_of_the_exception_itself_wins_over_the_one_on_its_response(tmp_path, own, response, free):
    caller, _, _, log = make(tmp_path, [Mixed(own, response)] * 3 + [reply()], model_ref=GATEWAY)
    with pytest.raises(LLMCallFailed):
        caller.call(MSGS, res())
    row = [x for x in ledger(log) if x["event"] == "llm_call"][0]
    assert (row["charged"] == "none") is free and row["http_status"] == own
