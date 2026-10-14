"""Phase 2b: the orchestrator plans with a model, the harness validates the plan.
All tests use scripted fake models: no network, no API key, no cost."""
import copy
import json
import subprocess
import sys
from collections import Counter
from pathlib import Path

import pytest
import yaml
from langchain_core.messages import HumanMessage, ToolMessage

from models.fake import FakeHTTPError, ScriptedChatModel, reply
from nodes.contract import SALES_REPORT
from nodes.plan import SubmitPlan, validate_plan
from runner import ROOT, load_config, run_task

GOAL = "Analyze penjualan.csv: top 3 products, monthly trend, 2 recommendations -> laporan.md"


def task(id, output, instruction=None, feedback=""):
    return {"id": id, "output": output, "feedback": feedback,
            "instruction": instruction or f"Produce the {output} output from penjualan.csv as specified."}


GOOD = {"tasks": [task("calc_top", "top3"), task("calc_trend", "trend"), task("check", "data_check")],
        "rationale": "one output per worker"}
GOOD_FIXED = {"tasks": [task("calc_top", "top3", feedback="sum revenue per product"),
                        task("calc_trend", "trend", feedback="include every month"),
                        task("check", "data_check")]}


def plan_call(args, id="call_1"):
    return reply("", input_tokens=700, output_tokens=300,
                 tool_calls=[{"name": "SubmitPlan", "args": args, "id": id}])


def cfg_llm(**budget):
    cfg = copy.deepcopy(load_config())
    cfg["impl"]["orchestrator"] = "llm"
    cfg.pop("llm_token_estimates", None)   # these tests size the LLM node through token_estimates
    cfg["roles"]["orchestrator"]["model"] = "fake:scripted"
    cfg["token_estimates"]["orchestrator"] = 12_000   # a real planner needs room for retries
    cfg["llm"]["base_delay"] = 0
    cfg["budget"].update(budget)
    return cfg


def run(tmp_path, script, scenario="pass", cfg=None, run_id="t"):
    model = ScriptedChatModel(script=list(script))
    r = run_task(goal=GOAL, scenario=scenario, run_id=run_id, runs_dir=tmp_path,
                 cfg=cfg or cfg_llm(), models={"orchestrator": model})
    evs = [json.loads(l) for l in (tmp_path / run_id / "events.jsonl").read_text().splitlines()]
    return r, model, evs


def kinds(evs, kind):
    return [e for e in evs if e["event"] == kind]


# ---- happy path ----------------------------------------------------------------------

def test_valid_plan_runs_to_done_with_the_models_own_task_ids(tmp_path):
    cfg = cfg_llm()
    cfg["orchestrator"]["force_tool"] = True
    r, model, evs = run(tmp_path, [plan_call(GOOD)], cfg=cfg)
    assert r["status"] == "DONE" and r["iteration"] == 1
    assert len(model.calls) == 1
    assert model.tool_choice == "SubmitPlan" and model.bound_tools == [SubmitPlan]
    workers = sorted(e["task"] for e in evs if e["event"] == "node_end" and e["node"] == "worker")
    assert workers == ["calc_top", "calc_trend", "check"]


def test_truncated_plan_is_never_accepted_and_not_retried(tmp_path):
    # 2e smoke: a revised plan stopped at exactly its 905-token cap. Here the cut-off plan is even valid.
    cut = reply("", input_tokens=2095, output_tokens=905, stop_reason="max_tokens",
                tool_calls=[{"name": "SubmitPlan", "args": GOOD, "id": "c1"}])
    r, model, evs = run(tmp_path, [cut, plan_call(GOOD)])
    assert r["status"] == "FAILED_PLAN" and r["stop_reason"].startswith("output_truncated")
    assert len(model.calls) == 1
    assert not kinds(evs, "spec_created") and not kinds(evs, "plan_invalid")
    assert not [e for e in evs if e["event"] == "node_start" and e["node"] == "worker"]
    assert [e["truncated"] for e in kinds(evs, "llm_call")] == [True]
    assert len(kinds(evs, "output_truncated")) == 1 and len(kinds(evs, "plan_truncated")) == 1


@pytest.mark.parametrize("metadata, cut", [
    ({"stop_reason": "max_tokens"}, True),      # Anthropic
    ({"finish_reason": "length"}, True),        # OpenAI, DeepSeek
    ({"truncated": True}, True),                # replayed from the memo
    ({"stop_reason": "end_turn"}, False),
    ({"stop_reason": "tool_use"}, False),
    ({"finish_reason": "stop"}, False),
    ({}, False),
])
def test_truncation_is_read_from_the_provider_stop_signal(metadata, cut):
    from langchain_core.messages import AIMessage
    from harness.llm import is_truncated
    assert is_truncated(AIMessage(content="", response_metadata=metadata)) is cut


def test_default_config_does_not_force_the_tool(tmp_path):
    # claude-sonnet-5-5 (the default orchestrator) rejects a forced tool_choice with HTTP 400.
    assert load_config()["orchestrator"]["force_tool"] is False
    r, model, _ = run(tmp_path, [plan_call(GOOD)])
    assert r["status"] == "DONE"
    assert model.tool_choice is None and model.bound_tools == [SubmitPlan]


def test_revision_receives_the_evaluators_failed_checks(tmp_path):
    r, model, evs = run(tmp_path, [plan_call(GOOD), plan_call(GOOD_FIXED)], scenario="fail_then_pass")
    assert r["status"] == "DONE" and r["iteration"] == 2
    revision_prompt = model.calls[1]["messages"][-1].content
    assert "top3_amounts" in revision_prompt and "trend_months" in revision_prompt
    assert "calc_top" in revision_prompt                       # the previous plan is shown
    assert "top3_amounts" not in model.calls[0]["messages"][-1].content


def test_system_prompt_states_the_contract_and_limits(tmp_path):
    _, model, _ = run(tmp_path, [plan_call(GOOD)])
    system = model.calls[0]["messages"][0].content
    assert "At most 3 tasks" in system
    for name in SALES_REPORT["outputs"]:
        assert f"`{name}`" in system


# ---- validation ------------------------------------------------------------------------

INVALID = [
    ({"tasks": [task("a", "top3")]}, "required output 'trend'"),
    ({"tasks": [task("a", "top3"), task("a", "trend")]}, "duplicate task ids"),
    ({"tasks": [task("a", "top3"), task("b", "trend"), task("c", "foo")]}, "'foo' is not in the contract"),
    ({"tasks": [task("a", "top3"), task("b", "trend"), task("c", "data_check"), task("d", "data_check")]},
     "at most 3 are allowed"),
    ({"tasks": [task("1x", "top3"), task("b", "trend")]}, "task id '1x' is invalid"),
    ({"tasks": [task("a", "top3", instruction="do it"), task("b", "trend")]}, "too short"),
    ({"tasks": [task("a", "top3"), task("b", "top3"), task("c", "trend")]}, "produced by 2 tasks"),
    ({"steps": []}, "tasks"),
    ({"tasks": "all of them"}, "tasks"),
    ({"tasks": []}, "no tasks"),
]


@pytest.mark.parametrize("args, error", INVALID)
def test_validate_plan_rejects(args, error):
    plan, errors = validate_plan(args, SALES_REPORT, 3)
    assert plan is None and any(error in e for e in errors), errors


def test_validate_plan_accepts_good_plans():
    for args in (GOOD, GOOD_FIXED, {"tasks": [task("a", "top3"), task("b", "trend")]}):
        plan, errors = validate_plan(args, SALES_REPORT, 3)
        assert errors == [] and plan is not None


@pytest.mark.parametrize("args, error", INVALID)
def test_invalid_plan_is_returned_to_the_model_then_fixed(tmp_path, args, error):
    r, model, evs = run(tmp_path, [plan_call(args, id="bad_1"), plan_call(GOOD, id="good_1")])
    assert r["status"] == "DONE" and len(model.calls) == 2
    (invalid,) = kinds(evs, "plan_invalid")
    assert any(error in e for e in invalid["errors"])
    feedback = model.calls[1]["messages"][-1]
    assert isinstance(feedback, ToolMessage) and feedback.tool_call_id == "bad_1"
    assert error in feedback.content


def test_no_tool_call_is_answered_with_a_message(tmp_path):
    r, model, evs = run(tmp_path, [reply("Here is my plan: ..."), plan_call(GOOD)])
    assert r["status"] == "DONE"
    follow_up = model.calls[1]["messages"][-1]
    assert isinstance(follow_up, HumanMessage) and "exactly once" in follow_up.content


def test_two_plan_calls_in_one_turn_are_rejected_and_both_answered(tmp_path):
    double = reply("", tool_calls=[{"name": "SubmitPlan", "args": GOOD, "id": "a"},
                                   {"name": "SubmitPlan", "args": GOOD, "id": "b"}])
    r, model, _ = run(tmp_path, [double, plan_call(GOOD)])
    assert r["status"] == "DONE"
    answered = [m.tool_call_id for m in model.calls[1]["messages"] if isinstance(m, ToolMessage)]
    assert answered == ["a", "b"]


@pytest.mark.parametrize("extra", [
    [{"name": "UnexpectedTool", "args": {"x": 1}, "id": "b"}],
    [{"name": "run_python", "args": {"code": "import os"}, "id": "b"}],
    [{"name": "UnexpectedTool", "args": {}, "id": "b"}, {"name": "Other", "args": {}, "id": "c"}],
])
def test_valid_plan_with_extra_tool_calls_is_rejected(tmp_path, extra):
    """GPT audit 2b (P2): one valid SubmitPlan plus any other tool call must not be accepted."""
    mixed = reply("", tool_calls=[{"name": "SubmitPlan", "args": GOOD, "id": "a"}] + extra)
    r, model, evs = run(tmp_path, [mixed, plan_call(GOOD, id="good")])
    (invalid,) = kinds(evs, "plan_invalid")
    assert "unexpected tools" in invalid["errors"][0]
    # every tool call in the rejected turn gets an answer, and no worker ran before the valid plan
    answered = [m.tool_call_id for m in model.calls[1]["messages"] if isinstance(m, ToolMessage)]
    assert answered == ["a"] + [c["id"] for c in extra]
    first_worker = next(i for i, e in enumerate(evs) if e["event"] == "node_start" and e["node"] == "worker")
    accepted = next(i for i, e in enumerate(evs) if e["event"] == "spec_created")
    assert accepted < first_worker and evs.index(invalid) < accepted
    assert r["status"] == "DONE" and len(model.calls) == 2


def test_extra_tool_calls_every_time_ends_as_failed_plan(tmp_path):
    mixed = reply("", tool_calls=[{"name": "SubmitPlan", "args": GOOD, "id": "a"},
                                  {"name": "UnexpectedTool", "args": {}, "id": "b"}])
    r, _, evs = run(tmp_path, [mixed] * 3)
    assert r["status"] == "FAILED_PLAN"
    assert not [e for e in evs if e["event"] == "node_start" and e["node"] == "worker"]


def test_gives_up_after_plan_attempts_and_no_worker_runs(tmp_path):
    bad = {"tasks": [task("a", "top3")]}
    r, model, evs = run(tmp_path, [plan_call(bad)] * 3)
    assert r["status"] == "FAILED_PLAN" and r["stop_reason"].startswith("plan_invalid after 3 attempts")
    assert len(model.calls) == 3
    assert not [e for e in evs if e["event"] == "node_start" and e["node"] == "worker"]
    assert evs[-1]["event"] == "run_end" and evs[-1]["status"] == "FAILED_PLAN"


# ---- model failures and budget -----------------------------------------------------------

def test_transient_error_is_retried_by_the_wrapper(tmp_path):
    r, model, evs = run(tmp_path, [FakeHTTPError(429), plan_call(GOOD)])
    assert r["status"] == "DONE" and len(model.calls) == 2
    assert [e["status"] for e in kinds(evs, "llm_call")] == ["transient_error", "ok"]


def test_permanent_model_error_stops_the_run_cleanly(tmp_path):
    r, model, _ = run(tmp_path, [FakeHTTPError(401, "invalid api key")])
    assert r["status"] == "FAILED_LLM" and "invalid api key" in r["stop_reason"]
    assert len(model.calls) == 1


def test_node_reservation_too_small_refuses_before_sending(tmp_path):
    cfg = cfg_llm()
    cfg["token_estimates"]["orchestrator"] = 500    # the prompt alone is ~700 tokens
    r, model, evs = run(tmp_path, [plan_call(GOOD)], cfg=cfg)
    assert r["status"] == "FAILED_BUDGET" and r["stop_reason"].startswith("node_reservation")
    assert model.calls == []                        # nothing was sent
    assert [e["status"] for e in kinds(evs, "llm_call")] == ["refused"]


def test_retries_stop_when_the_node_reservation_runs_out(tmp_path):
    cfg = cfg_llm()
    cfg["token_estimates"]["orchestrator"] = 2_500  # room for about two attempts, not three
    bad = {"tasks": [task("a", "top3")]}
    r, model, _ = run(tmp_path, [plan_call(bad)] * 3, cfg=cfg)
    assert r["status"] == "FAILED_BUDGET" and len(model.calls) < 3
    assert r["tokens_used"] <= 2_500


def test_accounting_matches_the_ledger(tmp_path):
    r, _, evs = run(tmp_path, [FakeHTTPError(500), plan_call({"tasks": [task("a", "top3")]}), plan_call(GOOD)])
    ledger = kinds(evs, "llm_call")
    orch_tokens = [e["tokens"] for e in evs if e["event"] == "node_end" and e["node"] == "orchestrator"]
    assert orch_tokens == [sum(e["tokens"] for e in ledger)]
    assert r["usd_billed"] == pytest.approx(sum(e["usd"] for e in ledger))
    assert r["usd_used"] == pytest.approx(r["usd_billed"] + 3 * 2000 * 0.50 / 1e6)  # + fake workers' USD


# ---- crash-resume with the model in a separate process ----------------------------------

def _cli_run(tmp_path, script, *extra):
    cfg = cfg_llm()
    cfg_path = tmp_path / "config.yaml"
    cfg_path.write_text(yaml.safe_dump(cfg), encoding="utf-8")
    script_path = tmp_path / "script.json"
    script_path.write_text(json.dumps(script), encoding="utf-8")
    env = {**__import__("os").environ, "ARGUS_FAKE_SCRIPT": str(script_path)}
    base = [sys.executable, "main.py", "--config", str(cfg_path), "--scenario", "fail_then_pass",
            "--run-id", "rc", "--runs-dir", str(tmp_path / "runs"), "--quiet"]
    return subprocess.run(base + list(extra), cwd=ROOT, capture_output=True, text=True, env=env)


def _json_plan(args, id):
    return {"tool_calls": [{"name": "SubmitPlan", "args": args, "id": id}],
            "usage": {"input_tokens": 700, "output_tokens": 300}}


@pytest.mark.parametrize("crash_at", ["orchestrator@after_commit", "worker", "evaluator"])
def test_crash_resume_never_pays_for_a_committed_plan_twice(tmp_path, crash_at):
    script = [_json_plan(GOOD, "p1"), _json_plan(GOOD_FIXED, "p2")]
    r1 = _cli_run(tmp_path, script, "--crash-at", crash_at)
    assert r1.returncode == 42, r1.stderr
    r2 = _cli_run(tmp_path, script, "--resume")
    assert r2.returncode == 0, r2.stderr

    run_dir = tmp_path / "runs" / "rc"
    result = json.loads((run_dir / "result.json").read_text())
    assert result["status"] == "DONE" and result["iteration"] == 2
    evs = [json.loads(l) for l in (run_dir / "events.jsonl").read_text().splitlines()]
    ok_calls = [e for e in evs if e["event"] == "llm_call" and e["status"] == "ok"]
    assert len(ok_calls) == 2                                   # one plan per iteration, never re-bought
    assert int((tmp_path / "script.json.pos").read_text()) == 2  # the model was called exactly twice
    committed = Counter((e["node"], e.get("task"), e.get("iteration")) for e in evs if e["event"] == "result_committed")
    assert all(n == 1 for n in committed.values())


# ---- every model call goes through harness/llm.py ---------------------------------------------

def test_no_code_outside_the_wrapper_calls_a_model_directly():
    """Nodes and the harness may reach a provider only through LLMCaller. A direct .invoke() on a chat
    model, or building one with build_chat_model, anywhere else would bypass budget and ledger."""
    import re
    allowed = {ROOT / "harness" / "llm.py", ROOT / "models" / "registry.py"}
    offenders = []
    for path in sorted((ROOT / "nodes").glob("*.py")) + sorted((ROOT / "harness").glob("*.py")) + [ROOT / "graph.py"]:
        if path in allowed:
            continue
        text = path.read_text(encoding="utf-8")
        for pattern in (r"\.invoke\(", r"\.ainvoke\(", r"\.stream\(", r"\.batch\(", r"build_chat_model\("):
            for m in re.finditer(pattern, text):
                offenders.append(f"{path.relative_to(ROOT)}:{text[:m.start()].count(chr(10)) + 1} {pattern}")
    assert offenders == [], offenders
