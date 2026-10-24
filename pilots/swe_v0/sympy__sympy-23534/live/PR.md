# task: Using symbols to create functions doesn't work if there is an extra layer of...

## Issue

````
Using symbols to create functions doesn't work if there is an extra layer of parentheses
Sympy version == 1.10.1

Using `symbols` to create symbol-like objects like instances of `Function` as shown in the [documentation](https://docs.sympy.org/latest/modules/core.html?highlight=symbols#symbols) creates objects of class `Symbol` instead of `Function` if there is an extra layer of parentheses.

The extra layer of parentheses are necessary to deconstruct the output as separate tuples.

Running the code:
```
q, u = smp.symbols(('q:2', 'u:2'), cls=smp.Function)
print(type(q[0]))
```
#### Expected result:
<class 'sympy.core.function.UndefinedFunction'>

#### Actual result: 
<class 'sympy.core.symbol.Symbol'>
````

## What changed

- `M` `sympy/core/symbol.py`
- `A` `sympy/core/tests/test_symbols_cls.py` (new test, approved with the task)

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

- The issue shows `print(type(q[0]))` printing `<class 'sympy.core.function.UndefinedFunction'>`; the tests check the class with isinstance instead, so the exact printed text is not verified.
- Whether the `symbols` docstring is extended to mention that `cls` is honoured for iterable input is not checked by any test.

## Agent's summary (not evidence)

```
Fixed `symbols` so that the `cls` keyword is forwarded to the recursive call for each element when a sequence of names is given, so `cls=Function` (or `Dummy`, etc.) is honored for tuple/list inputs with ranges or names.
```

## How to apply

```sh
git checkout -b <branch> 832c24fec1046eaa544a4cab4c69e3af3e651759
git apply --whitespace=nowarn changes.patch
```

## Provenance

- base: `https://github.com/sympy/sympy.git` at `832c24fec1046eaa544a4cab4c69e3af3e651759`
- Argus: `9d9f97b030a397257665d485aec9885480d9005e`
- contract: `task` sha256 `3ecc74ac2cf9dacb796d5d3c53395d80dc1fa4ee5e7339f365f6e7264d5854d1`
- models: deepseek:deepseek-flash; 4 calls, $0.005374
- run: `j20261024_140954_dfb0-a1`, 1 attempt(s); patch sha256 `7a44a85f0aae405760f05096527d3acda65859c3101e03a48b9b7746b2b0d4b6`

## Outcome of the pilot

Set by the reviewer, not by Argus: **agent-completed** if the patch is applied unchanged and the independent validation and `verify.sh` pass; **human-assisted** if you change any file in it (keep that change as its own diff); **failed** otherwise. Editing this description is supervision time, not a change of status.
