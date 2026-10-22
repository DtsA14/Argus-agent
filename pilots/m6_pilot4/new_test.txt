"""models/pricing.py is_peak: a peak window that crosses midnight (M6 pilot 4).

A window is [start, end) in UTC hours, end exclusive. [1, 4] is 01:00 up to 04:00. A window with start > end crosses midnight: [22, 4]
is 22:00 up to midnight and midnight up to 04:00. Today such a window never matches, so a provider whose peak price runs through the night
would be billed at the off-peak price.

Rules the tests pin down:
- start < end: as before, start <= hour < end.
- start > end: hour >= start or hour < end (end exclusive).
- start == end: an empty window, never peak (not "all day").
- weekdays_only is judged on the UTC date of `now`, also for a window that crosses midnight (Saturday 01:00 UTC is not peak even though
  the window began on Friday evening).
- several windows: peak when any matches; a `now` in another time zone is converted to UTC; no window (None, empty): never peak.
"""
from datetime import datetime, timedelta, timezone

import pytest

from models.pricing import cost_usd, is_peak, multiplier

NIGHT = {"utc_hours": [[22, 4]]}
NIGHT_WEEKDAYS = {"utc_hours": [[22, 4]], "weekdays_only": True}
PRICE = {"input": 1.0, "output": 1.0, "peak_multiplier": 2}
FRI, SAT, SUN, MON = (datetime(2026, 10, d, tzinfo=timezone.utc) for d in (23, 24, 25, 26))   # 2026-10-26 is a Monday


def at(day, hour, minute=0):
    return day + timedelta(hours=hour, minutes=minute)


# ---- a window that crosses midnight (these fail until is_peak handles it) --------------------------------------------

def test_the_evening_part_of_a_window_across_midnight_is_peak():
    assert is_peak(NIGHT, at(FRI, 22))
    assert is_peak(NIGHT, at(FRI, 23, 59))


def test_the_early_morning_part_of_a_window_across_midnight_is_peak():
    assert is_peak(NIGHT, at(SAT, 0))
    assert is_peak(NIGHT, at(SAT, 1))
    assert is_peak(NIGHT, at(SAT, 3, 59))


def test_two_windows_one_of_them_across_midnight():
    two = {"utc_hours": [[22, 4], [6, 10]]}
    assert is_peak(two, at(FRI, 23)) and is_peak(two, at(SAT, 2)) and is_peak(two, at(FRI, 7))
    assert not is_peak(two, at(FRI, 5)) and not is_peak(two, at(FRI, 12))


def test_weekdays_only_follows_the_utc_date_of_now_also_across_midnight():
    assert is_peak(NIGHT_WEEKDAYS, at(FRI, 23))
    assert is_peak(NIGHT_WEEKDAYS, at(MON, 1))           # Monday 01:00 UTC: a weekday, although the window began on Sunday
    assert not is_peak(NIGHT_WEEKDAYS, at(SAT, 1))       # Saturday 01:00 UTC: a weekend date, although the window began on Friday
    assert not is_peak(NIGHT_WEEKDAYS, at(SAT, 23))
    assert not is_peak(NIGHT_WEEKDAYS, at(SUN, 23))


def test_a_time_in_another_zone_is_converted_to_utc():
    seven_am_in_jakarta = datetime(2026, 10, 24, 6, 0, tzinfo=timezone(timedelta(hours=7)))   # 2026-10-23 23:00 UTC
    assert is_peak(NIGHT, seven_am_in_jakarta)


def test_the_multiplier_and_the_cost_follow_a_window_across_midnight():
    kw = dict(input_tokens=1_000_000, output_tokens=1_000_000, window=NIGHT)
    assert multiplier(PRICE, NIGHT, at(FRI, 23)) == 2 and multiplier(PRICE, NIGHT, at(SAT, 2)) == 2
    assert cost_usd(PRICE, now=at(FRI, 23), **kw) == pytest.approx(4.0)
    assert cost_usd(PRICE, now=at(SAT, 12), **kw) == pytest.approx(2.0)


# ---- what is true today and must stay true (these pass before the change too) ----------------------------------------

def test_hours_outside_a_window_across_midnight_are_not_peak_and_the_end_is_exclusive():
    for hour in (4, 5, 12, 21):
        assert not is_peak(NIGHT, at(FRI, hour))
    assert not is_peak(NIGHT, at(FRI, 21, 59))


def test_an_ordinary_window_is_start_inclusive_and_end_exclusive():
    w = {"utc_hours": [[1, 4]]}
    assert is_peak(w, at(FRI, 1)) and is_peak(w, at(FRI, 3, 59))
    assert not is_peak(w, at(FRI, 0, 59)) and not is_peak(w, at(FRI, 4))


def test_two_ordinary_windows_and_weekends():
    w = {"utc_hours": [[1, 4], [6, 10]], "weekdays_only": True}
    assert is_peak(w, at(FRI, 2)) and is_peak(w, at(FRI, 9)) and not is_peak(w, at(FRI, 5)) and not is_peak(w, at(FRI, 10))
    assert not is_peak(w, at(SAT, 2)) and not is_peak(w, at(SUN, 7))


def test_a_window_whose_start_equals_its_end_is_empty():
    for window in ({"utc_hours": [[5, 5]]}, {"utc_hours": [[22, 22]]}, {"utc_hours": [[0, 0]]}):
        assert not any(is_peak(window, at(FRI, h)) for h in range(24))


def test_no_window_is_never_peak():
    assert not is_peak(None, at(FRI, 23)) and not is_peak({}, at(FRI, 23))


def test_an_end_of_24_runs_to_midnight():
    w = {"utc_hours": [[20, 24]]}
    assert is_peak(w, at(FRI, 20)) and is_peak(w, at(FRI, 23, 59))
    assert not is_peak(w, at(FRI, 19, 59)) and not is_peak(w, at(SAT, 0))


def test_the_cost_outside_any_window_is_the_plain_price():
    kw = dict(input_tokens=1_000_000, output_tokens=0, window={"utc_hours": [[1, 4]]})
    assert cost_usd(PRICE, now=at(FRI, 2), **kw) == pytest.approx(2.0)
    assert cost_usd(PRICE, now=at(FRI, 5), **kw) == pytest.approx(1.0)
