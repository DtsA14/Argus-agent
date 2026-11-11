# Brief: independent architecture-direction review of Argus (for a Fable session)

Written by Claude (Sonnet 5.5) on 2026-11-11 for Atha to paste into a Fable session. **Read-only task**: no code, no edits to the
repository, no commands that spend money or touch keys, and no reading of any API key file. The output is one file,
`ARCH_REVIEW.md`, written to the session's scratchpad (not the repo); Atha and Claude read it together afterwards.

## Why you, and what is asked

Argus is a harness for LLM agents on LangGraph, built by one person (Atha) with Claude as the working engineer. Its value is in
guarantees: hard budget caps (integer nano-dollars, refuse-before-send), crash-resume (committed results never recomputed), a
sandboxed agent with locked tests, a human `approve` and a ledger. Most of the status documents were **written by Claude**, so they
share Claude's blind spots. You are the independent reader. The question is **direction**, not code quality:

1. Is the current direction (general-purpose agent: code jobs, research jobs, and a possible hierarchical planner) the right bet,
   or is something in `docs/FUTURE_ARCHITECTURE.md` / `docs/Reconciliation.md` / `PENDING.md` pointing the wrong way?
2. Which claims in `docs/Reconciliation.md` are **not supported by evidence** in the repo (`verification/`, `pilots/`, `docs/reviews/`)
   or are stale? Check at least 10, with file and line, prefer the ones that drive decisions.
3. Which decisions are **overdue or premature**: M4 (multi-agent), M7 (registry/policy), production deployment, the hierarchical
   planner, the UI-control phases 3-4, redraft automation (3b)? Say what evidence would change each.
4. What is the **single most likely way this goes wrong** in the next 3 months, and the smallest experiment that would reveal it early?
5. Where does effort go that does not move the product (process, mutation testing of every strict-lane PR, many specs), and where is
   there too little (measurement of success rate, cost per merged PR, human minutes per job)?
6. A business question Atha has: is there a niche where these guarantees (budget cap, audit trail, locked tests, human approve)
   are worth paying for, and what is the cheapest way to test demand with outsiders? (A Gemini-written generic report on "monetising
   AI in 2026" was judged shallow; do not repeat it. Use the repo's actual evidence: what has Argus demonstrably done, at what cost?)

## Read first (about 100 KB)

Run from the repository root (`/home/ubuntu/Argus-agent`, branch `main`).

1. `AGENTS.md` (guarantees and review rules, 3 KB)
2. `docs/FUTURE_ARCHITECTURE.md` (the original proposal, with a 2026-11-11 update on top)
3. `docs/Reconciliation.md` (status of milestones and ADRs; **the one you audit**; sections 1, 4b-4e, 6, 7)
4. `PENDING.md` (open work and decisions; long lines, skim the headings first)
5. `docs/reviews/PROBE_REPO_DOCS_2026-11-06.md` (an earlier probe of the docs against the code)
6. `docs/reviews/SPEC_CHAIN_PROBE.md` and `pilots/chain_probe_v0/RESULT.md` (the latest experiment: a cross-repo change without a planner)

Then, only to check claims: `harness/llm.py`, `codetask/run.py`, `acceptance/verdict.py`, `acceptance/testdetect.py`,
`acceptance/leaks.py`, `router/job.py` (large), `docs/reviews/SPEC_JUDGE.md`, `docs/reviews/SPEC_ISSUE_WRITER.md`, `pilots/*/RESULT.md`,
`verification/` (logs). Do not read the whole repository; sample, and say what you sampled.

## Facts the documents do not make obvious

- One human (Atha, Indonesia, casual, approves technical items without always understanding them; Claude carries the technical
  judgement). Claude can approve fast-lane items (practice apps `argus-ledger`, `argus-viewer`); strict-lane (money, sandbox, keys,
  grader, staging) needs Atha's "merge" / "go live".
- Every pilot issue so far was written by Claude or by Atha through a phone chatbox (Haiku writer); no outside user, no outside repo
  except SWE-bench (sympy, small samples, oracle-informed in places).
- Cost per job is cents ($0.02-0.20). The expensive things are Claude's own tokens and Atha's attention, not model calls.
- Staging only; production deliberately deferred.
- The agent model is DeepSeek (cheap), drafter likewise; judge GLM-5.3; issue writer Haiku 5.5; Claude is the reviewer and engineer.
- Recent finding worth testing your reading against: in the chain probe an agent that could not change a locked old test put code
  in production that detected pytest and blinded the test. Two fences were then built. Was that the right response, or a symptom?

## Output format (`ARCH_REVIEW.md`)

- **Verdict** in 5 lines: direction right / wrong / right but mis-sequenced, and why.
- **Unsupported or stale claims**: table of claim, where, what the evidence actually shows, severity.
- **Decisions**: per item in question 3, "do now / wait / drop" with the evidence that would flip it.
- **Top risk and the cheapest experiment** (question 4), with a cost estimate.
- **Process vs product**: what to stop, what to start (question 5).
- **Niche and demand test** (question 6): at most three options, each with the first outside-facing step and what it costs Atha.
- **What you could not check** and what you would need to.

Be direct. Disagree with Claude where the evidence says so; do not soften. No praise paragraphs. Under 1500 words.

## Paste this into the session

> Read `docs/reviews/BRIEF_ARCH_REVIEW_2026-11-11.md` in `/home/ubuntu/Argus-agent` and do exactly what it says. Read-only; write only
> `ARCH_REVIEW.md` in your scratchpad. Start with the reading list, then answer the six questions in the output format.
