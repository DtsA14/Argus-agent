"""FIX-C: the event log is on disk before emit returns (D2), and a registered API key value never reaches the event log or
an error text (D7; attack A9 of FABLE_INJECTION_ATTACKS.md as a test)."""
import copy
import sys
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
        assert os.fstat(fd).st_ino == path.stat().st_ino        # the descriptor of the log file itself
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


def test_a_key_that_json_would_escape_is_still_hidden(tmp_path):
    odd = 'sk-odd"key\\with-escapes-123'
    redact.register(odd)
    log = EventLog(tmp_path / "e.jsonl")
    log.emit("llm_call", error=f"echo {odd} end", nested={odd: [odd]})
    raw = (tmp_path / "e.jsonl").read_text(encoding="utf-8")
    assert odd not in raw and json.dumps(odd)[1:-1] not in raw         # neither as written nor as json escapes it
    rec = json.loads(raw)
    assert rec["error"] == f"echo {redact.MARK} end" and rec["nested"] == {redact.MARK: [redact.MARK]}


def test_a_registered_value_equal_to_json_syntax_or_a_field_name_cannot_damage_a_record(tmp_path):
    for weak in ("worker_id", "llm_call_started", '"event": '):
        redact.register(weak)
    log = EventLog(tmp_path / "e.jsonl")
    log.emit("llm_call_started", worker_id=7, call_id="c1")
    (rec,) = [json.loads(l) for l in (tmp_path / "e.jsonl").read_text(encoding="utf-8").splitlines()]
    assert rec["worker_id"] == 7 and rec["call_id"] == "c1" and set(rec) == {"ts", "event", "worker_id", "call_id"}
    assert rec["event"] == "llm_call_started"     # the event name is the harness's own: reconcile_ledger reads it


def test_scrub_value_walks_dicts_lists_and_tuples_and_leaves_other_types():
    redact.register(CANARY)
    out = redact.scrub_value({"a": (CANARY, 1, None, 2.5, True), f"k{CANARY}": {"b": [CANARY]}})
    assert out == {"a": [redact.MARK, 1, None, 2.5, True], f"k{redact.MARK}": {"b": [redact.MARK]}}


def test_a_key_registered_with_surrounding_whitespace_is_hidden_without_it():
    redact.register("  sk-whitespace-key-123456  \n")
    assert redact.scrub("x sk-whitespace-key-123456 y") == f"x {redact.MARK} y"


def test_the_marker_is_a_visible_fixed_word():
    assert redact.MARK == "[redacted]"
    redact.register(CANARY)
    assert redact.scrub(CANARY) == "[redacted]"


def test_clear_forgets_every_value():
    redact.register(CANARY)
    redact.clear()
    assert redact.scrub(f"still {CANARY}") == f"still {CANARY}"


# ---- after Fable's reading: the writers, the cut, the encodings, the terminal ---------------------------------------------------------

import base64  # noqa: E402
import io  # noqa: E402
import traceback  # noqa: E402
import urllib.parse  # noqa: E402

KEY2 = "sk-live/key+with=chars-1234567890"


def test_the_base64_and_url_encoded_forms_of_a_key_are_hidden_too():
    redact.register(KEY2)
    b64 = base64.b64encode(KEY2.encode()).decode()
    quoted = urllib.parse.quote(KEY2, safe="")
    assert b64 != KEY2 and quoted != KEY2
    out = redact.scrub(f"Authorization: Basic {b64}; url=?k={quoted}; raw={KEY2}")
    assert b64 not in out and quoted not in out and KEY2 not in out and out.count(redact.MARK) == 3


def test_an_error_text_is_scrubbed_before_it_is_cut_so_no_prefix_of_a_key_is_left(tmp_path):
    redact.register(CANARY)
    c, log = caller(tmp_path, [FakeHTTPError(401, "x" * 195 + CANARY)])           # the key straddles the 200 character cut
    with pytest.raises(LLMCallFailed):
        c.call([HumanMessage("hi")], Reservation(tokens=100_000, usd=1.0))
    raw = log.read_text(encoding="utf-8")
    assert "sk-CA" not in raw and "sk-C" not in raw and "xxxx" in raw


def test_a_job_file_never_holds_a_registered_key(tmp_path):
    from router import job as rj
    redact.register(CANARY)
    d = tmp_path / "j1"
    d.mkdir()
    job = rj.Job(d)
    job.data = {"job": "j1", "state": "AGENT_FAILED", "stages": {"a1": {"reason": f"provider said {CANARY}"}}, "log": [{"what": "x", "note": CANARY}]}
    job.save()
    text = (d / "job.json").read_text(encoding="utf-8")
    assert CANARY not in text and text.count(redact.MARK) == 2
    assert job.data["stages"]["a1"]["reason"].endswith(CANARY)           # memory is untouched: only what reaches the disk is cleaned


def test_a_result_file_never_holds_a_registered_key(tmp_path):
    import json
    from codetask.run import run_code_task
    redact.register(CANARY)
    cfg = load_config()
    cfg["roles"]["coder"]["model"] = "fake:scripted"
    bad = tmp_path / f"{CANARY}.json"                                      # no such contract: the reason names the path
    r = run_code_task(contract_path=bad, run_id="t", runs_dir=tmp_path / "runs", cfg=cfg, models={"coder": ScriptedChatModel(script=[])},
                      validate=lambda *a, **k: None, preflight=lambda: (True, "ok"))
    assert r["status"] == "BLOCKED" and "invalid contract" in r["stop_reason"]
    assert CANARY not in (tmp_path / "runs" / "t" / "result.json").read_text(encoding="utf-8")


def test_the_terminal_filter_hides_a_key_in_a_printed_traceback_of_a_chained_exception(capsys):
    redact.register(CANARY)
    redact.install()
    try:
        try:
            try:
                raise RuntimeError(f"provider echoed {CANARY}")
            except RuntimeError as e:
                raise LLMCallFailed("worker: failed") from e
        except LLMCallFailed:
            traceback.print_exc()
        print(f"error: {CANARY}")
        sys.stderr.write(f"warn: {CANARY}\n")
    finally:
        redact.uninstall()
    cap = capsys.readouterr()
    assert CANARY not in cap.out and CANARY not in cap.err
    assert "provider echoed [redacted]" in cap.err and "error: [redacted]" in cap.out and "warn: [redacted]" in cap.err


def test_the_filter_is_installed_once_removed_cleanly_and_passes_other_attributes(capsys):
    stream = sys.stdout
    redact.install()
    redact.install()
    assert isinstance(sys.stdout, redact._Scrubbing) and not isinstance(sys.stdout._stream, redact._Scrubbing)
    assert sys.stdout.encoding == stream.encoding            # other attributes pass through
    sys.stdout.writelines(["a\n", "b\n"])
    redact.uninstall()
    assert sys.stdout is stream and capsys.readouterr().out == "a\nb\n"


def test_a_key_typed_for_a_live_stage_is_registered_from_then_on(tmp_path, monkeypatch):
    import test_router as tr
    from codetask import drafter as cdr
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    e = tr.Env(tmp_path, config=tr.real_cfg())
    e.deps.get_key = lambda: "sk-ant-test-0000-typed"
    monkeypatch.setattr(cdr, "run_drafter", tr.fake_draft_run([]))
    e.code()
    assert redact.scrub("x sk-ant-test-0000-typed y") == f"x {redact.MARK} y"


def test_a_failed_token_count_is_scrubbed_before_its_cut_too(tmp_path):
    redact.register(CANARY)
    cfg = copy.deepcopy(load_config())
    cfg["llm"].update({"base_delay": 0})
    log = EventLog(tmp_path / "e.jsonl")

    def counting_fails(messages, tools):
        raise FakeHTTPError(401, "y" * 195 + CANARY)
    c = LLMCaller(cfg, "worker", log, model=ScriptedChatModel(script=[reply()]), counter=counting_fails, sleep=lambda s: None)
    with pytest.raises(LLMCallFailed) as e:
        c.call([HumanMessage("hi")], Reservation(tokens=100_000, usd=1.0))
    raw = (tmp_path / "e.jsonl").read_text(encoding="utf-8")
    assert CANARY not in raw and "sk-CA" not in raw and CANARY not in str(e.value) and "yyyy" in raw


def test_the_terminal_filter_reports_the_length_it_was_given_even_when_a_key_was_replaced():
    redact.register(CANARY)
    sink = io.StringIO()
    stream = redact._Scrubbing(sink)
    text = f"error: {CANARY}\n"
    assert stream.write(text) == len(text) and sink.getvalue() == "error: [redacted]\n"


def test_a_key_registered_later_is_found_by_the_cached_order_and_clear_empties_it():
    redact.register("sk-short-key-aaa")
    redact.register("sk-short-key-aaa-and-longer")
    assert redact.scrub("sk-short-key-aaa-and-longer|sk-short-key-aaa") == f"{redact.MARK}|{redact.MARK}"
    redact.clear()
    assert redact.scrub("sk-short-key-aaa") == "sk-short-key-aaa" and redact._ordered == ()
