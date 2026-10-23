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
| claim[0]:tests_pass | D | pass | - |
| claim[1]:issue_fixed | D | pass | - |
| claim[2]:file_changed | D | pass | - |
| claim[3]:file_changed | D | pass | - |
| workspace:unchanged_during_evaluation | B | pass | - |

## validation `target`

`python -m pytest tests/test_router_list.py`
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
| `tests/test_router_list.py::test_list_prints_one_sorted_line_per_job` | ok | ok |
| `tests/test_router_list.py::test_list_shows_the_spend_its_stage_runs_recorded` | ok | ok |
| `tests/test_router_list.py::test_a_job_json_that_cannot_be_read_is_named_and_others_still_listed` | ok | ok |
| `tests/test_router_list.py::test_list_takes_no_lock_and_changes_nothing` | ok | ok |
| `tests/test_router_list.py::test_the_cli_lists_jobs_and_exits_zero` | ok | ok |
| `tests/test_router_list.py::test_the_cli_says_no_jobs_for_a_directory_that_does_not_exist` | ok | ok |
| `tests/test_router_list.py::test_only_directories_with_a_job_json_are_jobs` | ok | ok |
| `tests/test_router_list.py::test_no_jobs_and_a_missing_directory_say_exactly_no_jobs` | ok | ok |
