Athena issue 1: make `test_open_position_returns_a_level` pass on days that are not working days

`tests/test_api_journal.py::TestGetTrailingStops::test_open_position_returns_a_level` fails when the suite runs on a Saturday or Sunday. The fake price fetch builds its two bars with `pd.bdate_range(end=<today>, periods=2)`, which never contains a weekend day, while the position is recorded with an entry date of today. On a weekend no bar is on or after the entry date, so `compute_trailing_stop_levels` correctly omits the position and the test sees `{}`.

Fix the TEST only. Build the fake bars so the last bar is on the entry day whatever the weekday (for example `pd.date_range(end=<today>, periods=2)`), keep every other line and assertion of the test, and do not change `compute_trailing_stop_levels` or any file outside `tests/`.

Add one test in the same class that proves the intent: with the fake bars from the fixed test, the result is the same level (`1100.0 - 45.0`) on a weekday and on a weekend. It must not depend on the real date (patch or pass the date it needs), so it passes on every day of the week.
