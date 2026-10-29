"""SPEC_ESTIMATE_REASONING: the heuristic counter counts what an adapter sends, earlier reasoning included.
ArgusChatDeepSeek sends every earlier reply's reasoning_content back; uncounted, sympy-19954 a2 was billed 1.91x its
estimate at margin 2.5. Counted, the router's DeepSeek margin is 1.5."""
import copy
import json
from types import SimpleNamespace

import pytest
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import tool
from langchain_core.utils.function_calling import convert_to_openai_tool

import harness.llm as hl
from harness.events import EventLog
from models import registry
from models.fake import ScriptedChatModel
from router import job as rj
from runner import load_config

DEEPSEEK = "deepseek:deepseek-flash"
REASONING = "think " * 10_000                                          # 60,000 characters
CALL_ID = "call_" + "0" * 200                  # long, so a sent id that goes uncounted shows (see the adapter guard)


def conversation(reasoning=REASONING):
    """One agent attempt as it is sent: a tool call with its reasoning, the tool's result, and a reply."""
    call = {"name": "EditFile", "args": {"path": "sympy/core/numbers.py", "old_text": "if not self:\n" * 50,
                                         "new_text": "naïve € ünïcödé\n" * 50}, "id": CALL_ID, "type": "tool_call"}
    return [SystemMessage("You fix one issue. " * 200), HumanMessage("S(0.0) == S.false returns True. " * 100),
            AIMessage("", tool_calls=[call], additional_kwargs={"reasoning_content": reasoning}),
            ToolMessage("Edited sympy/core/numbers.py: 1 replacement. " * 40, tool_call_id=CALL_ID),
            AIMessage("Done: the Boolean check comes first.", additional_kwargs={"reasoning_content": reasoning[:9_000]})]


def without_reasoning(msgs):
    return [m.model_copy(update={"additional_kwargs": {}}) if isinstance(m, AIMessage) else m for m in msgs]


def test_earlier_reasoning_is_counted():
    count = hl.heuristic_counter(1.5)[0]
    msgs = conversation()
    added = count(msgs, None) - count(without_reasoning(msgs), None)
    assert added >= (len(REASONING) + 9_000) / 3 * 1.5 - 2


# Every adapter kind the registry builds is either counted exactly by its provider, never sends (fake), or counted by
# the heuristic, which must count every string of the request it sends. A new kind fails here until it is placed.
EXACT, NOT_SENT = {"anthropic"}, {"fake"}
HEURISTIC = {"openai": ("openai:gpt-test", {}), "openai_compatible": ("local:some-model", {"base_url": "http://x.test"}),
             "deepseek": (DEEPSEEK, {})}


def test_every_adapter_kind_is_placed():
    assert set(registry.BUILDERS) == EXACT | NOT_SENT | set(HEURISTIC)


@tool
def EditFile(path: str, old_text: str, new_text: str) -> str:
    """Replace old_text with new_text in the file at path (exactly one occurrence)."""
    return ""


# Fixed words of the request format (roles, the tool type); dict keys are left out too. Both are what the counter's
# 8 tokens per message stand for, so they are not compared: every other string of the request is.
STRUCTURE = {"system", "user", "assistant", "tool", "function"}


def _values(x):
    if isinstance(x, str):
        if x not in STRUCTURE:
            yield x
    elif isinstance(x, dict):
        for v in x.values():
            yield from _values(v)
    elif isinstance(x, (list, tuple)):
        for v in x:
            yield from _values(v)


def _sent_chars(model, msgs, tools=()):
    """Characters of the strings in the request the adapter builds (nothing is sent): messages and tool schemas."""
    payload = model._get_request_payload(msgs, **({"tools": [convert_to_openai_tool(t) for t in tools]} if tools else {}))
    return sum(len(s) for s in _values([payload["messages"], payload.get("tools", [])]))


@pytest.mark.parametrize("kind", sorted(HEURISTIC))
def test_the_heuristic_counts_every_string_an_adapter_sends(kind, monkeypatch):
    monkeypatch.setenv("ARGUS_TEST_KEY", "sk-test")
    ref, pcfg = HEURISTIC[kind]
    model = registry.BUILDERS[kind](registry.ModelRef.parse(ref), {"api_key_env": "ARGUS_TEST_KEY", **pcfg}, {})
    count, exact = hl.provider_counter(model, 1.0)
    assert not exact
    msgs = conversation()
    counted = (count(msgs, [EditFile]) - 1 - 8 * len(msgs) + 1) * 3     # its characters: int((c/3 + 8n) * 1.0) + 1
    assert counted >= _sent_chars(model, msgs, [EditFile]), kind
    if kind == "deepseek":                                              # it sends the reasoning: counted, not just
        assert _sent_chars(model, msgs) > _sent_chars(model, without_reasoning(msgs)) + len(REASONING)   # covered


def test_anthropic_is_counted_by_its_provider():
    from langchain_anthropic import ChatAnthropic
    assert hl.provider_counter(ChatAnthropic(model="claude-test", api_key="sk-test"), 1.5)[1] is True


def test_reasoning_stays_out_of_the_prompt_hash():
    """Memo keys carry prompt_hash: runs committed before this change resume from their memo."""
    msgs = conversation()
    assert hl.prompt_hash(msgs, None) == hl.prompt_hash(without_reasoning(msgs), None)
    assert hl.prompt_hash(msgs, None) == "0a0c454768562993"


def caller(tmp_path, cfg):
    cfg = copy.deepcopy(cfg)
    cfg["roles"]["coder"]["model"] = DEEPSEEK
    cfg["roles"]["coder"]["max_output_tokens"] = 32_000
    return hl.LLMCaller(cfg, "coder", EventLog(tmp_path / "e.jsonl"), model=ScriptedChatModel(script=[]))


def router_cfg():
    return rj.stage_config(load_config(), 1.0)


def recorded(est_input, margin, reasoning_chars):
    """A context like a recorded step: its counted part gave est_input at `margin`, plus the reasoning sent back."""
    return [HumanMessage("y" * int((est_input / margin - 8 * 2) * 3)),
            AIMessage("", additional_kwargs={"reasoning_content": "r" * reasoning_chars})]


@pytest.mark.parametrize("name, est_input, margin, reasoning, left, billed", [
    # sympy-24562 dev retry a2, attempt 3 step 18: estimate 33,003 at 1.2 with 79,307 characters of reasoning sent;
    # 46,859 tokens left; billed 45,296 + 1,747: it was sent and ran 184 tokens over the attempt
    ("24562 a2 step 18", 33_003, 1.2, 79_307, 46_859, 45_296 + 1_747),
    # sympy-19954 batch 5 a2, attempt 1 step 22: estimate 39,980 at 2.5 with 208,378 characters; billed 64,534 in
    ("19954 a2 step 22", 39_980, 2.5, 208_378, None, 64_534),
])
def test_recorded_steps_are_estimated_above_what_was_billed(tmp_path, name, est_input, margin, reasoning, left, billed):
    c = caller(tmp_path, router_cfg())
    msgs = recorded(est_input, margin, reasoning)
    assert abs(hl.heuristic_counter(margin)[0](without_reasoning(msgs), None) - est_input) <= 3   # the counted part
    est = c.count(msgs, None)
    assert est >= billed, (name, est)
    if left is not None:
        assert est > left and c._output_cap(est, hl.Reservation(tokens=left, usd=0.45)) < c.min_output  # refused
        # as it happened: counted without the reasoning at the old margin, it was sent and ran over
        old = hl.heuristic_counter(margin)[0](without_reasoning(msgs), None)
        cap = c._output_cap(old, hl.Reservation(tokens=left, usd=0.45))
        assert cap >= c.min_output and old + cap < billed


def test_router_margin_and_input_limits():
    cfg, base = router_cfg(), load_config()
    o = base["router"]["overrides"]
    assert o["llm.input_margin_by_model"] == {DEEPSEEK: 1.5, "deepseek:deepseek-v4-pro": 1.5}
    assert o["code_task.max_input_tokens_by_model"] == {DEEPSEEK: 150_000, "deepseek:deepseek-v4-pro": 150_000}
    assert o["drafter.max_input_tokens"] == 250_000
    assert cfg["llm"]["input_margin_by_model"][DEEPSEEK] == 1.5
    assert "input_margin_by_model" not in base["llm"] and base["llm"]["input_margin"] == 1.2       # evals unchanged
    assert base["code_task"]["max_input_tokens_by_model"][DEEPSEEK] == 60_000
    assert base["drafter"]["max_input_tokens"] == 200_000


def _ledger(path, events):
    path.parent.mkdir(parents=True)
    path.write_text("".join(json.dumps(e) + "\n" for e in events), encoding="utf-8")


def test_status_lines_count_the_estimate_misses_of_each_stage(tmp_path):
    calls = [{"event": "llm_call", "call_id": f"c{i}", "status": "ok"} for i in range(9)] + [
        {"event": "llm_call", "call_id": "r", "status": "refused"}, {"event": "llm_call", "call_id": "e", "status": "error"}]
    miss = [{"event": "estimate_miss", "est_input": 1000, "input_tokens": n} for n in (1100, 1910, 1020)]
    _ledger(tmp_path / "j-d1" / "events.jsonl", calls[:3])
    _ledger(tmp_path / "j-a1" / "events.jsonl", calls + miss)
    job = SimpleNamespace(runs=tmp_path, data={"stages": {"d1": {"run_id": "j-d1"}, "a1": {"run_id": "j-a1"},
                                                          "a2": {"run_id": "j-gone"}, "a3": {}}})
    assert rj._estimate_lines(job) == ["  a1 estimate misses: 3 of 9 calls, max 1.91"]     # billed calls only
