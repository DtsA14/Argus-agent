# SPEC: `queue retry` after a failed agent, and a PRD turn that a provider failure no longer kills (2026-11-24)

Status: **rev 2, built** (Opus review 2026-11-24: GO WITH CHANGES, applied below). Items H3 and C24 of `PENDING_PRIORITAS.md` (Atha 2026-11-24: "h3 dan c24"). Strict lane (queue state transitions; a job state for the PRD writer).

## H3: `argus queue retry` also for an item whose job is `AGENT_FAILED`

Problem (NEXUS-lite, twice; ledger-cli, once): when an item's agent fails, the queue STOPS and the way to try the issue again is five commands (`queue close`, `prd reply`, approve the PRD and the money, `queue go`, `queue step`). `queue retry --item N` exists only for a `REJECTED` job whose patch readers raised blockers.

Rule. `rq.retry` accepts, in addition to today's case, an item whose job is `AGENT_FAILED` and is the item the queue stopped at. Everything else in `retry` is unchanged and applies equally: queue not closed, approved and unchanged list, the queue's own jobs directory, the stopped item, at most `MAX_RETRIES` (2) retries **per item, counted across both kinds**, the old job stays as it is, what it spent is recorded in `retries[].spent_nano` and stays counted in the queue's money, the next `step` starts the new job and it must fit the money left.
- **No findings are handed over.** For `AGENT_FAILED` there is no reader note, so the retry record has `findings: ""` and the item's `retry_note` is set to `None` (an older retry's reader note is **not** carried to a different failure). The new drafter gets the issue text byte for byte and nothing else; no model text enters a prompt that was not there before.
- The check "rejected on a concerns" stays for `REJECTED` (a rejected job with no findings is still refused: "nothing to hand to a new drafter").
- `derive` (the STOPPED hint) offers `argus queue retry <q> --item N` for `AGENT_FAILED` too, while retries are left. CLI help and the module docstring say so.
- `_retries_ok` already accepts `findings: ""` (a str); no shape change. A `retry_note` that is `None` is already valid.

Not changed: other failed states (`DRAFT_FAILED`, `BLOCKED`, `REVIEW_INVALID`, `ABANDONED`, research states) still go through the PRD; a job-level `argus redraft --note` (#702) is unchanged; no new command.

## C24: a provider failure in a PRD turn is `WRITE_FAILED`, not `BLOCKED`

Problem: in `codetask/prd_writer.py` an attempt that ends `llm_failed` returns `BLOCKED`; `router/prd_job.py` then moves the job to `BLOCKED`, which has no way out (`LEGAL` has no edge from it). A provider hiccup (HTTP 402, 429, 5xx) kills the conversation and what it already paid.

Rule. In `run_prd_writer` an `llm_failed` attempt returns `status: FAILED` with the same `stop_reason` (`provider_failure_reason(http_status)`, unchanged). `run_prd_job` already moves any non-`WRITTEN`, non-`BLOCKED` status to `WRITE_FAILED` (a state `reply` accepts: `REPLYABLE`). `BLOCKED` stays for what it means: money (reservation or caps), the state of the repository, the snapshot copy, sandbox. The `LEGAL` table, the money rules and the ledger entries are unchanged: a failed call is booked as before (worst case, or `$0` for a gateway 401/402/429).

Not changed: `codetask/issue_writer.py` has the same mapping for the `issue` job (out of scope; a separate item if wanted).

## Money

No cap, price, profile or ledger change. H3: the retried attempt's spend is recorded and counted as for a `REJECTED` retry (`spent_nano`), so `left_usd` and the daily cap see it. C24: unchanged accounting; a `reply` after `WRITE_FAILED` is a normal paid turn under the job's own cap.

## Tests

H3 (in `tests/test_queue.py`): an `AGENT_FAILED` item is retried (a new job on the next `step`, same issue byte for byte, the old job untouched, spend recorded); no note reaches the new drafter (`calls[-1]` has no `note`), including after an earlier `REJECTED` retry (the old `retry_note` is cleared); the two retries are shared across both kinds (a third is refused with "retried 2 times"); other failed states and other items are still refused; the STOPPED hint shows for `AGENT_FAILED` and disappears after the second retry; a tampered `queue.json` is still "damaged". C24 (in the PRD writer and PRD job tests): an attempt ending `llm_failed` gives `FAILED` with the provider reason; the job ends `WRITE_FAILED`, not `BLOCKED`; `reply` is accepted from it and runs a turn; an attempt ending for money still ends `BLOCKED`.

## Rev 2: what the review changed (Opus, 2026-11-24, GO WITH CHANGES)

- **H3, HIGH: the old job is ABANDONED by the retry.** A REJECTED job can only be judged afterwards (at most $0.30), but an `AGENT_FAILED` job can still be moved on (`retry`, `redraft --note`, `resume`), so the queue would hold only what it had spent while the old job spent its whole cap again outside the queue (two jobs per item at most) or reached `REVIEW_READY` beside the new one. `retry` now takes the old job's lock through `rj.abandon` as the last check before it changes the item (a busy job refuses the whole retry, `JobBusy`; `step` already abandons under the queue lock, same lock order). An ABANDONED job is in `SPENT_ONLY`, so the queue counts what it spent and nothing more. The spec's earlier sentence "the old job stays as it is" holds only for REJECTED.
- **H3, MEDIUM: not retried when a new job would fail the same way.** Refused (with the reason named) after a confirmed `BLOCKED/test_conflict` and after `BLOCKED/sandbox_unavailable`, as the job-level `retry` refuses a confirmed conflict. Other failures (`max_iterations`, stagnation, `provider_failed`, `test_detection`) are retried: a new draft is a new chance, and the bound is two retries per item and the queue's money.
- **H3, MEDIUM: the chat card** (`router/cards.py` `_stopped_hint`) offers `argus queue retry` for `AGENT_FAILED` with its own wording (no "temuan pembaca"), and says "Retry habis" after the second retry. Display only.
- **H3, LOW:** the derive hint, the module docstring, the `retry` and `retired_nano` docstrings and the CLI help say what an `AGENT_FAILED` retry does. A human note left on the old job (an earlier `redraft --note`) does not reach the new job: the new drafter gets the issue alone, as stated above.
- **C24:** no change to the rule; the `prd_job.py` docstring now says a provider failure is `WRITE_FAILED`. Checked by the review: a reply after `WRITE_FAILED` is a new stage `w<n+1>` with a new run id (no committed result is bought twice); `run_stage` treats `FAILED` and `BLOCKED` the same on resume; nothing in router, chat or tests depends on `BLOCKED` for `llm_failed`.

Tests added: `tests/test_queue.py` (7 + 2 parametrised: the retry with the issue alone and the old job abandoned, the old job cannot be moved on, a held job refuses and nothing changes, an old reader note is not carried over, the two retries shared by both kinds, test_conflict and sandbox_unavailable refused, other states and items refused, the abandoned job's spend stays counted); `tests/test_chat_cards.py` (AGENT_FAILED hint, retries exhausted); `tests/test_prd_writer.py` (provider failure is `WRITE_FAILED` and a reply continues, stage status and reason, an unfunded turn is still `BLOCKED`).
