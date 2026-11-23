"""PENDING_PRIORITAS 2 (NEXUS-lite pilot, stage 4 issue 3): a provider failure shows its HTTP status and what it usually means, never the provider's own
text; and the bill of a refusal is pinned as it is. Scripted fake model: no network, no cost."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_drafter as td  # noqa: E402
from test_drafter import root  # noqa: E402,F401  (the fixture)

from codetask import drafter as dt  # noqa: E402
from harness.errors import LLMCallFailed
from harness.llm import provider_failure_reason
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

@pytest.mark.parametrize("status", [401, 402])
def test_a_gateway_401_or_402_is_still_charged_worst_case_until_atha_decides_otherwise(tmp_path, status):
    """PENDING_PRIORITAS 2, open question for Atha: the pilot booked a 402 at $0.0645 that OpenRouter very likely never billed. Only a 429 is not charged
    (SPEC_RATE_LIMIT_RETRY R3, decided by Atha); this pins today's rule for 401 and 402 so that changing it is a deliberate act."""
    caller, fake, _, log = make(tmp_path, [FakeHTTPError(status, "refused"), reply()], model_ref=GATEWAY)
    r = res()
    with pytest.raises(LLMCallFailed) as e:
        caller.call(MSGS, r)
    done = [x for x in ledger(log) if x["event"] == "llm_call"]
    assert len(done) == 1 and len(fake.calls) == 1                       # not retried
    assert done[0]["charged"] == "worst_case" and done[0]["usd_nano"] > 0 and done[0]["http_status"] == status
    assert e.value.__cause__.status_code == status


@pytest.mark.parametrize("status", [403, 404, 500])
def test_a_gateway_answer_that_may_have_run_the_model_is_still_charged_worst_case(tmp_path, status):
    caller, _, _, log = make(tmp_path, [FakeHTTPError(status), FakeHTTPError(status), FakeHTTPError(status), reply()], model_ref=GATEWAY)
    with pytest.raises((LLMCallFailed, Exception)):
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
