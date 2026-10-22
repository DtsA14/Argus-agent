# Validation

**Verdict**: what acceptance recorded at the end of the run, in the run's workspace.  
**Fresh**: the same validation run again in the sandbox on a clean tree built from the base commit and `changes.patch`, which is the tree a reviewer gets.

| Criterion | Layer | Verdict | Fresh |
|---|---|---|---|
| scope:protected | A | pass | - |
| scope:writable | A | pass | - |
| scope:regular_files | A | pass | - |
| artifact:SUMMARY.json | B | pass | - |
| validation:report | C | pass | pass |
| validation:regression | C | pass | pass |
| claim[0]:file_changed | D | pass | - |
| claim[1]:tests_pass | D | pass | - |
| claim[2]:tests_pass | D | pass | - |
| claim[3]:issue_fixed | D | pass | - |
| workspace:unchanged_during_evaluation | B | pass | - |

## validation `report`

`python -m pytest tests/test_pilot_report.py`
sandbox environment: `argus`

| | Verdict | Fresh |
|---|---|---|
| status | pass | pass |
| outcome | OK | OK |
| tests_run | 17 | 17 |
| failures | 0 | 0 |
| errors | 0 | 0 |
| skipped | 0 | 0 |

| Required test | Verdict | Fresh |
|---|---|---|
| `tests/test_pilot_report.py::test_the_report_over_seven_kinds_of_run` | ok | ok |
| `tests/test_pilot_report.py::test_the_report_with_supervision_minutes` | ok | ok |
| `tests/test_pilot_report.py::test_missing_minutes_are_null_and_a_zero_is_data` | ok | ok |
| `tests/test_pilot_report.py::test_no_run_done` | ok | ok |
| `tests/test_pilot_report.py::test_no_cost_known` | ok | ok |
| `tests/test_pilot_report.py::test_only_runs_without_a_result` | ok | ok |
| `tests/test_pilot_report.py::test_no_run_is_refused` | ok | ok |
| `tests/test_pilot_report.py::test_an_argument_that_is_not_a_run_directory_is_refused` | ok | ok |
| `tests/test_pilot_report.py::test_an_invalid_supervision_file_is_refused[negative]` | ok | ok |
| `tests/test_pilot_report.py::test_an_invalid_supervision_file_is_refused[string]` | ok | ok |
| `tests/test_pilot_report.py::test_an_invalid_supervision_file_is_refused[bool]` | ok | ok |
| `tests/test_pilot_report.py::test_an_invalid_supervision_file_is_refused[list]` | ok | ok |
| `tests/test_pilot_report.py::test_an_invalid_supervision_file_is_refused[nan]` | ok | ok |
| `tests/test_pilot_report.py::test_an_invalid_supervision_file_is_refused[unknown_run]` | ok | ok |
| `tests/test_pilot_report.py::test_an_invalid_supervision_file_is_refused[not_json]` | ok | ok |
| `tests/test_pilot_report.py::test_an_invalid_supervision_file_is_refused[number]` | ok | ok |
| `tests/test_pilot_report.py::test_a_missing_supervision_file_is_refused` | ok | ok |

## validation `regression`

`python -m pytest tests/test_run_inspectors.py tests/test_run_inspectors_data.py tests/test_eval_cost.py tests/test_run_stats.py`
sandbox environment: `argus`

| | Verdict | Fresh |
|---|---|---|
| status | pass | pass |
| outcome | OK | OK |
| tests_run | 30 | 30 |
| failures | 0 | 0 |
| errors | 0 | 0 |
| skipped | 0 | 0 |

| Required test | Verdict | Fresh |
|---|---|---|
| `tests/test_run_inspectors.py::test_a_cut_line_in_the_middle_of_the_log_adds_one_line_and_changes_nothing_else` | ok | ok |
| `tests/test_run_inspectors.py::test_a_run_blocked_before_any_model_call_is_audited` | ok | ok |
| `tests/test_eval_cost.py::test_an_unknown_cost_stops_the_scripted_modes_too` | ok | ok |
| `tests/test_eval_cost.py::test_known_costs_keep_the_eval_going_and_the_total_is_complete` | ok | ok |
| `tests/test_eval_cost.py::test_a_cost_is_shown_as_n_a_when_it_is_not_known` | ok | ok |
| `tests/test_run_stats.py::test_a_log_without_damage_is_counted_as_before` | ok | ok |
| `tests/test_run_stats.py::test_a_line_cut_short_in_the_middle_is_skipped` | ok | ok |
| `tests/test_run_stats.py::test_every_line_that_is_not_json_is_skipped_and_blank_lines_too` | ok | ok |
