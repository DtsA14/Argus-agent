# Draft review: `base` (j20261028_030915_ef15-d2)

Status: **DRAFTED** (a draft passed its check)

Written by the harness from the draft and its check. The draft itself was written by a model: read the tests. A passing baseline shows only that the new tests fail now, not that they test the right thing.

## Issue

```text
Argument invariance of codegen.ast String
Currently, the `codegen.ast` `String` class does not support argument invariance like:
`expr.func(*expr.args) == expr`, but instead uses the invariance `expr.func(**expr.kwargs()) == expr`.
The former should hold for any `Basic` subclass, which `String` is.
```

## Plan

Files: `sympy/codegen/ast.py`

Steps:
- In `sympy/codegen/ast.py`, remove `not_in_args = ['text']` from `String` so that `Token.__new__` no longer drops the text and `Basic.args` becomes `('foo',)` for `String('foo')`.
- Leave `_construct_text` (the `str` type check), `is_Atom = True`, `_sympystr` and `kwargs()` untouched, so `str`/`repr`/`Type(String(...))` printing, equality, hashing and `String(text='foo')` keep working.
- Rebuild-from-args must also work through `Token.__new__`'s pass-through branch, i.e. `String(*String('foo').args) == String('foo')` and the same for `QuotedString` and `Comment`.

Risks:
- `String.args` will then hold a plain Python `str`, so helpers that assume every `Basic` argument is a `Basic` (e.g. `_test_args` in `sympy/core/tests/test_args.py`, which covers `test_sympy__codegen__ast__String`, or `Basic.free_symbols` over the arguments) no longer hold for `String`; that file is protected and is deliberately not part of the validations.
- Changing `Token`/`Token.__new__` in general instead of just `String` would change `Type`, `Attribute`, `Variable`, `FunctionPrototype`, ... and break their round-tripping.
- Dropping `_construct_text`, `is_Atom` or `_sympystr` would break `String('foo') == 'foo'`-style printing (`str`, `repr`) and the `is_Atom` behaviour that other code relies on.
- Making `func` return something other than the class (e.g. a closure) would satisfy the check only vacuously; the text must stay reachable from `args`.

## Scope

Writable: `sympy/codegen/ast.py`

Protected: `sympy/**/tests/**`, `conftest.py`, `pytest.ini`

No scope warnings.

## Validations

- `target`: `python -m pytest sympy/codegen/tests/test_ast_invariance.py`, at least 4 tests, environment `sympy`; required new tests: 4, required existing tests: 0
  - new: `sympy/codegen/tests/test_ast_invariance.py::test_String_args_hold_the_text`
  - new: `sympy/codegen/tests/test_ast_invariance.py::test_String_func_of_args`
  - new: `sympy/codegen/tests/test_ast_invariance.py::test_QuotedString_func_of_args`
  - new: `sympy/codegen/tests/test_ast_invariance.py::test_Comment_func_of_args`
- `regression_ast`: `python -m pytest sympy/codegen/tests/test_ast.py`, at least 31 tests, environment `sympy`; required new tests: 0, required existing tests: 31
  - existing: `sympy/codegen/tests/test_ast.py::test_Assignment`
  - existing: `sympy/codegen/tests/test_ast.py::test_AugAssign`
  - existing: `sympy/codegen/tests/test_ast.py::test_Assignment_printing`
  - existing: `sympy/codegen/tests/test_ast.py::test_CodeBlock`
  - existing: `sympy/codegen/tests/test_ast.py::test_CodeBlock_topological_sort`
  - existing: `sympy/codegen/tests/test_ast.py::test_CodeBlock_free_symbols`
  - existing: `sympy/codegen/tests/test_ast.py::test_CodeBlock_cse`
  - existing: `sympy/codegen/tests/test_ast.py::test_CodeBlock_cse__issue_14118`
  - existing: `sympy/codegen/tests/test_ast.py::test_For`
  - existing: `sympy/codegen/tests/test_ast.py::test_none`
  - existing: `sympy/codegen/tests/test_ast.py::test_String`
  - existing: `sympy/codegen/tests/test_ast.py::test_Comment`
  - existing: `sympy/codegen/tests/test_ast.py::test_Node`
  - existing: `sympy/codegen/tests/test_ast.py::test_Type`
  - existing: `sympy/codegen/tests/test_ast.py::test_Type__from_expr`
  - existing: `sympy/codegen/tests/test_ast.py::test_Type__cast_check__integers`
  - existing: `sympy/codegen/tests/test_ast.py::test_Attribute`
  - existing: `sympy/codegen/tests/test_ast.py::test_Variable`
  - existing: `sympy/codegen/tests/test_ast.py::test_Pointer`
  - existing: `sympy/codegen/tests/test_ast.py::test_Declaration`
  - existing: `sympy/codegen/tests/test_ast.py::test_IntBaseType`
  - existing: `sympy/codegen/tests/test_ast.py::test_FloatType`
  - existing: `sympy/codegen/tests/test_ast.py::test_Type__cast_check__floating_point`
  - existing: `sympy/codegen/tests/test_ast.py::test_Type__cast_check__complex_floating_point`
  - existing: `sympy/codegen/tests/test_ast.py::test_While`
  - existing: `sympy/codegen/tests/test_ast.py::test_Scope`
  - existing: `sympy/codegen/tests/test_ast.py::test_Print`
  - existing: `sympy/codegen/tests/test_ast.py::test_FunctionPrototype_and_FunctionDefinition`
  - existing: `sympy/codegen/tests/test_ast.py::test_Return`
  - existing: `sympy/codegen/tests/test_ast.py::test_FunctionCall`
  - existing: `sympy/codegen/tests/test_ast.py::test_ast_replace`

Budget profile for the agent: `large_usd`

Tools added for the agent: `edit_file`, `search_files`

## New tests

### `sympy/codegen/tests/test_ast_invariance.py`

On the code as it is now, validation `target`: `test_String_args_hold_the_text` FAIL, `test_String_func_of_args` FAIL, `test_QuotedString_func_of_args` FAIL, `test_Comment_func_of_args` FAIL

Why they fail now (test output; check that this is the behaviour to fix):

```text
sympy/codegen/tests/test_ast_invariance.py:23: in test_String_func_of_args
E   AssertionError: String.func(*String.args) raised TypeError: No value for 'text' given and attribute has no default (args was ())
sympy/codegen/tests/test_ast_invariance.py:33: in test_QuotedString_func_of_args
    rebuilt = qs.func(*qs.args)
sympy/codegen/ast.py:237: in __new__
E   TypeError: No value for 'text' given and attribute has no default
sympy/codegen/tests/test_ast_invariance.py:35: in test_QuotedString_func_of_args
E   AssertionError: QuotedString.func(*QuotedString.args) raised TypeError: No value for 'text' given and attribute has no default (args was ())
sympy/codegen/tests/test_ast_invariance.py:47: in test_Comment_func_of_args
E   AssertionError: Comment.func(*Comment.args) raised TypeError: No value for 'text' given and attribute has no default (args was ())
============================== 4 failed in Xs ===============================
```

The file:

```python
"""Argument invariance of ``sympy.codegen.ast.String``.

``expr.func(*expr.args) == expr`` must hold for every ``Basic`` subclass, and
``String`` is one of them.  It used to be excluded from that invariance: the
text was listed in ``not_in_args``, so ``String('foo').args`` was ``()`` and
only ``expr.func(**expr.kwargs()) == expr`` worked.
"""

from sympy.codegen.ast import String, QuotedString, Comment


def test_String_args_hold_the_text():
    # the text has to be the argument of the instance, not an attribute that
    # is hidden from ``Basic.args``
    assert String('foobar').args == ('foobar',)


def test_String_func_of_args():
    st = String('foobar')
    try:
        rebuilt = st.func(*st.args)
    except Exception as exc:
        raise AssertionError(
            'String.func(*String.args) raised %s: %s (args was %r)'
            % (type(exc).__name__, exc, st.args)) from exc
    assert rebuilt == String('foobar')
    assert rebuilt == st


def test_QuotedString_func_of_args():
    qs = QuotedString('foobar')
    try:
        rebuilt = qs.func(*qs.args)
    except Exception as exc:
        raise AssertionError(
            'QuotedString.func(*QuotedString.args) raised %s: %s (args was %r)'
            % (type(exc).__name__, exc, qs.args)) from exc
    assert rebuilt == QuotedString('foobar')
    assert rebuilt == qs


def test_Comment_func_of_args():
    cm = Comment('a comment')
    try:
        rebuilt = cm.func(*cm.args)
    except Exception as exc:
        raise AssertionError(
            'Comment.func(*Comment.args) raised %s: %s (args was %r)'
            % (type(exc).__name__, exc, cm.args)) from exc
    assert rebuilt == cm
    assert isinstance(rebuilt, Comment)
    assert rebuilt.text == 'a comment'

```

## Not verified automatically

- Whether other ``Basic`` subclasses of the repository keep the ``expr.func(*expr.args) == expr`` invariance is not checked; only ``String`` and its ``QuotedString``/``Comment`` subclasses are.
- The consequences of ``text`` becoming a plain ``str`` argument for helpers that assume every ``Basic`` argument is a ``Basic`` (``_test_args`` in ``sympy/core/tests/test_args.py``, which covers ``test_sympy__codegen__ast__String`` and ``test_sympy__codegen__ast__QuotedString``, and ``Basic.free_symbols``/``Basic.atoms`` over a ``String``) are not covered by any validation here, because test files are protected and cannot be adjusted.
- Nothing checks the printed output of real code generated for e.g. C/Fortran/Python beyond what ``sympy/codegen/tests/test_ast.py`` already covers.

## Cost

Drafter: $0.0647, 18 model calls, 1 submits, 17 steps (ended: submitted).

## Approve

`approve_draft.py` checks the draft again under your task name, issue, cap and attempt limit, and publishes it only with `--approve`. Without a reference patch the task is recorded as `feasibility: unproven`; with one (`--reference-patch <patch>` instead of `--no-reference`) it is proven before the agent runs.

```bash
python scripts/approve_draft.py --draft runs/j20261028_030915_ef15-d2/draft.json --task <name> --issue-file runs/j20261028_030915_ef15-d2/issue.txt --max-usd <cap> --max-iterations <n> --no-reference
```
