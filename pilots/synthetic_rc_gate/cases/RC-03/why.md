# RC-03: old test fails in a protected helper module

## Expectation

`decision: confirmed`.

## The tree, by construction

- `tests/test_records.py::test_record_shape` calls `assert_record_shape()` from `tests/helpers.py`; the `assert` that fails is in the helper, so the innermost repository frame (`path`) is `tests/helpers.py`, not the test file.
- `tests/helpers.py` is an input file, not changed by the agent, matches the protected glob `tests/**`, and is not the draft's new test file (`tests/test_email.py`).
- The red NODE is in `tests/test_records.py`, which is the file the agent names. `tests/helpers.py` is deliberately NOT named: it holds no test node.
- Input: the node is green. Workspace: `make_record` gains the key `email` (required by the new test, which is red on the input with `TypeError` and green with the change).

## Spec sentences that decide it

- v3 C1: "`path` di record `red_check` adalah frame terdalam di dalam repositori, bukan frame tes [...]. "`path` = berkas tes itu sendiri" menolak tes lama yang gagal di dalam helper atau `conftest.py`."
- v3 C1: "Syarat baru, untuk setiap node merah: `outcome == "failed"`, `path` tidak `None`, dan berkas `path` (a) ada di intake dengan digest yang sama, (b) cocok glob protected (kontrak atau `repo_protected` yang dibekukan di setup), (c) bukan berkas `new_tests`/`changed_tests` draf." (a), (b), (c) hold for `tests/helpers.py`.
- v3 §2 tes 1: "Tes lama gagal di dalam helper pada berkas terkunci yang tidak berubah → terkonfirmasi (C1)."
- v3 §7: "Syarat C1 (a)(b)(c) dikenakan pada **dua hal**: berkas node merah dan `path` dari record `red_check` (keduanya harus berkas input yang tak disentuh, terlindungi, dan bukan tes draf)." Both the node's file (`tests/test_records.py`) and the `path` file (`tests/helpers.py`) satisfy them.
- v3 C5: "Setiap node merah harus berada di salah satu berkas yang disebut; berkas yang disebut tanpa node merah → tak terkonfirmasi." The rule speaks of the red NODE's file, so naming `tests/test_records.py` alone is right; naming `tests/helpers.py` too would be "berkas yang disebut tanpa node merah".

## Why nothing else decides it

Every other condition holds, so nothing else can explain a different decision: the agent touched only writable production files (and `SUMMARY.json`, which the tool itself writes: v1 R1 "Tool menulis `SUMMARY.json` dengan `claims: []`"), no detection pattern appears, the named files are unchanged input files matching the protected glob and are not the draft's new test file, every `must_pass` node is green, the production diff is non-empty, the red nodes are green on the input, and the tests are pure functions (same result on every run). `helpers` is importable because pytest puts the directory of a test file without `__init__.py` on `sys.path` (default import mode).
