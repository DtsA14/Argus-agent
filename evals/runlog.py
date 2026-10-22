"""The one reader of a code-task run directory: its events, its result and its memo."""
import json
import sqlite3
from pathlib import Path

from harness.events import parse_lines


def read_events(run_dir):
    """(events, skipped): the records of events.jsonl that decode, and the number of non-blank lines that did not."""
    path = Path(run_dir) / "events.jsonl"
    if not path.exists():
        return [], 0
    text = path.read_text(encoding="utf-8")
    events = parse_lines(text)
    nonblank = sum(1 for line in text.splitlines() if line.strip())
    return events, nonblank - len(events)


def read_result(run_dir):
    """result.json as a dict, or None when the run has none."""
    path = Path(run_dir) / "result.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def read_memo(run_dir):
    """{key: value} of memo.sqlite, both decoded from JSON."""
    path = Path(run_dir) / "memo.sqlite"
    if not path.exists():
        return {}
    db = sqlite3.connect(path)
    try:
        return {k: json.loads(v) for k, v in db.execute("select key, value from memo")}
    finally:
        db.close()


def skipped_line(skipped):
    """'events skipped: N', or None when N is 0."""
    return f"events skipped: {skipped}" if skipped else None
