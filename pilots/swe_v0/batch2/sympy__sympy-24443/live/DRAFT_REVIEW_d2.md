# Draft review: `base` (j20261024_181455_d71c-d2)

Status: **DRAFTED** (a draft passed its check)

Written by the harness from the draft and its check. The draft itself was written by a model: read the tests. A passing baseline shows only that the new tests fail now, not that they test the right thing.

## Issue

````text
`_check_homomorphism` is broken on PermutationGroups
```python
In [1]: from sympy.combinatorics import *
   ...: from sympy.combinatorics.homomorphisms import homomorphism
   ...: D3 = DihedralGroup(3)
   ...: T = homomorphism(D3, D3, D3.generators, D3.generators)

ValueError: The given images do not define a homomorphism
```

The issue is in the internal `_image()` function, where it handles the case of a `PermutationGroup`:

https://github.com/sympy/sympy/blob/809c53c077485ca48a206cee78340389cb83b7f1/sympy/combinatorics/homomorphisms.py#L336-L337

When `r[i]` is an inverted generator, the `in gens` test fails.

I think the whole thing can be greatly simplified.
````

## Plan

Files: `sympy/combinatorics/homomorphisms.py`

Steps:
- Rewrite the inner `_image` helper of `_check_homomorphism` so that, for a `PermutationGroup` domain, it walks the relator's `array_form` (symbol index, exponent) and looks the corresponding element up in `domain.generators` (or in the presentation generators) instead of comparing `r[i]` against the presentation generators.
- Apply the exponent with its sign, i.e. use `images[s]**power` for positive powers and the inverse image raised to `-power` for negative powers, so an inverted generator is never silently dropped.
- Keep the FpGroup/FreeGroup relator branch (`codomain.equals` / `make_confluent`) and the return convention (True/False) unchanged, so `group_isomorphism` and the existing `test_check_homomorphism` rejection case keep working.
- Verify with `homomorphism(DihedralGroup(3), DihedralGroup(3), D3.generators, D3.generators)` that the created map sends each generator to itself.

Risks:
- Mapping the presentation's generator symbols to the wrong entries of `domain.generators` (the presentation may eliminate or reorder generators), giving a wrong image.
- Losing the sign of the exponent so that `g**-1` is mapped to `images[g]**power` instead of `images[g]**-power`, which still accepts invalid maps or rejects valid ones.
- Making the check trivially true (e.g. returning True early or ignoring relators), which breaks the existing rejection test `homomorphism(G, G, [a], [a])` in `sympy/combinatorics/tests/test_homomorphisms.py`.
- Changing the return type of `_check_homomorphism` (e.g. returning None) and so breaking `group_isomorphism`, which uses it as a truth value.

## Scope

Writable: `sympy/combinatorics/homomorphisms.py`

Protected: `sympy/combinatorics/tests/**`, `sympy/combinatorics/named_groups.py`, `sympy/combinatorics/perm_groups.py`

No scope warnings.

## Validations

- `target`: `python -m pytest sympy/combinatorics/tests/test_homomorphisms_permutation_groups.py`, at least 2 tests, environment `sympy`; required new tests: 2, required existing tests: 0
  - new: `sympy/combinatorics/tests/test_homomorphisms_permutation_groups.py::test_check_homomorphism_permutation_group_identity`
  - new: `sympy/combinatorics/tests/test_homomorphisms_permutation_groups.py::test_homomorphism_permutation_group_onto_itself`
- `regression`: `python -m pytest sympy/combinatorics/tests/test_homomorphisms.py`, at least 3 tests, environment `sympy`; required new tests: 0, required existing tests: 3
  - existing: `sympy/combinatorics/tests/test_homomorphisms.py::test_homomorphism`
  - existing: `sympy/combinatorics/tests/test_homomorphisms.py::test_isomorphisms`
  - existing: `sympy/combinatorics/tests/test_homomorphisms.py::test_check_homomorphism`

Budget profile for the agent: `large_usd`

Tools added for the agent: `edit_file`

## New tests

### `sympy/combinatorics/tests/test_homomorphisms_permutation_groups.py`

On the code as it is now, validation `target`: `test_check_homomorphism_permutation_group_identity` FAIL, `test_homomorphism_permutation_group_onto_itself` FAIL

Why they fail now (test output; check that this is the behaviour to fix):

```text
sympy/combinatorics/tests/test_homomorphisms_permutation_groups.py:13: in test_check_homomorphism_permutation_group_identity
E   assert False
E    +  where False = _check_homomorphism(PermutationGroup([\n    (0 1 2),\n    (0 2)]), PermutationGroup([\n    (0 1 2),\n    (0 2)]), {Permutation(0, 1, 2)...
sympy/combinatorics/tests/test_homomorphisms_permutation_groups.py:23: in test_homomorphism_permutation_group_onto_itself
E   AssertionError: ValueError('The given images do not define a homomorphism')
============================== 2 failed in Xs ===============================
```

The file:

```python
from sympy.combinatorics.named_groups import DihedralGroup
from sympy.combinatorics.homomorphisms import (
    GroupHomomorphism, homomorphism, _check_homomorphism)


def test_check_homomorphism_permutation_group_identity():
    # Sending each generator of D3 to itself is a homomorphism, so the
    # check has to accept it.  The relators of a permutation group's
    # presentation contain inverted generators; those used to be dropped
    # silently by the image computation of ``_check_homomorphism``.
    D3 = DihedralGroup(3)
    images = dict(zip(D3.generators, D3.generators))
    assert _check_homomorphism(D3, D3, images)


def test_homomorphism_permutation_group_onto_itself():
    D3 = DihedralGroup(3)
    failure = None
    try:
        T = homomorphism(D3, D3, D3.generators, D3.generators)
    except ValueError as exc:
        failure = exc
    assert failure is None, failure
    assert isinstance(T, GroupHomomorphism)
    for g in D3.generators:
        assert T(g) == g

```

## Not verified automatically

- The issue also asks that the check be 'greatly simplified'; no test can measure simplicity, only that the identity map of D3 is accepted and that invalid images are still rejected (the latter is only covered by the existing test file).
- The behaviour of `_check_homomorphism` for a PermutationGroup whose presentation eliminates generators, or for groups with more than two generators, is not exercised by the new tests; only DihedralGroup(3) is used.
- The FpGroup codomain branch of the relator check (including the `make_confluent` fallback) is untouched by the new tests and remains covered only by sympy/combinatorics/tests/test_homomorphisms.py.

## Cost

Drafter: $0.0126, 9 model calls, 1 submits, 8 steps (ended: submitted).

## Approve

`approve_draft.py` checks the draft again under your task name, issue, cap and attempt limit, and publishes it only with `--approve`. Without a reference patch the task is recorded as `feasibility: unproven`; with one (`--reference-patch <patch>` instead of `--no-reference`) it is proven before the agent runs.

```bash
python scripts/approve_draft.py --draft runs/j20261024_181455_d71c-d2/draft.json --task <name> --issue-file runs/j20261024_181455_d71c-d2/issue.txt --max-usd <cap> --max-iterations <n> --no-reference
```
