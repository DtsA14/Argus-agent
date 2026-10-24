# Spec: jatah output agen untuk model thinking, dan feedback setelah balasan terpotong

Status: **spec, belum dikoding.** 2026-10-24. Dari pilot SWE v0 batch 2 (`pilots/swe_v0/batch2/`, `sympy__sympy-24443`); Atha: "Ok
perbaiki sesuai saran lu". **Keputusan yang diminta: bagian 5.**

## 1. Masalah

Job `j20261024_181455_d71c`, tahap `a1`, profil `large_usd` (`max_output_tokens` 8.192), DeepSeek V4.1 Flash thinking. Di kedua
attempt, langkah 3 berakhir `output_truncated`: thinking memakai 7.858 dan 8.192 dari 8.192 token output, sehingga balasan terpotong
(`stop_reason: length`) **sebelum satu pun panggilan tool**. `edit_file` sudah ada di kontrak, tapi tidak pernah sempat dipanggil.
Attempt 2 tidak diberi tahu kenapa attempt 1 berhenti dengan cara yang bisa dipakai: petunjuk #188 hanya untuk `context_limit`.
Hasilnya stagnan, `FAILED_ACCEPTANCE`, $0,0207.

Pelajaran yang sama sudah tercatat untuk Sonnet ("thinking eats output"). Batas 8.192 dipilih untuk Sonnet tanpa thinking (kalibrasi
2026-10-14: median output 1.216, p95 3.419).

## 2. Usulan

### 2.1 `max_output_tokens` per model, hanya untuk profil USD

`code_task.max_output_tokens_by_model: {"deepseek:deepseek-flash": 32000, "deepseek:deepseek-v4-pro": 32000}`. Bila model coder ada di
daftar **dan** profil memakai `attempt_usd` (profil USD, sekarang `large_usd`), angka model menggantikan `max_output_tokens` profil.
Profil berbasis token (`default`, `large`) **tidak** berubah: di sana reservasi attempt dihitung dari token, dan output 32.000 bisa
melebihi `attempt_tokens` profil itu sendiri. Angka efektif tercatat di `budget_profile` run seperti sekarang.

- **Biaya terburuk per panggilan:** 32.000 × $0,60 × 2 (peak) / 1M = **$0,0384** output, ditambah input (≤ 60.000 × $0,15 × 2 / 1M =
  $0,018). Setiap panggilan tetap ditolak sebelum dikirim bila kasus terburuknya tidak muat di sisa reservasi attempt ($0,45), jadi
  cap uang tidak berubah; yang berubah hanya ruang satu balasan.
- Sonnet tetap 8.192 (harganya $15/M output; 32.000 output = $0,48, lebih dari satu attempt).

### 2.2 Feedback setelah `output_truncated`

Mengikuti pola petunjuk konteks #188: bila attempt sebelumnya (atau tahap sebelumnya, lewat carry) berakhir `output_truncated`,
prompt attempt berikutnya mendapat, setelah baris "How the previous attempt ended", satu petunjuk:

```
Its last reply was cut at the output limit before any of its tool calls ran: the reasoning used the whole reply budget. Keep each
reply short: make the change in small steps with EditFile (one function or a few lines per call) instead of writing a whole file,
and run the validations after each step.
```

- Ditampilkan untuk `output_truncated`, baik attempt itu sudah menulis atau belum. Petunjuk `context_limit` tidak berubah.
- Dalam carry (retry), kalimat yang sama dipakai, tanpa "the workspace is kept".
- Feedback tanpa `stopped`, atau dengan `end` lain, menghasilkan prompt yang sama seperti sekarang.
- `audit_run.py` membangun ulang prompt ini lewat `task_prompt` yang sama (tidak ada perubahan di audit).

## 3. Yang tidak berubah

Jalur uang (reservasi per panggilan, cap attempt, cap job), perkiraan token, aturan stagnan, drafter (`max_output_tokens` 16.384 di
role-nya), profil berbasis token, dan Sonnet.

## 4. Tes (gagal di kode lama; mutan)

1. DeepSeek dengan `large_usd` mendapat 32.000; dengan `large` (token) tetap 8.192; Sonnet dengan `large_usd` tetap 8.192; angka
   efektif tercatat di `budget_profile`; nilai di `config.yaml`.
2. Panggilan dengan output 32.000 yang kasus terburuknya tidak muat di sisa reservasi tetap ditolak sebelum dikirim (tes reservasi
   yang ada, dengan angka baru).
3. Attempt yang berakhir `output_truncated` membuat prompt attempt berikutnya memuat petunjuk itu; juga untuk carry di retry;
   tidak untuk `finished` atau `context_limit`; feedback lama tanpa `stopped` tetap sama persis.
4. `audit_run.py` merekonstruksi prompt dengan petunjuk itu tanpa mismatch.

Mutan untuk setiap butir, semua tes non-sandbox, lalu `verify.sh` di latar belakang. Sesudahnya: `argus retry` job
`j20261024_181455_d71c` (tahap `a2`, carry dari `a1`), setelah "y".

## 5. Keputusan

| | Pertanyaan | Usul |
|---|---|---|
| K1 | Angka DeepSeek | 32.000 untuk flash dan v4-pro, hanya profil USD |
| K2 | Kapan petunjuk muncul | Setiap `output_truncated` (menulis atau tidak), di attempt berikutnya dan di carry |
| K3 | Isi petunjuk | Balasan pendek, `EditFile` bertahap, validasi tiap langkah; tidak menyebut angka token |
