from datetime import datetime, timedelta, timezone


class WindowError(ValueError):
    """A peak window or a time that cannot be interpreted safely."""


def _is_int(v):
    return isinstance(v, int) and not isinstance(v, bool)


def is_peak(window, now):
    """True if `now` falls inside a provider's peak-price window (UTC hours, end exclusive).

    `now` must be timezone-aware (a naive datetime raises WindowError); it is
    converted to UTC. A falsy window means no peak window (False). An invalid
    window raises WindowError.
    """
    if not window:
        return False
    if not isinstance(window, dict):
        raise WindowError(f"peak window is not a dict: {window!r}")
    if "utc_hours" not in window:
        raise WindowError(f"peak window has no 'utc_hours' key: {window!r}")
    hours = window["utc_hours"]
    if not isinstance(hours, (list, tuple)):
        raise WindowError(f"'utc_hours' is not a list or tuple: {hours!r}")
    for item in hours:
        if not (isinstance(item, (list, tuple)) and len(item) == 2
                and _is_int(item[0]) and _is_int(item[1])):
            raise WindowError(f"'utc_hours' item is not [start, end] of two integers: {item!r}")
        if not (0 <= item[0] <= 23):
            raise WindowError(f"start hour not in 0..23: {item!r}")
        if not (0 <= item[1] <= 24):
            raise WindowError(f"end hour not in 0..24: {item!r}")
    if "weekdays_only" in window and not isinstance(window["weekdays_only"], bool):
        raise WindowError(f"'weekdays_only' is not a bool: {window['weekdays_only']!r}")
    if now.tzinfo is None or now.utcoffset() is None:
        raise WindowError(f"'now' has no time zone (naive datetime): {now!r}")
    now = now.astimezone(timezone.utc)
    if window.get("weekdays_only") and now.weekday() >= 5:
        return False
    hour = now.hour
    for start, end in hours:
        if start < end:
            if start <= hour < end:
                return True
        elif start > end:
            if hour >= start or hour < end:
                return True
    return False


def multiplier(price, window, now=None):
    now = now or datetime.now(timezone.utc)
    return price.get("peak_multiplier", 1) if (price and is_peak(window, now)) else 1


def cost_usd(price, *, input_tokens, output_tokens, cache_read_tokens=0, cache_write_tokens=0, cache_write_1h_tokens=0,
             window=None, now=None):
    """USD cost of one call, or None when the price is unknown (never guess). input_tokens is the whole prompt, cache
    reads and writes included (as LangChain reports it); writes are 5-minute unless counted as 1-hour. A write without
    a write rate has no known cost."""
    if not price or price.get("input") is None or price.get("output") is None:
        return None
    if (cache_write_tokens and price.get("cache_write_5m") is None) or (
            cache_write_1h_tokens and price.get("cache_write_1h") is None):
        return None
    now = now or datetime.now(timezone.utc)
    multiplier = price.get("peak_multiplier", 1) if is_peak(window, now) else 1
    cache_rate = price.get("cache_read", price["input"])
    fresh = max(input_tokens - cache_read_tokens - cache_write_tokens - cache_write_1h_tokens, 0)
    usd = (fresh * price["input"] + cache_read_tokens * cache_rate + output_tokens * price["output"]
           + cache_write_tokens * price.get("cache_write_5m", 0) + cache_write_1h_tokens * price.get("cache_write_1h", 0))
    return usd / 1_000_000 * multiplier


WIB = timezone(timedelta(hours=7))


def peak_line(provider, price, window, now, soon_s=1800):
    """The router's peak warning (SPEC_PEAK_EDGES P3): one line when `provider` is at its peak price at `now`, or goes to
    it within `soon_s`; None otherwise, and for a price without a multiplier above 1. Window hours are whole hours."""
    mult = (price or {}).get("peak_multiplier", 1)
    if not window or mult <= 1:
        return None
    now = now.astimezone(timezone.utc)
    hour = now.replace(minute=0, second=0, microsecond=0)
    times = lambda t: f"{t:%H:%M} UTC = {t.astimezone(WIB):%H:%M} WIB"
    tail = "off-peak costs about half" if mult == 2 else f"off-peak costs 1/{mult:g}"
    if is_peak(window, now):
        end = hour + timedelta(hours=1)
        for _ in range(24 * 8):                       # a week and a day: any weekly window ends in it
            if not is_peak(window, end):
                break
            end += timedelta(hours=1)
        return f"peak: {provider} is at {mult:g}x now (until {times(end)}); {tail}"
    start = hour + timedelta(hours=1)
    if (start - now).total_seconds() <= soon_s and is_peak(window, start):
        return f"peak: {provider} goes to {mult:g}x at {times(start)}; {tail}"
    return None
