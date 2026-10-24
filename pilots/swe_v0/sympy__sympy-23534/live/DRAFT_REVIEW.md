# Draft review: `base` (j20261024_140954_dfb0-d1)

Status: **DRAFTED** (a draft passed its check)

Written by the harness from the draft and its check. The draft itself was written by a model: read the tests. A passing baseline shows only that the new tests fail now, not that they test the right thing.

## Issue

````text
Using symbols to create functions doesn't work if there is an extra layer of parentheses
Sympy version == 1.10.1

Using `symbols` to create symbol-like objects like instances of `Function` as shown in the [documentation](https://docs.sympy.org/latest/modules/core.html?highlight=symbols#symbols) creates objects of class `Symbol` instead of `Function` if there is an extra layer of parentheses.

The extra layer of parentheses are necessary to deconstruct the output as separate tuples.

Running the code:
```
q, u = smp.symbols(('q:2', 'u:2'), cls=smp.Function)
print(type(q[0]))
```
#### Expected result:
<class 'sympy.core.function.UndefinedFunction'>

#### Actual result: 
<class 'sympy.core.symbol.Symbol'>
````

## Plan

Files: `sympy/core/symbol.py`

Steps:
- In `symbols`, note that `cls` is keyword-only (`def symbols(names, *, cls=Symbol, **args)`), so it is never present in `args`.
- In the non-string branch (the `else` that loops `for name in names: result.append(symbols(name, **args))`), forward the requested class explicitly, i.e. recurse with `symbols(name, cls=cls, **args)`, so the nested call no longer falls back to `Symbol`.
- Keep the returned container (`type(names)(result)`) and all range/parenthesis parsing unchanged.
- Confirm `symbols(('q:2', 'u:2'), cls=Function)` now yields a tuple of two tuples of `UndefinedFunction` classes, and that `symbols((...))` without `cls` still returns plain `Symbol`s.

Risks:
- Forwarding `cls` twice (e.g. leaving it in `args` as well) would raise `TypeError: got multiple values for keyword argument 'cls'`.
- Changing the recursion for the default case would break the many existing `symbols(('x:3', 'y:2'))`, list/dict/set input and `var` tests.
- Returning the wrong container type (list vs tuple vs set) when `cls` is forwarded.
- Applying the fix in the string branch instead of the iterable branch, which would not address the issue.

## Scope

Writable: `sympy/core/symbol.py`

Protected: `sympy/core/tests/**`, `sympy/**/tests/**`, `conftest.py`, `sympy/conftest.py`, `pytest.ini`

No scope warnings.

## Validations

- `target`: `python -m pytest sympy/core/tests/test_symbols_cls.py`, at least 4 tests, environment `sympy`; required new tests: 4, required existing tests: 0
  - new: `sympy/core/tests/test_symbols_cls.py::test_symbols_cls_function_with_tuple_of_ranges`
  - new: `sympy/core/tests/test_symbols_cls.py::test_symbols_cls_function_with_tuple_of_names`
  - new: `sympy/core/tests/test_symbols_cls.py::test_symbols_cls_dummy_with_tuple_of_ranges`
  - new: `sympy/core/tests/test_symbols_cls.py::test_symbols_cls_function_with_list_input`
- `regression`: `python -m pytest sympy/core/tests/test_symbol.py sympy/core/tests/test_var.py`, at least 16 tests, environment `sympy`; required new tests: 0, required existing tests: 3
  - existing: `sympy/core/tests/test_symbol.py::test_symbols`
  - existing: `sympy/core/tests/test_var.py::test_var`
  - existing: `sympy/core/tests/test_var.py::test_var_cls`

Budget profile for the agent: `large_usd`

Tools added for the agent: `edit_file`, `search_files`

## New tests

### `sympy/core/tests/test_symbols_cls.py`

On the code as it is now, validation `target`: `test_symbols_cls_function_with_tuple_of_ranges` FAIL, `test_symbols_cls_function_with_tuple_of_names` FAIL, `test_symbols_cls_dummy_with_tuple_of_ranges` FAIL, `test_symbols_cls_function_with_list_input` FAIL

Why they fail now (test output; check that this is the behaviour to fix):

```text
sympy/core/tests/test_symbols_cls.py:13: in test_symbols_cls_function_with_tuple_of_ranges
E   assert False
E    +  where False = isinstance(q0, FunctionClass)
============================== 4 failed in Xs ===============================
```

The file:

```python
from sympy import Function, symbols
from sympy.core.function import FunctionClass, UndefinedFunction
from sympy.core.symbol import Dummy


def test_symbols_cls_function_with_tuple_of_ranges():
    # An extra layer of parentheses (a tuple of name strings) must not
    # discard the requested ``cls``.
    q, u = symbols(('q:2', 'u:2'), cls=Function)
    assert isinstance(q, tuple) and isinstance(u, tuple)
    assert len(q) == 2 and len(u) == 2
    for s in q + u:
        assert isinstance(s, FunctionClass)
        assert isinstance(s, UndefinedFunction)
    assert [s.name for s in q] == ['q0', 'q1']
    assert [s.name for s in u] == ['u0', 'u1']


def test_symbols_cls_function_with_tuple_of_names():
    f, g = symbols(('f', 'g'), cls=Function)
    for s in (f, g):
        assert isinstance(s, FunctionClass)
        assert isinstance(s, UndefinedFunction)
    assert (f.name, g.name) == ('f', 'g')


def test_symbols_cls_dummy_with_tuple_of_ranges():
    d, = symbols(('d:2',), cls=Dummy)
    assert len(d) == 2
    for s in d:
        assert isinstance(s, Dummy)
    assert [s.name for s in d] == ['d0', 'd1']


def test_symbols_cls_function_with_list_input():
    res = symbols(['f:2', 'g'], cls=Function)
    assert isinstance(res, list)
    assert len(res) == 2
    assert [s.name for s in res[0]] == ['f0', 'f1']
    assert isinstance(res[1], UndefinedFunction)

```

## Not verified automatically

- The issue shows `print(type(q[0]))` printing `<class 'sympy.core.function.UndefinedFunction'>`; the tests check the class with isinstance instead, so the exact printed text is not verified.
- Whether the `symbols` docstring is extended to mention that `cls` is honoured for iterable input is not checked by any test.

## Cost

Drafter: $0.0149, 10 model calls, 1 submits, 9 steps (ended: submitted).

## Approve

`approve_draft.py` checks the draft again under your task name, issue, cap and attempt limit, and publishes it only with `--approve`. Without a reference patch the task is recorded as `feasibility: unproven`; with one (`--reference-patch <patch>` instead of `--no-reference`) it is proven before the agent runs.

```bash
python scripts/approve_draft.py --draft runs/j20261024_140954_dfb0-d1/draft.json --task <name> --issue-file runs/j20261024_140954_dfb0-d1/issue.txt --max-usd <cap> --max-iterations <n> --no-reference
```
