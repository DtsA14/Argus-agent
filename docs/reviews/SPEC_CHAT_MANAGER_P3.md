# SPEC_CHAT_MANAGER_P3: the foreman on the chat page

Status: rev 0, 2026-11-26. Parent: `SPEC_CHAT_MANAGER.md` rev 1 section 13 (binding), `SPEC_CHAT_MANAGER_P1.md`, `SPEC_CHAT_MANAGER_P2B.md`. Atha 2026-11-26: "Gass bro". Strict lane (the page is pinned, and it holds the one new POST path). Presentation of data the server already gives; no server route or rule changes except the three pins.

## 1. What it is

The "+" menu gets "Foreman". In that mode the Chat tab shows the one OPEN foreman session (found in `/api/threads`: kind `manager`, state OPEN; read with `GET /api/manager/<job>`), or a card with the button "Prepare a session" when there is none. The card is `prepare({action: "manager_new"})`, shown and confirmed like every card (it now also shows the session's lifetime, turn limit, and what the one confirmation covers); after Confirm the page looks for the new session every 2 s, at most 12 times.

## 2. The conversation

One card: state, budget left (`max_usd - spent_usd`, "unknown" when either is not a number), time left (`expires_in_s`), then the turns as text: the human's as "You: ...", the foreman's as a `say` line labelled "foreman (a model, not Argus)" with a left rule; a failed turn shows "This turn failed". Every string is a text node (no HTML sink). The box sends a turn: `post("/api/manager/turn", {session, message})` (exact keys, nothing else), only into an OPEN, idle session with a non-empty message; the textarea is limited to 2000; a refused turn keeps what was typed; after a send the page reads the session every 2 s until the answer is in (at most 2 minutes), and on the 30 s poll otherwise.

## 3. Proposals

Under a foreman turn with `propose`: route `research` or `prd` gets a dashed box: the route, the repo (prd), the text, the reason labelled "written by the model" (the reason is shown here and never on a card, 13.6), the line "Nothing is started", and two buttons. "Prepare" sends `prepare({action, [repo], message, source_job, source_turn})` (P2b) with the proposal's own text; it is off when a PRD proposal names no repo. "Edit first" opens the research or PRD form (`setMode`), fills text (and repo), and remembers the source in `fromProposal`; the form's `prepare` adds `source_job`/`source_turn` only for `research_new` and `prd_new` and only while `fromProposal` is set; every `setMode` clears it. `ask` shows "waiting for your answer", `none` "no route". The Confirm card of a form from a proposal shows "Started from: the foreman's proposal, as written / edited by you" and the server's `source_note`. Nothing from a proposal reaches `/api/confirm` or a token: the buttons only call `prepare`.

## 4. Pins and locks changed (deliberate)

`STATIC_SHA256` (all three files); `test_chat_ui`: the posted paths are now `/api/confirm`, `/api/manager/turn`, `/api/prepare`; `JS.count("action:")` 11 to 15 (manager_new twice, and the two proposal buttons); the research `prepare` literals list gains the proposal's. Unchanged and still locked: one `href`, no `.focus(`, no `innerHTML`, one `Confirm`, the confirm body `{ token: prep.token }`.

## 4b. Amendments from the Opus review (2026-11-26, GO WITH CHANGES; taken)

The server leaves an expired or used-up session OPEN and refuses its turns, so the page offers "Prepare a new session" when `expires_in_s` is 0, when what is left is below the turn limit, when the turns are used up, or after the server refused a turn; for that the read route also gives `turn_cap_usd` and `max_turns`. `fromProposal` is cleared after the confirm of the form it filled (and by every `setMode`); a turn answered after the person left the mode draws nothing, clears nothing and starts no poll (an epoch that only `mgrStop` moves); a second send while one is in flight is refused (`mgr.sending`); the retry timer is replaced, not stacked; the "Started" and "Status unknown" texts have a foreman branch; a route other than research or prd gets no button.

## 5. Tests and mutants

Static tests and node smoke tests of the page's own functions (`tests/test_chat_manager_ui.py`, `tests/chat_ui_smoke_manager.js`); a real-browser look at 390 px with no console error (not a test). Mutants (written, run once after review): M1 the turn body gets an extra key; M2 a turn sent into a non-OPEN session; M3 into a busy one; M4 an empty message sent; M5 a refused turn clears the box; M6 a proposal button posts to confirm or to the turn route; M7 `source_turn` not stringified or `source_job` missing; M8 the source added to every action; M9 `fromProposal` not cleared by `setMode`; M10 `why` dropped from the box or put on the card; M11 the label "a model, not Argus" dropped; M12 PRD Prepare enabled without a repo; M13 `Edit first` does not set the source; M14 the foreman mode missing from `setChrome` (box hidden); M15 `message.maxLength` not set; M16 the poll never stops; M17 ask/none routes get a Prepare button; M18 the budget shown as `max_usd` only; M19 the "Started from" fact dropped; M20 the 2 s session search unbounded; M21 `fromProposal` kept after a confirm; M22 no new-session offer for an expired or used-up session; M23 a turn answered after leaving the mode clears the box or polls; M24 no in-flight guard; M25 no session search after Confirm; M26 `mgr.expect` not decremented; M27 the poll stops one answer early; M28 the manager mode missing from `setChrome`; M29 `maxLength` 6000; M30 an unknown route gets a button; M31 the Started note says "issue list"; M32 `loadManager` without the seq check.

## 6. Not in P3

The next-step card and job-state hints (P4); resuming an ended or expired session (a new session is a new confirmation); showing earlier sessions; Indonesian text (F23b); the page's own "Hasil" tab.
