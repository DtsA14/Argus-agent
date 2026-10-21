# M6 pilot 3a: simulasi token tanpa biaya (hanya reader dan dua inspektor)

Status 2026-10-21. Tanpa panggilan model, tanpa biaya. Simulasi terkalibrasi (`scripts/measure_context.py`: token ≈ 407 + 0,3186 ×
karakter) yang menjalankan loop agen harness sungguhan dengan model terskrip. **Profil dan cap belum diputuskan.**

## Apa yang diubah dibanding simulasi gabungan

Simulasi gabungan menunjukkan bahwa berkas tes terlindungi (±18 KB, ±6k token, terkirim ulang di setiap langkah) adalah biaya
terbesar. Untuk 3a:

- Isi tes dipecah: `tests/test_run_inspectors.py` (8,6 KB: builder fixture dan tes) dan `tests/test_run_inspectors_data.py`
  (15 KB: keluaran emas, tanpa logika). Coder perlu membaca yang pertama saja; yang kedua dibaca hanya bila ia memilih melakukannya.
  (`approve_draft` hanya menerima berkas `test_*.py` dan menuntut tes wajib di tiap berkas, jadi data emas ada di modul tes kedua yang
  juga memuat dua tes kontrak reader.)
- Bacaan sumber yang diperlukan kecil: `audit_run.py` 4,6 KB, `failure_trace.py` 1,6 KB, `harness/events.py` 2,0 KB.
- Issue 1827 karakter (batas 2000).

## Hasil attempt pertama (token terpakai / status), penulisan seluruh berkas, tiga penulisan digabung dalam satu langkah

| Rencana | 30k | 45k | 60k |
|---|---|---|---|
| tanpa membaca tes: baca 3 skrip, tulis 3 berkas, validasi, Finish (4 langkah) | selesai, ±25k | selesai, ±25k | selesai, ±25k |
| membaca tes, jalur bersih (5 langkah) | ditolak di langkah 4 (±27k terpakai) | **selesai, ±38k** | selesai, ±38k |
| membaca tes, satu siklus perbaikan (7 langkah) | ditolak di langkah 4 | ditolak di langkah 5 (±40k) | ditolak di langkah 6 (±52k) |

Versi sebelum tes dipecah (tes 21,6 KB dibaca, tiap tulis di langkah terpisah): ditolak di langkah 3 pada 30k dan langkah 4 pada 45k.

Catatan metode: setiap langkah mengirim ulang seluruh riwayat, jadi biaya tumbuh kuadratik terhadap jumlah langkah. Simulasi menulis
seluruh berkas; agen nyata yang memakai `EditFile` untuk `audit_run.py` akan sedikit lebih murah. Agen yang membaca lebih banyak
(`evals/score.py`, `codetask/*`) lebih mahal. Penghitung memakai estimasi, bukan token sebenarnya.

## Aritmetika admission (attempt diterima bila terpakai + reservasi ≤ cap; cap = min(config $0,50, kontrak))

Biaya per attempt jalur bersih ±$0,10 (45k) atau ±$0,075 (25k).

| Profil / cap | Attempt yang bisa diterima |
|---|---|
| default 30k ($0,30) pada $0,50 | sampai 3 attempt; hanya jalur tanpa baca tes yang muat |
| large 45k ($0,45) pada $0,50 | **1 attempt**: tidak ada ruang untuk percobaan kedua |
| large 45k pada $0,75 | 2–3 attempt (setelah dua attempt ±$0,20, attempt ketiga masih muat) |
| large 45k pada $1,00 | 3+ attempt |

## Bacaan

- 3a muat di profil `large` pada jalur bersih bila agen membaca tes; satu siklus perbaikan tidak muat bahkan di 60k.
- Dengan `default` 30k, 3a hanya muat bila agen **tidak** membaca berkas tes, padahal issue mengarahkan agen ke kontrak yang diuji.
- Pilihan (bukan keputusan): `default` pada $0,50 (risiko: attempt ditolak sebelum selesai), atau `large` dengan cap lebih tinggi dari $0,50
  agar ada lebih dari satu attempt.

`large` 45k dan cap $1 **tidak** disetujui. Tidak ada coder yang dijalankan.
