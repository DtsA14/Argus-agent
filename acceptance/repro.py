"""The issue's own example, run at the base commit, shown before approve (SPEC_REPRO_V0 R1).

An issue that is already fixed at the base gives the drafter nothing to reproduce; it drafts something else, and the draft can
look fine. This runs the Python code blocks of the issue in the sandbox on a copy of the base tree and shows what they do, so
a human sees `ran clean, last output "0o600"` next to an issue that says 0o644. Display only: it never refuses, never changes a
draft, and any error (sandbox down, odd issue text) gives no result. A clean run does not prove the bug is gone, and a crash
does not prove it is there: the human reads the output against the issue.
"""
import hashlib
import json
import re
import shutil
import tempfile
import textwrap
from pathlib import Path

MAX_BLOCKS = 3
MAX_CODE_BYTES = 4000
MAX_OUT = 2000
OUT_SHOWN = 60       # characters of the last output line shown on the approve line
TIMEOUT_S = 20
PRELUDE = "import sys; sys.path.insert(0, '/workspace')\n"      # the sandbox runs python -I: the project is not importable otherwise
# the info string may carry more than the language (```python title=x, ```{.python}, ```python {1,2})
FENCE = re.compile(r"^[ \t]*(`{3,}|~{3,})[ \t]*\{?\.?(python3?|py)(?=[ \t}]|$)[^\n]*\n(.*?)^[ \t]*\1[ \t]*$", re.M | re.S | re.I)
KEEP = ("index", "status", "exit_code", "stdout", "stderr_last_line", "reason")


def blocks(issue):
    """[(index, code)] of the issue's python fences, in order, at most MAX_BLOCKS."""
    if not isinstance(issue, str):
        return []
    return [(i, textwrap.dedent(m.group(3))) for i, m in enumerate(FENCE.finditer(issue))][:MAX_BLOCKS]


def skip_reason(code):
    if len(code.encode("utf-8")) > MAX_CODE_BYTES:
        return f"longer than {MAX_CODE_BYTES} bytes"
    lines = [ln for ln in code.splitlines() if ln.strip()]
    if not lines:
        return "empty"
    if any(ln.lstrip().startswith(">>>") for ln in lines):
        return "an interactive session (>>>), not a script"
    if any(ln.strip() == "..." for ln in lines):
        return "contains a bare ... line, not a script"
    if any(ln.startswith("$ ") for ln in lines):
        return "a shell session, not a script"
    return None


def program(code):
    """The code with the prelude in front; `from __future__` lines must come first in a file, so they go before it."""
    lines = code.splitlines(keepends=True)
    future = [ln for ln in lines if re.match(r"\s*from\s+__future__\s+import\b", ln)]
    rest = [ln for ln in lines if ln not in future]
    return "".join(ln.lstrip() for ln in future) + PRELUDE + "".join(rest)


def key(issue, snapshot_sha256):
    """What a stored result is bound to: this issue text at this base."""
    return hashlib.sha256(f"{snapshot_sha256}\n{issue}".encode("utf-8")).hexdigest()


# C0/C1 controls (a newline and a tab stay), and the Unicode marks that reorder or hide text (bidi, zero width, line and
# paragraph separators): none of them is shown to the human
CONTROL = re.compile("[\x00-\x08\x0b-\x1f\x7f-\x9f\u061c\u200b-\u200f\u2028-\u202e\u2060-\u2069\ufeff\u00ad\u180e\u2800\U000e0000-\U000e007f]")


def _cut(text, limit):
    """At most `limit` bytes of utf-8, never half a character, and no control character: the code is the issue
    author's, and what it prints reaches the human's terminal on the approve screen (an escape sequence could hide or
    redraw the lines next to it). A newline and a tab stay."""
    return CONTROL.sub("?", (text or "")).encode("utf-8")[:limit].decode("utf-8", "ignore")


def _last_line(text):
    lines = [ln for ln in (text or "").strip().splitlines() if ln.strip()]
    return _cut(lines[-1], 300) if lines else ""


def _result(index, code, r):
    if r.get("timed_out"):
        return {"index": index, "status": "timeout", "exit_code": None, "stdout": _cut(r.get("stdout"), MAX_OUT),
                "stderr_last_line": "", "reason": f"no end within {TIMEOUT_S} s"}
    ok = r.get("exit_code") == 0
    return {"index": index, "status": "ok" if ok else "raised", "exit_code": r.get("exit_code"),
            "stdout": _cut(r.get("stdout"), MAX_OUT), "stderr_last_line": "" if ok else _last_line(r.get("stderr")),
            "reason": ""}


def run(base_dir, issue, sandbox_cfg, runner=None):
    """[result] for the issue's runnable blocks; [] when it has none; None (not run) when anything goes wrong. Runs on a
    copy of base_dir (the intake is never written to)."""
    try:
        found = blocks(issue)
        if not found:
            return []
        if runner is None:
            from tools import sandbox
            runner = sandbox.run_python
        cfg = {**(sandbox_cfg or {}), "timeout_s": TIMEOUT_S}
        out = []
        with tempfile.TemporaryDirectory() as tmp:
            for index, code in found:
                why = skip_reason(code)
                if why:
                    out.append({"index": index, "status": "skipped", "exit_code": None, "stdout": "",
                                "stderr_last_line": "", "reason": why})
                    continue
                work, data = Path(tmp) / f"w{index}", Path(tmp) / f"d{index}"
                data.mkdir()
                shutil.copytree(base_dir, work, symlinks=True)
                out.append(_result(index, code, runner(program(code), workdir=work, data_dir=data, cfg=cfg)))
        return out
    except Exception:  # advisory: no result, never an error into the job
        return None


def store(path, issue, snapshot_sha256, results):
    try:
        Path(path).write_text(json.dumps({"key": key(issue, snapshot_sha256), "results": results}), encoding="utf-8")
    except Exception:
        pass


def load(path, issue, snapshot_sha256):
    """The stored results when they belong to this issue at this base; None when it could not run (or the file is bad);
    False when the result is for another issue or base."""
    try:
        rec = json.loads(Path(path).read_text(encoding="utf-8"))
        if rec.get("key") != key(issue, snapshot_sha256):
            return False                                        # a result for another issue or base: stale
        if not isinstance(rec.get("results"), list):            # None: it could not run
            return None
        clean = ("stdout", "stderr_last_line", "reason")        # the file can be edited: shown text is cleaned again
        return [{k: (_cut(r.get(k), MAX_OUT) if k in clean else r.get(k)) for k in KEEP}
                for r in rec["results"] if isinstance(r, dict)]
    except Exception:
        return None


def line(results):
    """The one line for the approve screen and status; None when nothing was run (the caller says so)."""
    if results is False:
        return "issue example at base: not run (the issue or the base changed since it was run)"
    if results is None:
        return "issue example at base: not run"
    if not results:
        return "issue example at base: no runnable example in the issue"
    ran = [r for r in results if r.get("status") in ("ok", "raised", "timeout")]
    if not ran:
        return "issue example at base: not run (" + "; ".join(str(r.get("reason")) for r in results) + ")"
    parts = []
    for r in ran:
        if r["status"] == "ok":
            last = _last_line(r.get("stdout"))[:OUT_SHOWN]
            parts.append(f'ran clean, last output "{last}"' if last else "ran clean")
        elif r["status"] == "raised":
            parts.append("raised " + (r.get("stderr_last_line") or "an error")[:80])
        else:
            parts.append("timed out")
    return ("issue example at base: " + ", ".join(parts)
            + (": a clean run does not prove the bug is gone, read repro.json against the issue"
               if any(r["status"] == "ok" for r in ran) else ""))
