Ledger issue 022: GET /scoreboard/models gets cost_usd and a total

Extend `GET /scoreboard/models` (ledger issue 021, already in the code). Keep every existing key and their order.

Each entry gets a key `cost_usd` right after `cost_nano`: the same four-decimal text `GET /summary` uses for dollars (the helper the scoreboard already uses for its own `cost_usd`). The object gets a second top-level key `total`, after `models`: `{"calls": <int>, "cost_nano": <int>, "cost_usd": <text>}`, the sums over all entries.

With the example of issue 021 the answer becomes `{"models":[{"model":"anthropic:claude-haiku","calls":2,"cost_nano":300,"cost_usd":"0.0000"},{"model":"deepseek:deepseek-flash","calls":2,"cost_nano":150,"cost_usd":"0.0000"}],"total":{"calls":4,"cost_nano":450,"cost_usd":"0.0000"}}`.

An empty or missing jobs directory answers `{"models":[],"total":{"calls":0,"cost_nano":0,"cost_usd":"0.0000"}}`. `total.cost_nano` equals the total cost of `GET /summary` and the sum of the `cost_nano` of `GET /scoreboard`'s kinds. Update the tests of issue 021 where the shape changed, add tests for the new keys, and update the README section.
