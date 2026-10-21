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

`python -m pytest tests/test_peak_window_strict.py`
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
| `tests/test_peak_window_strict.py::test_v1_a_window_that_is_not_a_dict_is_refused` | ok | ok |
| `tests/test_peak_window_strict.py::test_v2_a_window_without_utc_hours_is_refused` | ok | ok |
| `tests/test_peak_window_strict.py::test_v3_utc_hours_that_is_not_a_list_is_refused` | ok | ok |
| `tests/test_peak_window_strict.py::test_v4_an_item_that_is_not_two_integers_is_refused` | ok | ok |
| `tests/test_peak_window_strict.py::test_v5_an_hour_out_of_range_is_refused` | ok | ok |
| `tests/test_peak_window_strict.py::test_v6_weekdays_only_that_is_not_a_bool_is_refused` | ok | ok |
| `tests/test_peak_window_strict.py::test_v7_a_time_without_a_zone_is_refused_and_a_time_with_a_zone_is_not` | ok | ok |
| `tests/test_peak_window_strict.py::test_a_bad_item_behind_an_item_that_matches_is_still_refused` | ok | ok |
| `tests/test_peak_window_strict.py::test_the_refusal_also_comes_from_multiplier_and_cost_usd` | ok | ok |
| `tests/test_peak_window_strict.py::test_every_hour_pair_outside_the_valid_ranges_is_refused` | ok | ok |

## validation `regression`

`python -m pytest tests/test_peak_window.py tests/test_models.py tests/test_llm_wrapper.py::test_peak_hours_halve_the_output_cap_for_deepseek tests/test_llm_wrapper.py::test_node_usd_estimates_use_the_dearer_rate_and_peak`
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
| `tests/test_peak_window.py::test_the_evening_part_of_a_window_across_midnight_is_peak` | ok | ok |
| `tests/test_peak_window.py::test_weekdays_only_follows_the_utc_date_of_now_also_across_midnight` | ok | ok |
| `tests/test_peak_window.py::test_no_window_is_never_peak` | ok | ok |
| `tests/test_models.py::test_cost_of_a_plain_call` | ok | ok |
| `tests/test_models.py::test_unknown_price_is_none_not_a_guess` | ok | ok |
| `tests/test_models.py::test_deepseek_peak_windows` | ok | ok |
| `tests/test_models.py::test_peak_doubles_the_price` | ok | ok |
| `tests/test_llm_wrapper.py::test_peak_hours_halve_the_output_cap_for_deepseek` | ok | ok |
| `tests/test_llm_wrapper.py::test_node_usd_estimates_use_the_dearer_rate_and_peak` | ok | ok |
