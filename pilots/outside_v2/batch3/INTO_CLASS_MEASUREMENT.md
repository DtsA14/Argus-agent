# Batch 3 issues re-drafted after INSERT-INTO (2026-11-14): does the drafter use `into_class`?

What: the drafter run again on the same 8 issues, base commits, environment and issue text as APPEND_MEASUREMENT.md, **draft stage only** (nothing approved, no agent, nothing applied), with the harness of main at 7c499e4 (INSERT-INTO #514, SANDBOX-SPLIT #509 merged). Money: **$0.0919** for the 8 jobs (Atha approved about $0.08: this is $0.012 over, inside the stop I set at $0.12). Eight new jobs in `jobs/`.

| issue | job state | drafter spend | where the tests went | the maintainers' PR added tests to |
|---|---|---|---|---|
| #1252 split_before/after/when | AWAITING_APPROVAL | $0.0123 | new class at the end of the file | `SplitAfterTest` (3 classes would need tests; one entry per file) |
| #1250 value_chain | AWAITING_APPROVAL | $0.0070 | **into `ValueChainTests`** | `ValueChainTests` (same) |
| #1247 numeric_range | **DRAFT_FAILED** (`submits_exhausted`, 5 submits) | $0.0182 | - (the drafter had chosen `NumericRangeTests`, the maintainers' class) | `NumericRangeTests` |
| #1192 interleave_evenly | AWAITING_APPROVAL | $0.0068 | **into `InterleaveEvenlyTests`** | `InterleaveEvenlyTests` (same) |
| #849 peekable | AWAITING_APPROVAL | $0.0110 | **into `PeekableTests`** | `PeekableTests` (same) |
| #1152 numeric_range reversed | AWAITING_APPROVAL | $0.0097 | **into `NumericRangeTests`** | `NumericRangeTests` (same) |
| #813 replace | AWAITING_APPROVAL | $0.0168 | **into `ReplaceTests`** | the PR changed existing tests (no comparable class) |
| #1098 serialize decorator | AWAITING_APPROVAL | $0.0101 | new class at the end of the file | `TestSynchronized` (a new class, like the drafter's) |

**Result: 7 of 8 drafts accepted (APPEND_MEASUREMENT.md: 8 of 8); 5 of the 7 insert into an existing class (before INSERT-INTO: 0 of 8); in all 4 cases where the maintainers' PR has a comparable class, the drafter chose the same class.** The 2 that were appended at the end of the file are defensible: #1098's maintainers also made a new class, and #1252's needs three classes while the harness takes one entry per file.

**The failure (#1247), read from the job's own conversation (not a verdict on `into_class`):** the five submits were refused for: (1) a validation with more than 16 args (an old limit); (2) the changed file not run whole by any validation (an old rule); (3) **it listed existing tests of `NumericRangeTests` (`test_basic`, `test_contains`, ...) in `must_pass` as a regression check, which K1 of APPEND-TESTS refuses for an added test file ("required ... is already a test ... an appended file adds new tests")**; (4) a new test that passes on the baseline (not red) plus failures of tests it did not require; (5) a regression validation that runs the whole file and so includes the new failing tests. Rules 1, 2, 4 and 5 are ones the model can meet and are not about `into_class`; rule 3 is the one that fits the new behaviour (a model that adds to an existing class naturally lists the class's old tests as required), and it is the same K1 rule APPEND-TESTS has had since #506. One run, one failure: it could be sampling noise (the same issue was accepted in the append-only run), or a real extra friction from inserting into a class; this measurement cannot tell which.

What this does and does not say: it says the drafter picks the maintainers' class when it uses `into_class`, and does use it in 5 of 8; it does **not** say the tests are better (no reader, no agent run here), nor that the 1 failure is noise. One repository, one model (DeepSeek flash), n = 8, one run each.

Next step if wanted: a blind read of the 5 inserted blocks against the maintainers' (same protocol as APPEND_READ.md, no Argus money) and a second run of #1247 to see whether the failure repeats (about $0.02).
