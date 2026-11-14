# Spec MAX-SUBMITS: the drafter may submit 7 times, and the job status says how many it used

Status: **review Opus: GO WITH FIXES (diterapkan); dibangun; tidak di-merge sampai Atha bilang "merge"** (alur baku strict-lane). Atha 2026-11-14: "Ok langkah 1". Ditulis Claude.
Dasar: `pilots/outside_v2/batch3/SUBMITS_ANALYSIS.md`, `docs/reviews/SPEC_DROP_OLD_REQUIRED.md` bagian 5.

## 0. Masalah (terukur)

Sejak APPEND-TESTS (#506) drafter memakai **4 sampai 5 submit per isu (total 37 untuk 8 isu; sebelumnya 20)**; **11 dari 16 draf memakai kelima-limanya, jadi kebutuhan sebenarnya terpotong di batas, bukan "4 sampai 5"**, dengan batas `drafter.max_submits: 5` (`config.yaml:151`). Satu draf dari sembilan berakhir `DRAFT_FAILED` (`submits_exhausted`, #1247) dan run ulangnya lolos persis di submit kelima. Batas itu kini penentu, bukan pengaman. Jumlah submit yang dipakai tidak tampil di ringkasan job: ia baru ketahuan karena dihitung dari log.

## 1. Perubahan

1. `config.yaml` `drafter.max_submits: 5` menjadi **7**. Tidak ada perubahan lain pada kebijakan drafter. **Batas uang tidak berubah**: tiap percobaan drafter tetap dibatasi `attempt_usd` (0,70) dan stage cap (0,75), jadi submit tambahan tidak dapat menaikkan biaya di atas batas itu; yang berubah hanya berapa banyak penolakan yang boleh dilalui sebelum `submits_exhausted`. Satu submit tambahan menghabiskan sekitar $0,002 sampai $0,005 (data pengukuran).
2. `router/job.py` `status()` mencetak **satu baris per tahap draf**: `  d1 submits: 4 of 7`, dibaca dari events run tahap itu (`draft_submitted` dihitung; batasnya dari event `drafter_policy`), seperti `_attempt_lines` dan `_estimate_lines` (hanya baca, tanpa kunci, berkas yang hilang atau rusak berarti tidak ada baris). Tahap non-draf tidak dicetak. Baris ini juga muncul di keluaran `argus code`, `argus approve` dan `argus status`.

**Perbaikan dari review:** (a) `tests/test_drafter.py:212` memeriksa teks "submit 1 of 5" dari config dan diubah memakai nilai config; (b) baris ringkasan menghitung **nomor submit yang berbeda**, bukan jumlah event, karena titik crash `drafter@after_tool` menulis `draft_submitted` sebelum memo sehingga resume menulis event ganda bernomor sama; submit yang ditolak (`draft_submit_refused`) tidak dihitung, jadi run yang habis menampilkan "7 of 7"; jangan memakai `drafting_end.submits` atau `result.json` (pada kehabisan keduanya menghitung submit yang ditolak, 8); tanpa event `drafter_policy` baris memuat jumlah saja; (c) submit ke-7 terjangkau karena loop berjalan `max_steps + max_submits` langkah (`codetask/drafter.py:821-827`); job yang di-resume tetap memakai kebijakan beku 5.

Tidak berubah: aturan K1, isi prompt, batas `max_steps`, `attempt_usd`, semua pemeriksaan draf, dan batas submit tahap lain (`planner`, `issue_writer`, dll).

## 2. Verifikasi

- **Tes** (`tests/test_submit_lines.py`): `load_config()["drafter"]["max_submits"] == 7`; `submit` ke-6 dan ke-7 diterima dan ke-8 ditolak dengan `draft_submit_refused` (limit 7), memakai kebijakan dari `config.yaml` bukan angka dalam tes; teks "of N" di pesan penolakan memakai N dari kebijakan; baris ringkasan: jumlah submit dan batas dari events, nol submit, tahap draf kedua (redraft) dihitung per tahap, events hilang atau rusak (tanpa baris, tanpa crash), tahap agen tidak dicetak, baris terakhir yang terpotong (multibyte) dibaca seperti `_attempt_lines`, dan baris itu muncul di `status()` sebuah job.
- **Mutan** (`verification/max_submits_mutants.py`): angka diubah, baris tidak dicetak, jumlah salah dihitung (`draft_submitted` ok=false saja, atau semua event), batas dibaca dari tempat yang salah.
- Satu review Opus atas spec dan atas kode; satu `verify_at` penuh.
- **Efek pada perilaku**: tidak diukur oleh tes. Yang diharapkan dari pengukuran draf-saja berikutnya (butuh persetujuan uang Atha): #1247 tidak lagi mentok; jumlah submit per isu tetap 4 sampai 5 (batas tidak mengubah berapa yang dibutuhkan, hanya apa yang terjadi di tepi).

## 3. Sengaja tidak dikerjakan

Normalisasi `must_pass` (P4) dan penyusunan ulang validasi (P5): spec terpisah bila dipilih (`SPEC_DROP_OLD_REQUIRED.md` bagian 5). Menaikkan batas tahap lain. Peringatan otomatis bila submit mendekati batas.

## 4. Batas yang diketahui

Batas 7 menutupi gejala, bukan penyebabnya (K1 dan jebakan berikutnya tetap membuat drafter butuh 4 sampai 5 submit). Tujuh dipilih karena data menunjukkan 5 sebagai maksimum yang dipakai dan satu draf yang mentok; ia bukan hasil optimasi. Dua kali lipat biaya per percobaan tidak terjadi (batas uang sama), tetapi waktu per draf yang gagal bertambah: satu submit biasanya 20 sampai 60 detik, **paling buruk `validation_timeout_s` (300 detik) per validasi**. Kebutuhan maksimum sebenarnya tidak diketahui (terpotong di 5); 7 dipilih karena batas uang tidak bergeser dan 8 juga akan dapat dibela.
