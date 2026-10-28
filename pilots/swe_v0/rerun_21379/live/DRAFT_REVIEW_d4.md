# Draft review: `base` (j20261027_185915_f13b-d4)

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

Files: `sympy/core/mod.py`, `sympy/polys/polytools.py`, `sympy/core/function.py`

Steps:
- Reproduce with the new test: exp(sinh(Piecewise((x, y > x), (y, True))/z)).subs({1: 1.0}) with real x, y, z.
- Follow the traceback: Mod.eval calls gcd(p, q), which reaches _parallel_poly_from_expr and raises PolynomialError because a generator is a Piecewise.
- Make the Mod/gcd path handle non-polynomial (Piecewise-containing) arguments gracefully instead of raising. e.g. catch PolynomialError and leave the Mod unevaluated or fall back to the non-gcd branch.
- Run the new test and the existing subs and Piecewise regression tests.

Risks:
- Catching the PolynomialError too broadly could hide real errors and change Mod/expr evaluation results.
- A guard placed in the wrong layer could leave the Piecewise as a generator in later gcd/poly calls (failing elsewhere).
- Only the sinh variant may be addressed, leaving the cosh/tanh variants broken.
- Returning an unevaluated form could change printing or equality in existing tests.

## Scope

Writable: `sympy/core/*.py`, `sympy/functions/elementary/*.py`, `sympy/polys/polytools.py`

Protected: `**/test_*.py`, `**/tests/**`, `**/conftest.py`, `pytest.ini`, `setup.py`, `setup.cfg`, `bin/**`, `sympy/testing/**`

**Warnings:**

- writable `sympy/core/*.py` is a pattern: the agent may change every file it matches
- writable `sympy/functions/elementary/*.py` is a pattern: the agent may change every file it matches

## Validations

- `target`: `python -m pytest sympy/core/tests/test_issue_piecewise_subs.py`, at least 1 tests, environment `sympy_py39`; required new tests: 1, required existing tests: 0
  - new: `sympy/core/tests/test_issue_piecewise_subs.py::test_subs_int_to_float_with_piecewise_hyperbolic_argument`
- `regression_subs`: `python -m pytest sympy/core/tests/test_subs.py::test_issue_8886 sympy/core/tests/test_subs.py::test_issue_12657 sympy/core/tests/test_subs.py::test_issue_13333 sympy/core/tests/test_subs.py::test_issue_15234 sympy/core/tests/test_subs.py::test_issue_11746 sympy/core/tests/test_subs.py::test_issue_17823 sympy/core/tests/test_subs.py::test_issue_19326 sympy/core/tests/test_subs.py::test_issue_19558`, at least 8 tests, environment `sympy_py39`; required new tests: 0, required existing tests: 8
  - existing: `sympy/core/tests/test_subs.py::test_issue_8886`
  - existing: `sympy/core/tests/test_subs.py::test_issue_12657`
  - existing: `sympy/core/tests/test_subs.py::test_issue_13333`
  - existing: `sympy/core/tests/test_subs.py::test_issue_15234`
  - existing: `sympy/core/tests/test_subs.py::test_issue_11746`
  - existing: `sympy/core/tests/test_subs.py::test_issue_17823`
  - existing: `sympy/core/tests/test_subs.py::test_issue_19326`
  - existing: `sympy/core/tests/test_subs.py::test_issue_19558`
- `regression_piecewise`: `python -m pytest sympy/functions/elementary/tests/test_piecewise.py::test_issue_14787 sympy/functions/elementary/tests/test_piecewise.py::test_issue_8458 sympy/functions/elementary/tests/test_piecewise.py::test_issue_16417 sympy/functions/elementary/tests/test_piecewise.py::test_eval_rewrite_as_KroneckerDelta sympy/functions/elementary/tests/test_piecewise.py::test_identical_conds_issue sympy/functions/elementary/tests/test_piecewise.py::test_issue_7370 sympy/functions/elementary/tests/test_piecewise.py::test_issue_16715 sympy/functions/elementary/tests/test_piecewise.py::test_issue_20360`, at least 8 tests, environment `sympy_py39`; required new tests: 0, required existing tests: 8
  - existing: `sympy/functions/elementary/tests/test_piecewise.py::test_issue_14787`
  - existing: `sympy/functions/elementary/tests/test_piecewise.py::test_issue_8458`
  - existing: `sympy/functions/elementary/tests/test_piecewise.py::test_issue_16417`
  - existing: `sympy/functions/elementary/tests/test_piecewise.py::test_eval_rewrite_as_KroneckerDelta`
  - existing: `sympy/functions/elementary/tests/test_piecewise.py::test_identical_conds_issue`
  - existing: `sympy/functions/elementary/tests/test_piecewise.py::test_issue_7370`
  - existing: `sympy/functions/elementary/tests/test_piecewise.py::test_issue_16715`
  - existing: `sympy/functions/elementary/tests/test_piecewise.py::test_issue_20360`

Budget profile for the agent: `large_usd`

Tools added for the agent: `edit_file`, `search_files`

## New tests

### `sympy/core/tests/test_issue_piecewise_subs.py`

On the code as it is now, validation `target`: `test_subs_int_to_float_with_piecewise_hyperbolic_argument` FAIL

Why they fail now (test output; check that this is the behaviour to fix):

```text
sympy/core/function.py:473: in __new__
    result = super().__new__(cls, *args, **options)
sympy/core/cache.py:72: in wrapper
    retval = cfunc(*args, **kwargs)
sympy/core/function.py:285: in __new__
    evaluated = cls.eval(*args)
sympy/core/mod.py:169: in eval
    G = gcd(p, q)
sympy/polys/polytools.py:5306: in gcd
    (F, G), opt = parallel_poly_from_expr((f, g), *gens, **args)
sympy/polys/polytools.py:4340: in parallel_poly_from_expr
    return _parallel_poly_from_expr(exprs, opt)
sympy/polys/polytools.py:4399: in _parallel_poly_from_expr
E   sympy.polys.polyerrors.PolynomialError: Piecewise generators do not make sense
sympy/core/tests/test_issue_piecewise_subs.py:21: in test_subs_int_to_float_with_piecewise_hyperbolic_argument
    _subs_without_error(exp(func(pw)))
sympy/core/tests/test_issue_piecewise_subs.py:10: in _subs_without_error
E   AssertionError: subs({1: 1.0}) raised PolynomialError: Piecewise generators do not make sense
========================= 1 failed, 1 warning in Xs =========================
```

The file:

```python
from sympy import cosh, exp, log, Piecewise, sin, sinh, symbols, tanh
from sympy.core.basic import Basic
from sympy.core.cache import clear_cache


def _subs_without_error(expr):
    try:
        result = expr.subs({1: 1.0})
    except Exception as exc:
        raise AssertionError(
            "subs({1: 1.0}) raised %s: %s" % (type(exc).__name__, exc)
        ) from exc
    assert isinstance(result, Basic)


def test_subs_int_to_float_with_piecewise_hyperbolic_argument():
    x, y, z = symbols('x y z', real=True)
    pw = Piecewise((x, y > x), (y, True)) / z
    for func in (sinh, cosh, tanh, sin, log):
        clear_cache()
        _subs_without_error(exp(func(pw)))

```

## Not verified automatically

- The issue reports the error for cosh/tanh and other unary functions too; the new test only checks that subs does not raise, not that every such variant is fixed by the change.
- The issue also reports that the error disappears on a second call without clearing the cache; that caching behaviour is not asserted.
- The exact returned expression of subs({1: 1.0}) is not asserted (only that no exception is raised).

## Cost

Drafter: $0.0720, 24 model calls, 3 submits, 23 steps (ended: submitted).

## Approve

`approve_draft.py` checks the draft again under your task name, issue, cap and attempt limit, and publishes it only with `--approve`. Without a reference patch the task is recorded as `feasibility: unproven`; with one (`--reference-patch <patch>` instead of `--no-reference`) it is proven before the agent runs.

```bash
python scripts/approve_draft.py --draft runs/j20261027_185915_f13b-d4/draft.json --task <name> --issue-file runs/j20261027_185915_f13b-d4/issue.txt --max-usd <cap> --max-iterations <n> --no-reference
```
