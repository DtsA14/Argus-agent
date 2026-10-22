# Validation

**Verdict**: what acceptance recorded at the end of the run, in the run's workspace.  
**Fresh**: the same validation run again in the sandbox on a clean tree built from the base commit and `changes.patch`, which is the tree a reviewer gets.

| Criterion | Layer | Verdict | Fresh |
|---|---|---|---|
| scope:protected | A | pass | - |
| scope:writable | A | pass | - |
| scope:regular_files | A | pass | - |
| artifact:SUMMARY.json | B | pass | - |
| validation:inspectors | C | pass | pass |
| validation:regression | C | pass | pass |
| claim[0]:tests_pass | D | pass | - |
| claim[1]:tests_pass | D | pass | - |
| claim[2]:issue_fixed | D | pass | - |
| claim[3]:file_changed | D | pass | - |
| claim[4]:file_changed | D | pass | - |
| claim[5]:file_changed | D | pass | - |
| workspace:unchanged_during_evaluation | B | pass | - |

## validation `inspectors`

`python -m pytest tests/test_run_inspectors.py tests/test_run_inspectors_data.py`
sandbox environment: `argus`

| | Verdict | Fresh |
|---|---|---|
| status | pass | pass |
| outcome | OK | OK |
| tests_run | 16 | 16 |
| failures | 0 | 0 |
| errors | 0 | 0 |
| skipped | 0 | 0 |

| Required test | Verdict | Fresh |
|---|---|---|
| `tests/test_run_inspectors.py::test_a_cut_line_in_the_middle_of_the_log_adds_one_line_and_changes_nothing_else` | ok | ok |
| `tests/test_run_inspectors.py::test_a_run_blocked_before_any_model_call_is_audited` | ok | ok |
| `tests/test_run_inspectors.py::test_a_directory_without_a_result_is_reported_and_the_next_one_is_still_traced` | ok | ok |
| `tests/test_run_inspectors_data.py::test_events_are_read_with_the_number_of_lines_that_did_not_decode` | ok | ok |
| `tests/test_run_inspectors_data.py::test_result_memo_and_the_skipped_line_are_read_as_the_inspectors_need_them` | ok | ok |

## validation `regression`

`python -m pytest tests/test_eval_cost.py tests/test_run_stats.py`
sandbox environment: `argus`

| | Verdict | Fresh |
|---|---|---|
| status | pass | pass |
| outcome | OK | OK |
| tests_run | 14 | 14 |
| failures | 0 | 0 |
| errors | 0 | 0 |
| skipped | 0 | 0 |

| Required test | Verdict | Fresh |
|---|---|---|
| `tests/test_eval_cost.py::test_an_unknown_cost_stops_the_scripted_modes_too` | ok | ok |
| `tests/test_eval_cost.py::test_known_costs_keep_the_eval_going_and_the_total_is_complete` | ok | ok |
| `tests/test_eval_cost.py::test_a_cost_is_shown_as_n_a_when_it_is_not_known` | ok | ok |
| `tests/test_run_stats.py::test_a_log_without_damage_is_counted_as_before` | ok | ok |
| `tests/test_run_stats.py::test_a_line_cut_short_in_the_middle_is_skipped` | ok | ok |
| `tests/test_run_stats.py::test_every_line_that_is_not_json_is_skipped_and_blank_lines_too` | ok | ok |
