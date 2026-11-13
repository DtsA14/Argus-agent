"""The issue's own example, run at the base commit, shown before approve (SPEC_REPRO_V0 R1).

An issue that is already fixed at the base gives the drafter nothing to reproduce; it drafts something else, and the draft can
look fine. This runs the Python code blocks of the issue in the sandbox on a copy of the base tree and shows what they do, so
a human sees `ran clean, last output "0o600"` next to an issue that says 0o644. Display only: it never refuses, never changes a
draft, and any error (sandbox down, odd issue text) gives no result. A clean run does not prove the bug is gone, and a crash
does not prove it is there: the human reads the output against the issue.
"""
import doctest
import hashlib
import json
import os
import re
import shutil
import subprocess
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


def _session(code):
    """True for a block written as an interactive session: some line starts with the prompt `>>>`."""
    return any(ln.lstrip().startswith(">>>") for ln in code.splitlines())


def _examples(code):
    """[source] of the examples of a session block that run, in order (`# doctest: +SKIP` ones left out); ValueError when
    doctest's parser refuses the block. The expected output is not kept: comparing it is R2."""
    return [ex.source for ex in doctest.DocTestParser().get_examples(code)
            if not ex.options.get(doctest.SKIP) and ex.source.strip()]       # a bare prompt (or one before CRLF) has no code


def skip_reason(code):
    if len(code.encode("utf-8")) > MAX_CODE_BYTES:
        return f"longer than {MAX_CODE_BYTES} bytes"
    lines = [ln for ln in code.splitlines() if ln.strip()]
    if not lines:
        return "empty"
    if any(ln.startswith("$ ") for ln in lines):
        return "a shell session, not a script"
    if _session(code):
        try:
            return None if _examples(code) else "no runnable doctest example"
        except ValueError:
            return "doctest examples do not parse"
    if any(ln.strip() == "..." for ln in lines):
        return "contains a bare ... line, not a script"
    return None


def program(code):
    """The code with the prelude in front; `from __future__` lines must come first in a file, so they go before it. A session
    block (`>>>`) becomes one `exec(compile(source, "<doctest>", "single"), globals())` per example, in one namespace: `single`
    prints the repr of an expression like the interactive prompt, and the source goes in through repr(), never as program text."""
    if _session(code):
        return PRELUDE + "".join(f"exec(compile({src!r}, '<doctest>', 'single'), globals())\n" for src in _examples(code))
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


# ---- the same example on the patched tree (SPEC_REPRO_PATCHED): shown next to the base run, never decisive -----------

PATCHED_SENTENCE = "the example runs agent-written code; compare both outputs against the issue"
PREFIX = "issue example, base -> patched: "


def run_patched(base_dir, patch_file, issue, sandbox_cfg, runner=None):
    """[result] like run(), on a copy of base_dir with the patch applied by `git apply` (what a human would apply); None
    (not run) when anything goes wrong, the patch not applying included."""
    try:
        with tempfile.TemporaryDirectory() as tmp:
            tree = Path(tmp) / "tree"
            shutil.copytree(base_dir, tree, symlinks=True)
            subprocess.run(["git", "-C", str(tree), "apply", "--whitespace=nowarn", str(Path(patch_file).resolve())],
                           check=True, capture_output=True, timeout=60)
            return run(tree, issue, sandbox_cfg, runner)
    except Exception:
        return None


def patch_sha(patch_file):
    """The sha256 of the patch as it is on disk now; "none" when there is none (an invalid package has no patch)."""
    try:
        return hashlib.sha256(Path(patch_file).read_bytes()).hexdigest()
    except OSError:
        return "none"


def pkey(issue, patch_sha256):
    return hashlib.sha256(f"patched\n{patch_sha256}\n{issue}".encode("utf-8")).hexdigest()


def store_patched(path, issue, patch_sha256, *, results=None, skipped=None):
    """Written atomically: a process that dies leaves the earlier file (the pending marker) and never half of a new one.
    results None and no skipped reason means "could not run" (also what a pending marker reads as)."""
    try:
        path = Path(path)
        tmp = path.with_name(path.name + ".tmp")
        tmp.write_text(json.dumps({"key": pkey(issue, patch_sha256), "skipped": skipped, "results": results}),
                       encoding="utf-8")
        os.replace(tmp, path)
    except Exception:
        pass


def load_patched(path, issue, patch_sha256):
    """None: no file (a job from before this). ("results", [..]), ("skipped", reason), ("error", None) it could not run
    (or the file is bad), ("stale", None) the file is for another issue or another patch."""
    try:
        if not Path(path).exists():
            return None
        rec = json.loads(Path(path).read_text(encoding="utf-8"))
        if rec.get("key") != pkey(issue, patch_sha256):
            return ("stale", None)
        if rec.get("skipped"):
            return ("skipped", _cut(str(rec["skipped"]), 200))
        if not isinstance(rec.get("results"), list):
            return ("error", None)
        clean = ("stdout", "stderr_last_line", "reason")
        return ("results", [{k: (_cut(r.get(k), MAX_OUT) if k in clean else r.get(k)) for k in KEEP}
                            for r in rec["results"] if isinstance(r, dict)])
    except Exception:
        return ("error", None)


def _kind(r):
    """(status, exception type, last output line) of a block that ran; None for one that did not."""
    if not isinstance(r, dict) or r.get("status") not in ("ok", "raised", "timeout"):
        return None
    exc = (r.get("stderr_last_line") or "").split(":", 1)[0].strip() if r["status"] == "raised" else ""
    return (r["status"], exc, _last_line(r.get("stdout")))


def label(base, patched):
    """Per block: "changed" when status, exception type or last output differ, "unchanged" when none does, None when a
    side did not run. No direction is better: ran clean -> raised is as changed as raised -> ran clean."""
    b = {r.get("index"): r for r in (base or []) if isinstance(r, dict)} if isinstance(base, list) else {}
    p = {r.get("index"): r for r in (patched or []) if isinstance(r, dict)} if isinstance(patched, list) else {}
    out = []
    for i in range(max(len(base) if isinstance(base, list) else 0, len(patched) if isinstance(patched, list) else 0)):
        kb, kp = _kind(b.get(i)), _kind(p.get(i))
        out.append(None if kb is None or kp is None else ("unchanged" if kb == kp else "changed"))
    return out


def _desc(r):
    k = _kind(r)
    if k is None:
        return "not run"
    if k[0] == "ok":
        return f'ran clean "{k[2][:OUT_SHOWN]}"' if k[2] else "ran clean"
    if k[0] == "raised":
        return "raised " + (r.get("stderr_last_line") or "an error")[:80]
    return "timed out"


def patched_line(base, state):
    """The one line for status; None when there is nothing to say (no file, or neither run had a block)."""
    if state is None:
        return None
    kind, val = state
    if kind == "skipped":
        return PREFIX + f"not run ({val})"
    if kind == "stale":
        return PREFIX + "not run (the patch changed since it was run)"
    if kind != "results":
        return PREFIX + "not run (error)"
    base = base if isinstance(base, list) else None
    labels = label(base, val)
    if not any(_kind(r) for r in val) and not any(_kind(r) for r in base or []):
        return None                                           # nothing ran on either side: nothing to compare
    bmap = {r.get("index"): r for r in (base or []) if isinstance(r, dict)}
    pmap = {r.get("index"): r for r in val if isinstance(r, dict)}
    parts = []
    for i, lab in enumerate(labels):
        parts.append(f"{_desc(bmap.get(i))} -> {_desc(pmap.get(i))}" + (f" [{lab}]" if lab else ""))
    return PREFIX + "; ".join(parts) + ": " + PATCHED_SENTENCE
