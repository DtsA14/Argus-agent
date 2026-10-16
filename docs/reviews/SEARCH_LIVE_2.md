# Seri live #2 (umpan balik attempt berikutnya berbasis verdict): hasil

Seri yang disetujui dijalankan 2026-10-16 di VM, persis sesuai `SEARCH_LIVE_2_PREFLIGHT.md`:
- agen `86cadf4` (main; kodenya identik dengan `8b96f7b`), urutan dan kondisi sama dengan baseline #1;
- 30.000 token per attempt, `max_iterations` 3, cap $0.50 per run.

**9 dari 9 run berjalan. Tidak ada `BLOCKED`, `FAILED_BUDGET`, maupun anomali harness. Total $0.8949** (baseline
$1.0044). Bukti ada di `verification/search-live-2/<urutan>_<run>/`, sama seperti seri #1, ditambah
`feedback_attempt2.txt`, yaitu umpan balik yang benar-benar diterima attempt ke-2.

## Integritas

- **Audit prompt: 96 dari 96 panggilan cocok.** Prompt attempt ke-2 dibangun ulang dengan umpan balik bentuk baru, dan
  `prompt_hash` setiap panggilan cocok dengan ledger. Baseline #1 tetap 109/109 dengan audit yang sama.
- Prompt attempt pertama identik dengan baseline (hash dipatok di tes), dan audit yang cocok mengonfirmasinya.
- **b3** berakhir `output_truncated` di attempt pertama. Sisa reservasi hanya memberi output 642 token, sementara agen
  menulis ulang `prepare.py` utuh. Balasan yang terpotong tidak dijalankan, sesuai desain. Itu bukan anomali; bentuknya
  sama dengan masalah budget.
- Skrip audit sempat berhenti di balasan terpotong itu. Itu bug skrip, bukan harness, dan sudah diperbaiki di PR ini.

## Metrik utama

| | Baseline #1 | Seri #2 |
|---|---|---|
| **Tingkat sukses task** (DONE, lolos validasi independen dan klaim cocok dengan bukti) | 0/9 | **4/9** |
| **Biaya per task sukses** (biaya total dibagi sukses) | N/A (0 sukses; total $1.0044) | **$0.2237** (total $0.8949) |
| **Tingkat kegagalan jujur** | 9/9 | **5/5** |
| Klaim palsu baru | — | **0** |

**Per kondisi** (eksploratif, n = 3):
- A: 1/3 sukses, $0.3069 per sukses;
- B: 0/3, N/A;
- C: 3/3, $0.0825 per sukses.

Keempat DONE (c2, a2, c3, c1) divalidasi ulang secara independen: regresi 8/8, target 5/5. Klaimnya `file_changed`
`src/steps/prepare.py`, `tests_pass`, dan `issue_fixed`, semuanya didukung bukti. Perbaikannya di akar masalah
(`merge_options(base, plan)`).

## Apa yang terjadi di attempt ke-2

| Run | Setelah attempt 1 (verdict) | Attempt 2 | Hasil |
|---|---|---|---|
| c2 | target lulus, `SUMMARY.json` hilang | `ListFiles`, baca `prepare.py` → `Finish` (2 panggilan, 5.609 token) | DONE |
| a2 | sama | baca `prepare.py`, `options.py` → `Finish` (3 panggilan) | DONE |
| c3 | sama | jalankan `unit` dan `target` sendiri, baca `prepare.py` → `Finish` (2 panggilan) | DONE |
| c1 | sama | baca `prepare.py`, `options.py`, validasi → `Finish` (4 panggilan) | DONE |
| a1, a3, b1, b2, b3 | target gagal, tidak ada perubahan | diagnosis dari awal, kehabisan reservasi lagi | `FAILED_ACCEPTANCE`, tanpa klaim |

- **Setiap run yang memperbaiki bug di attempt pertama selesai di attempt kedua: 4/4.** Di baseline, angkanya 0/6.
  Agen memakai bukti itu, dan sebagian memeriksa ulang sendiri sebelum `Finish`. Ia tidak mendiagnosis ulang.
- **Run yang belum memperbaiki apa pun tidak terbantu: 0/5.** Umpan baliknya jujur ("target fail, files changed:
  none"), jadi tidak ada pekerjaan yang bisa dilanjutkan.
- Jumlah run yang memperbaiki di attempt pertama turun dari 6/9 ke 4/9. Prompt attempt pertama identik, jadi ini
  variasi model, bukan efek perubahan. Karena itu ukuran yang paling bersih untuk mekanisme ini adalah konversi
  "diperbaiki di attempt 1 → DONE": 0/6 menjadi 4/4.

## Kekurangan yang ditemukan

**Umpan balik salah menyebut tes ber-`subTest` sebagai "did not run".**
- Parser hasil unittest mencatat status `''` untuk `test_every_schedule_matches_the_account_page`, yang gagal lewat
  `subTest`.
- `feedback_from` menampilkan status kosong itu sebagai "did not run", padahal tesnya jalan dan gagal.
- Ini hanya muncul di run yang targetnya gagal, dan tidak memengaruhi acceptance (verdict tetap gagal). Tapi itu fakta
  yang keliru dalam umpan balik.
- Perbaikannya kecil: status kosong ditampilkan apa adanya. Perbaikan itu belum dikerjakan di sini.

## Jawaban untuk pertanyaan M3

**Apakah umpan balik berbasis verdict meningkatkan tingkat sukses tanpa merusak kejujuran atau menaikkan biaya secara
tidak perlu?**
- **Ya, untuk masalah yang ditargetkannya.** Sukses naik dari 0/9 ke 4/9. Setiap pekerjaan tervalidasi diselesaikan
  (4/4). Tidak ada klaim palsu. Biaya total turun, dan biaya per task sukses $0.22.
- **Tidak untuk sisanya.** Lima dari sembilan run tidak sempat memperbaiki bug dalam satu attempt 30.000 token. Untuk
  mereka mekanisme ini tidak berpengaruh, dan itu sesuai desain.
- Pengikat berikutnya adalah **diagnosis dan perbaikan dalam satu attempt** pada repo sebesar ini. Termasuk di dalamnya
  b3, yang kehabisan output saat menulis ulang file.

**Observasi, bukan kesimpulan** (search sudah dihentikan): di kedua seri, run yang memperbaiki bug di attempt pertama
adalah C 6/6, A 2/6, dan B 2/6. Kondisi tanpa search konsisten lebih baik, tapi n kecil dan eksperimennya tidak
dirancang untuk pertanyaan ini.
