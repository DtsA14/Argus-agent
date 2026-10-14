from datetime import datetime, timezone


def is_peak(window, now):
    """True if `now` falls inside a provider's peak-price window (UTC hours, end exclusive)."""
    if not window:
        return False
    now = now.astimezone(timezone.utc)
    if window.get("weekdays_only") and now.weekday() >= 5:
        return False
    return any(start <= now.hour < end for start, end in window["utc_hours"])


def cost_usd(price, *, input_tokens, output_tokens, cache_read_tokens=0, window=None, now=None):
    """USD cost of one call, or None when the price is unknown (never guess)."""
    if not price or price.get("input") is None or price.get("output") is None:
        return None
    now = now or datetime.now(timezone.utc)
    multiplier = price.get("peak_multiplier", 1) if is_peak(window, now) else 1
    cache_rate = price.get("cache_read", price["input"])
    fresh = max(input_tokens - cache_read_tokens, 0)
    usd = (fresh * price["input"] + cache_read_tokens * cache_rate + output_tokens * price["output"]) / 1_000_000
    return usd * multiplier
