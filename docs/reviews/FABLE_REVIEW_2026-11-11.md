# Fable's independent review of Argus (2026-11-11): findings, what Claude checked, and what to do

Two read-only Fable sessions ran: direction ([`ARCH_REVIEW_2026-11-11.md`](ARCH_REVIEW_2026-11-11.md), from
[`BRIEF_ARCH_REVIEW_2026-11-11.md`](BRIEF_ARCH_REVIEW_2026-11-11.md)) and four code files
([`FABLE_FOLLOWUP_2026-11-11.md`](FABLE_FOLLOWUP_2026-11-11.md)). Both texts are kept verbatim. This note is **Claude's reading**: for each
finding, whether Claude checked it against the repository on 2026-11-11, what Claude thinks, and the proposed action. Atha decides.

Status key: **verified** (Claude checked it) · **partly** · **unverified** (Claude did not check; line references into `router/job.py` etc. are
Fable's) · **by design** (true, and a documented decision).

## 1. Verdict (Fable)

Right core, wrong label, mis-sequenced. The harness guarantees are real and tested. "General-purpose agent, starting with deep research" is
not where the work went: since 2026-11-06 nearly all effort is code jobs on two practice apps, and research stage 1 was left unfinished. Every
success number comes from a loop in which Claude scaffolds the app, writes or repairs the issue, hand-fixes brittle tests, reviews and applies.
**The next step is outside evidence, not another fence, planner or UI phase.**

Claude's view: agree with the second half. The first half (the label) is a fair description of where effort went, not a verdict that the research
line is wrong; it has its own evidence (threshold v1, 17/17 SUPPORTED on the first real job) and the question is where effort goes next.

## 2. Stale or unsupported claims in `docs/Reconciliation.md` (ARCH_REVIEW table)

| # | Fable's claim | Status | Claude's view | Action |
|---|---|---|---|---|
| C1 | The viewer row (now 001-044) carries cost and "Claude's review changed nothing" of issues 001-002 only; later blocks, `NO_DRAFT`s and hand-edited tests contradict it (High) | **verified**: only the task-count column was updated on 2026-11-11 | Claude's error. | Rewrite the row from the real record |
| C2 | "J9 used in shadow batch 4-5": batch 5 was read in full by Claude; the judge was suspended on 11-07 over price; no judge verdict recorded in any pilot directory after `staging_stage14`; the chain probe spec required a judge per step and `RESULT.md` has none (High) | **partly**: chain probe part verified (spec §3 asks for "hasil judge", `RESULT.md` has none); whether batch 5 used the judge is unverified; the sentence in `Reconciliation.md` L17 is Claude's and overstated | Correct L17 to what the records show; record the missing judge in `RESULT.md` | Doc fix; judge on the next chain |
| C3 | "$0,02-0,08 per feature, 1-2 Atha decisions per job" excludes failed jobs (chain T1 $0,1820, $0,1527 wasted); since 11-08 fast-lane approvals are Claude's (High) | cost part **verified** (`chain_probe_v0/RESULT.md`); the decision count is **partly** (Atha still gave "go live" per job in the chain) | Agree: report cost including failed jobs. | Scoreboard (section 6, item 1) |
| C4 | Stage 2 closed on "judge 10/10": the 2 real cases were caught only after prompt tuning, 7 were planted by Claude; as PR reviewer 0/5 (High) | **unverified** (cites `SPEC_JUDGE.md` §6 and `self_review_v0`; the planted-defect test is in `SPEC_JUDGE.md` L178-179) | Plausible and consistent with the record; the "10/10" wording overstated what was proven. | Reword where "10/10" appears |
| C5 | #436 and #437 mutant counts have no log in `verification/` (Medium) | **verified** | Claude's error; breaks the evidence-log rule. | Re-run, save under `verification/` |
| C6 | `scope:no_test_detection` is six per-line regexes; misses split lines, `PYTEST_VERSION`, `inspect.stack()`, `unittest`, an unconditional equals-anything object (Medium) | **by design** (`SPEC_TEST_DETECTION_GATE` §2 C4 says it is a fence) | True; do not present it as an ADR-006 gate without that caveat. | Reword the Reconciliation row |
| C7 | M3 `[x]` "judge calibration PASS", evidence `M3_CLOSING.md`, but that file has no judge calibration (4/9 on one fixture, n = 9) (Medium) | **verified** that `M3_CLOSING.md` has no "judge" or "kalibrasi" text; the 4/9 detail unverified | Fix the evidence pointer or the claim. | Doc fix |
| C8 | "All issues written by Claude" (L92) contradicts "since 11-07 via phone chatbox" (L87); neither is an outside author (Medium) | **verified** (both lines exist; L87 is Claude's 2026-11-11 edit, L92 older) | Agree. | Doc fix |
| C9 | "Atha's minutes not yet asked" while measured twice (3 and 2 min); the omitted finding: Atha approved 022-024 "without understanding the issue" (Medium) | **partly**: `PENDING.md` L240 says minutes are asked once; L247 holds approve times (batch 3 about 5-7 min, batch 1 median 45 s). Not checked: the two figures Fable cites | Agree the section is inconsistent. | Doc fix; scoreboard |
| C10 | Research: "eval v0 8/8" graded by Claude, v1 batch skipped, factual correctness never checked independently (Medium) | consistent with `PENDING.md` (open item "kebenaran faktual belum dinilai") | Agree; already listed as open. | Keep open item; decide whether it matters (Section 4) |
| C11 | Prompt injection "not measured for code tasks" (L159) vs "v0 clean" (L282): actual is 4 comment-style variants, n = 1 each, simulated pages (Low) | **verified** (both lines exist; L282 is Claude's) | Agree. | Doc fix |
| C12 | "Basis: main after #266" (L3); section 6 items 2-3 stale (Low) | **verified** (L3 unchanged; items about UI kontrol and up2 are old) | Agree. | Doc fix |

Fable's "supported where sampled": refuse-before-send order in `harness/llm.py`, `durability="sync"` at the `graph.invoke` sites, latest `verify_at`
3623 passed with 0 sandbox skips, SWE and chain-probe figures match their `RESULT.md`. Fable's process counts (108 review files, 109 commits on
2026-11-11) are roughly confirmed (111 review files, 105 commits).

## 3. Decisions (ARCH_REVIEW table) and Claude's view

| Item | Fable's call | Claude's view |
|---|---|---|
| M4 multi-agent | Drop from the active roadmap | Agree; it is already deferred. Flip: a measured job class where one agent fails and a hand-split passes. |
| Hierarchical planner | Drop (three probes say no) | Agree; consistent with `PENDING.md`. |
| Fixed chain operator | Wait | Agree (also follow-up section 4). |
| M7 registry/policy | Wait, except record the approver's identity now | Small and cheap; follow-up says `by` is already logged but is `$USER` (cannot tell Atha from Claude). Do it when a second approver exists, or sooner if cheap. |
| M8 discovery, memory | Drop | Agree; nothing started. |
| Production deploy of the practice apps | Wait; the "second user" trigger is circular; Argus's first production is a PR on someone else's repo | Insightful; it changes what "production" means for Argus. Decide with Atha. |
| UI phase 3 (approve button) | Premature: Atha already approves without understanding; a button makes that cheaper | Agree. Flip: Atha rejects 4 of 5 planted bad drafts from the phone summary (a test worth running). |
| UI phase 4 (staging buttons) | Drop | Agree for one operator. |
| Redraft 3b | Wait | Agree (Atha already deferred it). Flip: `submits_exhausted` above ~10% of drafts. |
| Overdue | Outside-repo success rate; a legal "blocked by locked test" exit for the agent | Agree on both; the second was in `PENDING.md` and skipped. |

## 4. Risk, experiment, process, niche (ARCH_REVIEW) and Claude's view

- **Top risk:** three more months of hardening a system whose unassisted success rate is unknown and probably low (no-leak SWE 8/14, 3/4, 3/5, 2/5, **verified**
  in `Reconciliation.md` 4b). The chain-probe cheat is the fifth case of one class (`097d`, `1808`, 021 t1, injection V4, T1): a test contradicts a clean
  implementation and the agent bends production code. Claude: agree; each case got its own fence, the structural answer (an exit for the agent) was skipped.
- **Experiment:** 10 verbatim issues from 3 small outside Python repos with pytest, judge on all, Claude neither rewrites issues nor touches tests, blind
  grading, a kill line set first (for example fewer than 3/10 mergeable untouched); $1-3, one hour of Atha. Claude: agree; needs Atha to pick repos.
- **Process, stop:** the full ritual (spec, mutants, `verify_at`) for advisory or practice-app work (#437 got all three); one regex fence per incident; issue-writer
  latency tuning; hand-maintained status prose. **Start:** a scoreboard generated from job records; cost per merged change including failed jobs; Claude
  interventions and Claude token cost per merged change; Atha minutes on every job. Claude: the challenge to #437 is fair. Under the two-lane rule it was strict
  because it touches the draft check and the approve screen; a lighter lane for advisory heuristics is worth deciding explicitly.
- **Niche:** the budget cap protects nothing a buyer notices at $0,02-0,20 per job; the ledger and the red-by-assertion check are the stronger assets. Three
  options: (1) `harness/` as a library for agent builders on LangGraph, (2) failing-test reproducers for maintainers (5 PRs on live issues, disclosed), (3) capped
  dependency upgrades with staged rollback. Fable: do (2) first, because it doubles as the top-risk experiment. Claude: agree with the ordering; (2) also needs
  Atha's GitHub identity, so it is his call.
- **Limits Fable stated:** no job records, `SHADOW.md` or practice-app repos; nothing run; shallow clone (229 commits from 11-08); Claude's token spend and Atha's
  real time are recorded nowhere.

## 5. Follow-up: four code files (`FABLE_FOLLOWUP`)

| # | Finding (Fable) | Status | Claude's view | Action |
|---|---|---|---|---|
| B1 | Step memo keys and reservation-from-ledger upheld; refuse-before-send delegated to `LLMCaller` | **unverified** (positive) | – | – |
| B2 | One send-first path: `EstimateExceeded` handled after the money is spent (`run.py:442-455`) | **verified**; **by design** (heuristic counts for non-Anthropic models; `AGENTS.md` forbids calling them an absolute cap) | Keep the wording honest in any money claim. | – |
| B3 | By convention only: tool versions are hand-bumped literals (one patched into a shared dict after capture, `run.py:331`); "every tool is safe to repeat" is a docstring; money is float at the edges | **unverified** | Plausible; check when touching tools or `run.py`. | Low |
| B4 | The "human" is `$USER` plus `--yes` recording "approved in chat" | **partly** (`applied()` records `by=os.environ.get("USER")`, `router/job.py:1319`) | True; matters with a second user. | Low |
| B5 | No way to say "I am stuck"; no fitting terminal reason (`status.py:29`) | confirmed by Fable; consistent with `PENDING.md` | Agree. | `ReportConflict` |
| B6 | The regex gate is worse than first described: a hit is an ordinary failed criterion and the matched lines are fed back to the next attempt | **by design** (`SPEC_TEST_DETECTION_GATE` C3) | Fair criticism: it teaches the agent which patterns to avoid. Terminal, not feedback, may be better. | Revisit after `ReportConflict` |
| B7 | `applied` never reads the judge verdict; the judge is opt-in (`job.py:996`) | **partly** (`applied()` reads no judge state) | Advisory by design (`SPEC_JUDGE`), but nothing warns on an open BLOCK. | Warn in `applied` |
| B8 | Atha's time: an upper bound is recoverable from `job.json` timestamps (`approval.at` minus draft `ended_at`; `applied` minus agent `ended_at`); under `--yes` the confirm interval is zero; no link between jobs re-issued for one issue | **unverified**, plausible | Partly contradicts "not recorded anywhere"; makes the scoreboard cheap. | Measurement script |
| B9 | **`ReportConflict` design:** a tool beside Finish; acceptance verifies the agent's named red tests against the harness's own evidence (nothing else red, all red tests old and protected, passing at baseline, `must_pass` green, scope and detection pass); new blocked reason `test_conflict`, a job state with no retry, package built. Risks: lazy exit, injected or flaky trigger, dead end (`redraft` refused, each conflict costs a new unlinked job) | design sketch, **unverified** | Agree with the shape. Add: the human sees the named tests and their failing assertions; one conflict per job at most; treat a conflict as a draft defect to be fed back to the issue writer. | Spec |
| B10 | **Chain operator** would be the first router code to write to a target repository; breaks one cap per job, the per-job lock, "router calls no model"; needs its own job kind; job B still needs approve by sha | **unverified**, consistent with the code layout | Supports the deferral; if built, a coordinator over separate jobs. | None now |
| B11 | Detection gate: suffix allowlist; name-only exemption (`conftest.py`, any `test/` directory, `*.spec.*` skipped); pre-existing matching lines subtracted; unreadable and oversized files fail closed | **by design** (`SPEC_TEST_DETECTION_GATE`) | The exemptions are fail-open where a repo's writable scope contains such names; note it. | Low |
| B12 | Leak warning: any exception returns no finding and nothing is printed for none, so "clean", "crashed" and "not Python" look the same; under `--yes` the screen is only echoed | **partly** (`find` returns `[]` on any error; DRAFT_REVIEW prints "No old test looks affected" in all three cases) | Agree; "not checked" must differ from "none". | Fix |
| B13 | `applied` accepts any commit; neither its parent nor its tests are checked | **partly**: it records `as_is` (patch-id equal to the reviewed patch) but does not refuse when false; staging deploy refuses `as_is` false | The gate exists, one step later than Fable assumed. | Consider refusing earlier; low |
| B14 | API keys stay in `os.environ` for the whole stage while children are spawned (`job.py:449-456`); scrubbing is outside these files | **partly**: the variables are set inside a context manager and popped in `finally` (verified); whether child processes and sandbox containers inherit them is unverified | Needs a check of how stages start child processes; `AGENTS.md` says the sandbox gets no key. | Check before any claim about key handling |
| B15 | `applied` reads the patch from the recorded absolute directory; `recursion_limit` is a literal 40 (`run.py:420`) | **partly** (`job.py:1311` verified for the first) | Minor. | Low |

Not read by Fable: `harness/guard.py`, `harness/steps.py`, `codetask/tools.py`; "committed results never recomputed" and "tools are safe to repeat" are
verified only as far as the four files delegate.

## 6. Proposed actions (order by cost; Atha decides)

1. **Scoreboard script** (read-only, fast lane): from the real `jobs/`, per job: outcome (applied untouched / applied after human change / rejected /
   abandoned), money including failed jobs, decisions, human wait (upper bound), judge verdict if any. Baseline for C3, C9, B8 and the top risk.
2. **Fix what Claude got wrong:** C1, C2, C5, C7, C8, C11, C12 in `Reconciliation.md` and `PENDING.md`; save the #436/#437 mutant logs under
   `verification/`; note in `chain_probe_v0/RESULT.md` that the judge was not run; `leaks` distinguishes "not checked" from "none" (B12); `applied` warns on
   an unacknowledged judge BLOCK (B7).
3. **Spec `ReportConflict`** (strict lane; B5, B9, B6, and the structural fix for the repeated class): agent exit, harness verification, `test_conflict` state.
4. **Outside-repo experiment** (top risk): ten verbatim issues, three small repos, a kill line set first. Atha chooses the repositories and gives "go live".
5. **Check B14** (key variables in child processes).
6. **Decide explicitly:** a lighter lane for advisory work (section 4); what "production" means (section 3); whether to run the UI phase 3 test (reject 4 of 5
   planted bad drafts from the phone summary) before building the button.

## 7. Not adopted, or waiting

- Operator `argus chain`: unjustified (B10); revisit after a second cross-repo chain.
- M4, M8, UI phase 4: dropped from the active list if Atha agrees with section 3.
- UI phase 3 (approve button): on hold until the planted-draft test.
- Redraft 3b: waits for `submits_exhausted` above ~10% of drafts.
