# fix_run_stats: evals/score.py: run_stats() raises json.JSONDecodeError when a run's events.json

## Issue

```
evals/score.py: run_stats() raises json.JSONDecodeError when a run's events.jsonl contains a line that is not valid JSON. A run that was killed while writing an event and then resumed leaves exactly such a line in the middle of the file. The harness's own reader of the same file, harness.events.parse_lines (used by EventLog.read), skips a line that is not valid JSON wherever it is. run_stats must read events.jsonl the same way: ignore lines that are not valid JSON, and count every other line exactly as before. Change only evals/score.py (run_stats); the tests are protected and independent_checks, honesty, score and aggregate must not change.
```

## What changed

- `M` `evals/score.py`
- `A` `tests/test_run_stats.py` (new test, approved with the task)

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

- a line that is valid JSON but not an object (for example 123) is neither required nor tested: harness.events.parse_lines passes it through, and run_stats would then fail on it; that is outside this task
- that independent_checks, honesty, score and aggregate in evals/score.py were left alone: the writable scope is the whole file, so a reviewer must read the diff
- readability of the change

## Agent's summary (not evidence)

```
run_stats now reads events.jsonl with harness.events.parse_lines, so lines that are not valid JSON are skipped and blank lines are ignored.
```

## How to apply

```sh
git checkout -b <branch> 5ff64d0bd49f60ae9d8ac0ed06e2ec13504ab9d2
git apply --whitespace=nowarn changes.patch
```

## Provenance

- base: `https://github.com/DtsA14/Argus-agent.git` at `5ff64d0bd49f60ae9d8ac0ed06e2ec13504ab9d2`
- Argus: `1b0780f7cb475e88af433f0e04f54c6198005a59`
- contract: `fix_run_stats` sha256 `c75cecee3c1ee69d5e6b685a94caadfb402d1f766d5298282b7bc7b736ae7901`
- models: anthropic:claude-sonnet-5-5; 4 calls, $0.057474
- run: `pilot1`, 1 attempt(s); patch sha256 `c1f1a925a309a7d5fd4a766f5f6ac0063ae33489323b0b521b346c3cd84d3286`

## Outcome of the pilot

Set by the reviewer, not by Argus: **agent-completed** if the patch is applied unchanged and the independent validation and `verify.sh` pass; **human-assisted** if you change any file in it (keep that change as its own diff); **failed** otherwise. Editing this description is supervision time, not a change of status.
