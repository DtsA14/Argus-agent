# PREFLIGHT: third outside batch (2026-11-13) — DRAFT until Atha says "go live"

Status: **draft. It is frozen by the commit that adds the line `FROZEN: go live <date>` below, which only Atha's "go live" lets anyone add; no job has been run.**
Prepared by Claude 2026-11-13 from `pilots/outside_v1/candidates.jsonl` and `validity_v2.jsonl` (validity rule v2, `VALIDITY_V2.md`); nothing new was fetched or run.

Why this batch: batch 2 ran with the harness before six changes. Since then: judge off by default (#485), validity rule v2 (#487), R1b (patched tree re-run, #485), R1 reads `>>>`
sessions (#492), the file-mode fix (#482), O2 comment narrowing (#488/#489), and approve on the FINAL patch with a sealed verdict and a blind sample (#493). This batch is **for data**:
how often those pieces fire, and whether the numbers of batch 2 hold. Eight jobs is too few for a rate; nothing here is a verdict on Argus.

## What is run

Eight jobs, one per issue, each `argus code` with the issue's title and body byte for byte, `--environment ledger_py312_up2`, `--max-usd 1.00` (the job cap must cover the drafter plus one agent attempt, $0.70 reserved; 0.50 was refused before any call, see Correction), the rules of batch 2: at most one plain
`redraft` after `DRAFT_FAILED`, one `retry` after `AGENT_FAILED`, every draft the harness accepts is approved, harness frozen for the whole batch, nothing is applied (`applied` is never used),
after `BLOCKED/test_conflict` nobody uses `--not-a-conflict` unless Atha decides it, a `test_detection` stop is final for the job. **Changes from batch 2:** the judge is off (not run; no
`NOT_JUDGED` to count), and the verdict is on the final patch (`PROTOCOL_FINAL_PATCH.md`: Claude's verdicts are written and sealed first, then Atha chooses the nonce and reads the blind sample).
No controls this time (batch 2 had three): the question is the new pieces, not the old issues.

All eight are more-itertools, so **one repository**: the result is narrower than batch 2's two. boltons has no eligible issue left.

| # | Issue | Closed | Fix PR | Base (12) | Added F2P / P2P | Group | Source diff | Title |
|---|---|---|---|---|---|---|---|---|
| 1 | more-itertools#1252 | 2026-09-04 | #1253 (1 commit) | `d92f081a0897` | 1 / 595 | tested | 12 | split_before/split_after/split_when disagree with themselves on an empty iterable (maxsplit) |
| 2 | more-itertools#1250 | 2026-09-03 | #1251 (1) | `bc8be1013ac9` | 1 / 596 | tested | 4 | value_chain swallows a TypeError raised while iterating an argument |
| 3 | more-itertools#1247 | 2026-09-02 | #1248 (1) | `2fe1b2eeb9d7` | 2 / 593 | tested | 53 | numeric_range: len(), `in` and index() disagree with the items produced, for float steps |
| 4 | more-itertools#1192 | 2026-06-30 | #1193 (1) | `5d946b3590bf` | 1 / 585 | tested | 3 | interleave_evenly([]) raises IndexError |
| 5 | more-itertools#849 | 2026-04-14 | #1154 (3) | `247e15b3a489` | 2 / 575 | tested | 5 | TypeError: type 'peekable' is not subscriptable |
| 6 | more-itertools#1152 | 2026-04-13 | #1153 (1) | `247e15b3a489` | 1 / 575 | tested | 10 | Minor bug in numeric_range() |
| 7 | more-itertools#813 | 2026-03-31 | #1126 (1) | `c0ed9d187906` | 10 / 703 | **rubric_only** | 22 | Optimize replace itertool |
| 8 | more-itertools#1098 | 2025-11-12 | #1099 (1) | `04d266400d31` | 1 / 558 | **rubric_only** | 34 | Decorator version of serialize() |

Selection rule (mechanical, applied to the 17 candidates of `candidates.jsonl`): group `tested` under rule v2 and not used by batch 1 or 2 (six: the rows 1 to 6; #1214 is `invalid`, the others used);
then two of the three `rubric_only` ones (#813, #1041, #1098) to make eight. **This choice is a judgment, not mechanical:** Claude proposed #813 and #1098 and Atha agreed in chat; #1041 ("Add `running_mean`?", an open design question
rather than a defined change) stays in reserve, used only if one of the eight cannot be set up, replacing it in the same row. Newest-closed-first would have given #813 and #1041.
Row 5 and row 6 share a base (two issues, two PRs; one issue per fix PR holds). Rows 7 and 8 are graded by the blind rubric only: the issue may name the API differently from the fix.
Run order: the table's order (newest closed first), one job at a time. Full SHAs and issue bodies are fetched at the moment of the run. One worktree per issue is made from `~/outside/more-itertools`
at the listed base (the old `~/outside/wt` worktrees were removed 2026-11-13 and are recreated).

## What is counted (per job, from the job's own files, written down before the first job)

1. **R1 and R1b lines:** what R1 said at the base (now including `>>>` sessions); what R1b said on the patched tree (`changed` / `unchanged`, and the direction by reading: R1b does not give it);
   whether Atha finds either useful when approving.
2. **ReportConflict:** used or not; confirmed or not; the failed checks of an unconfirmed one; `retry --not-a-conflict` used or not (and Atha's reason).
3. **GATE:** runs stopped by `test_detection`; for each, Claude reads the hit and writes whether it is a real detection/forging or a false catch. Also whether O2's narrowing changed any outcome.
4. **Verdict on the final patch:** Claude's sealed verdict per job (approve = applied as it is; "needs tidying only" counts as reject, reason starts `cuma perapian:`); then, per `PROTOCOL_FINAL_PATCH.md`,
   the blind sample for Atha (`ceil(7 or 8 / 3)`), its reads and flips. Recorded as "0 human minutes, approved by the model" per job.
5. Cost per job from the ledgers; human minutes per job when Atha gives them; machine time per job.

## Grading (after all jobs)

- **Maintainers' tests** (rows 1 to 6): the PR's test files in the Argus sandbox, `pilots/outside_v0/grade_unittest.py` (pytest hides `subTest` failures), validated first with the maintainers' fix.
- **Blind A/B/C rubric** (all eight), by **two** models from a shuffled package (issue and final patch only), before the key is opened; Atha grades three or four as the anchor and the disagreements are reported.
  Rubric text, to be read by Atha before it is frozen: **A** = resolves the issue as stated and I would apply the patch exactly as it is; **B** = the behaviour is right but the patch needs tidying or has a small
  flaw (file mode, a test in the wrong place, an exception wrapper, wider than the issue) — a file-mode change counts as a flaw, as Fable ruled; **C** = does not resolve the issue, or breaks something else.
- Reported **two ways** as before ("as is" and "mode artefact removed"), per job and as counts; the protocol's lines (kill at 2 or fewer A, success at 5 or more) are **not** applied to eight jobs.
- A knowledge note, not a control: `knowledge_check.json` (2026-11-13) could not tell whether the model remembers these issues (it answered "no" even on the old control), so contamination is **open**.
  The closing dates (2025-11 to 2026-09) are listed so a later check can split the results by date.

## Caps and stops

`--max-usd 1.00` per job (a reservation ceiling: batch 2 spent $0.04 to $0.17 per job before the judge); the batch stops at **$2.00** real spend, or when one job's real spend passes $0.50, or on any run that ends outside the states above. Batch 2 cost $0.96 with the judge, about 77% of it the
judge; the estimate without it is $0.25 to $0.40 for eight. The deepseek key is used through `--key-file` (Atha's file; Claude never reads it), after Atha's "go live". Disk had 4.2 GB free (91%) on 2026-11-13: check
`df` before the first job and between jobs; a failed run from a full disk is not a result.

## Known limits

One repository; eight jobs (counts of what fired are data points, not rates); the two `rubric_only` rows have no maintainers' test grade; Claude's verdicts and one of the two blind graders are the same family of model
(`PROTOCOL_FINAL_PATCH.md`: this is a calibration of one reading against another, not an independent judge); RC and GATE still have no synthetic negative cases (Fable's item 5), so "nothing fired" is not evidence that they work.

## Go live

FROZEN: go live 2026-11-13 (Atha, in chat: "Ok bereskan docker dan go live"). Harness commit for the whole batch: `7ba6d2fee09169eda9e0b4159f817fb8492dbeda` (pilots/ files only change after it). Docker was cleaned first: 788 unreferenced dangling images removed, 10 kept because a pin or a job needs them, all 20 pins checked present; disk 91% -> 59%.

## Correction (2026-11-13, before any job spent money)

The draft said `--max-usd 0.50`. The first `argus code` (more-itertools#1252, job j20261113_132406_bf0b) was refused at admission, spent $0.0000 and was abandoned: "$0.5000 left for the drafter, one attempt needs $0.70". Batch 2's `1.00` is restored. The real spending limits that Atha approved are unchanged: the $2.00 batch stop and the $0.50 real-spend stop per job.
