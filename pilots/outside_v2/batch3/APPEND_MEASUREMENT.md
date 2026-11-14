# Batch 3 issues re-drafted after APPEND-TESTS (2026-11-14)

What: the drafter run again on the same 8 issues, same base commits, same environment (`ledger_py312_up2`), same issue text, **draft stage only**: the 8 new jobs stop at `AWAITING_APPROVAL`; none was approved, no agent ran, nothing was applied. Harness: main at 98e190f (APPEND-TESTS #506 and the sandbox split #509 merged). Money: **$0.0845** of drafter spend (Atha approved about $0.10 on 2026-11-14). Data: `append_measurement.json`.

Question: batch 3's 8 patches all put their tests in a new file (a habit that does not match how the maintainers write tests). With a changed_tests entry that may append, does the drafter append instead?

| issue | new job | drafter spend | new test files | changed test files | batch 3 (same issue) |
|---|---|---|---|---|---|
| more-itertools#1252 | j20261114_030430_3ce6 | $0.0103 | 0 | tests/test_more.py (append, 1335 B) | 1 new file |
| more-itertools#1250 | j20261114_030635_893a | $0.0080 | 0 | tests/test_more.py (append, 1424 B) | 1 new file |
| more-itertools#1247 | j20261114_030922_6085 | $0.0165 | 0 | tests/test_more.py (append, 1893 B) | 1 new file |
| more-itertools#1192 | j20261114_031225_ff91 | $0.0064 | 0 | tests/test_more.py (append, 783 B) | 1 new file |
| more-itertools#849 | j20261114_031442_6105 | $0.0106 | 0 | tests/test_more.py (append, 1528 B) | 1 new file |
| more-itertools#1152 | j20261114_031621_cb2d | $0.0078 | 0 | tests/test_more.py (append, 1344 B) | 1 new file |
| more-itertools#813 | j20261114_031918_6ce2 | $0.0150 | 0 | tests/test_more.py (append, 3256 B) | 1 new file |
| more-itertools#1098 | j20261114_032235_dad8 | $0.0099 | 0 | tests/test_more.py (append, 3383 B) | 1 new file |

**Result: 8 of 8 drafts append to the existing `tests/test_more.py` and create no new file; in batch 3 it was 0 of 8** (every batch 3 draft created one new file). All 8 appends are pure additions (the old text kept as a prefix).

What this does and does not say:
- It says the habit changed at the draft stage under the new rule. It does **not** say the tests are better: they were accepted by the harness's checks (red before the fix, baseline run), not read by a human here, and nothing was run past the draft. Whether the agent's patch then passes the maintainers' tests is a separate question that needs approving the drafts (about $0.05 to $0.10 per job).
- One repository, one model (DeepSeek flash), n = 8, one run each: a count, not a rate.
- Where the test goes inside `tests/test_more.py` is always the end of the file; whether a test sits in the related TestCase class (the maintainers' habit) is the later `insert_into` question and is not addressed here.
- The 8 new jobs are left at `AWAITING_APPROVAL` in `jobs/` (not part of this commit).
