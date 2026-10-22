# fix_is_peak: models/pricing.py: is_peak(window, now) never matches a peak window that crosses

## Issue

```
models/pricing.py: is_peak(window, now) never matches a peak window that crosses midnight, so a provider whose peak price runs through the night would be billed at the off-peak price. A window is [start, end) in UTC hours with the end excluded, for example [1, 4] is 01:00 up to 04:00. A window with start greater than end crosses midnight: [22, 4] is 22:00 up to midnight and midnight up to 04:00 (hour >= start or hour < end). Today only start <= hour < end is checked.

Change is_peak so that: a window with start < end behaves as before; a window with start > end matches as described; start == end is an empty window that never matches (it is not "all day"); several windows match when any of them matches; weekdays_only is still judged on the UTC date of `now`, also for a window that crosses midnight (Saturday 01:00 UTC is not peak even though a window began on Friday evening); `now` in another time zone is still converted to UTC; no window (None or empty) is never peak. multiplier() and cost_usd() use is_peak, so they follow.

Change only models/pricing.py; do not change config.yaml or any other file, the tests are protected. Only the function is_peak needs to change; no other file needs to be read.
```

## What changed

- `M` `models/pricing.py`
- `A` `tests/test_peak_window.py` (new test, approved with the task)

## Validation

Every validation was run again in the sandbox on the base commit plus `changes.patch` (see `tests.md`):

- `target`: pass
- `regression`: pass

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

- that config.yaml and the other protected files were left alone: they are protected, but a reviewer must read the diff
- that the production peak windows are not affected: none crosses midnight today, so no billed amount changes; the regression nodes and the guard tests show the non-crossing cases unchanged
- readability and the exact form of the condition (the contract fixes the behaviour)

## Agent's summary (not evidence)

```
is_peak matches a window that crosses midnight
```

## How to apply

```sh
git checkout -b <branch> 983a4ee1d633b860fe873183d1669c653abcb16b
git apply --whitespace=nowarn changes.patch
```

## Provenance

- base: `https://github.com/DtsA14/Argus-agent.git` at `983a4ee1d633b860fe873183d1669c653abcb16b`
- Argus: `2853ef34d52cae0266d6eafaeeb114194f44df8d`
- contract: `fix_is_peak` sha256 `1c3a063a3ab2c08da3a64bdea2d73c45415be3d3802fa210e75e33506dd901b5`
- models: fake:scripted; 6 calls, $0.009000
- run: `rehearsal_happy`, 1 attempt(s); patch sha256 `9e1a781ddaf6ee96abd5022b8cb1dee21e43768822679115e833bd152844c50b`

## Outcome of the pilot

Set by the reviewer, not by Argus: **agent-completed** if the patch is applied unchanged and the independent validation and `verify.sh` pass; **human-assisted** if you change any file in it (keep that change as its own diff); **failed** otherwise. Editing this description is supervision time, not a change of status.
