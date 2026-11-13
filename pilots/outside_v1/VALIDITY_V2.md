# Validity rule v2 (Fable's rule, 2026-11-13)

Why: batch 2 had two instances that tests could not grade. boltons#393: the maintainers' *added* test already passed on the base (the old rule counted a changed
old test as fail-to-pass). boltons#322: a feature whose API the issue names differently from the fix. `validity.py` v1 called all 17 candidates valid.

**Rule (mechanical, no model, nobody reads the fix; `pilots/outside_v1/validity.py`).**
1. The tests that count are the ones the PR **added**: ids that do not exist when the base's own test files run on the base (a third run, `base0`).
2. `valid` = at least one added test fails on the base (with the maintainers' test files overlaid) and passes on the fix, and nothing else of those files fails on the fix.
3. Group: `invalid` (not valid); `rubric_only` when **any** added fail-to-pass test fails on the base because a name is missing (`cannot import name`, `No module named`,
   `module '...' has no attribute`, `name '...' is not defined`): the feature's API is absent at the base and the issue may name it differently from the fix, so the job is graded by
   the blind rubric, not by the maintainers' tests; otherwise `tested`. One missing-name test is enough because a PR may bundle other tests. Limit: a bug whose symptom is a missing
   module attribute is moved to `rubric_only` too (conservative; we lose a hidden-test grade, never gain a wrong one).

**Calibration (known cases):** boltons#393 -> invalid; boltons#322 -> rubric_only; more-itertools#1284 and #1257 -> tested. All as expected.

**On the 17 candidates of batch 2 (`validity_v2.jsonl`; v1 said 17 valid):** 11 `tested`, 4 `rubric_only` (boltons#322, more-itertools#813, #1041, #1098), 2 `invalid`
(boltons#393, more-itertools#1214). Of the eight issues chosen for batch 2, exactly the two that could not be graded change: #393 and #322. The other six stay `tested`.

Pytest cuts the `-rA` reason to the terminal width, so the container runs with `COLUMNS=600` (found during calibration: the "module has no attribute" text was truncated).
Not a harness change: the script lives under `pilots/` (outside the pytest collection and outside every Argus guarantee).
