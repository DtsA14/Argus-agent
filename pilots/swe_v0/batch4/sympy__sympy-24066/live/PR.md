# task: SI._collect_factor_and_dimension() cannot properly detect that exponent is...

## Issue

````
SI._collect_factor_and_dimension() cannot properly detect that exponent is dimensionless
How to reproduce:

```python
from sympy import exp
from sympy.physics import units
from sympy.physics.units.systems.si import SI

expr = units.second / (units.ohm * units.farad)
dim = SI._collect_factor_and_dimension(expr)[1]

assert SI.get_dimension_system().is_dimensionless(dim)

buggy_expr = 100 + exp(expr)
SI._collect_factor_and_dimension(buggy_expr)

# results in ValueError: Dimension of "exp(second/(farad*ohm))" is Dimension(time/(capacitance*impedance)), but it should be Dimension(1)
```
````

## What changed

- `A` `sympy/physics/units/tests/test_collect_factor_and_dimension.py` (new test, approved with the task)
- `M` `sympy/physics/units/unitsystem.py`

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

- Whether a fix keeps the current result of `_collect_factor_and_dimension(exp(-log(cH)))`, which `test_quantities.py::test_factor_and_dimension` asserts as `(1, volume/amount_of_substance)`: a stricter fix that rejects every argument that is not dimensionless according to the dimension system makes that call raise, so that assertion is deliberately left out of the validations (either choice is accepted).
- Which exception path rejects a function of a dimensionful argument (the `Function` branch itself raising `ValueError`, or the enclosing `Add`): only the fact that `1 - exp(u/w)` and `1 + exp(second)` raise `ValueError` is checked.
- The numerical factor of `exp(<quantity>)` (the scale factors of the argument multiplied and exponentiated) is not asserted, only the returned dimension.
- Functions of more than one argument, for which the current code returns a tuple of the wrong length, are not covered.

## Agent's summary (not evidence)

```
In UnitSystem._collect_factor_and_dimension, the Function branch now asks the dimension system whether each argument's dimension is dimensionless and substitutes Dimension(1) for such arguments, so exp(second/(ohm*farad)) yields Dimension(1) and expressions like 100 + exp(second/(ohm*farad)) collect without a ValueError.
```

## How to apply

```sh
git checkout -b <branch> 514579c655bf22e2af14f0743376ae1d7befe345
git apply --whitespace=nowarn changes.patch
```

## Provenance

- base: `https://github.com/sympy/sympy.git` at `514579c655bf22e2af14f0743376ae1d7befe345`
- Argus: `e64014373f807395121a3aa46f75157fb4d91d09`
- contract: `task` sha256 `4238472ad1ccf59e16012336adb41ea29287b09b1bb2b2c381600ca10cce1f6f`
- models: deepseek:deepseek-flash; 4 calls, $0.002613
- run: `j20261028_030554_244f-a1`, 1 attempt(s); patch sha256 `4b1a83e79368af03b1b2183bf64f6791b16cd8ebf2939afcc62e797a30bdd0c4`

## Outcome of the pilot

Set by the reviewer, not by Argus: **agent-completed** if the patch is applied unchanged and the independent validation and `verify.sh` pass; **human-assisted** if you change any file in it (keep that change as its own diff); **failed** otherwise. Editing this description is supervision time, not a change of status.
