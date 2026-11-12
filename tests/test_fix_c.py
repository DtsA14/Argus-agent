"""FIX-C: the event log is on disk before emit returns (D2), and a registered API key value never reaches the event log or
an error text (D7; attack A9 of FABLE_INJECTION_ATTACKS.md as a test)."""
import copy
import json
import os
from pathlib import Path

import pytest
from langchain_core.messages import HumanMessage

from harness import redact
from harness.errors import LLMCallFailed
from harness.events import EventLog, TaggedLog
from harness.llm import LLMCaller, Reservation
from models import registry
from models.fake import FakeHTTPError, ScriptedChatModel, reply
from runner import load_config

CANARY = "sk-CANARY-NOT-A-KEY-1234567890"


@pytest.fixture(autouse=True)
def forget():
    redact.clear()
    yield
    redact.clear()


# ---- D2: on disk before emit returns -------------------------------------------------------------------------------

def test_every_record_is_flushed_and_fsynced_before_emit_returns(tmp_path, monkeypatch):
    path = tmp_path / "e.jsonl"
    log = EventLog(path)
    seen = []

    def fake_fsync(fd):
        seen.append(Path(path).read_text(encoding="utf-8"))   # what a reader sees at the moment of the fsync
    monkeypatch.setattr(os, "fsync", fake_fsync)
    log.emit("llm_call_started", call_id="c1")
    log.emit("llm_call", call_id="c1", status="ok")
    assert len(seen) == 2                                      # one fsync per record
    assert '"call_id": "c1"' in seen[0] and seen[0].count("\n") == 1   # already written (flushed) when fsync ran
    assert seen[1].count("\n") == 2


def test_a_failing_fsync_is_not_swallowed(tmp_path, monkeypatch):
    log = EventLog(tmp_path / "e.jsonl")
    monkeypatch.setattr(os, "fsync", lambda fd: (_ for _ in ()).throw(OSError("disk")))
    with pytest.raises(OSError):
        log.emit("x")


def test_tagged_logs_and_reading_still_work(tmp_path):
    log = EventLog(tmp_path / "e.jsonl")
    TaggedLog(log, origin="auto").emit("sandbox_run", n=1)
    assert log.read()[0]["origin"] == "auto"


# ---- D7: the scrub ---------------------------------------------------------------------------------------------------

def test_a_registered_value_is_replaced_everywhere_in_a_text():
    redact.register(CANARY)
    assert redact.scrub(f"Bearer {CANARY} and {CANARY}!") == f"Bearer {redact.MARK} and {redact.MARK}!"
    assert redact.scrub("nothing here") == "nothing here" and redact.scrub("") == ""
    assert redact.scrub(None) is None and redact.scrub(7) == 7 and redact.scrub(b"x") == b"x"


def test_the_longer_value_is_hidden_whole_when_one_contains_the_other():
    redact.register("sk-short-key")
    redact.register("sk-short-key-and-a-long-tail")
    assert redact.scrub("x sk-short-key-and-a-long-tail y") == f"x {redact.MARK} y"


@pytest.mark.parametrize("weak", ["", "unused", "short", "       ", None, 12345678, b"sk-bytes-key-123"])
def test_a_value_too_short_or_not_a_string_is_never_registered(weak):
    redact.register(weak)
    assert redact.scrub("unused short 12345678 sk-bytes-key-123") == "unused short 12345678 sk-bytes-key-123"


def test_the_event_log_hides_a_key_anywhere_in_a_record_and_on_the_echo(tmp_path, capsys):
    redact.register(CANARY)
    log = EventLog(tmp_path / "e.jsonl", echo=True)
    log.emit("llm_call", status="error", error=f"401 {CANARY}", nested={"a": [f"x{CANARY}y", 1]}, ok=1)
    raw = (tmp_path / "e.jsonl").read_text(encoding="utf-8")
    assert CANARY not in raw and redact.MARK in raw
    rec = json.loads(raw)
    assert rec["nested"] == {"a": [f"x{redact.MARK}y", 1]} and rec["ok"] == 1 and rec["event"] == "llm_call"
    assert CANARY not in capsys.readouterr().out


def test_a_failed_model_call_message_hides_a_key():
    redact.register(CANARY)
    assert CANARY not in str(LLMCallFailed(f"worker: AuthError: bad {CANARY}"))
    assert str(LLMCallFailed("plain")) == "plain" and str(LLMCallFailed()) == ""


def test_building_a_client_registers_the_key_it_reads(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", CANARY)
    cfg = load_config()
    pcfg = cfg["providers"]["anthropic"]
    registry._api_key(registry.ModelRef("anthropic", "m"), pcfg)
    assert redact.scrub(f"leak {CANARY}") == f"leak {redact.MARK}"


# ---- A9: a provider error that echoes the key ----------------------------------------------------------------------

def caller(tmp_path, script):
    cfg = copy.deepcopy(load_config())
    cfg["llm"].update({"base_delay": 0})
    fake = ScriptedChatModel(script=list(script))
    log = EventLog(tmp_path / "e.jsonl")
    return LLMCaller(cfg, "worker", log, model=fake, counter=lambda m, t: 100, sleep=lambda s: None), tmp_path / "e.jsonl"


def test_a9_a_permanent_provider_error_with_the_key_reaches_neither_the_ledger_nor_the_exception(tmp_path):
    redact.register(CANARY)
    c, log = caller(tmp_path, [FakeHTTPError(401, f"invalid x-api-key: {CANARY}")])
    with pytest.raises(LLMCallFailed) as e:
        c.call([HumanMessage("hi")], Reservation(tokens=100_000, usd=1.0))
    assert CANARY not in str(e.value)
    raw = log.read_text(encoding="utf-8")
    assert CANARY not in raw and "invalid x-api-key" in raw          # the rest of the error text is still there


def test_a9_a_transient_error_retried_then_failed_hides_the_key_in_every_event(tmp_path):
    redact.register(CANARY)
    c, log = caller(tmp_path, [FakeHTTPError(500, f"upstream echoed {CANARY}")] * 8)
    with pytest.raises(LLMCallFailed) as e:
        c.call([HumanMessage("hi")], Reservation(tokens=100_000, usd=1.0))
    assert CANARY not in str(e.value) and CANARY not in log.read_text(encoding="utf-8")
