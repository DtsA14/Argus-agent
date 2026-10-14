"""Phase 2c: worker tool-calling loop with a per-step memo. Scripted fake models only: no network, no cost.

The point of these tests (GPT's DoD) is to count real model calls and real tool executions after a
crash, not just to compare final results."""
import copy
import json
import os
import subprocess
import sys
from collections import Counter
from pathlib import Path

import pytest
import yaml
from langchain_core.messages import HumanMessage, ToolMessage

import dataset
from harness.events import EventLog
from harness.llm import LLMCaller, reconcile_ledger
from harness.memo import Memo
from models.fake import FakeHTTPError, ScriptedChatModel, pos_path, reply
from nodes import llm_worker
from nodes.contract import SALES_REPORT, validate_output
from nodes.llm_worker import make_llm_worker
from runner import ROOT, load_config, run_task
from tools.registry import ToolGate

TRUTH = dataset.truth()
VALUES = {
    "T1": {"rows": 24, "months": [m for m, _ in TRUTH["trend"]], "products": ["Kopi", "Roti", "Susu", "Teh"]},
    "T2": [list(x) for x in TRUTH["top3"]],
    "T3": [list(x) for x in TRUTH["trend"]],
}


def read_call(id="r1"):
    return reply("", input_tokens=400, output_tokens=30, tool_calls=[{"name": "ReadData", "args": {}, "id": id}])


def submit_call(value, id="s1"):
    return reply("", input_tokens=900, output_tokens=120,
                 tool_calls=[{"name": "SubmitResult", "args": {"value": value}, "id": id}])


def good_script():
    return {t: [read_call(), submit_call(v)] for t, v in VALUES.items()}


def cfg_llm(**budget):
    cfg = copy.deepcopy(load_config())
    cfg["impl"]["worker"] = "llm"
    cfg.pop("llm_token_estimates", None)   # these tests size the LLM node through token_estimates
    cfg["roles"]["worker"]["model"] = "fake:scripted"
    cfg["token_estimates"]["worker"] = 20_000
    cfg["llm"]["base_delay"] = 0
    cfg["budget"].update(budget)
    return cfg


def events(path):
    return [json.loads(l) for l in Path(path).read_text().splitlines() if l.strip()]


def run(tmp_path, script, cfg=None, scenario="pass"):
    model = ScriptedChatModel(script=script)
    r = run_task(goal="x", scenario=scenario, run_id="t", runs_dir=tmp_path, cfg=cfg or cfg_llm(),
                 models={"worker": model})
    return r, model, events(tmp_path / "t" / "events.jsonl")


# ---- the loop ----------------------------------------------------------------------------------

def test_workers_read_then_submit_and_the_run_passes(tmp_path):
    r, model, evs = run(tmp_path, good_script())
    assert r["status"] == "DONE" and r["iteration"] == 1
    assert {k: len(model.calls_for(k)) for k in VALUES} == {"T1": 2, "T2": 2, "T3": 2}
    assert sum(e["event"] == "tool_call" and e["role"] == "worker" for e in evs) == 3   # one ReadData each
    assert "Task id: T2" in model.calls_for("T2")[0]["messages"][1].content           # only its own task


def test_worker_sees_only_its_task_and_the_feedback(tmp_path):
    cfg = cfg_llm()
    r, model, _ = run(tmp_path, {"T1": [read_call(), submit_call(VALUES["T1"])],
                                 "T2": [read_call(), submit_call([["Kopi", 1], ["Teh", 2], ["Roti", 3]]),
                                        submit_call(VALUES["T2"], id="s2"),
                                        read_call(), submit_call(VALUES["T2"])],
                                 "T3": [read_call(), submit_call(VALUES["T3"])] * 2}, cfg=cfg)
    first = model.calls_for("T2")[0]["messages"][1].content
    assert "Task id: T2" in first and "T3" not in first and "Feedback" not in first


@pytest.mark.parametrize("bad, error", [
    ([["Kopi", 1], ["Teh", 2]], "exactly 3 entries"),
    ([["Kopi", 1.5], ["Teh", 1], ["Roti", 0]], "non-negative integer"),
    ([["Kopi", 1], ["Teh", 2], ["Roti", 3]], "highest to lowest"),
    ("Kopi, Teh, Roti", "non-empty list"),
])
def test_invalid_submission_is_rejected_with_errors_and_retried(tmp_path, bad, error):
    script = good_script()
    script["T2"] = [read_call(), submit_call(bad), submit_call(VALUES["T2"], id="s2")]
    r, model, evs = run(tmp_path, script)
    assert r["status"] == "DONE"
    calls = model.calls_for("T2")
    assert len(calls) == 3
    rejection = calls[2]["messages"][-1]
    assert isinstance(rejection, ToolMessage) and error in rejection.content
    # GPT review 2e: why the extra step was needed is visible in the event log, bounded
    (invalid,) = [e for e in evs if e["event"] == "submission_invalid"]
    assert invalid["task"] == "T2" and invalid["step"] == 1
    assert any(error in m for m in invalid["errors"]) and all(len(m) <= 200 for m in invalid["errors"])


def test_rejection_reasons_in_the_event_log_are_bounded(tmp_path, monkeypatch):
    monkeypatch.setattr(llm_worker, "validate_output", lambda name, value: [f"{i}:" + "x" * 500 for i in range(15)])
    fn, _, log = _worker(tmp_path, {"T2": [read_call(), submit_call(VALUES["T2"])]}, max_steps=2)
    fn(P)
    (invalid,) = [e for e in log.read() if e["event"] == "submission_invalid"]
    assert len(invalid["errors"]) == 10 and all(len(m) == 200 for m in invalid["errors"])


# ---- the tools offered and the prompt follow the allowlist and the sandbox (GPT review 2e, P2) ----

SANDBOX_CFG = {**load_config()["sandbox"], "kind": "docker", "image": "sha256:" + "a" * 64}


def _offer(tmp_path, allowed, sandbox, script):
    log = EventLog(tmp_path / "e.jsonl")
    model = ScriptedChatModel(script=script)
    caller = LLMCaller(cfg_llm(), "worker", log, model=model)
    box = {"cfg": SANDBOX_CFG, "workspace": str(tmp_path / "ws"), "data_dir": str(dataset.CSV_PATH.parent)} \
        if sandbox else None
    fn = make_llm_worker(caller, SALES_REPORT, ToolGate("worker", allowed, log), Memo(tmp_path / "memo.sqlite"),
                         log, tokens=20_000, usd=1.0, sandbox=box)
    out = fn(P)["results"]["T2"]
    names = [t.__name__ for t in model.bound_tools]
    return out, names, model.calls[0]["messages"][0].content, model, log


def test_without_sandbox_runpython_is_neither_offered_nor_described(tmp_path):
    out, names, prompt, _, _ = _offer(tmp_path, ["read_data", "run_python"], False,
                                      {"T2": [read_call(), submit_call(VALUES["T2"])]})
    assert out["value"] == VALUES["T2"]
    assert names == ["ReadData", "SubmitResult"]
    assert "ReadData" in prompt and "RunPython" not in prompt and "/data/penjualan.csv" not in prompt


def test_with_sandbox_runpython_is_offered_and_described(tmp_path):
    out, names, prompt, _, _ = _offer(tmp_path, ["read_data", "run_python"], True,
                                      {"T2": [read_call(), submit_call(VALUES["T2"])]})
    assert out["value"] == VALUES["T2"]
    assert names == ["ReadData", "SubmitResult", "RunPython"]
    assert "RunPython" in prompt and "/data/penjualan.csv" in prompt and "ReadData" in prompt


def test_python_only_offers_and_describes_no_readdata_and_answers_it_as_unknown(tmp_path):
    out, names, prompt, model, log = _offer(tmp_path, ["run_python"], True,
                                            {"T2": [read_call(), submit_call(VALUES["T2"])]})
    assert names == ["SubmitResult", "RunPython"]
    assert "ReadData" not in prompt and "RunPython" in prompt
    assert out["value"] == VALUES["T2"]                         # the run went on: no PermissionDenied crash
    answer = model.calls[1]["messages"][-1]
    assert isinstance(answer, ToolMessage) and "Unknown tool 'ReadData'" in answer.content
    assert not any(e["event"] in ("tool_call", "tool_denied") for e in log.read())   # data never read


def test_unknown_tool_and_no_tool_call_are_answered_and_cost_a_step(tmp_path):
    script = good_script()
    script["T3"] = [reply("let me think"), reply("", tool_calls=[{"name": "Shell", "args": {}, "id": "x"}]),
                    read_call(), submit_call(VALUES["T3"])]
    r, model, _ = run(tmp_path, script)
    assert r["status"] == "DONE"
    calls = model.calls_for("T3")
    assert isinstance(calls[1]["messages"][-1], HumanMessage)                    # nudge after no tool call
    assert "Unknown tool 'Shell'" in calls[2]["messages"][-1].content


MIXED = {
    "valid submit + unknown tool": [{"name": "SubmitResult", "args": {"value": VALUES["T2"]}, "id": "s"},
                                    {"name": "Shell", "args": {}, "id": "x"}],
    "valid submit + ReadData": [{"name": "SubmitResult", "args": {"value": VALUES["T2"]}, "id": "s"},
                                {"name": "ReadData", "args": {}, "id": "r"}],
    "two submits, different values": [{"name": "SubmitResult", "args": {"value": VALUES["T2"]}, "id": "s1"},
                                      {"name": "SubmitResult", "args": {"value": [["A", 3], ["B", 2], ["C", 1]]},
                                       "id": "s2"}],
    "two identical valid submits": [{"name": "SubmitResult", "args": {"value": VALUES["T2"]}, "id": "s1"},
                                    {"name": "SubmitResult", "args": {"value": VALUES["T2"]}, "id": "s2"}],
}


@pytest.mark.parametrize("case", sorted(MIXED))
def test_submission_mixed_with_other_tool_calls_is_rejected(tmp_path, case):
    """GPT audit 2c (P2): a SubmitResult must be the only tool call in its reply."""
    fn, model, log = _worker(tmp_path, {"T2": [read_call(), reply("", tool_calls=MIXED[case]),
                                               submit_call(VALUES["T2"], id="final")]})
    out = fn(P)
    assert out["results"]["T2"]["value"] == VALUES["T2"] and "error" not in out["results"]["T2"]
    assert len(model.calls) == 3                               # rejected, then a clean submission
    assert _tool_runs(log) == 1                                # only the first ReadData ran; nothing in the mix
    answers = [m for m in model.calls[2]["messages"] if isinstance(m, ToolMessage)][-len(MIXED[case]):]
    assert [m.tool_call_id for m in answers] == [c["id"] for c in MIXED[case]]
    assert all("must be the only tool call" in m.content for m in answers)
    (rej,) = [e for e in log.read() if e["event"] == "submission_rejected"]
    assert rej["step"] == 1


def test_mixed_submissions_every_time_end_in_max_steps(tmp_path):
    fn, model, log = _worker(tmp_path, {"T2": [reply("", tool_calls=MIXED["valid submit + ReadData"])] * 3},
                             max_steps=3)
    out = fn(P)
    assert out["results"]["T2"]["value"] is None
    assert out["results"]["T2"]["error"].startswith("max_steps")
    assert _tool_runs(log) == 0


def test_max_steps_ends_the_worker_with_a_reason(tmp_path):
    cfg = cfg_llm(max_iterations=1)
    cfg["roles"]["worker"]["max_steps"] = 2
    script = good_script()
    script["T3"] = [read_call(), read_call("r2")]
    r, model, evs = run(tmp_path, script, cfg=cfg)
    assert len(model.calls_for("T3")) == 2
    (failed,) = [e for e in evs if e["event"] == "worker_failed"]
    assert failed["task"] == "T3" and failed["error"].startswith("max_steps")
    assert r["status"] == "FAILED_BUDGET"                     # report incomplete, no budget for iteration 2


def test_worker_reservation_too_small_refuses_before_sending(tmp_path):
    cfg = cfg_llm(max_iterations=1)
    cfg["token_estimates"]["worker"] = 200
    r, model, evs = run(tmp_path, good_script(), cfg=cfg)
    assert model.calls == []
    assert {e["task"] for e in evs if e["event"] == "worker_failed"} == {"T1", "T2", "T3"}


def test_permanent_model_error_fails_the_worker_not_the_run(tmp_path):
    script = good_script()
    script["T1"] = [FakeHTTPError(400, "bad request")]
    r, _, evs = run(tmp_path, script, cfg=cfg_llm(max_iterations=1))
    (failed,) = [e for e in evs if e["event"] == "worker_failed"]
    assert failed["task"] == "T1" and failed["error"].startswith("llm_failed")
    assert r["status"] in ("DONE", "FAILED_BUDGET")           # T1 (data_check) is optional for the report


def test_output_validator():
    assert validate_output("top3", VALUES["T2"]) == []
    assert validate_output("trend", VALUES["T3"]) == []
    assert validate_output("trend", [["2026-13", 1]])
    assert validate_output("trend", [["2026-02", 1], ["2026-01", 1]])
    assert validate_output("data_check", {})


# ---- the step memo, in process --------------------------------------------------------------------

def _worker(tmp_path, script, tokens=20_000, model_ref=None, max_steps=6):
    cfg = cfg_llm()
    if model_ref:
        cfg["roles"]["worker"]["model"] = model_ref
    log = EventLog(tmp_path / "e.jsonl")
    model = ScriptedChatModel(script=script)
    caller = LLMCaller(cfg, "worker", log, model=model)
    gate = ToolGate("worker", ["read_data"], log)
    fn = make_llm_worker(caller, SALES_REPORT, gate, Memo(tmp_path / "memo.sqlite"), log,
                         tokens=tokens, usd=1.0, max_steps=max_steps)
    return fn, model, log


P = {"task": {"id": "T2", "output": "top3", "instruction": "Compute the top 3 products.", "feedback": ""},
     "iteration": 0}


def _tool_runs(log):
    return sum(e["event"] == "tool_call" for e in log.read())


def test_rerunning_a_finished_worker_makes_zero_calls_and_runs_zero_tools(tmp_path):
    fn, model, log = _worker(tmp_path, {"T2": [read_call(), submit_call(VALUES["T2"])]})
    first = fn(P)
    calls, tools = len(model.calls), _tool_runs(log)
    second = fn(P)                                             # same node run, e.g. after a crash
    assert len(model.calls) == calls == 2 and _tool_runs(log) == tools == 1
    assert second["results"] == first["results"]
    replayed = Counter(e["kind"] for e in log.read() if e["event"] == "step_replayed")
    assert replayed == {"llm": 2, "tool": 2}


def test_changed_feedback_does_not_reuse_the_memo(tmp_path):
    fn, model, log = _worker(tmp_path, {"T2": [read_call(), submit_call(VALUES["T2"])] * 2})
    fn(P)
    changed = {**P, "task": {**P["task"], "feedback": "sum per product"}}
    fn(changed)
    assert len(model.calls) == 4 and _tool_runs(log) == 2


def test_changed_tool_version_reruns_the_tool_only(tmp_path, monkeypatch):
    fn, model, log = _worker(tmp_path, {"T2": [read_call(), submit_call(VALUES["T2"])]})
    fn(P)
    monkeypatch.setitem(llm_worker.TOOL_VERSIONS, "ReadData", "2")
    fn(P)
    assert _tool_runs(log) == 2                               # ReadData re-executed under its new version
    assert len(model.calls) == 2                              # same tool output -> model steps still replay


def test_changed_model_does_not_reuse_the_memo(tmp_path):
    fn, model, _ = _worker(tmp_path, {"T2": [read_call(), submit_call(VALUES["T2"])]})
    fn(P)
    fn2, model2, _ = _worker(tmp_path, {"T2": [read_call(), submit_call(VALUES["T2"])]},
                             model_ref="anthropic:claude-haiku-5-5")
    fn2(P)
    assert len(model2.calls) == 2


# ---- replies cut off at max_tokens (2e smoke: a revised plan stopped at exactly its 905-token cap) ----

def cut_submit(value, id="s0"):
    """A SubmitResult whose value would pass validation, in a reply the provider cut off."""
    return reply("", input_tokens=900, output_tokens=1058, stop_reason="max_tokens",
                 tool_calls=[{"name": "SubmitResult", "args": {"value": value}, "id": id}])


def test_truncated_reply_is_neither_run_nor_accepted_nor_retried(tmp_path):
    fn, model, log = _worker(tmp_path, {"T2": [read_call(), cut_submit(VALUES["T2"]), submit_call(VALUES["T2"])]})
    out = fn(P)["results"]["T2"]
    assert out["value"] is None and out["error"].startswith("output_truncated")
    assert len(model.calls) == 2                               # no further step after the cut-off reply
    evs = log.read()
    assert [e["tools"] for e in evs if e["event"] == "reply_truncated"] == [["SubmitResult"]]
    assert not any(e["event"] == "worker_submitted" for e in evs)
    assert not any(e["event"] == "step_committed" and e["kind"] == "tool" and e["step"] == 1 for e in evs)
    (cut,) = [e for e in evs if e["event"] == "llm_call" and e.get("truncated")]
    assert cut["step"] == 1 and any(e["event"] == "output_truncated" for e in evs)


def test_truncated_reply_stays_unaccepted_when_replayed_after_a_crash(tmp_path):
    fn, model, log = _worker(tmp_path, {"T2": [read_call(), cut_submit(VALUES["T2"])]})
    fn(P)
    again = fn(P)["results"]["T2"]                             # same node run, e.g. after a crash
    assert again["value"] is None and again["error"].startswith("output_truncated")
    assert len(model.calls) == 2                               # both steps came from the memo
    replayed = [e for e in log.read() if e["event"] == "step_replayed" and e["kind"] == "llm"]
    assert [e["step"] for e in replayed] == [0, 1]


def test_llm_estimates_size_the_llm_worker_and_the_iteration(tmp_path):
    from harness.budget import effective_estimates, iteration_cost, iteration_usd, node_usd_estimates
    cfg = copy.deepcopy(load_config())
    assert effective_estimates(cfg) == cfg["token_estimates"]  # fake nodes: the M1 figures, untouched
    assert iteration_cost(effective_estimates(cfg), 3) == 11_500
    cfg["impl"].update(orchestrator="llm", worker="llm")
    est = effective_estimates(cfg)
    assert est["orchestrator"] == est["worker"] == 12_000 and est["synthesize"] == 1_000
    assert iteration_cost(est, 3) == 50_500
    usd = node_usd_estimates(cfg)                              # the USD worst case uses the same tokens
    assert usd["orchestrator"] == pytest.approx(12_000 * 10.00 / 1e6)   # sonnet-5-5, dearer rate
    assert usd["worker"] == pytest.approx(12_000 * 0.50 / 1e6)          # haiku-5-5
    assert iteration_usd(usd, 3) == pytest.approx(0.138)


def test_llm_worker_gets_its_llm_estimate_as_reservation(tmp_path):
    # Step 1 alone needs ~2,700 tokens: refused under the 2,000 fake-worker estimate, fine under 12,000.
    big = reply("", input_tokens=1700, output_tokens=1000,
                tool_calls=[{"name": "SubmitResult", "args": {"value": VALUES["T2"]}, "id": "s1"}])
    script = {t: [read_call(), submit_call(v)] for t, v in VALUES.items()}
    script["T2"] = [read_call(), big]
    cfg = copy.deepcopy(load_config())
    cfg["impl"]["worker"] = "llm"
    cfg["roles"]["worker"]["model"] = "fake:scripted"
    cfg["llm"]["base_delay"] = 0
    r, _, evs = run(tmp_path, script, cfg=cfg)
    assert r["status"] == "DONE", [e for e in evs if e["event"] in ("worker_failed", "llm_call")]
    assert not any(e["event"] == "llm_call" and e["status"] == "refused" for e in evs)


class ProcessDied(BaseException):
    """A hard crash mid-request: not an Exception, so the wrapper cannot catch it."""


def test_spend_before_a_crash_counts_against_the_same_node_run(tmp_path):
    fn, model, log = _worker(tmp_path, {"T2": [read_call(), ProcessDied(), submit_call(VALUES["T2"])]})
    with pytest.raises(ProcessDied):
        fn(P)                                                  # step 0 committed, step 1 cut off
    out = fn(P)                                                # resume
    mine = [e for e in log.read() if e.get("node") == "worker" and e.get("task") == "T2"]
    _, totals = reconcile_ledger(mine)
    assert totals["unknown_after_crash"] == 1
    assert out["tokens_used"] == totals["tokens"]             # node reports all of it, from the ledger
    assert len(model.calls) == 3                               # step 0 replayed, step 1 called again


def test_reservation_holds_across_a_crash(tmp_path):
    # Measured: before the crash this node run spent 430 (step 0) + 3,221 (step 1 cut off, worst case)
    # = 3,651 tokens; step 1 again needs >= 1,173 input + 64 output. With 4,000 reserved, a reservation
    # restored from the ledger must refuse; a fresh one (the bug this prevents) would allow it.
    fn, model, log = _worker(tmp_path, {"T2": [read_call(), ProcessDied(), submit_call(VALUES["T2"])]},
                             tokens=4_000)
    with pytest.raises(ProcessDied):
        fn(P)
    out = fn(P)
    assert out["tokens_used"] <= 4_000
    assert out["results"]["T2"].get("error", "").startswith("node_reservation")
    assert len(model.calls) == 2                              # the refused call was never sent


# ---- crash-resume across processes --------------------------------------------------------------

def _json_reply(tool, args, id):
    return {"tool_calls": [{"name": tool, "args": args, "id": id}], "usage": {"input_tokens": 500, "output_tokens": 50}}


def _cli(tmp_path, *extra, orchestrator="fake"):
    cfg = cfg_llm()
    cfg["impl"]["orchestrator"] = orchestrator
    if orchestrator == "llm":
        cfg["roles"]["orchestrator"]["model"] = "fake:scripted"
        cfg["token_estimates"]["orchestrator"] = 12_000
    (tmp_path / "config.yaml").write_text(yaml.safe_dump(cfg))
    env = {**os.environ, "ARGUS_FAKE_SCRIPT": str(tmp_path / "script.json")}
    base = [sys.executable, "main.py", "--config", str(tmp_path / "config.yaml"), "--scenario", "pass",
            "--run-id", "rc", "--runs-dir", str(tmp_path / "runs"), "--quiet"]
    return subprocess.run(base + list(extra), cwd=ROOT, capture_output=True, text=True, env=env)


def _write_script(tmp_path, extra_default=None, redo=False):
    # A redone step consumes the *next* scripted reply. redo=True scripts "read, read, submit, submit" so
    # that a worker whose step 0 is bought twice still reads before it submits.
    if redo:
        script = {t: [_json_reply("ReadData", {}, "r1"), _json_reply("ReadData", {}, "r2"),
                      _json_reply("SubmitResult", {"value": v}, "s1"), _json_reply("SubmitResult", {"value": v}, "s2")]
                  for t, v in VALUES.items()}
    else:  # one spare reply each, used only if a sibling's step is legitimately redone
        script = {t: [_json_reply("ReadData", {}, "r1"), _json_reply("SubmitResult", {"value": v}, "s1"),
                      _json_reply("SubmitResult", {"value": v}, "s9")] for t, v in VALUES.items()}
    if extra_default:
        script["default"] = extra_default
    (tmp_path / "script.json").write_text(json.dumps(script))


def _model_calls(tmp_path, key):
    p = Path(pos_path(str(tmp_path / "script.json"), key))
    return int(p.read_text()) if p.exists() else 0


def _crash_and_resume(tmp_path, point, **kw):
    r1 = _cli(tmp_path, "--crash-at", point, **kw)
    assert r1.returncode == 42, r1.stderr
    r2 = _cli(tmp_path, "--resume", **kw)
    assert r2.returncode == 0, r2.stderr
    run_dir = tmp_path / "runs" / "rc"
    return json.loads((run_dir / "result.json").read_text()), events(run_dir / "events.jsonl")


def _assert_no_committed_step_redone(evs):
    names = [e["event"] for e in evs]
    crash = names.index("crash_simulated")
    before, after = evs[:crash], evs[crash:]
    committed_llm = {(e["task"], e["step"]) for e in before if e["event"] == "step_committed" and e["kind"] == "llm"}
    called_after = {(e["task"], e["step"]) for e in after if e["event"] == "llm_call" and e.get("node") == "worker"}
    assert not committed_llm & called_after, committed_llm & called_after
    committed_tool = {(e["task"], e["step"], e["tool"]) for e in before
                      if e["event"] == "step_committed" and e["kind"] == "tool"}
    run_after = {(e["task"], e["step"], e["tool"]) for e in after
                 if e["event"] == "step_committed" and e["kind"] == "tool"}
    assert not committed_tool & run_after, committed_tool & run_after


CRASH_REPEATS = int(os.environ.get("CRASH_REPEATS", "1"))


@pytest.mark.parametrize("repeat", range(CRASH_REPEATS))
@pytest.mark.parametrize("point", ["worker@llm_committed", "worker@tool_committed"])
def test_crash_after_a_committed_step_redoes_nothing(tmp_path, point, repeat):
    _write_script(tmp_path)
    result, evs = _crash_and_resume(tmp_path, point)
    assert result["status"] == "DONE" and result["iteration"] == 1
    crash = next(e for e in evs if e["event"] == "crash_simulated")
    task = crash["task"]
    assert _model_calls(tmp_path, task) == 2                  # exactly the uncrashed number: zero re-calls
    reads = [e for e in evs if e["event"] == "step_committed" and e["kind"] == "tool"
             and e["task"] == task and e["tool"] == "ReadData"]
    assert len(reads) == 1                                     # the tool ran once
    _assert_no_committed_step_redone(evs)
    for t in VALUES:                                           # siblings: at most one legitimate redo each
        assert _model_calls(tmp_path, t) <= 3


@pytest.mark.parametrize("repeat", range(CRASH_REPEATS))
def test_crash_before_commit_redoes_one_call_and_counts_it(tmp_path, repeat):
    _write_script(tmp_path, redo=True)
    result, evs = _crash_and_resume(tmp_path, "worker@after_llm")
    assert result["status"] == "DONE"
    crash = next(e for e in evs if e["event"] == "crash_simulated")
    task = crash["task"]
    assert crash["step"] == 0
    assert _model_calls(tmp_path, task) == 3                  # step 0 bought twice (uncommitted), then step 1
    mine = [e for e in evs if e.get("node") == "worker" and e.get("task") == task]
    _, totals = reconcile_ledger(mine)
    assert totals["calls"] == 3                                # the ledger shows the redo
    (end,) = [e for e in evs if e["event"] == "node_end" and e["node"] == "worker" and e.get("task") == task]
    assert end["tokens"] == totals["tokens"]                   # and the node accounts for it
    _assert_no_committed_step_redone(evs)


def test_orchestrator_crash_mid_planning_counts_the_lost_call(tmp_path):
    plan = {"tasks": [{"id": t, "output": o, "instruction": f"Produce {o} from penjualan.csv exactly."}
                      for t, o in (("T1", "data_check"), ("T2", "top3"), ("T3", "trend"))]}
    default = [_json_reply("SubmitPlan", plan, "p1"), _json_reply("SubmitPlan", plan, "p2")]
    _write_script(tmp_path, extra_default=default)
    result, evs = _crash_and_resume(tmp_path, "orchestrator@after_llm", orchestrator="llm")
    assert result["status"] == "DONE"
    assert _model_calls(tmp_path, "default") == 2             # the plan was bought twice (not memoized)
    mine = [e for e in evs if e.get("node") == "orchestrator" and e.get("iteration") == 0]
    _, totals = reconcile_ledger(mine)
    (end,) = [e for e in evs if e["event"] == "node_end" and e["node"] == "orchestrator"]
    assert end["tokens"] == totals["tokens"]                   # both calls charged to the node run
    assert any(e["event"] == "reservation_restored" and e["node"] == "orchestrator" for e in evs)


def test_event_log_survives_a_line_cut_by_a_crash(tmp_path):
    path = tmp_path / "e.jsonl"
    EventLog(path).emit("first", n=1)
    with open(path, "a") as f:
        f.write('{"ts": 1, "event": "half-writ')          # process died mid-write
    log = EventLog(path)                                    # next process opens the log
    log.emit("second", n=2)
    assert [e["event"] for e in log.read()] == ["first", "second"]
