"""The only door to model providers. Nodes never call a chat model directly.

For every request:
  1. count input tokens over the full context, including assistant tool calls and tool results
     (exact via the provider's counting API when available, otherwise a conservative heuristic); a failed
     count is `llm_count_failed` (nothing sent), retried like a call when transient, else LLMCallFailed;
  2. derive the output cap from what is left of the node's reservation, in tokens AND in USD;
  3. refuse before sending when not even `min_output_tokens` would fit, or when the input is over the
     reservation's per-call limit `max_input` (reason input_limit); nothing is billed;
  4. write `llm_call_started` (call_id, worst case) to the ledger, then send with max_tokens = cap;
  5. write the final `llm_call` event (same call_id), then charge the reservation;
  6. charge actual usage, or the worst case when usage is missing or the attempt failed.

Ledger lifecycle, per call_id:
  refused                                -> one `llm_call` with status refused, nothing sent. Two shapes:
                                            budget: est_input, max_tokens (the cap), tokens_left, usd_left;
                                            reason "input_limit" (D1): est_input, max_input, and no
                                            max_tokens / tokens_left / usd_left. Readers use .get().
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

from models.pricing import WindowError, cost_usd, multiplier
from models.registry import (ConfigError, ModelRef, build_chat_model, cache_usage, price_for, usage_from_message,
                             window_for)

from .errors import InputLimitExceeded, LLMCallFailed, ReservationExhausted, TransientError

TRANSIENT_STATUS = {408, 409, 425, 429}
# Context a node may attach to ledger events. Anything else is rejected, so meta can never
# overwrite or collide with the fields the wrapper writes itself.
META_KEYS = {"run_id", "node", "task", "iteration", "step", "tool_call_id"}


def usd_limit(cfg):
    v = (cfg.get("budget") or {}).get("max_usd")
    return math.inf if v is None else float(v)


def prompt_cache_for(cfg, role, ref):
    """D5: whether this role's calls carry cache markers. Only Anthropic (and the scripted fake, for tests); only the
    5-minute TTL; not Haiku 5.5; a cached model must have a write price while the budget is finite."""
    pc = {**((cfg.get("llm") or {}).get("prompt_cache") or {}), **((cfg["roles"][role].get("prompt_cache")) or {})}
    if not pc.get("enabled"):
        return False
    kind = ((cfg.get("providers") or {}).get(ref.provider) or {}).get("kind")
    if kind not in ("anthropic", "fake"):
        return False                              # other providers cache by themselves, without a write price
    if str(pc.get("ttl", "5m")) != "5m":
        raise ConfigError(f"role {role!r}: prompt_cache.ttl must be 5m (D5 does not use {pc.get('ttl')!r})")
    if str(ref) == "anthropic:claude-haiku-5-5":
        raise ConfigError(f"role {role!r}: prompt caching is not used for {ref} in D5")
    price = price_for(cfg, ref)
    if math.isfinite(usd_limit(cfg)) and (price is None or price.get("cache_write_5m") is None):
        raise ConfigError(f"role {role!r} caches prompts of {ref}, which has no cache_write_5m price: a cache write "
                          "could not be priced (add it to 'prices' or turn llm.prompt_cache off)")
    return True


def check_long_context(cfg, ref, max_input, what):
    """K2 (D5): a model priced higher above a prompt size (Haiku 5.5: x5 above 100,000 tokens, cache included) is refused
    when one call's input may exceed it; that tier is not modelled. Applies with or without caching."""
    above = (price_for(cfg, ref) or {}).get("long_context_above")
    if above is not None and max_input > int(above):
        raise ConfigError(f"{what}: {ref} is billed at a higher rate above {int(above):,} input tokens, and one call "
                          f"may send {max_input:,}; set max_input_tokens to {int(above):,} or less")


def with_cache_markers(messages):
    """D5: copies of the messages with a 5-minute cache marker on the last block of the system message (tools and system
    render before it, so both are cached) and of the last message (the rolling prefix). Never stored, never hashed."""
    out = list(messages)
    for i in sorted({0, len(out) - 1} if out and type(out[0]).__name__ == "SystemMessage" else {len(out) - 1}):
        if i < 0:
            continue
        m = out[i]
        blocks = [{"type": "text", "text": m.content}] if isinstance(m.content, str) else [
            dict(b) if isinstance(b, dict) else {"type": "text", "text": str(b)} for b in m.content]
        if not blocks or (blocks[-1].get("type") == "text" and not blocks[-1].get("text")):
            continue                              # nothing to mark (an empty text block is rejected by the API)
        blocks[-1] = {**blocks[-1], "cache_control": {"type": "ephemeral"}}
        out[i] = m.model_copy(update={"content": blocks})
    return out


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
    max_input: int | None = None     # per-call input limit (D1); None: only tokens and USD bound a call
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


def reply_details(msg):
    """What the provider reported about how a reply ended, for the ledger: the reasoning (thinking) tokens included
    in output_tokens and the stop reason. None when the provider did not report it; never inferred."""
    usage = getattr(msg, "usage_metadata", None) or {}
    md = getattr(msg, "response_metadata", None) or {}
    details = usage.get("output_token_details") or {}
    return {"reasoning_tokens": details.get("reasoning"),
            "stop_reason": md.get("stop_reason") or md.get("finish_reason")}


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


def _sent_text(m):
    """What the heuristic counter counts: `_text` plus the reasoning_content ArgusChatDeepSeek sends back for every
    earlier reply (SPEC_ESTIMATE_REASONING E1). Only that key: the memo restores it alone, so a live and a resumed run
    count the same context alike; tests/test_estimate_reasoning.py checks every adapter sends nothing else uncounted.
    Not part of prompt_hash, so memo keys stay as they were."""
    rc = (getattr(m, "additional_kwargs", None) or {}).get("reasoning_content")
    return _text(m) + (rc if isinstance(rc, str) else "")


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
    Counts the whole context: message content, assistant tool calls with their arguments, earlier reasoning sent
    back, tool results, and the tool schemas."""

    def count(messages, tools):
        chars = sum(len(_sent_text(m)) for m in messages)
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
        self.cache = prompt_cache_for(cfg, role, self.ref)       # D5; raises ConfigError before anything is sent
        self.model = model if model is not None else build_chat_model(cfg, role)
        if counter is not None:
            self.count, self.exact = counter, True
        else:
            # SPEC_HEURISTIC_INPUT_MARGIN H1: llm.input_margin_by_model (set by the router's overrides, absent in
            # config.yaml so the evals' configs stay equal to it), else input_margin
            margin = (llm.get("input_margin_by_model") or {}).get(str(self.ref), llm.get("input_margin", 1.2))
            self.count, self.exact = provider_counter(self.model, float(margin))
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

    def _usd(self, tin, tout, cached=0, write_5m=0, write_1h=0, *, mult):
        """USD of a call at peak multiplier `mult`, or None when the model is unpriced (never reported as $0)."""
        if self.price is None:
            return None
        usd = cost_usd(self.price, input_tokens=tin, output_tokens=tout, cache_read_tokens=cached,
                       cache_write_tokens=write_5m, cache_write_1h_tokens=write_1h, window=None)
        return None if usd is None else usd * mult      # an unknown cost stays None, never a guess

    def _worst_mult(self):
        """SPEC_PEAK_EDGES P1: before sending, a provider with a peak window is always priced at its peak, whatever the
        hour, so a call that runs into the window (or is billed by its start) never costs more than its worst case."""
        return max(1, self.price.get("peak_multiplier", 1)) if (self.price and self.window) else 1

    def _end_mult(self, start_mult, end):
        """SPEC_PEAK_EDGES P2: the higher multiplier of a call's start and end, never below either billing rule. The
        call was sent and paid for: a clock that fails at the end (WindowError) costs the peak, it does not raise."""
        try:
            return max(start_mult, multiplier(self.price, self.window, end))
        except WindowError:
            return self._worst_mult()

    def _worst_usd(self, tin, tout):
        """The most a call can cost: no cache hit, and with caching on every input token may be written (D5)."""
        plain = self._usd(tin, tout, mult=self._worst_mult())
        if not self.cache or plain is None:
            return plain
        return max(plain, self._usd(tin, tout, write_5m=tin, mult=self._worst_mult()))

    def _output_cap(self, est_in, res):
        """Largest max_tokens that keeps tokens and USD within the reservation (worst case: no cache hits)."""
        cap = min(self.max_output, res.tokens_left - est_in)
        if self.price is not None:
            out_rate = self.price["output"] * self._worst_mult() / 1_000_000
            usd_after_input = res.usd_left - self._worst_usd(est_in, 0)
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
            try:
                est_in = self.count(messages, tools)
            except Exception as exc:  # the provider's counting API failed: nothing was sent, nothing is charged
                transient = is_transient(exc)
                emit("llm_count_failed", attempt=attempt, transient=transient, http_status=http_status(exc),
                     error=f"{type(exc).__name__}: {str(exc)[:200]}")
                if not transient:
                    raise LLMCallFailed(f"{self.role}: counting the input failed: {type(exc).__name__}: {exc}") from exc
                if attempt == self.attempts:
                    raise LLMCallFailed(f"{self.role}: counting the input still failing after {attempt} attempts: "
                                        f"{exc}") from exc
                wait = retry_after_seconds(exc)
                self.sleep(self.base_delay * 2 ** (attempt - 1) * (0.5 + random.random()) if wait is None else wait)
                continue
            if reservation.max_input is not None and est_in > reservation.max_input:
                emit("llm_call", status="refused", reason="input_limit", attempt=attempt, est_input=est_in,
                     max_input=reservation.max_input)
                raise InputLimitExceeded(f"{self.role}: {est_in} input tokens, the limit per call is "
                                         f"{reservation.max_input}")
            cap = self._output_cap(est_in, reservation)
            if cap < self.min_output:
                emit("llm_call", status="refused", attempt=attempt, est_input=est_in, max_tokens=cap,
                     tokens_left=reservation.tokens_left, usd_left=reservation.usd_left)
                raise ReservationExhausted(
                    f"{self.role}: {est_in} input tokens + {self.min_output} output do not fit "
                    f"(left: {reservation.tokens_left} tokens, ${reservation.usd_left:.6f})")

            call_id = uuid.uuid4().hex[:12]
            worst_tokens, worst_nano = est_in + cap, to_nano(self._worst_usd(est_in, cap))
            if self.full_prompts:
                emit("llm_prompt", call_id=call_id, messages=[{"type": type(m).__name__, "text": _text(m)}
                                                               for m in messages])
            # Written before sending: if the process dies mid-request, reconcile_ledger() finds this
            # started event without a final one and charges the worst case.
            # the window and the clock are checked here, before sending (WindowError: nothing sent, nothing charged)
            start_mult = multiplier(self.price, self.window, self._now())
            emit("llm_call_started", call_id=call_id, attempt=attempt, est_input=est_in, max_tokens=cap,
                 worst_tokens=worst_tokens, worst_usd_nano=worst_nano, worst_usd=_usd(worst_nano))

            t0 = time.monotonic()
            try:
                msg = model.invoke(with_cache_markers(messages) if self.cache else messages, max_tokens=cap)
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
            mult = self._end_mult(start_mult, self._now())
            tin, tout, cached = usage_from_message(msg)
            cu = cache_usage(msg)
            if tin == 0 and tout == 0:
                tok, nano, charged = worst_tokens, worst_nano, "worst_case_no_usage"
            else:
                tok, nano, charged = (tin + tout, to_nano(self._usd(tin, tout, cached, cu["write_5m"], cu["write_1h"],
                                                                     mult=mult)), "actual")
            truncated = is_truncated(msg)
            try:
                emit("llm_call", call_id=call_id, status="ok", attempt=attempt, est_input=est_in, max_tokens=cap,
                     input_tokens=tin, output_tokens=tout, cache_read=cached, cache_creation=cu["creation"], tokens=tok,
                     usd_nano=nano, usd=_usd(nano), charged=charged, latency_s=latency, truncated=truncated,
                     peak=mult > 1, **reply_details(msg))
            finally:
                reservation.charge(tok, nano)
            if cu["write_1h"]:                   # D5 asks only for 5 minutes: priced at the 1-hour rate, and reported
                emit("cache_ttl_unexpected", call_id=call_id, ephemeral_1h_input_tokens=cu["write_1h"])
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
