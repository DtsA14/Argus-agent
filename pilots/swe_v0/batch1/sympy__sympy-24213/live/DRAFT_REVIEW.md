# Draft review: `base` (j20261024_174741_e451-d1)

Status: **DRAFTED** (a draft passed its check)

Written by the harness from the draft and its check. The draft itself was written by a model: read the tests. A passing baseline shows only that the new tests fail now, not that they test the right thing.

## Issue

````text
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

## Plan

Files: `sympy/physics/units/unitsystem.py`

Steps:
- Read the Add branch of UnitSystem._collect_factor_and_dimension in sympy/physics/units/unitsystem.py.
- Replace the structural comparison `if dim != addend_dim` with a comparison that goes through the unit system's DimensionSystem, i.e. `if not self.get_dimension_system().equivalent_dims(dim, addend_dim)`.
- Keep raising the same ValueError (same message) when the addends really are dimensionally incompatible.
- Keep returning the factor sum together with the dimension of the first addend.

Risks:
- Comparing with `equivalent_dims` may be done without the unit system's DimensionSystem (e.g. `self.get_dimension_system()` is None for a bare UnitSystem) and crash.
- The fix might simply drop the check, so that genuinely incompatible addends (length + time, length + 1) stop raising; test_add_of_incompatible_dimensions_raises and the existing test_check_unit_consistency guard against that.
- The fix might also 'convert' the addend scale factors, changing the returned factor; the tests pin the factor to the plain sum of the addends' scale factors.
- Using is_dimensionless instead of dimensional equivalence would wrongly accept a dimensionless addend next to a dimensional one.
- Touching the Mul/Pow/Derivative branches would change unrelated behaviour covered by test_factor_and_dimension and test_dimensional_expr_of_derivative.

## Scope

Writable: `sympy/physics/units/unitsystem.py`

Protected: `sympy/physics/units/tests/test_collect_factor_and_dimension.py`, `sympy/physics/units/tests/*.py`

No scope warnings.

## Validations

- `target`: `python -m pytest sympy/physics/units/tests/test_collect_factor_and_dimension.py`, at least 3 tests, environment `sympy`; required new tests: 2, required existing tests: 0
  - new: `sympy/physics/units/tests/test_collect_factor_and_dimension.py::test_add_of_equivalent_dimensions`
  - new: `sympy/physics/units/tests/test_collect_factor_and_dimension.py::test_add_of_equivalent_dimensions_with_units`
- `regression`: `python -m pytest sympy/physics/units/tests/test_quantities.py::test_check_unit_consistency sympy/physics/units/tests/test_quantities.py::test_factor_and_dimension sympy/physics/units/tests/test_quantities.py::test_quantity_postprocessing sympy/physics/units/tests/test_quantities.py::test_dimensional_expr_of_derivative sympy/physics/units/tests/test_quantities.py::test_issue_20288 sympy/physics/units/tests/test_quantities.py::test_issue_22164 sympy/physics/units/tests/test_quantities.py::test_issue_24062 sympy/physics/units/tests/test_quantities.py::test_add_sub sympy/physics/units/tests/test_dimensions.py sympy/physics/units/tests/test_util.py sympy/physics/units/tests/test_unitsystem.py sympy/physics/units/tests/test_dimensionsystem.py sympy/physics/units/tests/test_prefixes.py`, at least 30 tests, environment `sympy`; required new tests: 0, required existing tests: 7
  - existing: `sympy/physics/units/tests/test_quantities.py::test_check_unit_consistency`
  - existing: `sympy/physics/units/tests/test_quantities.py::test_factor_and_dimension`
  - existing: `sympy/physics/units/tests/test_quantities.py::test_quantity_postprocessing`
  - existing: `sympy/physics/units/tests/test_quantities.py::test_dimensional_expr_of_derivative`
  - existing: `sympy/physics/units/tests/test_quantities.py::test_issue_20288`
  - existing: `sympy/physics/units/tests/test_unitsystem.py::test_definition`
  - existing: `sympy/physics/units/tests/test_dimensionsystem.py::test_is_consistent`

Budget profile for the agent: `large_usd`

Tools added for the agent: `edit_file`, `search_files`

## New tests

### `sympy/physics/units/tests/test_collect_factor_and_dimension.py`

On the code as it is now, validation `target`: `test_add_of_equivalent_dimensions` FAIL, `test_add_of_equivalent_dimensions_with_units` FAIL

Why they fail now (test output; check that this is the behaviour to fix):

```text
sympy/physics/units/tests/test_collect_factor_and_dimension.py:35: in test_add_of_equivalent_dimensions
E   AssertionError: ValueError('Dimension of "cfd_v1" is Dimension(velocity), but it should be Dimension(acceleration*time)')
sympy/physics/units/tests/test_collect_factor_and_dimension.py:48: in test_add_of_equivalent_dimensions_with_units
E   AssertionError: ValueError('Dimension of "cfd_v2" is Dimension(velocity), but it should be Dimension(length/time)')
========================= 2 failed, 1 passed in Xs ==========================
```

The file:

```python
"""UnitSystem._collect_factor_and_dimension must accept an addition whose
addends have dimensions that are equivalent without being structurally the
same object, e.g. ``velocity`` and ``acceleration*time``.
"""

from sympy.physics.units import (
    Dimension, acceleration, length, meter, second, time, velocity)
from sympy.physics.units.quantities import Quantity
from sympy.physics.units.systems.si import SI
from sympy.testing.pytest import raises


def _collect(expr):
    # Return the (factor, dimension) pair, or the exception that was raised
    # instead of letting it escape: the bug shows up as a spurious ValueError.
    try:
        return SI._collect_factor_and_dimension(expr)
    except ValueError as exc:
        return exc


def _quantity(name, dimension, scale_factor):
    q = Quantity(name)
    SI.set_quantity_dimension(q, dimension)
    SI.set_quantity_scale_factor(q, scale_factor)
    return q


def test_add_of_equivalent_dimensions():
    v1 = _quantity('cfd_v1', velocity, 2*meter/second)
    a1 = _quantity('cfd_a1', acceleration, -9.8*meter/second**2)
    t1 = _quantity('cfd_t1', time, 5*second)

    result = _collect(a1*t1 + v1)
    assert not isinstance(result, ValueError), result

    factor, dim = result
    assert isinstance(dim, Dimension)
    # -9.8*5 + 2
    assert abs(factor - (-47)) < 1e-10
    assert SI.get_dimension_system().equivalent_dims(dim, velocity)


def test_add_of_equivalent_dimensions_with_units():
    v2 = _quantity('cfd_v2', velocity, 3*meter/second)

    result = _collect(v2 + 5*meter/second)
    assert not isinstance(result, ValueError), result

    factor, dim = result
    assert factor == 8
    assert SI.get_dimension_system().equivalent_dims(dim, velocity)


def test_add_of_incompatible_dimensions_raises():
    u1 = _quantity('cfd_u1', length, 10*meter)
    t2 = _quantity('cfd_t2', time, 2*second)

    raises(ValueError, lambda: SI._collect_factor_and_dimension(u1 + t2))

```

## Not verified automatically

- The wording and arguments of the ValueError raised for genuinely incompatible addends are not asserted by any test; only the exception type is.
- Which representative dimension is returned when the addends are equivalent but structurally different (e.g. velocity vs acceleration*time) depends on the canonical ordering of the Add arguments and is not asserted; the tests only assert dimensional equivalence with velocity.
- Docstrings and documentation examples of _collect_factor_and_dimension are not checked by any test.

## Cost

Drafter: $0.0360, 16 model calls, 4 submits, 15 steps (ended: submitted).

## Approve

`approve_draft.py` checks the draft again under your task name, issue, cap and attempt limit, and publishes it only with `--approve`. Without a reference patch the task is recorded as `feasibility: unproven`; with one (`--reference-patch <patch>` instead of `--no-reference`) it is proven before the agent runs.

```bash
python scripts/approve_draft.py --draft runs/j20261024_174741_e451-d1/draft.json --task <name> --issue-file runs/j20261024_174741_e451-d1/issue.txt --max-usd <cap> --max-iterations <n> --no-reference
```
