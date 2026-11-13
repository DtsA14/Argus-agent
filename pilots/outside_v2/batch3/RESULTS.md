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

## Blind sample (2026-11-13): read by a model on Atha's delegation

Nonce `AH 28` (typed by Atha after the sealed verdicts were committed, #500); seed `412ed6013a54`; sample 3 of 8: R01 = mi-1098, R02 = mi-1247, R03 = mi-1152 (`packet_key.json`, #503).
Reader: **another Claude session, delegated by Atha; not a human.** It opened only the three packets on branch `b3-packet`, wrote `atha_verdicts.json` (`_reader` says so) and `atha_reasons.json`.
`compare`: **0 of 3 flipped** (reader: reject, reject, reject; Claude: reject, reject, reject).

What this does and does not show:
- **It cannot discriminate.** All eight of Claude's verdicts are reject, so the only way to flip is for the reader to approve. A reader who rejects everything agrees 3 of 3 by construction. Zero flips shows
  that the tool and the procedure work and that the reader applied rule 0 the same way; it says nothing about whether the verdicts separate good patches from bad ones (the tests resolve 6 of 6).
- **Same reasons, not just the same word.** R01 and R03: tests in a new file (the reader checked the repo's convention from the packets' own regression targets: `tests/test_more.py::TestSerialize`, `::NumericRangeTests`).
  R02 (#1247): the O(n) `len()` fallback, the same reason Claude wrote; the reader added a simulation (20,000 random float ranges chosen near the boundary, 3,450 took the O(n) path; not a real-world rate) and
  a cheaper fix (check `count +/- 1`).
- **Things the reader found that Claude's reading did not list:** a `getattr` helper in the #1098 tests and a `try/except AssertionError` wrapper in the #1152 tests, both "tidying" items. Claude's reasons named only the test location. They do not change a verdict (already reject) but show the reading was less complete.
- Model against model, same family possibly: not an independent human anchor. Reported as such (`PROTOCOL_FINAL_PATCH.md`, delegated reader).
