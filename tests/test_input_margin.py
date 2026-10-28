"""SPEC_HEURISTIC_INPUT_MARGIN: a heuristic input margin per model (router: DeepSeek 2.5), and large_usd's token ceiling.
sympy-24562's dev retry: estimate 33,003, billed 45,296 input, 184 tokens over a 400,000-token attempt at $0.036 of $0.45."""
import copy

from langchain_core.messages import HumanMessage

import harness.llm as hl
from harness.events import EventLog
from models.fake import ScriptedChatModel
from router import job as rj
from runner import load_config

DEEPSEEK = "deepseek:deepseek-flash"
MSGS = [HumanMessage("x" * 30_000)]


def caller(tmp_path, cfg, model_ref=DEEPSEEK, role="coder"):
    cfg = copy.deepcopy(cfg)
    cfg["roles"][role]["model"] = model_ref
    return hl.LLMCaller(cfg, role, EventLog(tmp_path / "e.jsonl"), model=ScriptedChatModel(script=[]))


def router_cfg():
    return rj.stage_config(load_config(), 1.0)


def test_the_router_counts_deepseek_with_margin_2_5_and_config_yaml_keeps_1_2(tmp_path):
    base = caller(tmp_path, load_config())
    routed = caller(tmp_path, router_cfg())
    assert not base.exact and not routed.exact
    assert base.count(MSGS, None) == hl.heuristic_counter(1.2)[0](MSGS, None)
    assert routed.count(MSGS, None) == hl.heuristic_counter(2.5)[0](MSGS, None)


def test_a_model_without_an_entry_keeps_input_margin(tmp_path):
    cfg = router_cfg()
    cfg["llm"]["input_margin_by_model"] = {"some:other-model": 9.0}
    c = caller(tmp_path, cfg)
    assert c.count(MSGS, None) == hl.heuristic_counter(1.2)[0](MSGS, None)


def test_the_24562_step_is_refused_before_sending_instead_of_overrunning(tmp_path):
    """Step 18 as recorded: 46,859 tokens left, estimate 33,003 at margin 1.2, max_tokens 32,000, billed 45,296 in +
    1,747 out. Margin 1.2 sent it with a worst case of exactly the remainder, and it ran 184 over; margin 2.5 refuses it
    before sending (the attempt then ends reservation_exhausted, which a retry can follow, not FAILED_BUDGET)."""
    msgs = [HumanMessage("y" * int((33_003 / 1.2 - 8) * 3))]
    billed = 45_296 + 1_747
    for cfg, sends in ((load_config(), True), (router_cfg(), False)):
        cfg = copy.deepcopy(cfg)
        cfg["roles"]["coder"]["max_output_tokens"] = 32_000
        c = caller(tmp_path, cfg)
        est = c.count(msgs, None)
        cap = c._output_cap(est, hl.Reservation(tokens=46_859, usd=0.45))
        assert (cap >= c.min_output) is sends
        if sends:
            assert abs(est - 33_003) <= 2 and est + cap < billed          # the overrun as it happened
        else:
            assert est > 46_859                                          # its estimate alone does not fit


def test_the_input_limits_scale_with_the_margin_so_the_billed_context_stays_the_same():
    o = load_config()["router"]["overrides"]
    base = load_config()
    assert o["code_task.max_input_tokens_by_model"][DEEPSEEK] == round(
        base["code_task"]["max_input_tokens_by_model"][DEEPSEEK] * 2.5 / 1.2, -3)
    assert abs(o["drafter.max_input_tokens"] - base["drafter"]["max_input_tokens"] * 2.5 / 1.2) < 1000


def test_large_usd_reserves_1_2_million_tokens_in_router_jobs_within_the_job_tokens():
    cfg = router_cfg()
    assert cfg["code_task"]["profiles"]["large_usd"]["attempt_tokens"] == 1_200_000 <= cfg["budget"]["max_tokens"]
    assert cfg["code_task"]["profiles"]["default"] == load_config()["code_task"]["profiles"]["default"]
    assert load_config()["code_task"]["profiles"]["large_usd"]["attempt_tokens"] == 400_000      # evals unchanged
