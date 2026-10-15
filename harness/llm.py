"""The only door to model providers. Nodes never call a chat model directly.

For every request:
  1. count input tokens over the full context, including assistant tool calls and tool results
     (exact via the provider's counting API when available, otherwise a conservative heuristic);
  2. derive the output cap from what is left of the node's reservation, in tokens AND in USD;
  3. refuse before sending when not even `min_output_tokens` would fit (nothing is billed);
  4. write `llm_call_started` (call_id, worst case) to the ledger, then send with max_tokens = cap;
  5. write the final `llm_call` event (same call_id), then charge the reservation;
  6. charge actual usage, or the worst case when usage is missing or the attempt failed.

Ledger lifecycle, per call_id:
  refused                                -> one `llm_call` with status refused, nothing sent
  llm_call_started + llm_call (final)    -> ok / transient_error / error, charged as recorded
  llm_call_started without a final event -> unknown_after_crash: the process died mid-request;
                                            reconcile_ledger() charges it at worst case

What is and is not guaranteed:
  - Exact input counts (Anthropic): charges never exceed the reservation. Hard cap.
  - Heuristic counts (other providers): the cap is enforced against an estimate with a margin. If the
    provider bills more input than estimated and that pushes the node over its reservation, this is a
    `budget_violation`: logged, the reservation is closed to further calls, and the run ends as
    FAILED_BUDGET. It is detected, never hidden, but it is not an absolute financial cap.
  - Models without a price cannot be capped in USD, so they are refused whenever max_usd is finite.
"""
import hashlib
import json
import math
import os
import random
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

from models.pricing import cost_usd, multiplier
from models.registry import ConfigError, ModelRef, build_chat_model, price_for, usage_from_message, window_for

from .errors import LLMCallFailed, ReservationExhausted, TransientError

TRANSIENT_STATUS = {408, 409, 425, 429}
# Context a node may attach to ledger events. Anything else is rejected, so meta can never
# overwrite or collide with the fields the wrapper writes itself.
META_KEYS = {"run_id", "node", "task", "iteration", "step", "tool_call_id"}


def usd_limit(cfg):
    v = (cfg.get("budget") or {}).get("max_usd")
    return math.inf if v is None else float(v)


def check_priced(cfg, ref, what):
    """Unpriced models are refused whenever a finite USD budget must be enforced."""
    if price_for(cfg, ref) is not None:
        return
    budget = cfg.get("budget") or {}
    if math.isfinite(usd_limit(cfg)):
        raise ConfigError(f"{what} uses {ref}, which has no price in 'prices'. With a finite budget.max_usd "
                          f"its cost cannot be capped: add a price (or set max_usd: null to run uncapped)")
    if not budget.get("allow_unpriced", False):
        raise ConfigError(f"{what} uses {ref}, which has no price; add it to 'prices' or set "
                          "budget.allow_unpriced: true")


NANO = 1_000_000_000  # money is accounted in integer nano-dollars, so ledger and reservation sum exactly


def to_nano(usd):
    return None if usd is None else int(round(usd * NANO))


@dataclass
class Reservation:
    """Budget a node may spend on model calls. Sized from token_estimates before the iteration starts.
    Spend is kept in integer nano-dollars; `used_usd` is derived from it."""
    tokens: int
    usd: float
    used_tokens: int = 0
    used_nano: int = 0
    violated: bool = False

    @property
    def used_usd(self):
        return self.used_nano / NANO

    @property
    def tokens_left(self):
        return self.tokens - self.used_tokens

    @property
    def usd_left(self):
        return self.usd - self.used_usd

    def charge(self, tokens, nano):
        self.used_tokens += tokens
        self.used_nano += nano or 0
        over_usd = math.isfinite(self.usd) and self.used_nano > to_nano(self.usd)
        if self.used_tokens > self.tokens or over_usd:
            self.violated = True


def is_truncated(msg):
    """True when the provider stopped the reply at max_tokens: its text or tool arguments may be cut
    off, so nothing in it may be executed or accepted. Anthropic: stop_reason "max_tokens"; OpenAI and
    DeepSeek: finish_reason "length"; a reply replayed from the memo carries "truncated"."""
    md = getattr(msg, "response_metadata", None) or {}
    return md.get("stop_reason") == "max_tokens" or md.get("finish_reason") == "length" or md.get("truncated") is True


def is_transient(exc):
    if isinstance(exc, TransientError):
        return True
    status = http_status(exc)
    if isinstance(status, int):
        return status in TRANSIENT_STATUS or status >= 500
    name = type(exc).__name__.lower()
    return any(k in name for k in ("timeout", "connection", "overloaded", "ratelimit"))


def http_status(exc):
    status = getattr(exc, "status_code", None) or getattr(getattr(exc, "response", None), "status_code", None)
    return status if isinstance(status, int) else None


def retry_after_seconds(exc):
    headers = getattr(getattr(exc, "response", None), "headers", None) or {}
    try:
        return float(headers.get("retry-after"))
    except (TypeError, ValueError):
        return None


def _text(m):
    """Everything in a message that is sent to the provider: content, tool calls (name + args), ids."""
    # sort_keys: the memo stores replies with sorted keys, so a replayed reply must hash like the original or the
    # step after it misses the memo and is bought again (found in 3b: args with more than one key).
    content = m.content if isinstance(m.content, str) else json.dumps(m.content, default=str, ensure_ascii=False,
                                                                        sort_keys=True)
    parts = [content]
    for tc in getattr(m, "tool_calls", None) or []:
        parts.append(json.dumps({"name": tc.get("name"), "args": tc.get("args"), "id": tc.get("id")},
                                default=str, ensure_ascii=False, sort_keys=True))
    for tc in getattr(m, "invalid_tool_calls", None) or []:   # sent to the provider too, so part of the identity
        parts.append(json.dumps({"invalid": tc.get("name"), "args": tc.get("args"), "id": tc.get("id")},
                                default=str, ensure_ascii=False, sort_keys=True))
    if getattr(m, "tool_call_id", None):
        parts.append(m.tool_call_id)
    return "".join(parts)


def prompt_hash(messages, tools):
    payload = [(type(m).__name__, _text(m)) for m in messages]
    names = sorted(getattr(t, "name", None) or getattr(t, "__name__", str(t)) for t in (tools or []))
    return hashlib.sha256(json.dumps([payload, names], ensure_ascii=False).encode()).hexdigest()[:16]


def _tool_schema_text(t):
    schema = getattr(t, "args_schema", None)
    if schema is not None and hasattr(schema, "model_json_schema"):
        return json.dumps(schema.model_json_schema(), default=str)
    if hasattr(t, "model_json_schema"):  # a pydantic model passed as a tool
        return json.dumps(t.model_json_schema(), default=str)
    return str(t)


def heuristic_counter(margin):
    """~3 characters per token is pessimistic for English and Indonesian text; the margin adds more room.
    Counts the whole context: message content, assistant tool calls with their arguments, tool results,
    and the tool schemas."""

    def count(messages, tools):
        chars = sum(len(_text(m)) for m in messages)
        chars += sum(len(_tool_schema_text(t)) for t in (tools or []))
        return int((chars / 3 + 8 * len(messages)) * margin) + 1

    return count, False


def provider_counter(model, margin):
    """Exact counter when the provider has a counting API (Anthropic); otherwise the heuristic."""
    if type(model).__name__ == "ChatAnthropic":
        def count(messages, tools):
            return model.get_num_tokens_from_messages(messages, tools=tools or None)
        return count, True
    return heuristic_counter(margin)


def _usd(nano):
    """Readable dollars for the ledger; the exact figure is usd_nano. None stays None (unpriced)."""
    return None if nano is None else nano / NANO


def reconcile_ledger(events):
    """Turn ledger events into one record per call_id. A call that started but has no final event
    (the process died mid-request) is `unknown_after_crash` and charged at its worst case.
    Returns (records, totals)."""
    started, final, refused = {}, {}, []
    for e in events:
        if e.get("event") == "llm_call_started":
            started[e["call_id"]] = e
        elif e.get("event") == "llm_call":
            if e.get("status") == "refused":
                refused.append(e)
            else:
                final[e["call_id"]] = e
    records = []
    for cid, s in started.items():
        if cid in final:
            f = final[cid]
            records.append({"call_id": cid, "status": f["status"], "tokens": f.get("tokens", 0),
                            "usd_nano": f.get("usd_nano")})
        else:
            records.append({"call_id": cid, "status": "unknown_after_crash",
                            "tokens": s["worst_tokens"], "usd_nano": s.get("worst_usd_nano")})
    priced = [r["usd_nano"] for r in records if r["usd_nano"] is not None]
    total_nano = sum(priced)
    totals = {
        "calls": len(records),
        "refused": len(refused),
        "unknown_after_crash": sum(r["status"] == "unknown_after_crash" for r in records),
        "tokens": sum(r["tokens"] for r in records),
        "usd_nano": total_nano,
        "usd": total_nano / NANO,
        "usd_complete": len(priced) == len(records),   # False when an unpriced model was used
    }
    return records, totals


class LLMCaller:
    """One caller per role. `call()` is safe to use from parallel worker threads (no shared mutable state
    other than the reservation passed in, which belongs to a single node run)."""

    def __init__(self, cfg, role, log, *, model=None, counter=None, sleep=time.sleep, now=None):
        self.cfg, self.role, self.log = cfg, role, log
        rcfg = cfg["roles"][role]
        self.ref = ModelRef.parse(rcfg["model"])
        check_priced(cfg, self.ref, f"role {role!r}")
        self.price = price_for(cfg, self.ref)
        llm = cfg.get("llm", {})
        self.max_output = int(rcfg.get("max_output_tokens", 2048))
        self.min_output = int(llm.get("min_output_tokens", 64))
        self.attempts = int(llm.get("attempts", 3))
        self.base_delay = float(llm.get("base_delay", 1.0))
        self.failed_charge = llm.get("failed_attempt_charge", "worst_case")
        self.window = window_for(cfg, self.ref.provider)
        self.model = model if model is not None else build_chat_model(cfg, role)
        if counter is not None:
            self.count, self.exact = counter, True
        else:
            self.count, self.exact = provider_counter(self.model, float(llm.get("input_margin", 1.2)))
        self.sleep, self.now = sleep, now
        self.full_prompts = self._full_prompt_logging(cfg)

    def _full_prompt_logging(self, cfg):
        mode = cfg.get("logging", {}).get("prompts", "hashed")
        if mode == "full" and os.environ.get("ARGUS_DEV") != "1":
            self.log.emit("config_warning", message="logging.prompts=full ignored: set ARGUS_DEV=1 (synthetic data only)")
            return False
        return mode == "full"

    # ---- pricing helpers --------------------------------------------------------

    def _now(self):
        return self.now() if callable(self.now) else (self.now or datetime.now(timezone.utc))

    def _usd(self, tin, tout, cached=0):
        """USD of a call, or None when the model is unpriced (never reported as $0)."""
        if self.price is None:
            return None
        return cost_usd(self.price, input_tokens=tin, output_tokens=tout, cache_read_tokens=cached,
                        window=self.window, now=self._now())

    def _output_cap(self, est_in, res):
        """Largest max_tokens that keeps tokens and USD within the reservation (worst case: no cache hits)."""
        cap = min(self.max_output, res.tokens_left - est_in)
        if self.price is not None:
            mult = multiplier(self.price, self.window, self._now())
            out_rate = self.price["output"] * mult / 1_000_000
            usd_after_input = res.usd_left - self._usd(est_in, 0)
            cap = min(cap, int(usd_after_input / out_rate) if out_rate > 0 else cap)
        return cap

    # ---- the call ------------------------------------------------------------------

    def call(self, messages, reservation, *, tools=None, tool_choice=None, meta=None):
        meta = dict(meta or {})
        bad = sorted(set(meta) - META_KEYS)
        if bad:
            raise ValueError(f"meta keys not allowed: {bad}; allowed: {sorted(META_KEYS)}")
        phash = prompt_hash(messages, tools)
        if tools:
            model = self.model.bind_tools(tools, tool_choice=tool_choice) if tool_choice else self.model.bind_tools(tools)
        else:
            model = self.model
        system = {"role": self.role, "model": str(self.ref), "prompt_hash": phash}

        def emit(event, **fields):
            self.log.emit(event, **meta, **system, **fields)  # system fields last; meta cannot collide

        for attempt in range(1, self.attempts + 1):
            # A violated reservation needs no special case: its tokens or USD left are negative, so the
            # output cap below is negative and the call is refused before sending.
            est_in = self.count(messages, tools)
            cap = self._output_cap(est_in, reservation)
            if cap < self.min_output:
                emit("llm_call", status="refused", attempt=attempt, est_input=est_in, max_tokens=cap,
                     tokens_left=reservation.tokens_left, usd_left=reservation.usd_left)
                raise ReservationExhausted(
                    f"{self.role}: {est_in} input tokens + {self.min_output} output do not fit "
                    f"(left: {reservation.tokens_left} tokens, ${reservation.usd_left:.6f})")

            call_id = uuid.uuid4().hex[:12]
            worst_tokens, worst_nano = est_in + cap, to_nano(self._usd(est_in, cap))
            if self.full_prompts:
                emit("llm_prompt", call_id=call_id, messages=[{"type": type(m).__name__, "text": _text(m)}
                                                               for m in messages])
            # Written before sending: if the process dies mid-request, reconcile_ledger() finds this
            # started event without a final one and charges the worst case.
            emit("llm_call_started", call_id=call_id, attempt=attempt, est_input=est_in, max_tokens=cap,
                 worst_tokens=worst_tokens, worst_usd_nano=worst_nano, worst_usd=_usd(worst_nano))

            t0 = time.monotonic()
            try:
                msg = model.invoke(messages, max_tokens=cap)
            except Exception as exc:  # classify below; every attempt is recorded, then charged
                latency = round(time.monotonic() - t0, 3)
                transient = is_transient(exc)
                status_code = http_status(exc)
                tok, nano = (worst_tokens, worst_nano) if self.failed_charge == "worst_case" else (0, 0)
                try:
                    emit("llm_call", call_id=call_id, status="transient_error" if transient else "error",
                         attempt=attempt, est_input=est_in, max_tokens=cap, tokens=tok,
                         usd_nano=nano, usd=_usd(nano),
                         charged="worst_case" if tok else "none",
                         # received: the provider answered with an HTTP status, so it saw the request.
                         # unknown: timeout or connection error; it may or may not have processed it.
                         delivery="received" if status_code else "unknown", http_status=status_code,
                         latency_s=latency, error=f"{type(exc).__name__}: {str(exc)[:200]}")
                finally:
                    reservation.charge(tok, nano)
                if not transient:
                    raise LLMCallFailed(f"{self.role}: {type(exc).__name__}: {exc}") from exc
                if attempt == self.attempts:
                    raise LLMCallFailed(f"{self.role}: still failing after {attempt} attempts: {exc}") from exc
                wait = retry_after_seconds(exc)
                if wait is None:
                    wait = self.base_delay * 2 ** (attempt - 1) * (0.5 + random.random())
                self.sleep(wait)
                continue

            latency = round(time.monotonic() - t0, 3)
            tin, tout, cached = usage_from_message(msg)
            if tin == 0 and tout == 0:
                tok, nano, charged = worst_tokens, worst_nano, "worst_case_no_usage"
            else:
                tok, nano, charged = tin + tout, to_nano(self._usd(tin, tout, cached)), "actual"
            truncated = is_truncated(msg)
            try:
                emit("llm_call", call_id=call_id, status="ok", attempt=attempt, est_input=est_in, max_tokens=cap,
                     input_tokens=tin, output_tokens=tout, cache_read=cached, tokens=tok,
                     usd_nano=nano, usd=_usd(nano), charged=charged, latency_s=latency, truncated=truncated)
            finally:
                reservation.charge(tok, nano)
            if truncated:
                emit("output_truncated", call_id=call_id, max_tokens=cap, output_tokens=tout)
            if tin > est_in:
                emit("estimate_miss", call_id=call_id, est_input=est_in, input_tokens=tin, exact_counter=self.exact)
            if reservation.violated:
                emit("budget_violation", call_id=call_id, tokens_used=reservation.used_tokens,
                     tokens_reserved=reservation.tokens, usd_used=reservation.used_usd,
                     usd_reserved=reservation.usd, exact_counter=self.exact)
            return msg

        raise AssertionError("unreachable")
