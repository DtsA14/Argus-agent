Ledger issue 021: GET /scoreboard/models, the model calls and their cost per model

Add `GET /scoreboard/models`. It answers one JSON object, `{"models": [...]}`, where each entry is `{"model": <string>, "calls": <int>, "cost_nano": <int>}`.

It reads the same jobs and the same run ledgers as `GET /summary` and `GET /scoreboard`, with the same login and `Host` rules, and changes no file. Every `events.jsonl` of every job is read once, exactly as the job cost already does (including a run no stage names).

A call is one `call_id`. Its model is the `model` string of its `llm_call_started` event; when that event has no string `model`, the call counts under the model `"unknown"`. Its cost is the one the ledger already computes for that call: the `usd_nano` of its final event, 0 for a `refused` or null cost, and the `worst_usd_nano` of its started event when no final event exists. `calls` counts every call_id that has a started event, whatever its status.

Entries are sorted by `cost_nano` descending, ties by `model` ascending (plain string order). An empty or missing jobs directory answers `{"models": []}`.

Example: job A has calls c1 (model `deepseek:deepseek-flash`, final usd_nano 100), c2 (same model, no final event, worst_usd_nano 50) and c3 (model `anthropic:claude-haiku`, final status `refused`); job B has c4 (model `anthropic:claude-haiku`, usd_nano 300). Answer: `{"models":[{"model":"anthropic:claude-haiku","calls":2,"cost_nano":300},{"model":"deepseek:deepseek-flash","calls":2,"cost_nano":150}]}`.

The sum of every `cost_nano` in the answer must equal the total cost `GET /summary` reports for the same directory. Add tests (including that equality and the example above) and a section in README.md.
