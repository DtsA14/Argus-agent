# SPEC_CHAT_UI3B — the Decisions tab shows what waits for the person; the Queue tab shows progress (rev 1)

Origin: SPEC_CHAT_UI3 phase 3b (Atha 2026-11-25, "sambil kerjain 3b"). The Decisions badge showed 9+ jobs that could only be rejected or
abandoned (old REVIEW_READY jobs, since cleared); it did not show what the mockup promises: the approvals that wait.

## 1. `GET /api/waiting` (read only, chat actions required)
`Actions.waiting()` returns `{"waiting": [row], "scanned": n, "skipped": n, "capped": bool}`; a row is
`{"action": "prd_approve"|"queue_go"|"queue_step"|"draft_approve", "id": <PRD job id or queue id>, "repo": str|null, "title": str|null, "item": int|null}`.
- Candidates come from `Cards.listing()` rows (already bounded and scrubbed): a `prd` row whose state is waiting for the human, and a `queue` row
  whose derived state is not DONE, CLOSED, PENDING-without-approval or empty. At most WAIT_SCAN_MAX (12) candidates are evaluated per request;
  more: `capped: true`.
- A candidate is a row only when the SAME builders the buttons use say a button is offered now: `plans.state(job)` (its `action`) and
  `steps.state(queue)` (its `action` and `item`). Those functions never raise and already include the daily cap and the 24-hour rule (K4):
  nothing is offered here that prepare would refuse. A candidate whose builder says no action is not listed (no reason text is sent).
- Any exception on one candidate counts it in `skipped`; the route never answers 500 for a hostile file.
- No new action, no write, no key, no money. The text is `title` and `repo` from the listing rows (scrubbed there); the label of each action is fixed in the page.

## 2. The Decisions tab
Top section "Waiting for you": one card per row, the label of the action (Approve the plan / Start the queue (money) / Start issue N (drafter) /
Approve the draft of issue N), the repo and the title (text nodes). A tap opens the existing card in the Queue tab (`showPlan` for PRD rows,
`showCard("queue", id)` for queue rows): the button, the sha binding, the confirm and the cap are the existing ones, unchanged.
Below it, "Open jobs": the existing list of jobs that can be rejected or abandoned, only when it has rows.
The badge and the header line count waiting rows plus open jobs, and say so: `aria-label` "N items waiting for you".
The background poll refreshes the rows and the badge only (never redraws a page that holds a reason being typed, like UI-3a).

## 3. The Queue tab: progress (page only, existing endpoints)
Each queue row that is not CLOSED shows a progress bar and "k of n applied" from `/api/cards/queue/<id>` (items' `applied`), for the six newest such
queues, one request at a time; failure shows the row without a bar. A bar only counts items whose card says `applied`; it never claims running or
failed items are done.

## Risks to review
- Cost of `waiting()` on a single-threaded server: at most 12 candidates, each `steps.state`/`plans.state` reads job files and the daily exposure.
- A hostile queue or job file must give "skipped", never 500 or a stalled loop; the response must not carry paths or reasons.
- The badge must not call something an approval that the builders refuse; and must not hide the "open jobs" count.
- Tests lock JS lines and `STATIC_SHA256`; the node smoke tests move.

## Rev 1: Opus review (GO WITH CHANGES), amendments taken
1. States named: a PRD candidate is `AWAITING_HUMAN`; a queue candidate has derived state `WAITING`. `queue_go` belongs to a PRD row (id = the PRD job).
2. Cheap filter: a PRD job whose queue is WAITING, STOPPED or DONE is not a candidate (its plan has no button); the newest candidates first; the builders stay the final word.
3. The exposure is computed once per request (`_exposure_once`, set and cleared in `finally` inside `waiting()`); `exposure()` returns it only then, so prepare and confirm never see a remembered value. An exposure failure is `cap_unknown: true`, and no money row is listed.
4. Budget: WAIT_SCAN_MAX 12 candidates, WAIT_BUDGET_S 2 s; either gives `capped: true`. A long listing (older rows) is not a reason to warn. An unreadable listing is `capped: true`, never "nothing waits". Measured on the real jobs: first answer 0.27 s, kept answer 0.00 s.
5. The answer is kept 20 s and cleared by every confirm.
6. Rows carry `card` ("plan" or "queue": which card the tap opens, from the kind of candidate, not from the action) and, for draft rows, `job` (the code job): the badge and the header count a draft's job once. No `why` is copied.
7. A tap does `setMode("cards")` and then `showPlan(id)` or `showCard("queue", id)` by `card`.
8. One `renderDecisions` draws both sections after both fetches resolve (sequence number); the background poll never redraws (UI-3a rule).
9. The labels are fixed strings in the page without the word approve, pinned by a test; the header count and the badge are the same number.
10. Progress: no extra requests: the queue rows of `/api/cards` carry `applied_n` (from `_derive`); the bar counts only items whose card shows a commit.
