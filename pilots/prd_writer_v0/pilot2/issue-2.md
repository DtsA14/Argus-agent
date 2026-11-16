Add GET /budget/jobs: jobs ranked by cost against the cap, filterable by ISO week

The human wants to know which jobs are the most expensive. Add one endpoint GET /budget/jobs in ledger/api.py, built on job_entries and the helpers budget_over_80 and job_week of ledger/summary.py. The endpoint follows the same login rules as /jobs.

Rules:
1. `GET /budget/jobs` answers a JSON list, one item per job of the directory, sorted by `cost_nano` descending, ties broken by job id ascending. Each item has the keys, in this order: `job`, `state`, `created_at`, `max_usd` (only when the job has a cap, the value as `_max_usd_number` gives it, e.g. 1.0; the key is absent for no cap), `cost_nano`, `cost_usd` (the four-decimal text, e.g. "0.8000" for 800000000), `over_80_percent` (the value of budget_over_80, a JSON true or false).
2. `?week=2026-W44` keeps only the jobs whose job_week is exactly "2026-W44". A job whose job_week is None is left out when a week is given. Without `week` every job is listed.
3. A `week` value that is not a real ISO week in the form YYYY-Www (for example "2026-44", "2026-W54", "2026-W5", "", "abc") answers 400 with {"detail": "unknown week: <value>"}. "2026-W53" is valid (2026 has 53 ISO weeks).
4. Example: jobs A (created 2026-10-28T03:13:52Z, cost 800000000, cap 1.0), B (created 2026-10-29T10:00:00Z, cost 1500000000, cap 1.0), C (created 2026-11-03T08:00:00Z, cost 800000000, no cap). Without week the order is B, A, C (the tie A and C is by job id, A first if its id sorts first). With ?week=2026-W44 only B and A are listed. B gives over_80_percent true, A false, C false and C has no max_usd key.
5. An empty or missing jobs directory answers []. Without a session when a password hash is set the endpoint answers 401 with {"detail": "login required"}, as /jobs does.
6. Add a section for this endpoint to README.md under the API part, with the example of rule 4, and say that the viewer proxy does not forward it yet.

Nothing else changes: `/jobs`, `/jobs/{job_id}`, `/summary`, `/scoreboard` and their outputs stay exactly as they are. The existing tests keep passing unchanged.

Tests: new file tests/test_budget_jobs.py with TestClient over a tmp_path directory holding the jobs A, B, C of rule 4: the exact list without week, the list with ?week=2026-W44, ?week=2026-W54 giving 400 with the detail text, an empty directory giving [], and the cost_usd text "0.8000".

Environment: ledger_py312_up2
