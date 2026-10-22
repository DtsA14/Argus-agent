# pilot_report: Add scripts/pilot_report.py: python scripts/pilot_report.py RUN_DIR... [--superv

## Issue

```
Add scripts/pilot_report.py: python scripts/pilot_report.py RUN_DIR... [--supervision FILE]. Change nothing else.
Read runs only via evals/runlog.py (read_events, read_result); cost known iff evals.score.cost_is_known(result).
Print json.dumps(obj, indent=2, ensure_ascii=False) + newline, exit 0. Keys in this order:
runs: per argument, in order: run_id (dir name), status (result status, or "NO_RESULT" if no result.json), done (status=="DONE"), attempts, llm_calls, usd_billed (as in result.json; null if NO_RESULT), cost_known (false if NO_RESULT), events_skipped (from read_events), supervision_minutes (null if none; never 0 instead).
runs_total; done; no_result;
success_rate = done/(runs_total-no_result), round 4; null if divisor 0;
usd_known_total = sum of usd_billed over cost_known runs, summed as round(x*1e9) nano-dollars, /1e9, round 6; 0.0 if none;
usd_unknown_runs = runs not cost_known;
cost_per_success = usd_known_total / runs both done and cost_known, round 6; null if divisor 0;
cost_complete = usd_unknown_runs == 0;
attempts = {mean round 3, median (statistics.median)} over done runs; null if none;
attempts_distribution = {"<attempts>": count} over runs with result.json, keys numeric order;
supervision = {runs_with_data, total, mean round 2} over runs with minutes; total, mean null if none;
events_skipped = sum.
Supervision file: JSON object {run_id: minutes}; each value int/float, not bool, finite, >= 0; each key a given run_id.
Exit 2, stdout empty, one stderr line, when: no runs ("no run directory given"); an argument not a directory or without events.jsonl (the argument and "not a run directory"); a supervision file unreadable or invalid ("supervision file" and its path).
```

## What changed

- `A` `scripts/pilot_report.py`
- `A` `tests/test_pilot_report.py` (new test, approved with the task)

## Validation

Every validation was run again in the sandbox on the base commit plus `changes.patch` (see `tests.md`):

- `report`: pass
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

- that the script reads runs only through evals.runlog and decides known cost only with cost_is_known (the tests see the output, not the code path)
- that nothing else was changed: the scope protects the rest, but a reviewer must read the diff
- readability and the internal layout of scripts/pilot_report.py

## Agent's summary (not evidence)

```
Added scripts/pilot_report.py. It reads runs only through evals/runlog.py and cost_is_known. It prints the JSON report in the specified key order and exits 2 with one stderr line on invalid input. No other file changed.
```

## How to apply

```sh
git checkout -b <branch> f37aaba03a19cb7f84d42a4f3f0b3b755f7b020d
git apply --whitespace=nowarn changes.patch
```

## Provenance

- base: `https://github.com/DtsA14/Argus-agent.git` at `f37aaba03a19cb7f84d42a4f3f0b3b755f7b020d`
- Argus: `400f3a58a6ad6f8203d8048e0ce5ee8c19780302`
- contract: `pilot_report` sha256 `bff30d351f1cb4f010f06d9687db28617bfd97ca80ef1fa929b028e668a34b1d`
- models: anthropic:claude-sonnet-5-5; 4 calls, $0.110328
- run: `pilot3b1`, 1 attempt(s); patch sha256 `84f365e83b439e4fb8b0c2803d4f14191cbcbc558e10bb92e68fa915b9f2ea0c`

## Outcome of the pilot

Set by the reviewer, not by Argus: **agent-completed** if the patch is applied unchanged and the independent validation and `verify.sh` pass; **human-assisted** if you change any file in it (keep that change as its own diff); **failed** otherwise. Editing this description is supervision time, not a change of status.
