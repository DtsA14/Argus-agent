# task: `_check_homomorphism` is broken on PermutationGroups

## Issue

````
`_check_homomorphism` is broken on PermutationGroups
```python
In [1]: from sympy.combinatorics import *
   ...: from sympy.combinatorics.homomorphisms import homomorphism
   ...: D3 = DihedralGroup(3)
   ...: T = homomorphism(D3, D3, D3.generators, D3.generators)

ValueError: The given images do not define a homomorphism
```

The issue is in the internal `_image()` function, where it handles the case of a `PermutationGroup`:

https://github.com/sympy/sympy/blob/809c53c077485ca48a206cee78340389cb83b7f1/sympy/combinatorics/homomorphisms.py#L336-L337

When `r[i]` is an inverted generator, the `in gens` test fails.

I think the whole thing can be greatly simplified.
````

## What changed

- `M` `sympy/combinatorics/homomorphisms.py`
- `A` `sympy/combinatorics/tests/test_homomorphisms_permutation_groups.py` (new test, approved with the task)

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

- The issue also asks that the check be 'greatly simplified'; no test can measure simplicity, only that the identity map of D3 is accepted and that invalid images are still rejected (the latter is only covered by the existing test file).
- The behaviour of `_check_homomorphism` for a PermutationGroup whose presentation eliminates generators, or for groups with more than two generators, is not exercised by the new tests; only DihedralGroup(3) is used.
- The FpGroup codomain branch of the relator check (including the `make_confluent` fallback) is untouched by the new tests and remains covered only by sympy/combinatorics/tests/test_homomorphisms.py.

## Agent's summary (not evidence)

```
Simplified the internal `_image()` helper in `_check_homomorphism` to build a symbol->image map from the presentation generators (paired positionally with the group's generators), so inverted generators in relators are no longer dropped; the mirror homomorphism of DihedralGroup(3) now works.
```

## How to apply

```sh
git checkout -b <branch> 809c53c077485ca48a206cee78340389cb83b7f1
git apply --whitespace=nowarn changes.patch
```

## Provenance

- base: `https://github.com/sympy/sympy.git` at `809c53c077485ca48a206cee78340389cb83b7f1`
- Argus: `77de43b15c0c89ae93a10ff70155f805370e7eb5`
- contract: `task` sha256 `e94a5f45fee1cfd5a19d0162f5ea463e4801cf2f7346ee2a4f925f510d2f842c`
- models: deepseek:deepseek-flash; 9 calls, $0.012201
- run: `j20261024_181455_d71c-a2`, 1 attempt(s); patch sha256 `5525ad44bda3c521d9ffa4207360120a4887b35b21150dfb427d3ae3ab8ea91d`

## Outcome of the pilot

Set by the reviewer, not by Argus: **agent-completed** if the patch is applied unchanged and the independent validation and `verify.sh` pass; **human-assisted** if you change any file in it (keep that change as its own diff); **failed** otherwise. Editing this description is supervision time, not a change of status.
