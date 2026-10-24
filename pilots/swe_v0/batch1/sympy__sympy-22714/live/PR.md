# task: simpify gives `Imaginary coordinates are not permitted.` with evaluate(False)

## Issue

````
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

## What changed

- `M` `sympy/geometry/point.py`
- `A` `sympy/geometry/tests/test_point_evaluate_false.py` (new test, approved with the task)

## Validation

Every validation was run again in the sandbox on the base commit plus `changes.patch` (see `tests.md`):

- `target`: pass
- `regression`: pass

The task was approved without a reference patch (feasibility: unproven): before this run, no solution had shown that its criteria can be met, and its new tests were drafted, not proven right. Read the tests as well as the change.

## Checks on this package

- ok: `contract_frozen`
- ok: `verdict_passed`
- ok: `summary_bound`
- ok: `input_unchanged`
- ok: `base_commit`
- ok: `changes_in_scope`
- ok: `changes_match_verdict`
- ok: `patch_made`
- ok: `patch_applies`
- ok: `final_state_identical`
- ok: `revalidation_matches`
- ok: `workspace_stable`

## Not verified automatically

- Whether an imaginary coordinate is still rejected while the global evaluate flag is False (e.g. Point2D(1, I) inside `with evaluate(False)`) is not checked; the issue only asks that real coordinates be accepted, and a fix may or may not keep that guard active in that mode.
- The exact interactive session from the report (a REPL snippet) is only approximated by the sympify and constructor tests.
- Any docstring/documentation wording about constructing points under evaluate(False) is not checked.

## Agent's summary (not evidence)

```
Replaced the evaluation-dependent imaginary-coordinate guard `im(a)` in Point.__new__ with the assumption query `a.is_extended_real is False`, so Point/Point2D/Point3D (and sympify of Point2D) no longer raise 'Imaginary coordinates are not permitted.' under `with evaluate(False)` while still rejecting truly complex numeric coordinates.
```

## How to apply

```sh
git checkout -b <branch> 3ff4717b6aef6086e78f01cdfa06f64ae23aed7e
git apply --whitespace=nowarn changes.patch
```

## Provenance

- base: `https://github.com/sympy/sympy.git` at `3ff4717b6aef6086e78f01cdfa06f64ae23aed7e`
- Argus: `af5f43480af03d58f0b6a6d38275b81b880eaf4d`
- contract: `task` sha256 `31e8db40541c6c9f7b2b5ddc4badf9881319f19bd3181712f12f213d845fa052`
- models: deepseek:deepseek-flash; 4 calls, $0.007723
- run: `j20261024_174223_9b1c-a1`, 1 attempt(s); patch sha256 `5acb75cb04ebb8fb778515f84c9e2c9e0afcef7f61f4f1ff38cdd22200c7e675`

## Outcome of the pilot

Set by the reviewer, not by Argus: **agent-completed** if the patch is applied unchanged and the independent validation and `verify.sh` pass; **human-assisted** if you change any file in it (keep that change as its own diff); **failed** otherwise. Editing this description is supervision time, not a change of status.
