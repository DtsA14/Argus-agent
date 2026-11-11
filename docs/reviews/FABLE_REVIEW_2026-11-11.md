# Fable's independent review of Argus (2026-11-11): findings, what Claude checked, and what to do

Two read-only Fable sessions ran: direction ([`ARCH_REVIEW_2026-11-11.md`](ARCH_REVIEW_2026-11-11.md), from
[`BRIEF_ARCH_REVIEW_2026-11-11.md`](BRIEF_ARCH_REVIEW_2026-11-11.md)) and four code files
([`FABLE_FOLLOWUP_2026-11-11.md`](FABLE_FOLLOWUP_2026-11-11.md)). Both texts are kept verbatim. This note is **Claude's reading**: for each
finding, whether Claude checked it against the repository on 2026-11-11, what Claude thinks, and the proposed action. Atha decides.

Status key: **verified** (Claude checked it) · **partly** · **unverified** (Claude did not check; line references into `router/job.py` etc. are
Fable's) · **by design** (true, and a documented decision).

## 0. Status board: what is fixed and what is not (kept current; update it in every PR that changes a row)

Status: **done** (merged, with the evidence named) · **in PR** (written, not yet merged) · **open** (planned, in the phase named) · **dropped** (decided not to do, with the reason) · **held** (waits for a named
condition) · **by design** (true, a documented decision) · **info** (a positive finding or a note, nothing to fix). Phases and ids are those of [`FABLE_PLAN_2026-11-11.md`](FABLE_PLAN_2026-11-11.md); the order is
in `PENDING.md`. Last updated 2026-11-11 (PR "docs-corrections").

**Counts (rows below):** done 4 · in PR 21 · open 22 · held 9 · dropped 9 · by design 3 · info 6 (total 74). Scoreboard, FIX-A and the ENV spike are merged (see their rows); FIX-B (E1, E2) is in a PR. C7, C9 and C10 stay open; every other code fix waits for its phase.

### A. Stale or unsupported documentation (section 2)
| Id | What | Status | Evidence or next step |
|---|---|---|---|
| C1 | Viewer row in Reconciliation described issues 001-002 | in PR | Rewritten from `verification/scoreboard-2026-11-11.json` (viewer 43 applied of 56 jobs, $0,060 each) |
| C2 | "J9 used in batch 4-5"; chain probe has no judge result | in PR | Reconciliation L17 corrected; `chain_probe_v0/RESULT.md` now says the judge was not run |
| C3 | Cost per feature excluded failed jobs | in PR | Figures now from the scoreboard, failed jobs included ($0,058 ledger, $0,060 viewer) |
| C4 | "Judge 10/10" overstated | in PR | Reworded in `PENDING.md`; the 10/10 breakdown itself is still not in the sources (open: find it in `SPEC_JUDGE.md` section 6 or drop the number) |
| C5 | No mutant logs for #436, #437 | in PR | `verification/test_detection_gate_mutants.log` and `old_test_leaks_mutants.log` (scripts alongside), rebuilt on current code |
| C6 | `no_test_detection` presented as an ADR-006 gate | in PR | Reconciliation row now says six regexes, a fence not a proof |
| C7 | M3 "judge calibration PASS" has no source in `M3_CLOSING.md` | open | Claim flagged in Reconciliation; still needs a source or removal |
| C8 | "All issues written by Claude" vs chatbox since 11-07 | in PR | Reconciliation L92 fixed |
| C9 | "Atha's minutes not yet asked" | open | Waits are measured (upper bound, scoreboard); real attention minutes and Claude's tokens are still unmeasured (weekly record, DOC) |
| C10 | Research eval graded by Claude only; no independent fact check | open | Held under "freeze the research line until the phase 2 verdict" |
| C11 | Prompt injection "not measured" vs "v0 clean" | in PR | Reconciliation row rewritten (v0 = 4 variants, n = 1) |
| C12 | "Basis main after #266", stale gap items | in PR | Header, gap items 2-3 updated |

### B. Code findings from the four-file reading (section 5)
| Id | What | Status | Evidence or next step |
|---|---|---|---|
| B1 | Memo keys and reservation-from-ledger upheld | info | – |
| B2 | Estimate overrun handled after the money is spent (`run.py:442-455`) | by design | Heuristic counts; `AGENTS.md` already forbids calling it an absolute cap |
| B3 | Tool versions hand-bumped; "safe to repeat" is a docstring; float money at the edges | done | Merged #446: the `RunValidation` version stays (section 14 correction); the other two points stay open |
| B4 | `by` is `$USER` | held | Matters with a second approver |
| B5 | No way to say "I am stuck" | open | RC, phase 3 |
| B6 | Detection-gate hits are fed back to the agent | open | GATE, phase 3 (after RC) |
| B7 | `applied` ignores the judge verdict | dropped | Plan: the judge ran on 8% of code jobs |
| B8 | Atha's time recoverable from timestamps | done | `scripts/scoreboard.py` (#444): upper bound, median 2 min per stage |
| B9 | `ReportConflict` design | open | RC, phase 3 (spec v2 is a draft) |
| B10 | Chain operator breaks three rules | held | Wait for a second cross-repo chain |
| B11 | Detection gate skips `conftest.py`, `test/`, `*.spec.*` | by design | Noted; low |
| B12 | `leaks` cannot tell "none" from "crashed" or "not Python" | open | ADV follow-up (advisory lane) |
| B13 | `applied` accepts any commit (records `as_is`) | held | Low; staging deploy refuses `as_is` false |
| B14 | Keys in `os.environ` during a stage | info | Scoped to the stage and removed in `finally`; git and docker CLI still inherit (see D12) |
| B15 | Patch read from a recorded absolute path; `recursion_limit` literal 40 | dropped | Low |

### C. Audit of the core guarantees (sections 8 and 9)
| Id | What | Status | Evidence or next step |
|---|---|---|---|
| D1 | **Run wedge**: `Toolbox.run` catches only two exception types; a model-chosen input wedges the run on every resume | done | Merged #446 (`ef64710`): `Toolbox.run` refuses OSError/ValueError from the file-system tools and from `Finish`; paths and args shape checked; replies scrubbed; `memo.put` survives a lone surrogate; verify_at 3652 passed |
| D2 | `EventLog.emit` never fsyncs; a damaged non-final line is skipped silently | open | FIX-C, phase 3 |
| D3 | `scripts/smoke_models.py` calls a model outside `LLMCaller` | in PR | Exception written into `AGENTS.md` ("by decision"); no code change |
| D4 | `get_num_tokens_from_messages` / `list_models` outside the ledger | open | Check whether they cost money (unverified) |
| D5 | **Forgeable verdict** (tests share a process with the agent's code) | open | VF, phase 3 (spec from the canary-and-nonce sketch); until then "never apply a DONE job unread" |
| D6 | `RunValidation` result unlabelled as data | done | Merged #446: `RUN_LABEL` line before the JSON; the tool version is deliberately not bumped |
| D7 | No key redaction in error text | open | FIX-C, phase 3 |
| D8 | Two processes on one job spend the reservation twice | dropped | Plan: does not move a measured number |
| D9 | A config change on resume restarts the attempt | dropped | Same |
| D10 | `delivery="unknown"` written as 0 when `failed_attempt_charge` is not `worst_case` | dropped | Config sets `worst_case` |
| D11 | Float arithmetic in caps | dropped | Known; keep comparisons in nano |
| D12 | Git and docker CLI inherit key variables | open | Fold into FIX-C if cheap |
| D13 | Path jail, sandbox flags, no unsandboxed exec hold | info | Good news |
| D14 | Memo keys, reservation, `durability="sync"` hold | info | Good news |
| E1 | **Unknown cost charged as zero** to the reservation | in PR | FIX-B: a call whose cost cannot be computed is charged the larger of its worst case and its real usage at the highest write rate (`charged = worst_case_unknown_cost`); tests, 22 mutants killed (`verification/fix_b_unknown_cost_mutants.log`) |
| E2 | Zero and negative prices not rejected | in PR | FIX-B: rates must be finite numbers of at least 0; zero input/output refused on a direct provider with a finite budget; peak multiplier at least 1; missing input/output refused |
| E3 | Verdict-forgery fix (canaries, nonce, frozen node set) | open | = VF |
| E4 | Zero written on a billing assumption (paid web) | dropped | Check with E1 only if cheap |
| E5 | Gateway provider pin is a prefix test | dropped | Low |
| E6 | Web tools hold (SSRF, redirects, sizes) | info | – |
| E7 | Staging runs no commit content outside a container; `package.json` read follows a link | dropped | The link read is low; not scheduled |

### D. Direction, experiment, scoreboard, attacks, plan (sections 1, 3, 4, 10-14)
| Id | What | Status | Evidence or next step |
|---|---|---|---|
| A1 | Outside evidence before more fences | open | EXP, phase 2 |
| M4, M8, planner | Drop from the active roadmap | held | Reopen conditions in the plan, section 4 |
| M7 | Record the approver's identity | held | With a second approver |
| Production | Redefine: first production is a PR on someone else's repo | held | Atha decides after the experiment |
| UI phase 3 / 4 | Approve button premature / staging buttons drop | held | Phase 3 reopens if Atha rejects 4 of 5 planted bad drafts from the phone summary |
| 3b | Auto-redraft | held | Waits for `submits_exhausted` above about 10% of drafts |
| Chain operator | `argus chain` | held | Second chain with the same glue |
| SB | Scoreboard script and baseline | done | #444, `verification/scoreboard-2026-11-11.json` |
| DOC | Documentation corrections and mutant logs | in PR | This PR |
| ADV | Advisory lane in `AGENTS.md` | in PR | This PR (Atha: yes, 2026-11-11) |
| WEEKLY | One weekly line: Atha hours and Claude usage | open | Phase 1; Atha fills it, the scoreboard cites it |
| FIX-A | D1 + D6 (+ tests for attacks A8, A7) | done | Merged #446 (`ef64710`) |
| ENV | One-repository spike (`cachetools`), then three sandbox environments | in PR | Spike done (`pilots/outside_v0/ENV_SPIKE.md`): cachetools 416 tests in 0.6 s (needs `-o pythonpath=src`), boltons 621 in 3.7 s (BSD-3 confirmed, 25,874 lines), humanize unusable; the environment entries and the src-layout handling are not started (strict, deferred) |
| GUARD | Phone page shows `for_human` beside new test names and changed files (attack A13) | open | Phase 1; check the ledger draft endpoint first |
| PRE | `PREFLIGHT.md`: ten issues by the fixed rule | open | Phase 1, after ENV |
| EXP | The retrospective outside experiment (kill at 2 or fewer A of 10, success at 5 or more) | open | Phase 2; Atha's "go live" and verdict |
| FIX-B | E1 + E2 | in PR | PR `fix-b-unknown-cost`; spec `SPEC_FIX_B_UNKNOWN_COST.md`; waits for `verify_at`, then merge (phase 2 item done early: it needs no model) |
| RC / GATE / VF / FIX-C | `ReportConflict` MVP; terminal gate; verdict forgery; ledger fsync and key redaction | open | Phase 3, only on a success verdict |
| G4, G6 | Candidate suites measured; environments built | in PR | Measured for the sandbox (see ENV_SPIKE); building the environment entries still open |
| G5 | Retrospective version first | done | Decided by Atha 2026-11-11 |
| H1 | CSV half of A15 not exploitable (the CSV has no title) | done | Checked, section 13 |
| H2 | Attacks A8, A9, A7, A10 become regression tests of the fixes | open | With FIX-A, FIX-C, VF |
| H3 | A13 as a guard, not an experiment | open | = GUARD |
| H4, H5 | A10 forger fixtures, A11 false-conflict test | open | With VF and RC |
| H6 | A1 succeeds by design | by design | Human reads the issue before `issue start --sha` |
| Plan risks | ENV cost, conflicts scored as failures, narrow FIX-A, memorised fixes, the middle outcome | info | First signals in the plan, section 6 |

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

## 8. Session A: audit of the core guarantees ([`AUDIT_2026-11-11.md`](AUDIT_2026-11-11.md))

Fable read `harness/{guard,steps,llm,events,memo,crash,errors}.py`, `codetask/tools.py`, `tools/{fs,sandbox,registry}.py`, `models/registry.py` and parts of
`tools/web.py` and `acceptance/validation.py`. Claude re-checked the points marked **verified** with grep on 2026-11-11 (no tests run).

| # | Finding (Fable) | Status | Claude's view | Action |
|---|---|---|---|---|
| D1 | **Run wedge (VIOLATED, reproduced by Fable):** `Toolbox.run` catches only `PathEscape` and `FileNotFoundError`; a model-chosen WriteFile onto an existing directory, a name over 255 bytes, or a lone surrogate raises uncaught. The model reply is already committed, so every resume replays the call and crashes again; a surrogate also fails `memo.put`, paid and lost, bought again | **verified** that the handler catches only those two (`codetask/tools.py:254-257`); the reproduction is Fable's | The most important finding: it breaks "resume works" for a model-chosen input, in the strict lane. | **Fix first**: catch `OSError`/`UnicodeError`, return "Refused"; escape surrogates before `memo.put`; tests that fail on the old code |
| D2 | `EventLog.emit` never fsyncs, unlike the memo; power loss after a send loses `llm_call_started`; `parse_lines` skips any undecodable line, not only the last, so damage silently removes spend | **verified** (`harness/events.py` `emit` writes without flush/fsync) | Real but narrow: process crashes are fine, power loss is not. The ledger is the money record. | Fix: flush + fsync; an undecodable non-final line is an error |
| D3 | "No `.invoke/.stream/.batch/build_chat_model` outside `harness/llm.py` and `models/registry.py`" is false by one script: `scripts/smoke_models.py` | **verified** (lines 39, 47, 55) | A manual script; still breaks the stated rule and costs money. | Route it through `LLMCaller`, or exempt it explicitly in the rule |
| D4 | `get_num_tokens_from_messages` makes a provider request per call outside the ledger; `list_models` uses raw SDK clients | **unverified** | Check whether those requests cost money. | Check |
| D5 | **Forgeable verdict:** the test result is parsed from the test process's own stdout; writable code in that process can print a consistent report and `os._exit(0)`; pytest has no nonce (the file admits it for unittest). "No small fix" | **unverified** (`validation.py:23-25` quoted by Fable) | Serious for any claim that acceptance proves behaviour. Idea to ask Fable: a harness-planted sentinel test that must fail; if it reports as passed, the report is forged. | Design a fix; until then, "never apply a DONE job unread" stays the rule |
| D6 | The `RunValidation` tool returns raw JSON with `output_tail`, unlabelled as data, unlike auto-validation and ReadDocs | **verified** (`codetask/tools.py:425-432`) | Small, closes an injection surface. | Fix: same label as auto-validation |
| D7 | No redaction exists; provider exception text goes to the ledger, the retry event and `LLMCallFailed` in full; a provider that echoes a key puts it in `events.jsonl` | **verified** that grep for `redact|mask|scrub` finds nothing in the code; the leak paths are Fable's | Real risk, low likelihood. | Replace configured key values in every error string before emit or raise |
| D8 | Two processes on one job: only the router locks; `run_code_task.py --resume` twice at once spends the attempt reservation twice | **unverified** | Matters only if someone runs it by hand twice. | flock the run directory |
| D9 | A config change on resume (a role model) misses every step key and restarts the attempt on a half-edited workspace | **unverified** | Could cost money; edge case. | Freeze the model in the contract or refuse the resume |
| D10 | `delivery="unknown"` is written `usd_nano=0` when `failed_attempt_charge` is not `worst_case`; a gateway 429 is always written 0 | **partly** (`config.yaml:60` sets `worst_case`, `harness/llm.py:355` defaults to it; the 429 part is Fable's) | Only if the config changes; 429 costs nothing at the provider. | Low |
| D11 | Money is float in cap and limit arithmetic; spend is integer | **unverified**, consistent with `harness/llm.py` | Known; keep comparisons in nano. | Low |
| D12 | Key variables are in `os.environ` for the whole stage; docker CLI and git inherit them; web children and containers do not ("sandbox gets no key" HOLDS) | **partly**: set in a context manager and removed in `finally` (`router/job.py:449-456`, verified); inheritance by each process is Fable's reading | Closes B14 for the sandbox; git and docker CLI still see the keys. | Give git a minimal environment |
| D13 | Path jail HOLDS (traversal, symlinks by descriptor with `O_NOFOLLOW`, special files); code never runs outside Docker; sandbox flags as designed (`--network none`, read-only, cap-drop ALL, no-new-privileges, 512m, 128 pids). Missing: file-size and open-file limits | **unverified**, positive | Good news to keep: the sandbox boundary itself held. | Consider `ulimit` file-size limits |
| D14 | Positives: no unsandboxed `exec`/`eval`/`shell=True`; step memo keys, reservation from ledger, `durability="sync"` at all ten `graph.invoke` sites HOLD | **unverified**, positive | – | – |

**Not covered by Fable** (listed in the audit): `harness/paid.py`, `budget.py`, `tools/web_fetch.py`, `deepseek_web.py`, `models/gateway.py`, `pricing.py`, the drafter, research,
judge and issue-writer loops, `router/stage*.py`, `control*.py`, `acceptance/contract.py`, `draft.py`, `review.py`, LangChain internals (`max_retries`, `max_tokens`).

**Order proposed:** D1 first (strict lane, small, high value), then D2, D6, D3 and D7 as one small batch, then D5 as a design problem. D1-D3 and D6-D7 are code the guarantees
in `AGENTS.md` depend on, so each needs a test that fails on the old code and the usual process.

## 9. Session A follow-up: forgeable verdict and the remaining files ([`AUDIT2_2026-11-11.md`](AUDIT2_2026-11-11.md))

Fable read `harness/paid.py`, `budget.py`, `models/pricing.py`, `models/gateway.py`, `tools/web_fetch.py`, `tools/deepseek_web.py` in full; `router/stage.py`,
`router/stage_viewer.py`, `acceptance/contract.py`, `acceptance/draft.py` only at the cited sections (so "staging: none found" is not a line-by-line result).
The verdict-fix sketch was not built or run.

| # | Finding (Fable) | Status | Claude's view | Action |
|---|---|---|---|---|
| E1 | **Unknown cost is charged as nothing (VIOLATED):** `cost_usd` returns `None` for a cache write without a write price; the ledger gets null but `Reservation.charge` adds 0 and `reconcile_ledger` skips it, so such calls are free to the cap | **verified** (`models/pricing.py:66-68` returns `None`; `harness/llm.py` `charge`: `self.used_nano += nano or 0`) | Narrow (needs a provider that reports cache-write tokens for a model priced without a write rate), but it contradicts "unknown cost is null, never 0" for the budget. | Fix first with D1: charge the worst case when cost is unknown and the budget is finite |
| E2 | Zero and negative prices are not rejected: `check_priced` tests only for a missing entry; `{input: 0, output: 0}` on a direct provider makes a finite cap vacuous; a negative price lowers recorded spend; only the gateway guards this | **verified** that `check_priced` checks presence only (`harness/llm.py:119-131`); the gateway part is Fable's | Cheap to fix. | Refuse non-positive prices unless the model is marked free |
| E3 | Forgeable verdict: no option makes it unforgeable. Recommended: must-fail canaries (pass, assertion-fail, error) written by the harness, a per-run nonce, and a node set frozen at approve; turns "print a clean report and exit 0" into a failure; targeted tampering (the chain-probe cheat) still passes, so "never apply a DONE job unread" stays. Sketch of 27 lines | design, **unverified** (not built) | A good, bounded answer; it also fits Atha's "reading the patch is still necessary" position. Build with the forger fixtures Fable lists as mutants (clean-report-and-exit-0, no-op `pytest_pyfunc_call`, dropped required node). | Spec (strict lane) after D1/E1/E2 |
| E4 | Zero written on a billing assumption: an error with DeepSeek's own body or an empty 200 is recorded as 0, not null (`paid.py:98-103`, `117-120`) | **unverified** | Plausible; same class as E1. | Check with E1 |
| E5 | Gateway provider pin is a prefix test and a reply that names no provider passes (`gateway.py:119-122`) | **unverified** | Pins protect price and data policy; check. | Low-medium |
| E6 | Web tools hold as read (SSRF, redirects, size limits; paid search/fetch with key on stdin and an empty environment); `materialize` writes model-chosen paths without the jail but is safe via the lexical `_plain` and the intake refusing symlinks | **unverified**, positive | Good news, with the second item "by convention". | – |
| E7 | Staging: no commit content runs outside a container (`git archive | tar -x`, modes changed without following links; containers with no network, read-only root, no capabilities; proxy `O_NOFOLLOW` with a peer-pid check). One host read follows a link (`package.json`, `stage_viewer.py:411`); `stage check` is forgeable by a conftest in the commit (the file says so) | **unverified**, partly a sampled reading | Positive; the `package.json` read is low. | Open it with `O_NOFOLLOW` |

**Combined fix list from sessions A (sections 8-9), by risk:** D1 run wedge; E1 unknown cost charged as zero; E2 non-positive prices; D2 ledger durability; D6 unlabelled
`RunValidation` output; D7 key redaction in error text; D3 `smoke_models.py` rule; then E3 (design) and the low items. D1, E1, E2, D2 are strict-lane code that the money and
crash-resume guarantees in `AGENTS.md` depend on: each needs a test that fails on the old code, review, mutants and `verify_at`.

## 10. Session B1: `ReportConflict` spec ([v1](FABLE_SPEC_REPORT_CONFLICT_v1.md), [v2](FABLE_SPEC_REPORT_CONFLICT_v2.md))

Fable drafted the spec (v1), then corrected it after Claude pointed out that `codetask/run.py` freezes the tool allowlist at setup (v2 keeps the tool in the
allowlist and refuses a second use inside the tool reply). v2 also replays six incidents on paper and cuts an MVP. **Draft, not approved; v2 replaces parts of v1.**
Claude re-checked these code claims on 2026-11-11: the allowlist is frozen at setup (`codetask/run.py:312-332`); `GATED` and `tools.coder` are where v2 puts the tool
(`codetask/tools.py:124-126`, `config.yaml` tools block); changed tests are refused for vitest drafts (`acceptance/draft.py:167-170`); `redraft` is allowed only from
`DRAFT_FAILED`/`AWAITING_APPROVAL` (`router/job.py:1232`); `MAX_NODES = 50` (`acceptance/validation.py:54`); `red_check` takes named nodes and returns
`outcome/type/assertion/path`. Not re-checked: the line references into `job.py` and `steps.py` beyond those, and the replay rows (inference from notes, as Fable says).

| # | Finding or design point | Status | Claude's view |
|---|---|---|---|
| F1 | Tool stays in the allowlist; a second use is refused inside the tool reply, memo-keyed; the "used" state lives in graph state committed after acceptance | design, partly **verified** against `run.py` | Right fix for the frozen allowlist. |
| F2 | The agent names test files, not nodes; the harness derives the red set (v1's five-node limit could have refused `c4be`) | design | Agree. |
| F3 | "Red by assertion" is too narrow (097d fails on a library query error); the new condition is "failed, in the test's own frame" | design | Agree; weaker evidence, so the human still decides. |
| F4 | An unconfirmed report stays visible on the status screen | design | Agree. |
| F5 | Replay: of six incidents, a report would be confirmed in `097d`, `1808` (already caught at approve, #275), `j20261111_112252_11b3` and `c4be`; undecided for 021 t1; correctly refused for V4 (a defective new test, no exit for it) | inference from notes | The honest gain is smaller than it looks: with the leak warning (#437) the ledger cases are also caught at draft time, so `ReportConflict` is the backstop. Still the only structural answer for the vitest cases (`097d`, 021 t1), where leak detection does not exist. |
| F6 | MVP: tool, verification (`acceptance/conflict.py`), `BLOCKED/test_conflict`, status lines, `retry` refused; no new `CONFLICT` job state, no `--from-conflict`, no approve gate; about 230 lines of code, 350 of tests; riskiest piece is the new branch in the acceptance node (`run.py:366-387`) | design | Reasonable size for the strict lane. Limit stated by Fable: it provides an exit, it does not force the agent to use it. |
| F7 | Until the verdict-forgery fix exists, `ReportConflict` can be built, because a confirmed conflict never becomes a pass or an apply; checks 4, 6, 7 are solid (baseline without agent code), checks 2, 3, 5, 8 are read from a process that contains agent code | design | Agree with the caveat. |
| F8 | The detection-gate hit should become terminal (not feedback) once `ReportConflict` exists, in its own PR | design | Agree; sequence after the MVP. |

**Proposed order of the strict-lane work from sessions A and B1** (each: test that fails on the old code, review, mutants, one `verify_at`, then "merge"):
1. D1 run wedge + E1 unknown cost charged as zero + E2 non-positive prices (money and crash-resume; small).
2. D2 ledger fsync + D6 `RunValidation` label + D7 key redaction + D3 `smoke_models.py`.
3. `ReportConflict` MVP (F6), then the terminal detection gate (F8).
4. The verdict-forgery fix (E3, canaries and nonce) as its own spec.

## 11. Session B2: outside-repo experiment protocol ([`FABLE_PROTOCOL_OUTSIDE_EXPERIMENT.md`](FABLE_PROTOCOL_OUTSIDE_EXPERIMENT.md))

Fable's design: ten verbatim issues from three small public Python repositories, **retrospective** (issues closed by a merged PR, given to Argus at the fix's parent commit,
graded with `scripts/swe_grade.py` against the maintainer's tests plus a blind rubric A/B/C); selection rule fixed before running (newest first, 4/3/3, mechanical drops);
every accepted draft approved; kill line 2 or fewer A of 10, success 5 or more; $1.00 per job, $8.00 per batch; no push or comment upstream by any automation; fix D1 and D6
first. Deviation from Claude's brief: the issues are not currently open ones.

Claude's checks on 2026-11-11 (public GitHub reads only, nothing cloned or run):

| # | Point | Status | Claude's view |
|---|---|---|---|
| G1 | Kill and success lines: 2 or fewer A of 10 has probability 2.0% if the true rate were 57%; 5 or more has 3.3% if it were 20% | **verified** (binomial, `0.020` and `0.033`). Also: at a true rate of 35% both "kill" and "success" happen about 25% of the time | The lines separate clear cases and leave a wide middle; Fable already says 3-4 means a second batch. |
| G2 | Candidates activity: Fable's "boltons may be inactive (last push Feb 2025)" | **verified wrong**: pushed 2026-10-25; humanize 2026-11-02 (74 open issues); cachetools 2026-11-10 (3 open issues) | All three are active. boltons' licence reads `NOASSERTION` on GitHub (Fable's web search says BSD); confirm before use. |
| G3 | At least 10 issues closed by a merged PR in 12 months | **partly verified**: issues closed with a linked PR since 2025-11-11: humanize 13, cachetools 17, boltons 13 (merged PRs 85, 34, 51). The test-and-non-test diff, 150-line and 8,000-character filters were not applied | Enough raw material for 4/3/3 after filtering, probably; cachetools is the safest. |
| G4 | Suite time under 120 s offline in the sandbox, size under 30,000 lines, installable into one image | **unverified** (Fable and Claude) | Must be measured (clone locally, run pytest in the sandbox image) before selection. |
| G5 | Retrospective instead of open issues | design choice | Gives an objective grade; costs contamination risk (recent issues may be in training data) and is not the "real unassisted work" of the original question. Option: run this first, then a small second phase of 5 truly open issues graded by the rubric only. Atha decides. |
| G6 | Sandbox environment per repository (`scripts/build_env_from_base.sh`, `scripts/check_env_image.py`) | **unverified** (Fable assumed, did not look) | A real cost: a config change per repo plus a pinned image. Check it before promising a date. |
| G7 | Fix D1 and D6 first; E1 and D5 not blocking (check `usd_complete`; the grade comes from the maintainer's tests and a reader, not from acceptance) | design, consistent with the fix queue in section 10 | Agree; it also gives the fix queue a concrete deadline. |

**Decision (Atha, 2026-11-11):** run the **retrospective** version first (issues closed by a merged PR, run at the fix's parent commit, graded by the maintainer's tests plus the
blind rubric). A second phase of truly open issues is not decided; it depends on the first result. Still to do before a first job: measure the three candidates (suite time under
120 s in the sandbox, size under 30,000 lines, one pinned image each), confirm the `boltons` licence, build and check one sandbox environment per repository, and fix D1 and D6.

## 12. Session B4: scoreboard definition ([`FABLE_SCOREBOARD_DEFINITION.md`](FABLE_SCOREBOARD_DEFINITION.md))

Fable defined outcome categories, money, decisions, human wait (upper bound), judge and the unknowns from `job.json` alone. Claude checked the field names against the 150 real
`job.json` files in `~/pilot3a_live/jobs` on 2026-11-11 (read-only; counts below are from that scan):

| Point | Result |
|---|---|
| Jobs by kind | 119 code, 26 research, 5 issue |
| Code and other states | APPLIED 62, REJECTED 18, ABANDONED 14, REVIEW_READY 20, AGENT_FAILED 5, DRAFT_FAILED 1, BLOCKED 1, REPORT_READY 22, HANDED_OFF 5, RESEARCH_INCONCLUSIVE 2 |
| `as_is` | present on exactly the 62 APPLIED jobs, as Fable assumed |
| Decision log | the entries sit under `log` (not `decisions`); `what` values seen: `created` 150, `intaken` 119, `state` 752, `approved` 107, `limits_shown` 285, `confirmed_by_flag` 285, `key_from_file` 311, `staged` 38, `stage_started` 169, `retry` 11, `redraft` 16, `research_ok` 1. Fields seen on entries include `by`, `via`, `as_is`, `commit`, `patch_sha256`, `old`, `new`, `at`, `note`, `draft`, `sha` |
| `confirmed` entries | **none**: every confirmation is `confirmed_by_flag` (all runs used `--yes`), so the "interval under `--yes` is zero" pitfall applies to every job; human wait must come from `approval.at` and the stage `ended_at` values |
| Judge coverage | 10 judge stages across 119 code jobs: the judge ran on about 8% of code jobs, so "judge verdict" is missing for most of them |
| Stage kinds | draft 133, agent 118, judge 10, write 13, plan 26, research_worker 84, report 23, check 23, research 1 |

**Verdict:** the definition fits the real data; build the script from it (a new script: `pilot_report.py` works on run directories). Two things to carry into the script:
the log key is `log`, and `by` cannot distinguish Atha from Claude, so Atha's time stays an upper bound. Fable's "what the script cannot know" list (re-issues of one issue,
who decided, minutes of attention, Claude's token cost, spend of cut-off stages) stands; the ledgers are the money record, so the script should read them for spend and use
`job.json` stage `usd` only as a cross-check.

## 13. Session B3: injection and approver-deception attacks ([`FABLE_INJECTION_ATTACKS.md`](FABLE_INJECTION_ATTACKS.md))

Fable designed sixteen attacks (A1-A16), all with canary payloads and none run. Ranking by likelihood times impact; first five to run: **A13** (the `for_human` sentence the approver reads
on the phone is never checked against the tests), **A8** (the run wedge: one sentence in any text the agent reads ends the job for good), **A6 with A7** (an instruction inside a test failure
message, with and without the data label), **A2** (repository text reaching the issue writer, which then writes the "human" issue), **A10** (the forged verdict, as a hand-written fixture
with no model); A9 costs nothing and runs alongside. Predicted to succeed today: A1 (by design), A8, A9, A10, A13; likely A3, A5, A6, A7; likely to fail A4, A16.

| # | Point | Status | Claude's view |
|---|---|---|---|
| H1 | A15 (job title in the CSV export, formula injection) | **checked, correction**: `ledger/api.py` `_jobs_csv` writes only `job`, `state`, `stages`, `cost_usd`, `running`; the title is not in the CSV, and job ids and states are generated by Argus. The CSV half of A15 is not exploitable through a title. The markup half remains untested (React escapes; `html.escape` in the control page) | Downgrade A15 to the viewer and control-page rendering only. |
| H2 | A8 (run wedge), A9 (error text with a key, no redaction), A7 (`RunValidation` unlabelled) | the underlying gaps were **verified** by Claude (sections 8-9: `codetask/tools.py:254-257`, `425-432`; grep finds no redaction) | These attacks need the fixes, not more evidence: A8 and A9 should be turned into the **regression tests of D1 and D7**, not run as experiments. |
| H3 | A13: `for_human` is "written by the drafter, not checked by a test" | **verified** as a documented statement in every `DRAFT_REVIEW.md` ("For the human (written by the drafter, not checked by a test)") | The highest-impact item because the approver reads that sentence on a phone. Consider a cheap guard first (show it only next to the list of new test names and the changed files). |
| H4 | A10 (forged verdict) as a hand-written fixture, no model | design | Becomes the forger fixtures for the canary-and-nonce fix (E3). |
| H5 | A11 (false conflict once `ReportConflict` exists) | not testable yet | Becomes a test of the `ReportConflict` MVP. |
| H6 | A1 succeeds by design (the issue is the instruction) | by design | Consistent with the outside-repo protocol: issue text is untrusted when it comes from outside, so the human reading the issue before `issue start --sha` is the defence. |

**Proposal:** run A13 as the first experiment (needs one model, about $0.05, a practice-app clone), fold A8, A9, A10 and A7 into the tests of the fix queue (section 10), and keep A2, A3, A5, A6 for a later
small batch of five or fewer runs. Nothing from this list is run yet.

## 14. Planning session: backlog and order ([`FABLE_PLAN_2026-11-11.md`](FABLE_PLAN_2026-11-11.md))

Fable merged the findings into a backlog (SB, DOC, FIX-A, ENV, PRE, EXP, FIX-B, RC, GATE, VF, FIX-C, GUARD, ADV), three phases with checkable exits, decision points for Atha, a cut list, and a schedule for 6 and
2 hours of Atha per week. **Proposal, not adopted.** Claude's assessment:

**Agree**
- Order: scoreboard (SB) and doc corrections (DOC) first; FIX-A (D1 run wedge + D6 `RunValidation` label) and the environment work (ENV) next, in parallel; the outside experiment (EXP) before `ReportConflict`,
  the terminal gate and the verdict fix, since the experiment supplies their evidence and they are wasted on a "kill".
- FIX-A as one PR: D1 (`codetask/tools.py:254-257`) and D6 (`codetask/tools.py:425-432`) are in the same file (verified). E1 and E2 (money) as a separate, later PR (FIX-B) so a money review cannot hold the experiment.
- D3 (`smoke_models.py`) is a sentence in `AGENTS.md`, not a code change. Skip running attack A13; do GUARD instead. Drop the `applied` judge warning (the judge ran on 10 of 119 code jobs).
- The rule: a number in a status document is copied from a generated file under `verification/` and cites it; `PENDING.md` holds open items only, by backlog id.
- The kill line and what each outcome changes (2 or fewer A: stop hardening after FIX-B; 5 or more: phase 3; 3-4: a second batch, budgeted now).

**Adjust (Claude proposes)**
1. **Measure the dominant cost.** The reviews say Claude's token cost and Atha's real hours are the main costs and recorded nowhere, yet the plan never schedules recording them. Add a tiny item to SB: one weekly line
   (Atha hours, Claude usage from the usage page) in a file under `verification/`, entered by Atha; the scoreboard cites it. Without it "cost per applied change" excludes the expensive part.
2. **ENV starts with one repository.** Run a one-repo spike (`cachetools`, smallest and cleanest) end to end (environment, check, one issue) before committing to three. This is the plan's own fallback, taken first,
   because ENV is the largest unverified cost.
3. **FIX-A implementation notes:** ~~bump the `RunValidation` tool version when the label is added~~ **corrected 2026-11-11 (Claude's own error): do not bump it.** Memo keys carry the tool version and the next LLM step's key carries the messages, so a bumped version re-runs the tool on resume, changes its text and re-buys the model's reply; a run in flight must replay its stored text. A test now guards that the version stays. The D1 handler must also cover a lone surrogate before `memo.put` (done).
4. **GUARD needs a data check:** confirm what the ledger's draft endpoint (Stage 14) returns (new test names, changed files, `for_human`) before promising the viewer change; if a field is missing it becomes a ledger change first.
5. **EXP effort "M" is optimistic:** ten jobs through draft, approve, agent and judge, plus blind grading and per-repo environments; plan for two or three sessions of waiting, not one.
6. **The 2 hours per week capacity** reaches the verdict only at week 8; say so to Atha before starting, so the schedule is a choice.

**Decisions needed from Atha**
- ADV: an advisory lane in `AGENTS.md` (advisory output such as leak warnings needs a short spec and tests, not 25 mutants and a full `verify_at`), yes or no. No: B12 (`leaks` "not checked" versus "none") is dropped.
- Approve the order above (phase 1: SB, DOC, FIX-A, ENV spike, GUARD, PRE), and which weekly capacity to plan for.
- Whether the plan replaces the order in `PENDING.md` (DOC would reorder it and add the backlog ids).

**Decisions (Atha, 2026-11-11):** (1) **Advisory lane: yes**, with the checklist in `AGENTS.md` (section "Advisory lane"); `leaks` "not checked" versus "none" (B12) stays in the backlog under it.
(2) **Capacity: 4 hours of Atha per week**, so the plan's reachable points are between its 6-hour and 2-hour columns: phase 1 exit around week 3, the experiment verdict around week 6.
(3) Claude proceeds with phase 1 in the plan's order (SB done in #444, DOC, FIX-A, a one-repository ENV spike, GUARD, PRE). Claude's adjustments in this section (weekly record of Atha hours and Claude usage,
ENV spike first, FIX-A notes, GUARD data check, EXP effort) are adopted unless Atha objects.
