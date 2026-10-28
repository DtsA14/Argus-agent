"""ReadDocs on the harness side (docs/reviews/SPEC_WEB_TOOLS.md): the child process that downloads, and the per-run
store and budgets that make a page read once per run and keep an attempt within its limits, also across a crash.

The harness process never opens a connection to the web: `spawn` runs tools/web_fetch.py as `python -I -S` with an
empty environment (no API key, no proxy) and checks the shape of its one JSON answer. `DocsReader` keeps every fetched
page (or the refusal of one) under <run>/web/pages/ before the tool result is returned, so a step that runs again after
a crash reads the stored page instead of downloading it again; the text served to each attempt is recorded per tool
step (its memo key), so a step that runs again is not counted twice.
"""
import hashlib
import json
import math
import os
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
    bad = sorted({str(v.get("environment")) for v in contract["validation"]
                  if v.get("environment") not in (w.get("environments") or [])})
    if bad:
        return f"ReadDocs is not allowed for environment(s) {', '.join(bad)} (web.environments)"
    if not w.get("hosts") or not w.get("limits"):
        return "ReadDocs has no hosts or limits in the config (web)"
    return None


def refusal(reason, chain=None):
    return {"ok": False, "reason": reason, "chain": list(chain or [])}


def checked(out, url, hosts, limits):
    """The child's answer if it has the documented shape and keeps every rule this side can check; else a refusal."""
    if not isinstance(out, dict) or not isinstance(out.get("ok"), bool):
        return refusal("the downloader gave no usable answer")
    chain = out.get("chain")
    if not isinstance(chain, list) or not all(isinstance(u, str) and wf.check_url(u, hosts, limits) is None
                                              for u in chain):
        return refusal("the downloader's answer names a URL that is not allowed")
    if not out["ok"]:
        return refusal(str(out.get("reason") or "refused")[:300], chain)
    if any(not isinstance(out.get(k), t) or isinstance(out.get(k), bool) for k, t in SHAPE.items()):
        return refusal("the downloader's answer is incomplete", chain)
    if (out["url"] != url or not chain or chain[0] != url or chain[-1] != out["final_url"]
            or len(chain) > limits["redirects"] + 1 or out["status"] != 200 or out["content_type"] not in wf.TYPES
            or not wf.ip_ok(out["ip"]) or out["bytes"] > limits["page_bytes"] or len(out["text"]) > limits["page_text"]
            or hashlib.sha256(out["text"].encode("utf-8")).hexdigest() != out["sha256"]):
        return refusal("the downloader's answer breaks a rule", chain)
    return {k: out[k] for k in ("ok", *SHAPE)}


def spawn(url, hosts, limits):
    """Fetch one URL in a child process with no environment -> a checked result (see web_fetch)."""
    cmd = [sys.executable, "-I", "-S", str(CHILD), json.dumps({"url": url, "hosts": hosts, "limits": limits})]
    try:
        p = subprocess.run(cmd, env={}, capture_output=True, text=True, timeout=limits["timeout_s"] + 15,
                           cwd=tempfile.gettempdir())
    except (subprocess.TimeoutExpired, OSError) as e:
        return refusal(f"the downloader did not finish: {type(e).__name__}")
    try:
        out = json.loads(p.stdout)
    except ValueError:
        return refusal("the downloader gave no usable answer")
    return checked(out, url, hosts, limits)


def _write(path, data):
    """Write JSON atomically (the file appears whole or not at all)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(f".{os.getpid()}.tmp")
    tmp.write_text(json.dumps(data, sort_keys=True), encoding="utf-8")
    os.replace(tmp, path)


class DocsReader:
    """The ReadDocs pages of one run (<run_dir>/web) for one attempt. web: the frozen config {hosts, limits}."""

    def __init__(self, web, run_dir, attempt, log, spawn=spawn, clock=time.time):
        self.hosts, self.limits = web["hosts"], web["limits"]
        self.dir, self.attempt, self.log, self.spawn, self.clock = Path(run_dir) / "web", attempt, log, spawn, clock
        self.served_path = self.dir / f"served_{attempt}.jsonl"

    def _pages(self):
        return [json.loads(p.read_text(encoding="utf-8")) for p in sorted((self.dir / "pages").glob("*.json"))]

    def _served(self):
        if not self.served_path.exists():
            return []
        return [json.loads(line) for line in self.served_path.read_text(encoding="utf-8").splitlines() if line]

    def _page(self, url):
        """The stored page (or refusal) of url, fetched now within the budgets if there is none."""
        path = self.dir / "pages" / (hashlib.sha256(url.encode("utf-8")).hexdigest() + ".json")
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
        why = wf.check_url(url, self.hosts, self.limits)
        if why:
            return refusal(why)                       # no connection was made: nothing to store
        lim, pages = self.limits, self._pages()
        here = sum(p.get("bytes", 0) for p in pages if p.get("attempt") == self.attempt)
        total = sum(p.get("bytes", 0) for p in pages)
        if len(pages) >= lim["pages_run"]:
            return refusal(f"this run has fetched {lim['pages_run']} pages, its limit")
        if here + lim["page_bytes"] > lim["attempt_bytes"] or total + lim["page_bytes"] > lim["run_bytes"]:
            return refusal(f"one more page could pass the download budget ({lim['attempt_bytes']} bytes per attempt, "
                           f"{lim['run_bytes']} per run)")
        out = self.spawn(url, self.hosts, self.limits)
        page = {**out, "attempt": self.attempt, "fetched_at": self.clock(), "asked": url}
        if not out["ok"]:
            page["bytes"] = 0
        _write(path, page)
        self.log.emit("web_fetch", url=url, ok=out["ok"], final_url=out.get("final_url"), chain=out.get("chain"),
                      ip=out.get("ip"), status=out.get("status"), bytes=out.get("bytes"), sha256=out.get("sha256"),
                      reason=out.get("reason"), attempt=self.attempt)
        return page

    def read(self, url, part, step_key):
        """{"ok": False, "reason"} or {"ok": True, "page", "part", "parts", "text"} for one ReadDocs call."""
        if not isinstance(url, str) or not isinstance(part, int) or isinstance(part, bool) or part < 1:
            return refusal("url must be text and part a whole number from 1")
        served = [s for s in self._served() if s["step"] != step_key]
        urls = {s["url"] for s in served}
        if url not in urls and len(urls) >= self.limits["pages_attempt"]:
            return refusal(f"this attempt has read {self.limits['pages_attempt']} different pages, its limit")
        page = self._page(url)
        if not page["ok"]:
            return refusal(page["reason"], page.get("chain"))
        size = self.limits["part_chars"]
        parts = max(1, math.ceil(len(page["text"]) / size))
        if part > parts:
            return refusal(f"the page has {parts} part(s); part {part} does not exist")
        text = page["text"][(part - 1) * size: part * size]
        used = sum(s["chars"] for s in served)
        if used + len(text) > self.limits["attempt_text"]:
            return refusal(f"this attempt has been given {used} characters of web text; this part would pass its "
                           f"limit of {self.limits['attempt_text']}")
        if step_key not in {s["step"] for s in self._served()}:
            self.served_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.served_path, "a", encoding="utf-8") as f:
                f.write(json.dumps({"step": step_key, "url": url, "part": part, "chars": len(text)}) + "\n")
                f.flush()
                os.fsync(f.fileno())
        return {"ok": True, "page": page, "part": part, "parts": parts, "text": text}
