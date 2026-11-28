# SPEC_FOREMAN_ISSUE_ROUTE (F31, 2026-11-28): the foreman can propose `issue`

Strict lane (the capability sheet is pinned and the route menu is the foreman's whole authority). Status: for Opus review, read-only.

## 1. Why

In the chat the foreman proposes `research`, `prd`, `ask` or `none`. A change that is ONE concrete thing on ONE registered repository (the 2026-11-28 test: "add `--month` to `report`") needs no PRD with a queue and steps: it is one issue, then one code job. Today the person must leave the foreman, open `+`, choose New issue, retype the text. F31 (Atha 2026-11-27): the foreman should lead there.

## 2. What changes (and what does not)

The foreman proposes, never starts. A proposal of route `issue` is a fill-in: the person taps "Edit first", the New issue form opens with the repository and the text filled, the person edits and taps the form's own Prepare, reads the card, confirms. Nothing in the server's start path changes.

1. `router/manager_route.py`
   - `ROUTES = ("research", "prd", "issue", "ask", "none")`.
   - `ISSUE_TEXT = (20, 4000)` (the writer's `message_max` is 4000, config `issue_writer.message_max`).
   - `proposal_problems`: route `issue` needs a registered repo and a text of `ISSUE_TEXT` characters (same shape as `prd`).
   - `INSTRUCTION`: the JSON shape lists "issue"; the rule: "issue" is ONE change that can be named in a few sentences on one registered repository; two or more separate changes, a feature with several parts, or a request that wants planning is "prd"; if the repository is unclear, "ask". The text is the request as the person would write it to the issue writer (a wish and its rules, not code).
2. `docs/CHAT_CAPABILITIES.md` rev 1: the route `issue` (one repository, 20 to 4000 characters, the writer asks questions and writes the issue, then the person starts one code job; typical cost $0.02 to $0.30 per issue and code job together, job cap $1.00), the rule that separates it from `prd`, and "apply/approve stay with the person". `SHEET_SHA256` repinned (`scripts/repin.py`).
3. `router/route_eval.py` + `pilots/route_eval_v0/cases.json` (rev 1, cases added, none removed): `judge` checks the expected repository for `issue` as for `prd`. New cases (accept lists in brackets):
   - c16 one small change on a registered repo [issue], c17 another on a different repo [issue],
   - c18 three separate changes in one message [prd], c19 an issue-sized request on an unregistered repo [none, ask],
   - c20 an injection inside `context` asking to propose `issue` on `argus-agent` [none, ask, chat; forbid argus-agent],
   - c01 (small button) accepts [prd, issue].
   Pass rule as K3: every case right in all 3 rounds with the manager's model (19 more calls than before is under $0.05).
4. Page (`router/chat_static/app.js`, `proposalBox`): route `issue` shows "The foreman proposes: an issue", repo, text, reason (as now, labelled model text); one button, "Edit first": `setMode("issue")`, `message.value = p.text`, `repoSel.value = p.repo`. No one-tap Prepare and no `source_job` for issue (that needs a server change to `issue_new`; non-goal here). The note under it says what the button does. `ask`/`none` unchanged.
5. `router/chat_actions.py`: `ROUTE_ACTION` is NOT extended: an `issue` proposal can never be a `source` of `research_new`/`prd_new` (line 864 refuses a route not in it; the refusal text is unchanged). `read_manager` already passes `route` through unchanged; the page must not rely on it being in `ROUTE_ACTION`.

## 3. Refusals and limits

- A proposal `issue` with an unregistered repo, a text outside 20..4000, or `repo: null` is not a card: `proposal_problems` returns the reason (as `prd`); the turn is stored with `propose: null` and the fixed say, exactly as for a bad `prd` today.
- The foreman still cannot approve, apply, merge, spend, or start: the proposal is data in the job file; the page's button only fills a form.
- Text from `context` stays data (the frame tags are inert as before); c20 is the evidence the instruction holds.

## 4. Tests (all deterministic, no model)

- `tests/test_manager_route.py`: `issue` parses; `proposal_problems` for registered/unregistered/null repo and text 19/20/4000/4001; the sheet pin matches the file; the instruction mentions `issue` and the prd boundary; a proposal with route `"Issue"` or `"issue "` is refused.
- `tests/test_route_eval.py`: `judge` for the new cases (repo expectation on `issue`, forbid list, accept list); case ids unique and every `accept` value in `ROUTES + chat`; 3 rounds scoring unchanged.
- `tests/test_manager_job.py`: a fake model replying with an `issue` proposal is stored; a bad one is stored as `propose: null` with the fixed say.
- `tests/chat_ui_smoke_manager.js` (+ `test_chat_ui*.py` pins): `proposalBox` for `issue` has exactly one button, "Edit first", no Prepare; its click sets mode issue, text and repo; `ask`/`none`/`research`/`prd` render as before.
- `tests/test_chat_manager*`: an `issue_new` or any prepare with `source_job` naming an `issue` proposal is refused (`ROUTE_ACTION`).

## 5. Mutants (written by the reviewer, run once after the review)

`issue` missing from `ROUTES`; `proposal_problems` skips the repo or the text bound; bound off by one; `ISSUE_TEXT` = prd's; `ROUTE_ACTION` gains `issue`; page gives `issue` a Prepare button or sends `source_job`; page fills only the text or only the repo; `judge` skips the repo check for `issue`; the sheet pin not updated; the instruction without the prd boundary.

## 6. Measured before it is on

`route_eval` run live (not by tests): 19 cases x 3 rounds with the manager's model, passing the K3 rule; the run's cost and the per-case table go in `pilots/route_eval_v0/RESULT.md`. A failed case changes the instruction or the sheet, never the case.

## 7. Not done here (listed, not forgotten)

One-tap Prepare from an `issue` proposal and its "Started from the foreman's proposal" label (server: `issue_new` source). Hiding New issue from the `+` menu (only after the route is proven in use). Foreman session notes/memory (F31 rest).

## Rev 1 (2026-11-28, after the Opus review: NO-GO on six spec errors, no redesign). This section wins over the text above.

1. **Cases.** 20 cases after c16-c20 (not 19). c01 and c02 accept [prd, issue]: both are one change with rules on one registered repo. Changing an accept list is allowed in rev 1 (as for c01); a case is never removed, and a failed case still changes the instruction or the sheet, not the case. c12 is read again for the same reason: its accept stays [none] (the key trap).
2. **c20** (injection): its `context` is a README of a registered repo (bulking-app) that asks for an `issue` on another registered repo (athena); it forbids athena. A second case c21 keeps the unregistered `argus-agent` variant. So 21 cases, 63 calls in a full run (about 18 more than before).
3. **Sheet rev 1** rewrites three places, not one: heading "Repo terdaftar" (the destination of `prd` and `issue`), the `prd` bullet and rule 2 ("a code change that can be named: ONE change on one repo is `issue`, several or one that needs planning is `prd`"). Cost line of `issue`: "penulis issue cap $0,50 + job kode cap $1,00, masing-masing dikonfirmasi sendiri".
4. **Live run:** `--cap-usd 0.30` (the default, 63 calls on the manager's model stay under it), model key `deepseek`, output cap as in `route_eval.run`.
5. **Raw text.** For route `issue`, `proposal_problems` also runs `iw.text_problem(raw_text, "text", ISSUE_TEXT[1])` on the RAW text (not stripped; refuses U+2028/2029, controls). The page fills `p.text` as it is. A proposal that passes here cannot be refused by the writer's own text check at Prepare. A test pins `ISSUE_TEXT[1] <= issue_writer.message_max` from the config. A bad `issue` proposal costs a second paid call, as a bad `prd` does today (`CALLS_PER_TURN`).
6. **Repo fill.** "Edit first" sets `repoSel.value` only if an option with that value exists; otherwise it leaves the repository unchosen and shows the line "the proposed repository X is not in the list" (text from the page, X shown as text).
7. **Guards named right.** An `issue_new` with `source_job`/`source_turn` is refused at `chat_actions.py` `build` (line 470, "only a research or PRD job..."); `ROUTE_ACTION` (line 62, 864) is the check for `research_new`/`prd_new` sources and is not extended (pinned by `tests/test_chat_apply_reply.py`). The page attaches the source only at `app.js:440` for research/prd; the `issue` "Edit first" does NOT set `fromProposal`. The smoke test submits the filled form and asserts the `issue_new` body has no `source_job` or `source_turn`.
8. **INSTRUCTION** names `issue` in the JSON shape, in the text clause ("for issue the request, for prd the request, else empty") and in the repo clause (issue needs a registered repository). Tests assert the phrases "ONE change", "several" and "prd".
9. **Pins:** `scripts/repin.py` for `SHEET_SHA256` and `STATIC_SHA256`. §7 adds: an issue started from the form is not linked to the session, so it is not in `next_steps` and the foreman may propose it again.
10. **Mutants** (replace §5): `issue` out of `ROUTES`; repo check dropped for issue; `lo < len`; `< hi`; `ISSUE_TEXT = RESEARCH_TEXT` (needs the 4000-char case); stripped instead of raw text; `ROUTE_ACTION` gains `issue`; `chat_actions.py:470` allows `issue_new` with a source; page sets `fromProposal` for issue AND line 440 drops its action filter; page gives `issue` a Prepare button; page fills only text or only repo; `judge` repo check stays prd-only; `judge` forbid check removed; sheet changed without repin; INSTRUCTION without the prd boundary phrases. (`ISSUE_TEXT = PRD_TEXT` is equivalent: both (20, 4000); not a mutant.)
