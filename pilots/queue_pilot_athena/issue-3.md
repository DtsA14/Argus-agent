Athena issue 3: `GET /api/v1/journal/time-stops`

Expose `compute_time_stop_status` (issue 2) through the API, the same way `/trailing-stops` exposes the trailing stop. Backend only: do not touch `frontend/`.

In `api/routes_journal.py` add `GET /time-stops` (route placed with the other fixed GET routes, before `/{trade_id}`), `response_model=dict[str, TimeStopStatus]`, where `TimeStopStatus` is a small pydantic model in `api/models.py` with `days_held: int`, `limit: int`, `days_left: int`, `due: bool`.

It selects open positions exactly as `/trailing-stops` does (`record_type == RECORD_TYPE_EXECUTED` and `exit_price is None`) and returns `compute_time_stop_status(open_positions)`. Unlike `/trailing-stops` it needs no price fetch, so it is cheap; say that in the docstring. The route has no side effect and writes no journal.

Add tests in `tests/test_api_journal.py`: no journal gives `{}`; an open `position` trade gives its status (patch the date helper or build `entry_date` from a fixed offset so the test passes on every day); a closed `position` trade is excluded; a `swing_pendek` trade is excluded; the route answers 200 and the keys are `trade_id`s. Add one line about the endpoint to the API list in README.md if the README lists the other journal endpoints.
