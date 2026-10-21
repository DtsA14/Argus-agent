"""The one reader of a code-task run directory (M6 pilot 3): the files a run leaves behind, read the same way by every tool
that looks at a run (scripts/audit_run.py, scripts/failure_trace.py, scripts/pilot_report.py).

events.jsonl is read like everywhere else (harness.events.parse_lines): a line that is not valid JSON is skipped wherever it
is, and the number of such lines is returned so a tool can say it. A run that crashed, or that never got a result.json, is read
as far as it goes; nothing here guesses a value the files do not hold."""
import json
import sqlite3
from pathlib import Path

from harness.events import parse_lines


def read_events(run_dir):
    """(events, skipped): every record of <run_dir>/events.jsonl that decodes, and how many non-blank lines did not."""
    path = Path(run_dir) / "events.jsonl"
    text = path.read_text(encoding="utf-8") if path.exists() else ""
    events = parse_lines(text)
    return events, sum(1 for line in text.splitlines() if line.strip()) - len(events)


def read_result(run_dir):
    """<run_dir>/result.json as a dict, or None when the run has none (it was never finished)."""
    path = Path(run_dir) / "result.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def read_memo(run_dir):
    """{key: value} of <run_dir>/memo.sqlite, both decoded from JSON."""
    db = sqlite3.connect(Path(run_dir) / "memo.sqlite")
    return {k: json.loads(v) for k, v in db.execute("select key, value from memo")}


def skipped_line(skipped):
    """The line a tool prints last when it had to skip lines of the event log; nothing when none were skipped."""
    return f"events skipped: {skipped}" if skipped else None
