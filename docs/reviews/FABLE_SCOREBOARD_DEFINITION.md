> Verbatim copy of Fable's `SCOREBOARD.md` (session B4), pasted by Atha on 2026-11-11 and not edited, apart from this note. **Proposal.** Fable's covering message:
> `router/job.py` field names came from its earlier full reading (this turn it only re-checked `scripts/pilot_report.py`, `scripts/audit_run.py` and the link field in
> `router/issue.py`); `job.json` alone under-reports spend, because `stages[*].usd` is written only when a stage ends; research-job stages were not confirmed to carry `usd`;
> `pilot_report.py` works on run directories, so this scoreboard would be a new script. Claude's check against the 150 real `job.json` files on the VM is in section 12 of
> [`FABLE_REVIEW_2026-11-11.md`](FABLE_REVIEW_2026-11-11.md).

# Scoreboard from `job.json` alone

Fields as `router/job.py` writes them (3d3b078). One row per job of `kind: "code"`.

## Outcome

Read `state`, and for `APPLIED` the log entry `what == "state"`, `new == "APPLIED"`.

| Category | Rule |
|---|---|
| Applied untouched | `APPLIED`, `as_is` true |
| Applied after human change | `APPLIED`, `as_is` false |
| Applied, not compared | `APPLIED`, `as_is` null |
| Rejected | `REJECTED`; split by the entry's `old` (draft, review package, research handoff) |
| Abandoned | `ABANDONED`; split by `old` |
| Failed | `DRAFT_FAILED`, `AGENT_FAILED`, `BLOCKED`, `REVIEW_INVALID`, `RESEARCH_FAILED`, `RESEARCH_INCONCLUSIVE` |
| Open | anything else |

Pitfalls:
- `as_is` compares one commit with the patch. A fix in a later commit is invisible, and a wrong commit recorded by hand
  reads as "changed" (viewer job 021).
- "Failed" states are not terminal: a later `retry` or `redraft` moves the job.

## Money

- Per job: sum of `stages[*].usd`, every kind (draft, agent, judge, research).
- Cost per applied change: money of **all** code jobs, plus issue jobs, divided by the count of applied jobs.
- Pitfalls: `usd` is written only when a stage ends, so a stage cut off by a crash has none; the ledgers are the money
  record. Several agent stages (`a1`, `a2`, ...) and drafts all count. `max_usd` is the cap, not spend.

## Decisions per job

Count log entries with `what` in `confirmed`, `confirmed_by_flag`, `not_confirmed`, `research_ok`, `retry`, `redraft`,
plus state moves into `REJECTED`, `ABANDONED`, `APPLIED`.

Pitfalls: `approve` writes a confirmation **and** `approved`; count it once. `by` is `$USER`, so Atha and Claude look
alike; only `via: "ui"` marks the phone.

## Human wait (upper bound)

- Draft: `approval.at` minus `ended_at` of the draft stage whose `draft_sha256` equals `approval.draft_sha256`.
- Review: the `APPLIED` or `REJECTED` entry's `at` minus the last agent stage's `ended_at`.

Pitfalls: under `--yes`, `limits_shown` and `confirmed_by_flag` are written together, so that interval is zero; never use
it. Both figures include idle time: they bound waiting, not attention.

## Judge

Last stage with `kind == "judge"`: `verdict`, `findings`, `status`. Report "no judge" as its own value, never as PASS.
A stage with `status` null was cut off. Staleness needs the review package files, not `job.json`.

## Other kinds

- `kind: "issue"`: add its money to the code job named in `handoff.job`; no outcome row.
- `kind: "research"`: money only, in a separate total.

## What the script cannot know

| Unknown | Record going forward |
|---|---|
| Which jobs are re-issues of one issue | `inputs.reissue_of: <job>` at `argus code`; until then report jobs per applied change by `inputs.repo` |
| Who decided | `by` from an explicit `--by`, not `$USER` |
| Minutes of attention | one `minutes` field on approve and applied, asked or timed |
| Claude's token cost | outside the harness; logged per session |
| Spend of cut-off stages | write `usd` from the ledger at `status` time, or read the ledgers |
