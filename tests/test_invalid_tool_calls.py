"""Found by calibration run #3 (docs/reviews/REVIEW_3D.md): a tool call whose arguments cannot be parsed arrives in
LangChain's `invalid_tool_calls`, not in `tool_calls`. The loops read only `tool_calls`, answered with a plain message
instead of a ToolMessage, and the provider rejected the next request with HTTP 400 (vague-3's invalid verdict).

What must hold in all four tool loops (orchestrator, worker, writer, judge):
- a malformed call is never treated as a valid one (nothing in it is run, read or accepted);
- every tool call id in a reply, valid or not, is answered by a ToolMessage before the next model turn;
- the memo keeps the malformed call, so a replay is the reply that was received and is answered the same way.
The strict fake model raises HTTP 400 exactly like DeepSeek when an id is left unanswered."""
import copy
import json

import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

import dataset
from harness.events import EventLog
from harness.llm import LLMCaller
from harness.memo import Memo
from harness.steps import message_from_json, message_to_json
from models.fake import FakeHTTPError, StrictScriptedChatModel, reply
from nodes.contract import SALES_REPORT
from nodes.facts import build_facts
from nodes.judge import make_judge
from nodes.llm_worker import make_llm_worker
from nodes.synthesize import make_llm_synthesize, report_text, template_recommendations
from runner import load_config, run_task
from tools.registry import ToolGate

T = dataset.truth()
TOP3, TREND = [list(x) for x in T["top3"]], [list(x) for x in T["trend"]]
FACTS = build_facts(TOP3, TREND)
RECS = template_recommendations(TOP3, TREND)
REPORT = report_text(TOP3, TREND, RECS)
CRITERIA = SALES_REPORT["rubric"]


def malformed(name, id="bad1", args='{"criteria": [{"id": "grounded", "pass": tr'):
    return reply("", input_tokens=1200, output_tokens=2388,
                 invalid_tool_calls=[{"name": name, "args": args, "id": id,
                                      "error": "Expecting value: line 1 column 40"}])


def tool(name, args, id="ok1"):
    return reply("", input_tokens=1200, output_tokens=300, tool_calls=[{"name": name, "args": args, "id": id}])


def verdict():
    return {"criteria": [{"id": c["id"], "pass": True, "evidence": [RECS[0]["text"][:40]], "reason": "checked"}
                         for c in CRITERIA]}


def cfg_for(role):
    cfg = copy.deepcopy(load_config())
    cfg["roles"][role]["model"] = "fake:scripted"
    cfg["llm"]["base_delay"] = 0
    return cfg


def answered_ids(model, call=1):
    msgs = model.calls[call]["messages"]
    return [m.tool_call_id for m in msgs if isinstance(m, ToolMessage)]


# ---- the strict model reproduces the provider's rejection -------------------------------------------------

def test_the_strict_model_rejects_an_unanswered_invalid_call_like_deepseek():
    model = StrictScriptedChatModel(script=[reply("never reached")])
    sent = [HumanMessage("judge this"), malformed("SubmitVerdict"), HumanMessage("Rejected: call the tool again")]
    with pytest.raises(FakeHTTPError) as e:
        model.invoke(sent)
    assert e.value.status_code == 400 and "tool_call_id" in str(e.value)
    ok = [HumanMessage("judge this"), malformed("SubmitVerdict"), ToolMessage("Rejected.", tool_call_id="bad1")]
    assert model.invoke(ok).content == "never reached"


# ---- judge (where run #3 hit it) ------------------------------------------------------------------------------

def judge(tmp_path, script, attempts=2, memo=None):
    log = EventLog(tmp_path / "e.jsonl")
    model = StrictScriptedChatModel(script=list(script))
    j = make_judge(LLMCaller(cfg_for("evaluator"), "evaluator", log, model=model), memo or Memo(tmp_path / "m.sqlite"),
                   log, criteria=CRITERIA, tokens=40_000, usd=1.0, attempts=attempts)
    return j, model, log


def test_judge_answers_a_malformed_call_and_its_next_verdict_counts(tmp_path):
    j, model, log = judge(tmp_path, [malformed("SubmitVerdict"), tool("SubmitVerdict", verdict(), id="v2")])
    r = j(REPORT, FACTS, 0, task="vague-3")
    assert r["valid"] is True and r["passed"] is True and len(model.calls) == 2   # no HTTP 400
    assert answered_ids(model) == ["bad1"]
    answer = [m for m in model.calls[1]["messages"] if isinstance(m, ToolMessage)][0]
    assert "not valid JSON" in answer.content
    (rejected,) = [e for e in log.read() if e["event"] == "verdict_rejected"]
    assert "not valid JSON" in rejected["errors"][0]


def test_a_malformed_verdict_alone_never_passes(tmp_path):
    j, model, _ = judge(tmp_path, [malformed("SubmitVerdict")], attempts=1)
    r = j(REPORT, FACTS, 0, task="t")
    assert r["valid"] is False and r["passed"] is False and "not valid JSON" in r["reason"]


def test_a_replayed_malformed_reply_is_answered_the_same_way(tmp_path):
    memo = Memo(tmp_path / "m.sqlite")
    j1, m1, _ = judge(tmp_path, [malformed("SubmitVerdict")], attempts=1, memo=memo)
    assert j1(REPORT, FACTS, 0, task="t")["valid"] is False
    # restart with one more attempt: step 0 is replayed from the memo, step 1 is a new call that must answer bad1
    j2, m2, log = judge(tmp_path, [tool("SubmitVerdict", verdict(), id="v2")], attempts=2, memo=memo)
    r = j2(REPORT, FACTS, 0, task="t")
    assert r["valid"] is True and len(m2.calls) == 1 and answered_ids(m2, 0) == ["bad1"]
    assert [e["step"] for e in log.read() if e["event"] == "step_replayed"] == [0]


def test_the_memo_keeps_the_malformed_call():
    original = malformed("SubmitVerdict")
    replayed = message_from_json(json.loads(json.dumps(message_to_json(original))))
    assert replayed.tool_calls == [] and len(replayed.invalid_tool_calls) == 1
    assert {k: replayed.invalid_tool_calls[0][k] for k in ("name", "args", "id")} == \
           {k: original.invalid_tool_calls[0][k] for k in ("name", "args", "id")}


def test_the_next_steps_memo_key_carries_the_malformed_call():
    # AGENTS.md: a step's memo key carries its input identity. The malformed arguments are sent to the provider in the
    # next request, so two different malformed replies must not share the next step's key.
    from harness.steps import llm_step_key

    def key(m):
        return llm_step_key("evaluator", "t", 0, 1, [HumanMessage("judge"), m, ToolMessage("Rejected.", tool_call_id="bad1")],
                            [], "fake:scripted")
    assert key(malformed("SubmitVerdict", args='{"a": 1')) != key(malformed("SubmitVerdict", args='{"b": 2'))


def test_a_reply_with_a_valid_and_a_malformed_call_answers_both(tmp_path):
    both = reply("", tool_calls=[{"name": "SubmitVerdict", "args": verdict(), "id": "good1"}],
                 invalid_tool_calls=[{"name": "SubmitVerdict", "args": "{", "id": "bad1", "error": "x"}])
    j, model, _ = judge(tmp_path, [both, tool("SubmitVerdict", verdict(), id="v2")])
    r = j(REPORT, FACTS, 0, task="t")
    assert r["valid"] is True and len(model.calls) == 2        # the mixed reply itself was not accepted
    assert sorted(answered_ids(model)) == ["bad1", "good1"]


# ---- writer ---------------------------------------------------------------------------------------------

def test_writer_answers_a_malformed_call(tmp_path):
    log = EventLog(tmp_path / "e.jsonl")
    model = StrictScriptedChatModel(script=[malformed("SubmitRecommendations"),
                                            tool("SubmitRecommendations", {"recommendations": RECS})])
    fn = make_llm_synthesize(LLMCaller(cfg_for("writer"), "writer", log, model=model),
                             ToolGate("orchestrator", ["write_file"], log), Memo(tmp_path / "m.sqlite"), log,
                             str(tmp_path), tokens=40_000, usd=1.0)
    fn({"iteration": 0, "goal": "x", "results": {"a": {"output": "top3", "value": TOP3, "iteration": 0},
                                                  "b": {"output": "trend", "value": TREND, "iteration": 0}}})
    assert len(model.calls) == 2 and answered_ids(model) == ["bad1"]
    assert json.loads((tmp_path / "laporan.provenance.json").read_text())["recommendations"] == RECS
    assert [e["event"] for e in log.read() if e["event"] in ("recs_invalid", "recs_accepted")] == \
           ["recs_invalid", "recs_accepted"]


# ---- worker ---------------------------------------------------------------------------------------------

def test_worker_runs_nothing_from_a_malformed_reply_and_answers_it(tmp_path):
    log = EventLog(tmp_path / "e.jsonl")
    model = StrictScriptedChatModel(script=[malformed("SubmitResult"), tool("ReadData", {}, id="r1"),
                                            tool("SubmitResult", {"value": TOP3}, id="s1")])
    fn = make_llm_worker(LLMCaller(cfg_for("worker"), "worker", log, model=model), SALES_REPORT,
                         ToolGate("worker", ["read_data"], log), Memo(tmp_path / "m.sqlite"), log,
                         tokens=40_000, usd=1.0)
    out = fn({"task": {"id": "T2", "output": "top3", "instruction": "Top 3 products.", "feedback": ""},
              "iteration": 0})["results"]["T2"]
    assert out["value"] == TOP3 and len(model.calls) == 3 and answered_ids(model) == ["bad1"]
    evs = log.read()
    assert [e["tools"] for e in evs if e["event"] == "invalid_tool_call"] == [["SubmitResult"]]
    assert not any(e["event"] == "step_committed" and e["kind"] == "tool" and e["step"] == 0 for e in evs)


# ---- orchestrator ---------------------------------------------------------------------------------------

def test_orchestrator_answers_a_malformed_plan_call(tmp_path):
    plan = {"tasks": [{"id": t, "output": o, "instruction": f"Produce {o} from penjualan.csv exactly."}
                      for t, o in (("T1", "data_check"), ("T2", "top3"), ("T3", "trend"))]}
    cfg = cfg_for("orchestrator")
    cfg["impl"]["orchestrator"] = "llm"
    model = StrictScriptedChatModel(script=[malformed("SubmitPlan"), tool("SubmitPlan", plan, id="p2")])
    r = run_task(goal="x", scenario="pass", run_id="t", runs_dir=tmp_path, cfg=cfg, models={"orchestrator": model})
    assert r["status"] == "DONE" and len(model.calls) == 2 and answered_ids(model) == ["bad1"]
    evs = [json.loads(l) for l in (tmp_path / "t" / "events.jsonl").read_text().splitlines()]
    (invalid,) = [e for e in evs if e["event"] == "plan_invalid"]
    assert "not valid JSON" in invalid["errors"][0]
