# task: Python code printer not respecting tuple with one element

## Issue

````
Python code printer not respecting tuple with one element
Hi,

Thanks for the recent updates in SymPy! I'm trying to update my code to use SymPy 1.10 but ran into an issue with the Python code printer. MWE:


```python
import inspect
from sympy import lambdify

inspect.getsource(lambdify([], tuple([1])))
```
SymPy 1.9 and under outputs:
```
'def _lambdifygenerated():\n    return (1,)\n'
```

But SymPy 1.10 gives

```
'def _lambdifygenerated():\n    return (1)\n'
```
Note the missing comma after `1` that causes an integer to be returned instead of a tuple. 

For tuples with two or more elements, the generated code is correct:
```python
inspect.getsource(lambdify([], tuple([1, 2])))
```
In SymPy  1.10 and under, outputs:

```
'def _lambdifygenerated():\n    return (1, 2)\n'
```
This result is expected.

Not sure if this is a regression. As this breaks my program which assumes the return type to always be a tuple, could you suggest a workaround from the code generation side? Thank you.
````

## What changed

- `M` `sympy/utilities/lambdify.py`
- `A` `sympy/utilities/tests/test_lambdify_tuple_one_element.py` (new test, approved with the task)

## Validation

Every validation was run again in the sandbox on the base commit plus `changes.patch` (see `tests.md`):

- `target`: pass
- `lambdify_regression`: pass
- `printing_regression`: pass

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

- Whether the fix also corrects `lambdastr`, which shares `_recursive_to_string`, is not checked: the issue only reports `lambdify`.
- The exact spacing of the generated source is only checked loosely (the presence of `(1,)`), so a differently formatted but semantically correct output is accepted.
- Printing a SymPy `Tuple` with one element through the code printers (`pycode`) already produced `(1,)` before the fix, so it is not part of the checked behaviour.

## Agent's summary (not evidence)

```
Fixed _recursive_to_string in lambdify.py so a one-element tuple gets a trailing comma, generating `return (1,)` instead of `return (1)` while leaving empty and multi-element tuples unchanged.
```

## How to apply

```sh
git checkout -b <branch> fdc707f73a65a429935c01532cd3970d3355eab6
git apply --whitespace=nowarn changes.patch
```

## Provenance

- base: `https://github.com/sympy/sympy.git` at `fdc707f73a65a429935c01532cd3970d3355eab6`
- Argus: `e64014373f807395121a3aa46f75157fb4d91d09`
- contract: `task` sha256 `f5d9c69126b4ebf7ea4e77c4534c977d5bba3748e4c8e0b696640c648062619c`
- models: deepseek:deepseek-flash; 6 calls, $0.007535
- run: `j20261028_031352_c162-a1`, 1 attempt(s); patch sha256 `86b3efb8bc4e4ef0cf0e55ac0c8d33392c4d825a9935a5d45bab284c43222195`

## Outcome of the pilot

Set by the reviewer, not by Argus: **agent-completed** if the patch is applied unchanged and the independent validation and `verify.sh` pass; **human-assisted** if you change any file in it (keep that change as its own diff); **failed** otherwise. Editing this description is supervision time, not a change of status.
