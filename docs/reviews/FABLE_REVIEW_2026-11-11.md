# Fable's independent review of Argus (2026-11-11): findings and what we did about them

Two read-only Fable sessions ran from `docs/reviews/BRIEF_ARCH_REVIEW_2026-11-11.md` (direction) and a follow-up prompt (four code files).
**Claude has only the sessions' written summaries**, pasted by Atha, not the full `ARCH_REVIEW.md` and `FOLLOWUP.md` (they stayed in
the Fable sessions' scratchpads). Anything below marked *summary only* is as Fable reported it and not re-read by Claude. If Atha
pastes the full files, add them under `docs/reviews/` and reconcile this list with them.

Status key: **verified** = Claude checked it against the repository on 2026-11-11 · **partly** · **unverified** · **by design** = true,
and a documented decision.

## 1. Session 1: direction (`ARCH_REVIEW.md`)

**Verdict (Fable):** right core, wrong label, mis-sequenced. The harness guarantees held up where sampled. "General-purpose agent,
starting with deep research" is not what the evidence supports or where the work went. Every success number comes from a loop in which
Claude scaffolds the app, writes or repairs the issue, hand-fixes tests, reviews and applies.

| # | Finding (Fable) | Status | Claude's view | Action |
|---|---|---|---|---|
| A1 | The chain-probe cheat is a **symptom**: the fifth case of one class (a test contradicts a clean implementation, the agent bends production code): `097d`, `1808`, 021 t1, injection V4, and now `j20261111_112252_11b3`. `scope:no_test_detection` is six per-line regexes and will not stop the next variant. The structural fix, a "blocked by locked test" exit for the agent, was in `PENDING.md` and skipped in favour of two fences. | the "skipped" part is **verified** (`PENDING.md` has the item since early November; #436/#437 were built instead) | Agree. Fences were easier to mutation-test; they treat the symptom. | Spec `ReportConflict` (section 3, item 3) |
| A2 | The judge evidence is weaker than "10/10": the two real cases were caught only after the prompt was tuned on them; seven were planted by Claude. No judge verdict is recorded in any pilot directory after 2026-11-08, including the chain probe whose spec required one. | chain probe part **verified** (`SPEC_CHAIN_PROBE` §3 asks for "hasil judge"; `pilots/chain_probe_v0/RESULT.md` has none); the rest *summary only* | Agree. Judge was not run on T1/T2; Claude's miss. | Record it in `RESULT.md`; run judge on the next chain (section 3, item 2) |
| A3 | The viewer row in `Reconciliation.md` is stale in a way that matters: labelled issues 001-044, but its cost and "Claude's review changed nothing" describe issues 001-002 only. | **verified** (only the task-count column was updated on 2026-11-11) | Claude's error. | Fix the row (section 3, item 2) |
| A4 | The mutant counts for #436 and #437 (24/24, 25/25) have no log in `verification/`; they exist only in commit messages. | **verified** (the scripts were in a scratch directory and are gone) | Claude's error; it breaks the "evidence logs are kept" rule. | Re-run and save under `verification/` (section 3, item 2) |
| A5 | **Top risk:** three more months of hardening a system whose unassisted success rate on work it did not shape is unknown. No-leak SWE is 8/14 and falling batch by batch (3/4, 3/5, 2/5). | numbers **verified** (`Reconciliation.md` 4b); the risk is a judgement | Agree. This is also the answer to Atha's business question. | Items 1 and 4 of section 3 |
| A6 | **Cheapest experiment:** ten verbatim issues from three small outside repos, with Claude not rewriting issues or touching tests. About $1-3 in model calls and an hour of Atha. | *summary only* | Agree; needs Atha's choice of repos and a "go live". | Section 3, item 4 |
| A7 | Do the failing-test reproducer PRs first, because that doubles as the top-risk experiment. | *summary only* (the exact meaning of "reproducer PRs" is in the full file) | Interpret with the full file before acting. | Ask Atha for `ARCH_REVIEW.md` |
| A8 | Per-item decisions (M4, M7, M8, production, planner, UI phases 3-4, redraft 3b), process versus product, and three demand tests. | **not seen by Claude**: the summary only says they exist | Needed for the decisions; do not guess. | Ask Atha for `ARCH_REVIEW.md` |

**Limits Fable stated:** nothing was run; job records outside the checkout were not available; the clone was shallow (229 commits from
2026-11-08), so claims about earlier PRs are unverified; it did not read `codetask/run.py`, `acceptance/verdict.py`, `router/job.py` or
`SPEC_ISSUE_WRITER.md` (the follow-up covered the first three).

## 2. Session 2: four code files (`FOLLOWUP.md`)

Read in full: `codetask/run.py`, `acceptance/verdict.py`, `router/job.py`, `codetask/agent.py`, `codetask/status.py`, `acceptance/testdetect.py`,
`acceptance/leaks.py`. **Not read:** `harness/guard.py`, `harness/steps.py`, `codetask/tools.py`, so "committed results never recomputed" and
"tools are safe to repeat" are verified only as far as these files delegate to them.

| # | Finding (Fable) | Status | Claude's view | Action |
|---|---|---|---|---|
| B1 | Step memo keys and reservation-from-ledger are upheld in the code. Refuse-before-send is delegated to `LLMCaller`. | *summary only* (positive) | – | – |
| B2 | One send-first path: an estimate overrun is handled after the money is spent (`run.py:442-455`). | **verified**; **by design**: only non-Anthropic models with heuristic token counts, and `AGENTS.md` already forbids calling that an absolute cap | True and documented; keep the wording honest in any money claim. | – |
| B3 | Tool versions are hand-bumped literals; money is float at the edges. | *summary only* | Plausible; check when touching tools or `run.py`. | Low |
| B4 | The "human" is `$USER` plus a `--yes` flag that records "approved in chat"; `by` in the decision log cannot tell Atha from Claude. | **partly** (`applied()` records `by=os.environ.get("USER")`, `router/job.py:1319`) | True; irrelevant while there is one user, relevant for any second one. | Low |
| B5 | "No way to say I'm stuck" (the agent has no exit when a locked test contradicts a correct implementation). | confirmed by Fable; consistent with A1 and `PENDING.md` | Agree. | `ReportConflict` |
| B6 | The regex gate is worse than first described: a hit is an ordinary failed criterion, so the matched lines are fed back to the agent for its next attempt, which teaches it which patterns to avoid. | **by design** (`SPEC_TEST_DETECTION_GATE` C3: "no special path") | Fair criticism of that choice; it loses its point once `ReportConflict` exists. | Revisit after `ReportConflict`; low |
| B7 | `applied` never reads the judge verdict, so the rule "only judge-blocked jobs get read" is habit, not code. | **partly** (`applied()` reads no judge state) | Agree; judge is advisory by design (`SPEC_JUDGE`), but nothing warns when a BLOCK is open. | Warn in `applied` on an unacknowledged BLOCK (section 3, item 2) |
| B8 | Atha's time: an upper bound per job is recoverable from the timestamps in `job.json`. | *summary only*, plausible | This partly contradicts the PENDING claim that human minutes are not measured. | Measurement script (section 3, item 1) |
| B9 | **`ReportConflict` design:** a tool beside Finish, verified in acceptance against the harness's own failing-test evidence, ending in a new `test_conflict` blocked reason and a job state that offers no retry. Main risk: a lazy exit. The checks prove "new tests green, only the named old tests red", not that the old test is wrong. | design sketch, *summary only* | Agree with the shape. The lazy-exit cost is small because a human reads the claim; mitigate by showing the named tests and their failures on the approve and status screens. | Spec (section 3, item 3) |
| B10 | **Chain operator:** it would be the first router code to write to a target repository, and it breaks the one-cap-per-job, per-job-lock and router-calls-no-model rules. | *summary only*, consistent with the code layout | Supports the deferral; if built, a coordinator over separate jobs, not a job kind. | None now (`PENDING.md` keeps it unjustified) |
| B11 | The detection gate skips `conftest.py`, any `test/` directory and `*.spec.*` names. | **by design** (`SPEC_TEST_DETECTION_GATE`); the fail-open risk is real where a repo's writable scope contains such names | Acceptable while scope normally protects tests; note it. | Low |
| B12 | The leak warning prints nothing whether it found nothing, crashed, or the repository is not Python. | **partly** (the DRAFT_REVIEW sentence "No old test looks affected" is also printed after a crash or for a JS repo, because `find` returns `[]` on any error) | Agree; "not checked" must differ from "none". | Fix (section 3, item 2) |
| B13 | Surprise: `applied` accepts any commit without checking its parent or tests. | **partly**: it records `as_is` (patch-id equal to the reviewed patch) but does not refuse when false; staging deploy refuses `as_is` false | The gate exists, one step later than Fable assumed. | Consider refusing earlier; low |
| B14 | Surprise: API keys stay in the process environment for the whole stage while child processes are spawned. | **unverified** | Needs a check of how stages start sandbox containers and child processes (the sandbox itself gets no key, per `AGENTS.md`). | Check, then decide (strict lane) |

## 3. What we do about it (proposal, order by cost; Atha decides)

1. **Measurement script** (read-only, fast lane): from the real `jobs/`, per job state, money, human wait (timestamps), decisions;
   totals for success rate, cost per applied PR, human minutes (upper bound). It gives the baseline for A5 and B8 at no model cost.
2. **Fix what Claude got wrong:** the viewer row in `Reconciliation.md` (A3); re-run and save the #436/#437 mutant logs in `verification/`
   (A4); note in `chain_probe_v0/RESULT.md` that the judge was not run (A2); `leaks` distinguishes "not checked" from "none" (B12);
   `applied` warns on an unacknowledged judge BLOCK (B7).
3. **Spec `ReportConflict`** (strict lane; A1, B5, B9, B6): agent exit, harness verification, `test_conflict` state, what the human sees.
4. **Outside-repo experiment** (A5, A6): ten verbatim issues from three small repos, Claude not editing issues or tests; Atha picks the
   repositories and gives "go live". Cost about $1-3.
5. **Check B14** (keys in the process environment) before any claim about key handling.

## 4. Not adopted, or waiting

- Operator `argus chain`: stays unjustified (B10); revisit only after a second cross-repo chain.
- Fable's per-item decisions on M4, M7, M8, production, planner, UI phases 3-4 and 3b (A8): wait for the full `ARCH_REVIEW.md`.
- Fable's label "general-purpose is the wrong label": noted, not decided. The research line has its own evidence (`argus research`, threshold v1);
  the question is where effort should go next, to be answered with item 1's numbers.
