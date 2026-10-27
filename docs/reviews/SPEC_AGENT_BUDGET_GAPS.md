# Spec: tiga celah dari SWE batch 3 (max_steps tanpa menulis, output drafter, profil yang dilihat drafter)

Status: **spec, belum dikoding.** 2026-10-27. Dari `pilots/swe_v0/batch3/RESULT.md` bagian "Yang dipelajari" 2–4; Atha: "spek satu
PR kecil buat celah 1-3". **Keputusan yang diminta: bagian 5.**

## 1. Masalah

1. **`max_steps` tanpa menulis tidak diberi petunjuk.** `21379`: empat attempt (dua tahap) tidak menulis satu berkas pun; dua
   berakhir `max_steps` (12 langkah, hampir semua `search_files`). Feedback #188 hanya untuk `context_limit`, #200 hanya untuk
   `output_truncated`; attempt berikutnya hanya tahu "max_steps after 12 steps; it changed no file".
2. **Output drafter.** `21612` `d1`: `NO_DRAFT output_truncated`, reasoning memakai 16.384 dari 16.384 (`roles.drafter.max_output_tokens`).
   #200 hanya menaikkan output agen (`code_task`).
3. **Profil yang dilihat drafter memakai angka mentah.** `drafter_policy.profile_info` = `code_task.profiles` apa adanya, jadi
   drafter diberi tahu `large_usd` = input 40.000 dan output 8.192, padahal coder DeepSeek mendapat 60.000 (#188) dan 32.000 (#200).
   Angka itu **juga dipakai** `rewrite_problems`: tanpa `edit_file`, berkas writable yang lebih besar dari output satu panggilan
   ditolak. Dengan 8.192, draf yang sebenarnya bisa dikerjakan (berkas sampai ±32.000 token) ikut ditolak.

## 2. Usulan

### 2.1 Petunjuk setelah `max_steps` tanpa menulis

Seperti #188/#200, di `_context_hint` (attempt berikutnya dan carry retry), **hanya** bila `end` = `max_steps` dan `wrote` = false:

```
It used all of its steps without changing any file: it kept searching and reading. Make a first change early (within a few
steps) with EditFile on the most likely place, run the validations, and refine from their output; the workspace is kept between
attempts.
```

(Di carry, tanpa kalimat terakhir.) Attempt yang menulis lalu habis langkah tidak diberi petunjuk ini.

### 2.2 `max_output_tokens` drafter per model

`drafter.max_output_tokens_by_model: {"deepseek:deepseek-flash": 32000, "deepseek:deepseek-v4-pro": 32000}`. Bila model role
drafter ada di daftar, angka itu menggantikan `roles.<drafter>.max_output_tokens` untuk run drafter. Drafter selalu memakai
reservasi USD (`attempt_usd` 0,70), jadi aturan #200 berlaku: `max_tokens` setiap panggilan = min(batas ini, yang muat di sisa
reservasi), dan panggilan ditolak bila yang muat di bawah output minimum. Biaya terburuk per panggilan: $0,0384 output (peak). Angka
efektif dicatat di `drafter_policy`.

### 2.3 Profil yang dilihat drafter = profil efektif untuk model coder

`profile_info` dihitung dengan `codetask.run.apply_profile` untuk model coder yang dikonfigurasi (jadi memakai
`max_input_tokens_by_model` dan `max_output_tokens_by_model`), bukan dari `code_task.profiles` mentah. `rewrite_problems` dan teks
prompt drafter memakai angka efektif itu. `profile_info` dibekukan di policy drafter saat setup seperti sekarang, jadi run lama yang
di-resume tidak berubah.

## 3. Yang tidak berubah

Jalur uang (reservasi per panggilan, cap attempt, cap job), perkiraan token, aturan stagnan, Sonnet dan model lain yang tidak ada di
daftar, profil berbasis token, petunjuk #188/#200.

## 4. Tes (gagal di kode lama; mutan)

1. Attempt yang berakhir `max_steps` tanpa menulis → prompt berikutnya (dan carry) memuat petunjuk 2.1; yang menulis lalu `max_steps`
   tidak; `context_limit`/`output_truncated` tetap petunjuknya sendiri; feedback lama tanpa `stopped` tetap sama persis; `audit_run`
   merekonstruksinya.
2. Drafter DeepSeek mendapat output 32.000 (tercatat di `drafter_policy`), Sonnet tetap 16.384; panggilan drafter yang tidak muat di
   reservasi diturunkan `max_tokens`-nya (kasus terburuk ≤ reservasi).
3. `profile_info` untuk coder DeepSeek: `large_usd` input 60.000, output 32.000; untuk Sonnet: 40.000 / 8.192; `rewrite_problems`
   menerima berkas ±20.000 token tanpa `edit_file` untuk DeepSeek dan menolaknya untuk Sonnet.

Mutan untuk setiap butir, semua tes non-sandbox, lalu `verify.sh` di latar belakang.

## 5. Keputusan

| | Pertanyaan | Usul |
|---|---|---|
| K1 | Petunjuk `max_steps` | Hanya bila tanpa menulis; isi: tulis lebih awal dengan `EditFile`, validasi, lalu perbaiki |
| K2 | Output drafter DeepSeek | 32.000 (sama dengan agen #200) |
| K3 | `profile_info` | Angka efektif untuk model coder yang dikonfigurasi, juga untuk `rewrite_problems` |
