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


---

# Job 3 (DeepSeek V4.1 Flash, non-thinking): berhasil

2026-10-23. Job `j20261023_031205_d0f8`, issue yang sama, setelah PR #165 (perbaikan pilot ini, pindah ke DeepSeek), #166
(input drafter 200.000, pengingat langkah), #167 (batas dolar, hanya tool submit di 3 langkah terakhir), dan #169 (approve
tetap bisa setelah redraft gagal).

| Tahap | Hasil | Biaya |
|---|---|---|
| d1 | `NO_DRAFT context_limit`: membaca 13 file tanpa submit, input melewati 64.000 | $0,0160 |
| d2 | `NO_DRAFT reservation_exhausted`: membaca 12 file; batas token (input cache ikut dihitung) habis di $0,018 | $0,0184 |
| d3 | **`DRAFTED`**, 2 submit. `ReadFile` di langkah 13 ditolak (hanya tool submit); submit 1 ditolak (2 tes gagal tanpa diwajibkan, regresi butuh `git`); `ReviseDraft` diterima. Profil `large_usd`, `edit_file` + `search_files`, 8 tes wajib | $0,0216 |
| d4 | `redraft` dijalankan tidak sengaja (riwayat terminal): `NO_DRAFT max_steps`. Job jadi `DRAFT_FAILED`, dan draf d3 tidak bisa di-approve. Celah ini ditutup PR #169 | $0,0143 |
| a1 | Approve d3 (sha `79fa37fd71ba`, cap agen $0,75). Agen **`DONE`** di attempt kedua: attempt 0 mengedit dan memvalidasi lalu habis langkah (`max_steps`); attempt 1 memperbaiki sisa tes lalu `Finish`. Paket review **valid** | **$0,0090** |
| **Job** | **`REVIEW_READY`** | **$0,0792** dari cap $1,00 |

**Patch agen** (`job3/review/changes.patch`): `list_jobs` dan `_job_line` di `router/job.py`, subperintah `list` di
`scripts/argus.py`, tes yang disetujui. **Agen juga mengubah `spent_nano`** (biaya job, dipakai untuk cap job) supaya
menjumlahkan folder run milik job yang tidak tercatat di `job.json`. Tes drafter menuntut itu (job `jb` tanpa tahap
tercatat). Efeknya hanya bisa **menambah** biaya yang terhitung (lebih ketat), dan tidak berubah untuk job buatan router
(tahap selalu dicatat sebelum run dibuat). Penyimpangan kecil ini dari issue ("dihitung sama seperti `status`") sudah
disebut ke Atha sebelum approve.

**Keputusan Atha untuk job ini:** `code`, `redraft` ×3 (satu tidak sengaja), dan `approve`. Masing-masing dengan `[y/N]`
dan kunci. Ditambah lima PR perbaikan di tengahnya. Router-nya sendiri hanya butuh 2 perintah bila drafter lolos sejak
awal. Yang menambah keputusan adalah perilaku drafter DeepSeek non-thinking, bukan router.

**Status:** patch diterapkan ke branch `router-p1-apply` tanpa perubahan; `verify.sh` **lulus** (1.443 tes, 0 sandbox di-skip; `verification/verify-20261023T060627Z-aarch64.log`). Setelah merge,
pilot #1 menjadi **`agent-completed`**, dengan biaya model **$0,08** (pilot #1 dengan Sonnet: $0,65 dan gagal).
