Add budget flag and ISO week helpers to ledger/summary.py

The ledger has no per-job view of spending against the cap. Add two pure helper functions in ledger/summary.py that the next item will use. No route changes here.

Rules:
1. `budget_over_80(entry)` returns True only when `entry["max_usd"]` is a positive number (int or float, not bool) and `entry["nano"]` is strictly more than 80% of the cap in nano-dollars, i.e. `Fraction(nano) > Fraction(4, 5) * Fraction(max_usd) * 1000000000`, computed exactly with fractions.Fraction, never with float rounding. Examples: max_usd 1.0 and nano 800000000 gives False (exactly 80%); max_usd 1.0 and nano 800000001 gives True; max_usd 1.0 and nano 1500000000 gives True; max_usd 0.5 and nano 400000000 gives False; max_usd 0.5 and nano 400000001 gives True; max_usd 1.0 and nano 0 gives False; max_usd 0 and nano 5 gives False; max_usd -1.0 and nano 5 gives False; max_usd None (no cap) gives False.
2. `job_week(entry)` returns the ISO week of `entry["created_at"]` as text `YYYY-Www` (two-digit week, ISO year, zero-padded), using the UTC moment: a text ending in Z or with an offset is converted to UTC; a naive text is taken as UTC. Examples: created_at "2026-10-28T03:13:52Z" gives "2026-W44"; "2026-10-28T03:13:52+02:00" gives "2026-W44" (01:13:52 UTC, same day); "2027-01-01T00:00:00Z" gives "2026-W53" (the ISO year, not the calendar year); "2026-10-28T03:13:52" (naive) gives "2026-W44"; "not a date" gives None; "" gives None; a created_at that is not a string gives None.
3. Both helpers only read the entry dict they are given; they never open files.

Nothing else changes: `job_entries`, `_job_json` and every existing output stay as they are. The existing tests keep passing unchanged.

Tests: new file tests/test_budget_helpers.py with one test per example above (values exactly as listed: 800000000 False, 800000001 True, 400000001 with max_usd 0.5 True, "2026-W53" for 2027-01-01, None for "not a date").

Environment: ledger_py312_up2
