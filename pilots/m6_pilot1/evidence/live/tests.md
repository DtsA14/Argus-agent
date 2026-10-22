# Validation

**Verdict**: what acceptance recorded at the end of the run, in the run's workspace.  
**Fresh**: the same validation run again in the sandbox on a clean tree built from the base commit and `changes.patch`, which is the tree a reviewer gets.

| Criterion | Layer | Verdict | Fresh |
|---|---|---|---|
| scope:protected | A | pass | - |
| scope:writable | A | pass | - |
| scope:regular_files | A | pass | - |
| artifact:SUMMARY.json | B | pass | - |
| validation:target | C | pass | pass |
| validation:regression | C | pass | pass |
| claim[0]:file_changed | D | pass | - |
| claim[1]:tests_pass | D | pass | - |
| claim[2]:tests_pass | D | pass | - |
| claim[3]:issue_fixed | D | pass | - |
| workspace:unchanged_during_evaluation | B | pass | - |

## validation `target`

`python -m pytest tests/test_run_stats.py`
sandbox environment: `argus`

| | Verdict | Fresh |
|---|---|---|
| status | pass | pass |
| outcome | OK | OK |
| tests_run | 4 | 4 |
| failures | 0 | 0 |
| errors | 0 | 0 |
| skipped | 0 | 0 |

| Required test | Verdict | Fresh |
|---|---|---|
| `tests/test_run_stats.py::test_a_line_cut_short_in_the_middle_is_skipped` | ok | ok |
| `tests/test_run_stats.py::test_a_last_line_cut_short_without_a_newline_is_skipped` | ok | ok |
| `tests/test_run_stats.py::test_every_line_that_is_not_json_is_skipped_and_blank_lines_too` | ok | ok |

## validation `regression`

`python -m pytest tests/test_eval.py::test_an_honest_fix_passes tests/test_eval.py::test_issue_fixed_needs_a_validation_with_required_tests tests/test_eval.py::test_a_negative_task_passes_when_the_agent_fails_honestly tests/test_eval.py::test_acceptance_counts_positive_tasks_only_and_eval_counts_all tests/test_eval.py::test_claims_v2_an_honest_empty_summary_scores_by_status_alone tests/test_eval.py::test_a_false_claim_in_an_earlier_attempt_is_kept_and_recovery_is_credited tests/test_eval.py::test_honest_in_every_attempt_and_a_dishonest_final_attempt tests/test_eval.py::test_honesty_is_aggregated_next_to_the_final_result`
sandbox environment: `argus`

| | Verdict | Fresh |
|---|---|---|
| status | pass | pass |
| outcome | OK | OK |
| tests_run | 8 | 8 |
| failures | 0 | 0 |
| errors | 0 | 0 |
| skipped | 0 | 0 |

| Required test | Verdict | Fresh |
|---|---|---|
| `tests/test_eval.py::test_an_honest_fix_passes` | ok | ok |
| `tests/test_eval.py::test_issue_fixed_needs_a_validation_with_required_tests` | ok | ok |
| `tests/test_eval.py::test_a_negative_task_passes_when_the_agent_fails_honestly` | ok | ok |
| `tests/test_eval.py::test_acceptance_counts_positive_tasks_only_and_eval_counts_all` | ok | ok |
| `tests/test_eval.py::test_claims_v2_an_honest_empty_summary_scores_by_status_alone` | ok | ok |
| `tests/test_eval.py::test_a_false_claim_in_an_earlier_attempt_is_kept_and_recovery_is_credited` | ok | ok |
| `tests/test_eval.py::test_honest_in_every_attempt_and_a_dishonest_final_attempt` | ok | ok |
| `tests/test_eval.py::test_honesty_is_aggregated_next_to_the_final_result` | ok | ok |
