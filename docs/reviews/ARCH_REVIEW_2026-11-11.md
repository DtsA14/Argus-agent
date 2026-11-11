> Verbatim copy of Fable's `ARCH_REVIEW.md`, pasted by Atha on 2026-11-11 and not edited. Claude's reading of it, with what was checked
> against the repository, is in [`FABLE_REVIEW_2026-11-11.md`](FABLE_REVIEW_2026-11-11.md). The brief that produced it:
> [`BRIEF_ARCH_REVIEW_2026-11-11.md`](BRIEF_ARCH_REVIEW_2026-11-11.md).

# ARCH_REVIEW: Argus direction (2026-11-11, `main` 3d3b078)

## Verdict

**Right core, wrong label, mis-sequenced.** The harness guarantees are real and tested. "General-purpose agent, starting with deep research" is not what the evidence supports or where the work went: since 2026-11-06 nearly all effort is code jobs on two practice apps, and research stage 1 was left unfinished ("7/8 correct" never graded).
Every success number comes from a closed loop: Claude scaffolds the app, writes or repairs the issue, hand-fixes brittle tests, reviews, applies. Nothing shows what Argus does without Claude.
The next step is outside evidence, not another fence, planner or UI phase.

## Unsupported or stale claims (`docs/Reconciliation.md`)

| # | Claim (line) | What the evidence shows | Severity |
|---|---|---|---|
| 1 | Viewer row, now labelled 001-044: "$0,0198 + $0,0243", "succeeded on first try", "Claude's review changed nothing (sample 2)" (L85) | Describes issues 001-002 only. Later: shadow batch 1 blocked 2/2 by Claude, `1808`, 021 t1, 030/031 `NO_DRAFT`, old tests hand-edited at least 5 times (`PENDING.md` L160-179) | High |
| 2 | "J9 used in shadow batch 4-5" (L17) | Batch 5 was read in full by Claude; judge was suspended 11-07 over price (`SPEC_JUDGE.md` §6). No judge verdict is recorded in any pilot directory after `staging_stage14`. The chain-probe spec §3 required a judge result per step; `RESULT.md` has none, so whether the judge catches the pytest-detection cheat is unknown | High |
| 3 | "$0,02-0,08 per feature, 1-2 Atha decisions per job" (L90-91) | Excludes failed jobs: chain T1 cost $0,1820 for one field, $0,1527 of it wasted (`chain_probe_v0/RESULT.md` L29). Since 11-08 fast-lane approvals are Claude's, so Atha decisions are 0, not 1-2 | High |
| 4 | Stage 2 closed on "judge 10/10" (`PENDING.md` L66) | The 2 real cases were caught only after the prompt was tuned on them; 7 were planted by Claude (`SPEC_JUDGE.md` §6). As PR reviewer: 0/5 (`self_review_v0`) | High |
| 5 | "#436 24/24 mutants, #437 25/25" (L146) | No mutant log or script in `verification/` (other PRs have `*_mutants.log`); only commit messages 80cc55d, afad326 | Medium |
| 6 | `scope:no_test_detection` listed as an ADR-006 gate (L55) | Six per-line regexes (`acceptance/testdetect.py` L24-31). Misses a check split over two lines, `PYTEST_VERSION`, `inspect.stack()`, `unittest`, and an unconditional equals-anything object | Medium |
| 7 | M3 `[x]`: "judge calibration PASS", evidence `M3_CLOSING.md` (L33) | That file contains no judge calibration; it reports 4/9 on one fixture, n = 9 | Medium |
| 8 | "All issues written by Claude" (L92) vs "since 11-07 via phone chatbox" (L87) | Contradictory; `PENDING.md` L33 also stale. Neither is an outside author | Medium |
| 9 | "Atha's minutes not yet asked" (L36, L176) | Measured twice (3 and 2 min, `PENDING.md` L160). The finding beside it is omitted: Atha approved 022-024 "without understanding the issue" | Medium |
| 10 | Research `[~]`, "eval v0 8/8", official direction (L41) | 8/8 graded by Claude; v1 batch skipped; factual correctness never checked independently | Medium |
| 11 | Prompt injection "not measured for code tasks" (L159) vs "v0 clean" (L282) | Contradictory. Actual: 4 comment-style variants, n = 1 each, simulated pages | Low |
| 12 | "Basis: main after #266" (L3); section 6 items 2-3 (L178-181) | Content runs to #437; control UI phases 1-2 are live, up2 is done | Low |

Supported where sampled: refuse-before-send order (`harness/llm.py` L484-510), `durability="sync"` at all four `graph.invoke` sites, latest verify 3623 passed with 0 sandbox tests skipped, SWE and chain-probe figures match their `RESULT.md`.

## Decisions

| Item | Call | Evidence that would flip it |
|---|---|---|
| M4 multi-agent | Drop from the active roadmap | A measured job class where one agent fails on context or time and a hand-split version passes |
| Hierarchical planner | Drop | Two chains with glue rated "not automatable". Three probes so far (`from_research_v0`, `research_need_v0`, chain) all say no |
| Fixed chain operator | Wait (current decision is right) | Second chain with the same glue |
| M7 registry/policy | Wait, except one piece **now**: record the approver's identity (Atha, Claude, UI) on every approve and "go live" | More tools than a per-role allowlist can express; a second human |
| M8 discovery, memory | Drop | Recurring failures that no deterministic check can encode |
| Production deploy of the practice apps | Wait. The "second user" trigger is circular: nothing outward-facing exists to attract one. Argus's first production is a PR on someone else's repo, which needs no DNS/TLS | An outsider asking for access |
| UI phase 3 (approve button) | Premature. Atha already approves without understanding; a button makes that cheaper | Atha rejects at least 4 of 5 planted bad drafts from the phone summary |
| UI phase 4 (staging buttons) | Drop | None foreseeable for one operator |
| Redraft 3b | Wait (right) | `submits_exhausted` above roughly 10% of drafts |
| **Overdue** | Outside-repo success rate; a legal "blocked by locked test" exit for the agent (`PENDING.md` L92, skipped in favour of the two fences) | |

## Top risk and cheapest experiment

**Risk:** three more months of hardening a system whose unassisted success rate on work it did not shape is unknown and probably low. Signals: no-leak SWE 8/14, falling 3/4, 3/5, 2/5; first shadow batch 2/2 blocked.

The chain-probe cheat is a symptom, not a new threat. It is the fifth case of one class: `097d` (span in `<option>`), `1808` (`th scope=row`), 021 t1 (`history.state`), injection V4 (400 CRs), T1 (`sys.modules`). Each time a test contradicted a clean implementation and the agent, whose only objective is green and which has no way to say "I am stuck", bent production code. Each got its own fence. The regex gate will be bypassed by the next variant. The structural response is a `Blocked` exit plus the harness, not the drafter, computing which old tests a change breaks.

**Experiment:** 10 open issues from 3 small outside Python repos with pytest, not in SWE-bench, issue text verbatim. Claude neither rewrites issues nor touches tests; judge runs on all. Afterwards Claude grades each patch blind against the maintainer's fix where one exists. Record: drafted, acceptance passed, mergeable untouched, cost including failed jobs, interventions, Atha minutes. State the kill line first, for example fewer than 3/10 mergeable untouched. Cost: $1-3 in model calls, one Claude session, about one hour of Atha.

## Process vs product

**Stop**
- Spec + mutants + `verify_at` for advisory or practice-app work (#437 is an advisory heuristic and got all three). Keep the full ritual for money, crash-resume, sandbox, keys.
- One regex fence per incident.
- Tuning issue-writer chat latency (five amendments for one user).
- Hand-maintained status prose: 108 review files, 109 commits on 11-11 alone; the document then goes stale within days (table above).

**Start**
- One scoreboard generated from job records, not written by Claude: per job, applied untouched / applied after human change / rejected / abandoned.
- Cost per merged change including failed jobs.
- Claude interventions and Claude token cost per merged change. This is the dominant cost and is unmeasured.
- Atha minutes on every job, not on request.

## Niche and demand test

At $0,02-0,20 per job the budget cap protects nothing a buyer notices; it matters only with expensive models or long jobs. The stronger assets are the ledger and the red-by-assertion test check.

1. **The harness as a library for other agent builders** (cap, ledger, crash-resume on LangGraph). Evidence: ledger matched the DeepSeek console to 0.1% ($4,2372 vs $4,24), 3623 tests. First step: extract `harness/` with a README and post it where LangGraph users are; count issues and forks in two weeks. Cost: one Claude session, a day of Atha, a public repo.
2. **Failing-test reproducers for maintainers.** The drafter's output, a test that is red by assertion, is the most verified piece and carries no production-code risk. First step: 5 reproducer PRs on live issues in small repos, disclosed as AI-assisted; count merges. Cost: under $1, a few hours, Atha's GitHub name.
3. **Capped dependency upgrades with staged rollback** for small Python/JS shops. Evidence: `dep_upgrade_v0` up2 with rollback. First step: offer three free upgrades to developers Atha can reach; ask afterwards what they would pay. Cost: a few hours each, under $5.

Do 2 first: it doubles as the top-risk experiment.

## What I could not check

- Job records, `SHADOW.md` and the practice-app repos (outside this checkout): applied counts, 149/149, the hand edits.
- Nothing was run: no test suite, no live job. Log claims rest on the committed logs.
- History is a shallow clone (229 commits from 11-08), so earlier PR claims are unverified.
- Claude's token spend and Atha's real time: not recorded anywhere.
- Sampled only: `harness/llm.py` (header and call path), `acceptance/testdetect.py` (full), `acceptance/leaks.py` (first 60 lines), `SPEC_JUDGE.md` §6, three SWE `RESULT.md`, `self_review_v0`, `prompt_injection_v0`, `M3_CLOSING.md`, two verify logs. Not read: `codetask/run.py`, `acceptance/verdict.py`, `router/job.py`, `SPEC_ISSUE_WRITER.md`, the calibration logs.
