# Draft review: `base` (j20261024_181455_d71c-d1)

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
- Reproduce: mapping DihedralGroup(3)'s generators to themselves makes `_check_homomorphism` return False, so `homomorphism` raises ValueError.
- Rewrite `_image` inside `_check_homomorphism` so that relator letters are translated to the corresponding domain generator (the presentation generator at position i corresponds to `domain.generators[i]`) and the image of the letter is looked up whether the letter is a generator or an inverse generator.
- Multiply the image by `images[g]**power` using the sign of the exponent taken from `r.array_form` instead of skipping unhandled letters, and keep the same return type (True/False) for the identity comparison.
- Keep the FpGroup/FreeGroup paths (relators from `domain.relators`, codomain equality via `codomain.equals`) working unchanged.
- Run the new tests and the existing homomorphism test file.

Risks:
- Mismapping presentation generators to `domain.generators` (index/order mismatch) so genuine homomorphisms are still rejected or wrong ones accepted.
- Handling only positive powers and dropping the `power` sign, so relators with inverse letters are mis-evaluated.
- Changing behaviour for FpGroup/FreeGroup domains or for codomains that are FpGroups, breaking `test_homomorphism`/`test_isomorphisms` or `group_isomorphism`.
- Returning a SymPy Boolean or None instead of a truth value for the codomain identity comparison.
- Weakening the check so that `_check_homomorphism` accepts images that are not a homomorphism (e.g. the existing `test_check_homomorphism` case must keep raising ValueError).

## Scope

Writable: `sympy/combinatorics/homomorphisms.py`

Protected: `sympy/combinatorics/tests/**`, `sympy/combinatorics/tests/test_homomorphisms_permutation_check.py`, `sympy/testing/**`, `conftest.py`, `sympy/conftest.py`, `pytest.ini`

No scope warnings.

## Validations

- `target`: `python -m pytest sympy/combinatorics/tests/test_homomorphisms_permutation_check.py`, at least 3 tests, environment `sympy`; required new tests: 2, required existing tests: 0
  - new: `sympy/combinatorics/tests/test_homomorphisms_permutation_check.py::test_check_homomorphism_for_permutation_group_identity_map`
  - new: `sympy/combinatorics/tests/test_homomorphisms_permutation_check.py::test_homomorphism_from_permutation_group_to_itself`
- `regression`: `python -m pytest sympy/combinatorics/tests/test_homomorphisms.py`, at least 3 tests, environment `sympy`; required new tests: 0, required existing tests: 3
  - existing: `sympy/combinatorics/tests/test_homomorphisms.py::test_homomorphism`
  - existing: `sympy/combinatorics/tests/test_homomorphisms.py::test_isomorphisms`
  - existing: `sympy/combinatorics/tests/test_homomorphisms.py::test_check_homomorphism`

Budget profile for the agent: `large_usd`

Tools added for the agent: `edit_file`, `search_files`

## New tests

### `sympy/combinatorics/tests/test_homomorphisms_permutation_check.py`

On the code as it is now, validation `target`: `test_check_homomorphism_for_permutation_group_identity_map` FAIL, `test_homomorphism_from_permutation_group_to_itself` FAIL

Why they fail now (test output; check that this is the behaviour to fix):

```text
sympy/combinatorics/tests/test_homomorphisms_permutation_check.py:12: in test_check_homomorphism_for_permutation_group_identity_map
E   assert False
E    +  where False = _check_homomorphism(PermutationGroup([\n    (0 1 2),\n    (0 2)]), PermutationGroup([\n    (0 1 2),\n    (0 2)]), {Permutation(0, 1, 2)...
sympy/combinatorics/tests/test_homomorphisms_permutation_check.py:22: in test_homomorphism_from_permutation_group_to_itself
E   assert None is not None
========================= 2 failed, 1 passed in Xs ==========================
```

The file:

```python
from sympy.combinatorics import Permutation
from sympy.combinatorics.perm_groups import PermutationGroup
from sympy.combinatorics.homomorphisms import homomorphism, _check_homomorphism
from sympy.combinatorics.named_groups import DihedralGroup


def test_check_homomorphism_for_permutation_group_identity_map():
    # mapping every generator of a PermutationGroup to itself is a
    # homomorphism, so the internal check must accept it
    D3 = DihedralGroup(3)
    images = dict(zip(D3.generators, D3.generators))
    assert _check_homomorphism(D3, D3, images)


def test_homomorphism_from_permutation_group_to_itself():
    D3 = DihedralGroup(3)
    gens = D3.generators
    try:
        T = homomorphism(D3, D3, gens, gens)
    except ValueError:
        T = None
    assert T is not None
    r, s = gens
    assert T(r) == r
    assert T(s) == s
    assert T.image().order() == D3.order()


def test_check_homomorphism_rejects_bad_images_for_permutation_group():
    # the images of the generators do not define a homomorphism here,
    # so the check must keep returning a false value
    a = Permutation(1, 2, 3, 4)
    b = Permutation(1, 3)
    G = PermutationGroup([a, b])
    assert not _check_homomorphism(G, G, {a: a, b: G.identity})

```

## Not verified automatically

- The issue also asks for the `_image` helper to be greatly simplified; no test can check how simple or readable the rewritten code is.
- Whether `_check_homomorphism` handles presentation relators whose letters mix inverses and powers for arbitrary groups (only the DihedralGroup(3) case from the report and one rejection case are asserted).

## Cost

Drafter: $0.0152, 10 model calls, 1 submits, 9 steps (ended: submitted).

## Approve

`approve_draft.py` checks the draft again under your task name, issue, cap and attempt limit, and publishes it only with `--approve`. Without a reference patch the task is recorded as `feasibility: unproven`; with one (`--reference-patch <patch>` instead of `--no-reference`) it is proven before the agent runs.

```bash
python scripts/approve_draft.py --draft runs/j20261024_181455_d71c-d1/draft.json --task <name> --issue-file runs/j20261024_181455_d71c-d1/issue.txt --max-usd <cap> --max-iterations <n> --no-reference
```
