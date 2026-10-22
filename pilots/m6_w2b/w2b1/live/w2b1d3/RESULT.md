# Pilot W2b-1, run `w2b1d3`: hasil

2026-10-22. Drafter dengan ReviseDraft dan penyebutan tes yang gagal di luar `must_pass`; attempt $0,70, input
64.000, output 16.384, cap $0,75 (PREFLIGHT bagian 7). Argus `c3fcb85` (checkout bersih), Sonnet 5.5.

## Ringkasan

| | |
|---|---|
| Status | **`DRAFTED`** dalam **2 submit** (1 SubmitDraft ditolak, 1 ReviseDraft diterima): **berhasil** menurut kriteria 1 |
| Panggilan model | 8, 0 ditolak; langkah 7 dari 16 |
| Biaya | **$0,2911** (`usd_complete` true); cache read 157.589, write 41.873, penghematan ±$0,278. W2b-1 total (3 run): **$0,6688** |
| Salinan intake | tidak berubah (`source_unchanged` true) |
| Waktu terminal | gerbang lolos 16:44:48Z, kunci 16:44:55Z, selesai 16:47:04Z (**2 menit 16 detik**) |

## Jalur

| Langkah | Masukan | Keluaran (thinking) | USD | Apa |
|---|---|---|---|---|
| s0 | 3.980 | 134 (0) | 0,0113 | ListFiles, baca `evals/runlog.py`, SearchFiles `def cost_is_known` |
| s1 | 12.471 | 172 (0) | 0,0234 | baca `evals/score.py`, `fixtures/audit/pilot3a4/result.json`, `scripts/audit_run.py` |
| s2 | 19.746 | 274 (59) | 0,0222 | baca `scripts/run_series.py`, `tests/test_run_series.py`, `conftest.py`, `AGENTS.md` |
| s3 | 28.487 | 227 (171) | 0,0261 | SearchFiles `def parse_lines` |
| s4 | 28.920 | 54 (0) | 0,0045 | baca `harness/events.py` |
| s5 | 29.792 | 3.967 (3.890) | 0,0447 | SearchFiles `scripts` (hampir seluruhnya thinking) |
| s6 | 34.209 | 6.511 (79) | 0,0791 | **SubmitDraft**: ditolak |
| s7 | 41.875 | 5.726 (211) | 0,0798 | **ReviseDraft** (`validation`, `new_tests`): **diterima** |

Submit 1 ditolak dengan satu masalah: validasi `regression` memuat `tests/test_eval.py`, yang gagal di baseline karena
membaca `verification/eval-live-1/...`, sedangkan `verification/` dikecualikan dari intake. Revisi membuang berkas itu
dari regresi. Revisi juga mengirim ulang `new_tests` (8.397 → 8.420 byte, perubahan kecil), padahal tidak wajib.
Penghematan dari ReviseDraft jadi lebih kecil dari yang mungkin, tetapi semuanya muat.

## Draf

- **Scope:** writable hanya `scripts/pilot_report.py`, sama dengan draf manusia. Protected: `tests/**`, `evals/**`,
  `harness/**`, `acceptance/**`, `codetask/**`, `fixtures/**`, tiga skrip yang dibaca, `AGENTS.md`, dan `config.yaml`.
  Tidak ada peringatan scope.
- **Validasi:** `target` = `tests/test_pilot_report.py`, 20 node wajib (manusia: 17). `regression` =
  `tests/test_eval_cost.py` dan `tests/test_run_series.py`, **tanpa node wajib** dan `min_tests: 1`. Validasi itu tetap
  harus lulus seluruhnya, tetapi batas jumlah tesnya longgar. Draf manusia memakai keempat berkas tes 3a dengan
  minimal 30 tes.
- **Tanpa `budget_profile`**, jadi agen akan mendapat profil `default` (30.000 token, output 4.096). Untuk task 3b, agen
  memakai `large_usd`. Draf tidak bisa diubah saat approve; kalau disetujui seperti ini, agen kemungkinan kehabisan
  anggaran. Drafter tidak punya panduan untuk memilih profil.
- **`unverifiable` (4):** pembacaan lewat `evals/runlog.py`, penjumlahan nano-dollar yang tak terbedakan di 6 desimal,
  "tidak ada yang lain berubah" (dijaga scope), dan nilai attempts/llm_calls untuk run NO_RESULT yang tidak
  ditentukan issue. Keempatnya catatan yang jujur dan relevan.

## Kualitas tes (pengukuran tambahan, di sandbox)

1. **Tes drafter terhadap `scripts/pilot_report.py` di `main`** (patch agen 3b yang sudah diterapkan dan diverifikasi):
   **20/20 lulus.** Nilai yang diharapkan konsisten dengan implementasi yang sudah diterima.
2. **20 mutan referensi 3b terhadap tes drafter** (`mutants_on_drafted_tests.log`): **19/20 tertangkap**. Tes manusia:
   20/20. Mutan yang lolos: *"`done` = status bukan FAILED_ACCEPTANCE"*. Tes drafter tidak punya run berstatus BLOCKED
   atau FAILED_BUDGET, jadi `done` yang terlalu longgar tidak terdeteksi. Draf manusia punya "tujuh jenis run".
3. **Tuntutan tambahan di luar issue:** tes drafter menjalankan skrip **tanpa `PYTHONPATH`**. Patch referensi manusia
   tidak lulus tanpa satu baris `sys.path` (pengukuran pertama: 0/20, dibuang). Patch agen 3b mengatur `sys.path`
   sendiri. Issue tidak menyebut cara menjalankan skrip. Ini pilihan yang wajar ("bisa dijalankan sebagai
   `python scripts/pilot_report.py`"), tetapi tetap tuntutan yang tidak tertulis di issue.

## Kriteria (PREFLIGHT bagian 4)

1. **Berhasil: terpenuhi.** `DRAFTED` dalam 2 submit (≤ 3), salinan tidak berubah, biaya $0,29 ≤ $0,70, dan
   `usd_complete` true.
3. **Dicatat:** di atas. Cakupan setara draf manusia, kecuali jenis run BLOCKED/FAILED_BUDGET. Ada tuntutan tambahan
   `PYTHONPATH`. Regresi lebih sempit dan longgar, dan tidak ada profil budget.
4. **Bukan bagian pilot ini:** approve dan menjalankan agen. Bila diteruskan, profil `default` menjadi risiko utama.

## Supervisi (ukuran ringan)

- **Titik keputusan Atha untuk W2b-1:** merge preflight, go live `w2b1d1`, pilihan A, merge, go live `w2b1d2`,
  "1+2+revisedraft", dan "merge langsung go live" (w2b1d3). Total **7**, ditambah tiga kali mengetik kunci.
- **Waktu terminal:** 1:23, 1:51, dan 2:16 (per run).
- **Menit Atha:** `unknown` (belum ditanya).
