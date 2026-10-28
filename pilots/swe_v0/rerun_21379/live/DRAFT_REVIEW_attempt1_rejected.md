# Draft review: `base` (j20261027_175610_34ba-d1)

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

Files: `sympy/core/power.py`, `sympy/core/mul.py`, `sympy/core/function.py`, `sympy/functions/elementary/exponential.py`, `sympy/functions/elementary/piecewise.py`, `sympy/core/expr.py`, `sympy/core/basic.py`, `sympy/polys/polytools.py`

Steps:
- Reproduce the issue's snippet (real x, y, z; clear_cache(); exp(sinh(Piecewise((x, y > x), (y, True))/z)).subs({1: 1.0})) and read the full traceback to find which `_eval_subs`/assumption helper on the substitution path hands a `Piecewise` to `Poly`, ending in `sympy/polys/polytools.py::_parallel_poly_from_expr` and the 'Piecewise generators do not make sense' error.
- Guard that call site so a `Piecewise` (or any sub-expression that is not a valid polynomial generator) never reaches `_parallel_poly_from_expr`, returning None / falling back to the plain recursive substitution instead of raising.
- Make sure `subs` of a value that does not occur in the expression (here `1 -> 1.0`) does not raise for real and for plain symbols, and that it still returns the same unchanged expression it returns today when the cache is warm.
- Run the new regression test, the named subs regression tests, and by hand the whole sympy/core/tests/test_subs.py and the piecewise/hyperbolic/exponential suites.

Risks:
- A guard placed too high could disable legitimate substitutions of Pow/Mul patterns that the subs tests rely on.
- Returning None where a caller expects a value could silently change the result of `subs` on expressions containing a Piecewise.
- The failure is cache- and assumption-dependent (it needs real x, y and a cold cache); a fix that only works on the already-cached path leaves the first call broken.
- Swallowing `PolynomialError` inside the polys layer would hide genuine polynomial errors raised elsewhere.
- The whole of sympy/core/tests/test_subs.py cannot be used as regression validation here because it contains an xfail; the regression validation therefore names individual subs tests that pass on the baseline - re-run the whole file by hand.

## Scope

Writable: `sympy/core/basic.py`, `sympy/core/expr.py`, `sympy/core/function.py`, `sympy/core/mul.py`, `sympy/core/power.py`, `sympy/functions/elementary/exponential.py`, `sympy/functions/elementary/piecewise.py`, `sympy/polys/polytools.py`

Protected: `sympy/core/tests/test_piecewise_subs.py`, `sympy/**/tests/*.py`, `conftest.py`, `sympy/conftest.py`, `pytest.ini`

No scope warnings.

## Validations

- `target`: `python -m pytest sympy/core/tests/test_piecewise_subs.py`, at least 2 tests, environment `sympy_py39`; required new tests: 1, required existing tests: 0
  - new: `sympy/core/tests/test_piecewise_subs.py::test_subs_with_piecewise_hyperbolic_real_symbols`
- `regression`: `python -m pytest sympy/core/tests/test_subs.py::test_RootOf_issue_10092 sympy/core/tests/test_subs.py::test_issue_8886 sympy/core/tests/test_subs.py::test_issue_12657 sympy/core/tests/test_subs.py::test_recurse_Application_args sympy/core/tests/test_subs.py::test_Subs_subs sympy/core/tests/test_subs.py::test_issue_13333 sympy/core/tests/test_subs.py::test_issue_15234 sympy/core/tests/test_subs.py::test_issue_6976 sympy/core/tests/test_subs.py::test_issue_11746 sympy/core/tests/test_subs.py::test_issue_17823 sympy/core/tests/test_subs.py::test_issue_19326 sympy/core/tests/test_subs.py::test_issue_19558`, at least 12 tests, environment `sympy_py39`; required new tests: 0, required existing tests: 0

Budget profile for the agent: `large_usd`

Tools added for the agent: `edit_file`, `search_files`

## New tests

### `sympy/core/tests/test_piecewise_subs.py`

On the code as it is now, validation `target`: `test_subs_with_piecewise_hyperbolic_real_symbols` FAIL

Why they fail now (test output; check that this is the behaviour to fix):

```text
sympy/core/tests/test_piecewise_subs.py:41: in test_subs_with_piecewise_hyperbolic_real_symbols
    _assert_no_exception(result, 1, 1.0)
sympy/core/tests/test_piecewise_subs.py:27: in _assert_no_exception
E   AssertionError: subs({1: 1.0}) raised PolynomialError: Piecewise generators do not make sense
==================== 1 failed, 1 passed, 1 warning in Xs ====================
```

The file:

```python
"""Regression test for a spurious ``PolynomialError`` raised by ``subs``.

For an expression built from a Piecewise with a relational condition, a
division and a hyperbolic function under an exponential, substituting a
value that does not even occur in the expression used to raise
``PolynomialError: Piecewise generators do not make sense`` when the
symbols are real and the cache is cold.
"""

from sympy import Piecewise, exp, sinh, symbols
from sympy.core.cache import clear_cache


def _subs_or_exception(expr, old, new):
    """Return ``expr.subs({old: new})`` or the raised exception.

    Returning the exception instead of letting it propagate lets the test
    report the spurious error with an assertion instead of an error.
    """
    try:
        return expr.subs({old: new})
    except Exception as exc:
        return exc


def _assert_no_exception(result, old, new):
    assert not isinstance(result, Exception), (
        "subs({%s: %s}) raised %s: %s" % (
            old, new, type(result).__name__, result))


def test_subs_with_piecewise_hyperbolic_real_symbols():
    # a cold cache is what makes the spurious PolynomialError show up
    clear_cache()
    x, y, z = symbols('x y z', real=True)
    expr = exp(sinh(Piecewise((x, y > x), (y, True)) / z))

    result = _subs_or_exception(expr, 1, 1.0)

    # substituting a value that does not occur in expr must not raise
    _assert_no_exception(result, 1, 1.0)


def test_subs_with_piecewise_hyperbolic_plain_symbols():
    # without the real assumptions the same substitution does not raise
    clear_cache()
    x, y, z = symbols('x y z')
    expr = exp(sinh(Piecewise((x, y > x), (y, True)) / z))

    result = _subs_or_exception(expr, 1, 1.0)

    _assert_no_exception(result, 1, 1.0)

```

## Not verified automatically

- That the same spurious error for other nested functions (cosh, tanh, sin, log in place of sinh, or other unary outer functions in place of exp) is gone: only exp(sinh(Piecewise(...)/z)) is tested.
- The cache dependence reported in the issue (a second .subs({1: 1.0}) call in the same session already worked) is not asserted; every test starts from a cleared cache.
- The reporter's original motivation, casting int atoms to float before a TensorFlow lambdify, is not exercised.
- That the real cause is a Poly construction with a Piecewise generator is only implied by the issue's error message; the tests check the observable behaviour, not the internal call path.

## Cost

Drafter: $0.0515, 16 model calls, 4 submits, 15 steps (ended: submitted).

## Approve

`approve_draft.py` checks the draft again under your task name, issue, cap and attempt limit, and publishes it only with `--approve`. Without a reference patch the task is recorded as `feasibility: unproven`; with one (`--reference-patch <patch>` instead of `--no-reference`) it is proven before the agent runs.

```bash
python scripts/approve_draft.py --draft runs/j20261027_175610_34ba-d1/draft.json --task <name> --issue-file runs/j20261027_175610_34ba-d1/issue.txt --max-usd <cap> --max-iterations <n> --no-reference
```
