from datetime import datetime, timezone

import pytest
from langchain_core.messages import AIMessage

from models.pricing import cost_usd, is_peak
from models.registry import (
    BUILDERS, ConfigError, MissingApiKey, ModelRef, apply_overrides, build_chat_model,
    message_cost, parse_overrides, register_kind, role_warnings,
)
from runner import load_config

KEYS = ("ANTHROPIC_API_KEY", "OPENAI_API_KEY", "DEEPSEEK_API_KEY", "TOGETHER_API_KEY")


@pytest.fixture
def keys(monkeypatch):
    for k in KEYS:
        monkeypatch.setenv(k, "test-key")


def utc(y, m, d, h):
    return datetime(y, m, d, h, tzinfo=timezone.utc)


# ---- building models --------------------------------------------------------

def test_default_roles_build_without_network(keys):
    from langchain_anthropic import ChatAnthropic
    from langchain_openai import ChatOpenAI
    cfg = load_config()
    assert isinstance(build_chat_model(cfg, "orchestrator"), ChatAnthropic)
    assert isinstance(build_chat_model(cfg, "worker"), ChatAnthropic)
    assert isinstance(build_chat_model(cfg, "evaluator"), ChatOpenAI)


def test_deepseek_role_builds(keys):
    from langchain_deepseek import ChatDeepSeek
    cfg = apply_overrides(load_config(), parse_overrides(["worker=deepseek:deepseek-flash"]))
    model = build_chat_model(cfg, "worker")
    assert isinstance(model, ChatDeepSeek)
    assert model.model_name == "deepseek-flash"


def test_missing_key_names_the_env_var(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with pytest.raises(MissingApiKey, match="ANTHROPIC_API_KEY"):
        build_chat_model(load_config(), "worker")


# ---- swapping and adding ----------------------------------------------------

def test_swap_model_for_a_role_leaves_original_untouched():
    cfg = load_config()
    swapped = apply_overrides(cfg, parse_overrides(["worker=deepseek:deepseek-flash"]))
    assert swapped["roles"]["worker"]["model"] == "deepseek:deepseek-flash"
    assert cfg["roles"]["worker"]["model"] == "anthropic:claude-haiku-5-5"


def test_override_errors_are_clear():
    cfg = load_config()
    with pytest.raises(ConfigError, match="unknown role"):
        apply_overrides(cfg, {"janitor": "anthropic:x"})
    with pytest.raises(ConfigError, match="unknown provider"):
        apply_overrides(cfg, {"worker": "nope:x"})
    with pytest.raises(ConfigError):
        parse_overrides(["worker"])
    with pytest.raises(ConfigError):
        ModelRef.parse("no-colon")


def test_new_openai_style_provider_needs_no_code(keys):
    cfg = load_config()
    cfg["providers"]["together"] = {
        "kind": "openai_compatible",
        "api_key_env": "TOGETHER_API_KEY",
        "base_url": "https://api.together.xyz/v1",
    }
    cfg["roles"]["worker"]["model"] = "together:some/model"
    model = build_chat_model(cfg, "worker")
    assert model.openai_api_base == "https://api.together.xyz/v1"
    assert model.model_name == "some/model"


def test_new_provider_kind_can_be_registered(keys):
    @register_kind("echo")
    def _echo(ref, pcfg, params):
        return ("echo", ref.model, params)

    try:
        cfg = load_config()
        cfg["providers"]["mine"] = {"kind": "echo"}
        cfg["roles"]["worker"] = {"model": "mine:m1", "params": {"max_tokens": 5}}
        # max_retries=0 is always injected: SDK-internal retries would be billed outside the ledger
        assert build_chat_model(cfg, "worker") == ("echo", "m1", {"max_tokens": 5, "max_retries": 0})
    finally:
        BUILDERS.pop("echo")


def test_warns_when_evaluator_shares_the_workers_provider():
    cfg = load_config()
    assert role_warnings(cfg) == []
    same = apply_overrides(cfg, {"evaluator": "anthropic:claude-sonnet-5-5"})
    assert any("evaluator" in w for w in role_warnings(same))


# ---- pricing ----------------------------------------------------------------

def test_cost_of_a_plain_call():
    price = load_config()["prices"]["anthropic:claude-haiku-5-5"]
    assert cost_usd(price, input_tokens=1_000_000, output_tokens=1_000_000) == pytest.approx(0.60)


def test_unknown_price_is_none_not_a_guess():
    assert cost_usd(None, input_tokens=10, output_tokens=10) is None
    assert cost_usd({"input": None, "output": None}, input_tokens=10, output_tokens=10) is None


def test_cached_tokens_use_the_cache_rate():
    price = load_config()["prices"]["deepseek:deepseek-flash"]
    off_peak = utc(2026, 10, 17, 2)  # Saturday
    cost = cost_usd(price, input_tokens=1_000_000, output_tokens=0, cache_read_tokens=1_000_000, now=off_peak)
    assert cost == pytest.approx(0.003)


def test_deepseek_peak_windows():
    window = load_config()["peak_windows"]["deepseek"]
    assert is_peak(window, utc(2026, 10, 12, 1))       # Mon 01:00 UTC = 08:00 WIB
    assert is_peak(window, utc(2026, 10, 12, 3))
    assert not is_peak(window, utc(2026, 10, 12, 4))   # end is exclusive
    assert not is_peak(window, utc(2026, 10, 12, 5))
    assert is_peak(window, utc(2026, 10, 12, 6))       # Mon 06:00 UTC = 13:00 WIB
    assert not is_peak(window, utc(2026, 10, 12, 10))
    assert not is_peak(window, utc(2026, 10, 17, 2))   # Saturday is never peak


def test_peak_doubles_the_price():
    cfg = load_config()
    price, window = cfg["prices"]["deepseek:deepseek-flash"], cfg["peak_windows"]["deepseek"]
    kw = dict(input_tokens=1_000_000, output_tokens=1_000_000, window=window)
    peak = cost_usd(price, now=utc(2026, 10, 12, 2), **kw)
    off = cost_usd(price, now=utc(2026, 10, 12, 5), **kw)
    assert off == pytest.approx(0.75) and peak == pytest.approx(1.50)


def test_message_cost_reads_usage_and_cache_from_the_message():
    msg = AIMessage(content="", usage_metadata={
        "input_tokens": 100, "output_tokens": 20, "total_tokens": 120,
        "input_token_details": {"cache_read": 40},
    })
    cost = message_cost(load_config(), ModelRef("anthropic", "claude-haiku-5-5"), msg)
    assert cost == pytest.approx((60 * 0.10 + 40 * 0.01 + 20 * 0.50) / 1_000_000)
    assert message_cost(load_config(), ModelRef("openai", "gpt-5.6-sol"), msg) is None
