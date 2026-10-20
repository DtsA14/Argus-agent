"""run_stats reads a run's events.jsonl the way the harness does (harness.events.parse_lines): a line that is not
valid JSON is skipped wherever it is (a run killed while writing an event and then resumed leaves one in the middle),
and every other line is counted exactly as before."""
import json

from evals.score import run_stats

RESULT = {"attempts": 2, "llm_calls": 3, "tools": ["edit_file"], "usd_billed": 0.123, "usd_complete": True}
EVENTS = [
    {"ts": 1.0, "event": "llm_call_started", "call_id": "a"},
    {"ts": 2.0, "event": "llm_call", "call_id": "a", "status": "ok", "tokens": 100},
    {"ts": 3.0, "event": "llm_call", "call_id": "b", "status": "transient_error", "tokens": 40},
    {"ts": 4.0, "event": "reply_truncated"},
    {"ts": 5.0, "event": "resume"},
    {"ts": 6.0, "event": "llm_call", "call_id": "c", "status": "ok", "tokens": 60},
]
CUT = '{"ts": 2.5, "event": "llm_call", "cal'          # what a process killed mid-write leaves behind


def make_run(tmp_path, name, text):
    run = tmp_path / name
    run.mkdir()
    (run / "result.json").write_text(json.dumps(RESULT), encoding="utf-8")
    (run / "events.jsonl").write_text(text, encoding="utf-8")
    return run


def lines(events):
    return [json.dumps(e) for e in events]


def clean_text():
    return "".join(line + "\n" for line in lines(EVENTS))


def test_a_log_without_damage_is_counted_as_before(tmp_path):
    stats = run_stats(make_run(tmp_path, "clean", clean_text()))
    assert stats["tokens"] == 200 and stats["transient_errors"] == 1
    assert stats["reply_truncated"] == 1 and stats["resume"] == 1 and stats["invalid_tool_call"] == 0
    assert stats["attempts"] == 2 and stats["llm_calls"] == 3 and stats["usd_billed"] == 0.123


def test_a_line_cut_short_in_the_middle_is_skipped(tmp_path):
    damaged = lines(EVENTS[:2]) + [CUT] + lines(EVENTS[2:])
    stats = run_stats(make_run(tmp_path, "damaged", "".join(line + "\n" for line in damaged)))
    assert stats == run_stats(make_run(tmp_path, "clean", clean_text()))
    assert stats["tokens"] == 200 and stats["transient_errors"] == 1 and stats["resume"] == 1


def test_a_last_line_cut_short_without_a_newline_is_skipped(tmp_path):
    stats = run_stats(make_run(tmp_path, "tail", clean_text() + CUT))
    assert stats == run_stats(make_run(tmp_path, "clean", clean_text()))
    assert stats["tokens"] == 200


def test_every_line_that_is_not_json_is_skipped_and_blank_lines_too(tmp_path):
    text = "garbage\n" + CUT + "\n\n" + clean_text() + "\nnot json {\n"
    stats = run_stats(make_run(tmp_path, "noisy", text))
    assert stats == run_stats(make_run(tmp_path, "clean", clean_text()))
    assert stats["tokens"] == 200 and stats["reply_truncated"] == 1
