# Draft review: `base` (j20261027_151922_fcff-d1)

Status: **DRAFTED** (a draft passed its check)

Written by the harness from the draft and its check. The draft itself was written by a model: read the tests. A passing baseline shows only that the new tests fail now, not that they test the right thing.

## Issue

````text
The evaluate=False parameter to `parse_expr` is ignored for relationals
See also #22305 and #22098

This inequality evaluates even though `evaluate=False` is given:
```python
In [14]: parse_expr('1 < 2', evaluate=False)
Out[14]: True
```
The result that should be returned is:
```python
In [15]: Lt(1, 2, evaluate=False)
Out[15]: 1 < 2
```
````

## Plan

Files: `sympy/parsing/sympy_parser.py`

Steps:
- Add a `relational_operators` mapping in `EvaluateFalseTransformer` from `ast.Lt/Gt/LtE/GtE/Eq/NotEq` to the SymPy class names 'Lt', 'Gt', 'Le', 'Ge', 'Eq', 'Ne'.
- Add a `visit_Compare` method to `EvaluateFalseTransformer` that visits the left side and first comparator and re-emits them as a call to the mapped SymPy relational class with `evaluate=False`.
- Leave comparisons whose operator is not mapped (e.g. `is`, `in`) untouched and let non-comparison nodes fall through, so `parse_expr(..., evaluate=True)` and all other parsing paths are unchanged.
- Run the new relational tests and the existing parser tests to confirm unevaluated relationals and no regressions.

Risks:
- Rebuilding a comparison with only the first operator silently drops the rest of a chained comparison such as '1 < 2 < 3'.
- Forgetting to recurse into the operands with `self.visit`, so nested arithmetic like '2*x < 1' keeps default evaluation.
- Handling ast.Compare in the existing BinOp `operators` dict instead of a dedicated `visit_Compare`, which would never fire or would raise.
- Changing the behaviour for evaluate=True or for `Eq` built by the `convert_equals_signs` transformation, which must stay as it is.

## Scope

Writable: `sympy/parsing/sympy_parser.py`

Protected: `sympy/parsing/tests/**`, `sympy/core/relational.py`

No scope warnings.

## Validations

- `target`: `python -m pytest sympy/parsing/tests/test_parse_expr_relationals.py`, at least 8 tests, environment `sympy_py39`; required new tests: 6, required existing tests: 0
  - new: `sympy/parsing/tests/test_parse_expr_relationals.py::test_lt_with_evaluate_false`
  - new: `sympy/parsing/tests/test_parse_expr_relationals.py::test_gt_with_evaluate_false`
  - new: `sympy/parsing/tests/test_parse_expr_relationals.py::test_le_with_evaluate_false`
  - new: `sympy/parsing/tests/test_parse_expr_relationals.py::test_ge_with_evaluate_false`
  - new: `sympy/parsing/tests/test_parse_expr_relationals.py::test_eq_with_evaluate_false`
  - new: `sympy/parsing/tests/test_parse_expr_relationals.py::test_ne_with_evaluate_false`
- `regression`: `python -m pytest sympy/parsing/tests/test_sympy_parser.py`, at least 28 tests, environment `sympy_py39`; required new tests: 0, required existing tests: 28
  - existing: `sympy/parsing/tests/test_sympy_parser.py::test_sympy_parser`
  - existing: `sympy/parsing/tests/test_sympy_parser.py::test_rationalize`
  - existing: `sympy/parsing/tests/test_sympy_parser.py::test_factorial_fail`
  - existing: `sympy/parsing/tests/test_sympy_parser.py::test_repeated_fail`
  - existing: `sympy/parsing/tests/test_sympy_parser.py::test_repeated_dot_only`
  - existing: `sympy/parsing/tests/test_sympy_parser.py::test_local_dict`
  - existing: `sympy/parsing/tests/test_sympy_parser.py::test_local_dict_split_implmult`
  - existing: `sympy/parsing/tests/test_sympy_parser.py::test_local_dict_symbol_to_fcn`
  - existing: `sympy/parsing/tests/test_sympy_parser.py::test_global_dict`
  - existing: `sympy/parsing/tests/test_sympy_parser.py::test_no_globals`
  - existing: `sympy/parsing/tests/test_sympy_parser.py::test_issue_2515`
  - existing: `sympy/parsing/tests/test_sympy_parser.py::test_issue_7663`
  - existing: `sympy/parsing/tests/test_sympy_parser.py::test_recursive_evaluate_false_10560`
  - existing: `sympy/parsing/tests/test_sympy_parser.py::test_function_evaluate_false`
  - existing: `sympy/parsing/tests/test_sympy_parser.py::test_issue_10773`
  - existing: `sympy/parsing/tests/test_sympy_parser.py::test_split_symbols`
  - existing: `sympy/parsing/tests/test_sympy_parser.py::test_split_symbols_function`
  - existing: `sympy/parsing/tests/test_sympy_parser.py::test_functional_exponent`
  - existing: `sympy/parsing/tests/test_sympy_parser.py::test_match_parentheses_implicit_multiplication`
  - existing: `sympy/parsing/tests/test_sympy_parser.py::test_convert_equals_signs`
  - existing: `sympy/parsing/tests/test_sympy_parser.py::test_parse_function_issue_3539`
  - existing: `sympy/parsing/tests/test_sympy_parser.py::test_split_symbols_numeric`
  - existing: `sympy/parsing/tests/test_sympy_parser.py::test_unicode_names`
  - existing: `sympy/parsing/tests/test_sympy_parser.py::test_python3_features`
  - existing: `sympy/parsing/tests/test_sympy_parser.py::test_issue_19501`
  - existing: `sympy/parsing/tests/test_sympy_parser.py::test_parsing_definitions`
  - existing: `sympy/parsing/tests/test_sympy_parser.py::test_builtins`
  - existing: `sympy/parsing/tests/test_sympy_parser.py::test_issue_22822`

Budget profile for the agent: `large_usd`

Tools added for the agent: `edit_file`, `search_files`

## New tests

### `sympy/parsing/tests/test_parse_expr_relationals.py`

On the code as it is now, validation `target`: `test_lt_with_evaluate_false` FAIL, `test_gt_with_evaluate_false` FAIL, `test_le_with_evaluate_false` FAIL, `test_ge_with_evaluate_false` FAIL, `test_eq_with_evaluate_false` FAIL, `test_ne_with_evaluate_false` FAIL

Why they fail now (test output; check that this is the behaviour to fix):

```text
sympy/parsing/tests/test_parse_expr_relationals.py:16: in test_lt_with_evaluate_false
E   assert False
E    +  where False = isinstance(True, Lt)
========================= 6 failed, 2 passed in Xs ==========================
```

The file:

```python
"""Tests for ``parse_expr(..., evaluate=False)`` applied to relationals.

The ``evaluate=False`` parameter of ``parse_expr`` used to be ignored for
relationals, so that e.g. ``parse_expr('1 < 2', evaluate=False)`` returned
``True`` instead of the unevaluated ``Lt(1, 2, evaluate=False)``.
"""

from sympy.core import Integer, Symbol
from sympy.core.relational import Eq, Ge, Gt, Le, Lt, Ne
from sympy.core.singleton import S
from sympy.parsing.sympy_parser import parse_expr


def test_lt_with_evaluate_false():
    expr = parse_expr('1 < 2', evaluate=False)
    assert isinstance(expr, Lt)
    assert expr.args == (Integer(1), Integer(2))
    assert str(expr) == '1 < 2'


def test_gt_with_evaluate_false():
    expr = parse_expr('1 > 2', evaluate=False)
    assert isinstance(expr, Gt)
    assert expr.args == (Integer(1), Integer(2))


def test_le_with_evaluate_false():
    expr = parse_expr('1 <= 1', evaluate=False)
    assert isinstance(expr, Le)
    assert expr.args == (Integer(1), Integer(1))


def test_ge_with_evaluate_false():
    expr = parse_expr('1 >= 1', evaluate=False)
    assert isinstance(expr, Ge)
    assert expr.args == (Integer(1), Integer(1))


def test_eq_with_evaluate_false():
    expr = parse_expr('1 == 1', evaluate=False)
    assert isinstance(expr, Eq)
    assert expr.args == (Integer(1), Integer(1))


def test_ne_with_evaluate_false():
    expr = parse_expr('1 != 2', evaluate=False)
    assert isinstance(expr, Ne)
    assert expr.args == (Integer(1), Integer(2))


def test_relational_with_symbols_with_evaluate_false():
    x = Symbol('x')
    expr = parse_expr('x < 1', evaluate=False)
    assert expr == Lt(x, Integer(1), evaluate=False)


def test_relational_evaluates_by_default():
    assert parse_expr('1 < 2') is S.true
    assert parse_expr('2 < 1') is S.false
    assert parse_expr('1 == 1') is True

```

## Not verified automatically

- Documentation of the ``evaluate`` parameter of ``parse_expr`` (docstring/online docs) is not checked by any test.
- Chained comparisons such as ``parse_expr('1 < 2 < 3', evaluate=False)`` are not specified by the issue and are not covered by a test.

## Cost

Drafter: $0.0218, 11 model calls, 2 submits, 10 steps (ended: submitted).

## Approve

`approve_draft.py` checks the draft again under your task name, issue, cap and attempt limit, and publishes it only with `--approve`. Without a reference patch the task is recorded as `feasibility: unproven`; with one (`--reference-patch <patch>` instead of `--no-reference`) it is proven before the agent runs.

```bash
python scripts/approve_draft.py --draft runs/j20261027_151922_fcff-d1/draft.json --task <name> --issue-file runs/j20261027_151922_fcff-d1/issue.txt --max-usd <cap> --max-iterations <n> --no-reference
```
