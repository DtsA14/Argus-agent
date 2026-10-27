# Draft review: `base` (j20261027_151320_1514-d2)

Status: **DRAFTED** (a draft passed its check)

Written by the harness from the draft and its check. The draft itself was written by a model: read the tests. A passing baseline shows only that the new tests fail now, not that they test the right thing.

## Issue

````text
Latex parsing of fractions yields wrong expression due to missing brackets
Problematic latex expression: `"\\frac{\\frac{a^3+b}{c}}{\\frac{1}{c^2}}"`

is parsed to: `((a**3 + b)/c)/1/(c**2)`.

Expected is: `((a**3 + b)/c)/(1/(c**2))`. 

The missing brackets in the denominator result in a wrong expression.

## Tested on

- 1.8
- 1.6.2

## Reproduce:

```
root@d31ef1c26093:/# python3
Python 3.6.9 (default, Jan 26 2021, 15:33:00)
[GCC 8.4.0] on linux
Type "help", "copyright", "credits" or "license" for more information.
>>> from sympy.parsing.latex import parse_latex
>>> parse_latex("\\frac{\\frac{a^3+b}{c}}{\\frac{1}{c^2}}")
((a**3 + b)/c)/1/(c**2)
````

## Plan

Files: `sympy/printing/str.py`

Steps:
- Build the expression the LaTeX converter builds for \frac{\frac{a^3+b}{c}}{\frac{1}{c^2}}: Mul(Mul(Add(a**3, b), Pow(c, -1)), Pow(Pow(Pow(c, 2), -1), -1)), all unevaluated.
- Reproduce the reported output: str() of it is '((a**3 + b)/c)/1/(c**2)' because StrPrinter._print_Mul puts the denominator factor Pow(Pow(c, 2), -1) into the denominator list and prints it as '1/(c**2)' with no brackets.
- Fix _print_Mul in sympy/printing/str.py so a denominator factor that prints as a quotient (a Pow with negative exponent, such as the base of the outer Pow with exponent -1) is enclosed in brackets, giving '((a**3 + b)/c)/(1/(c**2))' and 'a/(1/b)'.
- Leave the numerator handling, the 'unevaluated Mul' branch, the associativity order and every other printed form untouched so no existing string changes.
- Run the new test file and the regression suites sympy/printing/tests/test_str.py and sympy/printing/tests/test_precedence.py, and narrow the bracketing until nothing previously printed changes.

Risks:
- Over-parenthesizing: bracketing every denominator (or swapping strict=False for strict=True everywhere) changes strings checked by sympy/printing/tests/test_str.py and sympy/printing/tests/test_latex.py.
- Double brackets, e.g. '((a**3 + b)/c)/((1/(c**2)))', which is not the expression the issue expects.
- Only patching the special 'unevaluated Mul' branch of _print_Mul while the normal branch (the one this example takes) keeps printing the denominator unbracketed.
- Bracketing the wrong side, e.g. printing 'c*(a**3 + b)/(1)' or dropping the denominator altogether by evaluating the nested Pow.
- Breaking plain quotients such as x/y, 1/x, x/(y*z) or a**-1 by adding brackets where none are wanted.

## Scope

Writable: `sympy/printing/str.py`

Protected: `sympy/printing/tests/**`, `sympy/parsing/tests/**`

No scope warnings.

## Validations

- `target`: `python -m pytest sympy/parsing/tests/test_latex_nested_frac.py`, at least 3 tests, environment `sympy_py39`; required new tests: 3, required existing tests: 0
  - new: `sympy/parsing/tests/test_latex_nested_frac.py::test_nested_frac_roundtrip`
  - new: `sympy/parsing/tests/test_latex_nested_frac.py::test_nested_frac_str_keeps_denominator_brackets`
  - new: `sympy/parsing/tests/test_latex_nested_frac.py::test_frac_with_frac_denominator_roundtrip`
- `strprinter`: `python -m pytest sympy/printing/tests/test_str.py`, at least 50 tests, environment `sympy_py39`; required new tests: 0, required existing tests: 2
  - existing: `sympy/printing/tests/test_str.py::test_Mul`
  - existing: `sympy/printing/tests/test_str.py::test_Pow`
- `precedence`: `python -m pytest sympy/printing/tests/test_precedence.py`, at least 2 tests, environment `sympy_py39`; required new tests: 0, required existing tests: 2
  - existing: `sympy/printing/tests/test_precedence.py::test_Mul`
  - existing: `sympy/printing/tests/test_precedence.py::test_Pow`

Budget profile for the agent: `large_usd`

Tools added for the agent: `edit_file`, `search_files`

## New tests

### `sympy/parsing/tests/test_latex_nested_frac.py`

On the code as it is now, validation `target`: `test_nested_frac_roundtrip` FAIL, `test_nested_frac_str_keeps_denominator_brackets` FAIL, `test_frac_with_frac_denominator_roundtrip` FAIL

Why they fail now (test output; check that this is the behaviour to fix):

```text
sympy/parsing/tests/test_latex_nested_frac.py:37: in test_nested_frac_roundtrip
E   AssertionError: assert (a**3 + b)/c**3 == c*(a**3 + b)
E    +  where (a**3 + b)/c**3 = sympify('((a**3 + b)/c)/1/(c**2)')
E    +    where '((a**3 + b)/c)/1/(c**2)' = str(((a**3 + b)/c)/1/(c**2))
sympy/parsing/tests/test_latex_nested_frac.py:41: in test_nested_frac_str_keeps_denominator_brackets
E   AssertionError: assert '((a**3 + b)/c)/1/(c**2)' == '((a**3 + b)/c)/(1/(c**2))'
E     
E     - ((a**3 + b)/c)/(1/(c**2))
E     ?                -        -
E     + ((a**3 + b)/c)/1/(c**2)
sympy/parsing/tests/test_latex_nested_frac.py:47: in test_frac_with_frac_denominator_roundtrip
E   AssertionError: assert a/b == (a / (1 / b))
E    +  where a/b = sympify('a/1/b')
E    +    where 'a/1/b' = str(a/1/b)
========================= 3 failed, 1 warning in Xs =========================
```

The file:

```python
"""Missing brackets when printing a fraction whose denominator is a fraction.

``\\frac{\\frac{a^3+b}{c}}{\\frac{1}{c^2}}`` is converted to the unevaluated
product ``((a**3 + b)/c) * (1/(c**2))**-1``.  Printing that product dropped the
brackets around the denominator and gave ``((a**3 + b)/c)/1/(c**2)``, which no
longer means what was parsed.  The LaTeX converter itself needs the antlr4
runtime, so these tests build the expression the converter builds and check
how it prints: the printed form has to read back as the parsed expression.
"""

from sympy import Add, Mul, Pow, sympify
from sympy.abc import a, b, c


def _Add(*args):
    return Add(*args, evaluate=False)


def _Mul(*args):
    return Mul(*args, evaluate=False)


def _Pow(base, exp):
    return Pow(base, exp, evaluate=False)


def _nested_frac():
    # \frac{\frac{a^3+b}{c}}{\frac{1}{c^2}}
    upper = _Mul(_Add(_Pow(a, 3), b), _Pow(c, -1))
    lower = _Pow(_Pow(c, 2), -1)  # \frac{1}{c^2}
    return _Mul(upper, _Pow(lower, -1))


def test_nested_frac_roundtrip():
    expr = _nested_frac()
    expected = (a**3 + b)/c/(1/c**2)
    assert sympify(str(expr)) == expected


def test_nested_frac_str_keeps_denominator_brackets():
    assert str(_nested_frac()) == "((a**3 + b)/c)/(1/(c**2))"


def test_frac_with_frac_denominator_roundtrip():
    # \frac{a}{\frac{1}{b}}
    expr = _Mul(a, _Pow(_Pow(b, -1), -1))
    assert sympify(str(expr)) == a/(1/b)

```

## Not verified automatically

- The end-to-end call parse_latex('\\frac{\\frac{a^3+b}{c}}{\\frac{1}{c^2}}') cannot be exercised in the sandbox: the antlr4 runtime is not installed, so sympy/parsing/tests/test_latex.py is skipped entirely. The tests therefore build the exact expression the latex converter builds for that input and check its printed form; the conversion step itself is not covered.
- Whether the converter could instead be changed so that the denominator never becomes a nested unevaluated Pow (an alternative fix in sympy/parsing/latex/_parse_latex_antlr.py) is not checked, and cannot be checked here.
- The internal structure of the parsed object is not checked: it already evaluates correctly (substituting a=2, b=5, c=3 gives 39); only the printed form is wrong, so only printing is tested.
- Printing of quotients whose denominator is a quotient in other shapes than the two tested is not covered.

## Cost

Drafter: $0.0401, 15 model calls, 3 submits, 14 steps (ended: submitted).

## Approve

`approve_draft.py` checks the draft again under your task name, issue, cap and attempt limit, and publishes it only with `--approve`. Without a reference patch the task is recorded as `feasibility: unproven`; with one (`--reference-patch <patch>` instead of `--no-reference`) it is proven before the agent runs.

```bash
python scripts/approve_draft.py --draft runs/j20261027_151320_1514-d2/draft.json --task <name> --issue-file runs/j20261027_151320_1514-d2/issue.txt --max-usd <cap> --max-iterations <n> --no-reference
```
