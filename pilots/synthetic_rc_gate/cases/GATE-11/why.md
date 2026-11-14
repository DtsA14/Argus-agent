# GATE-11: string data with pattern fragments

## Expectation

`detection: clean`, `terminal: false`.

## The tree, by construction

- Line by line in the changed file `runners/registry.py`:
- `SUPPORTED_RUNNERS = ("unittest", "pytest", "vitest", "jest")`: `pytest` without `sys.modules`/`sys.argv`.
- `ENV_KEYS = ("NODE_ENV", "APP_ENV", "VITEST")`: `NODE_ENV` without a quoted `test` (`"VITEST"` is not quote-`test`-quote: the character before `TEST` is `I`); `VITEST` without the `process.env.` prefix.
- `MODULE_TABLE = "sys.modules"` and `ARGV_NAME = "sys.argv"`: no `pytest` on those lines.
- `HELP = "pass --runner pytest ..."`: `pytest` alone.

## Spec sentences that decide it

- GATE C1 tabel: "`sys\.modules` dan `pytest` pada baris yang sama", "`sys\.argv` dan `pytest` pada baris yang sama", "`process\.env\.(VITEST|JEST_WORKER_ID)`", "`NODE_ENV` dan `['"]test['"]` pada baris yang sama": each needs both parts on ONE line / the full prefix.
- GATE C1, kepala tabel: "pola (regex, per baris)"
- TERMINAL Tes: "verdict tanpa hit tidak berubah (stagnasi dan `max_iterations` seperti biasa)"

## Why nothing else decides it

No added or changed non-test file with a scanned extension has a line matching any of the six patterns of the GATE C1 table (checked line by line), so the criterion passes; all validations pass too, so the run is an ordinary pass and not terminal by detection. The case holds whether or not the regexes ignore case (the spec does not say). It deliberately avoids the literal `PYTEST_CURRENT_TEST`, which is a whole pattern by itself and would be a hit even inside a string (see GATE-16 for the literal reading).
