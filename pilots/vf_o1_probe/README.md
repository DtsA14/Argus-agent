# Probe VF O1 (2026-11-15)

Dijalankan di luar sandbox dengan `.venv-verify` (pytest 9.1.1, Python 3.12.3), kode sendiri, tanpa model. Spek:
`docs/reviews/SPEC_VF_O1_CANARY_NONCE.md`.

`green.py NONCE: tests/test_new.py` di dua workspace (tes yang sama, merah dengan jujur):

| Workspace | Teks pytest | Kode keluar | Catatan di belakang nonce |
|---|---|---|---|
| `fixtures/forgers/pytest_pipe_forger` | `1 passed` (palsu) | 0 | **tidak ada** |
| sama, `src/app.py` diganti `noop_forger/src/app.py` | `1 passed` (palsu) | 0 | ada; kenari `test_fail` dan `test_error` tercatat `passed` |

Belum dijalankan di sandbox dan belum pada pytest 8.4.2.

## Tambahan dari tinjauan Opus (2026-11-15, dijalankan oleh peninjau di pytest 9.1.1)

- `path_forger_f1/src/app.py`: tes di bawah akar repositori menjadi no-op, tes di tempat lain (kenari di `/tmp`) berjalan jujur.
- `session_forger_f2/src/app.py`: semua tes no-op, dipulihkan di `pytest_sessionfinish`.
- Keduanya lolos semua aturan spek versi pertama: teks "1 passed", kode keluar 0, catatan benar, kenari benar.
- `cmp_record_vs_text.py`: perbandingan hasil per node dari `pytest_runtest_logreport` dengan `parse_pytest`; berbeda untuk setup error,
  teardown error, xfail dan xpass non-strict.
