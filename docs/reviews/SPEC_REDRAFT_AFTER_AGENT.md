# SPEC: redraft after an agent that failed or was stopped (2026-11-23)

Status: **built, for review.** Item 4 of `PENDING_PRIORITAS.md`. Strict lane (it changes which job states may start a new drafter and closes an agent stage).

## Problem (NEXUS-lite stage 3, 2026-11-22)

1. A human stopped an agent that was running tests that could not pass. The job stayed `AGENT_RUNNING` with no process; `redraft` refused ("only a failed or unapproved draft is redrafted"); the only ways out were `resume` (run the agent to its end: +14 minutes, +$0.07) or `abandon` (lose the job and rebuild the queue: about 12 minutes).
2. After an agent that failed for any reason other than "the draft's own tests cannot pass" (A', #689), `redraft` was refused, so a human who saw the draft was wrong (`max_iterations`, stagnation) had `retry` (the same draft again) or `abandon`.

## Rule

`redraft JOB --note "<what the draft got wrong>"` is accepted, in addition to today's states, when:
- **the job is `AGENT_FAILED`** and the last agent run did not end `BLOCKED/test_conflict` (a conflict with OLD tests that the harness confirmed: the draft is not the problem; the ways out are `abandon` with a new job naming the file(s), or `retry --not-a-conflict`) and its `stop_reason` does not start with `test_detection` (the agent's code recognises tests; a new draft does not change that). A note of the human's own is **required**. After a `draft_test_conflict` (A') nothing changes: the harness facts go in, the note stays optional.
- **the job is `AGENT_RUNNING` and nothing holds the job**: `redraft` takes the job lock (refused at once, `JobBusy`, when a live process holds it), so an acquired lock means the agent process is gone. A note is **required** (the human says why). The agent stage is closed first: `status: INTERRUPTED`, `ended_at`, `usd` from its ledger (cut-off calls at their worst case, as `spent_nano` counts them), and the job moves `AGENT_RUNNING -> AGENT_FAILED -> DRAFTING` (both moves already legal). `resume` is unchanged and still continues the agent.

Everything after the checks is the existing redraft: the note is told to the drafter as the reviewer's note, the job is marked human-steered, the new draft needs a new approval (agent stage `a<n+1>`, a draft identical to the approved one is refused).

`status` for an `AGENT_FAILED` job offers `redraft --note "<what the draft got wrong>"` between `retry` and `abandon` unless the refusal above applies.

## Money

The job total is `spent_nano`, read from every stage's run ledger regardless of the stage's status, so a stopped agent's spend stays in the job total and in `left_usd`. The stage's own `usd` field is filled from the same ledger so that `status` and `list` show it. No cap, price or profile changes.

## Unchanged on purpose

The `report_conflict` second attempt for an UNCONFIRMED conflict about OLD tests still runs (the harness's check is fed back to the agent, and nothing measured shows that attempt wasted); `BLOCKED/test_conflict` and the `draft_test_conflict` stop are as before; no new command (`argus stop` would have to signal a running process; out of scope).

## Tests

`tests/test_redraft_after_agent.py` (12; 9 fail on the old code): redraft after a failed agent with a note; without a note refused; refused after BLOCKED/test_conflict and after test_detection with or without a note; allowed when no result is on disk; status offers it only for plain failures; a stopped agent redrafted with a note (stage INTERRUPTED, ended_at, usd, both moves logged, human-steered); the spend of an interrupted stage stays in the job total; refused without a note naming `resume`; refused under a live holder (`JobBusy`); other states keep a refusal. Two old tests that pinned the old wording were updated (`test_router.py`, `test_report_conflict.py`).

## Rev 2: what the review changed (Opus, 2026-11-23, GO-WITH-FIXES)

- **A stopped stage whose run already finished is not redrafted.** `run_code_task` writes `result.json` before `_agent` saves the stage, and the review package is built while the job is still `AGENT_RUNNING`; a kill in that window leaves a paid result, maybe a valid patch. When a result is on disk, `redraft` refuses and names `argus resume` (which records it). The interrupted branch therefore only runs for a run with no result (killed mid-run).
- **The stage is closed after the human confirmed**, inside `_draft` through a `before_move` callback just before the job moves to `DRAFTING`: a declined `[y/N]`, a wrong key file or a budget stop leaves the job `AGENT_RUNNING` with `resume` possible. The `redraft` log entry stays before the confirmation as for every redraft.
- **Integrity stops are never redrafted:** `blocked_reason` `contract_changed` and `invalid_contract` (the frozen contract or the input repository changed) join `test_conflict` and `test_detection`. Infrastructure stops (`sandbox_unavailable`, `provider_failed`) may be redrafted with a note, but `status` does not suggest it (a new draft fixes nothing there).
- **No `result.json` does not mean "allowed":** the job's own log reason (`test_detection...`, "the harness confirmed its shape") decides when the file is missing or damaged.
- **`status` after a killed stage** (INTERRUPTED, no result) offers `redraft --note` and `abandon` only: `retry` would be refused (`carry_from` needs a result).
- **Money:** the confirmation screen of a redraft after an agent warns when the job cap left after the drafter's cap is less than one more agent attempt (shown, not enforced: the drafter rarely spends its cap, and a refusal would block cheap redrafts). The stopped stage's `usd` is its ledger, and the job total counts it exactly once (a test compares the total before and after).
- **Containers:** the interrupted branch removes the leftover sandbox containers of the stopped run (`remove_labeled`, as `resume` does; skipped when `deps.validate` is injected, so not covered by a test).
