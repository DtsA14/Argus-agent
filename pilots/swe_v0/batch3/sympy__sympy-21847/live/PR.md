# task: itermonomials returns incorrect monomials when using min_degrees argument

## Issue

````
itermonomials returns incorrect monomials when using min_degrees argument
`itermonomials` returns incorrect monomials when using optional `min_degrees` argument

For example, the following code introduces three symbolic variables and generates monomials with max and min degree of 3:


```
import sympy as sp
from sympy.polys.orderings import monomial_key

x1, x2, x3 = sp.symbols('x1, x2, x3')
states = [x1, x2, x3]
max_degrees = 3
min_degrees = 3
monomials = sorted(sp.itermonomials(states, max_degrees, min_degrees=min_degrees), 
                   key=monomial_key('grlex', states))
print(monomials)
```
The code returns `[x3**3, x2**3, x1**3]`, when it _should_ also return monomials such as `x1*x2**2, x2*x3**2, etc...` that also have total degree of 3. This behaviour is inconsistent with the documentation that states that 

> A generator of all monomials `monom` is returned, such that either `min_degree <= total_degree(monom) <= max_degree`...

The monomials are also missing when `max_degrees` is increased above `min_degrees`.
````

## What changed

- `M` `sympy/polys/monomials.py`
- `A` `sympy/polys/tests/test_itermonomials.py` (new test, approved with the task)

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

- The order in which the generator yields monomials is not specified by the documentation, so no test fixes it.
- The doctest examples in the `itermonomials` docstring are exercised by `bin/doctest`, not by pytest, so they are not part of the validations (they already show the corrected output).
- Performance of the generator for large `max_degree` (the filter change does not alter the enumeration cost) is not checked by any test.

## Agent's summary (not evidence)

```
Fixed itermonomials so the min_degrees filter uses the total degree (sum of exponents) instead of the maximum single-variable exponent, in both the commutative and noncommutative branches. All target and regression tests pass.
```

## How to apply

```sh
git checkout -b <branch> d9b18c518d64d0ebe8e35a98c2fb519938b9b151
git apply --whitespace=nowarn changes.patch
```

## Provenance

- base: `https://github.com/sympy/sympy.git` at `d9b18c518d64d0ebe8e35a98c2fb519938b9b151`
- Argus: `ed186476f66033bb479b572c56e6ba8fc5755934`
- contract: `task` sha256 `66d93d93736ea559c77d4d5a761fd93f941dadc10341775c4858e8c2f645cf95`
- models: deepseek:deepseek-flash; 8 calls, $0.009327
- run: `j20261027_151126_f6bf-a1`, 2 attempt(s); patch sha256 `f4669f22f7d02e57b4fce11eb8469f0a382491696896b9a17481b772e0e3209b`

## Outcome of the pilot

Set by the reviewer, not by Argus: **agent-completed** if the patch is applied unchanged and the independent validation and `verify.sh` pass; **human-assisted** if you change any file in it (keep that change as its own diff); **failed** otherwise. Editing this description is supervision time, not a change of status.
