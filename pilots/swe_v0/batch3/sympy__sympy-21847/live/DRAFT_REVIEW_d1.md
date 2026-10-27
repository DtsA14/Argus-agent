# Draft review: `base` (j20261027_151126_f6bf-d1)

Status: **DRAFTED** (a draft passed its check)

Written by the harness from the draft and its check. The draft itself was written by a model: read the tests. A passing baseline shows only that the new tests fail now, not that they test the right thing.

## Issue

````text
itermonomials returns incorrect monomials when using min_degrees argument
`itermonomials` returns incorrect monomials when using optional `min_degrees` argument

For example, the following code introduces three symbolic variables and generates monomials with max and min degree of 3:


```
import sympy as sp
from sympy.polys.orderings import monomial_key

x1, x2, x3 = sp.symbols('x1, x2, x3')
states = [x1, x2, x3]
max_degrees = 3
min_degrees = 3
monomials = sorted(sp.itermonomials(states, max_degrees, min_degrees=min_degrees), 
                   key=monomial_key('grlex', states))
print(monomials)
```
The code returns `[x3**3, x2**3, x1**3]`, when it _should_ also return monomials such as `x1*x2**2, x2*x3**2, etc...` that also have total degree of 3. This behaviour is inconsistent with the documentation that states that 

> A generator of all monomials `monom` is returned, such that either `min_degree <= total_degree(monom) <= max_degree`...

The monomials are also missing when `max_degrees` is increased above `min_degrees`.
````

## Plan

Files: `sympy/polys/monomials.py`

Steps:
- In the total-degree branch of `itermonomials`, change the commutative filter `max(powers.values()) >= min_degree` to use the total degree `sum(powers.values()) >= min_degree`, so that monomials with padded `S.One` factors (degree below `max_degree`) are kept whenever their total degree is at least `min_degree`.
- Apply the same `sum(powers.values()) >= min_degree` change to the non-commutative loop, which also filters by the largest single-variable exponent instead of the total degree.
- Leave the argument validation, the `min_degree > max_degree` shortcut and the degree-list (Case II) branch untouched, and keep the docstring examples valid.

Risks:
- Filtering by `len(item)` or by the padded length would count the `S.One` padding as degree and yield monomials of total degree below `min_degree`.
- Touching the degree-list branch or the `min_degree > max_degree` early return would regress existing behaviour in `sympy/polys/tests/test_monomials.py`.
- Dropping or reordering the `set(...)` de-duplication changes the yield order, which the docs do not fix but the non-commutative case relies on for unique monomials.
- Counting exponents of the appended `S.One` sentinel as a variable would break the total degree computation.

## Scope

Writable: `sympy/polys/monomials.py`

Protected: `sympy/polys/tests/**`, `sympy/polys/__init__.py`, `sympy/__init__.py`

No scope warnings.

## Validations

- `target`: `python -m pytest sympy/polys/tests/test_itermonomials.py`, at least 6 tests, environment `sympy_py39`; required new tests: 5, required existing tests: 0
  - new: `sympy/polys/tests/test_itermonomials.py::test_itermonomials_min_degrees_equal_to_max_degrees`
  - new: `sympy/polys/tests/test_itermonomials.py::test_itermonomials_min_degrees_below_max_degrees`
  - new: `sympy/polys/tests/test_itermonomials.py::test_itermonomials_min_degrees_cases`
  - new: `sympy/polys/tests/test_itermonomials.py::test_itermonomials_min_degrees_noncommutative`
  - new: `sympy/polys/tests/test_itermonomials.py::test_itermonomials_min_degrees_mixed_commutativity`
- `regression`: `python -m pytest sympy/polys/tests/test_monomials.py`, at least 11 tests, environment `sympy_py39`; required new tests: 0, required existing tests: 11
  - existing: `sympy/polys/tests/test_monomials.py::test_monomials`
  - existing: `sympy/polys/tests/test_monomials.py::test_monomial_count`
  - existing: `sympy/polys/tests/test_monomials.py::test_monomial_mul`
  - existing: `sympy/polys/tests/test_monomials.py::test_monomial_div`
  - existing: `sympy/polys/tests/test_monomials.py::test_monomial_gcd`
  - existing: `sympy/polys/tests/test_monomials.py::test_monomial_lcm`
  - existing: `sympy/polys/tests/test_monomials.py::test_monomial_max`
  - existing: `sympy/polys/tests/test_monomials.py::test_monomial_pow`
  - existing: `sympy/polys/tests/test_monomials.py::test_monomial_min`
  - existing: `sympy/polys/tests/test_monomials.py::test_monomial_divides`
  - existing: `sympy/polys/tests/test_monomials.py::test_Monomial`

Budget profile for the agent: `large_usd`

Tools added for the agent: `edit_file`

## New tests

### `sympy/polys/tests/test_itermonomials.py`

On the code as it is now, validation `target`: `test_itermonomials_min_degrees_equal_to_max_degrees` FAIL, `test_itermonomials_min_degrees_below_max_degrees` FAIL, `test_itermonomials_min_degrees_cases` FAIL, `test_itermonomials_min_degrees_noncommutative` FAIL, `test_itermonomials_min_degrees_mixed_commutativity` FAIL

Why they fail now (test output; check that this is the behaviour to fix):

```text
sympy/polys/tests/test_itermonomials.py:59: in test_itermonomials_min_degrees_cases
E   assert {x**2*y, y**3... x**2, x*y**2} == {x*y, x**2*y,...*3, x**2, ...}
E     
E     (pytest_assertion plugin: representation of details failed: /workspace/sympy/core/relational.py:398: TypeError: cannot determine truth value of Relatio...
E      Probably an object has a faulty __repr__.)
sympy/polys/tests/test_itermonomials.py:67: in test_itermonomials_min_degrees_noncommutative
E   assert {b**2, a**2} == {b*a, a*b, a**2, b**2}
E     
E     (pytest_assertion plugin: representation of details failed: /workspace/sympy/core/relational.py:398: TypeError: cannot determine truth value of Relatio...
E      Probably an object has a faulty __repr__.)
sympy/polys/tests/test_itermonomials.py:76: in test_itermonomials_min_degrees_mixed_commutativity
E   assert {a**2, x**2} == {x*a, a**2, x**2}
E     
E     (pytest_assertion plugin: representation of details failed: /workspace/sympy/core/relational.py:398: TypeError: cannot determine truth value of Relatio...
E      Probably an object has a faulty __repr__.)
========================= 5 failed, 1 passed in Xs ==========================
```

The file:

```python
"""Tests for itermonomials with a non-zero minimum total degree. """

from itertools import product

from sympy.core import Mul, S, symbols
from sympy.polys.monomials import itermonomials


def monomials_between_degrees(variables, max_degree, min_degree):
    """Reference enumeration of every monomial in ``variables`` whose
    total degree lies between ``min_degree`` and ``max_degree``."""
    monomials = set()
    for exponents in product(range(max_degree + 1), repeat=len(variables)):
        if min_degree <= sum(exponents) <= max_degree:
            monomials.add(Mul(*[var**exp for var, exp in
                                zip(variables, exponents)]))
    return monomials


def test_itermonomials_min_degrees_equal_to_max_degrees():
    x1, x2, x3 = symbols('x1 x2 x3')
    states = [x1, x2, x3]

    monomials = set(itermonomials(states, 3, min_degrees=3))

    assert monomials == {
        x1**3, x2**3, x3**3,
        x1**2*x2, x1**2*x3, x2**2*x1, x2**2*x3, x3**2*x1, x3**2*x2,
        x1*x2*x3,
    }


def test_itermonomials_min_degrees_below_max_degrees():
    x1, x2, x3 = symbols('x1 x2 x3')
    variables = [x1, x2, x3]

    monomials = set(itermonomials(variables, 3, min_degrees=2))

    assert monomials == monomials_between_degrees(variables, 3, 2)
    assert x1*x2 in monomials
    assert x1*x2*x3 in monomials
    assert x1 not in monomials


def test_itermonomials_min_degrees_cases():
    x, y, z = symbols('x y z')

    cases = [
        ([x, y], 3, 2),
        ([x, y], 4, 3),
        ([x, y, z], 2, 2),
        ([x, y, z], 3, 3),
        ([x, y, z], 4, 2),
        ([x, y, z], 4, 3),
    ]

    for variables, max_degree, min_degree in cases:
        expected = monomials_between_degrees(variables, max_degree, min_degree)
        assert set(itermonomials(variables, max_degree, min_degree)) == expected


def test_itermonomials_min_degrees_noncommutative():
    a, b = symbols('a b', commutative=False)

    monomials = set(itermonomials([a, b], 2, min_degrees=2))

    assert monomials == {a**2, a*b, b*a, b**2}


def test_itermonomials_min_degrees_mixed_commutativity():
    x = symbols('x')
    a = symbols('a', commutative=False)

    monomials = set(itermonomials([x, a], 2, min_degrees=2))

    assert monomials == {x**2, a**2, x*a, a*x}


def test_itermonomials_default_min_degree_unchanged():
    x, y = symbols('x y')

    assert set(itermonomials([x, y], 2)) == {S.One, x, y, x**2, x*y, y**2}
    assert set(itermonomials([x, y], 2, 1)) == {x, y, x**2, x*y, y**2}
    assert set(itermonomials([x], 3, 2)) == {x**2, x**3}
    assert set(itermonomials([x, y], [2, 4], [1, 2])) == {
        x*y**2, x*y**3, x*y**4,
        x**2*y**2, x**2*y**3, x**2*y**4,
    }

```

## Not verified automatically

- The order in which the generator yields monomials is not specified by the documentation, so no test fixes it.
- The doctest examples in the `itermonomials` docstring are exercised by `bin/doctest`, not by pytest, so they are not part of the validations (they already show the corrected output).
- Performance of the generator for large `max_degree` (the filter change does not alter the enumeration cost) is not checked by any test.

## Cost

Drafter: $0.0166, 9 model calls, 2 submits, 8 steps (ended: submitted).

## Approve

`approve_draft.py` checks the draft again under your task name, issue, cap and attempt limit, and publishes it only with `--approve`. Without a reference patch the task is recorded as `feasibility: unproven`; with one (`--reference-patch <patch>` instead of `--no-reference`) it is proven before the agent runs.

```bash
python scripts/approve_draft.py --draft runs/j20261027_151126_f6bf-d1/draft.json --task <name> --issue-file runs/j20261027_151126_f6bf-d1/issue.txt --max-usd <cap> --max-iterations <n> --no-reference
```
