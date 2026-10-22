# Draft review: `argus_p6` (w2b1d1)

Status: **NO_DRAFT** (output_truncated)

Written by the harness from the draft and its check. The draft itself was written by a model: read the tests. A passing baseline shows only that the new tests fail now, not that they test the right thing.

## Issue

```text
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

No draft passed its check; nothing to approve.

## Cost

Drafter: $0.1596, 4 model calls, 0 submits, 3 steps (ended: output_truncated).
