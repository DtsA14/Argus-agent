# Draft review: `base` (j20261024_175159_6482-d1)

Status: **DRAFTED** (a draft passed its check)

Written by the harness from the draft and its check. The draft itself was written by a model: read the tests. A passing baseline shows only that the new tests fail now, not that they test the right thing.

## Issue

````text
`PolyElement.as_expr()` not accepting symbols
The method `PolyElement.as_expr()`

https://github.com/sympy/sympy/blob/193e3825645d93c73e31cdceb6d742cc6919624d/sympy/polys/rings.py#L618-L624

is supposed to let you set the symbols you want to use, but, as it stands, either you pass the wrong number of symbols, and get an error message, or you pass the right number of symbols, and it ignores them, using `self.ring.symbols` instead:

```python
>>> from sympy import ring, ZZ, symbols
>>> R, x, y, z = ring("x,y,z", ZZ)
>>> f = 3*x**2*y - x*y*z + 7*z**3 + 1
>>> U, V, W = symbols("u,v,w")
>>> f.as_expr(U, V, W)
3*x**2*y - x*y*z + 7*z**3 + 1
```
````

## Plan

Files: `sympy/polys/rings.py`

Steps:
- In PolyElement.as_expr, raise the ValueError only when symbols were given and their count differs from ring.ngens.
- Fall back to self.ring.symbols only when no symbols were passed (replace the `else:` branch that currently always overwrites symbols with an `if not symbols:` branch).
- Keep the existing call expr_from_dict(self.as_expr_dict(), *symbols), which already zips the given generators with the monomials, so no other change is needed.
- Optionally note in the docstring that the given symbols are used for the conversion.

Risks:
- Checking the count before assigning the default, otherwise the given symbols are still clobbered.
- Using `symbols = symbols or self.ring.symbols` style code that mishandles an empty argument list.
- Breaking FracElement.as_expr in polys/fields.py, which forwards *symbols to numer.as_expr/denom.as_expr.
- Changing the error message text that existing callers/tests do not depend on, or dropping the ValueError for a wrong count.

## Scope

Writable: `sympy/polys/rings.py`

Protected: `sympy/polys/tests/**`, `sympy/polys/fields.py`, `sympy/polys/polyutils.py`

No scope warnings.

## Validations

- `target`: `python -m pytest sympy/polys/tests/test_rings_as_expr.py`, at least 4 tests, environment `sympy`; required new tests: 3, required existing tests: 0
  - new: `sympy/polys/tests/test_rings_as_expr.py::test_as_expr_uses_given_symbols`
  - new: `sympy/polys/tests/test_rings_as_expr.py::test_as_expr_given_symbols_univariate`
  - new: `sympy/polys/tests/test_rings_as_expr.py::test_as_expr_given_symbols_have_no_ring_symbols`
- `regression_rings`: `python -m pytest sympy/polys/tests/test_rings.py`, at least 50 tests, environment `sympy`; required new tests: 0, required existing tests: 1
  - existing: `sympy/polys/tests/test_rings.py::test_PolyElement_as_expr`
- `regression_fields`: `python -m pytest sympy/polys/tests/test_fields.py::test_FracElement_as_expr`, at least 1 tests, environment `sympy`; required new tests: 0, required existing tests: 1
  - existing: `sympy/polys/tests/test_fields.py::test_FracElement_as_expr`

Budget profile for the agent: `large_usd`

Tools added for the agent: `edit_file`, `search_files`

## New tests

### `sympy/polys/tests/test_rings_as_expr.py`

On the code as it is now, validation `target`: `test_as_expr_uses_given_symbols` FAIL, `test_as_expr_given_symbols_univariate` FAIL, `test_as_expr_given_symbols_have_no_ring_symbols` FAIL

Why they fail now (test output; check that this is the behaviour to fix):

```text
sympy/polys/tests/test_rings_as_expr.py:15: in test_as_expr_uses_given_symbols
E   assert 3*x**2*y - x*y*z + 7*z**3 + 1 == (((((3 * (u ** 2)) * v) - ((u * v) * w)) + (7 * (w ** 3))) + 1)
E    +  where 3*x**2*y - x*y*z + 7*z**3 + 1 = as_expr(u, v, w)
E    +    where as_expr = 3*x**2*y - x*y*z + 7*z**3 + 1.as_expr
sympy/polys/tests/test_rings_as_expr.py:24: in test_as_expr_given_symbols_univariate
E   assert x**3 - 2*x + 4 == (((t ** 3) - (2 * t)) + 4)
E    +  where x**3 - 2*x + 4 = as_expr(t)
E    +    where as_expr = x**3 - 2*x + 4.as_expr
sympy/polys/tests/test_rings_as_expr.py:34: in test_as_expr_given_symbols_have_no_ring_symbols
E   assert x**2/2 + x*y - y**2 == ((((a ** 2) / 2) + (a * b)) - (b ** 2))
========================= 3 failed, 1 passed in Xs ==========================
```

The file:

```python
"""PolyElement.as_expr must convert with the symbols it is given. """

from sympy.core.symbol import symbols
from sympy.polys.domains import ZZ, QQ
from sympy.polys.rings import ring
from sympy.testing.pytest import raises


def test_as_expr_uses_given_symbols():
    R, x, y, z = ring("x,y,z", ZZ)
    f = 3*x**2*y - x*y*z + 7*z**3 + 1

    u, v, w = symbols("u,v,w")

    assert f.as_expr(u, v, w) == 3*u**2*v - u*v*w + 7*w**3 + 1


def test_as_expr_given_symbols_univariate():
    R, x = ring("x", ZZ)
    f = x**3 - 2*x + 4

    t = symbols("t")

    assert f.as_expr(t) == t**3 - 2*t + 4


def test_as_expr_given_symbols_have_no_ring_symbols():
    R, x, y = ring("x,y", QQ)
    f = x**2/2 + x*y - y**2

    a, b = symbols("a,b")
    expr = f.as_expr(a, b)

    assert expr == a**2/2 + a*b - b**2
    assert expr.free_symbols == {a, b}


def test_as_expr_default_symbols_and_wrong_count():
    R, x, y, z = ring("x,y,z", ZZ)
    f = 3*x**2*y - x*y*z + 7*z**3 + 1

    X, Y, Z = symbols("x,y,z")
    g = 3*X**2*Y - X*Y*Z + 7*Z**3 + 1

    assert f.as_expr() == g
    assert f.as_expr(X, Y, Z) == g

    u, v, w, t = symbols("u,v,w,t")
    raises(ValueError, lambda: f.as_expr(u, v))
    raises(ValueError, lambda: f.as_expr(u, v, w, t))

```

## Not verified automatically

- The exact wording of the ValueError raised for a wrong number of symbols is not asserted by any test (only that ValueError is raised).
- Any docstring or example added to PolyElement.as_expr is not checked by a test.
- Whether FracElement.as_expr also honours user supplied symbols is not asserted by a new test; it delegates to PolyElement.as_expr, so it changes as a side effect only.

## Cost

Drafter: $0.0172, 12 model calls, 2 submits, 11 steps (ended: submitted).

## Approve

`approve_draft.py` checks the draft again under your task name, issue, cap and attempt limit, and publishes it only with `--approve`. Without a reference patch the task is recorded as `feasibility: unproven`; with one (`--reference-patch <patch>` instead of `--no-reference`) it is proven before the agent runs.

```bash
python scripts/approve_draft.py --draft runs/j20261024_175159_6482-d1/draft.json --task <name> --issue-file runs/j20261024_175159_6482-d1/issue.txt --max-usd <cap> --max-iterations <n> --no-reference
```
