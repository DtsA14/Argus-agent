# PREFLIGHT (FINAL): second outside batch, issues on code Argus did not shape (2026-11-13)

Status: **final, frozen by this commit; no job has been run.** Prepared by Claude 2026-11-13 from GitHub metadata and one mechanical check
(`validity.py`: the maintainers' test files of each fix are run, unread, in the Argus sandbox on the base and on the fix; the names and counts
printed are all anyone sees). Why this batch exists: six strict-lane changes went into `main` in under a day (R1, FIX-C, RC, GATE, VF O2) and none
has met a real job; the first batch (`pilots/outside_v0/RESULT.md`) was measured with the old prompt and the old harness. This batch is **for
data**, not for a verdict: how often the new pieces fire and whether the numbers of batch 1 still hold.

## What is run

Eight jobs, one per issue, each `argus code` with the issue's title and body byte for byte, `--environment ledger_py312_up2`, `--max-usd 1.00`,
the same rules as batch 1: at most one plain `redraft` after `DRAFT_FAILED`, one `retry` after `AGENT_FAILED`, every draft the harness accepts is
approved (Claude's own verdict is written down first), judge on every job (as data: it is not a gate), harness frozen for the whole batch. New
here: after `BLOCKED/test_conflict` nobody uses `--not-a-conflict` unless the human (Atha) decides it; a `test_detection` stop is final for the job.

### Controls (3): batch 1 issues that were valid, with batch 1's bases, to see whether the new prompt and harness move the result

| Issue | Batch 1 blind grade | Base (12) |
|---|---|---|
| more-itertools#1304 (ichunked n=0) | A, resolved | `790bb0bb2c03` |
| more-itertools#1344 (numeric_range eq/hash) | C (modulo-7 length key), judge BLOCK | `08dca284ba54` |
| boltons#383 (PathLike) | A, resolved | `ebc7a8f776de` |

### New issues (5): the rule below, applied mechanically

1. An issue closed by a **merged** pull request of the same repository, closed on or after 2025-11-12, not one of batch 1's ten, and not closed by a
   pull request batch 1 used (610, 425, 440, 445, 416, 1345, 1309, 1305, 1294, 1276).
2. The fix changes a test file and a source file (docs excluded), the source diff is at most 150 lines, the issue body at most 8,000 characters,
   no dependency or build configuration; **one issue per fix PR**.
3. **Base = the parent of the first commit of the pull request** (`pilots/outside_v1/preflight_scan.py`), the lesson of batch 1's #343.
4. **Valid = at least one maintainers' test fails on the base and passes on the fix, and nothing else of those files fails on the fix**
   (`pilots/outside_v1/validity.py`, results in `validity.jsonl`; all 15 candidates were valid).
5. Newest closed first: three from `more-itertools`, two from `boltons` (the only two eligible there; `boltons#479` shares PR 610 with batch 1).

| Issue | Closed | Fix PR | Base (12) | F2P / P2P | Title |
|---|---|---|---|---|---|
| more-itertools#1284 | 2026-09-17 | #1285 (2 commits) | `b2f3aff76330` | 4 / 609 | bucket: a failed lookup or `in` test adds a phantom key to the keys returned by iteration |
| more-itertools#1277 | 2026-09-14 | #1278 (1 commit) | `9ed3dbb0ae52` | 1 / 604 | zip_broadcast opens input iterables twice |
| more-itertools#1257 | 2026-09-08 | #1261 (2 commits) | `b656ecc0a64e` | 2 / 600 | combination_with_replacement_index mistakes None values for exhaustion |
| boltons#393 | 2026-01-28 | #394 (1 commit) | `ce7c7d2b15ea` | 1 / 40 | Bug: `research` fails to traverse identical small tuples |
| boltons#322 | 2025-12-30 | #388 (4 commits) | `0c88f25323de` | 3 / 16 | Function to format a list with commas and a final 'and'/'or' (a feature; the issue names `human_list` and shows examples) |

Full SHAs and issue bodies are fetched at the moment of the run. Full clones are in `~/outside/` (one worktree per issue at its base, as in batch 1).
The candidates that were valid but not chosen (later or earlier in the list) are in `candidates.jsonl` / `validity.jsonl`; they stay unused.

## What is counted (per job, from the job's own files, written down before the first job)

1. **R1 line** (`issue example at base: ...`): what it said, and whether Atha finds it useful when approving.
2. **ReportConflict**: used or not; confirmed or not; the failed checks of an unconfirmed one; whether a rejection is because the failing frame is in
   production code (the case C1 refuses on purpose); `retry --not-a-conflict` used or not (and Atha's reason).
3. **GATE**: runs stopped by `test_detection`; for each, Claude reads the hit and writes whether it is a real detection/forging or a false catch.
4. The batch 1 numbers for the controls against the new ones: drafted yes/no, run result, judge verdict, hidden-test grade, blind grade, cost.
5. Cost per job from the ledgers; human minutes per job (Atha's, noted when given).

## Grading (as in batch 1, after all jobs)

Hidden-test grading with the maintainers' tests of each fix in the Argus sandbox (`pilots/outside_v0/grade_pytest.py` for boltons,
`grade_unittest.py` for more-itertools: pytest hides `subTest` failures), validated first with the maintainers' fix; a blind A/B/C rubric by a
fresh session of another model from a shuffled package (issue and patch only), before the key is opened. Reported per job and as counts; the
protocol's lines (kill at 2 or fewer A, success at 5 or more) are **not** applied to 8 jobs; the controls are read against batch 1, the new five
as a rate with its width, nothing finer.

## Caps and stops

`--max-usd 1.00` per job; the batch stops at **$6.00** real spend or when one job passes $1.00. The deepseek key is used for code stages and the
openrouter key for the judge, both through `--key-file`, after Atha's "go live" for this batch. Nothing here is applied (`applied` is never used).

## Known limits

All eight issues were closed in 2025-12 to 2026-10, so a model may have seen some of them or their fixes. The two `more-itertools` controls that were graded A
are the easy end; `boltons#322` is a feature request, a different kind of task from the bug reports. Eight jobs is a small sample: counts of what fired are
data points, not rates.
