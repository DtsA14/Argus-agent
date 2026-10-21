# fix_impl_flag: main.py: the --impl option (node=kind, which switches a node of the pipeline bet

## Issue

```
main.py: the --impl option (node=kind, which switches a node of the pipeline between 'fake' and 'llm') is not validated. A mistyped node such as --impl evalutor=llm is accepted and silently ignored, so the run goes on with the fake evaluator while the user believes the real one is used. An item without '=', with an empty node or kind, or with a kind other than exactly 'fake' or 'llm' (for example 'llmm' or 'LLM') fails late inside the graph with a traceback, after the run directory and its checkpoint were created, so the corrected command with the same --run-id is then refused as an existing run. Every invalid --impl must be refused before anything is created, the way --model already is: a 'config error: ...' message on stderr (no traceback) and exit code 1. For an unknown node the message names the node and lists the valid ones (orchestrator, worker, synthesize, evaluator); for a wrong kind it names the node, the value and the allowed ones ('fake' or 'llm'). Kinds are not normalised: 'LLM' is refused. Valid --impl flags, no flag, repeated --impl for one node (the last one wins) and --model behave exactly as before. Change only main.py and models/registry.py; the tests are protected.
```

## What changed

- `M` `main.py`
- `M` `models/registry.py`
- `A` `tests/test_impl_flag.py` (new test, approved with the task)

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

- a mistyped node under impl: in a config file is ignored too; that is a separate change and is not tested
- the exact wording of the error messages beyond the key words the tests look for
- that graph.py, runner.py and config.yaml were left alone: they are protected, but a reviewer must read the diff
- readability and where the validation lives (the contract fixes the behaviour, not the code layout)

## Agent's summary (not evidence)

```
Added parse_impl validation in models/registry.py (node and kind checks, raising ConfigError) and main.py now calls it before anything is created, printing 'config error: ...' and exiting 1. Target and regression validations pass.
```

## How to apply

```sh
git checkout -b <branch> cc8a2fda4b29b9e862d8f1a2d0e3a750d2a35c95
git apply --whitespace=nowarn changes.patch
```

## Provenance

- base: `https://github.com/DtsA14/Argus-agent.git` at `cc8a2fda4b29b9e862d8f1a2d0e3a750d2a35c95`
- Argus: `5996b08a43e6402cc297e03ab256254357a7a254`
- contract: `fix_impl_flag` sha256 `295e95147779c5e8fa0526600afb5cc6f0195f2f54a9d4e5c0d36bf8eef9d23e`
- models: anthropic:claude-sonnet-5-5; 5 calls, $0.079526
- run: `pilot2`, 2 attempt(s); patch sha256 `d96f57299946b8ecb5e6bb697ae2894df93c00b06fb2af65cd27dfac7ebc470f`

## Outcome of the pilot

Set by the reviewer, not by Argus: **agent-completed** if the patch is applied unchanged and the independent validation and `verify.sh` pass; **human-assisted** if you change any file in it (keep that change as its own diff); **failed** otherwise. Editing this description is supervision time, not a change of status.
