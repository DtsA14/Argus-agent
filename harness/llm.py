"""The only door to model providers. Nodes never call a chat model directly.

For every request:
  1. count input tokens (exact via the provider's counting API when available, otherwise a
     conservative character heuristic with a safety margin);
  2. derive the output cap from what is left of the node's reservation, in tokens AND in USD;
  3. refuse before sending when not even `min_output_tokens` would fit (nothing is billed);
  4. send with max_tokens set to that cap;
  5. charge actual usage, or the worst case when the provider reports none or the attempt failed;
  6. write one `llm_call` ledger event per attempt, including refused and failed ones.

Guarantee: charged tokens and USD never exceed the reservation, provided the input count is not
an underestimate. Anthropic counts are exact. Heuristic counts carry a margin; if the provider
reports more input than estimated, the overshoot is charged and logged as `estimate_miss`.
"""
import hashlib
import json
import os
import random
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone

from models.pricing import cost_usd, multiplier
from models.registry import ConfigError, ModelRef, build_chat_model, price_for, usage_from_message, window_for

from .errors import LLMCallFailed, ReservationExhausted, TransientError

TRANSIENT_STATUS = {408, 409, 425, 429}


@dataclass
class Reservation:
    """Budget a node may spend on model calls. Sized from token_estimates before the iteration starts."""
    tokens: int
    usd: float
    used_tokens: int = 0
    used_usd: float = 0.0
    attempts: list = field(default_factory=list)

    @property
    def tokens_left(self):
        return self.tokens - self.used_tokens

    @property
    def usd_left(self):
        return self.usd - self.used_usd

    def charge(self, tokens, usd):
        self.used_tokens += tokens
        self.used_usd += usd


def is_transient(exc):
    if isinstance(exc, TransientError):
        return True
    status = getattr(exc, "status_code", None) or getattr(getattr(exc, "response", None), "status_code", None)
    if isinstance(status, int):
        return status in TRANSIENT_STATUS or status >= 500
    name = type(exc).__name__.lower()
    return any(k in name for k in ("timeout", "connection", "overloaded", "ratelimit"))


def retry_after_seconds(exc):
    headers = getattr(getattr(exc, "response", None), "headers", None) or {}
    try:
        return float(headers.get("retry-after"))
    except (TypeError, ValueError):
        return None


def prompt_hash(messages, tools):
    payload = [(type(m).__name__, m.content if isinstance(m.content, str) else json.dumps(m.content, default=str))
               for m in messages]
    names = sorted(getattr(t, "name", str(t)) for t in (tools or []))
    return hashlib.sha256(json.dumps([payload, names], ensure_ascii=False).encode()).hexdigest()[:16]


def heuristic_counter(margin):
    """~3 characters per token is pessimistic for English and Indonesian text; the margin adds more room."""

    def count(messages, tools):
        chars = sum(len(m.content if isinstance(m.content, str) else json.dumps(m.content, default=str))
                    for m in messages)
        chars += sum(len(json.dumps(getattr(t, "args_schema", None).model_json_schema()
                                    if getattr(t, "args_schema", None) is not None else str(t), default=str))
                     for t in (tools or []))
        return int((chars / 3 + 8 * len(messages)) * margin) + 1

    return count, False


def provider_counter(model, margin):
    """Exact counter when the provider has a counting API (Anthropic); otherwise the heuristic."""
    if type(model).__name__ == "ChatAnthropic":
        def count(messages, tools):
            return model.get_num_tokens_from_messages(messages, tools=tools or None)
        return count, True
    return heuristic_counter(margin)


class LLMCaller:
    """One caller per role. `call()` is safe to use from parallel worker threads (no shared mutable state
    other than the reservation passed in, which belongs to a single node run)."""

    def __init__(self, cfg, role, log, *, model=None, counter=None, sleep=time.sleep, now=None):
        self.cfg, self.role, self.log = cfg, role, log
        rcfg = cfg["roles"][role]
        self.ref = ModelRef.parse(rcfg["model"])
        self.price = price_for(cfg, self.ref)
        budget = cfg.get("budget", {})
        if self.price is None and not budget.get("allow_unpriced", False):
            raise ConfigError(f"role {role!r} uses {self.ref}, which has no price in config 'prices'; "
                              "add one or set budget.allow_unpriced: true")
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
        if self.price is None:
            return 0.0
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

    def call(self, messages, reservation, *, tools=None, meta=None):
        meta = dict(meta or {})
        phash = prompt_hash(messages, tools)
        model = self.model.bind_tools(tools) if tools else self.model
        base = {"role": self.role, "model": str(self.ref), "prompt_hash": phash, **meta}

        for attempt in range(1, self.attempts + 1):
            est_in = self.count(messages, tools)
            cap = self._output_cap(est_in, reservation)
            if cap < self.min_output:
                self.log.emit("llm_call", status="refused", attempt=attempt, est_input=est_in, max_tokens=cap,
                              tokens_left=reservation.tokens_left, usd_left=round(reservation.usd_left, 6), **base)
                raise ReservationExhausted(
                    f"{self.role}: {est_in} input tokens + {self.min_output} output do not fit "
                    f"(left: {reservation.tokens_left} tokens, ${reservation.usd_left:.6f})")

            if self.full_prompts:
                self.log.emit("llm_prompt", prompt_hash=phash, messages=[
                    {"type": type(m).__name__, "content": m.content} for m in messages], **meta)

            t0 = time.monotonic()
            try:
                msg = model.invoke(messages, max_tokens=cap)
            except Exception as exc:  # classify below; every attempt is charged and logged
                latency = round(time.monotonic() - t0, 3)
                transient = is_transient(exc)
                tok, usd = (est_in + cap, self._usd(est_in, cap)) if self.failed_charge == "worst_case" else (0, 0.0)
                reservation.charge(tok, usd)
                self.log.emit("llm_call", status="transient_error" if transient else "error", attempt=attempt,
                              est_input=est_in, max_tokens=cap, tokens=tok, usd=round(usd, 8), charged="worst_case"
                              if tok else "none", latency_s=latency, error=f"{type(exc).__name__}: {str(exc)[:200]}",
                              **base)
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
                tok, usd, charged = est_in + cap, self._usd(est_in, cap), "worst_case_no_usage"
            else:
                tok, usd, charged = tin + tout, self._usd(tin, tout, cached), "actual"
            reservation.charge(tok, usd)
            self.log.emit("llm_call", status="ok", attempt=attempt, est_input=est_in, max_tokens=cap,
                          input_tokens=tin, output_tokens=tout, cache_read=cached, tokens=tok, usd=round(usd, 8),
                          charged=charged, latency_s=latency, **base)
            if tin > est_in:
                self.log.emit("estimate_miss", role=self.role, est_input=est_in, input_tokens=tin,
                              exact_counter=self.exact, **meta)
            return msg

        raise AssertionError("unreachable")
