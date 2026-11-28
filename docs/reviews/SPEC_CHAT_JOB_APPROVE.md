# SPEC: `job_approve`, the draft approval of a standalone code job from the chat (F35), strict lane

Draft for Opus read-only review. 2026-11-28. Atha: "F35 lalu konteks foreman dulu" after F35 was logged (his "Di queue sama decision ga ada", "Cuma ada reject").

## Problem (observed, job j20261128_035717_0f18)
A code job born from chat "New issue" and started with `issue_start` stops at AWAITING_APPROVAL. Decisions offers only Reject and Abandon.
`draft_approve` (T4B) exists only for the next item of a queue the chat itself approved (`Steps.facts` demands a queue). The approval was made from
the terminal (`argus approve --sha ... --yes`, actor `claude`). The path "request to installed" is broken at this step.

## Change: one new action `job_approve` in the `job_` family (same family as `job_reject`, `job_abandon`)
Client sends `{action: "job_approve", job: <id>, sha: <12 hex>}` and nothing else (`sha` = the draft the person was shown, an equality check as in `job_reject`).
Everything else is read by the server at prepare and again at confirm.

### Refusals at prepare (each with its own gate word and a sentence)
1. `UI_ID` job id; the directory is not reached through a link; `rj.open_job` ok; kind is `code`; state is exactly AWAITING_APPROVAL
   (stricter than the CLI, which also takes DRAFT_FAILED).
2. **Standalone only:** the job is not an item of any queue of this jobs directory. Decided with `examples_read.chain(...)["standalone"] is True`
   (the key added by #782: only the two "not a queue item" results carry it; an unopenable queues directory does NOT, so it refuses). A queue item stays on `draft_approve`.
3. `sha` (12 hex) must equal the sha12 of the job's last DRAFTED draft read now (`_sha`), else "the draft changed since you read it".
4. The draft facts as `Steps.build_approve` has them: the last draft is not reached through a link; not already approved
   (`approval.draft_sha256 == seen`); `rj._conflict_refusal(job, draft, "approved")` is None; `rj.environment_changed` is None; the agent cap
   `min(profile cap, rj.left_usd(job))` is at least one attempt. These are moved out of `build_approve` into one helper used by both (output of
   `build_approve` byte-identical; its existing tests unchanged).
5. The spawner is not busy for this job; a key file is available (`a._need_key(False)` as T4B).
6. The daily cap check (`check_cap`) as every card.

### The card (shown on the confirm page; the client draws it, it never composes it)
`{action: "job_approve", title: "Approve the draft (the agent starts)", job, repo, item_text (the issue, scrubbed), draft_sha, draft_run, sha12,
 writable, validations, profile, agent_cap_usd, attempt_usd, flags, changed_tests..., plan/warnings/unverifiable (model text, labelled), money}` = the T4B card with
`queue/item/list_sha/approved_sha` removed. `money`: "the agent runs inside the job's own cap; no new money; the command re-checks the draft in the sandbox and the repository's HEAD; this card does not". Nothing is pushed, PR'd, merged or deployed.

### Execute
`argus --jobs-dir D approve JOB --sha FULLSHA --via ui --key-file K --yes` as a child process through the spawner keyed by the job id (as T4B). The CLI keeps its gates.
The foreman cannot trigger it (not in the foreman's route list; `ROUTE_ACTION` unchanged).

### Money
The agent spends inside `max_usd` of the job, which `issue_start` already booked in the daily cap when the job is younger than 24 hours.
`exposure_of(job_approve)` = 0 when the job id's creation time is within 24 hours, else the agent cap of the card (a job that old is no longer in the net).
The audit line at confirm carries `job`, `sha` (12) and `usd` = that exposure; `audited()` of T4B is NOT changed (it reads only `queue_step`).

### Page
- `decision_row.allowed` gains `"approve"` for a code job in AWAITING_APPROVAL that is standalone (a cheap check; prepare does all the refusals and says why).
- The Decisions card shows a button "Approve draft" (label as `Reject`/`Abandon` are built in `decideCard`), which prepares `{action: "job_approve", job, sha: r.sha12}`; the confirm card is drawn by `renderCard` with a Started text ("The agent is starting inside this job's cap. Nothing is applied yet: you will read the patch on the install card.") and the existing note under the draft: "Read the draft before you approve" with the link to the Draft page.
- No button for a queue item (still `draft_approve`), for any other kind or state.

## Not changed
`draft_approve`, `queue_step`, the CLI, the audit net, the T4B card for a queue item, `issue_start`. No retry/redraft.

## Tests / mutants
Prepare refusals one by one (kind, state, queue item, unopenable queues dir, stale sha, link, already approved, conflict, environment, money, busy, no key);
card has no queue keys; execute argv exactly; exposure inside and outside 24 h; audit line fields; the page: button only for a standalone AWAITING_APPROVAL code row; click sends job and sha only.
Mutants on each refusal, on `standalone is True`, on the sha equality, on the exposure window, on the argv, on the page conditions.
Strict lane: Opus review, mutants once, precheck, one `verify_at`. Restart of `argus-chat` after merge. Live proof: a New issue job approved from the phone.

## Rev 1 (after the Opus review, NO-GO as written, GO with these; this section wins over the text above)
1. **Money window.** Not "job id younger than 24 h". The job is *inside the booking* only when an issue job exists with `handoff.job == this job`,
   `handoff.via == "ui"` and `handoff.at >= now - DAY` (the test `_exposure_scan` uses). Then `exposure_of = 0`. Otherwise (born in the terminal, or older) it is the card's
   `agent_cap_usd`. The card carries `outside_window` (bool), so a boundary crossed between prepare and confirm changes the digest and the confirm is refused.
2. **The net.** `Steps.audited()` also reads `job_approve` `attempt=confirm` lines (same F25 rule: an invalid `usd` is a 503 refusal). The confirm audit record of
   `job_approve` carries `usd = exposure_of(card)` and `sha` (12).
3. **Execute is its own branch** in `Actions.execute` (not `Steps.execute`: it needs `rp["queue"]`). argv = `[python, ARGUS, --jobs-dir D, --queues-dir Q, approve, JOB, --sha FULLSHA, --via ui, --key-file K, --yes]`
   passed through `a.with_config(...)` (so the caps and profiles are the card's), spawn key = the job id, return `{job, started: True}`.
4. **Build routing.** `job_approve` has its own branch after `cfg = self.cfg` (it needs the config); it is NOT in the `("job_reject","job_abandon")` early return; params other than `{job, sha}` are refused (400, form). It is NOT added to `control.ACTIONS` or `allowed()` (those feed the 8711 `cli()` path with a reason); `"approve"` is added only in `decision_row`.
5. **`chain(...)` is called with `queues_dir=a.cards.queues_dir`** (its default may be another directory); a wrong directory would give a false `standalone`.
6. **Two draft reads agree:** require `seen[:12] == sha12 read by _sha` as its own check (refusal gate `draft`).
7. **Page:** the approve button has its own `prepare({action: "job_approve", job: r.id, sha: r.sha12})` (not `decide()`, which always sends `reason`); in `renderCard` the `job_approve` Started text is tested before the `card.draft_sha` branch; the issue text label says it is the issue writer's text; `item_text` is the job's frozen issue read through descriptors, scrubbed and cut.
8. **Refactor:** `build_approve`'s draft facts move into one helper (keeps `except self.Refusal: raise` before the broad except, the order of refusals, and returns `st, path, draft, seen, profile, want, cap, need, advisories, valid, writable`). A snapshot test of `build_approve`'s card is written BEFORE the move.
9. **Forgotten places:** `tests/test_chat_decide.py` "an approve is not an action at all" keeps `approve`, `job_redraft`, `job_start` as 404 (the action is `job_approve`); `tests/test_chat_ui.py` pins for `Approve`/`approve` in the JS, waiting labels, decide pins; the ACTIONS comment; `verification/chat_c4_mutants.py` "an approve action exists" mutant retired. Optional, not now: the waiting list does not show a standalone approve (Decisions does).
