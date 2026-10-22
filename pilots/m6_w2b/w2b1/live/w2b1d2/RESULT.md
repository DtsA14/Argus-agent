# Pilot W2b-1, run `w2b1d2`: hasil

2026-10-22. Seperti `w2b1d1`, dengan satu perubahan: output drafter 16.384 (pilihan A, PREFLIGHT bagian 6). Argus
`53a8e9b` (checkout bersih), Sonnet 5.5.

## Ringkasan

| | |
|---|---|
| Status | **`NO_DRAFT`** (`context_limit`): **gagal** menurut kriteria 1 |
| Panggilan model | 5 terkirim dan 1 **ditolak sebelum dikirim** (`input_limit`: perkiraan input 45.035 > 40.000); langkah 5 dari 16 |
| Submit | 1 dicek, ditolak dengan 1 masalah |
| Biaya | **$0,2181** (`usd_complete` true); cache read 55.775, write 30.566, penghematan ±$0,091. W2b-1 total: $0,3777 |
| Salinan intake | tidak berubah |
| Waktu terminal | gerbang lolos 16:16:45Z, kunci 16:16:53Z, selesai 16:18:36Z (**1 menit 51 detik**) |

## Jalur

| Langkah | Masukan | Keluaran (thinking) | USD | Apa |
|---|---|---|---|---|
| s0 | 2.858 | 28 | 0,0074 | ListFiles |
| s1 | 10.461 | 215 | 0,0215 | baca 4 berkas (seperti `w2b1d1`) |
| s2 | 18.458 | 348 | 0,0245 | baca `scripts/audit_run.py`, `fixtures/audit/pilot3a4/result.json`, `conftest.py`; SearchFiles `subprocess` di `tests` |
| s3 | 24.008 | 276 | 0,0185 | baca `scripts/run_eval.py`, `harness/events.py`, `tests/test_eval_cost.py` |
| s4 | 30.568 | **12.743 (5.296)** | 0,1462 | **SubmitDraft 1**: tes 9,7 KB, 23 node wajib baru, validasi regresi `tests/test_eval_cost.py` |
| s5 | 45.035 (perkiraan) | – | 0 | **ditolak sebelum dikirim**: input lebih dari 40.000 |

## Submit 1: hampir lolos

Masalah satu-satunya: *"validation target: 24 failures and 0 errors on the baseline; exactly the 23 new required tests
may fail"*. Tes ke-24 yang gagal adalah `test_no_run_directory_given_no_args`. Model menulisnya di berkas, tetapi lupa
memasukkannya ke `must_pass`. Ke-23 node wajib **merah karena assertion** di sandbox, dan validasi regresi hijau.

Drafter menghindari jebakan "berkas baru" yang diperkirakan di preflight: skrip dijalankan sebagai subprocess, jadi tes
gagal karena assertion atas keluarannya (`can't open file ... pilot_report.py`), bukan karena import error.

Perbaikannya hanya menambah satu node ke `must_pass`. Tetapi untuk itu model harus mengirim ulang seluruh draf, karena
draf pertama (15,5 KB argumen) kini ada di riwayat. Panggilan berikutnya butuh input ±45.000, sehingga ditolak oleh batas
input per panggilan (D1, 40.000) sebelum dikirim. Harness bekerja sesuai rancangan.

**Celah harness yang terlihat:** pesan penolakan tidak menyebut tes mana yang gagal tanpa diwajibkan. Model hanya tahu
"24 vs 23". Status setiap node sebenarnya sudah di-parse (`parse_pytest`), tetapi tidak masuk bukti validasi.

## Cakupan dibanding draf manusia (dari isi tes submit 1, `submit1_args.json`)

| Perilaku (draf manusia) | Draf model |
|---|---|
| tujuh jenis run | `test_mixed_runs_report_values` dan `..._key_order`: **lima** run campuran (DONE, FAILED_ACCEPTANCE, DONE dengan biaya tak diketahui, NO_RESULT, events terlewat). Jenis run yang mati karena crash tidak terlihat |
| menit supervisi; menit hilang = null dan 0 = data | `test_mixed_runs_report_values` (30, 0, null, 45,5; "0 is data, no data is null"); `test_no_supervision_file_gives_nulls` |
| tidak ada run `DONE`; tidak ada biaya diketahui | `test_runs_without_any_done_run`; `test_success_rate_rounding_and_unknown_costs` |
| hanya run tanpa hasil | `test_only_runs_without_result` |
| tanpa argumen; bukan direktori run | `test_no_run_directory_given[...]`; `test_not_a_run_directory[missing, plain_file, no_events]` |
| berkas supervisi tidak valid; tidak ada | `test_bad_supervision_file[...]`: 10 bentuk, termasuk `missing_file`, `infinity`, `null_value`, `unknown_run_id` |
| (tidak ada di draf manusia) | stdout persis `json.dumps`, run id non-ASCII tidak di-escape |

Kesan (Claude, bukan cek otomatis): cakupannya setara atau lebih luas dari draf manusia. Kebenaran nilai yang diharapkan
belum diperiksa baris demi baris.

## Status pilot

**Gagal** (kriteria 2): berhenti. Dua run, $0,38. Pilihan berikutnya ada di PR ini.
