# Draft review: `base` (j20261028_030915_ef15-d1)

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
- In ``sympy/codegen/ast.py`` remove ``String.not_in_args = ['text']`` so that ``String.text`` is passed to ``Basic.__new__`` and stored in ``Basic._args``; then ``String('foo').args == ('foo',)`` and ``String('foo').func('foo') == String('foo')``.
- Keep ``String.is_Atom = True`` (``test_ast.py::test_String`` asserts ``st.is_Atom``) and keep ``_construct_text`` raising ``TypeError`` for non-``str`` input, so ``func(*args)`` rebuilds the same instance and ``String(String('x'))`` still returns the argument unchanged.
- Give ``String`` a ``free_symbols`` property that returns ``set()``: ``Basic.free_symbols`` calls ``.free_symbols`` on every element of ``args`` and ``text`` is a plain ``str``.
- Check that nodes embedding ``String`` (``Type``, ``Attribute``, ``Print``, ``FunctionCall``, ``Variable``, ``Label``...) still rebuild and print identically: ``repr``/``sstr`` come from ``__slots__`` (``text`` was already printed), so ``repr(String('foo')) == "String('foo')"`` must not change.
- Run the validations: the new invariance tests, ``sympy/codegen/tests/test_ast.py`` and the cnodes/fnodes regression.

Risks:
- Removing ``not_in_args`` puts a plain Python ``str`` into ``args``; ``Basic.free_symbols`` calls ``arg.free_symbols`` for each argument, so ``String('foo').free_symbols`` raises ``AttributeError: 'str' object has no attribute 'free_symbols'`` unless ``String`` overrides it.
- ``Basic.atoms()`` collects nodes with ``not node.args``, so ``String`` stops counting as an atom there; that is why ``test_cnodes.py::test_sizeof`` is adjusted to ask for ``String`` atoms. Do not "fix" this by changing ``Basic.atoms`` in sympy/core/basic.py, which is not writable.
- Dropping ``is_Atom = True`` (or otherwise making ``String`` non-atomic) fails ``sympy/codegen/tests/test_ast.py::test_String``.
- Leaking the new ``args`` into printing: ``repr``/``sstr`` must stay ``String('foo')`` / ``foo`` (they read ``__slots__``, not ``args``), and ``kwargs()`` must keep returning ``{'text': ...}``.
- Storing something other than the exact ``text`` string in ``args`` (a wrapper, a sympified object) breaks ``_construct_text``'s ``TypeError`` contract, ``str(String)`` and equality with the rebuilt instance.

## Scope

Writable: `sympy/codegen/ast.py`

Protected: `sympy/codegen/tests/**`, `sympy/**/tests/**`, `sympy/**/test_*.py`, `sympy/testing/**`, `conftest.py`, `pytest.ini`

No scope warnings.

## Validations

- `target`: `python -m pytest sympy/codegen/tests/test_string_arg_invariance.py`, at least 6 tests, environment `sympy`; required new tests: 4, required existing tests: 0
  - new: `sympy/codegen/tests/test_string_arg_invariance.py::test_String_arg_invariance`
  - new: `sympy/codegen/tests/test_string_arg_invariance.py::test_String_arg_invariance_of_text`
  - new: `sympy/codegen/tests/test_string_arg_invariance.py::test_QuotedString_arg_invariance`
  - new: `sympy/codegen/tests/test_string_arg_invariance.py::test_Comment_arg_invariance`
- `ast_regression`: `python -m pytest sympy/codegen/tests/test_ast.py`, at least 30 tests, environment `sympy`; required new tests: 0, required existing tests: 7
  - existing: `sympy/codegen/tests/test_ast.py::test_String`
  - existing: `sympy/codegen/tests/test_ast.py::test_Comment`
  - existing: `sympy/codegen/tests/test_ast.py::test_Type`
  - existing: `sympy/codegen/tests/test_ast.py::test_IntBaseType`
  - existing: `sympy/codegen/tests/test_ast.py::test_Print`
  - existing: `sympy/codegen/tests/test_ast.py::test_ast_replace`
  - existing: `sympy/codegen/tests/test_ast.py::test_none`
- `codegen_regression`: `python -m pytest sympy/codegen/tests/test_cnodes.py`, at least 10 tests, environment `sympy`; required new tests: 0, required existing tests: 0

Budget profile for the agent: `large_usd`

Tools added for the agent: `edit_file`, `search_files`

## New tests

### `sympy/codegen/tests/test_string_arg_invariance.py`

On the code as it is now, validation `target`: `test_String_arg_invariance` FAIL, `test_String_arg_invariance_of_text` FAIL, `test_QuotedString_arg_invariance` FAIL, `test_Comment_arg_invariance` FAIL

Why they fail now (test output; check that this is the behaviour to fix):

```text
sympy/codegen/tests/test_string_arg_invariance.py:13: in _invariant
    return expr.func(*expr.args)
sympy/codegen/ast.py:237: in __new__
E   TypeError: No value for 'text' given and attribute has no default
sympy/codegen/tests/test_string_arg_invariance.py:36: in test_QuotedString_arg_invariance
    assert _invariant(expr) == expr
sympy/codegen/tests/test_string_arg_invariance.py:15: in _invariant
E   AssertionError: QuotedString does not support argument invariance: expr.func(*expr.args) raised TypeError: No value for 'text' given and attribute has no...
sympy/codegen/tests/test_string_arg_invariance.py:41: in test_Comment_arg_invariance
    assert _invariant(expr) == expr
sympy/codegen/tests/test_string_arg_invariance.py:15: in _invariant
E   AssertionError: Comment does not support argument invariance: expr.func(*expr.args) raised TypeError: No value for 'text' given and attribute has no default
========================= 4 failed, 2 passed in Xs ==========================
```

The file:

```python
"""Argument invariance of ``sympy.codegen.ast.String``.

``String`` is a ``Basic`` subclass, so ``expr.func(*expr.args) == expr`` has
to hold for it just as it does for e.g. ``Attribute`` or ``Variable``.
"""

from sympy.codegen.ast import Comment, QuotedString, String


def _invariant(expr):
    """Return ``expr.func(*expr.args)``, failing as an assertion on error."""
    try:
        return expr.func(*expr.args)
    except Exception as exc:
        raise AssertionError(
            "%s does not support argument invariance: "
            "expr.func(*expr.args) raised %s: %s"
            % (type(expr).__name__, type(exc).__name__, exc)) from exc


def test_String_arg_invariance():
    expr = String('foo')
    assert _invariant(expr) == expr


def test_String_arg_invariance_of_text():
    text = 'set s = "a b c";'
    expr = String(text)
    rebuilt = _invariant(expr)
    assert rebuilt == expr
    assert rebuilt.text == text


def test_QuotedString_arg_invariance():
    expr = QuotedString('bar')
    assert _invariant(expr) == expr


def test_Comment_arg_invariance():
    expr = Comment('a comment')
    assert _invariant(expr) == expr


def test_String_kwargs_constructor_still_works():
    expr = String('foo')
    assert expr.func(**expr.kwargs()) == expr
    assert str(expr) == 'foo'
    assert repr(expr) == "String('foo')"


def test_String_free_symbols():
    # ``text`` lives in ``args`` and ``Basic.free_symbols`` calls
    # ``.free_symbols`` on every argument, so it must not raise.
    try:
        free = String('foo').free_symbols
    except Exception as exc:
        raise AssertionError(
            "String.free_symbols raised %s: %s"
            % (type(exc).__name__, exc)) from exc
    assert free == set()

```

## Existing tests changed

The draft changes 1 existing test file(s). The harness checked that no old test is lost unless listed in removed, that no test function changes unless it is required or listed in modified, and that no test of these files is skipped or xfail unless it was before. It cannot tell whether a test got weaker: read the diff.

No warnings (K3).

### `sympy/codegen/tests/test_cnodes.py`

- modified `test_sizeof`: ``String`` is given arguments so that ``expr.func(*expr.args) == expr`` holds for it; the default ``atoms()`` filter (``not node.args``) therefore no longer selects ``String`` nodes. Asking for ``String`` atoms keeps the intent of the assertion and holds both before and after the change.

Diff from the intake version:

```diff
--- a/sympy/codegen/tests/test_cnodes.py
+++ b/sympy/codegen/tests/test_cnodes.py
@@ -78,7 +78,7 @@
     assert ccode(sz) == 'sizeof(%s)' % typename
     assert sz.func(*sz.args) == sz
     assert not sz.is_Atom
-    assert sz.atoms() == {String('unsigned int'), String('sizeof')}
+    assert sz.atoms(String) == {String('unsigned int'), String('sizeof')}
 
 
 def test_struct():
```

## Not verified automatically

- The general claim that ``expr.func(*expr.args) == expr`` should hold for *any* ``Basic`` subclass: only ``String`` and its subclasses (``QuotedString``, ``Comment``) are checked here; the rest of the library is out of the issue's scope.
- The doctest examples in the ``String`` docstring (``>>> f`` / ``print(repr(f))``) are not run by pytest, so a fix that leaves them stale or wrong is not caught by these validations.
- That ``sympy/core/tests/test_args.py::test_sympy__codegen__ast__String`` still passes is not required by a validation (its ``_test_args`` helper only checks recreatability, so it passes before and after, but that file is not run here).
- ``sympy/codegen/tests/test_fnodes.py`` (Fortran printing, ``fcode`` of nodes embedding ``String``) is not used as a regression because six of its tests skip in the sandbox (no Fortran compiler), and skipped tests are not allowed in a validation; ``sympy/utilities/tests/test_codegen.py`` and the code-printer suites are likewise not run, so a change in the ``ccode``/``fcode`` output of ``String`` beyond ``sympy/codegen/tests`` would only be caught by reviewers.

## Cost

Drafter: $0.0716, 17 model calls, 3 submits, 16 steps (ended: submitted).

## Approve

`approve_draft.py` checks the draft again under your task name, issue, cap and attempt limit, and publishes it only with `--approve`. Without a reference patch the task is recorded as `feasibility: unproven`; with one (`--reference-patch <patch>` instead of `--no-reference`) it is proven before the agent runs.

```bash
python scripts/approve_draft.py --draft runs/j20261028_030915_ef15-d1/draft.json --task <name> --issue-file runs/j20261028_030915_ef15-d1/issue.txt --max-usd <cap> --max-iterations <n> --no-reference
```
