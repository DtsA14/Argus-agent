# Draft review: `base` (j20261028_030146_c6ca-d1)

Status: **DRAFTED** (a draft passed its check)

Written by the harness from the draft and its check. The draft itself was written by a model: read the tests. A passing baseline shows only that the new tests fail now, not that they test the right thing.

## Issue

```text
Rational calc value error
python 3.11, sympy 1.11.1
when calc Rational('0.5', '100'), the value is 1/100100; but Rational(0.5, 100) the value is 1/200, this value is the true value, and the version of sympy 1.8 is normal
```

## Plan

Files: `sympy/core/numbers.py`

Steps:
- Open Rational.__new__ in sympy/core/numbers.py (starts at line 1589) and trace what happens when the first argument p is a decimal string and the second argument q is given (both as strings).
- Make the string handling used for a single string argument (the space stripping, '/' split and decimal/float parsing around lines 1594-1620) also apply when p is a string and q is supplied, so '0.5' is turned into the exact rational 5/10 before the arguments are reduced.
- Make sure a string q is also parsed exactly (not only via int(q) at line 1640) so decimal strings on either side work.
- Reduce the resulting numerator and denominator with the gcd path at line 1655 so Rational('0.5', '100') is 1/200 and not 5/1000.
- Re-run the Rational tests of sympy/core/tests/test_numbers.py to confirm Rational('3/4'), Rational('.76'), Rational('1e2/1e-2'), Rational('1 234'), Rational('1/1 234') and the TypeError cases still behave as before.

Risks:
- Parsing the decimal string through a float would lose exactness for long decimals and change Rational('1.' + '9'*20).
- Forgetting to reduce after scaling by a power of ten, so the result is an unreduced fraction such as 5/1000 instead of 1/200.
- Changing behaviour of the single-string path (spaces, '/', exponents, negative signs) that existing tests in sympy/core/tests/test_numbers.py depend on.
- Breaking construction from non-string second arguments (int, Integer, Rational, float) or the ZeroDivisionError / sign normalisation when q is negative.
- Special-casing only the exact input '0.5' instead of handling decimal strings in both arguments.

## Scope

Writable: `sympy/core/numbers.py`

Protected: `sympy/core/tests/test_numbers.py`, `sympy/core/tests/test_rational_strings.py`, `sympy/**/tests/*.py`, `sympy/testing/**`, `conftest.py`, `pytest.ini`

No scope warnings.

## Validations

- `target`: `python -m pytest sympy/core/tests/test_rational_strings.py`, at least 3 tests, environment `sympy`; required new tests: 3, required existing tests: 0
  - new: `sympy/core/tests/test_rational_strings.py::test_rational_two_decimal_string_args_value`
  - new: `sympy/core/tests/test_rational_strings.py::test_rational_two_decimal_string_args_match_numeric_args`
  - new: `sympy/core/tests/test_rational_strings.py::test_rational_two_decimal_string_args_numerator_and_denominator`
- `regression`: `python -m pytest sympy/core/tests/test_numbers.py::test_Rational_new sympy/core/tests/test_numbers.py::test_Rational_cmp sympy/core/tests/test_numbers.py::test_Rational_int`, at least 3 tests, environment `sympy`; required new tests: 0, required existing tests: 3
  - existing: `sympy/core/tests/test_numbers.py::test_Rational_new`
  - existing: `sympy/core/tests/test_numbers.py::test_Rational_cmp`
  - existing: `sympy/core/tests/test_numbers.py::test_Rational_int`

Budget profile for the agent: `large_usd`

Tools added for the agent: `edit_file`, `search_files`

## New tests

### `sympy/core/tests/test_rational_strings.py`

On the code as it is now, validation `target`: `test_rational_two_decimal_string_args_value` FAIL, `test_rational_two_decimal_string_args_match_numeric_args` FAIL, `test_rational_two_decimal_string_args_numerator_and_denominator` FAIL

Why they fail now (test output; check that this is the behaviour to fix):

```text
sympy/core/tests/test_rational_strings.py:41: in test_rational_two_decimal_string_args_value
E   AssertionError: Rational('0.5', '100') == 1/100100, expected 1/200
sympy/core/tests/test_rational_strings.py:46: in test_rational_two_decimal_string_args_match_numeric_args
E   AssertionError: Rational('0.5', '100') == 1/100100, expected the same value as Rational(0.5, 100), 1/200
sympy/core/tests/test_rational_strings.py:56: in test_rational_two_decimal_string_args_numerator_and_denominator
E   AssertionError: Rational('0.5', '100') has p, q = 1, 100100, expected 1, 200
============================== 3 failed in Xs ===============================
```

The file:

```python
"""Tests for building a Rational from two string arguments.

Rational('0.5', '100') must give the same exact value as Rational(0.5, 100),
namely 1/200.
"""

from sympy import Rational, S


def _rational_from_strings(p, q):
    """Return Rational(p, q) for string arguments, reporting errors as failures."""
    try:
        return Rational(p, q)
    except Exception as exc:
        raise AssertionError(
            "Rational(%r, %r) raised %s: %s" % (p, q, type(exc).__name__, exc)
        ) from exc


def _num_den_from_strings(p, q):
    """Return the (p, q) parts of Rational(p, q) for string arguments."""
    try:
        r = Rational(p, q)
        return (r.p, r.q)
    except Exception as exc:
        raise AssertionError(
            "Rational(%r, %r) gave no numerator/denominator (%s: %s)"
            % (p, q, type(exc).__name__, exc)
        ) from exc


def test_rational_two_decimal_string_args_value():
    r = _rational_from_strings('0.5', '100')
    try:
        equal = (r == Rational(1, 200))
    except Exception as exc:
        raise AssertionError(
            "comparing Rational('0.5', '100') with Rational(1, 200) raised %s: %s"
            % (type(exc).__name__, exc)
        ) from exc
    assert equal, "Rational('0.5', '100') == %s, expected %s" % (r, Rational(1, 200))


def test_rational_two_decimal_string_args_match_numeric_args():
    r = _rational_from_strings('0.5', '100')
    assert r == Rational(0.5, 100), (
        "Rational('0.5', '100') == %s, expected the same value as "
        "Rational(0.5, 100), %s" % (r, Rational(0.5, 100)))
    assert r == Rational(S.Half, 100), (
        "Rational('0.5', '100') == %s, expected the same value as "
        "Rational(S.Half, 100), %s" % (r, Rational(S.Half, 100)))


def test_rational_two_decimal_string_args_numerator_and_denominator():
    num, den = _num_den_from_strings('0.5', '100')
    assert (num, den) == (1, 200), (
        "Rational('0.5', '100') has p, q = %s, %s, expected 1, 200" % (num, den))

```

## Not verified automatically

- The issue's remark that sympy 1.8 behaved correctly: no test checks the behaviour of other sympy versions.
- Whether the printed representation shown by the reporter (a wrong fraction such as 1/100100) is replaced by 1/200 in every front end; the tests only compare exact values of Rational('0.5', '100').
- Decimal strings in the second argument (for example Rational('0.5', '1.5')) and in longer inputs are not required by the tests, only the reported case Rational('0.5', '100').

## Cost

Drafter: $0.0749, 23 model calls, 2 submits, 22 steps (ended: submitted).

## Approve

`approve_draft.py` checks the draft again under your task name, issue, cap and attempt limit, and publishes it only with `--approve`. Without a reference patch the task is recorded as `feasibility: unproven`; with one (`--reference-patch <patch>` instead of `--no-reference`) it is proven before the agent runs.

```bash
python scripts/approve_draft.py --draft runs/j20261028_030146_c6ca-d1/draft.json --task <name> --issue-file runs/j20261028_030146_c6ca-d1/issue.txt --max-usd <cap> --max-iterations <n> --no-reference
```
