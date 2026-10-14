import os
import time

from .errors import BudgetExceeded, EstimateExceeded, TransientError
from .memo import node_key


def _meta(state):
    meta = {}
    if isinstance(state.get("task"), dict):
        meta["task"] = state["task"]["id"]
    if "iteration" in state:
        meta["iteration"] = state["iteration"]
    return meta


def guard(name, fn, *, log, retry, admit=None, estimate=None, memo=None, crash_at=None, crash_marker=None):
    """Wrap a graph node with the harness.

    Order of a node run:
      admission gate -> [simulated crash] -> memo lookup -> work (with retry)
      -> estimate check -> body_done (real spend) -> memo commit -> node_end

    admit(state) -> reason | None   refuse to run the node when it returns a reason (BudgetExceeded)
    estimate                        tokens this node may report; reporting more raises EstimateExceeded
    memo                            durable result store; a committed result is returned instead of redoing work
    crash_at/crash_marker           simulate a hard process crash (once) to prove checkpoint resume

    Events: body_done        = work actually performed and paid for (the spend ledger);
            result_committed = result is durable in the memo, so this node run will never be redone;
            node_end         = result handed back to LangGraph;
            memo_hit         = a re-scheduled node run answered from the memo, no work done.
    """

    def wrapped(state):
        meta = _meta(state)

        if admit is not None:
            reason = admit(state)
            if reason:
                log.emit("budget_stop", node=name, reason=reason, tokens_used=state.get("tokens_used", 0))
                raise BudgetExceeded(reason)

        def maybe_crash(point):
            # crash_at "worker" = before the node runs; "worker@after_commit" = result committed to the
            # memo but not yet handed back to LangGraph (the case the memo exists for).
            if crash_at == point and crash_marker and not os.path.exists(crash_marker):
                open(crash_marker, "w").close()
                log.emit("crash_simulated", node=name, point=point, **meta)
                os._exit(42)

        maybe_crash(name)

        key = node_key(name, state)
        if memo is not None:
            cached = memo.get(key)
            if cached is not None:
                log.emit("memo_hit", node=name, tokens=cached.get("tokens_used", 0), **meta)
                return {**cached, "elapsed_s": 0.0}

        log.emit("node_start", node=name, **meta)
        t0 = time.monotonic()
        for attempt in range(1, retry["attempts"] + 1):
            try:
                out = fn(state)
                break
            except TransientError as e:
                log.emit("retry", node=name, attempt=attempt, error=str(e), **meta)
                if attempt == retry["attempts"]:
                    log.emit("retry_exhausted", node=name, attempts=attempt, **meta)
                    raise
                time.sleep(retry["base_delay"] * 2 ** (attempt - 1))

        out = dict(out)
        used = out.get("tokens_used", 0)
        if estimate is not None and used > estimate:
            log.emit("estimate_overrun", node=name, tokens=used, estimate=estimate, **meta)
            raise EstimateExceeded(f"{name} reported {used} tokens, estimate is {estimate}")
        log.emit("body_done", node=name, tokens=used, **meta)

        if memo is not None:
            memo.put(key, out)
            log.emit("result_committed", node=name, **meta)
            maybe_crash(f"{name}@after_commit")

        dt = time.monotonic() - t0
        log.emit("node_end", node=name, seconds=round(dt, 3), tokens=used, **meta)
        return {**out, "elapsed_s": dt}

    return wrapped
