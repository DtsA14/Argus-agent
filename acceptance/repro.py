"""The issue's own example, run at the base commit, shown before approve (SPEC_REPRO_V0 R1).

An issue that is already fixed at the base gives the drafter nothing to reproduce; it drafts something else, and the draft can
look fine. This runs the Python code blocks of the issue in the sandbox on a copy of the base tree and shows what they do, so
a human sees "ran clean, printed 0o600" next to an issue that says 0o644. Display only: it never refuses, never changes a
draft, and any error (sandbox down, odd issue text) gives no result. A clean run does not prove the bug is gone, and a crash
does not prove it is there: the human reads the output against the issue.
"""
import hashlib
import json
import re
import shutil
import tempfile
from pathlib import Path

MAX_BLOCKS = 3
MAX_CODE_BYTES = 4000
MAX_OUT = 2000
TIMEOUT_S = 20
PRELUDE = "import sys; sys.path.insert(0, '/workspace')\n"      # the sandbox runs python -I: the project is not importable otherwise
FENCE = re.compile(r"^[ \t]*(`{3,}|~{3,})[ \t]*(python3?|py)[ \t]*\n(.*?)^[ \t]*\1[ \t]*$", re.M | re.S | re.I)
KEEP = ("index", "status", "exit_code", "stdout", "stderr_last_line", "reason")


def blocks(issue):
    """[(index, code)] of the issue's python fences, in order, at most MAX_BLOCKS."""
    if not isinstance(issue, str):
        return []
    return [(i, m.group(3)) for i, m in enumerate(FENCE.finditer(issue))][:MAX_BLOCKS]


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


def key(issue, snapshot_sha256):
    """What a stored result is bound to: this issue text at this base."""
    return hashlib.sha256(f"{snapshot_sha256}\n{issue}".encode("utf-8")).hexdigest()


def _last_line(text):
    lines = [ln for ln in (text or "").strip().splitlines() if ln.strip()]
    return lines[-1][:300] if lines else ""


def _result(index, code, r):
    if r.get("timed_out"):
        return {"index": index, "status": "timeout", "exit_code": None, "stdout": (r.get("stdout") or "")[:MAX_OUT],
                "stderr_last_line": "", "reason": f"no end within {TIMEOUT_S} s"}
    ok = r.get("exit_code") == 0
    return {"index": index, "status": "ok" if ok else "raised", "exit_code": r.get("exit_code"),
            "stdout": (r.get("stdout") or "")[:MAX_OUT], "stderr_last_line": "" if ok else _last_line(r.get("stderr")),
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
                out.append(_result(index, code, runner(PRELUDE + code, workdir=work, data_dir=data, cfg=cfg)))
        return out
    except Exception:  # advisory: no result, never an error into the job
        return None


def store(path, issue, snapshot_sha256, results):
    try:
        Path(path).write_text(json.dumps({"key": key(issue, snapshot_sha256), "results": results}), encoding="utf-8")
    except Exception:
        pass


def load(path, issue, snapshot_sha256):
    """The stored results when they belong to this issue at this base, else None (not run, or changed since)."""
    try:
        rec = json.loads(Path(path).read_text(encoding="utf-8"))
        if rec.get("key") != key(issue, snapshot_sha256) or not isinstance(rec.get("results"), list):  # None: not run
            return None
        return [{k: r.get(k) for k in KEEP} for r in rec["results"] if isinstance(r, dict)]
    except Exception:
        return None


def line(results):
    """The one line for the approve screen and status; None when nothing was run (the caller says so)."""
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
            parts.append("ran clean")
        elif r["status"] == "raised":
            parts.append("raised " + (r.get("stderr_last_line") or "an error")[:80])
        else:
            parts.append("timed out")
    return ("issue example at base: " + ", ".join(parts)
            + (": a clean run does not prove the bug is gone, read repro.json against the issue"
               if any(r["status"] == "ok" for r in ran) else ""))
