# M6 pilot 1: run_stats must skip lines that are not JSON (draft, not run)

Status 2026-10-21: **draft checked, not approved, not run.** No model has been called.

| File | What |
|---|---|
| `issue.txt` | the issue the agent gets |
| `draft.json` | the typed draft: plan, contract parts (scope, two pytest validations in the `argus` sandbox environment, tools `search_files` + `edit_file`, profile `default`), the new test file, notes for the reviewer |
| `new_test.txt` | the new test file as plain text (same content as in `draft.json`) |
| `reference.patch` | the human's solution, a git diff of `evals/score.py` (two hunks: one import, one line) |
| `check_report.json` | `scripts/approve_draft.py` check, run in the `argus` sandbox on the VM: `ok: true` |

Base: intake `argus_m6` = Argus at `5ff64d0` minus `verification/` and `pilots/` (the one test in `tests/test_eval.py`
that reads `verification/` is left out of the regression set).

Check result: the 3 required new tests fail on the baseline with `json.decoder.JSONDecodeError` raised from
`evals/score.py:100` (the bug itself, not a setup error); the 4th new test (an undamaged log is counted as before) and
the 8 regression nodes of `tests/test_eval.py` pass on the baseline; with the reference patch everything passes and
only `evals/score.py` changes.

Cap proposal for the run: `max_usd` 0.50, `max_iterations` 3, profile `default` (30k / 4,096). Not yet approved.

## Why the undamaged-log test is not in `must_pass` (GPT review, 2026-10-21)

GPT suggested listing `test_a_log_without_damage_is_counted_as_before` in `target.must_pass`. The draft check refuses
that: a required node of a new test must **fail by assertion** on the baseline (W2a, `acceptance/draft.py`), and this
one passes there. Tried on the VM: `ok: false`, "is 'ok', not a failure by assertion on the baseline" and "exactly the 4
new required tests may fail". The behaviour is still enforced: the `target` validation runs the whole file, needs
`min_tests` 4 and exit 0, so that test must pass after the change, and the tests are protected (the agent cannot edit or
remove them). A per-node "must keep passing" list for new tests would be a change to the draft check, which is not part
of this pilot.
