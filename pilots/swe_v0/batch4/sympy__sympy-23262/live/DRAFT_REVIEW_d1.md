# Draft review: `base` (j20261028_031352_c162-d1)

Status: **DRAFTED** (a draft passed its check)

Written by the harness from the draft and its check. The draft itself was written by a model: read the tests. A passing baseline shows only that the new tests fail now, not that they test the right thing.

## Issue

````text
Python code printer not respecting tuple with one element
Hi,

Thanks for the recent updates in SymPy! I'm trying to update my code to use SymPy 1.10 but ran into an issue with the Python code printer. MWE:


```python
import inspect
from sympy import lambdify

inspect.getsource(lambdify([], tuple([1])))
```
SymPy 1.9 and under outputs:
```
'def _lambdifygenerated():\n    return (1,)\n'
```

But SymPy 1.10 gives

```
'def _lambdifygenerated():\n    return (1)\n'
```
Note the missing comma after `1` that causes an integer to be returned instead of a tuple. 

For tuples with two or more elements, the generated code is correct:
```python
inspect.getsource(lambdify([], tuple([1, 2])))
```
In SymPy  1.10 and under, outputs:

```
'def _lambdifygenerated():\n    return (1, 2)\n'
```
This result is expected.

Not sure if this is a regression. As this breaks my program which assumes the return type to always be a tuple, could you suggest a workaround from the code generation side? Thank you.
````

## Plan

Files: `sympy/utilities/lambdify.py`

Steps:
- In `_recursive_to_string` (sympy/utilities/lambdify.py), special-case a tuple of length one so that its printed form keeps the trailing comma, i.e. `(x,)` instead of `(x)`.
- Keep the special case inside the recursive helper so nested one-element tuples also get their comma.
- Leave the empty tuple printing as `()` and leave lists and multi-element tuples printed exactly as before.
- Run the new tests and the existing lambdify test module.

Risks:
- Adding the comma unconditionally would give `(,)` for the empty tuple and break `lambdify([], ())`.
- Fixing only the top-level expression in `_EvaluatorPrinter.doprint` instead of the recursive helper would leave nested one-element tuples wrong.
- Adding a trailing comma to every tuple would needlessly change the generated source of multi-element tuples.
- Touching the list or dict branches of `_recursive_to_string` could break list/dict expressions covered by existing tests.

## Scope

Writable: `sympy/utilities/lambdify.py`

Protected: `sympy/**/tests/**`, `sympy/**/test_*.py`, `sympy/utilities/tests/test_lambdify_tuple_one_element.py`

No scope warnings.

## Validations

- `target`: `python -m pytest sympy/utilities/tests/test_lambdify_tuple_one_element.py`, at least 6 tests, environment `sympy`; required new tests: 4, required existing tests: 0
  - new: `sympy/utilities/tests/test_lambdify_tuple_one_element.py::test_single_element_tuple_constant`
  - new: `sympy/utilities/tests/test_lambdify_tuple_one_element.py::test_single_element_tuple_symbol`
  - new: `sympy/utilities/tests/test_lambdify_tuple_one_element.py::test_single_element_tuple_in_generated_source`
  - new: `sympy/utilities/tests/test_lambdify_tuple_one_element.py::test_nested_single_element_tuple`
- `lambdify_regression`: `python -m pytest sympy/utilities/tests/test_lambdify.py::test_no_args sympy/utilities/tests/test_lambdify.py::test_nested_args sympy/utilities/tests/test_lambdify.py::test_str_args sympy/utilities/tests/test_lambdify.py::test_lambdify_imps sympy/utilities/tests/test_lambdify.py::test_vector_simple sympy/utilities/tests/test_lambdify.py::test_issue_14941 sympy/utilities/tests/test_lambdify.py::test_lambdify_inspect sympy/utilities/tests/test_lambdify.py::test_issue_2790 sympy/utilities/tests/test_lambdify.py::test_matrix sympy/utilities/tests/test_lambdify.py::test_lambdify_dummy_arg sympy/utilities/tests/test_lambdify.py::test_true_false`, at least 11 tests, environment `sympy`; required new tests: 0, required existing tests: 11
  - existing: `sympy/utilities/tests/test_lambdify.py::test_no_args`
  - existing: `sympy/utilities/tests/test_lambdify.py::test_nested_args`
  - existing: `sympy/utilities/tests/test_lambdify.py::test_str_args`
  - existing: `sympy/utilities/tests/test_lambdify.py::test_lambdify_imps`
  - existing: `sympy/utilities/tests/test_lambdify.py::test_vector_simple`
  - existing: `sympy/utilities/tests/test_lambdify.py::test_issue_14941`
  - existing: `sympy/utilities/tests/test_lambdify.py::test_lambdify_inspect`
  - existing: `sympy/utilities/tests/test_lambdify.py::test_issue_2790`
  - existing: `sympy/utilities/tests/test_lambdify.py::test_matrix`
  - existing: `sympy/utilities/tests/test_lambdify.py::test_lambdify_dummy_arg`
  - existing: `sympy/utilities/tests/test_lambdify.py::test_true_false`
- `printing_regression`: `python -m pytest sympy/printing/tests/test_pycode.py::test_PythonCodePrinter sympy/printing/tests/test_pycode.py::test_codegen_ast_nodes sympy/printing/tests/test_pycode.py::test_NumPyPrinter_print_seq`, at least 3 tests, environment `sympy`; required new tests: 0, required existing tests: 3
  - existing: `sympy/printing/tests/test_pycode.py::test_PythonCodePrinter`
  - existing: `sympy/printing/tests/test_pycode.py::test_codegen_ast_nodes`
  - existing: `sympy/printing/tests/test_pycode.py::test_NumPyPrinter_print_seq`

Budget profile for the agent: `large_usd`

Tools added for the agent: `edit_file`, `search_files`

## New tests

### `sympy/utilities/tests/test_lambdify_tuple_one_element.py`

On the code as it is now, validation `target`: `test_single_element_tuple_constant` FAIL, `test_single_element_tuple_symbol` FAIL, `test_single_element_tuple_in_generated_source` FAIL, `test_nested_single_element_tuple` FAIL

Why they fail now (test output; check that this is the behaviour to fix):

```text
sympy/utilities/tests/test_lambdify_tuple_one_element.py:18: in test_single_element_tuple_constant
E   AssertionError: lambdify returned 1, which is not a tuple
sympy/utilities/tests/test_lambdify_tuple_one_element.py:26: in test_single_element_tuple_symbol
E   AssertionError: lambdify returned 2, which is not a tuple
sympy/utilities/tests/test_lambdify_tuple_one_element.py:34: in test_single_element_tuple_in_generated_source
E   AssertionError: generated source has no one-element tuple:
E     def _lambdifygenerated():
E         return (1)
E     
sympy/utilities/tests/test_lambdify_tuple_one_element.py:41: in test_nested_single_element_tuple
E   AssertionError: lambdify returned 2 for the nested tuple
========================= 4 failed, 2 passed in Xs ==========================
```

The file:

```python
"""Tests for lambdify printing of tuples with a single element.

``lambdify([], (1,))`` must generate ``return (1,)``; the missing comma
made the generated function return the integer ``1`` instead of a tuple.
"""

import inspect

from sympy.core.symbol import Symbol
from sympy.utilities.lambdify import lambdify

x = Symbol('x')


def test_single_element_tuple_constant():
    f = lambdify([], tuple([1]))
    result = f()
    assert isinstance(result, tuple), \
        "lambdify returned {!r}, which is not a tuple".format(result)
    assert result == (1,)


def test_single_element_tuple_symbol():
    f = lambdify([x], (x,))
    result = f(2)
    assert isinstance(result, tuple), \
        "lambdify returned {!r}, which is not a tuple".format(result)
    assert result == (2,)


def test_single_element_tuple_in_generated_source():
    f = lambdify([], tuple([1]))
    source = inspect.getsource(f)
    assert "(1,)" in source, \
        "generated source has no one-element tuple:\n{}".format(source)


def test_nested_single_element_tuple():
    f = lambdify([x], ((x,), x + 1))
    result = f(2)
    assert isinstance(result[0], tuple), \
        "lambdify returned {!r} for the nested tuple".format(result[0])
    assert result == ((2,), 3)


def test_empty_tuple_is_unchanged():
    f = lambdify([], tuple())
    result = f()
    assert isinstance(result, tuple), \
        "lambdify returned {!r}, which is not a tuple".format(result)
    assert result == ()


def test_several_element_tuple_is_unchanged():
    f = lambdify([], (1, 2))
    assert f() == (1, 2)
    g = lambdify([x], (x, x + 1))
    assert g(3) == (3, 4)

```

## Not verified automatically

- Whether the fix also corrects `lambdastr`, which shares `_recursive_to_string`, is not checked: the issue only reports `lambdify`.
- The exact spacing of the generated source is only checked loosely (the presence of `(1,)`), so a differently formatted but semantically correct output is accepted.
- Printing a SymPy `Tuple` with one element through the code printers (`pycode`) already produced `(1,)` before the fix, so it is not part of the checked behaviour.

## Cost

Drafter: $0.0574, 18 model calls, 3 submits, 17 steps (ended: submitted).

## Approve

`approve_draft.py` checks the draft again under your task name, issue, cap and attempt limit, and publishes it only with `--approve`. Without a reference patch the task is recorded as `feasibility: unproven`; with one (`--reference-patch <patch>` instead of `--no-reference`) it is proven before the agent runs.

```bash
python scripts/approve_draft.py --draft runs/j20261028_031352_c162-d1/draft.json --task <name> --issue-file runs/j20261028_031352_c162-d1/issue.txt --max-usd <cap> --max-iterations <n> --no-reference
```
