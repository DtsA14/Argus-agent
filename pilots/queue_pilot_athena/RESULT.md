# Pilot 2: queue on an outside repo (athena), 2026-11-16

n = 1, kept apart from the scoreboard figure. Queue `q20261116T025657Z-bddf`, repo `athena` at 2a1079ef86ad, environment `athena_py312`, cap $3.00, $1.00 per job.

| Item | Job | Result | Cost |
|---|---|---|---|
| 1 weekend-date test | j20261116_025704_dc79 | APPLIED 649e0c5 | $0.0841 |
| 2 `compute_time_stop_status` | j20261116_040843_157a | APPLIED 08700e9 | $0.0281 |
| 3 `GET /journal/time-stops` | j20261116_041841_201a | APPLIED dc98df1 | $0.0175 |

Total $0.1297 of $3.00. No retry, no redraft, no failure. Human actions (Atha, in the chat): one `queue go`, three `approve --sha`, three `apply --read-sha`. Claude ran the commands and read each draft and each patch's production diff.

Evidence after the last apply: the full athena suite in its own venv (not the sandbox) gave 903 passed, 0 failed (baseline in the sandbox: 871 passed, 6 skipped, 1 date-dependent failure; the venv checkout has the universe data, so the two numbers are not the same run).

Honest limits:
- Issues were written by Claude after reading athena's code, so "no Claude involvement" is not shown. The writing of issues is B2, still open.
- Issue 3 is backend only: the sandbox has no node, so no frontend test could run. Nothing shows the time-stop in the Journal tab.
- The README line asked for in issue 3 was not made: README was outside the writable scope (my scope error).
- Issue 1's patch adds a near-duplicate test (the drafter's red test file plus the one in the class); a comment calls 2024-03-13 a Monday (it is a Wednesday).
- Commits sit on athena `master`, not pushed, not deployed.
