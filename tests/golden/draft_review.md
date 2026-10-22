# Draft review: `shop` (d1)

Status: **DRAFTED** (a draft passed its check)

Written by the harness from the draft and its check. The draft itself was written by a model: read the tests. A passing baseline shows only that the new tests fail now, not that they test the right thing.

## Issue

```text
total() can go negative when the discount is larger than the sum; it must never be below 0.
```

## Plan

Files: `src/shop.py`

Steps:
- floor the total at 0

Risks:
- a discount of 0

## Scope

Writable: `src/*.py`

Protected: `tests/**`

**Warnings:**

- writable `src/*.py` is a pattern: the agent may change every file it matches

## Validations

- `target`: `python -m pytest tests/test_new.py`, at least 1 tests, environment `argus`; required new tests: 1, required existing tests: 0
  - new: `tests/test_new.py::test_total_never_negative`
- `regression`: `python -m pytest tests/test_old.py`, at least 1 tests, environment `argus`; required new tests: 0, required existing tests: 1
  - existing: `tests/test_old.py::test_total_plain`

Budget profile for the agent: `large`

## New tests

### `tests/test_new.py`

On the code as it is now, validation `target`: `test_total_never_negative` FAIL

Why they fail now (test output; check that this is the behaviour to fix):

```text
tests/test_new.py:5: in test_total_never_negative
E       assert 1 == 0
E        +  where 1 = total([1], 5)
==== 1 failed, 0 passed, 0 errors in Xs ====
```

The file:

```python
from src.shop import total


def test_total_never_negative():
    assert total([1], 5) == 0

```

## Not verified automatically

- the error message reads well

## Cost

Drafter: $0.0123, 4 model calls, 1 submits, 3 steps (ended: submitted).

## Approve

`approve_draft.py` checks the draft again under your task name, issue, cap and attempt limit, and publishes it only with `--approve`. Without a reference patch the task is recorded as `feasibility: unproven`; with one (`--reference-patch <patch>` instead of `--no-reference`) it is proven before the agent runs.

```bash
python scripts/approve_draft.py --draft runs/d1/draft.json --task <name> --issue-file runs/d1/issue.txt --max-usd <cap> --max-iterations <n> --no-reference
```
