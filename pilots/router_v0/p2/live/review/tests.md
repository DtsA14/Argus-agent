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

`python -m pytest tests/test_argus_list.py`
sandbox environment: `argus`

| | Verdict | Fresh |
|---|---|---|
| status | pass | pass |
| outcome | OK | OK |
| tests_run | 7 | 7 |
| failures | 0 | 0 |
| errors | 0 | 0 |
| skipped | 0 | 0 |

| Required test | Verdict | Fresh |
|---|---|---|
| `tests/test_argus_list.py::test_list_prints_one_line_per_job_sorted_by_job_id` | ok | ok |
| `tests/test_argus_list.py::test_list_ignores_entries_that_are_not_jobs` | ok | ok |
| `tests/test_argus_list.py::test_list_marks_a_job_json_that_is_not_valid_json` | ok | ok |
| `tests/test_argus_list.py::test_list_marks_a_job_json_it_cannot_read` | ok | ok |
| `tests/test_argus_list.py::test_list_says_no_jobs_for_a_missing_or_empty_jobs_dir` | ok | ok |
| `tests/test_argus_list.py::test_list_takes_no_lock_and_changes_nothing` | ok | ok |
