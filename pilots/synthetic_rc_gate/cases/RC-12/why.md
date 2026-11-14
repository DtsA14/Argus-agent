# RC-12: red in one run, green in another (deterministic, order-dependent)

## Expectation

`decision: unconfirmed`.

## The tree, by construction

- The agent added a module-level price cache that is not invalidated by `set_discount` (an agent bug).
- Full validation run `python -m pytest tests` (files in alphabetical order, one process): `tests/test_a_discount.py::test_discount_applies` runs first, caches the discounted price 2 for `apple` and passes; then `tests/test_b_price.py::test_list_price` reads the stale 2 and is red (2 != 3). So the verdict's `failed_nodes` is exactly that node, and the agent names its file.
- When that node is run ALONE (as `red_check` does), the cache is empty and the test passes: in the workspace and in the input.
- The new test `tests/test_c_cache.py::test_price_is_cached` is green with the change and red on the input. Nothing depends on time, randomness or files: the instability comes only from which nodes share a process.

## Spec sentences that decide it

- v3 C5: "`red_check` dijalankan pada node-node itu saja (dua kali di workspace, satu kali di input, seperti v2)." So the re-run executes only `tests/test_b_price.py::test_list_price`.
- v3 C1: "Syarat baru, untuk setiap node merah: `outcome == "failed"`, `path` tidak `None`, dan berkas `path` (a) ada di intake dengan digest yang sama, (b) cocok glob protected (kontrak atau `repo_protected` yang dibekukan di setup), (c) bukan berkas `new_tests`/`changed_tests` draf." In the `red_check` record of that node `outcome` is not `"failed"`: the condition fails.
- v1 R2.9: "Butir 7 dan 8 dijalankan dua kali; keempat hasil harus sama (tes flaky)." / v2 §2 (baris R2.9): "Dua `red_check` pada workspace, satu pada input: tiga run": the runs must agree on red-with-the-change; here the validation says red and both workspace re-runs say green.
- v1 §4 (Penyalahgunaan): "Tes lama flaky | Butir 9"

## Why nothing else decides it

Scope, detection, must_pass, baseline (green on the input), file naming and the production diff all hold; only the re-run disagrees. NOTE: this is the flaky analogue the spec DOES decide. A test whose two identical `red_check` runs differ from each other cannot be built without state that survives between sandbox runs (clock, randomness, files), and the spec does not say whether the workspace is writable during `red_check` (v1 §3 says "sandbox read-only", v3 C2 says "Sandbox me-mount workspace bisa-tulis" for validation): listed as a spec gap, no case written.
