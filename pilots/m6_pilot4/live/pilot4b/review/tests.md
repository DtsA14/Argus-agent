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
| claim[1]:issue_fixed | D | pass | - |
| claim[2]:tests_pass | D | pass | - |
| workspace:unchanged_during_evaluation | B | pass | - |

## validation `target`

`python -m pytest tests/test_peak_window.py`
sandbox environment: `argus`

| | Verdict | Fresh |
|---|---|---|
| status | pass | pass |
| outcome | OK | OK |
| tests_run | 13 | 13 |
| failures | 0 | 0 |
| errors | 0 | 0 |
| skipped | 0 | 0 |

| Required test | Verdict | Fresh |
|---|---|---|
| `tests/test_peak_window.py::test_the_evening_part_of_a_window_across_midnight_is_peak` | ok | ok |
| `tests/test_peak_window.py::test_the_early_morning_part_of_a_window_across_midnight_is_peak` | ok | ok |
| `tests/test_peak_window.py::test_two_windows_one_of_them_across_midnight` | ok | ok |
| `tests/test_peak_window.py::test_weekdays_only_follows_the_utc_date_of_now_also_across_midnight` | ok | ok |
| `tests/test_peak_window.py::test_a_time_in_another_zone_is_converted_to_utc` | ok | ok |
| `tests/test_peak_window.py::test_the_multiplier_and_the_cost_follow_a_window_across_midnight` | ok | ok |

## validation `regression`

`python -m pytest tests/test_models.py tests/test_llm_wrapper.py::test_peak_hours_halve_the_output_cap_for_deepseek tests/test_llm_wrapper.py::test_node_usd_estimates_use_the_dearer_rate_and_peak`
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
| `tests/test_models.py::test_cost_of_a_plain_call` | ok | ok |
| `tests/test_models.py::test_unknown_price_is_none_not_a_guess` | ok | ok |
| `tests/test_models.py::test_deepseek_peak_windows` | ok | ok |
| `tests/test_models.py::test_peak_doubles_the_price` | ok | ok |
| `tests/test_models.py::test_message_cost_reads_usage_and_cache_from_the_message` | ok | ok |
| `tests/test_llm_wrapper.py::test_peak_hours_halve_the_output_cap_for_deepseek` | ok | ok |
| `tests/test_llm_wrapper.py::test_node_usd_estimates_use_the_dearer_rate_and_peak` | ok | ok |
