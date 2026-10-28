# task: Unexpected `PolynomialError` when using simple `subs()` for particular...

## Issue

````
Unexpected `PolynomialError` when using simple `subs()` for particular expressions
I am seeing weird behavior with `subs` for particular expressions with hyperbolic sinusoids with piecewise arguments. When applying `subs`, I obtain an unexpected `PolynomialError`. For context, I was umbrella-applying a casting from int to float of all int atoms for a bunch of random expressions before using a tensorflow lambdify to avoid potential tensorflow type errors. You can pretend the expression below has a `+ 1` at the end, but below is the MWE that I could produce.

See the expression below, and the conditions in which the exception arises.

Sympy version: 1.8.dev

```python
from sympy import *
from sympy.core.cache import clear_cache

x, y, z = symbols('x y z')

clear_cache()
expr = exp(sinh(Piecewise((x, y > x), (y, True)) / z))
# This works fine
expr.subs({1: 1.0})

clear_cache()
x, y, z = symbols('x y z', real=True)
expr = exp(sinh(Piecewise((x, y > x), (y, True)) / z))
# This fails with "PolynomialError: Piecewise generators do not make sense"
expr.subs({1: 1.0})  # error
# Now run it again (isympy...) w/o clearing cache and everything works as expected without error
expr.subs({1: 1.0})
```

I am not really sure where the issue is, but I think it has something to do with the order of assumptions in this specific type of expression. Here is what I found-

- The error only (AFAIK) happens with `cosh` or `tanh` in place of `sinh`, otherwise it succeeds
- The error goes away if removing the division by `z`
- The error goes away if removing `exp` (but stays for most unary functions, `sin`, `log`, etc.)
- The error only happens with real symbols for `x` and `y` (`z` does not have to be real)

Not too sure how to debug this one.
````

## What changed

- `M` `sympy/core/mod.py`
- `A` `sympy/core/tests/test_issue_piecewise_subs.py` (new test, approved with the task)

## Validation

Every validation was run again in the sandbox on the base commit plus `changes.patch` (see `tests.md`):

- `target`: pass
- `regression_subs`: pass
- `regression_piecewise`: pass

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

- The issue reports the error for cosh/tanh and other unary functions too; the new test only checks that subs does not raise, not that every such variant is fixed by the change.
- The issue also reports that the error disappears on a second call without clearing the cache; that caching behaviour is not asserted.
- The exact returned expression of subs({1: 1.0}) is not asserted (only that no exception is raised).

## Agent's summary (not evidence)

```
Fixed the unexpected PolynomialError in Mod.eval by catching PolynomialError from the internal gcd extraction when operands (e.g. Piecewise expressions) cannot be handled by the polynomial machinery, treating the gcd as 1 and leaving the Mod unsimplified. This lets subs() on expressions such as exp(sinh(Piecewise(...)/z)) work for real symbols.
```

## How to apply

```sh
git checkout -b <branch> 624217179aaf8d094e6ff75b7493ad1ee47599b0
git apply --whitespace=nowarn changes.patch
```

## Provenance

- base: `https://github.com/sympy/sympy.git` at `624217179aaf8d094e6ff75b7493ad1ee47599b0`
- Argus: `58f5db4095eca0cf2264577bce165e11a2c5de7e`
- contract: `task` sha256 `971f1e819da4c2175316ff222b4d16f802b26203432ab788c6966695d4580168`
- models: deepseek:deepseek-flash; 32 calls, $0.052082
- run: `j20261027_185915_f13b-a2`, 3 attempt(s); patch sha256 `9b390b01bb3aa5bc88f447179248477533839bec1caed61ea89695cebf23ae3f`

## Outcome of the pilot

Set by the reviewer, not by Argus: **agent-completed** if the patch is applied unchanged and the independent validation and `verify.sh` pass; **human-assisted** if you change any file in it (keep that change as its own diff); **failed** otherwise. Editing this description is supervision time, not a change of status.
