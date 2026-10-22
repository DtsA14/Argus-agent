# Draft review: `argus_p7` (w2b2d1)

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
- In render_pr, replace the [:80] slice of the issue's first line with a helper that applies the word-boundary rule and appends '...'.
- Keep the contract-name prefix, cell(title, 120), and the rest of PR.md unchanged.

Risks:
- Off-by-one: the cut uses the first 81 characters, so a space at index 80 keeps the whole 80-character word.
- Trailing spaces must be removed before appending '...'.
- The existing cell(title, 120) must still be applied to the whole heading.

## Scope

Writable: `codetask/review.py`

Protected: `tests/**`, `acceptance/**`, `harness/**`, `scripts/**`

No scope warnings.

## Validations

- `target`: `python -m pytest tests/test_pr_title.py`, at least 8 tests, environment `argus`; required new tests: 5, required existing tests: 0
  - new: `tests/test_pr_title.py::test_cut_before_last_space`
  - new: `tests/test_pr_title.py::test_space_at_index_80_keeps_word`
  - new: `tests/test_pr_title.py::test_one_long_word`
  - new: `tests/test_pr_title.py::test_multiple_spaces_removed`
  - new: `tests/test_pr_title.py::test_only_first_line_used`

Budget profile for the agent: `default`

## New tests

### `tests/test_pr_title.py`

On the code as it is now, validation `target`: `test_cut_before_last_space` FAIL, `test_space_at_index_80_keeps_word` FAIL, `test_one_long_word` FAIL, `test_multiple_spaces_removed` FAIL, `test_only_first_line_used` FAIL

Why they fail now (test output; check that this is the behaviour to fix):

```text
tests/test_pr_title.py:52: in test_one_long_word
E   AssertionError: assert '# fix_x: xxx...xxxxxxxxxxxxx' == '# fix_x: xxx...xxxxxxxxxx...'
E     
E     - # fix_x: xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx...
E     ?                                                                                          ---
E     + # fix_x: xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
tests/test_pr_title.py:57: in test_multiple_spaces_removed
E   AssertionError: assert '# fix_x: aaa...aaaa bbbbbbbb' == '# fix_x: aaa...aaaaaaaaaa...'
E     
E     - # fix_x: aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa...
E     ?                                                                                ^^^
E     + # fix_x: aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa bbbbbbbb
E     ?                                                                                ^^^^^^^^^
========================= 5 failed, 3 passed in Xs ==========================
```

The file:

```python
from codetask import review


class _Ck:
    valid = True
    problems = []


def _prov():
    return {
        "patch": {"files": [], "sha256": "0" * 64},
        "validation_fresh": {},
        "checks": [],
        "base": {"repo": "r", "commit": "c" * 40},
        "argus": {"commit": "a" * 40, "dirty": False},
        "contract": {"name": "fix_x", "sha256": "f" * 64},
        "models": [],
        "cost": {"calls": 0, "usd": 0.0, "usd_complete": True},
        "run_id": "run",
        "attempts": 1,
    }


def _heading(issue, name="fix_x"):
    contract = {"contract": name, "inputs": {"issue": issue}}
    out = review.render_pr(_prov(), contract, None, None, _Ck())
    return out.splitlines()[0]


def test_exactly_80_chars_unchanged():
    line = "abcdefghi " * 7 + "abcdefghij"
    assert len(line) == 80
    assert _heading(line) == "# fix_x: " + line


def test_short_line_unchanged():
    assert _heading("Short title\n\nbody") == "# fix_x: Short title"


def test_cut_before_last_space():
    line = "The title of a review package's pull request draft is cut in the middle of a word and more text"
    assert _heading(line) == "# fix_x: The title of a review package's pull request draft is cut in the middle of a..."


def test_space_at_index_80_keeps_word():
    first = "abcdefghi " * 7 + "abcdefghij"
    assert len(first) == 80
    assert _heading(first + " tail of the line") == "# fix_x: " + first + "..."


def test_one_long_word():
    assert _heading("x" * 100) == "# fix_x: " + "x" * 80 + "..."


def test_multiple_spaces_removed():
    line = "a" * 70 + "  " + "b" * 30
    assert _heading(line) == "# fix_x: " + "a" * 70 + "..."


def test_only_first_line_used():
    line = "word " * 30
    issue = "  \n" + line + "\nsecond line"
    assert _heading(issue) == "# fix_x: " + ("word " * 16).rstrip() + "..."


def test_heading_still_cut_to_120():
    name = "n" * 50
    line = "word " * 30
    full = name + ": " + ("word " * 16).rstrip() + "..."
    assert len(full) > 120
    assert _heading(line, name) == "# " + full[:117] + "..."

```

## Not verified automatically

Nothing.

## Cost

Drafter: $0.0933, 4 model calls, 2 submits, 3 steps (ended: submitted).

## Approve

`approve_draft.py` checks the draft again under your task name, issue, cap and attempt limit, and publishes it only with `--approve`. Without a reference patch the task is recorded as `feasibility: unproven`; with one (`--reference-patch <patch>` instead of `--no-reference`) it is proven before the agent runs.

```bash
python scripts/approve_draft.py --draft runs/w2b2d1/draft.json --task <name> --issue-file runs/w2b2d1/issue.txt --max-usd <cap> --max-iterations <n> --no-reference
```
