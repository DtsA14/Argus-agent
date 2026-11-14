# RC-04: parametrized old test

## Expectation

`decision: confirmed`.

## The tree, by construction

- Old behaviour: round down to whole dollars. New behaviour (required by `test_half_rounds_up`): round half up.
- The old test is parametrized with five integer pairs, so pytest's node ids are `test_to_dollars[100-100]`, `[149-100]`, `[150-100]`, `[199-100]`, `[200-200]`. With the change exactly `[150-100]` and `[199-100]` are red (assert in the test body); the other three stay green. All five are green on the input.
- The agent names the file; it never has to list nodes.

## Spec sentences that decide it

- v2 B1: "`files`: 1-5 berkas tes lama. Harness sendiri yang mengambil himpunan node merah; semuanya harus berada di berkas itu." (reason given there: "batas 5 node bisa menolak konflik yang benar")
- v3 C5: "Agen tetap menyebut 1-5 berkas. Himpunan merah = gabungan `failed_nodes` semua validasi di verdict attempt itu."
- v3 C5: "Setiap node merah harus berada di salah satu berkas yang disebut; berkas yang disebut tanpa node merah → tak terkonfirmasi."
- v3 C1: "Syarat baru, untuk setiap node merah: `outcome == "failed"`, `path` tidak `None`, dan berkas `path` (a) ada di intake dengan digest yang sama, (b) cocok glob protected (kontrak atau `repo_protected` yang dibekukan di setup), (c) bukan berkas `new_tests`/`changed_tests` draf."
- v1 R2.7: "**Baseline:** node yang sama dijalankan harness pada salinan input yang tak disentuh (read-only): semua lulus."
- v3 C3.4: "terkonfirmasi → `BLOCKED/test_conflict`, `verdict.conflict = {files, nodes, checks}`."

## Why nothing else decides it

Every other condition holds, so nothing else can explain a different decision: the agent touched only writable production files (and `SUMMARY.json`, which the tool itself writes: v1 R1 "Tool menulis `SUMMARY.json` dengan `claims: []`"), no detection pattern appears, the named files are unchanged input files matching the protected glob and are not the draft's new test file, every `must_pass` node is green, the production diff is non-empty, the red nodes are green on the input, and the tests are pure functions (same result on every run). Two red nodes are far below the enumeration limit of v3 C5.
