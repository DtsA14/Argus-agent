"""Phase 2a: the LLM wrapper enforces the budget per request, before any cost is incurred.
All tests use a scripted fake model: no network, no API key, no cost."""
import copy
import json
import random
from datetime import datetime, timezone
from pathlib import Path

import pytest
from langchain_core.messages import HumanMessage

from harness.budget import Budget, iteration_usd, next_iteration_blocker, node_usd_estimates
from harness.errors import LLMCallFailed, ReservationExhausted
from harness.events import EventLog
from harness.llm import LLMCaller, Reservation, is_transient, prompt_hash
from models.fake import FakeHTTPError, ScriptedChatModel, reply
from models.registry import ConfigError, build_chat_model
from runner import load_config, run_task

OFF_PEAK = datetime(2026, 10, 17, 2, tzinfo=timezone.utc)   # Saturday
PEAK = datetime(2026, 10, 12, 2, tzinfo=timezone.utc)       # Monday 02:00 UTC
MSGS = [HumanMessage("hello")]
HAIKU = {"input": 0.10, "output": 0.50, "cache_read": 0.01}


def events(path):
    return [json.loads(l) for l in Path(path).read_text(encoding="utf-8").splitlines()]


def calls(path, status=None):
    return [e for e in events(path) if e["event"] == "llm_call" and (status is None or e["status"] == status)]


def make(tmp_path, script, *, est_in=100, role="worker", model_ref=None, now=OFF_PEAK, **llm):
    cfg = copy.deepcopy(load_config())
    cfg["llm"].update({"base_delay": 0, **llm})
    if model_ref:
        cfg["roles"][role]["model"] = model_ref
    fake = ScriptedChatModel(script=list(script))
    log = EventLog(tmp_path / "e.jsonl")
    caller = LLMCaller(cfg, role, log, model=fake, counter=lambda m, t: est_in, sleep=lambda s: None, now=now)
    return caller, fake, tmp_path / "e.jsonl"


# ---- refusal happens before anything is sent ---------------------------------

def test_request_that_cannot_fit_is_refused_before_sending(tmp_path):
    caller, fake, log = make(tmp_path, [reply()], est_in=1000)
    res = Reservation(tokens=1000 + 63, usd=1.0)   # 63 < min_output_tokens (64)
    with pytest.raises(ReservationExhausted):
        caller.call(MSGS, res)
    assert fake.calls == []                        # nothing reached the provider
    assert res.used_tokens == 0 and res.used_usd == 0
    assert [e["status"] for e in calls(log)] == ["refused"]


def test_usd_alone_can_refuse(tmp_path):
    caller, fake, _ = make(tmp_path, [reply()], est_in=100)
    # plenty of tokens, but $ left only covers the input plus a handful of output tokens
    res = Reservation(tokens=10**9, usd=(100 * 0.10 + 10 * 0.50) / 1e6)
    with pytest.raises(ReservationExhausted):
        caller.call(MSGS, res)
    assert fake.calls == []


# ---- the output cap sent to the model ------------------------------------------

@pytest.mark.parametrize("tokens, usd, expected", [
    (10**9, 10.0, 2048),                                   # role max_output_tokens
    (100 + 500, 10.0, 500),                                # tokens left after input
    (10**9, (100 * 0.10 + 300 * 0.50) / 1e6, 300),         # USD left after input
])
def test_max_tokens_is_the_tightest_limit(tmp_path, tokens, usd, expected):
    caller, fake, _ = make(tmp_path, [reply(input_tokens=100, output_tokens=10)], est_in=100)
    caller.call(MSGS, Reservation(tokens=tokens, usd=usd))
    assert fake.calls[0]["kwargs"]["max_tokens"] == expected


def test_peak_hours_halve_the_output_cap_for_deepseek(tmp_path):
    usd = (100 * 0.15 + 1000 * 0.60) / 1e6
    off, f1, _ = make(tmp_path / "a", [reply()], est_in=100, model_ref="deepseek:deepseek-flash", now=OFF_PEAK)
    peak, f2, _ = make(tmp_path / "b", [reply()], est_in=100, model_ref="deepseek:deepseek-flash", now=PEAK)
    off.call(MSGS, Reservation(tokens=10**9, usd=usd))
    peak.call(MSGS, Reservation(tokens=10**9, usd=usd))
    assert f1.calls[0]["kwargs"]["max_tokens"] == 1000                        # (615 - 15) / 0.60
    assert f2.calls[0]["kwargs"]["max_tokens"] == int((615 - 2 * 15) / 1.20)  # 487: input and output both doubled


# ---- charging and the ledger -----------------------------------------------------

def test_actual_usage_is_charged_and_logged(tmp_path):
    caller, _, log = make(tmp_path, [reply(input_tokens=90, output_tokens=40, cache_read=50)], est_in=100)
    res = Reservation(tokens=10_000, usd=1.0)
    caller.call(MSGS, res)
    expected_usd = (40 * 0.10 + 50 * 0.01 + 40 * 0.50) / 1e6
    assert res.used_tokens == 130 and res.used_usd == pytest.approx(expected_usd)
    (e,) = calls(log)
    assert e["status"] == "ok" and e["charged"] == "actual" and e["tokens"] == 130
    assert e["usd"] == pytest.approx(expected_usd)


def test_missing_usage_is_charged_as_worst_case(tmp_path):
    caller, fake, log = make(tmp_path, [reply(usage=False)], est_in=100)
    res = Reservation(tokens=10_000, usd=1.0)
    caller.call(MSGS, res)
    cap = fake.calls[0]["kwargs"]["max_tokens"]
    assert res.used_tokens == 100 + cap
    assert calls(log)[0]["charged"] == "worst_case_no_usage"


def test_estimate_miss_is_logged(tmp_path):
    caller, _, log = make(tmp_path, [reply(input_tokens=150, output_tokens=5)], est_in=100)
    caller.call(MSGS, Reservation(tokens=10_000, usd=1.0))
    miss = [e for e in events(log) if e["event"] == "estimate_miss"]
    assert miss and miss[0]["input_tokens"] == 150 and miss[0]["est_input"] == 100


# ---- retries ---------------------------------------------------------------------

def test_transient_error_is_retried_and_every_attempt_is_charged(tmp_path):
    caller, fake, log = make(tmp_path, [FakeHTTPError(429), reply(input_tokens=100, output_tokens=10)], est_in=100)
    res = Reservation(tokens=100_000, usd=1.0)
    caller.call(MSGS, res)
    statuses = [e["status"] for e in calls(log)]
    assert statuses == ["transient_error", "ok"]
    first_cap = fake.calls[0]["kwargs"]["max_tokens"]
    assert res.used_tokens == (100 + first_cap) + 110     # failed attempt charged at worst case
    assert res.used_tokens == sum(e["tokens"] for e in calls(log))


def test_retry_is_refused_when_the_failed_attempt_used_up_the_reservation(tmp_path):
    caller, fake, log = make(tmp_path, [FakeHTTPError(503), reply()], est_in=100)
    res = Reservation(tokens=100 + 2048 + 100, usd=1.0)   # enough for exactly one worst-case attempt
    with pytest.raises(ReservationExhausted):
        caller.call(MSGS, res)
    assert len(fake.calls) == 1                            # the retry was never sent
    assert [e["status"] for e in calls(log)] == ["transient_error", "refused"]
    assert res.used_tokens <= res.tokens


def test_permanent_error_is_not_retried(tmp_path):
    caller, fake, log = make(tmp_path, [FakeHTTPError(400), reply()], est_in=100)
    with pytest.raises(LLMCallFailed):
        caller.call(MSGS, Reservation(tokens=100_000, usd=1.0))
    assert len(fake.calls) == 1 and [e["status"] for e in calls(log)] == ["error"]


def test_gives_up_after_max_attempts(tmp_path):
    caller, fake, log = make(tmp_path, [FakeHTTPError(500)] * 5, est_in=100, attempts=3)
    with pytest.raises(LLMCallFailed):
        caller.call(MSGS, Reservation(tokens=10**6, usd=10.0))
    assert len(fake.calls) == 3


def test_retry_after_header_is_respected(tmp_path):
    waits = []
    cfg = copy.deepcopy(load_config())
    fake = ScriptedChatModel(script=[FakeHTTPError(429, retry_after=7), reply()])
    caller = LLMCaller(cfg, "worker", EventLog(tmp_path / "e.jsonl"), model=fake,
                       counter=lambda m, t: 10, sleep=waits.append, now=OFF_PEAK)
    caller.call(MSGS, Reservation(tokens=10**6, usd=10.0))
    assert waits == [7.0]


@pytest.mark.parametrize("exc, transient", [
    (FakeHTTPError(429), True), (FakeHTTPError(500), True), (FakeHTTPError(529), True),
    (FakeHTTPError(408), True), (FakeHTTPError(400), False), (FakeHTTPError(401), False),
    (FakeHTTPError(404), False), (TimeoutError("t"), True), (ValueError("v"), False),
])
def test_error_classification(exc, transient):
    assert is_transient(exc) is transient


# ---- the budget invariant under random sequences ---------------------------------

@pytest.mark.parametrize("seed", range(40))
def test_reservation_is_never_exceeded(tmp_path, seed):
    """Random mixes of successes, transient and permanent errors, missing usage and tight budgets.
    As long as the input count is not an underestimate, charges never exceed the reservation."""
    rng = random.Random(seed)
    est_in = rng.randint(10, 500)
    script = []
    for _ in range(30):
        r = rng.random()
        if r < 0.2:
            script.append(FakeHTTPError(rng.choice([429, 500, 503])))
        elif r < 0.25:
            script.append(FakeHTTPError(400))
        elif r < 0.3:
            script.append(reply(usage=False))
        else:
            # providers bill input <= our (non-underestimating) count, output <= max_tokens
            script.append(reply(input_tokens=rng.randint(1, est_in), output_tokens=rng.randint(0, 64)))
    caller, fake, log = make(tmp_path, script, est_in=est_in, model_ref=rng.choice(
        ["anthropic:claude-haiku-5-5", "anthropic:claude-sonnet-5-5", "deepseek:deepseek-flash"]),
        now=rng.choice([PEAK, OFF_PEAK]))
    res = Reservation(tokens=rng.randint(0, 20_000), usd=rng.uniform(0, 0.02))
    for _ in range(15):
        try:
            caller.call(MSGS, res)
        except (ReservationExhausted, LLMCallFailed):
            pass
        assert res.used_tokens <= res.tokens
        assert res.used_usd <= res.usd + 1e-12
        for c in fake.calls:  # the output cap actually sent never exceeded what was left
            assert c["kwargs"]["max_tokens"] >= 64
    ledger = calls(log)
    assert sum(e.get("tokens", 0) for e in ledger) == res.used_tokens
    assert sum(e.get("usd", 0) for e in ledger) == pytest.approx(res.used_usd, abs=1e-8)
    assert len([e for e in ledger if e["status"] != "refused"]) == len(fake.calls)


# ---- configuration safety ---------------------------------------------------------

def test_unpriced_model_is_refused_unless_allowed(tmp_path):
    cfg = copy.deepcopy(load_config())
    cfg["roles"]["worker"]["model"] = "openai:gpt-5.6-sol"     # no price in config
    with pytest.raises(ConfigError, match="no price"):
        LLMCaller(cfg, "worker", EventLog(tmp_path / "e.jsonl"), model=ScriptedChatModel())
    cfg["budget"]["allow_unpriced"] = True
    LLMCaller(cfg, "worker", EventLog(tmp_path / "e.jsonl"), model=ScriptedChatModel())


def test_prompts_are_hashed_and_full_mode_needs_dev_flag(tmp_path, monkeypatch):
    secret = "client revenue 12345678"
    caller, _, log = make(tmp_path, [reply()], est_in=10)
    caller.call([HumanMessage(secret)], Reservation(tokens=10**6, usd=1.0))
    text = Path(log).read_text()
    assert secret not in text and prompt_hash([HumanMessage(secret)], None) in text

    monkeypatch.delenv("ARGUS_DEV", raising=False)
    cfg = copy.deepcopy(load_config())
    cfg["logging"]["prompts"] = "full"
    caller = LLMCaller(cfg, "worker", EventLog(tmp_path / "f.jsonl"), model=ScriptedChatModel(script=[reply()]),
                       counter=lambda m, t: 10, now=OFF_PEAK)
    caller.call([HumanMessage(secret)], Reservation(tokens=10**6, usd=1.0))
    assert secret not in (tmp_path / "f.jsonl").read_text()         # refused without ARGUS_DEV=1

    monkeypatch.setenv("ARGUS_DEV", "1")
    caller = LLMCaller(cfg, "worker", EventLog(tmp_path / "g.jsonl"), model=ScriptedChatModel(script=[reply()]),
                       counter=lambda m, t: 10, now=OFF_PEAK)
    caller.call([HumanMessage(secret)], Reservation(tokens=10**6, usd=1.0))
    assert secret in (tmp_path / "g.jsonl").read_text()


@pytest.mark.parametrize("ref", ["anthropic:claude-haiku-5-5", "openai:gpt-5.6-sol", "deepseek:deepseek-flash"])
def test_real_provider_classes_receive_the_cap_and_no_hidden_retries(monkeypatch, ref):
    """Builds the real LangChain class (no network) and inspects the request it would send."""
    for k in ("ANTHROPIC_API_KEY", "OPENAI_API_KEY", "DEEPSEEK_API_KEY"):
        monkeypatch.setenv(k, "test-key")
    cfg = copy.deepcopy(load_config())
    cfg["roles"]["worker"]["model"] = ref
    model = build_chat_model(cfg, "worker")
    assert model.max_retries == 0
    payload = model._get_request_payload(MSGS, max_tokens=321)
    # Chat Completions uses max_tokens / max_completion_tokens; newer OpenAI models go through the
    # Responses API, where LangChain maps the same cap to max_output_tokens.
    caps = {k: payload[k] for k in ("max_tokens", "max_completion_tokens", "max_output_tokens") if k in payload}
    assert list(caps.values()) == [321], payload


# ---- run-level USD reservation ------------------------------------------------------

def test_node_usd_estimates_use_the_dearer_rate_and_peak():
    cfg = load_config()
    est = node_usd_estimates(cfg)
    assert est["orchestrator"] == pytest.approx(3000 * 10.00 / 1e6)   # Sonnet output rate
    assert est["worker"] == pytest.approx(2000 * 0.50 / 1e6)          # Haiku output rate
    assert est["synthesize"] == est["evaluator"] == 0.0               # no model calls in M2
    ds = copy.deepcopy(cfg)
    ds["roles"]["worker"]["model"] = "deepseek:deepseek-flash"
    assert node_usd_estimates(ds)["worker"] == pytest.approx(2000 * 0.60 * 2 / 1e6)


def test_unpriced_llm_node_fails_at_build():
    cfg = copy.deepcopy(load_config())
    cfg["roles"]["worker"]["model"] = "openai:gpt-5.6-sol"
    with pytest.raises(ConfigError):
        node_usd_estimates(cfg)


def test_usd_blocker():
    b = Budget(max_iterations=9, max_tokens=10**9, max_seconds=999, stagnation_rounds=9, max_usd=0.10)
    kw = dict(iteration=0, tokens_used=0, elapsed_s=0, iteration_tokens=1)
    assert next_iteration_blocker(b, usd_used=0.05, iteration_usd=0.05, **kw) is None
    assert next_iteration_blocker(b, usd_used=0.05, iteration_usd=0.0501, **kw) == "max_usd"


@pytest.mark.parametrize("max_usd", [0.0, 0.01, 0.0329, 0.033, 0.05, 0.1, 0.5])
def test_run_refuses_iterations_that_do_not_fit_the_usd_budget(tmp_path, max_usd):
    cfg = copy.deepcopy(load_config())
    cfg["budget"].update(max_usd=max_usd, stagnation_rounds=99, max_iterations=99, max_tokens=10**9)
    per_iter = iteration_usd(node_usd_estimates(cfg), 3)                # 0.033 with default roles
    r = run_task(goal="x", scenario="never_pass", run_id="t", runs_dir=tmp_path, cfg=cfg)
    assert r["status"] == "FAILED_BUDGET" and r["stop_reason"] == "max_usd"
    assert r["iteration"] == int(max_usd / per_iter + 1e-9)            # as many iterations as fit, no more
    assert r["usd_used"] <= max_usd + 1e-12                            # never over
    assert r["usd_used"] + per_iter > max_usd                          # stopped only when the next would not fit
