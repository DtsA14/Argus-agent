# Research -> issue -> code, by hand (athena, 2026-11-16)

n = 1, kept apart from the scoreboard figure. The chain a one-prompt connector (PENDING, parkiran) would have to automate, run step by step with Claude relaying and Atha approving.

| Step | Job | Result | Cost |
|---|---|---|---|
| Research: BEI trading rules now | j20261116_081333_0a18 | REPORT_READY, claim checker 14 supported / 2 partial / 0 unsupported; 2 findings conflicted, 1 question (trading hours, settlement) found nothing | $0.1399 |
| Web search by Claude (2 queries) | n/a | resolved the conflict (ARB 15% -> 7% from 19 Oct 2026, Rp11-14 ARB Rp1 from 20 Oct, OJK: 7% only to 31 Dec 2026); min price Rp50 -> Rp1 from 28 Sep 2026; primary IDX source not found, all secondary | not metered |
| Issue writer (Haiku 5.5), 2 turns | j20261116_084611_3ee5 | issue written, then corrected | $0.0263 |
| Draft, agent | j20261116_085332_afdf | DRAFTED (4 of 7 submits), DONE in 13 steps, no retry | $0.0590 |
| Apply | | APPLIED 705db5b (athena master, not pushed); athena suite 915 passed, 0 failed (908 before) | |

Total about $0.2252 (research $0.1399, issue $0.0263, code $0.0590).

**What the chain found that matters**
- athena's own `IDX_MIN_PRICE = 50.0` was out of date (its docstring called the floor "long-stable"); and its flat 15% ARB buffer was left alone on purpose, because the 7% ARB is temporary (to 31 Dec 2026) and 2027 is unclear.
- The research report was honest about its limits (conflicts, unanswered questions) and had no primary source; a human-run web search was still needed to settle the conflict.

**What did not work without a human**
- The issue writer's first issue had four wrong example numbers (entry 0.5 raises ZeroDivisionError; 1.5 is rounded to 2; 1.2 to 1; "stop 47.0" is 45.0). Claude found them by running `compute_position_size` with the floor set to 1.0 in memory and sent the real outputs back as a reply. Nothing in the harness checks an issue's example numbers against the code: Claude was that gate. A draft built on them would have produced tests no agent could pass.
- Research -> issue was relayed by hand (Claude wrote the question and the message).

Human actions (Atha): one research go, one issue start, one draft approve, one apply, and the decision to use a plain issue instead of a PRD for one change. Frontend (`ScanResultCard.jsx` still says Rp50) not done: no node in the sandbox.
