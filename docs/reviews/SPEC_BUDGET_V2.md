# SPEC_BUDGET_V2 (F47 phase B, 2026-11-28): a daily and a monthly budget of actual spend

Strict lane. Status: for Opus review, read-only. Replaces "money, not time" and the topic pool (F48) of `docs/PLAN_FOREMAN_TOPICS.md`. Atha 2026-11-28: "kayak limit claude ... daily limit dan monthly limit": calendar days and months; $1 per day, $30 per month; at the limit a spending action is refused, the foreman's turns included.

## 1. Why

Today the daily cap (`chat.daily_cap_usd` 7.00, `_exposure_scan`) books each job's MAXIMUM for 24 hours from its creation: over all jobs made through the UI $18.80 was booked and $0.82 spent (4.4%); in the last 24 hours $3.90 booked, $0.28 spent. The booking also needs a session to die before 24 hours and cannot see a job older than 2 days. A limit on actual spend (like Claude's) is truer and removes both problems.

## 2. Definitions

- **Day** and **month**: calendar, in `Asia/Jakarta` (fixed UTC+7, no DST): the day resets at 00:00 WIB, the month on the 1st at 00:00 WIB.
- **Spend** of a window: the sum of `usd_nano` of the `llm_call` events (the charged amount: the larger of the harness count and the gateway's reported cost, as the ledger already holds it) whose `ts` is in the window, over EVERY stage ledger `runs/*/events.jsonl` of the jobs directory, whoever started the job (the chat or the CLI): one wallet.
- **Not counted** (said on the meter): runs outside the jobs directory (`route-eval`, `patch-trial`, `t3b-run`, pilots, a run with another `--jobs-dir`). The provider's dashboard is the wallet's truth; the meter is the jobs directory's.
- **Unknown**: a ledger that cannot be read, a `llm_call_started` without its `llm_call` (`usd_complete` false) or an amount that is not a finite non negative number makes the window's spend UNKNOWN, never zero. Unknown refuses every spending action (fail closed) and the meter says so.

## 3. Part 1, the meters (read only; built first)

1. `router/budget.py`: `Spend` reads the ledgers incrementally: a map `ledger path -> (size, mtime_ns, {WIB date: nano})`, re-read only when size or mtime changed (a ledger is append only; a shrunk one is re-read whole); lines that are not events are ignored, a line that cannot be parsed makes the file unknown. Memory only plus an optional rebuildable cache file in the chat's own directory (no authority in it, never trusted over the ledgers). Measured on this host: 635 ledgers, 16.4 MB; a cold scan must stay under 2 s (a test with 600 synthetic ledgers), a warm one under 50 ms.
2. Config `chat.budget: {daily_usd: 1.00, monthly_usd: 30.00, warn_at: 0.8}` validated in one place (finite, positive, daily at most monthly, `warn_at` in (0, 1]); `chat.daily_cap_usd` stays in this part and is still the gate.
3. `GET /api/budget` (read only, like the other reads): `{day: {date, spent_usd, limit_usd, resets_at}, month: {...}, unknown: bool, note: "jobs directory only"}` or `unknown` with a fixed reason.
4. Page: a chip in the header ("Today $0.28 of $1.00") and a section in the Cost tab (both meters, 80% in the warning colour, text only), refreshed with the existing poll.
Part 1 gates nothing and changes no cap: it shows the truth so Atha can compare it with the dashboard before part 2 relies on it.

## 4. Part 2, the gate (after part 1 is live and the meters have been compared with the dashboard)

1. **Admission.** Every action that can spend (`issue_new`, `issue_reply`, `issue_start`, `prd_new`, `prd_reply`, `research_new`, `manager_new`, the foreman's turn, `queue_go`/`queue_step`/`draft_approve`/`job_approve`, `patch_read_run`) must satisfy, for the day AND the month: `spend + reservations + reserve(card) <= limit`. `reserve(card)` is the cap the action authorizes for the stage it starts (the existing `exposure_of` amounts, per stage, not per job). `reservations` = for every stage RUNNING now (a job state that says a stage runs, or an in flight confirm the directory does not show yet, for at most 10 minutes) its stage cap minus what it has spent. Checked at prepare and at confirm (as `check_cap` is now). A foreman turn reserves its worst case (3 calls at `turn_cap_usd`).
2. **No booking.** `_exposure_scan` and its audit nets are removed from the gate (the 24 hour windows and the "created via the UI" log scans go; so does the 2 day name break). Actions that cost nothing (`prd_approve`, `code_apply`, `job_reject`, `job_abandon`) are never refused by the budget.
3. **Refusals** are one fixed sentence each: "the daily budget would be passed ($0.92 of $1.00 spent, this needs up to $0.15; it resets at 00:00 WIB)" and the monthly one; unknown: "the spend cannot be computed (reason)".
4. **Strict means the caps must fit the budget.** A guarantee that the day never passes $1 needs every stage cap far under $1. Observed maxima: writer job $0.023, draft $0.069, agent $0.125, readers about $0.01, research $0.105, a PRD turn $0.036. Proposed (Atha confirms, config only): `issue_writer.max_usd` 0.50 to 0.15, `issue_writer.turn.cap_usd` 0.10 to 0.05, `code_max_usd` 1.00 to 0.40, the patch readers' cap 0.20 to 0.08, research 1.00 to 0.30, PRD 1.50 to 0.30; the foreman's $0.20 session and $0.03 turn stay. The check that a stage cap cannot pass the job's remaining cap already exists; a test pins that no configured cap exceeds the daily limit.
5. **The foreman session** keeps its own cap ($0.20, one confirmation); its turns are admitted one by one against the budget (item 1), so its age no longer matters for money: `ttl_hours` is replaced by an idle limit (`idle_days`, default 7: a session with no turn for that long is BLOCKED), and the 23 hour wall of `settings` goes. Opening a new session when one ends is the topic work (phase C).
6. Removing `chat.daily_cap_usd`: the key is refused as unknown once part 2 lands; `waiting()`'s "capped" and "cap unknown" notes now speak of the budget.

## 5. Tests (deterministic)

Part 1: window edges at 00:00 WIB (an event at 16:59:59Z and at 17:00:00Z belong to different days; month edges, a leap day); a ledger with a call in two days; incremental re-read after an append; a shrunk ledger; unknown on a half written line, a started call without its end, a negative or NaN amount, an unreadable file; CLI and chat jobs both counted; the route and the chip text; warn colour at exactly `warn_at`; config validation; the 600 ledger timing bounds. Part 2: each action admitted at `limit - reserve` and refused one nano above, day and month separately; a running stage reserves its remaining cap and releases it when it ends; an in flight confirm reserves for 10 minutes only; unknown refuses spending actions and never the free ones; the foreman's turn refused at the limit with its fixed sentence; a stage cap above the daily limit is refused at config load; the removed key; reset times in the sentences.

## 6. Mutants (the reviewer extends; run once after the review)

A day boundary in UTC instead of WIB; month off by one; `ts` read as milliseconds; a started call counted as zero; unknown counted as zero; the cache not invalidated on append; a shrunk ledger not re-read; CLI jobs left out; the month meter showing the day; `warn_at` off by one; (part 2) admission with `<` instead of `<=`; the month not checked; reservations not released; a free action refused; the confirm check dropped; the foreman's turn exempt; the in flight reservation never expiring; the old exposure still consulted.

## 7. Not in this spec

Topics and continuing a topic (C), steps in the chat (D, E), the foreman's auto approval of a clean draft, and a pool of money per topic (not needed: the budget is the one door).
