# task: Latex parsing of fractions yields wrong expression due to missing brackets

## Issue

````
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

## What changed

- `A` `sympy/parsing/tests/test_latex_nested_frac.py` (new test, approved with the task)
- `M` `sympy/printing/str.py`

## Validation

Every validation was run again in the sandbox on the base commit plus `changes.patch` (see `tests.md`):

- `target`: pass
- `strprinter`: pass
- `precedence`: pass

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

- The end-to-end call parse_latex('\\frac{\\frac{a^3+b}{c}}{\\frac{1}{c^2}}') cannot be exercised in the sandbox: the antlr4 runtime is not installed, so sympy/parsing/tests/test_latex.py is skipped entirely. The tests therefore build the exact expression the latex converter builds for that input and check its printed form; the conversion step itself is not covered.
- Whether the converter could instead be changed so that the denominator never becomes a nested unevaluated Pow (an alternative fix in sympy/parsing/latex/_parse_latex_antlr.py) is not checked, and cannot be checked here.
- The internal structure of the parsed object is not checked: it already evaluates correctly (substituting a=2, b=5, c=3 gives 39); only the printed form is wrong, so only printing is tested.
- Printing of quotients whose denominator is a quotient in other shapes than the two tested is not covered.

## Agent's summary (not evidence)

```
Denominator factors in StrPrinter._print_Mul whose printed form contains a top-level division are now bracketed, so \\frac{\\frac{a^3+b}{c}}{\\frac{1}{c^2}} prints as ((a**3 + b)/c)/(1/(c**2)) and round-trips correctly.
```

## How to apply

```sh
git checkout -b <branch> b4777fdcef467b7132c055f8ac2c9a5059e6a145
git apply --whitespace=nowarn changes.patch
```

## Provenance

- base: `https://github.com/sympy/sympy.git` at `b4777fdcef467b7132c055f8ac2c9a5059e6a145`
- Argus: `ed186476f66033bb479b572c56e6ba8fc5755934`
- contract: `task` sha256 `0dcce489073c263146b6bea785f0d14d03d813a8a1f2bcdc032f85c471624943`
- models: deepseek:deepseek-flash; 16 calls, $0.023885
- run: `j20261027_151320_1514-a1`, 2 attempt(s); patch sha256 `8ad15cb2f8ba5c0c9a7799822d97e643e97297a29e1464e6131f0ec09e377241`

## Outcome of the pilot

Set by the reviewer, not by Argus: **agent-completed** if the patch is applied unchanged and the independent validation and `verify.sh` pass; **human-assisted** if you change any file in it (keep that change as its own diff); **failed** otherwise. Editing this description is supervision time, not a change of status.
