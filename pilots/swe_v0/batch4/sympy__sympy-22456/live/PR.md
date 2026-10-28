# task: Argument invariance of codegen.ast String

## Issue

```
Argument invariance of codegen.ast String
Currently, the `codegen.ast` `String` class does not support argument invariance like:
`expr.func(*expr.args) == expr`, but instead uses the invariance `expr.func(**expr.kwargs()) == expr`.
The former should hold for any `Basic` subclass, which `String` is.
```

## What changed

- `M` `sympy/codegen/ast.py`
- `A` `sympy/codegen/tests/test_ast_invariance.py` (new test, approved with the task)

## Validation

Every validation was run again in the sandbox on the base commit plus `changes.patch` (see `tests.md`):

- `target`: pass
- `regression_ast`: pass

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

- Whether other ``Basic`` subclasses of the repository keep the ``expr.func(*expr.args) == expr`` invariance is not checked; only ``String`` and its ``QuotedString``/``Comment`` subclasses are.
- The consequences of ``text`` becoming a plain ``str`` argument for helpers that assume every ``Basic`` argument is a ``Basic`` (``_test_args`` in ``sympy/core/tests/test_args.py``, which covers ``test_sympy__codegen__ast__String`` and ``test_sympy__codegen__ast__QuotedString``, and ``Basic.free_symbols``/``Basic.atoms`` over a ``String``) are not covered by any validation here, because test files are protected and cannot be adjusted.
- Nothing checks the printed output of real code generated for e.g. C/Fortran/Python beyond what ``sympy/codegen/tests/test_ast.py`` already covers.

## Agent's summary (not evidence)

```
Removed `text` from `String.not_in_args` so the text is stored in `.args` (making `expr.func(*expr.args) == expr` hold for `String`, `QuotedString` and `Comment`), and added `match`/`matches`/`free_symbols` overrides to `String` because `text` is a plain Python `str` and cannot go through `Basic`'s pattern-matching/free-symbol recursion (this keeps `replace()` working).
```

## How to apply

```sh
git checkout -b <branch> a3475b3f9ac662cd425157dd3bdb93ad7111c090
git apply --whitespace=nowarn changes.patch
```

## Provenance

- base: `https://github.com/sympy/sympy.git` at `a3475b3f9ac662cd425157dd3bdb93ad7111c090`
- Argus: `e64014373f807395121a3aa46f75157fb4d91d09`
- contract: `task` sha256 `198d181227533bfdb61f047ba63d7be9be267e936d943c9c92d9228defce89c7`
- models: deepseek:deepseek-flash; 7 calls, $0.022184
- run: `j20261028_030915_ef15-a2`, 1 attempt(s); patch sha256 `360722113bd43fd4675430ec7b4ac5c20d263a27e6fc2c1639e0009e14d93ece`

## Outcome of the pilot

Set by the reviewer, not by Argus: **agent-completed** if the patch is applied unchanged and the independent validation and `verify.sh` pass; **human-assisted** if you change any file in it (keep that change as its own diff); **failed** otherwise. Editing this description is supervision time, not a change of status.
