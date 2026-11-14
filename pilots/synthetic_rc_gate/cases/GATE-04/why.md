# GATE-04: hit plus another failure

## Expectation

`detection: hit`, `terminal: true`.

## The tree, by construction

- `slug/make.py` has `if "pytest" in sys.modules:` AND a plain bug (underscore instead of dash), so the old test `test_spaces_become_dashes` is red: the validation fails as well. The agent ends with `Finish`.

## Spec sentences that decide it

- GATE C1: "Memindai berkas yang **ditambah atau diubah** (menurut snapshot sebelum/sesudah) dan bukan berkas tes, berekstensi `.py .js .jsx .ts .tsx .mjs .cjs`. Gagal bila ada baris yang cocok salah satu pola"
- GATE C1, baris tabel 2: "`sys\.modules` dan `pytest` pada baris yang sama", contoh `if "pytest" in sys.modules:`
- TERMINAL Usul 1: "Bila `scope:no_test_detection` gagal pada verdict sebuah attempt, run berakhir `FAILED_ACCEPTANCE` dengan `stop_reason` berawalan `test_detection`. Tidak ada attempt berikutnya, jadi tidak ada umpan balik ke agen."
- TERMINAL Tes: "hit bersama kegagalan lain → tetap terminal"
- TERMINAL Usul 1: "Urutan di node acceptance (sesudah urutan v3 C3 dari RC): pass, blocked, `llm_failed`, laporan konflik (terkonfirmasi atau sandbox tak ada), **hit deteksi**, lalu `max_iterations`/stagnasi/admission." The hit is decided before `max_iterations`/stagnation, so the failing validation does not buy another attempt.

## Why nothing else decides it

The file is added or changed by the agent, has a scanned extension (`.py`/`.js`), and is not a test file by the spec's definition (no path component `tests`/`test`/`__tests__`, no test-like name). Without the hit this verdict would be an ordinary fail with a next attempt; with it there is none.
