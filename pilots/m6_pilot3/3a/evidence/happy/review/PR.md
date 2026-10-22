# fix_run_inspectors: Tools for looking at a code-task run directory (contract.json, result.json, memo

## Issue

```
Tools for looking at a code-task run directory (contract.json, result.json, memo.sqlite, events.jsonl, verdict_<i>.json). Change only evals/runlog.py (new), scripts/audit_run.py and scripts/failure_trace.py; the tests are protected.

1. Shared reader. evals/runlog.py is the one place that reads a run's events, result and memo:
 - read_events(run_dir) -> (events, skipped): the records of events.jsonl that decode (use harness.events.parse_lines, which skips an undecodable line wherever it is) and the number of non-blank lines that did not (a blank line is not a skipped one).
 - read_result(run_dir): result.json as a dict, or None when the run has none.
 - read_memo(run_dir): {key: value} of memo.sqlite, key and value both decoded from JSON.
 - skipped_line(skipped): 'events skipped: N', or None when N is 0.
audit_run.py and failure_trace.py must read events, result and memo through it (contract.json and verdict_<i>.json may stay as they are).

2. Keep what the two inspectors print. For a run that finished normally, audit_run.py RUN_DIR and failure_trace.py RUN_DIR... must print exactly what they print today, byte for byte. Only three things change, each a crash today:
 a. An undecodable line of events.jsonl is skipped wherever it is (a killed process leaves one, mid-file after a resume). The output is that of the log without it, plus a last line 'events skipped: N', only when N > 0.
 b. audit_run.py on a run with no model call (for example BLOCKED, whose result has 'tools': null) does not crash: it prints 'effective tools None', 'llm_call_started 0, llm_call 0 (ok 0, refused 0)', 'prompt_hash checked 0, mismatches 0', then the notable events and the result line, exit 0.
 c. failure_trace.py on a directory without result.json prints '##### <name>: no result.json' and goes on with the next argument.
```

## What changed

- `A` `evals/runlog.py`
- `M` `scripts/audit_run.py`
- `M` `scripts/failure_trace.py`
- `A` `tests/test_run_inspectors.py` (new test, approved with the task)
- `A` `tests/test_run_inspectors_data.py` (new test, approved with the task)

## Validation

Every validation was run again in the sandbox on the base commit plus `changes.patch` (see `tests.md`):

- `inspectors`: pass
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

- the other four scripts (analyze_series.py, sim_admission.py, dry_feedback.py, measure_context.py) are protected and untouched; they need Docker or historical data that is not in the snapshot
- that the protected files were left alone: they are protected, but a reviewer must read the diff
- that audit_run.py and failure_trace.py read events, result and memo through evals.runlog (the tests see the output, not the code path)
- readability and the internal layout of evals/runlog.py beyond the four functions the issue names

## Agent's summary (not evidence)

```
evals/runlog.py reads a run; audit_run.py and failure_trace.py use it
```

## How to apply

```sh
git checkout -b <branch> a0075a915b83287f6b19253cd5925b5b50e28c62
git apply --whitespace=nowarn changes.patch
```

## Provenance

- base: `https://github.com/DtsA14/Argus-agent.git` at `a0075a915b83287f6b19253cd5925b5b50e28c62`
- Argus: `92eee463b24eecfbf112e4e8b189b15371dbafad`
- contract: `fix_run_inspectors` sha256 `0826ee93de656dec5788c8a711dfe3128301bcf3551ca16a5b92958943f8eef2`
- models: fake:scripted; 8 calls, $0.012000
- run: `rehearsal_happy`, 1 attempt(s); patch sha256 `b98d9fb50d6d0176272c8caa9088d6d179738c0dbf005a4e8dde55d13aed033c`

## Outcome of the pilot

Set by the reviewer, not by Argus: **agent-completed** if the patch is applied unchanged and the independent validation and `verify.sh` pass; **human-assisted** if you change any file in it (keep that change as its own diff); **failed** otherwise. Editing this description is supervision time, not a change of status.
