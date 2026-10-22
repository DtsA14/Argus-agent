"""D5 (docs/reviews/SPEC_D5_prompt_caching.md): prompt caching for Anthropic, priced and reserved honestly.

- Prices (section 9a, checked 2026-10-22 on Anthropic's pricing page): Sonnet 5.5 reads at $0.10/M (config.yaml had $0.20), writes
  at $2.50/M for 5 minutes and $4/M for 1 hour.
- LangChain's usage_metadata.input_tokens INCLUDES cache reads and writes (section 9b), so fresh = input - read - write.
- Before sending, every input token is priced at the dearer of input and 5-minute write: a hit is never assumed.
- Cache markers are added only to what is sent; prompt hashes and memo keys are the same with caching on or off.
fake:scripted is priced $1/M input, $5/M output, $1.25/M write (5m), $2/M write (1h), $0.10/M read (config.yaml).
"""
import copy
import json
import sys
from pathlib import Path

import pytest
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

import harness.llm as llm
from codetask import status as st
from codetask.run import apply_profile, run_code_task, settings
from harness.events import EventLog
from harness.llm import LLMCaller, Reservation, reconcile_ledger, to_nano
from models.fake import CallableChatModel, StrictScriptedChatModel, reply
from models.pricing import cost_usd
from models.registry import ConfigError
from runner import load_config

ROOT = Path(__file__).resolve().parent.parent
CONTRACT = json.loads((ROOT / "fixtures" / "contracts" / "fix_divide.json").read_text(encoding="utf-8"))
CALC = (ROOT / "fixtures" / "repos" / "calc" / "src" / "calc.py").read_text(encoding="utf-8")
TEST = (ROOT / "fixtures" / "repos" / "calc" / "tests" / "test_calc.py").read_text(encoding="utf-8")
FIXED = CALC.replace("    if b == 0:\n        return 0\n", "")
CLAIMS = [{"claim": "tests_pass", "evidence": "validation:unit"},
          {"claim": "issue_fixed", "evidence": "validation:target"},
          {"claim": "file_changed", "path": "src/calc.py"}]
SONNET = {"input": 2.00, "output": 10.00, "cache_read": 0.10, "cache_write_5m": 2.50, "cache_write_1h": 4.00}
on_vm = pytest.mark.skipif(sys.platform == "win32", reason="the path jail needs openat; the VM runs these")


class Crash(BaseException):
    pass


def cfg(cache=True, model="fake:scripted", **llm_over):
    c = load_config()
    c["roles"]["coder"]["model"] = model
    c["llm"]["base_delay"] = 0
    c["llm"]["prompt_cache"] = {"enabled": cache, "ttl": "5m"}
    c["llm"].update(llm_over)
    return c


def with_usage(text="ok", *, total_in, out, read=None, creation=None, e5=None, e1=None, tool_calls=None):
    """An AIMessage with usage as langchain_anthropic reports it: input_tokens is the TOTAL (uncached + read + write)."""
    details = {}
    if read is not None:
        details["cache_read"] = read
    if creation is not None:
        details["cache_creation"] = creation
    if e5 is not None or e1 is not None:
        details.update(ephemeral_5m_input_tokens=e5 or 0, ephemeral_1h_input_tokens=e1 or 0)
    return AIMessage(content=text, tool_calls=tool_calls or [],
                     usage_metadata={"input_tokens": total_in, "output_tokens": out, "total_tokens": total_in + out,
                                     "input_token_details": details})


def caller(config, model, counter=lambda m, t: 1000, log=None, tmp=None):
    log = log or EventLog(tmp / "e.jsonl")
    return LLMCaller(config, "coder", log, model=model, counter=counter), log


def ledger(log, kind="llm_call"):
    return [e for e in log.read() if e["event"] == kind]


MSGS = [SystemMessage("system rules"), HumanMessage("the task")]


# ---- 1. prices and the cost formula (K1) ------------------------------------------------------------------------

def test_the_configured_anthropic_prices_are_the_verified_ones():
    p = load_config()["prices"]
    assert {k: p["anthropic:claude-sonnet-5-5"].get(k) for k in SONNET} == SONNET          # read was 0.20
    assert p["anthropic:claude-opus-5-5"].get("cache_write_5m") == 5.00 and p["anthropic:claude-opus-5-5"]["cache_read"] == 0.20
    assert p["anthropic:claude-haiku-5-5"].get("cache_write_5m") == 0.125


def test_cost_prices_fresh_write_read_and_output_each_at_its_own_rate():                 # T1
    # input_tokens is the total: 1,000 uncached + 3,000 written + 6,000 read
    usd = cost_usd(SONNET, input_tokens=10000, output_tokens=500, cache_read_tokens=6000, cache_write_tokens=3000)
    assert to_nano(usd) == to_nano((1000 * 2.00 + 3000 * 2.50 + 6000 * 0.10 + 500 * 10.00) / 1e6) == 15_100_000
    one_hour = cost_usd(SONNET, input_tokens=10000, output_tokens=0, cache_write_1h_tokens=3000)
    assert to_nano(one_hour) == to_nano((7000 * 2.00 + 3000 * 4.00) / 1e6)
    assert cost_usd({"input": 2.0, "output": 10.0}, input_tokens=10, output_tokens=0, cache_write_tokens=5) is None  # no rate: unknown


# ---- 2. reserve with the write rate; 3. config errors (and K2) -------------------------------------------------

def test_the_output_cap_prices_every_input_token_as_a_write(tmp_path):                  # T2
    # $0.00135 left: 1,000 input at $1/M leaves room for 70 output tokens; at the $1.25/M write rate only 20 (< 64)
    res = lambda: Reservation(tokens=10**6, usd=0.00135)                                  # noqa: E731
    off, log_off = caller(cfg(cache=False), StrictScriptedChatModel(script=[reply("ok")]), tmp=tmp_path)
    off.call(MSGS, res())
    assert ledger(log_off)[0]["status"] == "ok"
    (tmp_path / "on").mkdir()
    on, log_on = caller(cfg(cache=True), StrictScriptedChatModel(script=[reply("ok")]), tmp=tmp_path / "on")
    with pytest.raises(llm.ReservationExhausted):
        on.call(MSGS, res())
    assert ledger(log_on)[0]["status"] == "refused" and not ledger(log_on, "llm_call_started")


def test_caching_an_anthropic_model_without_a_write_price_is_a_config_error(tmp_path):  # T3
    c = cfg(model="anthropic:claude-sonnet-5-5")
    del c["prices"]["anthropic:claude-sonnet-5-5"]["cache_write_5m"]
    model = StrictScriptedChatModel(script=[reply("ok")])
    with pytest.raises(ConfigError, match="cache_write_5m"):
        caller(c, model, tmp=tmp_path)
    assert model.calls == []
    caller(cfg(cache=False, model="anthropic:claude-sonnet-5-5"), model, tmp=tmp_path)   # caching off: no write rate needed


@pytest.mark.parametrize("model, ttl", [("anthropic:claude-haiku-5-5", "5m"), ("anthropic:claude-sonnet-5-5", "1h")])
def test_caching_haiku_or_a_one_hour_ttl_is_refused_in_d5(tmp_path, model, ttl):
    c = cfg(model=model)
    c["llm"]["prompt_cache"]["ttl"] = ttl
    with pytest.raises(ConfigError):
        caller(c, StrictScriptedChatModel(script=[]), tmp=tmp_path)


def test_a_haiku_coder_whose_calls_may_exceed_100k_input_is_a_config_error():           # K2: with or without caching
    c = cfg(cache=False, model="anthropic:claude-haiku-5-5")
    c["code_task"]["profiles"]["wide"] = {"attempt_tokens": 400000, "attempt_usd": 0.05, "max_input_tokens": 100001,
                                          "max_output_tokens": 4096}
    with pytest.raises(ConfigError, match="100,000"):
        settings(apply_profile(c, "wide"))
    c["code_task"]["profiles"]["wide"]["max_input_tokens"] = 100000
    settings(apply_profile(c, "wide"))                                                     # at the threshold: allowed
    c["code_task"]["profiles"]["wide"].pop("max_input_tokens")                             # no input limit: the attempt
    with pytest.raises(ConfigError, match="100,000"):                                      # tokens bound a call (400,000)
        settings(apply_profile(c, "wide"))


# ---- 4. the ledger; 7. usage as langchain_anthropic reports it (K3) --------------------------------------------

def test_the_ledger_records_reads_and_writes_apart_and_charges_them(tmp_path):         # T4, T7
    m = with_usage(total_in=10000, out=500, read=6000, creation=3000, e5=3000, e1=0)
    on, log = caller(cfg(), StrictScriptedChatModel(script=[m]), tmp=tmp_path)
    on.call(MSGS, Reservation(tokens=10**6, usd=1.0))
    e = ledger(log)[0]
    assert (e["input_tokens"], e["cache_read"], e["cache_creation"]) == (10000, 6000, 3000)
    assert e["usd_nano"] == to_nano((1000 * 1.0 + 3000 * 1.25 + 6000 * 0.10 + 500 * 5.0) / 1e6)
    assert not ledger(log, "cache_ttl_unexpected")


def test_the_generic_creation_count_without_a_ttl_breakdown_is_a_5_minute_write(tmp_path):     # T7, second shape
    m = with_usage(total_in=10000, out=0, read=0, creation=4000)
    on, log = caller(cfg(), StrictScriptedChatModel(script=[m]), tmp=tmp_path)
    on.call(MSGS, Reservation(tokens=10**6, usd=1.0))
    assert ledger(log)[0]["usd_nano"] == to_nano((6000 * 1.0 + 4000 * 1.25) / 1e6)


def test_a_one_hour_write_is_priced_as_one_and_reported(tmp_path):                     # K3 addition
    m = with_usage(total_in=10000, out=0, read=0, creation=0, e5=1000, e1=2000)   # langchain sets the generic key to 0
    on, log = caller(cfg(), StrictScriptedChatModel(script=[m]), tmp=tmp_path)
    on.call(MSGS, Reservation(tokens=10**6, usd=1.0))
    e = ledger(log)[0]
    assert e["cache_creation"] == 3000 and e["usd_nano"] == to_nano((7000 * 1.0 + 1000 * 1.25 + 2000 * 2.0) / 1e6)
    warn = ledger(log, "cache_ttl_unexpected")
    assert [(w["ephemeral_1h_input_tokens"], w["call_id"]) for w in warn] == [(2000, e["call_id"])]


def test_cache_creation_is_null_where_the_provider_has_no_such_thing(tmp_path):        # K3
    on, log = caller(cfg(), StrictScriptedChatModel(script=[reply("ok", input_tokens=900, output_tokens=10)]), tmp=tmp_path)
    on.call(MSGS, Reservation(tokens=10**6, usd=1.0))
    assert ledger(log)[0]["cache_creation"] is None
    (tmp_path / "z").mkdir()
    zero = with_usage(total_in=900, out=10, read=0, creation=0)                       # Anthropic, caching off: 0 reported
    off, log2 = caller(cfg(cache=False), StrictScriptedChatModel(script=[zero]), tmp=tmp_path / "z")
    off.call(MSGS, Reservation(tokens=10**6, usd=1.0))
    assert ledger(log2)[0]["cache_creation"] == 0


def test_usage_parsed_from_a_langchain_anthropic_response_is_not_counted_twice():       # T7, the real converter
    lca = pytest.importorskip("langchain_anthropic.chat_models")
    from anthropic.types import Usage
    raw = Usage.model_validate({"input_tokens": 1000, "output_tokens": 500, "cache_read_input_tokens": 6000,
                                "cache_creation_input_tokens": 3000,
                                "cache_creation": {"ephemeral_5m_input_tokens": 3000, "ephemeral_1h_input_tokens": 0}})
    um = lca._create_usage_metadata(raw)
    assert um["input_tokens"] == 10000                                                   # the total, as section 9b says
    from models.registry import cache_usage
    msg = AIMessage(content="ok", usage_metadata=um)
    assert cache_usage(msg) == {"read": 6000, "write_5m": 3000, "write_1h": 0, "creation": 3000}
    usd = cost_usd(SONNET, input_tokens=um["input_tokens"], output_tokens=500, cache_read_tokens=6000,
                   cache_write_tokens=3000)
    assert to_nano(usd) == 15_100_000


# ---- 5. markers only in what is sent; 6. hashes and memo keys unchanged -----------------------------------------

def marked(m):
    return isinstance(m.content, list) and any(isinstance(b, dict) and "cache_control" in b for b in m.content)


def test_markers_go_on_the_system_message_and_the_last_message_of_what_is_sent(tmp_path):     # T5
    model = StrictScriptedChatModel(script=[reply("ok")])
    on, log = caller(cfg(), model, tmp=tmp_path)
    msgs = [SystemMessage("rules"), HumanMessage("task"), AIMessage("thinking aloud"), HumanMessage("go on")]
    before = copy.deepcopy(msgs)
    on.call(msgs, Reservation(tokens=10**6, usd=1.0))
    sent = model.calls[0]["messages"]
    assert [marked(m) for m in sent] == [True, False, False, True]
    assert sum(marked(m) for m in sent) <= 4
    assert sent[0].content[-1]["cache_control"] == {"type": "ephemeral"}
    assert msgs == before and not any(marked(m) for m in msgs)                           # the caller's list is untouched
    (tmp_path / "off").mkdir()
    model_off = StrictScriptedChatModel(script=[reply("ok")])
    off, _ = caller(cfg(cache=False), model_off, tmp=tmp_path / "off")
    off.call(msgs, Reservation(tokens=10**6, usd=1.0))
    assert not any(marked(m) for m in model_off.calls[0]["messages"])


def fake_validate(spec, workspace, sandbox_cfg, log=None):
    ws = Path(workspace)
    ok = (ws / "src" / "calc.py").read_text() == FIXED and (ws / "tests" / "test_calc.py").read_text() == TEST
    return {"id": f"validation:{spec['id']}", "layer": "C", "status": "pass" if ok else "fail", "reason": "",
            "evidence": {"must_pass": {t: "ok" if ok else "FAIL" for t in spec.get("must_pass", [])},
                         "tests_run": 7, "failures": 0 if ok else 1, "output_tail": ""}}


def call(name, args, id):
    return reply(tool_calls=[{"name": name, "args": args, "id": id}], input_tokens=500, output_tokens=60)


SCRIPT = [call("ReadFile", {"path": "src/calc.py"}, "r1"), call("WriteFile", {"path": "src/calc.py", "content": FIXED}, "w1"),
          call("Finish", {"claims": CLAIMS, "summary": "divide raises on zero"}, "f1")]


def run(tmp_path, config):
    path = tmp_path / "contract.json"
    path.write_text(json.dumps(CONTRACT), encoding="utf-8")
    model = StrictScriptedChatModel(script=list(SCRIPT))
    r = run_code_task(contract_path=path, run_id="t", runs_dir=tmp_path / "runs", cfg=config, models={"coder": model},
                      validate=fake_validate, preflight=lambda: (True, "ok"))
    return r, model, tmp_path / "runs" / "t"


@on_vm
def test_caching_changes_neither_prompt_hashes_nor_memo_keys(tmp_path):                 # T5, T6
    import sqlite3
    out = {}
    for name, cache in (("off", False), ("on", True)):
        (tmp_path / name).mkdir()
        r, model, d = run(tmp_path / name, cfg(cache=cache))
        assert r["status"] == st.DONE
        evs = [json.loads(l) for l in (d / "events.jsonl").read_text().splitlines() if l.strip()]
        keys = sorted(k for (k,) in sqlite3.connect(d / "memo.sqlite").execute("select key from memo"))
        values = "".join(v for (v,) in sqlite3.connect(d / "memo.sqlite").execute("select value from memo"))
        out[name] = ([e["prompt_hash"] for e in evs if e["event"] == "llm_call_started"], keys)
        assert "cache_control" not in values                                             # nothing stored carries a marker
        if cache:
            last = model.calls[1]["messages"]
            assert marked(last[0]) and marked(last[-1]) and isinstance(last[-1], ToolMessage)
            assert not any(marked(m) for m in last[1:-1])
        # the scripted replies report reads (0) but no writes: nothing saved, creation unknown (null, K3)
        assert r.get("cache") == {"cache_read_tokens": 0, "cache_creation_tokens": None, "usd_saved_estimate": 0.0}
    assert out["on"] == out["off"]


# ---- 8. a crash mid-call is charged at the write-rate worst case -----------------------------------------------

def test_a_call_cut_off_by_a_crash_is_charged_at_the_write_rate(tmp_path):              # T8
    def die(messages):
        raise Crash()
    on, log = caller(cfg(), CallableChatModel(respond=die), counter=lambda m, t: 10000, tmp=tmp_path)
    with pytest.raises(Crash):
        on.call(MSGS, Reservation(tokens=10**6, usd=1.0))
    started = ledger(log, "llm_call_started")[0]
    cap = started["max_tokens"]
    assert started["worst_usd_nano"] == to_nano((10000 * 1.25 + cap * 5.0) / 1e6)
    _, totals = reconcile_ledger(log.read())
    assert totals["unknown_after_crash"] == 1 and totals["usd_nano"] == started["worst_usd_nano"]
