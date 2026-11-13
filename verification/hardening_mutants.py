"""Mutants for the hardening after Fable's reading (acceptance/conflict.py checks, acceptance/testdetect.py patterns, harness/redact.py and its writers):
each applied alone in a worktree; killed = a test failed (an error or a skip is not a kill). Usage: hardening_mutants.py <worktree> <python>"""
import subprocess
import sys
from pathlib import Path

WT, PY = Path(sys.argv[1]), sys.argv[2]
C, D, R, J, L, S = "acceptance/conflict.py", "acceptance/testdetect.py", "harness/redact.py", "router/job.py", "harness/llm.py", "codetask/run.py"
TESTS = ["tests/test_fix_c.py", "tests/test_report_conflict.py", "tests/test_test_detection.py", "tests/test_detection_terminal.py"]
M = [
    # conflict.py
    ("support: not checked", C, "    for p in sorted(p for p in changed if support_file(p))[:3]:", "    for p in []:"),
    ("support: test files not counted", C, "    return is_test_file(path) or path.rsplit", "    return False or path.rsplit"),
    ("support: names not counted", C, 'or path.rsplit("/", 1)[-1] in SUPPORT_NAMES', "or False"),
    ("support: conftest not a support name", C, 'SUPPORT_NAMES = {"conftest.py", ', "SUPPORT_NAMES = {"),
    ("support: pytest.ini not a support name", C, '"pytest.ini", ', ""),
    ("support: package.json not a support name", C, '".coveragerc", "package.json",', '".coveragerc",'),
    ("support: vitest config not a support name", C, '"vitest.config.js", "vitest.config.ts", "vitest.config.mjs", ', ""),
    ("required: none needed", C, "    if not required_ok:", "    if False:"),
    ("required: a failing test counts", C, '            if s == "ok":\n                required_ok += 1', '            if s is not None:\n                required_ok += 1'),
    # testdetect.py
    ("O2: any _exit method", D, r'r"\bos\._exit\s*\(|\bfrom\s+os\s+import\b[^#\n]*\b_exit\b"', r'r"\b_exit\s*\("'),
    ("O2: the import of _exit not flagged", D, r'|\bfrom\s+os\s+import\b[^#\n]*\b_exit\b"', '"'),
    ("O2: os.exec not flagged", D, r'"os.exec": (re.compile(r"\bos\.exec(?:l|le|lp|lpe|v|ve|vp|vpe)\s*\("),),', r'"os.exec": (re.compile(r"NEVER_MATCHES"),),'),
    ("O2: process.exit not flagged", D, r'"process.exit": (re.compile(r"\bprocess\.(?:exit|abort|kill)\s*\("),),', r'"process.exit": (re.compile(r"NEVER_MATCHES"),),'),
    ("O2: only process.exit", D, r"process\.(?:exit|abort|kill)", r"process\.exit"),
    ("O2: fs.writeSync not flagged", D, r'"fs.writeSync stdout/stderr": (re.compile(r"\bfs\.writeSync\(\s*[12]\s*,"),),', r'"fs.writeSync stdout/stderr": (re.compile(r"NEVER_MATCHES"),),'),
    ("O2: comments count for forgers", D, "            if comment and name in FORGERS:\n                continue\n", ""),
    ("O2: comments are not read for anything", D, "            if comment and name in FORGERS:", "            if comment:"),
    ("O2: a commented line is flagged as forging", D, "    return not line.lstrip().startswith(COMMENT) and any(", "    return any("),
    ("O2: a leading * counts as a comment", D, 'COMMENT = ("#", "//")', 'COMMENT = ("#", "//", "*")'),
    ("O2: a leading /* counts as a comment", D, 'COMMENT = ("#", "//")', 'COMMENT = ("#", "//", "/*")'),
    ("O2: // is not a comment", D, 'COMMENT = ("#", "//")', 'COMMENT = ("#",)'),
    # redact.py and the writers
    ("redact: no base64 form", R, 'forms = {key, base64.b64encode(key.encode("utf-8")).decode("ascii"), urllib.parse.quote(key, safe="")}',
     'forms = {key, urllib.parse.quote(key, safe="")}'),
    ("redact: no url form", R, 'forms = {key, base64.b64encode(key.encode("utf-8")).decode("ascii"), urllib.parse.quote(key, safe="")}',
     'forms = {key, base64.b64encode(key.encode("utf-8")).decode("ascii")}'),
    ("redact: short forms registered", R, "_secrets.update(f for f in forms if len(f) >= MIN_LEN)", "_secrets.update(forms)"),
    ("stream: write reports the scrubbed length", R, "        return len(text)                  # what the caller handed over", "        return len(scrub(text))                  # what the caller handed over"),
    ("redact: the cached order is not rebuilt", R, "            _ordered = tuple(sorted(_secrets, key=len, reverse=True))", "            pass"),
    ("redact: the cached order is shortest first", R, "_ordered = tuple(sorted(_secrets, key=len, reverse=True))", "_ordered = tuple(sorted(_secrets, key=len))"),
    ("redact: clear keeps the cached order", R, "        _secrets.clear()\n        _ordered = ()", "        _secrets.clear()"),
    ("conflict: a missing record reads as a failure", C, "            if base.get(n) is None:", "            if False:"),
    ("stream: nothing scrubbed", R, "        self._stream.write(scrub(text))\n        return len(text)", "        self._stream.write(text)\n        return len(text)"),
    ("stream: install does nothing", R, "            setattr(sys, name, _Scrubbing(stream))", "            pass"),
    ("stream: uninstall does nothing", R, "            setattr(sys, name, stream._stream)", "            pass"),
    ("stream: install wraps twice", R, "        if not isinstance(stream, _Scrubbing):\n            setattr(sys, name, _Scrubbing(stream))", "        setattr(sys, name, _Scrubbing(stream))"),
    ("stream: attributes are not passed on", R, "        return getattr(self._stream, name)", "        raise AttributeError(name)"),
    ("job file: not scrubbed", J, "json.dumps(scrub_value(self.data), indent=2", "json.dumps(self.data, indent=2"),
    ("result file: not scrubbed", S, "json.dumps(scrub_value(result), ensure_ascii=False, indent=2)", "json.dumps(result, ensure_ascii=False, indent=2)"),
    ("llm: a failed count is cut before the scrub", L,
     'http_status=http_status(exc),\n                     error=f"{type(exc).__name__}: {scrub(str(exc))[:200]}")', 'http_status=http_status(exc),\n                     error=f"{type(exc).__name__}: {str(exc)[:200]}")'),
    ("llm: a failed call is cut before the scrub", L, 'latency_s=latency, error=f"{type(exc).__name__}: {scrub(str(exc))[:200]}")',
     'latency_s=latency, error=f"{type(exc).__name__}: {str(exc)[:200]}")'),
    ("live: a typed key is not registered", J, "            redact.register(key)              # from here on", "            pass              # from here on"),
]

if __name__ == "__main__":
    killed = 0
    for name, f, old, new in M:
        p = WT / f
        orig = p.read_text()
        assert orig.count(old) == 1, (name, orig.count(old))
        p.write_text(orig.replace(old, new, 1))
        r = subprocess.run([PY, "-m", "pytest", "-x", "-q", "-p", "no:cacheprovider", *TESTS], cwd=WT, capture_output=True, text=True)
        p.write_text(orig)
        last = (r.stdout.strip().splitlines() or [""])[-1]
        k = "failed" in last
        killed += k
        fails = [line for line in r.stdout.splitlines() if line.startswith("FAILED")][:1]
        print(f"{'KILLED ' if k else 'SURVIVED'} {name}: {fails or last}", flush=True)
    print(f"RESULT: {killed}/{len(M)} killed")
