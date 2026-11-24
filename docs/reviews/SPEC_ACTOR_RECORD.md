# SPEC: record who did each decision (E2 of PENDING_PRIORITAS, 2026-11-24)

Status: **rev 1, built** (Opus review 2026-11-24: GO WITH CHANGES, applied below). Strict lane (it touches `job.json` and the approve, apply and reject paths; it changes no decision, refusal, money or key).

## Problem

The headline figure of the direction (2026-11-15), "share of issues that reach staging without Claude's intervention", is only an upper bound (23.8%): every decision is recorded with `by = $USER`, the same for Atha and for Claude (Claude Code runs the commands as the same Linux user). A job that is `hands_off` may still have had Claude approve, apply and deploy it by hand.

## Rule

One field, `actor`, written next to `by` wherever a decision is recorded. Its value is a FACT about the process, not a guess about a person:
- `"ui"` when the command was started by the chat app (`--via ui`; the chat only runs commands after Atha's own confirmation card),
- else `"claude"` when the environment of the command has `CLAUDECODE` set to a non-empty value (Claude Code sets it in every shell it runs: a command typed by Claude, or by Atha with the `!` prefix inside a Claude session),
- else `"terminal"` (a shell that is not Claude Code's: Atha at Termius, a script).

`rj.actor(via=None)` returns it; no flag, no declaration: a flag would be one more thing that Claude must remember to type and that nothing checks.

Where it is written (`actor` beside `by`; the key `actor` is added to the reserved keys of `_record_applied` so a caller cannot set it): `research_ok`, the approval record (`job.data["approval"]`), `retry`, `redraft`, `reject`, `abandon`, APPLIED (`apply` and `applied`), and the queue's `approved`, `closed` and each `retries` entry. A record written before this change has no `actor`; a reader treats it as **unknown**, never as `terminal`.

## Scoreboard

`scripts/scoreboard.py` adds, next to the upper bound and without changing it: for each code job, `actors` = the set of `actor` values of its decision records (approval, APPLIED, and the ones above). A job counts as `without_claude` only when it is `hands_off`, the approval and the APPLIED record both have an actor, and no actor is `"claude"`. The report gives `without_claude` (count and share of the jobs that have actors), `with_claude`, and `unknown_actor` (jobs whose approval or apply predates the field), and says that `unknown` jobs are in none of the first two. The old upper bound stays as it is.

## Known limits (stated in the report)

- The signal is the process's environment, not the person: Atha typing with `!` inside a Claude session reads as `claude`; a process that unsets `CLAUDECODE` reads as `terminal`. It measures "did a Claude Code session run this command", which is the quantity asked for, and does not stop deliberate evasion.
- A staging deploy (`argus stage`, `deploy`) is not covered by this change: `stage` entries carry no actor, so "to staging without Claude" still needs the deploy step to be looked at by hand until a second PR adds it.
- `via` is trusted as the chat sets it (same trust as `exposure()`).

## Money and ledger

None: no cap, price, ledger entry or reservation changes; `actor` is a string in records that already exist.

## Tests

`actor()`: ui wins over the environment; `CLAUDECODE` set gives `claude`; unset or empty gives `terminal`. Each decision site writes the field (approve, apply through `argus apply` and through `applied`, reject, abandon, retry, redraft, research_ok, queue approve and close and retry) under both environments. `_record_applied` refuses `actor` as an extra. The scoreboard: a job approved and applied under `terminal` counts `without_claude`; one with `claude` at the approval only, at the apply only, or an extra retry does not; a job with no actors is `unknown_actor` and is counted in neither; the old upper bound is unchanged for the same data.

## Rev 1: what the review changed (Opus, 2026-11-24)

- **Order of the signal:** `CLAUDECODE` is checked FIRST: a Claude shell that passes `--via ui` reads `claude`, and a chat started by hand from a Claude shell reads conservatively. The systemd chat service has a clean environment (checked on the live process), and its children inherit it.
- **The partition is defined per code job:** `with_claude` = any decision record of the job says `claude`; `unknown` = applied and the approval or the APPLIED record has no valid actor (before this field); `without_claude` = `hands_off`, applied by `argus apply` (a job applied by hand, `applied_by` unknown, is not claimed), and the approval and APPLIED records both `ui` or `terminal`; every other job (open, failed, rejected, abandoned, changed) is `other`. Any value outside `{ui, claude, terminal}` is unknown. The report gives the four counts, `without_claude_share_of_code_jobs` (denominator: all code jobs, as the upper bound) and `without_claude_and_staged`; the old upper bound is unchanged.
- **The approval actor is read from `job.data["approval"]`**; `actor` is also on the log notes `approved` and `research_ok`.
- **Limits added:** decisions upstream of the job (queue `go`, `prd approve`, `issue start`), the staging deploy, a `!` command typed by Atha inside a Claude session, and processes started with a cleaned environment (`systemd-run` as a service, `at`, cron, `sudo`).
- **Not covered, on purpose:** `prd approve` and `issue start` record no `by` at all today; a later change may add both.
