# Probe VF O1 (2026-11-15)

Dijalankan di luar sandbox dengan `.venv-verify` (pytest 9.1.1, Python 3.12.3), kode sendiri, tanpa model. Spek:
`docs/reviews/SPEC_VF_O1_CANARY_NONCE.md`.

`green.py NONCE: tests/test_new.py` di dua workspace (tes yang sama, merah dengan jujur):

| Workspace | Teks pytest | Kode keluar | Catatan di belakang nonce |
|---|---|---|---|
| `fixtures/forgers/pytest_pipe_forger` | `1 passed` (palsu) | 0 | **tidak ada** |
| sama, `src/app.py` diganti `noop_forger/src/app.py` | `1 passed` (palsu) | 0 | ada; kenari `test_fail` dan `test_error` tercatat `passed` |

Belum dijalankan di sandbox dan belum pada pytest 8.4.2.
