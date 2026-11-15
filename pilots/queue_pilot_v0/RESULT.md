# Pilot v0 of `argus queue`: three chained issues on argus-ledger (2026-11-15)

Queue `q20261115T175659Z-94a1` (SPEC_PRD_QUEUE part A, #555), repo argus-ledger at `1aeb82d`, up to $3.00, $1.00 per job, environment `ledger_py312_up2`. Issues: `issue-1.md` to `issue-3.md` (ledger 021-023: `GET /scoreboard/models`, then `cost_usd` and a total, then `?kind=`). **n = 1; not part of the scoreboard figure** (`verification/scoreboard-*.json`), kept apart from the old data.

| Item | Job | Draft (submits) | Agent | Model cost | Applied (UTC) | Commit |
|---|---|---|---|---|---|---|
| 1 | j20261115_175928_aaad | first, 3 of 7 | 1 attempt, 16 steps | $0.0292 | 18:06:23 | 3633c98 |
| 2 | j20261115_180631_8742 | first, 2 of 7 | 1 attempt, 27 steps | $0.0330 | 18:15:46 | f230474 |
| 3 | j20261115_181548_0bc4 | first, 7 of 7 | 1 attempt, 18 steps | $0.0470 | 18:43:42 | 88c31e1 |

Total model cost $0.1092 of $3.00. All three reached `APPLIED` (`argus apply`, `as_is` true, patch as it was), each on the commit the previous was applied as; the queue ended `DONE`. Nothing pushed or deployed (no staging, so this is not a "to staging" figure).

Human actions: one `queue go`, three `approve --sha`, three `apply --read-sha` (Atha, in the chat; Claude ran the commands and read each patch's production diff, not the whole test diff). About 46 minutes from `go` (about 17:57) to the last apply; the longest wait was 21 minutes for the approval of draft 3 (ready 18:18:51, approved 18:40:21). Each `queue step` was one drafter run of 2-3 minutes; each agent run 1.5-3 minutes.

What this shows: the chain works as built (commit threading, one drafter run per step, each item's old tests held as the guard: issue 2 and 3 drafts kept issue 1's tests required, and the issue 2 draft adjusted the old helpers as its issue asked). What it does not show: the figure "to staging without Claude" (Claude was in the middle for every gate), whether a failure stops the queue in real use (no item failed), or anything about bigger or less well-specified issues (the issues were written by Claude with exact examples, on an app whose tests the agent already knew). Independent run of the tests: not done in the Argus venv (no `fastapi`; the base commit fails the same way); the green validations are the harness's, in the `ledger_py312_up2` image.
