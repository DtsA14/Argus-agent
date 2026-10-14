"""Fixes from the GPT audit of phase 2a: unpriced models, full-context counting, ledger lifecycle with
call_id and crash reconciliation, explicit budget violations, structured meta, full USD precision."""
import copy
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from harness.errors import LLMCallFailed, ReservationExhausted
from harness.events import EventLog
from harness.llm import LLMCaller, Reservation, heuristic_counter, reconcile_ledger
from models.fake import FakeHTTPError, ScriptedChatModel, reply
from models.registry import ConfigError
from runner import load_config, run_task

OFF_PEAK = datetime(2026, 10, 17, 2, tzinfo=timezone.utc)
MSGS = [HumanMessage("hello")]


def events(path):
    return [json.loads(l) for l in Path(path).read_text(encoding="utf-8").splitlines()]


def make(tmp_path, script, *, est_in=100, cfg=None, counter="fixed", log=None):
    cfg = cfg or copy.deepcopy(load_config())
    cfg["llm"]["base_delay"] = 0
    fake = ScriptedChatModel(script=list(script))
    log = log or EventLog(tmp_path / "e.jsonl")
    kw = {} if counter is None else {"counter": lambda m, t: est_in}
    caller = LLMCaller(cfg, "worker", log, model=fake, sleep=lambda s: None, now=OFF_PEAK, **kw)
    return caller, fake, tmp_path / "e.jsonl"


# ---- #3 unpriced models cannot slip past the USD budget -----------------------------------

def test_unpriced_model_never_reports_zero_dollars(tmp_path):
    cfg = copy.deepcopy(load_config())
    cfg["roles"]["worker"]["model"] = "openai:gpt-5.6-sol"
    cfg["budget"].update(max_usd=None, allow_unpriced=True)
    caller, _, log = make(tmp_path, [reply(input_tokens=10, output_tokens=5)], cfg=cfg)
    res = Reservation(tokens=10_000, usd=float("inf"))
    caller.call(MSGS, res)
    final = [e for e in events(log) if e["event"] == "llm_call"][0]
    assert final["usd"] is None                       # unknown, not $0
    _, totals = reconcile_ledger(events(log))
    assert totals["usd_complete"] is False


def test_unpriced_llm_node_blocks_the_run_while_usd_is_capped():
    from harness.budget import node_usd_estimates
    cfg = copy.deepcopy(load_config())
    cfg["roles"]["worker"]["model"] = "openai:gpt-5.6-sol"
    cfg["budget"]["allow_unpriced"] = True
    with pytest.raises(ConfigError, match="cannot be capped"):
        node_usd_estimates(cfg)


# ---- P2 the heuristic counts the whole tool-calling context ---------------------------------

def test_heuristic_counts_tool_call_arguments_and_tool_results():
    count, _ = heuristic_counter(1.2)
    base = [HumanMessage("x")]
    long_args = {"code": "y" * 6000}
    loop = base + [AIMessage("", tool_calls=[{"name": "run_python", "args": long_args, "id": "c1"}]),
                   ToolMessage("z" * 3000, tool_call_id="c1")]
    assert count(loop, None) - count(base, None) >= (6000 + 3000) / 3   # every character is counted


@pytest.mark.parametrize("rounds", [1, 3, 6])
def test_multi_round_tool_loop_estimate_is_not_below_the_text_sent(rounds):
    count, _ = heuristic_counter(1.2)
    msgs = [HumanMessage("compute the trend")]
    for i in range(rounds):
        msgs.append(AIMessage("thinking " * 20, tool_calls=[{"name": "run_python",
                                                             "args": {"code": f"print({i})\n" * 200}, "id": f"c{i}"}]))
        msgs.append(ToolMessage("result line\n" * 150, tool_call_id=f"c{i}"))
    sent_chars = sum(len(m.content) for m in msgs) + sum(
        len(json.dumps(tc["args"])) for m in msgs for tc in (getattr(m, "tool_calls", None) or []))
    assert count(msgs, None) >= sent_chars / 3


# ---- P1 ledger lifecycle: call_id, started before sending, final after -----------------------

def test_every_sent_attempt_has_started_and_final_with_the_same_call_id(tmp_path):
    caller, _, log = make(tmp_path, [FakeHTTPError(429), reply()])
    caller.call(MSGS, Reservation(tokens=100_000, usd=1.0))
    evs = events(log)
    started = [e for e in evs if e["event"] == "llm_call_started"]
    final = [e for e in evs if e["event"] == "llm_call"]
    assert [e["call_id"] for e in started] == [e["call_id"] for e in final]
    assert len({e["call_id"] for e in started}) == 2
    for s, f in zip(started, final):
        assert evs.index(s) < evs.index(f)              # started is written before the request


def test_refused_call_has_no_started_event(tmp_path):
    caller, fake, log = make(tmp_path, [reply()], est_in=10_000)
    with pytest.raises(ReservationExhausted):
        caller.call(MSGS, Reservation(tokens=10_050, usd=1.0))
    assert not [e for e in events(log) if e["event"] == "llm_call_started"] and fake.calls == []


class ProcessDied(BaseException):
    """Stands in for a hard crash mid-request: not an Exception, so nothing in the wrapper catches it."""


def test_crash_mid_request_is_reconciled_at_worst_case(tmp_path):
    caller, fake, log = make(tmp_path, [reply(input_tokens=100, output_tokens=10), ProcessDied()])
    res = Reservation(tokens=100_000, usd=1.0)
    caller.call(MSGS, res)
    with pytest.raises(ProcessDied):
        caller.call(MSGS, res)
    records, totals = reconcile_ledger(events(log))
    assert [r["status"] for r in records] == ["ok", "unknown_after_crash"]
    started = [e for e in events(log) if e["event"] == "llm_call_started"][1]
    assert records[1]["tokens"] == started["worst_tokens"]
    assert records[1]["usd_nano"] == started["worst_usd_nano"] > 0
    assert totals["unknown_after_crash"] == 1
    assert totals["usd_nano"] == records[0]["usd_nano"] + started["worst_usd_nano"]


def test_charge_happens_even_if_writing_the_ledger_fails(tmp_path):
    class FailingLog(EventLog):
        def emit(self, event, **fields):
            if event == "llm_call" and fields.get("status") == "ok":
                raise OSError("disk full")
            super().emit(event, **fields)

    caller, _, log = make(tmp_path, [reply(input_tokens=100, output_tokens=10)],
                          log=FailingLog(tmp_path / "e.jsonl"))
    res = Reservation(tokens=100_000, usd=1.0)
    with pytest.raises(OSError):
        caller.call(MSGS, res)
    assert res.used_tokens == 110                      # in-memory budget still reflects the spend
    _, totals = reconcile_ledger(events(log))
    assert totals["unknown_after_crash"] == 1          # and the ledger counts it at worst case


def test_error_delivery_distinguishes_received_from_unknown(tmp_path):
    caller, _, log = make(tmp_path, [FakeHTTPError(503), TimeoutError("read timeout"), reply()])
    caller.call(MSGS, Reservation(tokens=100_000, usd=1.0))
    final = [e for e in events(log) if e["event"] == "llm_call"]
    assert [(e["status"], e.get("delivery")) for e in final] == [
        ("transient_error", "received"), ("transient_error", "unknown"), ("ok", None)]


# ---- P1 estimate miss over the reservation is an explicit budget violation ---------------------

def test_overshoot_is_a_budget_violation_and_closes_the_reservation(tmp_path):
    caller, fake, log = make(tmp_path, [reply(input_tokens=5_000, output_tokens=10), reply()], est_in=100)
    res = Reservation(tokens=1_000, usd=1.0)
    caller.call(MSGS, res)                              # provider billed far more input than estimated
    assert res.violated and res.used_tokens == 5_010
    kinds = [e["event"] for e in events(log)]
    assert "estimate_miss" in kinds and "budget_violation" in kinds
    with pytest.raises(ReservationExhausted):           # no further calls on a violated reservation
        caller.call(MSGS, res)
    assert len(fake.calls) == 1


def test_a_node_over_its_estimate_ends_the_run_as_failed_budget(tmp_path):
    cfg = copy.deepcopy(load_config())
    cfg["token_estimates"]["worker"] = 1_999            # the fake worker reports 2,000
    r = run_task(goal="x", scenario="pass", run_id="t", runs_dir=tmp_path, cfg=cfg)
    assert r["status"] == "FAILED_BUDGET" and r["stop_reason"].startswith("budget_violation")
    assert r["budget_violations"] == 1
    assert json.loads((tmp_path / "t" / "result.json").read_text())["status"] == "FAILED_BUDGET"


# ---- structured meta -------------------------------------------------------------------------

@pytest.mark.parametrize("meta", [{"role": "orchestrator"}, {"model": "spoofed"}, {"call_id": "x"},
                                  {"status": "ok"}, {"usd": 0}, {"anything": 1}])
def test_meta_cannot_override_or_add_system_fields(tmp_path, meta):
    caller, fake, _ = make(tmp_path, [reply()])
    with pytest.raises(ValueError, match="meta keys not allowed"):
        caller.call(MSGS, Reservation(tokens=100_000, usd=1.0), meta=meta)
    assert fake.calls == []                             # rejected before anything is sent


def test_structured_meta_is_recorded(tmp_path):
    caller, _, log = make(tmp_path, [reply()])
    meta = {"run_id": "r1", "node": "worker", "task": "T2", "iteration": 1, "step": 3}
    caller.call(MSGS, Reservation(tokens=100_000, usd=1.0), meta=meta)
    for e in events(log):
        if e["event"].startswith("llm_call"):
            assert {k: e[k] for k in meta} == meta and e["role"] == "worker"


# ---- full USD precision -----------------------------------------------------------------------

def test_ledger_usd_is_full_precision(tmp_path):
    caller, _, log = make(tmp_path, [reply(input_tokens=7, output_tokens=3)] * 20)
    res = Reservation(tokens=10**6, usd=1.0)
    for _ in range(20):
        caller.call(MSGS, res)
    _, totals = reconcile_ledger(events(log))
    assert totals["usd_nano"] == res.used_nano           # exact integer nano-dollars on both sides
    assert totals["usd"] == res.used_usd
    assert sum(e["usd_nano"] for e in events(log) if e["event"] == "llm_call") == res.used_nano
