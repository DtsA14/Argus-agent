# Batch 3: results so far (2026-11-13)

Status: the eight jobs ran under `PREFLIGHT_BATCH3.md` (harness commit `7ba6d2f`, judge not run). Claude's verdicts on the final patches were sealed and committed before anything below
was looked at (`SEALED.json`, #500). **Not done yet:** Atha's nonce and blind sample, the two-model blind A/B/C grades, the human reading. Nothing here is a verdict on Argus.

## Per job

| Label | Job | Cost | Agent steps | Maintainers' tests (added tests only, rule v2) |
|---|---|---|---|---|
| mi-1252 | j20261113_132449_2496 | $0.0086 | 4 | RESOLVED |
| mi-1250 | j20261113_133048_4030 | $0.0059 | 3 | RESOLVED |
| mi-1247 | j20261113_133204_88d9 | $0.0344 | 14 | RESOLVED |
| mi-1192 | j20261113_133651_af64 | $0.0033 | 3 | RESOLVED |
| mi-849 | j20261113_133741_0520 | $0.0128 | 12 | NOT RESOLVED |
| mi-1152 | j20261113_134208_04f1 | $0.0091 | 3 | RESOLVED |
| mi-813 | j20261113_134337_925c | $0.0212 | 12 | not graded by tests (rubric_only) |
| mi-1098 | j20261113_134939_136d | $0.0088 | 8 | not graded by tests (rubric_only) |

Total **$0.1041** for eight jobs (batch 2: $0.96 with the judge). Every job: one draft, one attempt, `REVIEW_READY`, no redraft or retry, **no ReportConflict, no GATE stop**.
`mi-813` and `mi-1098` are `rubric_only` and have no test grade. `mi-849`: its own added test (`test_class_getitem`) passes; the one failure, `NumericRangeTests.test_empty_reversed`, belongs to PR #1153
(issue #1152) and enters through the shared base (`247e15b3a489`; PR #1154's merge commit carries PR #1153's change). Counted both ways: 5 of 6 resolved as the script printed, 6 of 6 by each PR's own tests.

## What the new pieces did

- **Claude's verdicts (sealed): 8 of 8 reject.** Seven are `cuma perapian`: the fix is right and every patch puts its tests in a **new file** under `tests/` (test_split_empty_maxsplit.py, ...) instead of
  `test_more.py`, which rule 0 counts as test location. One (#1247) is a wide rewrite (helpers, binary search, an O(n) `len()` fallback). So by rule 0 the verdict is dominated by one habit of the
  drafter (its validation target names a new test file); it says little about whether the fixes work (6 of 6 resolved by tests). Read the blind sample with that in mind.
- **R1/R1b:** an R1 line on 6 of 8 jobs; none for #1247 (a `pycon` fence) and #1152 (no fence). R1b `changed` on #1252, #1250, #1192 (the three small, clear bugs). Where the example is a snippet with
  missing imports (#849, #813, #1098) R1 ran but R1b said `unchanged` or the example did not parse (timeit magics): neither tells anything about the patch.
- **Mode fix (#482):** no `old mode/new mode` lines in any patch.
- **Identical to upstream:** the `more.py` change of #1252 has the same git blob (`9af3065`) as the maintainers' fix. The issue text itself proposes that exact fix, so this is expected, but it is one more
  reason not to read the knowledge question as closed (`knowledge_check.json` could not answer it).
- **Grading script bug found:** `outside_v1/grade_unittest.py` creates its work directory inside the repository; `git apply` from a subfolder of a repository silently skips paths outside the subfolder, so
  the patch is not applied and a correct patch reads as failing. The copy used for batch 2 ran from the scratchpad and was not affected; the batch 3 script (`grade_unittest_v2.py`) uses a directory outside any repository.

Files: `jobs.json`, `verdicts_claude.json`, `SEALED.json`, `grades/` (script output), `logs/` (issue texts as sent, reading notes).
