"""Mutants for FIX-C (harness/events.py, harness/redact.py, harness/errors.py, models/registry.py): each applied alone in a worktree,
tests/test_fix_c.py run with -x; killed = a test failed (an error or a skip is not a kill). Usage: fix_c_mutants.py <worktree> <python>"""
import subprocess
import sys
from pathlib import Path

WT, PY = Path(sys.argv[1]), sys.argv[2]
E, R, X, G = "harness/events.py", "harness/redact.py", "harness/errors.py", "models/registry.py"
T = "tests/test_fix_c.py"
M = [
    ("D2: no fsync", E, "                os.fsync(f.fileno())\n", "", [T]),
    ("D2: no flush before fsync", E, "                f.flush()\n", "", [T]),
    ("D2: fsync before the write", E, "                f.write(line)\n                f.flush()\n                os.fsync(f.fileno())\n",
     "                os.fsync(f.fileno())\n                f.write(line)\n                f.flush()\n", [T]),
    ("D2: fsync error swallowed", E, "                os.fsync(f.fileno())\n",
     "                try:\n                    os.fsync(f.fileno())\n                except OSError:\n                    pass\n", [T]),
    ("D2: fsync outside the lock", E, "        with self._lock:\n            with open(self.path, \"a\", encoding=\"utf-8\") as f:\n                f.write(line)\n                f.flush()\n                os.fsync(f.fileno())\n",
     "        with self._lock:\n            with open(self.path, \"a\", encoding=\"utf-8\") as f:\n                f.write(line)\n                f.flush()\n        os.fsync(os.open(self.path, os.O_RDONLY))\n", [T]),
    ("D7: events not scrubbed", E, "**{k: scrub_value(v) for k, v in fields.items()}}", "**fields}", [T]),
    ("D7: only strings at the top level", E, "scrub_value(v) for k, v in fields.items()", "scrub(v) for k, v in fields.items()", [T]),
    ("D7: echo not scrubbed", E, "print(scrub(f\"[{event}] {detail}\"), flush=True)", "print(f\"[{event}] {detail}\", flush=True)", [T]),
    ("D7: field names scrubbed", E, "**{k: scrub_value(v) for k, v in fields.items()}}", "**scrub_value(fields)}", [T]),
    ("D7: the event name scrubbed", E, '"event": event,', '"event": scrub(event),', [T]),
    ("D7: the line scrubbed instead of the values", E, 'line = json.dumps(rec, ensure_ascii=False) + "\\n"',
     'line = scrub(json.dumps(rec, ensure_ascii=False)) + "\\n"', [T]),
    ("D7: LLMCallFailed message not scrubbed", X, "super().__init__(scrub(message), *args)", "super().__init__(message, *args)", [T]),
    ("D7: registry does not register", G, "    redact.register(key)", "    pass", [T]),
    ("D7: register ignores the length floor", R, "len(secret.strip()) >= MIN_LEN", "len(secret.strip()) >= 1", [T]),
    ("D7: register accepts non-strings", R, "if isinstance(secret, str) and len(secret.strip()) >= MIN_LEN:", "if len(str(secret).strip()) >= MIN_LEN:", [T]),
    ("D7: register keeps the whitespace", R, "_secrets.add(secret.strip())", "_secrets.add(secret)", [T]),
    ("D7: MIN_LEN too small", R, "MIN_LEN = 8", "MIN_LEN = 4", [T]),
    ("D7: shortest first", R, "sorted(_secrets, key=len, reverse=True)", "sorted(_secrets, key=len)", [T]),
    ("D7: only the first occurrence", R, "text = text.replace(s, MARK)", "text = text.replace(s, MARK, 1)", [T]),
    ("D7: no marker", R, 'MARK = "[redacted]"', 'MARK = ""', [T]),
    ("D7: a non-string is turned into one", R, "if not isinstance(text, str) or not text:\n        return text", "if not text:\n        return text", [T]),
    ("D7: dict keys not scrubbed", R, "{scrub_value(k): scrub_value(v) for k, v in obj.items()}", "{k: scrub_value(v) for k, v in obj.items()}", [T]),
    ("D7: tuples not walked", R, "if isinstance(obj, (list, tuple)):", "if isinstance(obj, list):", [T]),
    ("D7: lists not walked", R, "if isinstance(obj, (list, tuple)):", "if isinstance(obj, tuple):", [T]),
    ("D7: dict values not walked", R, "{scrub_value(k): scrub_value(v) for k, v in obj.items()}", "{scrub_value(k): v for k, v in obj.items()}", [T]),
    ("D7: nothing scrubbed", R, "    for s in secrets:\n        if s in text:\n            text = text.replace(s, MARK)\n", "", [T]),
    ("D7: clear does not clear", R, "        _secrets.clear()", "        pass", [T]),
]

if __name__ == "__main__":
    killed = 0
    for name, f, old, new, tests in M:
        p = WT / f
        orig = p.read_text()
        assert orig.count(old) == 1, (name, orig.count(old))
        p.write_text(orig.replace(old, new, 1))
        r = subprocess.run([PY, "-m", "pytest", "-x", "-q", "-p", "no:cacheprovider", *tests], cwd=WT,
                           capture_output=True, text=True)
        p.write_text(orig)
        last = (r.stdout.strip().splitlines() or [""])[-1]
        k = "failed" in last
        killed += k
        fails = [line for line in r.stdout.splitlines() if line.startswith("FAILED")][:1]
        print(f"{'KILLED ' if k else 'SURVIVED'} {name}: {fails or last}", flush=True)
    print(f"RESULT: {killed}/{len(M)} killed")
