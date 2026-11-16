## Goal
The human wants to see which jobs cost the most against their cap. Two additions: each job's cost is compared with its `max_usd` cap and a job that used more than 80% of it is flagged; and one endpoint lists the jobs from the most expensive down, filterable by ISO week.

## Contract
- Issue 1 creates in `ledger/summary.py`: `budget_over_80(entry)` (True only when the job has a positive numeric cap and its cost is strictly more than 80% of it) and `job_week(entry)` (the ISO week of `created_at` in UTC, text `YYYY-Www`, or None).
- Issue 2 uses both and creates `budget_jobs`, the handler of `GET /budget/jobs`. Its items have keys `job`, `state`, `created_at`, optionally `max_usd`, then `cost_nano`, `cost_usd`, `over_80_percent`.
- The endpoint is served by the ledger app. The viewer proxy does not forward it yet; reaching it through the proxy needs a separate change to the proxy outside this queue.
- Existing outputs of `/jobs`, `/jobs/{job_id}`, `/summary`, `/scoreboard` and the summary command do not change.

## Order
1. Helpers in `ledger/summary.py` (pure functions, no route). Testable alone.
2. The endpoint and its README section, using the helpers.

## Notes
Money stays integer nano-dollars. The 80% test is exact (Fraction), not float, so 800000000 nano against a cap of 1.0 is not flagged and 800000001 is.
