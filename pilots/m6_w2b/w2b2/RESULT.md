# Pilot W2b-2: hasil

2026-10-23. Alur end-to-end: issue, drafter, approve (`--no-reference`), agen, paket review, lalu patch ke `main`.
Kriteria: `w2b2/PREFLIGHT.md` bagian 5 dan `w2b2/PREFLIGHT_AGENT.md`.

## Ringkasan

| | |
|---|---|
| Status | **Agen `DONE`**, paket review **valid**, patch diterapkan ke `main` **tanpa perubahan** (commit `83a75d5`). `verify.sh`: lihat bagian terakhir |
| Task | `pr_title2`: judul `PR.md` dipotong di batas kata. Issue ditulis Claude atas permintaan Atha; **tes dan kontrak ditulis drafter**; **tanpa patch referensi** |
| Biaya | drafter $0,4651 (3 run) + agen $0,0778 = **$0,5429** |
| Agen | 2 attempt, 4 panggilan model. Attempt 0: baca `review.py`, satu `EditFile`, `RunValidation`; validasi otomatis lulus; panggilan berikutnya ditolak sebelum dikirim (`reservation_exhausted`, profil `default` 30.000 token); verdict gagal hanya karena `SUMMARY.json`/klaim belum ada. Attempt 1: baca tes, `Finish`; verdict lulus |

Jalan agen persis seperti ekspektasi preflight ("bila attempt pertama berakhir `reservation_exhausted` setelah edit,
attempt kedua tinggal `Finish`").

## Patch agen (`live/w2b2a1/review/changes.patch`)

9 baris di `render_pr`: baris pertama issue di-`strip()`; ≤ 80 karakter dipakai apa adanya; selain itu 81 karakter
pertama dipotong di spasi terakhir lalu di-`rstrip`; bila kosong atau tanpa spasi, 80 karakter; lalu `...`. Sesuai
aturan issue. Ada satu `strip()` tambahan pada baris pertama (spasi di ujung baris pendek ikut hilang). Tidak
terlihat di keluaran karena `cell()` sudah merapikan spasi.

## Drafter (tiga run) dan perbaikan harness yang dipicunya

| Run | Hasil | Pelajaran → perbaikan |
|---|---|---|
| `w2b2d1` | `DRAFTED`, disetujui sebagai `pr_title`, **mustahil** dikerjakan (tanpa `edit_file`; berkas 30 KB > output 4.096) | `tools` untuk drafter + cek tulis ulang deterministik (PR #157) |
| `w2b2d2` | `NO_DRAFT` (submit habis) | batas sandbox di prompt, petunjuk untuk tes yang sudah lulus, 5 submit (PR #158) |
| `w2b2d3` | `DRAFTED` di submit ke-5 | – |

Masalah yang masih terbuka: drafter tetap mencoba regresi `tests/test_review.py` (butuh `git`) di `w2b2d3`, walau prompt
sudah menyebut batas sandbox. Satu submit terbuang.

## Supervisi (ukuran ringan)

- **Titik keputusan Atha** (W2b-2, dari pemilihan task sampai merge patch): pilihan task, siapa penulis issue,
  pertanyaan W2a-ext, merge persiapan, go live ×3 drafter, approve ×2, "gas" untuk tools, "gas 1+2+3", merge ×3, go live
  agen, dan merge patch (menunggu). Total **±17**, ditambah 4 kali mengetik kunci. Banyak di antaranya akibat dua
  kegagalan drafter, yang menjadi perbaikan harness.
- **Waktu terminal:** drafter 0:55, 1:25, 1:26; agen 0:36.
- **Menit Atha:** belum ditanya.

## verify.sh setelah patch diterapkan

**PASS** di `2b0e9f8` (patch agen `83a75d5` di atas `main` `b4ba73e`): 1.392 tes lulus, 0 sandbox di-skip
(`verification/verify-20261022T181625Z-aarch64.log`). Termasuk tes lama paket review (`tests/test_review.py`), yang tidak
bisa jalan di sandbox. Setelah merge: **`agent-completed` tanpa patch referensi manusia**, yang pertama di Argus.
