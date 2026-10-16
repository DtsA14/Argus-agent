# Penutupan M3: apa yang terbukti, apa yang belum, dan analisis lima kegagalan

2026-10-17.

## 1. Pertanyaan dan jawabannya

**Pertanyaan M3:** apakah harness memastikan pekerjaan agen yang benar dan tervalidasi tidak hilang di garis akhir?

**Jawaban:** ya, untuk mekanisme yang diuji. Bukti utama ada di dua seri live pada fixture `ledger` (A/B/C × 3, 30.000
token per attempt, `max_iterations` 3, $0.50 per run). Kedua seri identik kecuali umpan balik attempt ke-2.

| Metrik | Seri #1 (baseline, PR #58) | Seri #2 (umpan balik berbasis verdict, PR #62) |
|---|---|---|
| Tingkat sukses task (DONE + validasi independen + klaim cocok bukti) | 0/9 | **4/9** |
| Biaya per task sukses | N/A (total $1.0044) | **$0.2237** (total $0.8949) |
| Tingkat kegagalan jujur | 9/9 | **5/5** |
| Klaim palsu | 0 | **0** |
| Perbaikan di attempt 1 → DONE | 0/6 | **4/4** |

## 2. Yang terbukti

- **Umpan balik berbasis verdict** (PR #60) membuat setiap run yang sudah memperbaiki bug di attempt pertama selesai
  di attempt kedua.
  - Konversinya 4/4, dengan 2–4 panggilan dan tanpa diagnosis ulang.
  - Kejujuran tidak turun: tidak ada klaim palsu, dan acceptance tetap menjalankan semuanya ulang.
- **Integritas alat ukur:**
  - setiap `prompt_hash` di kedua seri cocok dengan prompt efektifnya (109/109 dan 96/96);
  - prompt attempt pertama identik antarseri;
  - tidak ada `BLOCKED`, `FAILED_BUDGET`, maupun anomali harness;
  - setiap DONE divalidasi ulang secara independen.
- **Completion reserve versi naif akan merugikan.** Di baseline, ia akan memblokir panggilan yang menulis fix di
  keenam run (`DESIGN_FINISH_STEP.md`).

## 3. Yang belum terbukti, dan batas generalisasi

- **4/9 adalah kemajuan pada satu fixture, bukan tingkat sukses Argus secara umum.** Satu task, satu model, n = 9. Untuk
  mengukur kemampuan agen secara umum, kita butuh beberapa task dengan karakteristik berbeda.
- **Nilai tambah `search_files` belum terbukti.**
  - Selisih tokennya sekitar 2% di seri #1, dan search tidak mengubah sukses.
  - Eksperimen search dihentikan untuk fixture ini.
  - Observasi saja: run yang memperbaiki bug di attempt pertama adalah C (tanpa search) 6/6, A dan B masing-masing 2/6.
- **Lima kegagalan seri #2 tidak tersentuh** oleh mekanisme ini, sesuai desain. Analisisnya di bagian 4.
- **Kekurangan yang ditemukan dan diperbaiki di penutupan ini:** umpan balik menyebut tes ber-`subTest` yang gagal
  (status parser `''`) sebagai "did not run".
  - Sekarang ditampilkan "not ok (no single status in the unittest output)".
  - Acceptance tidak berubah: status itu memang tetap gagal.

## 4. Analisis lima kegagalan seri #2 (dari log yang ada, tanpa biaya)

Sumbernya ledger, memo (termasuk teks model sendiri), dan audit per panggilan. Ada 5 run dengan 2 attempt masing-masing,
jadi 10 attempt.

**Apakah agen salah arah? Tidak.**
- Di **10 dari 10 attempt**, agen membaca file dengan bug (`src/steps/prepare.py`) dan kontrak fungsinya
  (`src/common/options.py`).
- Tidak ada perbaikan di tempat yang salah dan tidak ada tambalan dangkal.

**Apakah agen kehabisan budget saat sudah dekat? Ya. Ia sudah menemukan akar masalahnya, lalu kehabisan budget pada
panggilan untuk menulis fix.**

| Run | Attempt 1: teks model sendiri | Panggilan berikutnya | Kurang |
|---|---|---|---|
| b1 | "Merge order is swapped; check merge_options." | ditolak: butuh 7.285 + 64, sisa 7.005 | **344** |
| b2 | "Merge order is swapped. Check merge_options and the pipeline config." | ditolak: butuh 7.515 + 64, sisa 6.885 | **694** |
| a1 | (tanpa teks; sudah membaca `prepare.py` dan `options.py`) | ditolak: butuh 9.312 + 64, sisa 8.782 | **594** |
| a3 | "Merge order is swapped in prepare.py. Check merge_options." | ditolak: butuh 8.634 + 64, sisa 1.514 | 7.184 (satu langkah baca ekstra) |
| b3 | "Arguments are swapped in prepare.py." | `WriteFile` dikirim, tapi output hanya boleh 642 token sementara file utuh lebih panjang → terpotong, tidak dijalankan | — |

- **Attempt kedua tidak membantu.** Umpan baliknya jujur: target gagal dan tidak ada file berubah. Hasil diagnosis
  agen sendiri ("merge order swapped in prepare.py") tidak terbawa, karena itu teks model, bukan bukti harness.
- Agen mendiagnosis ulang dari nol, menempuh jalur yang sama, dan kehabisan budget di titik yang sama (kurang
  2.000–6.700 token).

**Apakah agen banyak membaca file tidak relevan? Sebagian.**
- Per attempt dibaca 7–15 file. Dari itu, 2–8 ada di jalur bug, dan 4–7 di luar jalur.
- Yang di luar jalur, `accounts.py`, `terms.py`, dan `query.py`, adalah jalur halaman akun yang benar. Membacanya wajar
  untuk membandingkan pemakaian `merge_options`.
- Yang benar-benar umpan (`apply.py`, `compat.py`, `intake.py`, `output.py`, `fee_a/b.py`) 1–4 per attempt.
- Karena dibaca 3–5 file per langkah, setiap file ikut dikirim ulang di semua panggilan berikutnya.

**Kesimpulan analisis (fakta):**
- Kelima kegagalan terikat budget **pada langkah menulis**, setelah diagnosis yang benar.
- Penyebabnya bukan strategi diagnosis yang salah arah, dan bukan karena agen tidak bisa menemukan akar masalah.
- Di tiga run kekurangannya hanya 344–694 token.

**Implikasi (hipotesis, belum diuji):**
- Eksperimen budget 30k vs 45k kini **didukung bukti**. Kemungkinan besar sebagian besar dari kelima run ini akan
  selesai.
- Tapi itu membeli sukses dengan token, dan tidak menjelaskan apakah biayanya sepadan.
- Tuas yang lebih mendasar adalah **biaya kirim ulang konteks**. Setiap panggilan mengirim ulang semua file yang sudah
  dibaca, dan itu yang membuat attempt habis tepat sebelum menulis.
- Tool edit yang lebih kecil hanya akan membantu b3. Di run lain yang tidak muat adalah input panggilan, bukan
  outputnya.

## 5. Kandidat milestone berikutnya (untuk diputuskan)

1. **Eksperimen budget** pada seri yang sama: 30k vs 45k, satu variabel. Sekarang didukung bukti, dan biayanya kecil
   (maksimum $4.50 per seri). Ini menjawab berapa harga sukses dalam token.
2. **Desain efisiensi konteks.** Misalnya isi file lama tidak dikirim ulang utuh setelah dibaca. Ini perubahan
   harness besar, perlu desain sendiri, dan menyentuh jaminan memo dan step key.
3. **Memperluas eval** ke beberapa task dengan karakteristik berbeda sebelum mengklaim tingkat sukses umum.
