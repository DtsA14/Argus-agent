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
| claim[0]:tests_pass | D | pass | - |
| claim[1]:issue_fixed | D | pass | - |
| claim[2]:file_changed | D | pass | - |
| claim[3]:file_changed | D | pass | - |
| workspace:unchanged_during_evaluation | B | pass | - |

## validation `target`

`python -m pytest tests/test_impl_flag.py`
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
| `tests/test_impl_flag.py::test_a_mistyped_node_is_refused_before_anything_runs` | ok | ok |
| `tests/test_impl_flag.py::test_a_second_mistyped_node_is_refused_too` | ok | ok |
| `tests/test_impl_flag.py::test_an_empty_node_is_refused` | ok | ok |
| `tests/test_impl_flag.py::test_an_item_without_equals_is_refused_cleanly` | ok | ok |
| `tests/test_impl_flag.py::test_an_empty_kind_is_refused_cleanly` | ok | ok |
| `tests/test_impl_flag.py::test_a_kind_other_than_fake_or_llm_is_refused_cleanly` | ok | ok |
| `tests/test_impl_flag.py::test_a_refused_flag_starts_nothing_and_the_corrected_command_runs` | ok | ok |

## validation `regression`

`python -m pytest tests/test_models.py tests/test_milestone1.py::test_pass_first_try tests/test_milestone1.py::test_fail_then_pass_uses_feedback tests/test_milestone1.py::test_iteration_budget`
sandbox environment: `argus`

| | Verdict | Fresh |
|---|---|---|
| status | pass | pass |
| outcome | OK | OK |
| tests_run | 18 | 18 |
| failures | 0 | 0 |
| errors | 0 | 0 |
| skipped | 0 | 0 |

| Required test | Verdict | Fresh |
|---|---|---|
| `tests/test_models.py::test_override_errors_are_clear` | ok | ok |
| `tests/test_models.py::test_swap_model_for_a_role_leaves_original_untouched` | ok | ok |
| `tests/test_models.py::test_default_roles_build_without_network` | ok | ok |
| `tests/test_milestone1.py::test_pass_first_try` | ok | ok |
| `tests/test_milestone1.py::test_fail_then_pass_uses_feedback` | ok | ok |
| `tests/test_milestone1.py::test_iteration_budget` | ok | ok |
