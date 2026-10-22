# Draft review: `argus_p7` (w2b2d3)

Status: **DRAFTED** (a draft passed its check)

Written by the harness from the draft and its check. The draft itself was written by a model: read the tests. A passing baseline shows only that the new tests fail now, not that they test the right thing.

## Issue

```text
The title of a review package's pull request draft is cut in the middle of a word.

codetask/review.py, render_pr: the first line of review/PR.md is "# " followed by the contract name, ": " and the first
line of the task's issue cut to its first 80 characters. A long first line therefore ends mid-word, for example
"fix_x: The title of a review package's pull request draft is cut in the middle of a wor".

Wanted, for the issue part of the title only (call the issue's stripped first line L):
- if L has at most 80 characters, it is used as it is, with nothing added;
- otherwise take L's first 81 characters and cut them just before their last space; if that leaves something, remove
  trailing spaces and append "..." (three dots, no space before them);
- if those 81 characters contain no space (one long word), or the cut leaves nothing, use L's first 80 characters
  followed by "...".

Everything else stays as it is: the contract name and ": " before it, the cleaning of the whole heading for the
Markdown table cell (the existing cell(title, 120)), the rest of PR.md, and every other file of the review package.
```

## Plan

Files: `codetask/review.py`

Steps:
- In render_pr, replace the [:80] cut of the issue's first line with the rule: L unchanged if len<=80; else cut the first 81 characters before their last space, rstrip, append '...'; if there is no space or nothing remains, use L[:80] + '...'.
- Keep the contract-name prefix, the cell(title, 120) cleaning and everything else in PR.md unchanged.

Risks:
- Off-by-one: the cut must look at 81 characters (so a word ending exactly at 80 is kept whole), not 80.
- Changing the stripping of the issue or the cell() call would alter other output.
- An empty issue must still give 'name: ' without an error.

## Scope

Writable: `codetask/review.py`

Protected: `tests/**`

No scope warnings.

## Validations

- `target`: `python -m pytest tests/test_review_pr_title.py`, at least 9 tests, environment `argus`; required new tests: 5, required existing tests: 0
  - new: `tests/test_review_pr_title.py::test_the_issues_own_example_is_cut_at_a_word`
  - new: `tests/test_review_pr_title.py::test_a_long_first_line_is_cut_before_the_last_space_of_its_first_81_characters`
  - new: `tests/test_review_pr_title.py::test_spaces_before_the_cut_are_removed`
  - new: `tests/test_review_pr_title.py::test_one_long_word_is_cut_at_80_characters`
  - new: `tests/test_review_pr_title.py::test_a_word_ending_exactly_at_character_80_is_kept_whole`

Budget profile for the agent: `default`

Tools added for the agent: `edit_file`

## New tests

### `tests/test_review_pr_title.py`

On the code as it is now, validation `target`: `test_the_issues_own_example_is_cut_at_a_word` FAIL, `test_a_long_first_line_is_cut_before_the_last_space_of_its_first_81_characters` FAIL, `test_spaces_before_the_cut_are_removed` FAIL, `test_one_long_word_is_cut_at_80_characters` FAIL, `test_a_word_ending_exactly_at_character_80_is_kept_whole` FAIL

Why they fail now (test output; check that this is the behaviour to fix):

```text
tests/test_review_pr_title.py:29: in test_spaces_before_the_cut_are_removed
E   AssertionError: assert '# fix_x: aaa...bbbbbbbbbbbbb' == '# fix_x: aaa...aaaaaaaaaa...'
E     
E     - # fix_x: aaaaaaaaaaaaaaaaaaaaaaaaaaaaaa...
E     + # fix_x: aaaaaaaaaaaaaaaaaaaaaaaaaaaaaa bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb
tests/test_review_pr_title.py:33: in test_one_long_word_is_cut_at_80_characters
E   AssertionError: assert '# fix_x: zzz...zzzzzzzzzzzzz' == '# fix_x: zzz...zzzzzzzzzz...'
E     
E     - # fix_x: zzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzz...
E     ?                                                                                          ---
E     + # fix_x: zzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzz
tests/test_review_pr_title.py:39: in test_a_word_ending_exactly_at_character_80_is_kept_whole
E   AssertionError: assert '# fix_x: aaa...aaa bbbbbbbbb' == '# fix_x: aaa... bbbbbbbbb...'
E     
E     - # fix_x: aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa bbbbbbbbb...
E     ?                                                                                          ---
E     + # fix_x: aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa bbbbbbbbb
========================= 5 failed, 4 passed in Xs ==========================
```

The file:

```python
"""The title of review/PR.md: the issue part is cut at a word, with '...', not in the middle of a word."""
import pytest

from codetask import review


def pr_title(issue, name="fix_x"):
    prov = {"patch": {"files": [], "sha256": "0" * 64}, "validation_fresh": {}, "checks": [],
            "base": {"commit": "c" * 40, "repo": "r"}, "argus": {"commit": "a" * 40, "dirty": False},
            "contract": {"name": name, "sha256": "0" * 64}, "models": [],
            "cost": {"calls": 0, "usd": 0.0, "usd_complete": True}, "run_id": "r1", "attempts": 1}
    contract = {"contract": name, "inputs": {"issue": issue}}
    text = review.render_pr(prov, contract, None, None, review.Checks())
    return text.splitlines()[0]


def test_the_issues_own_example_is_cut_at_a_word():
    issue = "The title of a review package's pull request draft is cut in the middle of a word."
    assert pr_title(issue) == "# fix_x: The title of a review package's pull request draft is cut in the middle of a..."


def test_a_long_first_line_is_cut_before_the_last_space_of_its_first_81_characters():
    issue = "x" * 40 + " " + "y" * 50 + "\nsecond line"
    assert pr_title(issue) == "# fix_x: " + "x" * 40 + "..."


def test_spaces_before_the_cut_are_removed():
    issue = "a" * 30 + "   " + "b" * 60
    assert pr_title(issue) == "# fix_x: " + "a" * 30 + "..."


def test_one_long_word_is_cut_at_80_characters():
    assert pr_title("z" * 100) == "# fix_x: " + "z" * 80 + "..."


def test_a_word_ending_exactly_at_character_80_is_kept_whole():
    issue = "a" * 70 + " " + "b" * 9 + " " + "c" * 5
    assert len(issue.split(" ")[0]) + 1 + 9 == 80
    assert pr_title(issue) == "# fix_x: " + "a" * 70 + " " + "b" * 9 + "..."


@pytest.mark.parametrize("length", [1, 79, 80])
def test_a_first_line_of_at_most_80_characters_is_used_as_it_is(length):
    line = ("w" * 9 + " ") * 8
    line = (line + "v" * 80)[:length].rstrip() if length < 80 else (line[:79] + "v")
    assert len(line) <= 80
    assert pr_title(line + "\nmore") == "# fix_x: " + line


def test_the_heading_is_still_cleaned_and_limited_to_120_characters():
    title = pr_title("short issue", name="n" * 130)
    assert title == "# " + "n" * 117 + "..."

```

## Not verified automatically

Nothing.

## Cost

Drafter: $0.1844, 10 model calls, 5 submits, 9 steps (ended: submitted).

## Approve

`approve_draft.py` checks the draft again under your task name, issue, cap and attempt limit, and publishes it only with `--approve`. Without a reference patch the task is recorded as `feasibility: unproven`; with one (`--reference-patch <patch>` instead of `--no-reference`) it is proven before the agent runs.

```bash
python scripts/approve_draft.py --draft runs/w2b2d3/draft.json --task <name> --issue-file runs/w2b2d3/issue.txt --max-usd <cap> --max-iterations <n> --no-reference
```
