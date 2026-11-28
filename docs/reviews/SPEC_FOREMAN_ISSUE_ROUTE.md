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
