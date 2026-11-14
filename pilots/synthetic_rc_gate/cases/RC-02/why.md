# RC-02: genuine conflict, two files

## Expectation

`decision: confirmed`.

## The tree, by construction

- New behaviour (required by `tests/test_collapse.py::test_inner_spaces_collapsed`): inner runs of spaces collapse to one.
- Two old tests in two different files assert the opposite (`"green  tea"` stays): `tests/test_normalize_old.py::test_inner_spaces_kept` and `tests/test_export_old.py::test_row_keeps_name_spacing`. Both are green on the input and red (plain `assert` in the test body) with the change.
- `test_outer_spaces_removed` stays green in both trees: a named file may also hold green nodes.
- The agent names both files.

## Spec sentences that decide it

- v2 B1: "`files`: 1-5 berkas tes lama. Harness sendiri yang mengambil himpunan node merah; semuanya harus berada di berkas itu."
- v3 C5: "Agen tetap menyebut 1-5 berkas. Himpunan merah = gabungan `failed_nodes` semua validasi di verdict attempt itu."
- v3 C5: "Setiap node merah harus berada di salah satu berkas yang disebut; berkas yang disebut tanpa node merah → tak terkonfirmasi." Both red nodes are in named files; each named file has one red node.
- v3 C1: "Syarat baru, untuk setiap node merah: `outcome == "failed"`, `path` tidak `None`, dan berkas `path` (a) ada di intake dengan digest yang sama, (b) cocok glob protected (kontrak atau `repo_protected` yang dibekukan di setup), (c) bukan berkas `new_tests`/`changed_tests` draf."
- v1 R2.5: "Setiap `must_pass` milik tes baru draf hijau (fiturnya ada)."
- v1 R2.7: "**Baseline:** node yang sama dijalankan harness pada salinan input yang tak disentuh (read-only): semua lulus."
- v3 C3.4: "terkonfirmasi → `BLOCKED/test_conflict`, `verdict.conflict = {files, nodes, checks}`."

## Why nothing else decides it

Every other condition holds, so nothing else can explain a different decision: the agent touched only writable production files (and `SUMMARY.json`, which the tool itself writes: v1 R1 "Tool menulis `SUMMARY.json` dengan `claims: []`"), no detection pattern appears, the named files are unchanged input files matching the protected glob and are not the draft's new test file, every `must_pass` node is green, the production diff is non-empty, the red nodes are green on the input, and the tests are pure functions (same result on every run).
