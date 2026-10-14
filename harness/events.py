import json
import threading
import time
from pathlib import Path


class EventLog:
    """Append-only JSONL event log; thread-safe because workers run in parallel."""

    def __init__(self, path, echo=False):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.echo = echo
        self._lock = threading.Lock()

    def emit(self, event, **fields):
        rec = {"ts": round(time.time(), 3), "event": event, **fields}
        with self._lock:
            with open(self.path, "a", encoding="utf-8") as f:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            if self.echo:
                detail = " ".join(f"{k}={v}" for k, v in fields.items())
                print(f"[{event}] {detail}", flush=True)
