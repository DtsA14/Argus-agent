# task: scripts/pilot_report.py reports success_rate as done / (runs_total - no_result):...

## Issue

```
scripts/pilot_report.py reports success_rate as done / (runs_total - no_result): a run that left no result (NO_RESULT)
is dropped from the denominator, so a run that died looks like neither a success nor a failure.

Keep success_rate exactly as it is, and add one key to the report, right after it:

  "success_rate_all": done / runs_total, rounded to 4 decimals like success_rate, or null when runs_total is 0

so the report shows both. Nothing else in the report changes. tests/test_pilot_report.py compares the whole report
with one it computes itself from the issue's formulas, so it must be updated to expect the new key with that formula.
```

## What changed

- `M` `scripts/pilot_report.py`
- `M` `tests/test_pilot_report.py` (changed test, approved with the task)
- `A` `tests/test_pilot_report_all.py` (new test, approved with the task)

## Existing tests changed by the task

Approved with the task, before the agent ran (the agent cannot change them). Their diff is in `changes.patch`: read it, a changed test can be weaker than the old one.

- `tests/test_pilot_report.py`

## Validation

Every validation was run again in the sandbox on the base commit plus `changes.patch` (see `tests.md`):

- `target`: pass
- `changed_report`: pass
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

- The null branch for runs_total == 0 cannot be reached through the command line: no run directory given is refused (exit 2, one line on stderr), so no run set makes runs_total 0 and no test can check that the new key is then null.
- The issue says nothing else in the report changes: the tests check the report's key order and the run rows, but an unrelated change to an aggregate's value is only caught where the tests happen to compare a value.

## Agent's summary (not evidence)

```
Added the success_rate_all key (done / runs_total, rounded to 4 decimals, null when runs_total is 0) immediately after success_rate in scripts/pilot_report.py, leaving success_rate and the rest of the report unchanged.
```

## How to apply

```sh
git checkout -b <branch> d9a1ef4cc6ed35514638f18df869838982501350
git apply --whitespace=nowarn changes.patch
```

## Provenance

- base: `https://github.com/DtsA14/Argus-agent.git` at `d9a1ef4cc6ed35514638f18df869838982501350`
- Argus: `d9a1ef4cc6ed35514638f18df869838982501350`
- contract: `task` sha256 `a18192a80d0c011264c068fe5787d12456dd183bf2190684461cb4ca7ae5f5c4`
- models: deepseek:deepseek-flash; 4 calls, $0.002354
- run: `j20261023_164114_cfcb-a1`, 1 attempt(s); patch sha256 `005501718d991afa6383478584a63c8d19ec6763785fbe78d44a384f74068066`

## Outcome of the pilot

Set by the reviewer, not by Argus: **agent-completed** if the patch is applied unchanged and the independent validation and `verify.sh` pass; **human-assisted** if you change any file in it (keep that change as its own diff); **failed** otherwise. Editing this description is supervision time, not a change of status.
