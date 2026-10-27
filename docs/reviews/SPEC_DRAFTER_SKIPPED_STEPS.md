# Spec: penolakan "tests skipped" menyebut node-nya, dan langkah drafter 16 → 24 (dari run ulang SWE `21379`, percobaan 2)

Status: **disetujui** (Atha 2026-10-27: "Ok gas bro dan Max_steps sekalian tambah aja", juga untuk batch berikutnya dari SWE-rebench).
Kode di PR yang sama; proses ketat: tes yang gagal di kode lama, mutan, `verify.sh` penuh, tanpa biaya model.

## 1. Masalah (job `j20261027_185915_f13b`, `d1` $0,0421 dan `d2` $0,0333, keduanya `NO_DRAFT max_steps`)

1. Kedua run drafter berhenti di masalah yang sama: `validation regression ...: 1 tests skipped, contract allows 0`. Pesan itu tidak
   menyebut **node mana** yang di-skip; `d2` mencari `XFAIL` di dua direktori untuk menebaknya, lalu langkahnya habis.
2. Drafter membaca ±13 langkah di sympy sebelum submit pertama; dengan `max_steps` 16 tersisa 3 langkah untuk 2–3 submit.

## 2. Usulan

1. **Node yang di-skip disebut** (`acceptance/validation.py`): evidence validasi memuat `skipped_nodes` (skipped, xfail, xpass; paling
   banyak 50), dan alasan `N tests skipped, contract allows M` diakhiri `: <node>, ...` (paling banyak 10, lalu `and K more`). Awalan
   pesan tetap. Berlaku untuk setiap validasi (cek draf, verdict agen, penilai yang memakai `judge_result`), tanpa mengubah keputusan.
2. **`drafter.max_steps` 16 → 24** (`config.yaml`). Batas uang tidak berubah: setiap panggilan tetap di dalam reservasi attempt
   ($0,70) dan cap tahap drafter ($0,75); catatan "steps left" dan langkah terakhir mengikuti angka baru. Policy dibekukan saat setup,
   jadi run drafter lama yang di-resume tetap 16.

## 3. Tes

1. Validasi dengan node skipped dan xfail: alasan menyebut keduanya, `skipped_nodes` di evidence, lebih dari 10 → `and K more`; tanpa
   skip alasan tidak berubah. Gagal di kode lama.
2. Config: `drafter.max_steps` 24; policy run drafter mencatat 24.
