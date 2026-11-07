"""SPEC_RATE_LIMIT_RETRY: a 429 waits long (30 s doubling, at most 120 s), gets its own number of attempts, and a 429
answered by the gateway is not charged. Scripted fake model and a fake sleep: no network, no waiting, no cost."""
import copy
import json
import random
from datetime import datetime, timezone
from pathlib import Path

import pytest
from langchain_core.messages import HumanMessage

from harness.errors import LLMCallFailed
from harness.events import EventLog
from harness.llm import LLMCaller, Reservation
from models.fake import FakeHTTPError, ScriptedChatModel, reply
from models.registry import ConfigError
from runner import load_config

OFF_PEAK = datetime(2026, 10, 17, 2, tzinfo=timezone.utc)
MSGS = [HumanMessage("hello")]
GATEWAY = "openrouter:z-ai/glm-5.3"          # a paid gateway model listed in config.yaml


def make(tmp_path, script, *, model_ref=None, est_in=100, **llm):
    cfg = copy.deepcopy(load_config())
    cfg["llm"].update(llm)
    if model_ref:
        cfg["roles"]["worker"]["model"] = model_ref
        if model_ref.endswith(":free"):
            cfg["gateway"]["free_roles"] = ["worker"]
    waits = []
    fake = ScriptedChatModel(script=list(script))
    log = tmp_path / "e.jsonl"
    caller = LLMCaller(cfg, "worker", EventLog(log), model=fake, counter=lambda m, t: est_in, sleep=waits.append,
                       now=OFF_PEAK)
    return caller, fake, waits, log


def ledger(log):
    return [e for e in map(json.loads, Path(log).read_text(encoding="utf-8").splitlines())
            if e["event"] in ("llm_call_started", "llm_call")]


def res():
    return Reservation(tokens=10**7, usd=100.0)


# G1
def test_a_rate_limit_waits_30_seconds_doubling_up_to_120(tmp_path):
    random.seed(1)
    caller, fake, waits, _ = make(tmp_path, [FakeHTTPError(429)] * 3 + [reply()], rate_limit_attempts=4)
    caller.call(MSGS, res())
    assert len(waits) == 3
    for n, wait in enumerate(waits, start=1):
        assert 0.5 * 30 * 2 ** (n - 1) <= wait <= min(120, 1.5 * 30 * 2 ** (n - 1))


def test_the_120_second_bound_holds_for_every_jitter(tmp_path, monkeypatch):
    monkeypatch.setattr(random, "random", lambda: 0.999)
    caller, _, waits, _ = make(tmp_path, [FakeHTTPError(429)] * 3 + [reply()], rate_limit_attempts=4)
    caller.call(MSGS, res())
    assert waits[0] == pytest.approx(30 * 1.499) and waits[1] == pytest.approx(60 * 1.499) and waits[2] == 120


# G2
@pytest.mark.parametrize("after, expected", [(500, 120.0), (7, 7.0)])
def test_retry_after_wins_and_is_bounded_too(tmp_path, after, expected):
    caller, _, waits, _ = make(tmp_path, [FakeHTTPError(429, retry_after=after), reply()])
    caller.call(MSGS, res())
    assert waits == [expected]


# G3
@pytest.mark.parametrize("exc", [FakeHTTPError(500), FakeHTTPError(503), TimeoutError("t")])
def test_other_transient_errors_keep_the_short_delay(tmp_path, exc):
    caller, _, waits, _ = make(tmp_path, [exc, reply()], base_delay=1.0)
    caller.call(MSGS, res())
    assert len(waits) == 1 and 0.5 <= waits[0] <= 1.5


# G4
def test_a_rate_limit_gets_its_own_number_of_attempts(tmp_path):
    caller, fake, waits, _ = make(tmp_path, [FakeHTTPError(429)] * 9, attempts=3, rate_limit_attempts=4)
    with pytest.raises(LLMCallFailed, match="after 4 attempts"):
        caller.call(MSGS, res())
    assert len(fake.calls) == 4 and len(waits) == 3


def test_other_errors_keep_their_number_of_attempts(tmp_path):
    caller, fake, _, _ = make(tmp_path, [FakeHTTPError(500)] * 9, attempts=3, rate_limit_attempts=4)
    with pytest.raises(LLMCallFailed, match="after 3 attempts"):
        caller.call(MSGS, res())
    assert len(fake.calls) == 3


def test_rate_limits_and_other_errors_are_counted_apart(tmp_path):
    """Review: one kind's retries must not use up the other's, and a 429's backoff starts from its own count."""
    caller, fake, waits, _ = make(tmp_path, [FakeHTTPError(500), FakeHTTPError(500), FakeHTTPError(429),
                                             FakeHTTPError(429), FakeHTTPError(429), reply()],
                                  attempts=3, rate_limit_attempts=4, base_delay=1.0)
    caller.call(MSGS, res())
    assert len(fake.calls) == 6
    assert all(w <= 3 for w in waits[:2]) and 15 <= waits[2] <= 45 and 30 <= waits[3] <= 90


def test_two_429s_then_three_500s_fail_on_the_third_500(tmp_path):
    caller, fake, _, _ = make(tmp_path, [FakeHTTPError(429)] * 2 + [FakeHTTPError(500)] * 3 + [reply()],
                              attempts=3, rate_limit_attempts=4)
    with pytest.raises(LLMCallFailed, match="after 5 attempts"):
        caller.call(MSGS, res())
    assert len(fake.calls) == 5


def test_a_rate_limit_error_without_a_status_gets_the_long_wait(tmp_path):
    class RateLimitError(Exception):
        pass
    caller, _, waits, _ = make(tmp_path, [RateLimitError("slow down"), reply()])
    caller.call(MSGS, res())
    assert 15 <= waits[0] <= 45


def test_a_free_gateway_model_keeps_the_short_wait_and_three_attempts(tmp_path):
    """Review: a free model's chain falls back to the next free model, which is faster than waiting."""
    caller, fake, waits, _ = make(tmp_path, [FakeHTTPError(429)] * 9, attempts=3, base_delay=1.0,
                                  model_ref="openrouter:nvidia/nemotron-3.5-lightning:free")
    with pytest.raises(LLMCallFailed, match="after 3 attempts"):
        caller.call(MSGS, res())
    assert len(fake.calls) == 3 and all(w <= 3 for w in waits)


@pytest.mark.parametrize("after", ["-1", "nan", "inf"])
def test_a_retry_after_that_is_negative_or_not_finite_is_ignored(tmp_path, after):
    err = FakeHTTPError(429)
    err.response.headers = {"retry-after": after}
    caller, _, waits, _ = make(tmp_path, [err, reply()])
    caller.call(MSGS, res())
    assert 15 <= waits[0] <= 45


# G5
def test_a_gateway_rate_limit_is_not_charged_so_four_attempts_fit_a_one_attempt_cap(tmp_path):
    caller, fake, _, log = make(tmp_path, [FakeHTTPError(429)] * 3 + [reply(input_tokens=100, output_tokens=10)],
                                model_ref=GATEWAY, rate_limit_attempts=4)
    worst = caller._worst_usd(100, caller.max_output)
    r = Reservation(tokens=10**7, usd=worst * 1.5)          # room for one worst-case attempt, not two
    caller.call(MSGS, r)
    done = [e for e in ledger(log) if e["event"] == "llm_call"]
    assert [e["status"] for e in done] == ["transient_error"] * 3 + ["ok"]
    for e in done[:3]:
        assert e["charged"] == "none" and e["usd_nano"] == 0 and e["tokens"] == 0
        assert e["delivery"] == "received" and e["http_status"] == 429
    assert len(fake.calls) == 4 and r.used_usd == pytest.approx(done[3]["usd"])


# G6
def test_a_direct_provider_rate_limit_is_still_charged_worst_case(tmp_path):
    caller, _, _, log = make(tmp_path, [FakeHTTPError(429), reply()])
    assert caller.gateway is None
    r = res()
    caller.call(MSGS, r)
    first = [e for e in ledger(log) if e["event"] == "llm_call"][0]
    assert first["charged"] == "worst_case" and first["usd_nano"] > 0 and first["tokens"] > 0


def test_a_gateway_error_other_than_429_is_still_charged_worst_case(tmp_path):
    caller, _, _, log = make(tmp_path, [FakeHTTPError(503), reply()], model_ref=GATEWAY)
    caller.call(MSGS, res())
    first = [e for e in ledger(log) if e["event"] == "llm_call"][0]
    assert first["charged"] == "worst_case" and first["usd_nano"] > 0


# G7
def test_every_attempt_is_started_then_recorded_also_when_not_charged(tmp_path):
    caller, _, _, log = make(tmp_path, [FakeHTTPError(429)] * 2 + [reply()], model_ref=GATEWAY)
    caller.call(MSGS, res())
    events = ledger(log)
    assert [e["event"] for e in events] == ["llm_call_started", "llm_call"] * 3
    assert [e["call_id"] for e in events[0::2]] == [e["call_id"] for e in events[1::2]]


# G8
@pytest.mark.parametrize("bad", [{"rate_limit_delay_s": -1}, {"rate_limit_attempts": 0},
                                 {"rate_limit_delay_s": 30, "rate_limit_max_delay_s": 10},
                                 {"rate_limit_attempts": "four"}, {"rate_limit_delay_s": True},
                                 {"rate_limit_max_delay_s": float("inf")}, {"rate_limit_delay_s": float("nan")},
                                 {"attempts": 0}, {"base_delay": -1}])
def test_a_bad_rate_limit_setting_is_refused_before_anything_is_sent(tmp_path, bad):
    with pytest.raises(ConfigError, match="llm\\."):
        make(tmp_path, [reply()], **bad)


def test_config_yaml_has_the_approved_defaults():
    llm = load_config()["llm"]
    assert (llm["rate_limit_delay_s"], llm["rate_limit_max_delay_s"], llm["rate_limit_attempts"]) == (30, 120, 4)
