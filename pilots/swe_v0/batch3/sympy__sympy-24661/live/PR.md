# task: The evaluate=False parameter to `parse_expr` is ignored for relationals

## Issue

````
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

## What changed

- `M` `sympy/parsing/sympy_parser.py`
- `A` `sympy/parsing/tests/test_parse_expr_relationals.py` (new test, approved with the task)

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

- Documentation of the ``evaluate`` parameter of ``parse_expr`` (docstring/online docs) is not checked by any test.
- Chained comparisons such as ``parse_expr('1 < 2 < 3', evaluate=False)`` are not specified by the issue and are not covered by a test.

## Agent's summary (not evidence)

```
Added a visit_Compare handler to EvaluateFalseTransformer in sympy/parsing/sympy_parser.py so that comparison operators are rewritten into unevaluated relational constructors (Lt, Gt, Le, Ge, Eq, Ne) with evaluate=False (chained comparisons wrapped in unevaluated And); this makes parse_expr('1 < 2', evaluate=False) return Lt(1, 2) instead of True.
```

## How to apply

```sh
git checkout -b <branch> a36caf5c74fe654cedc488e8a8a05fad388f8406
git apply --whitespace=nowarn changes.patch
```

## Provenance

- base: `https://github.com/sympy/sympy.git` at `a36caf5c74fe654cedc488e8a8a05fad388f8406`
- Argus: `ed186476f66033bb479b572c56e6ba8fc5755934`
- contract: `task` sha256 `ec36ac475963293f8c26925d7864a8c7e75770e38b25df3bfbb4520a11bb8037`
- models: deepseek:deepseek-flash; 17 calls, $0.013033
- run: `j20261027_151922_fcff-a1`, 2 attempt(s); patch sha256 `cfc7096fa93b0fdbd3d67e173d19061eb637c8c896172a2691fbcb390d6ed768`

## Outcome of the pilot

Set by the reviewer, not by Argus: **agent-completed** if the patch is applied unchanged and the independent validation and `verify.sh` pass; **human-assisted** if you change any file in it (keep that change as its own diff); **failed** otherwise. Editing this description is supervision time, not a change of status.
