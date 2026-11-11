"""SPEC_FIX_B: a price must be usable numbers (E2). E1 (unknown cost charged at the worst case) is deferred, see the spec."""
import math
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from harness.llm import check_priced  # noqa: E402
from models.registry import ConfigError, ModelRef  # noqa: E402
from runner import load_config  # noqa: E402





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
