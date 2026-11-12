# Outside experiment v0, variant 1: result (2026-11-12)

Ten issues (boltons 5, more-itertools 5), two batches, one job each, harness frozen, judge on every job, about $1.9 in total (from the job `status` logs; the ledger is the exact source).
Grading: the maintainer's tests of the fix PR (their test files overlay the base tree, per test, in the Argus sandbox: no network, read-only, no capabilities) plus a blind A/B/C rubric by a fresh Claude session (Fable 5.2, from the package of shuffled issue + patch, before the key was opened).
Scripts: `grade_pytest.py` (boltons), `grade_unittest.py` (more-itertools: pytest without the subtests plugin does not report `subTest` failures, so `#1344` and `#1275` looked green under pytest; they are graded with `python -m unittest`).
Each variant is validated first: the maintainer's fix must pass all its tests, otherwise the setup is wrong, not the patch (all fix runs: all pass).

| Issue | Instance | Blind | Tests (maintainer) | Judge | Note |
|---|---|---|---|---|---|
| boltons#383 PathLike | valid | A | resolved (F2P 2, P2P 6) | PASS | |
| boltons#439 IndexedSet | valid | A | all setutils tests pass, but **none fails on base** (perf issue); the 3 F2P are another bug of the same PR (BarrelList), not this issue | NOT_JUDGED | tests cannot tell right from wrong here; A rests on the blind reading |
| boltons#480 FilePerms | **invalid** | (C) not counted | `test_fileperms_revoke` passes on base | PASS | the repro already passes at the base (`0o600`; `_update_integer` already masks the old bits): already fixed. Argus could not reproduce and wrote an unrelated type check; the judge PASSed it |
| boltons#343 wraps | **invalid** | (C) not counted | not run | NOT_JUDGED | wrong base (Amendment 2) |
| boltons#261 wraps kw-only | **not gradable** | (C) not counted | not run | NOT_JUDGED | repro already passes at the base (Amendment 2) |
| more-itertools#1344 eq/hash | valid | C | **not resolved**: F2P `test_hash_above_maxsize` fails (modulo-7 length key) | BLOCK | first draft was on target; the patch after one `retry` is wrong |
| more-itertools#1308 bucket | valid | A | resolved (F2P 1, P2P 619) | PASS | |
| more-itertools#1304 ichunked | valid | A | resolved (F2P 2, P2P 617) | PASS | |
| more-itertools#1293 seekable | valid | A | resolved (F2P 3, P2P 615) | NOT_JUDGED | blind reader: the old `chain` branch may remain as dead code (not visible in the diff) |
| more-itertools#1275 reversed | valid | A | resolved (F2P 2, P2P 613) | NOT_JUDGED | |

## Count and the lines (pre-registered for 10: kill at 2 or fewer A, success at 5 or more A; not moved)

- Counted: 7 valid. **6 A, 1 C.** Of the 6 A, 5 have a maintainer test that fails on base and passes with the patch; #439 is an A on reading only.
- Worst case, if the three invalid instances are counted as failures and #439 is not an A: **5 A of 10**, still on the success line. So the verdict does not depend on how the invalid ones are treated; it does depend on the blind reader, who is one model (a stronger A/B/C needs a human or a second reader).
- Cost per A: about $0.3 (about $1.9 over 6); the line was at most $0.50. Human minutes per A: not measured per job in this run (approve was by Claude; Atha's minutes were the two decisions and the file hand-off); the "10 minutes per A" half of the success line is therefore **not verified**.
- Upper bound: the issues are recent and small; the models may have seen them (named limit of the protocol). The bundle of other bugs in a fix PR (boltons #440, #610) makes "resolved" per issue need reading, not just a green run.

## What this showed about Argus (not about the lines)

1. **No "cannot reproduce" outcome.** On an issue already fixed at the base (#480), Argus did not stop: it drafted an unrelated change, it was approved by the rule of the protocol, and the judge PASSed it. A check "does the issue's reproduction fail at the base?" before drafting, and a drafter exit "cannot reproduce", would have caught it. Candidate strict-lane item; not started.
2. **Judge: PASS on a wrong patch (#480), BLOCK on a wrong patch (#1344), NOT_JUDGED 4 of 10** (about $0.15 each). Do not use the judge as a gate (Fable, Claude).
3. **Setup lessons:** base from the first commit of the fix, not from the merge commit (rebase merges); run the issue's repro at the base before spending money; pytest can hide `subTest` failures.
4. Claude's own reading before approve agreed with the blind grade on 9 of 10 patches; it missed #343 (a public-method regression) and read the draft plan, not the final patch, for #1344.
