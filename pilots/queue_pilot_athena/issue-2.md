Athena issue 2: `compute_time_stop_status`, a read-time time-stop for preset `position`

`docs/validation/16-exit-rules.md` found a real edge for a time-stop only for the preset `position` (40 trading days, `TIME_STOP_DAYS["position"]` in `scripts/validate_exit_rules.py`). It was never implemented. Add a pure helper in `dashboard/dashboard_logic.py`, next to `compute_trailing_stop_levels`:

`compute_time_stop_status(open_positions: list[TradeRecord], today: date | None = None) -> dict[str, dict]`

- Only a position whose `preset_key_at_signal == "position"` is considered. Positions with another preset, or with `None`, and positions missing `entry_date` are omitted (same "omit, do not invent" rule as the trailing stop).
- `today` defaults to the current date; a test passes its own.
- `days_held` is the number of weekdays (Monday to Friday) from the entry date up to `today`, counted with `numpy.busday_count(entry_day, today)` where `entry_day` is the first 10 characters of `entry_date`. Exchange holidays are NOT removed; say so in the docstring.
- Each result is keyed by `trade_id` and is `{"days_held": <int>, "limit": 40, "days_left": <int>, "due": <bool>}` where `days_left = max(limit - days_held, 0)` and `due = days_held >= limit`.
- The limit is one module constant `TIME_STOP_DAYS_POSITION = 40`. It must not import from `scripts/`.
- It changes no record, no stop-loss, no take-profit, and makes no network call. It is informational only, like the trailing stop.

Add tests in `tests/test_dashboard_logic.py` (or the file that already tests `compute_trailing_stop_levels`): a `position` trade 39, 40 and 41 weekdays old (due false, true, true; `days_left` 1, 0, 0), a trade of another preset, a `None` preset, a missing `entry_date`, an empty list, an entry date that is later than `today` (days_held 0, never negative), and an entry on a weekend. Write the docstring and a short note in CHANGELOG.md.
