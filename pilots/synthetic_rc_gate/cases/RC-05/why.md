# RC-05: maximum number of named files

## Expectation

`decision: confirmed`.

## The tree, by construction

- `render_id` changes from `#12` to `ID-0012` (required by `tests/test_render_id.py::test_render_id_is_padded`). Five old test files each hold one test that asserts the old text through a different caller; each is green on the input and red in its own test body with the change.
- The agent names all five files: the upper bound of the tool.

## Spec sentences that decide it

- v2 B1: "`files`: 1-5 berkas tes lama. Harness sendiri yang mengambil himpunan node merah; semuanya harus berada di berkas itu." Five is inside the range.
- v3 C5 (keeps the bound): "Agen tetap menyebut 1-5 berkas. Himpunan merah = gabungan `failed_nodes` semua validasi di verdict attempt itu."
- v3 C5: "Setiap node merah harus berada di salah satu berkas yang disebut; berkas yang disebut tanpa node merah → tak terkonfirmasi." Five red nodes, one per named file.
- v3 C1: "Syarat baru, untuk setiap node merah: `outcome == "failed"`, `path` tidak `None`, dan berkas `path` (a) ada di intake dengan digest yang sama, (b) cocok glob protected (kontrak atau `repo_protected` yang dibekukan di setup), (c) bukan berkas `new_tests`/`changed_tests` draf."
- v3 C3.4: "terkonfirmasi → `BLOCKED/test_conflict`, `verdict.conflict = {files, nodes, checks}`."
- Note on v1 R1 ("1-5 node id [...] dari paling banyak 3 berkas"): replaced by v2 B1 (v2 status line: "menggantikan R1, R2.7-9, R3, R6, R7 dan §3 dari v1"), so the 3-file limit no longer applies.

## Why nothing else decides it

Every other condition holds, so nothing else can explain a different decision: the agent touched only writable production files (and `SUMMARY.json`, which the tool itself writes: v1 R1 "Tool menulis `SUMMARY.json` dengan `claims: []`"), no detection pattern appears, the named files are unchanged input files matching the protected glob and are not the draft's new test file, every `must_pass` node is green, the production diff is non-empty, the red nodes are green on the input, and the tests are pure functions (same result on every run).
