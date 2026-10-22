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
| claim[0]:file_changed | D | pass | - |
| claim[1]:tests_pass | D | pass | - |
| claim[2]:issue_fixed | D | pass | - |
| workspace:unchanged_during_evaluation | B | pass | - |

## validation `target`

`python -m pytest tests/test_review_pr_title.py`
sandbox environment: `argus`

| | Verdict | Fresh |
|---|---|---|
| status | pass | pass |
| outcome | OK | OK |
| tests_run | 9 | 9 |
| failures | 0 | 0 |
| errors | 0 | 0 |
| skipped | 0 | 0 |

| Required test | Verdict | Fresh |
|---|---|---|
| `tests/test_review_pr_title.py::test_the_issues_own_example_is_cut_at_a_word` | ok | ok |
| `tests/test_review_pr_title.py::test_a_long_first_line_is_cut_before_the_last_space_of_its_first_81_characters` | ok | ok |
| `tests/test_review_pr_title.py::test_spaces_before_the_cut_are_removed` | ok | ok |
| `tests/test_review_pr_title.py::test_one_long_word_is_cut_at_80_characters` | ok | ok |
| `tests/test_review_pr_title.py::test_a_word_ending_exactly_at_character_80_is_kept_whole` | ok | ok |
