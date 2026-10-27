# Draft review: `base` (j20261027_151552_7cdd-d1)

Status: **DRAFTED** (a draft passed its check)

Written by the harness from the draft and its check. The draft itself was written by a model: read the tests. A passing baseline shows only that the new tests fail now, not that they test the right thing.

## Issue

````text
Unexpected `PolynomialError` when using simple `subs()` for particular expressions
I am seeing weird behavior with `subs` for particular expressions with hyperbolic sinusoids with piecewise arguments. When applying `subs`, I obtain an unexpected `PolynomialError`. For context, I was umbrella-applying a casting from int to float of all int atoms for a bunch of random expressions before using a tensorflow lambdify to avoid potential tensorflow type errors. You can pretend the expression below has a `+ 1` at the end, but below is the MWE that I could produce.

See the expression below, and the conditions in which the exception arises.

Sympy version: 1.8.dev

```python
from sympy import *
from sympy.core.cache import clear_cache

x, y, z = symbols('x y z')

clear_cache()
expr = exp(sinh(Piecewise((x, y > x), (y, True)) / z))
# This works fine
expr.subs({1: 1.0})

clear_cache()
x, y, z = symbols('x y z', real=True)
expr = exp(sinh(Piecewise((x, y > x), (y, True)) / z))
# This fails with "PolynomialError: Piecewise generators do not make sense"
expr.subs({1: 1.0})  # error
# Now run it again (isympy...) w/o clearing cache and everything works as expected without error
expr.subs({1: 1.0})
```

I am not really sure where the issue is, but I think it has something to do with the order of assumptions in this specific type of expression. Here is what I found-

- The error only (AFAIK) happens with `cosh` or `tanh` in place of `sinh`, otherwise it succeeds
- The error goes away if removing the division by `z`
- The error goes away if removing `exp` (but stays for most unary functions, `sin`, `log`, etc.)
- The error only happens with real symbols for `x` and `y` (`z` does not have to be real)

Not too sure how to debug this one.
````

## Plan

Files: `sympy/polys/polytools.py`, `sympy/core/basic.py`, `sympy/core/expr.py`, `sympy/functions/elementary/piecewise.py`

Steps:
- Reproduce the MWE with real symbols and a cleared cache and capture the traceback into the polynomial-construction helper that raises 'Piecewise generators do not make sense'.
- Trace which automatic evaluation step (subs/fallback reconstruction or Piecewise reconstruction) asks for a polynomial with Piecewise objects as generators.
- Change that path so a Piecewise-containing expression is not passed to polynomial construction as generators, or so the substitution leaves the expression unchanged instead of evaluating it via Poly.
- Run the new regression test plus the subs and Piecewise suites.

Risks:
- A broad catch around the polynomial helper could hide genuine PolynomialError cases and change Poly API behaviour.
- Changing Piecewise subs/reconstruction could alter evaluation of conditions or assumptions and break other substitution tests.
- Clearing the cache inside a test makes the failure order-dependent; the fix must work on a fresh process, not only after cache warm-up.

## Scope

Writable: `sympy/polys/polytools.py`, `sympy/core/basic.py`, `sympy/core/expr.py`, `sympy/functions/elementary/piecewise.py`

Protected: `sympy/**/tests/**`, `conftest.py`, `pytest.ini`, `setup.cfg`

No scope warnings.

## Validations

- `target`: `python -m pytest sympy/core/tests/test_issue_20521.py`, at least 1 tests, environment `sympy_py39`; required new tests: 1, required existing tests: 0
  - new: `sympy/core/tests/test_issue_20521.py::test_subs_int_to_float_with_piecewise_hyperbolic`
- `regression_subs_piecewise`: `python -m pytest sympy/core/tests/test_subs.py::test_subs sympy/functions/elementary/tests/test_piecewise.py::test_issue_7370 sympy/functions/elementary/tests/test_piecewise.py::test_issue_16715 sympy/functions/elementary/tests/test_piecewise.py::test_issue_20360`, at least 4 tests, environment `sympy_py39`; required new tests: 0, required existing tests: 4
  - existing: `sympy/core/tests/test_subs.py::test_subs`
  - existing: `sympy/functions/elementary/tests/test_piecewise.py::test_issue_7370`
  - existing: `sympy/functions/elementary/tests/test_piecewise.py::test_issue_16715`
  - existing: `sympy/functions/elementary/tests/test_piecewise.py::test_issue_20360`
- `regression_polytools`: `python -m pytest sympy/polys/tests/test_polytools.py`, at least 50 tests, environment `sympy_py39`; required new tests: 0, required existing tests: 0

Budget profile for the agent: `large_usd`

Tools added for the agent: `edit_file`, `search_files`

## New tests

### `sympy/core/tests/test_issue_20521.py`

On the code as it is now, validation `target`: `test_subs_int_to_float_with_piecewise_hyperbolic` FAIL

Why they fail now (test output; check that this is the behaviour to fix):

```text
sympy/polys/polytools.py:4399: in _parallel_poly_from_expr
E   sympy.polys.polyerrors.PolynomialError: Piecewise generators do not make sense
sympy/core/tests/test_issue_20521.py:15: in test_subs_int_to_float_with_piecewise_hyperbolic
E   AssertionError: subs raised PolynomialError: Piecewise generators do not make sense
========================= 1 failed, 1 warning in Xs =========================
```

The file:

```python
from sympy import Piecewise, exp, sinh, symbols
from sympy.core.cache import clear_cache


def test_subs_int_to_float_with_piecewise_hyperbolic():
    # This is the MWE from the issue: with real assumptions, substituting
    # an integer by a float inside this expression raised a PolynomialError
    # ("Piecewise generators do not make sense").
    x, y, z = symbols('x y z', real=True)
    clear_cache()
    expr = exp(sinh(Piecewise((x, y > x), (y, True)) / z))
    try:
        expr.subs({1: 1.0})
    except Exception as exc:
        assert False, 'subs raised %s: %s' % (type(exc).__name__, exc)

```

## Not verified automatically

- The issue also reports that a second subs call without clearing the cache succeeds; the test only exercises the cleared-cache path, where the exception occurs.
- The report says replacing sinh by cosh or tanh also triggers the error; the test deliberately uses only the MWE with sinh.

## Cost

Drafter: $0.0310, 16 model calls, 2 submits, 15 steps (ended: submitted).

## Approve

`approve_draft.py` checks the draft again under your task name, issue, cap and attempt limit, and publishes it only with `--approve`. Without a reference patch the task is recorded as `feasibility: unproven`; with one (`--reference-patch <patch>` instead of `--no-reference`) it is proven before the agent runs.

```bash
python scripts/approve_draft.py --draft runs/j20261027_151552_7cdd-d1/draft.json --task <name> --issue-file runs/j20261027_151552_7cdd-d1/issue.txt --max-usd <cap> --max-iterations <n> --no-reference
```
