# Pilot router v0 #1 (`argus list`): hasil

2026-10-23. Router v0 (`main` `9ceb6ca`), Sonnet 5.5 untuk drafter dan agen. Kriteria: `p1/PREFLIGHT.md` bagian 5.

## Ringkasan

| | |
|---|---|
| Status | **Gagal** (kriteria 3): agen `FAILED_ACCEPTANCE`, tidak ada patch |
| Job 2 (`j20261022_193531_259d`) | drafter `DRAFTED` di submit pertama ($0,1392), agen 2 attempt tanpa satu tulisan pun ($0,1221). Total **$0,2612** dari cap $1,00 |
| Job 1 (`j20261022_193403_3beb`) | terhenti di tengah drafter (langkah 6), tertinggal `DRAFTING`. Ledger: **$0,3937**, termasuk satu panggilan terputus yang dihitung kasus terburuk ($0,2773; tagihan sebenarnya bisa lebih kecil) |
| Total pilot | $0,6549 menurut ledger (kasus terburuk) |
| Keputusan Atha | `code` (y + kunci) dua kali karena job 1, lalu `approve` (y + kunci). Router sendiri: **2 perintah** untuk satu job |

## Apa yang terjadi

1. **Job 1:** router tidak mencetak apa pun selama drafter berjalan. Atha mengira macet ("udah masukin key dan enter
   tapi ga jalan"), proses berhenti di tengah panggilan model, lalu `code` dijalankan lagi sebagai job baru.
2. **Job 2, drafter:** draf kuat di submit pertama:
   - `edit_file` dan `search_files` ditambahkan;
   - 7 tes wajib membuat `job.json` sendiri (tanpa `git`), termasuk "`list` tidak mengubah apa pun, bahkan log yang
     terpotong";
   - drafter **menemukan bug di router**: `EventLog` menambah baris baru pada log yang terpotong, sehingga `status`
     tidak murni read-only.

   Profil yang dipilih: **`large`**.
3. **Job 2, agen:** cap $0,85 (Atha: `--max-usd 0.85`). Kedua attempt membaca `router/job.py` (23 KB),
   `scripts/argus.py`, dan tes, lalu panggilan ketiga **ditolak sebelum dikirim**. Reservasi `large` (45.000 token per
   attempt) habis karena setiap langkah mengirim ulang semua yang sudah dibaca. Setelah dua attempt dengan kegagalan
   yang sama, run dihentikan (`stagnant`).

## Temuan → perbaikan (PR berikutnya)

| Temuan | Perbaikan |
|---|---|
| Drafter memilih `large` (anggaran token habis untuk membaca) | `drafter.agent_profiles: [default, large_usd]`; prompt menjelaskan bahwa input dikirim ulang di setiap langkah, dan file > ±5 KB butuh profil USD |
| Router diam selama tahap berjalan; job ganda | Router mencetak "… running … do not start another job … `argus resume <job>`" dan baris selesai; Ctrl-C memberi tahu cara melanjutkan |
| `status` dan ledger job memakai `EventLog` (bisa menulis) | dibaca dengan `parse_lines`, murni read-only |
| Job yang ditinggal tidak bisa ditutup | `argus abandon <job> "alasan"` (memegang kunci, jadi tidak bisa menutup job yang tahapnya masih berjalan) |

Saldo Anthropic Atha habis setelah pilot ini. Drafter dan agen dipindah ke DeepSeek V4.1 Flash (non-thinking) di PR yang
sama.
