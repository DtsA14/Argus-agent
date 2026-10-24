# task: collect_factor_and_dimension does not detect equivalent dimensions in addition

## Issue

````
collect_factor_and_dimension does not detect equivalent dimensions in addition
Code to reproduce:
```python
from sympy.physics import units
from sympy.physics.units.systems.si import SI

v1 = units.Quantity('v1')
SI.set_quantity_dimension(v1, units.velocity)
SI.set_quantity_scale_factor(v1, 2 * units.meter / units.second)

a1 = units.Quantity('a1')
SI.set_quantity_dimension(a1, units.acceleration)
SI.set_quantity_scale_factor(a1, -9.8 * units.meter / units.second**2)

t1 = units.Quantity('t1')
SI.set_quantity_dimension(t1, units.time)
SI.set_quantity_scale_factor(t1, 5 * units.second)

expr1 = a1*t1 + v1
SI._collect_factor_and_dimension(expr1)
```
Results in:
```
Traceback (most recent call last):
  File "<stdin>", line 1, in <module>
  File "C:\Python\Python310\lib\site-packages\sympy\physics\units\unitsystem.py", line 179, in _collect_factor_and_dimension
    raise ValueError(
ValueError: Dimension of "v1" is Dimension(velocity), but it should be Dimension(acceleration*time)
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

- The wording and arguments of the ValueError raised for genuinely incompatible addends are not asserted by any test; only the exception type is.
- Which representative dimension is returned when the addends are equivalent but structurally different (e.g. velocity vs acceleration*time) depends on the canonical ordering of the Add arguments and is not asserted; the tests only assert dimensional equivalence with velocity.
- Docstrings and documentation examples of _collect_factor_and_dimension are not checked by any test.

## Agent's summary (not evidence)

```
In `UnitSystem._collect_factor_and_dimension`, the `Add` branch now compares addend dimensions with `self.get_dimension_system().equivalent_dims(dim, addend_dim)` instead of structural `!=`, so dimensionally equivalent (but structurally different) addends like `velocity` and `acceleration*time` are accepted, while genuinely incompatible dimensions still raise ValueError.
```

## How to apply

```sh
git checkout -b <branch> e8c22f6eac7314be8d92590bfff92ced79ee03e2
git apply --whitespace=nowarn changes.patch
```

## Provenance

- base: `https://github.com/sympy/sympy.git` at `e8c22f6eac7314be8d92590bfff92ced79ee03e2`
- Argus: `af5f43480af03d58f0b6a6d38275b81b880eaf4d`
- contract: `task` sha256 `139faa7fe61c1b4d0833abc9654364d793b30a0ed873fe2584960b349f06229f`
- models: deepseek:deepseek-flash; 8 calls, $0.002720
- run: `j20261024_174741_e451-a1`, 1 attempt(s); patch sha256 `345fdcaf47815344c2ef2cb618d5b968d8e116b8af355d75b19fdbe5e98d284a`

## Outcome of the pilot

Set by the reviewer, not by Argus: **agent-completed** if the patch is applied unchanged and the independent validation and `verify.sh` pass; **human-assisted** if you change any file in it (keep that change as its own diff); **failed** otherwise. Editing this description is supervision time, not a change of status.
