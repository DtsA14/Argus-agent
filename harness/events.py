import json
import threading
import time
from pathlib import Path


def parse_lines(text):
    """Parse JSONL, skipping a line cut short by a crash mid-write (it can only be a partial record)."""
    out = []
    for line in text.splitlines():
        if not line.strip():
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out


class TaggedLog:
    """A view of a log that adds fixed fields (tags) to every event it emits, e.g. origin="auto" on the sandbox runs
    of one caller. Reads go to the underlying log."""

    def __init__(self, log, **tags):
        self.log, self.tags = log, tags

    def emit(self, event, **fields):
        self.log.emit(event, **fields, **self.tags)

    def read(self):
        return self.log.read()


class EventLog:
    """Append-only JSONL event log; thread-safe because workers run in parallel.

    A process killed mid-write can leave a partial last line. On open, a missing final newline is
    restored, so the next record starts on its own line instead of fusing with the broken one.
    """

    def __init__(self, path, echo=False):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.echo = echo
        self._lock = threading.Lock()
        if self.path.exists() and self.path.stat().st_size:
            with open(self.path, "rb") as f:
                f.seek(-1, 2)
                last = f.read(1)
            if last != b"\n":
                with open(self.path, "a", encoding="utf-8") as f:
                    f.write("\n")

    def emit(self, event, **fields):
        rec = {"ts": round(time.time(), 3), "event": event, **fields}
        with self._lock:
            with open(self.path, "a", encoding="utf-8") as f:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            if self.echo:
                detail = " ".join(f"{k}={v}" for k, v in fields.items())
                print(f"[{event}] {detail}", flush=True)

    def read(self):
        """All complete records so far (consistent with concurrent writers in this process)."""
        with self._lock:
            if not self.path.exists():
                return []
            return parse_lines(self.path.read_text(encoding="utf-8"))
