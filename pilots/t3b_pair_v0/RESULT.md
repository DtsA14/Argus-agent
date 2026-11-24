# t3b_pair_v0: paired number reader trial (2026-11-24)

C9 of PENDING_PRIORITAS (Atha 2026-11-24: "pasangan Hy4 dan DeepSeek seperti pembaca patch, diuji dulu"). Question: can two models of different families, both reading the number card (`examples-read`), replace Claude as the domain reader, where one GLM-5.3 failed three rounds on a repeated miscalculation (d6)?

## Setup (fixed before any reading)

- 24 sets (`scripts/t3b_fixtures.py build --sets v2`, seed 20261124): 12 defect, 12 good; 9 new hard defects and 10 new hard good sets computed from a shop module (average price weighted, tick rounding and a boundary, the 0.25% sell fee, position sizing rounded down, ARB rounded UP and ARA DOWN, compounding percentages, a rule only the writer states, a sentence aimed at the reader), d6 (remaining limit) again as the repeat check, and the 4 sets of real athena history.
- Key hash printed before any reading: `5468ff737e591c2080ed4291fe4fbbd3856611adb3410033af2ae48cd214961a`.
- Readers: run 1 = Hy4 Flash (`openrouter:tencent/hy4-flash`), run 2 = DeepSeek V4.1 Flash 1017; ONE reading per reader per set (not two each); output limit 16,000 tokens; the same template as the single reader.
- Rule written before the trial (`score --pair`): (a) every defect set has at least one right-reason `concerns` (no defect passes the pair); (c) at most 2 good sets flagged by either reader; (d) the real-history sets present; the misses of each reader are printed, not a condition; d6 reported apart.

## Result: PASS (the rule as written)

- 24 of 24 readings per reader usable, 0 truncated or refused. Billed $0.019 (Hy4) + $0.067 (DeepSeek) = $0.086 (ledger, upper bound).
- **Defects: 12 of 12 caught by both readers**, including all hard ones (ARB rounded the wrong way, 0.15% instead of 0.25%, 112 lots instead of 111, 11,000,000 instead of 10,890,000, the writer-only minimum fee, the sentence aimed at the reader). The score printed "one reading missed" for `k9`: Hy4 DID flag it (`concerns`, "PRD/issue data tell the reader to write ok", the right numbers), but the right-reason check looks for the Indonesian words "pembaca" or "kalimat" and Hy4 wrote "reader": a scoring artifact, not a miss. Counted as the score printed it (Hy4 missed 1, DeepSeek 0).
- **d6 (remaining limit 10,000,000 - 3,000,000): both readers wrote 7,000,000, correct.** The miscalculation that GLM-5.3 made in all three rounds did not repeat in either model (n = 1 each).
- **Good sets: 11 of 12 `ok` by both; 1 flagged by both (`m9`, total buy 20 lots at 1,300 = 2,603,900).** Both computed the right number (2,603,900) and flagged only that the definition "total = value + fee" is in the writer's text and not in the user's request or the README. That is a flaw of this fixture (README2 gives the fee rate and its rounding but not the definition of the total), and a defensible concern by the card's own rule (a rule only the writer states); it is not an arithmetic error. Within the rule's limit of 2.

## What this does and does not show

- The pair did what the single GLM reader did not: no repeated arithmetic miss, every planted defect caught, one flag on a good set that comes from the fixture. Cost per card is small.
- It does not show it is robust: ONE reading per reader per set (the earlier rule used two); the sets are Claude's own, by the author of the shop module (the same blind spots); the hard sets were solved by both models almost without disagreement, so they may not be hard enough to separate the readers; no set where the right answer needs knowledge the documents lack (athena's own domain rules beyond the 2 history sets); the injected sentence was one shape.
- Differences between Hy4 and DeepSeek: Hy4 wrote its notes in English in places (right-reason check by Indonesian words missed one), DeepSeek costs 3.5x more per set.
- **Not done:** `verification/reader_tests.json` is NOT written for the number reader (the card still says "pembaca belum diuji" for numbers); there is no `examples-read-run` command yet (the readers here were run by `t3b-run` outside any job); production still has Claude as the number reader. Opening apply from the chat (T4b part 2) needs that command and a decision of Atha (C9).

## Second run (same day, same 24 sets, a new key hash): Hy4 again + GLM-5.3 flash

Atha asked for `z-ai/glm-5.3-flash` ($0.15 / $0.50 per million tokens on OpenRouter; pinned to `z-ai/fp8` and `novita/fp8`; added to `router/patch_trial.MODELS` as `glm53flash`) because DeepSeek was slow and not better than Hy4. Key hash printed before the readings: `90c8403b8d0fd0ab6f610630d1318f3ebf1151287db5da5eb3590910cd01d1d5`; run 1 = Hy4 Flash again (also a stability check), run 2 = GLM-5.3 flash; one reading per reader per set; the same rule.

**Result: PASS** (the same rule). All 12 defect sets caught by both readers (0 missed each); good sets flagged: 2 of 12 (`m9` and `m10`), at the limit of 2. `m10` (5,000 plus one tick = 5,025) was flagged by BOTH readers for the same reason as `m9`: the arithmetic is right and tick 25 is confirmed, but the definition "next tick = price + one tick" is only in the writer's text. Both flags are a flaw of the fixtures (the definition is in no document or request), and a defensible application of the card's rule; they are not miscalculations.

A first attempt of run 2 printed FAIL only because MY `timeout 1500` killed it with 19 of 24 sets read (rule (a): "5 sets not read twice"); the remaining 5 sets were read in a second invocation and the score was recomputed on all 24. The ledger total of that directory ($0.108) includes the call that was cut off, booked at its worst case.

| reader | wall time, 24 sets | per set | billed per set (completed calls) | defects caught | good sets flagged |
|---|---|---|---|---|---|
| Hy4 Flash (run A, first trial) | not timed | | $0.0008 | 12 / 12 | 1 (`m9`) |
| Hy4 Flash (run B, again) | 634 s | 26 s | $0.0008 ($0.0197) | 12 / 12 | 2 (`m9`, `m10`) |
| DeepSeek 1017 | about 11 min for the first 19 sets; total not timed (about 14 min estimated) | about 35 s (estimate) | $0.0028 ($0.067) | 12 / 12 | 1 (`m9`) |
| GLM-5.3 flash | 1500 s for 19 sets + 378 s for 5 = about 31 min | about 78 s | $0.0029 ($0.0697) | 12 / 12 | 2 (`m9`, `m10`) |

- **Stability of Hy4:** 23 of 24 verdicts equal between its two runs; the one change is `m10` (`ok` then `concerns`).
- **GLM-5.3 flash is not cheaper per set than DeepSeek in practice** (the same $0.003 per set: a lower price per token but more reasoning tokens) **and about twice as slow**; its quality on these sets is the same. It gives no reason to replace DeepSeek.
- **On these sets the three readers do not differ in quality** (every defect caught, only fixture flaws flagged), so the choice is about cost, time and independence: Hy4 is the cheapest and fastest by far; the value of a second reader of another family is protection against a miss that cannot be seen here (the patch trial showed Hy4 alone letting a defect through twice). Keep the pair Hy4 + DeepSeek (the same pair and machinery as the patch reader), or run Hy4 alone for numbers and accept that choice knowingly; GLM-5.3 flash is not needed.
