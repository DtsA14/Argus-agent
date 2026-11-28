# Provider speed for V4.1 Flash 1017 (2026-11-28)

Measured outside any job queue, by Claude through the CLI with a copy of `config.yaml` (the real config untouched): the pin `openrouter:deepseek/deepseek-v4.1-flash-1017` set to one upstream at a time. Model, prompts and prices of the role are the same; only the upstream changes. One sample each, so this is a first look, not a benchmark.

## Routing calls (route_eval, 6 calls of the same cases, thinking on)

| upstream | s per call | $ per call | right | note |
|---|---|---|---|---|
| deepinfra/fp8 (was first) | 18.5 | 0.00021 | 6/6 | thinking 43 to 135 tokens |
| morph/fp8 | **2.5** | 0.00019 | 6/6 | thinking 48 to 67 tokens |
| morph/fast | 1.7 | 0.00167 | 6/6 | 8x the price, 0.8 s faster than fp8 |
| fireworks | - | - | 0/3 | 503 "no healthy upstream" |
| deepseek (the maker) | - | - | 0/3 | 404: refused by our data policy (`data_collection: deny`) |

Thinking: with `reasoning: {enabled: false}` or `{effort: "low"}` (via `params.extra_body`) the provider accepted the call, reasoning tokens went to 0 and about half; the time per call did not change much on DeepInfra (floor about 14 s), so the slowness was the upstream, not the thinking.

## One code job: the ledger-cli `report --month` issue (same issue text, same base commit e112ce2), through `argus code` and `argus approve`

| | DeepInfra | morph/fp8 |
|---|---|---|
| draft | 7m47s, 15 calls, $0.069 | 4m35s, 15 calls, $0.032 |
| agent | 8m01s, 29 calls, $0.125 | 1m43s, 19 calls, $0.015 |
| total | 15m48s, $0.194 | 6m18s, $0.047 |
| review package | valid | valid |
| files | cli, filter, report, tests | the same four |
| own tests | 74 passed | 72 passed |
| cross tests | the morph tests pass on the DeepInfra code | the DeepInfra tests (74) pass on the morph code |

## Not shown

One issue; no run-to-run variation measured; the patch readers were not run on the morph result; a many-file or longer job; Morph's availability over time (DeepInfra stays behind it as the backup). `hy4-flash` as drafter/coder (3m47s, $0.016, one file) is another option, not decided.
