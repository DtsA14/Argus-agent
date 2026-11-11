"""SPEC_FIX_B: an unknown cost is never free to the cap (E1), and a price must be usable numbers (E2)."""
import copy
import math
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from harness.llm import Reservation, check_priced, reconcile_ledger  # noqa: E402
from models.registry import ConfigError, ModelRef  # noqa: E402
from runner import load_config  # noqa: E402
from test_prompt_cache import MSGS, caller, cfg, ledger, with_usage  # noqa: E402


def unpriced_write_cfg():
    """fake:scripted priced without a cache-write rate: a reply that reports a cache write cannot be costed."""
    c = cfg(cache=False)
    c["prices"]["fake:scripted"] = {"input": 1.00, "output": 5.00, "cache_read": 0.10}
    return c


def test_a_call_whose_cost_cannot_be_computed_is_charged_its_worst_case_and_the_ledger_says_so(tmp_path):
    from models.fake import ScriptedChatModel
    model = ScriptedChatModel(script=[with_usage(total_in=1000, out=10, creation=100)])
    c, log = caller(unpriced_write_cfg(), model, tmp=tmp_path)
    res = Reservation(tokens=100_000, usd=1.0)
    c.call(MSGS, res)
    (started,) = ledger(log, "llm_call_started")
    (done,) = ledger(log)
    assert done["charged"] == "worst_case_unknown_cost" and done["usd_nano"] == started["worst_usd_nano"] > 0
    assert res.used_nano == started["worst_usd_nano"]
    assert reconcile_ledger(log.read())[1]["usd_nano"] == res.used_nano      # a resume counts what the run charged


def test_a_known_cost_is_still_charged_as_it_was(tmp_path):
    from models.fake import ScriptedChatModel
    model = ScriptedChatModel(script=[with_usage(total_in=1000, out=10)])
    c, log = caller(unpriced_write_cfg(), model, tmp=tmp_path)
    res = Reservation(tokens=100_000, usd=1.0)
    c.call(MSGS, res)
    (done,) = ledger(log)
    assert done["charged"] == "actual" and 0 < done["usd_nano"] < ledger(log, "llm_call_started")[0]["worst_usd_nano"]


def test_an_unpriced_model_without_a_finite_budget_keeps_a_null_cost_and_charges_nothing(tmp_path):
    from models.fake import ScriptedChatModel
    conf = cfg(cache=False)
    conf["prices"].pop("fake:scripted")
    conf["budget"]["max_usd"] = None
    conf["budget"]["allow_unpriced"] = True
    model = ScriptedChatModel(script=[with_usage(total_in=1000, out=10)])
    c, log = caller(conf, model, tmp=tmp_path)
    res = Reservation(tokens=100_000, usd=math.inf)
    c.call(MSGS, res)
    (done,) = ledger(log)
    assert done["usd_nano"] is None and res.used_nano == 0 and done["charged"] == "actual"


@pytest.mark.parametrize("bad", [-1, -0.0001, math.nan, math.inf, True, "1.0"])
@pytest.mark.parametrize("key", ["input", "output", "cache_read"])
def test_a_rate_that_is_not_a_usable_number_is_always_refused(key, bad):
    conf = load_config()
    conf["prices"]["deepseek:deepseek-flash"] = {"input": 0.15, "output": 0.60, "cache_read": 0.003, key: bad}
    for limit in (0.5, None):
        conf["budget"]["max_usd"] = limit
        with pytest.raises(ConfigError, match="price"):
            check_priced(conf, ModelRef.parse("deepseek:deepseek-flash"), "t")


@pytest.mark.parametrize("zero", ["input", "output"])
def test_a_zero_input_or_output_price_on_a_direct_provider_is_refused_with_a_finite_budget(zero):
    conf = load_config()
    conf["prices"]["deepseek:deepseek-flash"] = {"input": 0.15, "output": 0.60, zero: 0}
    with pytest.raises(ConfigError, match="would cost nothing to the cap"):
        check_priced(conf, ModelRef.parse("deepseek:deepseek-flash"), "t")
    conf["budget"]["max_usd"] = None                       # no cap to be vacuous
    check_priced(conf, ModelRef.parse("deepseek:deepseek-flash"), "t")


def test_a_zero_cache_read_rate_is_allowed():
    conf = load_config()
    conf["prices"]["deepseek:deepseek-flash"] = {"input": 0.15, "output": 0.60, "cache_read": 0}
    check_priced(conf, ModelRef.parse("deepseek:deepseek-flash"), "t")


def test_every_configured_price_still_passes_and_a_free_gateway_model_is_not_refused():
    conf = load_config()
    for name in conf["prices"]:
        check_priced(conf, ModelRef.parse(name), "t")
    free = [n for n in conf["prices"] if conf["prices"][n].get("input") == 0 and n.startswith("openrouter:")]
    assert free, "the configuration is expected to carry free gateway models"


def test_an_unset_input_or_output_rate_is_refused_but_an_unset_cache_rate_means_unknown():
    conf = load_config()
    ref = ModelRef.parse("deepseek:deepseek-flash")
    conf["prices"]["deepseek:deepseek-flash"] = {"input": None, "output": 0.60}
    with pytest.raises(ConfigError, match="price"):
        check_priced(conf, ref, "t")
    conf["prices"]["deepseek:deepseek-flash"] = {"input": 0.15, "output": 0.60, "cache_read": None}
    check_priced(conf, ref, "t")


def test_when_the_estimate_missed_the_charge_is_the_real_usage_at_the_highest_write_rate(tmp_path):
    from models.fake import ScriptedChatModel
    conf = cfg(cache=False)
    conf["prices"]["fake:scripted"] = {"input": 1.00, "output": 5.00, "cache_read": 0.10, "cache_write_1h": 2.00}
    model = ScriptedChatModel(script=[with_usage(total_in=60_000, out=10, creation=50_000)])   # a 5-minute write: no rate
    c, log = caller(conf, model, counter=lambda m, t: 10, tmp=tmp_path)                        # the estimate was 10 tokens
    res = Reservation(tokens=1_000_000, usd=10.0)
    c.call(MSGS, res)
    (started,) = ledger(log, "llm_call_started")
    (done,) = ledger(log)
    real = (10_000 * 1.00 + 50_000 * 2.00 + 10 * 5.00) / 1e6
    assert done["charged"] == "worst_case_unknown_cost" and done["usd_nano"] >= round(real * 1e9) > started["worst_usd_nano"]
    assert res.used_nano == done["usd_nano"]


@pytest.mark.parametrize("bad", [0, 0.5, -1, math.nan, math.inf, True, "2"])
def test_a_peak_multiplier_below_one_or_not_a_number_is_refused(bad):
    conf = load_config()
    conf["prices"]["deepseek:deepseek-flash"] = {"input": 0.15, "output": 0.60, "peak_multiplier": bad}
    with pytest.raises(ConfigError, match="peak multiplier"):
        check_priced(conf, ModelRef.parse("deepseek:deepseek-flash"), "t")


@pytest.mark.parametrize("bad", [0, -1, math.nan, True, "100000"])
def test_a_long_context_threshold_must_be_a_positive_number(bad):
    conf = load_config()
    conf["prices"]["deepseek:deepseek-flash"] = {"input": 0.15, "output": 0.60, "long_context_above": bad}
    with pytest.raises(ConfigError, match="long-context threshold"):
        check_priced(conf, ModelRef.parse("deepseek:deepseek-flash"), "t")


@pytest.mark.parametrize("missing", ["input", "output"])
def test_a_price_without_an_input_or_output_rate_is_refused(missing):
    conf = load_config()
    price = {"input": 0.15, "output": 0.60}
    price.pop(missing)
    conf["prices"]["deepseek:deepseek-flash"] = price
    with pytest.raises(ConfigError, match=f"no '{missing}'"):
        check_priced(conf, ModelRef.parse("deepseek:deepseek-flash"), "t")


def test_the_unknown_cost_charge_uses_the_peak_multiplier_even_when_the_call_ended_off_peak(tmp_path):
    from datetime import datetime, timezone
    from models.fake import ScriptedChatModel
    off_peak = datetime(2026, 10, 17, 2, tzinfo=timezone.utc)                 # a Saturday: no peak window
    conf = cfg(cache=False)
    conf["roles"]["coder"]["model"] = "deepseek:deepseek-flash"               # priced with peak_multiplier 2, no write rate
    model = ScriptedChatModel(script=[with_usage(total_in=200_000, out=10, creation=150_000)])
    from harness.events import EventLog
    from harness.llm import LLMCaller
    log = EventLog(tmp_path / "e.jsonl")
    c = LLMCaller(conf, "coder", log, model=model, counter=lambda m, t: 10, now=off_peak)
    c.call(MSGS, Reservation(tokens=10_000_000, usd=10.0))
    (done,) = ledger(log)
    price = conf["prices"]["deepseek:deepseek-flash"]
    assert price["peak_multiplier"] == 2 and done["charged"] == "worst_case_unknown_cost" and done["peak"] is False
    real_at_peak = (50_000 * price["input"] + 150_000 * price["input"] + 10 * price["output"]) / 1e6 * 2
    assert done["usd_nano"] >= round(real_at_peak * 1e9)
