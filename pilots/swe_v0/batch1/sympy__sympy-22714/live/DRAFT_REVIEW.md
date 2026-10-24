# Draft review: `base` (j20261024_174223_9b1c-d1)

Status: **DRAFTED** (a draft passed its check)

Written by the harness from the draft and its check. The draft itself was written by a model: read the tests. A passing baseline shows only that the new tests fail now, not that they test the right thing.

## Issue

````text
simpify gives `Imaginary coordinates are not permitted.` with evaluate(False)
## Issue
`with evaluate(False)` crashes unexpectedly with `Point2D`

## Code
```python
import sympy as sp
with sp.evaluate(False):
  sp.S('Point2D(Integer(1),Integer(2))')
```

## Error
```
Traceback (most recent call last):
  File "<stdin>", line 1, in <module>
  File "/home/avinash/.local/lib/python3.8/site-packages/sympy/core/sympify.py", line 472, in sympify
    expr = parse_expr(a, local_dict=locals, transformations=transformations, evaluate=evaluate)
  File "/home/avinash/.local/lib/python3.8/site-packages/sympy/parsing/sympy_parser.py", line 1026, in parse_expr
    raise e from ValueError(f"Error from parse_expr with transformed code: {code!r}")
  File "/home/avinash/.local/lib/python3.8/site-packages/sympy/parsing/sympy_parser.py", line 1017, in parse_expr
    rv = eval_expr(code, local_dict, global_dict)
  File "/home/avinash/.local/lib/python3.8/site-packages/sympy/parsing/sympy_parser.py", line 911, in eval_expr
    expr = eval(
  File "<string>", line 1, in <module>
  File "/home/avinash/.local/lib/python3.8/site-packages/sympy/geometry/point.py", line 912, in __new__
    args = Point(*args, **kwargs)
  File "/home/avinash/.local/lib/python3.8/site-packages/sympy/geometry/point.py", line 153, in __new__
    raise ValueError('Imaginary coordinates are not permitted.')
ValueError: Imaginary coordinates are not permitted.
```

However, it works without `with evaluate(False)`. Both of following commands work
```python
sp.S('Point2D(Integer(1),Integer(2))')
sp.S('Point2D(Integer(1),Integer(2))', evaluate=False)
```
````

## Plan

Files: `sympy/geometry/point.py`

Steps:
- Reproduce mentally/with a quick run: inside `with evaluate(False)`, `Point2D(1, 2)` reaches `Point.__new__` and the guard `any(a.is_number and im(a) for a in coords)` sees the unevaluated `im(Integer(1))`, which is truthy, so it raises 'Imaginary coordinates are not permitted.'
- Change that guard in `Point.__new__` so its meaning does not depend on the global evaluate flag (e.g. compute the imaginary part with evaluation temporarily forced on, or test the coordinate's real/imaginary structure without relying on an unevaluated `im(...)`), while keeping the ValueError for genuinely imaginary coordinates with the default evaluation.
- Run the new test file and `sympy/geometry/tests/test_point.py` to confirm the fix and that `Point(3, I)`/`Point(2*I, I)`/`Point(3 + I, I)` still raise.

Risks:
- Removing or weakening the guard so that Point(3, I) no longer raises, which the existing test_point.py checks.
- Forcing evaluation with a context manager but leaking the global evaluate state (not restoring it), which would corrupt later computations.
- Special-casing only the sympify/parser path instead of fixing the constructor, leaving direct Point2D/Point/Point3D construction broken under evaluate(False).
- Changing the guard to something that also rejects valid real coordinates such as symbols or Floats.

## Scope

Writable: `sympy/geometry/point.py`

Protected: `sympy/geometry/tests/**`, `sympy/core/tests/**`, `sympy/parsing/tests/**`, `conftest.py`, `sympy/conftest.py`, `pytest.ini`, `setup.cfg`

No scope warnings.

## Validations

- `target`: `python -m pytest sympy/geometry/tests/test_point_evaluate_false.py`, at least 2 tests, environment `sympy`; required new tests: 2, required existing tests: 0
  - new: `sympy/geometry/tests/test_point_evaluate_false.py::test_sympify_point2d_under_evaluate_false`
  - new: `sympy/geometry/tests/test_point_evaluate_false.py::test_point2d_construction_under_evaluate_false`
- `regression`: `python -m pytest sympy/geometry/tests/test_point.py`, at least 12 tests, environment `sympy`; required new tests: 0, required existing tests: 12
  - existing: `sympy/geometry/tests/test_point.py::test_point`
  - existing: `sympy/geometry/tests/test_point.py::test_point3D`
  - existing: `sympy/geometry/tests/test_point.py::test_Point2D`
  - existing: `sympy/geometry/tests/test_point.py::test_issue_9214`
  - existing: `sympy/geometry/tests/test_point.py::test_issue_11617`
  - existing: `sympy/geometry/tests/test_point.py::test_transform`
  - existing: `sympy/geometry/tests/test_point.py::test_concyclic_doctest_bug`
  - existing: `sympy/geometry/tests/test_point.py::test_arguments`
  - existing: `sympy/geometry/tests/test_point.py::test_unit`
  - existing: `sympy/geometry/tests/test_point.py::test_dot`
  - existing: `sympy/geometry/tests/test_point.py::test__normalize_dimension`
  - existing: `sympy/geometry/tests/test_point.py::test_direction_cosine`

Budget profile for the agent: `large_usd`

Tools added for the agent: `edit_file`, `search_files`

## New tests

### `sympy/geometry/tests/test_point_evaluate_false.py`

On the code as it is now, validation `target`: `test_sympify_point2d_under_evaluate_false` FAIL, `test_point2d_construction_under_evaluate_false` FAIL

Why they fail now (test output; check that this is the behaviour to fix):

```text
sympy/geometry/tests/test_point_evaluate_false.py:17: in test_sympify_point2d_under_evaluate_false
E   AssertionError: Point2D construction raised ValueError('Imaginary coordinates are not permitted.')
sympy/geometry/tests/test_point_evaluate_false.py:34: in test_point2d_construction_under_evaluate_false
E   AssertionError: Point construction raised ValueError('Imaginary coordinates are not permitted.')
============================== 2 failed in Xs ===============================
```

The file:

```python
from sympy.core.numbers import Integer
from sympy.core.parameters import evaluate
from sympy.core.sympify import sympify
from sympy.geometry.point import Point, Point2D, Point3D


def test_sympify_point2d_under_evaluate_false():
    # sympify of a Point2D inside `with evaluate(False)` used to raise
    # ValueError('Imaginary coordinates are not permitted.')
    with evaluate(False):
        error = None
        point = None
        try:
            point = sympify('Point2D(Integer(1), Integer(2))')
        except ValueError as exc:
            error = exc
    assert error is None, 'Point2D construction raised %r' % (error,)
    assert isinstance(point, Point2D)
    assert point.args == (Integer(1), Integer(2))


def test_point2d_construction_under_evaluate_false():
    with evaluate(False):
        error = None
        p2d = None
        p = None
        p3d = None
        try:
            p2d = Point2D(1, 2)
            p = Point(1, 2)
            p3d = Point3D(1, 2, 3)
        except ValueError as exc:
            error = exc
    assert error is None, 'Point construction raised %r' % (error,)
    assert isinstance(p2d, Point2D)
    assert p2d.args == (Integer(1), Integer(2))
    assert isinstance(p, Point2D)
    assert p.args == (Integer(1), Integer(2))
    assert isinstance(p3d, Point3D)
    assert p3d.args == (Integer(1), Integer(2), Integer(3))

```

## Not verified automatically

- Whether an imaginary coordinate is still rejected while the global evaluate flag is False (e.g. Point2D(1, I) inside `with evaluate(False)`) is not checked; the issue only asks that real coordinates be accepted, and a fix may or may not keep that guard active in that mode.
- The exact interactive session from the report (a REPL snippet) is only approximated by the sympify and constructor tests.
- Any docstring/documentation wording about constructing points under evaluate(False) is not checked.

## Cost

Drafter: $0.0153, 8 model calls, 1 submits, 7 steps (ended: submitted).

## Approve

`approve_draft.py` checks the draft again under your task name, issue, cap and attempt limit, and publishes it only with `--approve`. Without a reference patch the task is recorded as `feasibility: unproven`; with one (`--reference-patch <patch>` instead of `--no-reference`) it is proven before the agent runs.

```bash
python scripts/approve_draft.py --draft runs/j20261024_174223_9b1c-d1/draft.json --task <name> --issue-file runs/j20261024_174223_9b1c-d1/issue.txt --max-usd <cap> --max-iterations <n> --no-reference
```
