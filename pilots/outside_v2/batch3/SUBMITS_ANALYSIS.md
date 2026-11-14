# #1247 rerun and why the drafter now needs about twice the submits (2026-11-14)

**Rerun of #1247** (draft only, Atha approved about $0.02): job `j20261114_073301_0d2a`, `DRAFTED`, $0.0244 (a little over the approved ~$0.02), inserted three methods into `NumericRangeTests` (the maintainers' class), **but only at submit 5 of 5** (the four before it were refused with 18, 4, 1 and 1 problems). The first run of the same issue ended `DRAFT_FAILED` after 5 submits. So the failure repeated in kind: with this harness #1247 needs every submit the drafter has.

**Submits the drafter needed (events `draft_submitted` of the `-d1` run; the limit is 5)**

| issue | batch 3 (new file) | after APPEND-TESTS (#506) | after INSERT-INTO (#514) |
|---|---|---|---|
| #1252 | 3 | 4 | 5 |
| #1250 | 2 | 5 | 5 |
| #1247 | 2 | 5 | 5 (and one run that failed; the rerun: 5) |
| #1192 | 3 | 5 | 4 |
| #849 | 3 | 4 | 4 |
| #1152 | 2 | 4 | 5 |
| #813 | 2 | 5 | 5 |
| #1098 | 3 | 5 | 5 |
| total | **20** | **37** | **38** |

**The submits nearly doubled with APPEND-TESTS (#506), not with `into_class`**: 2 to 3 per issue became 4 to 5, right against the cap of 5 (one draft in nine already ended `DRAFT_FAILED`).

**Why (rejection lines in the drafter's own conversation, one count per problem line):** after APPEND-TESTS the main reason is K1 of #506, "required <node> is already a test of tests/test_more.py in the intake: an appended file adds new tests": **73 lines** in the append measurement and **86** in the into_class one, against at most 9 for any other reason (`new test ... not a failure by assertion on the baseline` 9; `changed test ... is not run whole by any pytest validation` 7; `validation regression has no new test and must pass on the baseline` 4; `validation ... at most N args` 3). In batch 3 (new files) the whole list was 5 lines. The pattern: the drafter puts the OLD tests of the file (`NumericRangeTests::test_basic`, `test_contains`, ...) in a regression validation's `must_pass` to protect them, and K1 refuses an added file that "requires" an existing test, because a required existing test normally means a changed expectation (which needs the whole file as content). Those old tests would run anyway in the validation that runs the whole file.

**Not decided here (needs a spec and review, strict lane):** a harness-side normalization that drops the existing, already collected nodes from `must_pass` of an appended or inserted file instead of refusing (the way the harness already normalizes validation ids: `draft_normalized`) and says so to the drafter; the tests still run in the whole-file validation, so nothing is protected less. The alternative (a prompt hint) is weaker: the prompt already says "require only new tests in must_pass". Not measured: what this would do to the number of submits (my estimate: it removes most of the 86 lines, which is most of the refusals).

Caveats: one repository, one model, one run per issue (two for #1247); the submit counts come from events and the reasons from the stored conversation of each job with a regular expression, so a few lines may be missed; the counts of lines are per node listed, not per submit (one submit that listed 17 old tests counts 17).

## Third run of #1247, with the limit at 7 (2026-11-14, branch spec-max-submits = PR #519; draft only)

Job `j20261114_090135_7100`, **`DRAFTED`, $0.0155**, inserted two methods into `NumericRangeTests`, status line `d1 submits: 6 of 7` (the new line from #519). **Read the 6 carefully: the draft passed the harness at submit 5** (four refusals before it, with 12, 1, 1 and 1 problems), and the harness then asked the red question (`draft_submitted ... ok: true, red_question: 2`: whether the failure of each of the 2 required tests is the behaviour the issue asks for); **submit 6 is the drafter's answer (`held: true`)**. So the 6 is 4 refusals + the accepted draft + the answer to the question, not a sixth refusal.

What this adds: (1) #1247 across three runs: failed (5 submits), accepted at 5, accepted at 5 plus the red-question answer. It does **not** show that a limit above 5 was needed to get the draft accepted. (2) It shows a side effect of the limit: the red question is only asked while the submit number is below `max_submits` (`codetask/drafter.py:782`), so with a limit of 5 a draft that is first accepted at submit 5 is accepted **without** the red question being asked; with 7 it is asked. The question is a quality gate (`red_question: true`, `config.yaml:156`), so a low limit also skips it exactly for the drafts that struggled most. (3) The status line counts the answer as a submit, so `6 of 7` can read as more struggle than there was; a line that separates the held answer would be clearer (not done).

Caveats: one more run of one issue; the three runs of #1247 are not independent evidence of a rate.
