"""The only door to paid requests that are not model calls: DeepSeek Search and Fetch (docs/reviews/SPEC_RESEARCH_JOB.md §7-8).

Every request is accounted in the same ledger and the same reservation as the node's model calls, with the same events,
so reconcile_ledger, reservation_from_ledger, the router's job cap, status and the staging snapshot count it without a
change of their own:
  1. check the arguments (a refused URL or query is never sent, nothing is written or charged);
  2. refuse before sending when the reservation cannot pay one request (an `llm_call` with status refused);
  3. write `llm_call_started` (call_id, worst case = the price of one request), then run the child process;
  4. write the final `llm_call`, then charge the reservation (also when writing the event fails).
A request is a ledger line with role "web", model "<provider>:web_<kind>", tokens 0 and `paid_request: <kind>`.

What is charged: the provider bills only HTTP 200 answers that carry results or content. So: 200 with results or content
-> the price; an HTTP error status, or a 200 with nothing in it -> 0; no answer (timeout, connection lost, the child
failed) or an answer that cannot be read -> the price, because it cannot be shown that it was not billed. A request cut
off by a crash is `unknown_after_crash` in reconcile_ledger and charged at the price. Unpriced requests are refused
while max_usd is finite; when allowed, their cost is null, never 0.
"""
import ipaddress
import json
import math
import os
import subprocess
import sys
import tempfile
import time
import uuid
from pathlib import Path
from urllib.parse import urlsplit

from models.registry import ConfigError

from .errors import ReservationExhausted
from .llm import META_KEYS, to_nano, usd_limit, _usd

CHILD = Path(__file__).resolve().parent.parent / "tools" / "deepseek_web.py"
KINDS = ("search", "fetch")
TRANSIENT_STATUS = {408, 425, 429, 500, 502, 503, 504}
URL_MAX, QUERY_MAX, COUNT_MAX = 2048, 128, 10


class RequestRefused(ValueError):
    """The arguments cannot be sent (bad URL or query). Nothing was sent, written or charged."""


def check_query(query, count):
    if not isinstance(query, str) or not query.strip() or len(query) > QUERY_MAX:
        raise RequestRefused(f"the query must be 1..{QUERY_MAX} characters and not only spaces")
    if any(ord(c) < 32 or ord(c) == 127 for c in query):
        raise RequestRefused("the query contains control characters")
    if not isinstance(count, int) or isinstance(count, bool) or not 1 <= count <= COUNT_MAX:
        raise RequestRefused(f"count must be 1..{COUNT_MAX}")


def check_url(url):
    """http(s), a host name (not an IP address, not a single label), no user info, port 80/443 only, no spaces."""
    if not isinstance(url, str) or not url or len(url) > URL_MAX:
        raise RequestRefused(f"the URL must be 1..{URL_MAX} characters")
    if any(ord(c) <= 32 or ord(c) == 127 for c in url):
        raise RequestRefused("the URL contains spaces or control characters")
    try:
        parts = urlsplit(url)
        port = parts.port
    except ValueError:
        raise RequestRefused("the URL cannot be parsed") from None
    if parts.scheme not in ("http", "https"):
        raise RequestRefused("only http and https URLs can be fetched")
    if parts.username is not None or parts.password is not None or "@" in parts.netloc:
        raise RequestRefused("URLs with user info are refused")
    host = parts.hostname or ""
    if not host:
        raise RequestRefused("the URL has no host")
    try:
        ipaddress.ip_address(host.strip("[]"))
        is_ip = True
    except ValueError:
        is_ip = False
    if is_ip:
        raise RequestRefused("URLs with an IP address as host are refused")
    if "." not in host.strip("."):
        raise RequestRefused("the host must be a full domain name")
    if port not in (None, 80, 443):
        raise RequestRefused("only the default ports 80 and 443 are allowed")


def run_child(kind, args, key, limits):
    """One request in a child process with an empty environment; the key goes on stdin -> the child's result object,
    or {"ok": False, "reason": "child_failed"} when it could not be run or answered with something unreadable."""
    payload = json.dumps({"kind": kind, "args": args, "key": key, "limits": limits})
    try:
        p = subprocess.run([sys.executable, "-I", "-S", str(CHILD)], input=payload, env={}, capture_output=True,
                           text=True, timeout=limits["timeout_s"] + 15, cwd=tempfile.gettempdir())
        out = json.loads(p.stdout)
    except (subprocess.TimeoutExpired, OSError, ValueError):
        return {"ok": False, "reason": "child_failed", "status": None}
    return out if isinstance(out, dict) else {"ok": False, "reason": "child_failed", "status": None}


def known_empty(kind, body):
    """True only for the documented empty answers (search: results [], fetch: content ""). Any other shape is charged:
    an answer the harness does not recognise cannot be shown to be unbilled."""
    if kind == "search":
        return body.get("results") == []
    return isinstance(body.get("content"), str) and body["content"].strip() == ""


def outcome(kind, result):
    """(status, billed, delivery) of one child result. billed: True (the price), False (nothing)."""
    status = result.get("status")
    if result.get("ok") is True:
        body = result.get("body")
        if isinstance(body, dict):
            return "ok", not known_empty(kind, body), "received"
        return "error", True, "received"                       # unreadable: cannot show it was not billed
    reason = result.get("reason")
    if reason == "bad_request":                                # the child sent nothing
        return "error", False, "not_sent"
    if reason == "http_error" and isinstance(status, int) and 400 <= status <= 599:
        # free only with DeepSeek's own error body; a proxy's page (or a 3xx) may come after the request was billed
        billed = result.get("error_body") is not True
        return ("transient_error" if status in TRANSIENT_STATUS else "error"), billed, "received"
    if reason in ("timeout", "connection", "child_failed"):
        return "transient_error", True, "unknown"
    return "error", True, "received" if status else "unknown"  # too_large, bad_json, anything else


class PaidRequests:
    """One per node run's tools. `request()` is the only way a tool reaches DeepSeek Search/Fetch."""

    def __init__(self, cfg, log, *, spawn=run_child, key=None, now=time.monotonic):
        self.log, self.spawn, self.now = log, spawn, now
        wr = cfg.get("web_research") or {}
        self.provider = wr.get("provider", "deepseek")
        prices = wr.get("price_usd_per_request") or {}
        self.price_nano = {k: to_nano(prices[k]) if prices.get(k) is not None else None for k in KINDS}
        finite = math.isfinite(usd_limit(cfg))
        for kind, nano in self.price_nano.items():
            if nano is None and (finite or not (cfg.get("budget") or {}).get("allow_unpriced", False)):
                raise ConfigError(f"web_research.price_usd_per_request.{kind} is missing: with a finite budget.max_usd "
                                  f"the cost of a {kind} request cannot be capped")
        self.limits = {"timeout_s": float(wr.get("timeout_s", 30)), "max_bytes": int(wr.get("max_response_bytes",
                                                                                           4_000_000))}
        if key is None:
            env = ((cfg.get("providers") or {}).get(self.provider) or {}).get("api_key_env")
            key = os.environ.get(env) if env else None
        if not key:
            raise ConfigError(f"no API key for web_research provider {self.provider!r}")
        self._key = key

    def __repr__(self):                                         # never shows the key
        return f"PaidRequests(provider={self.provider!r})"

    def search(self, query, count, reservation, *, meta=None):
        check_query(query, count)
        return self._request("search", {"query": query, "count": count}, reservation, meta)

    def fetch(self, url, reservation, *, meta=None):
        check_url(url)
        return self._request("fetch", {"url": url}, reservation, meta)

    def _request(self, kind, args, reservation, meta):
        meta = dict(meta or {})
        bad = sorted(set(meta) - META_KEYS)
        if bad:
            raise ValueError(f"meta keys not allowed: {bad}; allowed: {sorted(META_KEYS)}")
        system = {"role": "web", "model": f"{self.provider}:web_{kind}", "paid_request": kind}

        def emit(event, **fields):
            self.log.emit(event, **meta, **system, **fields)

        price = self.price_nano[kind]
        if math.isfinite(reservation.usd) and (price is None or reservation.used_nano + price > to_nano(reservation.usd)):
            emit("llm_call", status="refused", attempt=1, est_input=0, max_tokens=0, tokens_left=reservation.tokens_left,
                 usd_left=reservation.usd_left)
            raise ReservationExhausted(f"web {kind}: unpriced, so it cannot run within a USD reservation" if price is None
                                       else f"web {kind}: one request costs ${price / 1e9:.6f}, "
                                            f"${reservation.usd_left:.6f} left")
        call_id = uuid.uuid4().hex[:12]
        # Written before sending: a crash mid-request leaves a started event without a final one, charged at the price.
        emit("llm_call_started", call_id=call_id, attempt=1, est_input=0, max_tokens=0, worst_tokens=0,
             worst_usd_nano=price, worst_usd=_usd(price))
        t0 = self.now()
        try:
            result = self.spawn(kind, args, self._key, dict(self.limits))
        except Exception:                                       # a spawn that raised: treated as no answer
            result = {"ok": False, "reason": "child_failed", "status": None}
        if not isinstance(result, dict):
            result = {"ok": False, "reason": "child_failed", "status": None}
        status, billed, delivery = outcome(kind, result)
        nano = (price if billed else 0) if price is not None else None
        try:
            emit("llm_call", call_id=call_id, status=status, attempt=1, est_input=0, max_tokens=0, tokens=0,
                 input_tokens=0, output_tokens=0, usd_nano=nano, usd=_usd(nano),
                 charged="request" if billed else "none", delivery=delivery, http_status=result.get("status"),
                 latency_s=round(self.now() - t0, 3),
                 **({} if result.get("ok") else {"error": str(result.get("reason"))[:40]}))
        finally:
            reservation.charge(0, nano)
        return result
