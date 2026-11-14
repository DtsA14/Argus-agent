# Three of the re-drafted batch 3 issues taken through the agent (2026-11-14)

What: after the blind read (APPEND_READ.md), three of the 8 re-drafted jobs were approved and run through the agent, one attempt each, then the maintainers' own tests were run on the final patch in the sandbox with `grade_unittest_v2.py` (the batch 3 procedure; outputs in `append_agent/`). Chosen: #1247, #1192, #1152 (draft graded B by the reader, catches the bug, not over-specified). **Not chosen: #813**, whose draft got a D (it requires padding semantics the issue never defines), so a failure there would say nothing about the append change. Nothing was applied; the three jobs sit at `REVIEW_READY` in `jobs/`. No judge, no blind grade of the patches (not part of this step).

| issue | job | agent | agent spend | maintainers' tests on the final patch | tests in the patch |
|---|---|---|---|---|---|
| #1247 numeric_range | j20261114_030922_6085 | DONE, 13 steps | $0.0211 | RESOLVED (F2P 2/2, P2P 593/593) | `tests/test_more.py` +51 (batch 3: new file `tests/test_numeric_range_float_consistency.py` +119) |
| #1192 interleave_evenly | j20261114_031225_ff91 | DONE, 3 steps | $0.0008 | RESOLVED (1/1, 585/585) | `tests/test_more.py` +22 (batch 3: new file) |
| #1152 numeric_range | j20261114_031621_cb2d | DONE, 3 steps | $0.0008 | RESOLVED (1/1, 575/575) | `tests/test_more.py` +43 (batch 3: new file) |

**Result: 3 of 3 resolved by the maintainers' tests (batch 3: the same three were resolved), and in all three the final patch now adds its tests to the existing `tests/test_more.py`, not to a new file (batch 3: new file each time).** The source change of #1247 is smaller (68 added lines against 84).

Spend of this day's measurement: drafts $0.0845 + these agents $0.0227 = **$0.1072** (Atha approved about $0.10 for the drafts and $0.15 to $0.30 for the three agents).

Caveats: n = 3 in one repository, one attempt each, one model; the maintainers' tests resolved the same three in batch 3, so this shows no loss, not a gain in correctness; the tests inside these patches are the drafter's (reader's grades: B, a new standalone class and try/except wrappers, not the maintainers' style); the patches themselves were not read by a human or graded blind here.
