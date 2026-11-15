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

## Pilot non-strict di sandbox (2026-11-15; `run_pilot.py`, `green_v2.py`, `honest_mix/`)

Tiga environment, Docker, `python3 -I -B -c` (skrip GREEN revisi 2 spek), pin image dari `.sandbox_image_*`; pytest 9.1.1 di `argus` dan
`ledger_py312_up2`, `sympy_py39` = Python 3.9 dengan pytest 8.4.2 (menurut `environments/sympy_py39/requirements.txt`, versi di dalam
kontainer tidak dicetak oleh pilot). Vonis di kolom kanan = apa yang akan diputuskan aturan spek (bukan lulus-tidaknya tes proyek).

| Kasus | argus | ledger_py312_up2 | sympy_py39 |
|---|---|---|---|
| `honest_mix` (red, skip, xfail, xpass, setup error, teardown error, teardown skip, parametrize dengan spasi dan `::`) | catatan sepakat dengan teks | sama | sama |
| `pipe_forger` | tolak: tidak ada catatan | tolak | tolak |
| `noop_forger` | tolak: kenari ketiganya `ok` | tolak | tolak |
| `f1` (pemalsu berdasarkan jalur) | **lolos** (diketahui) | lolos | lolos |
| `f2` (pemalsu berdasarkan sesi) | **lolos** (diketahui) | lolos | lolos |

Premis yang tadinya belum teruji dan kini teruji: `-I -c` jalan di Python 3.9; sesi dua di proses yang sama tidak mengganggu proyek
jujur di ketiga image; hash `(node, status)` dari perekam sama dengan yang `parse_pytest` baca dari teks untuk semua status di
`honest_mix`. Belum diuji: F3 (hookwrapper di `Config`), subtest, `PYTEST_ADDOPTS` di sesi 1, `/tmp` penuh, ukuran catatan pada ribuan tes.
