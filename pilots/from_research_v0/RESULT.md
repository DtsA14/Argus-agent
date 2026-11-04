# Pilot from_research v0: result (2026-11-04)

Plan: `PLAN.md` (one "go live" from Atha). Issue 015 on argus-ledger at 1f31e34, environment `ledger_py312_up1`.
Graded by the hidden grader in `grader/` (18 tests + a static check of the non-test diff), validated before any job ran.

| | arm B (code only) | arm A (research → code) |
|---|---|---|
| jobs | j20261104_151007_0f5f | research j20261104_151756_9829, code j20261104_152512_b93a |
| hidden grader | pass (154 tests incl. 18 hidden), static clean | pass (155 tests incl. 18 hidden), static clean |
| fix | `tuple(DEFAULT_EXCLUDED_CONTENT_TYPES) + ("text/csv",)` | `GZIP_EXCLUDED_CONTENT_TYPES = DEFAULT_EXCLUDED_CONTENT_TYPES + ("text/csv",)` |
| draft | 3 tests (1 red: CSV gzipped) | 4 tests (2 red: CSV, CSV behind login; HTML still gzipped) |
| agent | 2 attempts (first hit max_steps at 30), $0.0261 | 1 attempt, 15 steps, $0.0073 |
| drafter | $0.0123 | $0.0125 |
| research | – | $0.0546 (e1 CHECKED: 9 SUPPORTED, 2 PARTIAL; largest e1 call 8,747 output tokens) |
| total | **$0.0384** | **$0.0743** |
| Claude's decisions | 1 approve | 1 approve (+ the research question, written before) |

Arm A was applied (argus-ledger 4e947a0, `argus applied`, "the patch as it was"); arm B rejected with that reason.

Reading (n = 1 per arm: an anecdote, not evidence):
- **The research was not needed for this issue.** Arm B found `exclude_content_types` and kept the defaults with no
  documentation tool call (drafter: read/search files only; agent: no web). DeepSeek appears to know Starlette 1.5+.
  The issue was chosen to need post-cutoff docs; for this model it did not.
- **Arm A was cheaper at the agent (one attempt instead of two) but dearer overall** ($0.0743 vs $0.0384): the
  research cost more than it saved.
- **The research was right and the report carried the trap too**: its summary also offered `("text/*",)`, which would
  stop gzipping HTML. Arm A's drafter named that as a risk and the agent did not take it.
- **e1 with 32,000 output finished** (largest call 8,747 tokens, no truncation): one more checked report, no proof of
  the cap under load.
- **Next evidence needed:** an issue the code-only arm gets wrong. Until then `--from-research` stays an option, and a
  planner that chains research → code is not justified by this pilot.
