# Draft review: `base` (j20261024_174350_0c81-d1)

Status: **DRAFTED** (a draft passed its check)

Written by the harness from the draft and its check. The draft itself was written by a model: read the tests. A passing baseline shows only that the new tests fail now, not that they test the right thing.

## Issue

````text
Contains.as_set returns Contains
```py
>>> Contains(x, Reals).as_set()
Contains(x, Reals)
```

This is wrong because Contains is not a set (it's a boolean). It results in failures in other places because it doesn't have as_relational (since it isn't a set). For instance, from https://github.com/sympy/sympy/pull/14965#discussion_r205281989

```pytb
>>> Piecewise((6, Contains(x, Reals)), (7, True))
Traceback (most recent call last):
  File "<stdin>", line 1, in <module>
  File "./sympy/functions/elementary/piecewise.py", line 136, in __new__
    r = cls.eval(*newargs)
  File "./sympy/functions/elementary/piecewise.py", line 185, in eval
    c = c.as_set().as_relational(x)
AttributeError: 'Contains' object has no attribute 'as_relational'
```
````

## Plan

Files: `sympy/sets/contains.py`

Steps:
- Replace the `raise NotImplementedError()` body of `Contains.as_set` with `return self.args[1]`, so `Contains(x, S).as_set()` returns the set `S` (a Set) instead of a Boolean or an exception.
- Add a short docstring/doctest to `Contains.as_set` showing `Contains(x, S.Reals).as_set() == S.Reals`, matching the existing docstring style of the other `as_set` methods.
- Leave the rest of the class (eval, binary_symbols) untouched so that `Contains(x, S)` keeps evaluating to True/False when membership is decidable.

Risks:
- Returning `self.args[1]` ignores the case where the element itself occurs in the set (e.g. `Contains(x, FiniteSet(x))`), which yields a set still containing `x`.
- Code that relied on `NotImplementedError` from `Contains.as_set` (e.g. the `try/except NotImplementedError` in `Piecewise._eval_rewrite_as_ITE`, or `Piecewise.as_expr_set_pairs`) will now follow a different path and may produce different output for conditions containing `Contains`.
- Boolean expressions mixing `Contains` with relationals (`And(Contains(x, Reals), x > 0).as_set()`) now produce intersections/unions with the returned set, which can change results elsewhere.

## Scope

Writable: `sympy/sets/contains.py`

Protected: `**/tests/**`, `sympy/sets/tests/test_contains.py`, `sympy/sets/tests/test_contains_as_set.py`, `conftest.py`, `pytest.ini`, `sympy/conftest.py`

No scope warnings.

## Validations

- `target`: `python -m pytest sympy/sets/tests/test_contains_as_set.py`, at least 3 tests, environment `sympy`; required new tests: 3, required existing tests: 0
  - new: `sympy/sets/tests/test_contains_as_set.py::test_contains_as_set_returns_the_set`
  - new: `sympy/sets/tests/test_contains_as_set.py::test_contains_as_set_finiteset`
  - new: `sympy/sets/tests/test_contains_as_set.py::test_piecewise_with_contains_condition`
- `changed`: `python -m pytest sympy/sets/tests/test_contains.py`, at least 6 tests, environment `sympy`; required new tests: 0, required existing tests: 1
  - existing: `sympy/sets/tests/test_contains.py::test_as_set`
- `regression`: `python -m pytest sympy/functions/elementary/tests/test_piecewise.py sympy/sets/tests/test_conditionset.py`, at least 20 tests, environment `sympy`; required new tests: 0, required existing tests: 0

Budget profile for the agent: `large_usd`

Tools added for the agent: none (it rewrites whole files with WriteFile)

## New tests

### `sympy/sets/tests/test_contains_as_set.py`

On the code as it is now, validation `target`: `test_contains_as_set_returns_the_set` FAIL, `test_contains_as_set_finiteset` FAIL, `test_piecewise_with_contains_condition` FAIL

Why they fail now (test output; check that this is the behaviour to fix):

```text
sympy/sets/tests/test_contains_as_set.py:24: in test_contains_as_set_returns_the_set
E   assert False
E    +  where False = isinstance(None, Set)
sympy/sets/tests/test_contains_as_set.py:31: in test_contains_as_set_finiteset
E   assert None == {y}
E    +  where None = _as_set(Contains(x, {y}))
E    +    where Contains(x, {y}) = Contains(x, {y})
E    +      where {y} = FiniteSet(y)
E    +  and   {y} = FiniteSet(y)
sympy/sets/tests/test_contains_as_set.py:39: in test_piecewise_with_contains_condition
E   assert None == Reals
E    +  where None = _as_set(Contains(x, Reals))
E    +    where Contains(x, Reals) = (6, Contains(x, Reals)).cond
E    +  and   Reals = S.Reals
============================== 3 failed in Xs ===============================
```

The file:

```python
"""Tests for ``Contains.as_set``.

``Contains`` is a Boolean function: ``Contains(x, S)`` is a truth value, not a
set, so its ``as_set`` method must return the *set* described by the
condition (the set the element has to belong to).  It must never return a
``Contains`` object, because code that consumes ``as_set`` output (for
example :meth:`Piecewise.as_expr_set_pairs`) expects a set.
"""

from sympy import Contains, FiniteSet, Piecewise, S, Set, Symbol


def _as_set(expr):
    """Return ``expr.as_set()``, or ``None`` when it is not implemented."""
    try:
        return expr.as_set()
    except NotImplementedError:
        return None


def test_contains_as_set_returns_the_set():
    x = Symbol('x')
    result = _as_set(Contains(x, S.Reals))
    assert isinstance(result, Set)
    assert result == S.Reals


def test_contains_as_set_finiteset():
    x = Symbol('x')
    y = Symbol('y')
    assert _as_set(Contains(x, FiniteSet(y))) == FiniteSet(y)


def test_piecewise_with_contains_condition():
    # calling as_set on the (Boolean) condition of a Piecewise must give a
    # set, otherwise as_expr_set_pairs cannot compute the intervals
    x = Symbol('x')
    p = Piecewise((6, Contains(x, S.Reals)), (7, True))
    assert _as_set(p.args[0].cond) == S.Reals
    try:
        pairs = p.as_expr_set_pairs()
    except NotImplementedError:
        pairs = None
    assert pairs == [(6, S.Reals)]

```

## Existing tests changed

The draft changes 1 existing test file(s). The harness checked that no old test is lost unless listed in removed, that no test function changes unless it is required or listed in modified, and that no test of these files is skipped or xfail unless it was before. It cannot tell whether a test got weaker: read the diff.

No warnings (K3).

### `sympy/sets/tests/test_contains.py`


Diff from the intake version:

```diff
--- a/sympy/sets/tests/test_contains.py
+++ b/sympy/sets/tests/test_contains.py
@@ -42,9 +42,13 @@
     x = Symbol('x')
     y = Symbol('y')
     # Contains is a BooleanFunction whose value depends on an arg's
-    # containment in a Set -- rewriting as a Set is not yet implemented
-    raises(NotImplementedError, lambda:
-           Contains(x, FiniteSet(y)).as_set())
+    # containment in a Set; as_set must give back that Set -- never a
+    # Boolean and never an unimplemented error
+    try:
+        result = Contains(x, FiniteSet(y)).as_set()
+    except NotImplementedError:
+        result = None
+    assert result == FiniteSet(y)
 
 def test_type_error():
     # Pass in a parameter not of type "set"
```

## Not verified automatically

- The literal traceback of the issue (`AttributeError: 'Contains' object has no attribute 'as_relational'` from `Piecewise.eval`) no longer exists in this snapshot, so no test can reproduce that AttributeError; only the resulting behaviour of `Contains.as_set` and of `Piecewise.as_expr_set_pairs` is checked.
- Whether returning the underlying set is semantically right when the element itself appears in the set (e.g. `Contains(x, FiniteSet(x)).as_set()`) is not checked by any test.
- Downstream code such as `Piecewise._eval_rewrite_as_ITE`, which currently swallows `NotImplementedError` from `cond.as_set()`, is not checked for its behaviour change.

## Cost

Drafter: $0.0298, 16 model calls, 2 submits, 15 steps (ended: submitted).

## Approve

`approve_draft.py` checks the draft again under your task name, issue, cap and attempt limit, and publishes it only with `--approve`. Without a reference patch the task is recorded as `feasibility: unproven`; with one (`--reference-patch <patch>` instead of `--no-reference`) it is proven before the agent runs.

```bash
python scripts/approve_draft.py --draft runs/j20261024_174350_0c81-d1/draft.json --task <name> --issue-file runs/j20261024_174350_0c81-d1/issue.txt --max-usd <cap> --max-iterations <n> --no-reference
```
