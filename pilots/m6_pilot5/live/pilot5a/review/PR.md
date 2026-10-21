# fix_window_strict: models/pricing.py: is_peak(window, now) reads a peak window that it cannot inter

## Issue

```
models/pricing.py: is_peak(window, now) reads a peak window that it cannot interpret safely as "not peak", and reads a datetime without a time zone in the machine's own zone. Both can under-bill without any error. Refuse them instead: add class WindowError(ValueError) to models/pricing.py and raise it from is_peak (so also from multiplier() and cost_usd()), with a message that names the problem and shows the wrong value.

A window that is falsy (None, {}) is not an error: the provider has no peak window, the answer is False (do not check `now` then). For any other window raise WindowError when: V1 it is not a dict; V2 it has no 'utc_hours' key; V3 'utc_hours' is not a list or tuple; V4 an item is not [start, end] of two integers (bool and float are refused); V5 start is not in 0..23 or end is not in 0..24; V6 'weekdays_only' is present but is not a bool (None included). V7: `now` has no time zone (naive): raise WindowError; a time with an explicit zone is converted to UTC as before. Check every item and 'weekdays_only' before evaluating the hours, so a bad item behind an item that matches is still refused. State in the docstring that `now` must be timezone-aware.

Everything that was valid keeps its answer: 'utc_hours': [] (never peak), start == end (empty window), end 24, a window across midnight (start > end: hour >= start or hour < end), several windows, weekdays_only judged on the UTC date of `now`, unknown extra keys (ignored), and the windows of config.yaml.

Change only models/pricing.py; the tests are protected. Only is_peak (and the new class) needs to change.
```

## What changed

- `M` `models/pricing.py`
- `A` `tests/test_peak_window_strict.py` (new test, approved with the task)

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
- that harness/llm.py refuses before sending when a window is invalid: the code path was read (LLMCaller._output_cap calls multiplier before the request), it is not exercised by these tests
- the exact wording of the messages beyond naming the problem and showing the wrong value
- the behaviour of a falsy window with a naive `now` (the issue says: not checked, False)

## Agent's summary (not evidence)

```
Added WindowError(ValueError) and strict validation in is_peak (V1–V7, all items checked before evaluation, naive `now` refused), with docstring noting `now` must be timezone-aware.
```

## How to apply

```sh
git checkout -b <branch> 716d1dd22787cbb98b1c7213f7ad8ec2c66a2d03
git apply --whitespace=nowarn changes.patch
```

## Provenance

- base: `https://github.com/DtsA14/Argus-agent.git` at `716d1dd22787cbb98b1c7213f7ad8ec2c66a2d03`
- Argus: `1bb9b122c7202eb50d8e2c3b30a464b91e13fc0c`
- contract: `fix_window_strict` sha256 `a05548186f86ec8c740950e16e6aeff6489c9f4d0c72832fcddcfece0320eb9c`
- models: anthropic:claude-sonnet-5-5; 3 calls, $0.042622
- run: `pilot5a`, 1 attempt(s); patch sha256 `6de88b7286d47c8ef519fc7ecbda5a17cfa605339ef072d41ab052fd047bc0e5`

## Outcome of the pilot

Set by the reviewer, not by Argus: **agent-completed** if the patch is applied unchanged and the independent validation and `verify.sh` pass; **human-assisted** if you change any file in it (keep that change as its own diff); **failed** otherwise. Editing this description is supervision time, not a change of status.
