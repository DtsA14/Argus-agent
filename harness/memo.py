"""Durable per-node result memo.

Why: a node can finish its work and then lose its result if the process dies before LangGraph
persists it (seen with parallel workers: a sibling crashes before the finished worker's write
lands). LangGraph then re-runs the node on resume. Against a hard crash, "exactly once" is not
achievable; the guarantee is "at least once", so re-runs must be cheap and side-effect free.

The guard commits each node's output here *before* reporting it as finished. On resume, a node
whose output is already committed returns it from the memo instead of doing the work again.
The only remaining window is between the work returning and this commit (milliseconds).
"""
import json
import sqlite3
import threading


class Memo:
    def __init__(self, path):
        self.path = str(path)
        self._lock = threading.Lock()
        with self._connect() as db:
            db.execute("CREATE TABLE IF NOT EXISTS memo (key TEXT PRIMARY KEY, value TEXT NOT NULL)")

    def _connect(self):
        db = sqlite3.connect(self.path, timeout=30)
        db.execute("PRAGMA synchronous=FULL")
        return db

    def get(self, key):
        with self._lock:
            db = self._connect()
            try:
                row = db.execute("SELECT value FROM memo WHERE key = ?", (key,)).fetchone()
            finally:
                db.close()
        return json.loads(row[0]) if row else None

    def put(self, key, value):
        """Commit durably. Returns only after the row is on disk."""
        payload = json.dumps(value, ensure_ascii=False, sort_keys=True)
        with self._lock:
            db = self._connect()
            try:
                with db:  # transaction: commit on success
                    db.execute("INSERT OR REPLACE INTO memo (key, value) VALUES (?, ?)", (key, payload))
            finally:
                db.close()


def node_key(name, state):
    """One key per logical node run: (node, task, iteration). Each iteration runs each node once."""
    task = state.get("task", {}).get("id") if isinstance(state.get("task"), dict) else None
    return json.dumps([name, task, state.get("iteration", 0)])
