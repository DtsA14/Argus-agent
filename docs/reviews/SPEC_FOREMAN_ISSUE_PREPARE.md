# SPEC_FOREMAN_ISSUE_PREPARE (F44, 2026-11-28): one tap Prepare from an `issue` proposal

Strict lane. Status: for Opus review, read-only. Builds on SPEC_FOREMAN_ISSUE_ROUTE (rev 1, live as #790) and SPEC_CHAT_MANAGER_P2B (the source of a research/PRD form). Atha 2026-11-28, trying F31 on the phone: "Cuma ada edit first".

## 1. What changes

An `issue` proposal gets the same two buttons a `prd` or `research` proposal has: **Prepare** (the form as proposed, with its source) and **Edit first** (the form filled, the source kept). Prepare only asks the server for the card of `issue_new`; the person still reads the card and confirms it. Nothing starts without the person's confirmation, as before.

1. `router/chat_actions.py`
   - `ROUTE_ACTION` gains `"issue": "issue_new"` (the foreman's menu and the actions a proposal may fill are one table).
   - `build`: the guard at the top allows `issue_new` with `source_job`/`source_turn`; for `issue_new` with a source, `manager_source` is called and the card is built by the normal `issue_new` path (call `build("issue_new", rest)` with the source fields removed, then add `source` and `source_note`), exactly as for `research_new`/`prd_new`.
   - `manager_source`: the "edited" flag also compares the repository for `issue_new` (as for `prd_new`); the refusal text becomes "the foreman proposed no research, PRD or issue job in that turn".
   - A source whose proposal route does not match the action (a `prd` proposal used to fill `issue_new`, or the other way round) is allowed and marked `edited: true`, as today for research/prd.
2. `router/chat.py`: no change expected (the audit already writes `source`, `source_job`, `source_turn`, `edited` from `card["source"]`); the test below pins it for `issue_new`.
3. `router/chat_static/app.js` (`proposalBox`): the `issue` proposal has Prepare (disabled when the proposal names no repository) and Edit first. Prepare sends `{ action: "issue_new", repo, message, source_job, source_turn }` through `prepare()`. Edit first sets `fromProposal` like the prd path, so the form's own submit carries the source (the `prepare()` filter that attaches a source to `research_new`/`prd_new` also covers `issue_new`). A repo not in the select is not guessed (the rev 1 behaviour stays).
4. `docs/CHAT_CAPABILITIES.md` is unchanged except the sentence "Usulan `issue` hanya mengisi formulir New issue; Atha yang menekan Prepare dan konfirmasi" becomes "Usulan `issue` menyiapkan kartu New issue; Atha membaca kartunya dan mengonfirmasi sendiri" (repin). `route_eval` is not rerun: the proposal's shape and the instruction do not change.

## 2. What does not change

- No new action, no new route, no new field: the server's `issue_new` checks (registered repo, `message_problem`, key, cap, daily exposure) are the same for a typed form and a proposal; the proposal's `why` never reaches the card; the foreman still cannot confirm or start anything.
- `next_steps` skips issue jobs (it reads `kind` research/prd only); the foreman is not told an issue it proposed was started (listed, not fixed here).

## 3. Tests

- `tests/test_chat_manager_proposal.py`: an `issue_new` form filled from an `issue` proposal gets the card of a typed one plus `source`/`source_note` (the card minus those equals the typed card; the same `exposure_usd`); `edited` is false when text and repo are the proposal's, true when the text or the repo changed, true when the source is a `prd` or `research` proposal; a source naming an `ask`/`none`/null turn, a missing turn, a non-session job, or a bad turn string is refused (400/404, no token); `issue_reply`, `issue_start`, `issue_abandon` and the other actions with a source are still refused ("only a research, PRD or issue form..." wording pinned); the confirm writes the audit line with `source_job`, `source_turn`, `edited`.
- `tests/test_chat_apply_reply.py:205` (`ROUTE_ACTION` pin) becomes `{"research", "prd", "issue"}` and still asserts that no `ACTIONS` of `chat_apply` are in its values.
- `tests/test_chat_manager_ui.py` + `tests/chat_ui_smoke_manager.js`: the `issue` proposal has `["Prepare", "Edit first"]`; Prepare sends exactly `{action: "issue_new", repo, message, source_job, source_turn}`; no-repo proposal has Prepare off; Edit first sets `fromProposal`; the source reaches the submit body of the form. The earlier "never prepares / never sets the source" test for `issue` (rev 1) is replaced, not weakened: the new test pins the exact bodies.
- `tests/test_chat_manager_next.py`: an `issue_new` confirm with `source_job` of the session produces no `next_steps` item and no error.

## 4. Mutants (the reviewer extends this list; run once after the review)

`ROUTE_ACTION` lacks `issue`; the build guard still refuses `issue_new`; the source is not added to the card; `edited` ignores the repo for `issue_new`; `manager_source` accepts a source from a non-session job; the audit drops `source_job` for `issue_new`; the page's Prepare sends no source / the wrong action / a repo not from the proposal; Prepare enabled without a repo; Edit first does not set `fromProposal`; `prepare()` filter without `issue_new`; the `why` of the proposal reaches the card.
