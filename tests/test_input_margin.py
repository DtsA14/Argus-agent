"""SPEC_HEURISTIC_INPUT_MARGIN: a heuristic input margin per model, and large_usd's token ceiling. The router's DeepSeek
margin (1.5) and input limits, and the recorded steps, are in test_estimate_reasoning.py (SPEC_ESTIMATE_REASONING)."""
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


def test_the_router_counts_deepseek_with_margin_1_5_and_config_yaml_keeps_1_2(tmp_path):
    base = caller(tmp_path, load_config())
    routed = caller(tmp_path, router_cfg())
    assert not base.exact and not routed.exact
    assert base.count(MSGS, None) == hl.heuristic_counter(1.2)[0](MSGS, None)
    assert routed.count(MSGS, None) == hl.heuristic_counter(1.5)[0](MSGS, None)


def test_a_model_without_an_entry_keeps_input_margin(tmp_path):
    cfg = router_cfg()
    cfg["llm"]["input_margin_by_model"] = {"some:other-model": 9.0}
    c = caller(tmp_path, cfg)
    assert c.count(MSGS, None) == hl.heuristic_counter(1.2)[0](MSGS, None)


def test_large_usd_reserves_1_2_million_tokens_in_router_jobs_within_the_job_tokens():
    cfg = router_cfg()
    assert cfg["code_task"]["profiles"]["large_usd"]["attempt_tokens"] == 1_200_000 <= cfg["budget"]["max_tokens"]
    assert cfg["code_task"]["profiles"]["default"] == load_config()["code_task"]["profiles"]["default"]
    assert load_config()["code_task"]["profiles"]["large_usd"]["attempt_tokens"] == 400_000      # evals unchanged
