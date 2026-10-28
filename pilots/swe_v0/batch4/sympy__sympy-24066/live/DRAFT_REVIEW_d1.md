# Draft review: `base` (j20261028_030554_244f-d1)

Status: **DRAFTED** (a draft passed its check)

Written by the harness from the draft and its check. The draft itself was written by a model: read the tests. A passing baseline shows only that the new tests fail now, not that they test the right thing.

## Issue

````text
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

## Plan

Files: `sympy/physics/units/unitsystem.py`

Steps:
- In the `Function` branch of `UnitSystem._collect_factor_and_dimension`, get the dimension system once and test each argument's dimension with `is_dimensionless` instead of relying on structural equality with `Dimension(1)`.
- When every argument of the function is dimensionless, return the collected factor together with `Dimension(1)` so that `exp(second/(ohm*farad))` is reported as dimensionless.
- Keep the existing handling for functions whose arguments are not dimensionless (raise `ValueError` or keep propagating the argument dimensions), so that `1 - exp(u/w)` still raises and `exp(pH)`-style calls keep their current result.
- Keep `expr.func(*(f[0] for f in fds))` as the factor so that the scaling part of the call is preserved.

Risks:
- Comparing the argument dimension with `Dimension(1)` structurally instead of using `is_dimensionless` leaves the bug (time/(capacitance*impedance) is only dimensionally dimensionless).
- Rejecting (or discarding) every argument dimension that is not structurally `Dimension(1)` would change existing behaviour such as `_collect_factor_and_dimension(exp(-log(cH)))` and break `exp(pH)` in `test_factor_and_dimension`.
- Returning `Dimension(1)` for every function call, without checking the argument, would hide real errors and break `test_check_unit_consistency`, which requires `1 - exp(u/w)` to raise `ValueError`.
- Dropping the collected factor of the arguments (returning only the dimension) would break all callers of the tuple.
- Handling only one-argument functions while accidentally changing the returned tuple length for multi-argument functions.

## Scope

Writable: `sympy/physics/units/unitsystem.py`

Protected: `sympy/physics/units/tests/**`

No scope warnings.

## Validations

- `target`: `python -m pytest sympy/physics/units/tests/test_collect_factor_and_dimension.py`, at least 3 tests, environment `sympy`; required new tests: 2, required existing tests: 0
  - new: `sympy/physics/units/tests/test_collect_factor_and_dimension.py::test_exp_of_dimensionless_expression_is_dimensionless`
  - new: `sympy/physics/units/tests/test_collect_factor_and_dimension.py::test_number_added_to_exp_of_dimensionless_expression`
- `regression`: `python -m pytest sympy/physics/units/tests/test_unitsystem.py sympy/physics/units/tests/test_quantities.py::test_check_unit_consistency sympy/physics/units/tests/test_quantities.py::test_issue_20288 sympy/physics/units/tests/test_quantities.py::test_get_dimensional_expr_with_function sympy/physics/units/tests/test_quantities.py::test_dimensional_expr_of_derivative sympy/physics/units/tests/test_quantities.py::test_issue_22164`, at least 13 tests, environment `sympy`; required new tests: 0, required existing tests: 13
  - existing: `sympy/physics/units/tests/test_unitsystem.py::test_definition`
  - existing: `sympy/physics/units/tests/test_unitsystem.py::test_str_repr`
  - existing: `sympy/physics/units/tests/test_unitsystem.py::test_convert_to`
  - existing: `sympy/physics/units/tests/test_unitsystem.py::test_extend`
  - existing: `sympy/physics/units/tests/test_unitsystem.py::test_dim`
  - existing: `sympy/physics/units/tests/test_unitsystem.py::test_is_consistent`
  - existing: `sympy/physics/units/tests/test_unitsystem.py::test_get_units_non_prefixed`
  - existing: `sympy/physics/units/tests/test_unitsystem.py::test_derived_units_must_exist_in_unit_system`
  - existing: `sympy/physics/units/tests/test_quantities.py::test_check_unit_consistency`
  - existing: `sympy/physics/units/tests/test_quantities.py::test_issue_20288`
  - existing: `sympy/physics/units/tests/test_quantities.py::test_get_dimensional_expr_with_function`
  - existing: `sympy/physics/units/tests/test_quantities.py::test_dimensional_expr_of_derivative`
  - existing: `sympy/physics/units/tests/test_quantities.py::test_issue_22164`

Budget profile for the agent: `large_usd`

Tools added for the agent: `edit_file`, `search_files`

## New tests

### `sympy/physics/units/tests/test_collect_factor_and_dimension.py`

On the code as it is now, validation `target`: `test_exp_of_dimensionless_expression_is_dimensionless` FAIL, `test_number_added_to_exp_of_dimensionless_expression` FAIL

Why they fail now (test output; check that this is the behaviour to fix):

```text
sympy/physics/units/tests/test_collect_factor_and_dimension.py:36: in test_exp_of_dimensionless_expression_is_dimensionless
E   assert Dimension(time/(capacitance*impedance)) == Dimension(1)
E    +  where Dimension(1) = Dimension(1)
sympy/physics/units/tests/test_collect_factor_and_dimension.py:42: in test_number_added_to_exp_of_dimensionless_expression
    factor, dim = SI._collect_factor_and_dimension(expr)
sympy/physics/units/unitsystem.py:179: in _collect_factor_and_dimension
E   ValueError: Dimension of "exp(second/(farad*ohm))" is Dimension(time/(capacitance*impedance)), but it should be Dimension(1)
sympy/physics/units/tests/test_collect_factor_and_dimension.py:44: in test_number_added_to_exp_of_dimensionless_expression
E   AssertionError: collecting the factor and the dimension of exp(second/(farad*ohm)) + 100 raised Dimension of "exp(second/(farad*ohm))" is Dimension(time/...
========================= 2 failed, 1 passed in Xs ==========================
```

The file:

```python
"""Tests for dimensionless function arguments in ``UnitSystem``.

``UnitSystem._collect_factor_and_dimension`` has to notice that an argument
which is dimensionless according to the dimension system -- ``second/(ohm*farad)``
has the dimension ``Dimension(time/(capacitance*impedance))``, which the SI
dimension system knows to be dimensionless -- makes a function such as ``exp``
dimensionless, instead of propagating the dimension of the argument.
"""

from sympy.functions.elementary.exponential import exp
from sympy.physics.units import farad, ohm, second
from sympy.physics.units.definitions.dimension_definitions import Dimension
from sympy.physics.units.systems.si import SI


def dimensionless_expression():
    # dimensionless for the dimension system, but not structurally Dimension(1)
    return second/(ohm*farad)


def test_expression_is_dimensionless():
    expr = dimensionless_expression()
    dim = SI._collect_factor_and_dimension(expr)[1]
    assert SI.get_dimension_system().is_dimensionless(dim)


def test_exp_of_dimensionless_expression_is_dimensionless():
    arg = dimensionless_expression()
    expr = exp(arg)
    try:
        factor, dim = SI._collect_factor_and_dimension(expr)
    except Exception as exc:
        raise AssertionError(
            "collecting the factor and the dimension of %s raised %s, but its"
            " argument is dimensionless" % (expr, exc)) from exc
    assert dim == Dimension(1)


def test_number_added_to_exp_of_dimensionless_expression():
    expr = 100 + exp(dimensionless_expression())
    try:
        factor, dim = SI._collect_factor_and_dimension(expr)
    except Exception as exc:
        raise AssertionError(
            "collecting the factor and the dimension of %s raised %s, but the"
            " argument of exp is dimensionless" % (expr, exc)) from exc
    assert dim == Dimension(1)

```

## Not verified automatically

- Whether a fix keeps the current result of `_collect_factor_and_dimension(exp(-log(cH)))`, which `test_quantities.py::test_factor_and_dimension` asserts as `(1, volume/amount_of_substance)`: a stricter fix that rejects every argument that is not dimensionless according to the dimension system makes that call raise, so that assertion is deliberately left out of the validations (either choice is accepted).
- Which exception path rejects a function of a dimensionful argument (the `Function` branch itself raising `ValueError`, or the enclosing `Add`): only the fact that `1 - exp(u/w)` and `1 + exp(second)` raise `ValueError` is checked.
- The numerical factor of `exp(<quantity>)` (the scale factors of the argument multiplied and exponentiated) is not asserted, only the returned dimension.
- Functions of more than one argument, for which the current code returns a tuple of the wrong length, are not covered.

## Cost

Drafter: $0.0526, 9 model calls, 1 submits, 8 steps (ended: submitted).

## Approve

`approve_draft.py` checks the draft again under your task name, issue, cap and attempt limit, and publishes it only with `--approve`. Without a reference patch the task is recorded as `feasibility: unproven`; with one (`--reference-patch <patch>` instead of `--no-reference`) it is proven before the agent runs.

```bash
python scripts/approve_draft.py --draft runs/j20261028_030554_244f-d1/draft.json --task <name> --issue-file runs/j20261028_030554_244f-d1/issue.txt --max-usd <cap> --max-iterations <n> --no-reference
```
