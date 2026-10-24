# task: `PolyElement.as_expr()` not accepting symbols

## Issue

````
`PolyElement.as_expr()` not accepting symbols
The method `PolyElement.as_expr()`

https://github.com/sympy/sympy/blob/193e3825645d93c73e31cdceb6d742cc6919624d/sympy/polys/rings.py#L618-L624

is supposed to let you set the symbols you want to use, but, as it stands, either you pass the wrong number of symbols, and get an error message, or you pass the right number of symbols, and it ignores them, using `self.ring.symbols` instead:

```python
>>> from sympy import ring, ZZ, symbols
>>> R, x, y, z = ring("x,y,z", ZZ)
>>> f = 3*x**2*y - x*y*z + 7*z**3 + 1
>>> U, V, W = symbols("u,v,w")
>>> f.as_expr(U, V, W)
3*x**2*y - x*y*z + 7*z**3 + 1
```
````

## What changed

- `M` `sympy/polys/rings.py`
- `A` `sympy/polys/tests/test_rings_as_expr.py` (new test, approved with the task)

## Validation

Every validation was run again in the sandbox on the base commit plus `changes.patch` (see `tests.md`):

- `target`: pass
- `regression_rings`: pass
- `regression_fields`: pass

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

- The exact wording of the ValueError raised for a wrong number of symbols is not asserted by any test (only that ValueError is raised).
- Any docstring or example added to PolyElement.as_expr is not checked by a test.
- Whether FracElement.as_expr also honours user supplied symbols is not asserted by a new test; it delegates to PolyElement.as_expr, so it changes as a side effect only.

## Agent's summary (not evidence)

```
Fixed PolyElement.as_expr so that, when symbols are supplied, they are actually used for the conversion (raising ValueError only when the count does not match the ring's number of generators); with no arguments it still falls back to self.ring.symbols.
```

## How to apply

```sh
git checkout -b <branch> 193e3825645d93c73e31cdceb6d742cc6919624d
git apply --whitespace=nowarn changes.patch
```

## Provenance

- base: `https://github.com/sympy/sympy.git` at `193e3825645d93c73e31cdceb6d742cc6919624d`
- Argus: `af5f43480af03d58f0b6a6d38275b81b880eaf4d`
- contract: `task` sha256 `2d2491a0582ad5de3c78475c78ca912ee2e97c81a6fb14d89157f1d2452a8976`
- models: deepseek:deepseek-flash; 8 calls, $0.005913
- run: `j20261024_175159_6482-a1`, 1 attempt(s); patch sha256 `e0448833a8c475ec8facb0dad12662fce72a32fc2001a2eb44abd06f6eae1106`

## Outcome of the pilot

Set by the reviewer, not by Argus: **agent-completed** if the patch is applied unchanged and the independent validation and `verify.sh` pass; **human-assisted** if you change any file in it (keep that change as its own diff); **failed** otherwise. Editing this description is supervision time, not a change of status.
