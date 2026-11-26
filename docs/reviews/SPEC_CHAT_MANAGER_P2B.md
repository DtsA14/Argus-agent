# SPEC_CHAT_MANAGER_P2B: a form filled from the foreman's proposal

Status: rev 0, 2026-11-26. Parent: `SPEC_CHAT_MANAGER.md` rev 1 section 13 items 5 and 6 (binding), `SPEC_CHAT_MANAGER_P1.md`. Atha 2026-11-26: "Ok p2b". Strict lane. No page (P3 adds the button).

## 1. What it is

A proposal is data in a session (P1). P2b lets a form that a human fills from a proposal say so, and makes the server check the claim. Nothing else changes: the card, the checks, the token, the confirm and the exposure are those of a form the human typed. No code reads a proposal to start anything.

Reading of item 5 ("no proposal-specific code in prepare or confirm"): no code turns a proposal into input or reads its text, repo or `why` as a value. `manager_source` runs in `build()` (so on prepare and again on confirm, which rebuilds the card) only to check the claim of origin and compute `edited`; a session rewritten between the two is refused (404 or 409). A proposal counts as a source only when its route is `research` or `prd`.

## 2. Wire

`POST /api/prepare` for `research_new` and `prd_new` only accepts two more text fields: `source_job` (a session id) and `source_turn` (digits, 1-3). Both or neither (400). Any other action with either field: 400, no token. The two fields are in `chat.PARAMS`.

`manager_source(action, params)` (chat_actions): reads the session with `_read_data(job, ledgers=False)`; it must be kind `manager`, the turn index must be an entry of its `conversation` with `from == "manager"` and a dict `propose`; otherwise 404 `source`. The session's state and expiry do not matter (a proposal stays readable). The form's own fields (`repo`, `message`) go through the action's own checks unchanged: the proposal's text, repo and route are never read as input, only compared.

## 3. The card

`card.source = {"from": "manager", "job", "turn", "edited"}` and `card.source_note` (a fixed English sentence, the page renders its own Indonesian label:  the text was first written by the foreman, a model, read it before you confirm). `edited` is true when the route of the proposal is not the form's action, or the message differs from the proposal's text (after the same scrub and normalisation), or, for `prd_new`, the repo differs. A typed form has neither key. `why` is never in the card. The key is in the card, so the digest and the token cover it.

## 4. Audit

Prepare: `source_job`, `source_turn` (the client's strings, cut). Confirm: `source: "manager"`, `source_job`, `source_turn` (int), `edited`. No text, no `why`. `source_turn` is an int in both (-1 and `source_job` "bad" in the prepare line when the client's value is not an id or a number).

## 5. The read route

`GET /api/manager/<job>` gives each conversation entry its index `n` (its place in the stored list), which is what `source_turn` names.

## 6. Mutants (written, run once after review)

M1 `source` keys accepted for any action; M2 only one of the two keys accepted; M3 `source_turn` pattern loosened (sign, spaces, unicode digits, 4+ digits); M4 kind not checked; M5 turn index not bounded (negative via list); M6 human turn accepted as a source; M7 a foreman turn without a proposal accepted; M8 `source` left out of the card; M9 `edited` always false; M10 `edited` ignores the route; M11 ignores the text; M12 ignores the repo (prd); M13 `why` copied into the card; M14 `source_note` dropped; M15 source keys not stripped before the action's key check (a typed 400 is lost or the form fails); M16 prepare audit lacks the source; M17 confirm audit lacks the source or `edited`; M18 audit carries the text; M19 `n` missing from the read route; M20 `n` counts the filtered list instead of the stored one; M21 session state required OPEN; M22 ledgers read for the source check; M23 `enumerate` over the filtered list; M24 confirm skips `manager_source`; M25 route not limited to research/prd; M26 the source-key refusal moved after the job_ branch; M27 `edited` without normalize; M28 `edited` without scrub; M29 prepare audit writes the raw `source_job`; M30 off-by-one on the turn index; M31 kind not checked; M32 the source in the run params.

## 7. Not in P2b

P3 must not pre-fill a form from a withheld text (the "[withheld by the harness]" marker is not a proposal text). 
The button and the page (P3); next-step cards (P4); any change to confirm, the spawner, the exposure or the CLI.
