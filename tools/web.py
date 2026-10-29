"""ReadDocs on the harness side (docs/reviews/SPEC_WEB_TOOLS.md): the child process that downloads, and the per-run
store, ledger and budgets that make a page read once per run and keep an attempt within its limits, also across a crash.

The harness process never opens a connection to the web: `spawn` runs tools/web_fetch.py as `python -I -S` with an
empty environment (no API key, no proxy) and checks the shape of its one JSON answer; a refusal is rendered here from its
code (web_fetch.REASONS), never from text in the answer. `DocsReader` records each download in <run>/web/ledger.jsonl
before it starts (charged as a whole page, page_bytes) and when it ends (its real size when it succeeded), so a crash in
between still counts; it keeps every page (or a definite refusal of one; transient ones are tried again later) under
<run>/web/pages/ before the tool result is returned, so a step that runs again after a crash reads the stored page; and
it records the text served to each attempt per tool step (its memo key), so a step that runs again is not counted twice.
A line torn by a crash, or a page file left empty, is skipped or read as missing, never an error.
"""
import hashlib
import json
import math
import os
import secrets
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from . import web_fetch as wf

CHILD = Path(wf.__file__).resolve()
SHAPE = {"url": str, "final_url": str, "chain": list, "status": int, "content_type": str, "bytes": int, "ip": str,
         "sha256": str, "text": str}


def problem(web, contract):
    """Why ReadDocs may not be granted for (or run with) this contract, or None (SPEC_WEB_TOOLS 3). web: the config's
    web block. Every validation must run in an environment of web.environments, and hosts and limits must be set."""
    w = web or {}
    bad = sorted({str(v.get("environment") or "the default image (a validation names no environment)")
                  for v in contract["validation"] if v.get("environment") not in (w.get("environments") or [])})
    if bad:
        return f"ReadDocs is not allowed for environment(s) {', '.join(bad)} (web.environments)"
    if not w.get("hosts") or not w.get("limits"):
        return "ReadDocs has no hosts or limits in the config (web)"
    return None


def refusal(reason, chain=None, code=None):
    return {"ok": False, "reason": reason, "chain": list(chain or []), **({"code": code} if code else {})}


def failed(limits, chain=None):
    return refusal(wf.reason("failed", limits), chain, "failed")


def checked(out, url, hosts, limits):
    """The child's answer if it has the documented shape and keeps every rule this side can check; else a refusal."""
    if not isinstance(out, dict) or not isinstance(out.get("ok"), bool):
        return failed(limits)
    chain = out.get("chain")
    if not isinstance(chain, list) or not all(isinstance(u, str) and wf.check_url(u, hosts, limits) is None
                                              for u in chain):
        return failed(limits)
    if not out["ok"]:                     # rendered from the code, with the harness's values: no text of the answer
        code = out.get("code")
        if code == "url":
            return refusal(wf.check_url(url, hosts, limits) or wf.REASONS["url"], chain, "url")
        if code not in wf.REASONS:
            return refusal("the downloader refused the page", chain, "failed")
        return refusal(wf.reason(code, limits, out.get("status")), chain, code)
    if any(not isinstance(out.get(k), t) or isinstance(out.get(k), bool) for k, t in SHAPE.items()):
        return failed(limits, chain)
    if (out["url"] != url or not chain or chain[0] != url or chain[-1] != out["final_url"]
            or len(chain) > limits["redirects"] + 1 or out["status"] != 200 or out["content_type"] not in wf.TYPES
            or not wf.ip_ok(out["ip"]) or out["bytes"] > limits["page_bytes"] or len(out["text"]) > limits["page_text"]
            or hashlib.sha256(out["text"].encode("utf-8")).hexdigest() != out["sha256"]):
        return failed(limits, chain)
    return {k: out[k] for k in ("ok", *SHAPE)}


def spawn(url, hosts, limits):
    """Fetch one URL in a child process with no environment -> a checked result (see web_fetch)."""
    cmd = [sys.executable, "-I", "-S", str(CHILD), json.dumps({"url": url, "hosts": hosts, "limits": limits})]
    try:
        p = subprocess.run(cmd, env={}, capture_output=True, text=True, timeout=limits["timeout_s"] + 15,
                           cwd=tempfile.gettempdir())
    except (subprocess.TimeoutExpired, OSError):
        return failed(limits)
    try:
        out = json.loads(p.stdout)
    except ValueError:
        return failed(limits)
    return checked(out, url, hosts, limits)


def _fsync_dir(path):
    fd = os.open(path, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _write(path, data):
    """Write JSON atomically and durably (the file appears whole or not at all, also after a power loss)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(f".{os.getpid()}.tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(json.dumps(data, sort_keys=True))
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)
    _fsync_dir(path.parent)


def _append(path, record):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, sort_keys=True) + "\n")
        f.flush()
        os.fsync(f.fileno())


def _lines(path):
    """The JSON records of a journal; a line torn by a crash (it never completed, so it never counted) is skipped."""
    if not path.exists():
        return []
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            rec = json.loads(line)
        except ValueError:
            continue
        if isinstance(rec, dict):
            out.append(rec)
    return out


def page_path(run_dir, url):
    """Where the page (or definite refusal) asked for as `url` is kept in a run."""
    return Path(run_dir) / "web" / "pages" / (hashlib.sha256(url.encode("utf-8")).hexdigest() + ".json")


def _stored(path):
    try:
        page = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None                                    # missing, or left empty by a crash: as if never stored
    return page if isinstance(page, dict) and isinstance(page.get("ok"), bool) else None


def stored_page(run_dir, url):
    """The page this run downloaded for `url` ({"ok": True, "text", ...}), or None: never fetched, a refusal, or not
    readable (SPEC_RESEARCH_STAGE G1). Nothing is downloaded here."""
    if not isinstance(url, str):
        return None
    page = _stored(page_path(run_dir, url))
    return page if page and page["ok"] is True and isinstance(page.get("text"), str) else None


class DocsReader:
    """The ReadDocs pages of one run (<run_dir>/web) for one attempt. web: the frozen config {hosts, limits}."""

    def __init__(self, web, run_dir, attempt, log, spawn=spawn, clock=time.time):
        self.hosts, self.limits = web["hosts"], web["limits"]
        self.dir, self.attempt, self.log, self.spawn, self.clock = Path(run_dir) / "web", attempt, log, spawn, clock
        self.served_path, self.ledger_path = self.dir / f"served_{attempt}.jsonl", self.dir / "ledger.jsonl"

    def _downloads(self):
        """{id: {attempt, bytes}} of every download of the run: a whole page (page_bytes) until its end is recorded."""
        out = {}
        for rec in _lines(self.ledger_path):
            if rec.get("event") == "start" and isinstance(rec.get("id"), str):
                out[rec["id"]] = {"attempt": rec.get("attempt"), "bytes": self.limits["page_bytes"]}
            elif rec.get("event") == "end" and rec.get("id") in out and isinstance(rec.get("bytes"), int):
                out[rec["id"]]["bytes"] = rec["bytes"]
        return out

    def _page(self, url, text_room):
        """The stored page (or definite refusal) of url, fetched now within the budgets if there is none."""
        path = page_path(self.dir.parent, url)
        page = _stored(path)
        if page is not None:
            return page
        why = wf.check_url(url, self.hosts, self.limits)
        if why:
            return refusal(why, code="url")            # no connection was made: nothing to store
        lim, downloads = self.limits, self._downloads()
        if not text_room:
            return refusal(f"this attempt has no room left for web text (limit {lim['attempt_text']} characters); "
                           "no page was downloaded")
        here = sum(d["bytes"] for d in downloads.values() if d["attempt"] == self.attempt)
        total = sum(d["bytes"] for d in downloads.values())
        if len(downloads) >= lim["pages_run"]:
            return refusal(f"this run has made {lim['pages_run']} downloads, its limit")
        if here + lim["page_bytes"] > lim["attempt_bytes"] or total + lim["page_bytes"] > lim["run_bytes"]:
            return refusal(f"one more page could pass the download budget ({lim['attempt_bytes']} bytes per attempt, "
                           f"{lim['run_bytes']} per run)")
        did = secrets.token_hex(8)
        _append(self.ledger_path, {"event": "start", "id": did, "attempt": self.attempt, "url": url})
        out = self.spawn(url, self.hosts, self.limits)
        size = out["bytes"] if out["ok"] else lim["page_bytes"]          # a refusal may have read up to a whole page
        _append(self.ledger_path, {"event": "end", "id": did, "ok": out["ok"], "bytes": size})
        page = {**out, "attempt": self.attempt, "fetched_at": self.clock(), "asked": url}
        if out["ok"] or out.get("code") not in wf.TRANSIENT:
            _write(path, page)                         # a transient refusal is not kept: a later call tries again
        self.log.emit("web_fetch", url=url, ok=out["ok"], final_url=out.get("final_url"), chain=out.get("chain"),
                      ip=out.get("ip"), status=out.get("status"), bytes=out.get("bytes"), sha256=out.get("sha256"),
                      code=out.get("code"), attempt=self.attempt)
        return page

    def read(self, url, part, step_key):
        """{"ok": False, "reason"} or {"ok": True, "page", "part", "parts", "text"} for one ReadDocs call."""
        if not isinstance(url, str) or not isinstance(part, int) or isinstance(part, bool) or part < 1:
            return refusal("url must be text and part a whole number from 1")
        records = [s for s in _lines(self.served_path) if isinstance(s.get("step"), str)]
        served = [s for s in records if s["step"] != step_key]
        urls = {s.get("url") for s in served}
        if url not in urls and len(urls) >= self.limits["pages_attempt"]:
            return refusal(f"this attempt has read {self.limits['pages_attempt']} different pages, its limit")
        used = sum(s.get("chars", 0) for s in served)
        size = self.limits["part_chars"]
        page = self._page(url, text_room=used + min(size, self.limits["attempt_text"]) <= self.limits["attempt_text"])
        if not page["ok"]:
            return refusal(page["reason"], page.get("chain"), page.get("code"))
        parts = max(1, math.ceil(len(page["text"]) / size))
        if part > parts:
            return refusal(f"the page has {parts} part(s); part {part} does not exist")
        text = page["text"][(part - 1) * size: part * size]
        if used + len(text) > self.limits["attempt_text"]:
            return refusal(f"this attempt has been given {used} characters of web text; this part would pass its "
                           f"limit of {self.limits['attempt_text']}")
        if step_key not in {s["step"] for s in records}:
            _append(self.served_path, {"step": step_key, "url": url, "part": part, "chars": len(text)})
        return {"ok": True, "page": page, "part": part, "parts": parts, "text": text}
