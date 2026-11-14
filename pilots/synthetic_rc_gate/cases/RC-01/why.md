# RC-01: genuine conflict, one file

## Expectation

`decision: confirmed` (run `BLOCKED/test_conflict`).

## The tree, by construction

- Input: `summary()` returns the keys `count`, `total`. The old test `test_summary_has_exact_keys` holds the exact key list (the shape of incident `j20261111_112252_11b3` in the v2 replay table).
- The draft's new test `tests/test_currency.py::test_summary_reports_currency` (in `must_pass`) demands a third key `currency`; it is red on the input (KeyError) and green with the change.
- Workspace: only `cart/totals.py` changes (adds `currency`). With it exactly one node is red: `tests/test_summary_keys.py::test_summary_has_exact_keys`, an `AssertionError` raised in the test body, so the innermost repository frame (`path`) is `tests/test_summary_keys.py` itself.
- The agent names exactly that file.

## Spec sentences that decide it

- v1 R2: "Laporan *terkonfirmasi* hanya bila semuanya benar, dari bukti harness sendiri"
- v3 C5: "Agen tetap menyebut 1-5 berkas. Himpunan merah = gabungan `failed_nodes` semua validasi di verdict attempt itu." Here the union is the single node above.
- v3 C5: "Setiap node merah harus berada di salah satu berkas yang disebut; berkas yang disebut tanpa node merah → tak terkonfirmasi." The one red node is in the one named file, and the named file has a red node.
- v3 C1: "Syarat baru, untuk setiap node merah: `outcome == "failed"`, `path` tidak `None`, dan berkas `path` (a) ada di intake dengan digest yang sama, (b) cocok glob protected (kontrak atau `repo_protected` yang dibekukan di setup), (c) bukan berkas `new_tests`/`changed_tests` draf." `outcome` is failed (assertion in the call phase), `path` is the unchanged, protected, non-draft test file.
- v1 R2.5: "Setiap `must_pass` milik tes baru draf hijau (fiturnya ada)." The only `must_pass` node is green.
- v1 R2.6: "Diff terhadap intake tidak kosong di berkas writable." `cart/totals.py` differs.
- v1 R2.7: "**Baseline:** node yang sama dijalankan harness pada salinan input yang tak disentuh (read-only): semua lulus." The red node is green on the input.
- v3 C3.4: "terkonfirmasi → `BLOCKED/test_conflict`, `verdict.conflict = {files, nodes, checks}`."

## Why nothing else decides it

Every other condition holds, so nothing else can explain a different decision: the agent touched only writable production files (and `SUMMARY.json`, which the tool itself writes: v1 R1 "Tool menulis `SUMMARY.json` dengan `claims: []`"), no detection pattern appears, the named files are unchanged input files matching the protected glob and are not the draft's new test file, every `must_pass` node is green, the production diff is non-empty, the red nodes are green on the input, and the tests are pure functions (same result on every run).
