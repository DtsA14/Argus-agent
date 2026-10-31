# Spek: draf vitest wajib menjalankan setiap berkas tes yang ada

Status: **keputusan Atha 2026-10-31: K1-K3 ya**, dua penegasan ditambahkan (F1a, F1b, G6, G7). Jalur ketat (cek draf = aturan penilaian). Satu PR kecil.
Tweak 3 dari shadow batch 1 (`PENDING.md`).

## 1. Masalah

Validasi regresi dipilih **drafter**. Prompt hanya meminta "keep a regression validation of existing tests when the change can
break them"; harness tidak memeriksa tes lama mana yang dijalankan. Bukti (shadow batch 1, job `j20261031_051827_0e27`): draf
menjalankan `src/App.test.jsx src/job-page.test.jsx` saja, tanpa `src/jobs-list.test.jsx`. Patch agen merusak satu tes di berkas
itu, semua validasi hijau, job REVIEW_READY. Hanya ketahuan karena Claude menjalankan seluruh suite dengan tangan. Draf job
sebelumnya (`097d`) memasukkan berkas itu; jadi ini bukan kebiasaan tetap drafter, melainkan pilihan yang bisa meleset.

Sesudah tweak 1-2 (`argus-viewer` 56b7e00) gagalnya tes lama adalah satu-satunya jalan cacat batch 1 yang belum tertangkap mesin.

## 2. Usul

**F1. Cek draf.** Untuk draf yang validasinya memakai runner vitest: setiap berkas di intake yang cocok dengan `VITEST_FILE`
(`*.test.js|jsx|ts|tsx`) harus disebut oleh setidaknya satu validasi vitest draf (boleh tersebar di beberapa validasi). Bila
tidak, draf ditolak di `static_problems` (`acceptance/draft.py`) dengan satu pesan per berkas: `existing test file
src/jobs-list.test.jsx is in no validation (a vitest draft runs every existing test file)`. Tidak ada daftar pengecualian
(fail closed, K1).

**F1a. Definisi "berkas tes lama".** Berkas `base_files` dari snapshot intake, yaitu tree **commit job** (`git show`/archive
saat `argus code`, sama dengan sumber `.argus/protected`), tidak pernah working tree; tes baru draf (`new_tests`) bukan berkas
lama. Polanya **`VITEST_FILE` yang sama** dengan aturan `new_tests` dan `validate_vitest` (`acceptance/validation.py`), tidak
dibaca dari `include` di `vite.config.*`. Harness selalu menjalankan vitest dengan daftar berkas yang disebut (`include` dari
argv, bukan dari config), jadi config repo tidak menentukan apa yang dijalankan.

**F1b. Tidak ada tes yang diam-diam tidak terhitung.** Bila intake berisi berkas yang cocok dengan `include` bawaan vitest
(`**/*.{test,spec}.?(c|m)[jt]s?(x)`) tetapi tidak cocok dengan `VITEST_FILE` (mis. `*.spec.jsx`, `*.test.mjs`), draf vitest
ditolak: `test file src/a.spec.jsx cannot be run by the harness (only *.test.js|jsx|ts|tsx)`. Fail closed seperti K1; diperbaiki
lewat commit manual (ganti nama). `argus-viewer` tidak punya berkas seperti itu.

**F2. Akibatnya tanpa kode tambahan.** Di baseline, validasi tanpa node baru harus lulus, dan validasi **merah** hanya boleh
gagal pada node baru yang wajib (`failures == len(new)`, tanpa error; `baseline_problems`): berkas lama yang hanya disebut di
validasi merah tetap harus hijau di baseline. Di reference (bila ada) dan run agen (`codetask`) setiap validasi harus lulus
(`judge_vitest`: exit 0 dan outcome OK, bukan hanya `must_pass`). Jadi F1 membuat seluruh suite lama wajib hijau di ketiga
titik itu. Paket review memakai kontrak
yang sama.

**F3. Prompt.** Baris prompt drafter vitest "Keep a regression validation ... when the change can break them" diganti
"Name every existing test file (`*.test.*`) in a validation: the harness refuses a draft that leaves one out". Prompt
Python tidak berubah.

**F4. Lingkup.** Hanya vitest. Python tidak berubah: suite sympy ribuan tes, tidak muat di batas waktu validasi
(K2). Job yang sudah ada tidak berubah: cek berjalan saat draf diperiksa; draf lama yang di-approve sesudah merge diperiksa
ulang seperti biasa dan bisa ditolak (K3).

**Tidak dikerjakan:** harness menyuntikkan validasi `suite` sendiri ke kontrak (mengubah kontrak dan sha yang diikat record,
lebih besar dari perlu); `changed_tests` untuk vitest; cakupan Python.

## 3. Jaminan dan tes (`tests/test_vitest_full_regression.py`, non-sandbox kecuali G5)

- **G1.** Draf vitest yang tidak menyebut satu berkas tes lama ditolak; pesan menyebut berkas itu. Gagal bila cek dihapus.
- **G2.** Draf yang menyebut semua berkas lama, tersebar di dua validasi, tidak ditolak oleh F1 (tidak ada tolak palsu).
- **G3.** Tes baru draf (`new_tests`) bukan "berkas lama": tidak memicu pesan F1 (sudah wajib punya node sendiri).
- **G4.** Draf Python dengan berkas `test_*.py` lama yang tidak disebut tidak ditolak oleh F1.
- **G5** (sandbox, `pwa_node22`). Ulangan bentuk `0e27` kecil: intake dengan dua berkas tes lama, draf yang hanya menyebut satu
  ditolak sebelum menjalankan apa pun; draf yang menyebut keduanya dengan reference patch yang merusak tes lama ditolak di
  reference green. Tes yang di-skip (Docker tidak ada) tidak dihitung lulus.
- **G6** (sandbox). Berkas tes lama yang **hanya** disebut di validasi merah (bersama tes baru) dan gagal di baseline membuat draf
  ditolak (baseline: hanya node baru yang boleh gagal). Mengunci F2 untuk kasus ini.
- **G7.** F1a/F1b: berkas lama diambil dari snapshot intake (berkas working tree yang tidak ada di commit tidak dihitung);
  `src/a.spec.jsx` atau `src/a.test.mjs` di intake membuat draf vitest ditolak dengan pesan F1b.
- Prompt: teks F3 ada di prompt vitest dan tidak di prompt Python.

Mutants (`verification/vitest_full_regression_mutants.py`): cek F1 dihapus; F1b dihapus; berkas lama dari working tree; hanya validasi pertama dihitung; tes baru dihitung
sebagai lama; berlaku juga untuk Python; prompt lama dikembalikan. Lalu review (`/code-review medium`), verify.sh, "merge".

## 4. Biaya

Run tambahan per validasi: viewer seluruh suite ±3 detik. Drafter yang lupa satu berkas mendapat pesan F1 dan memakai satu submit
(dari 5).

## 5. Keputusan untuk Atha

- **K1.** Tanpa pengecualian: tes lama yang tidak bisa jalan di sandbox (mis. butuh network) membuat draf vitest selalu ditolak,
  diperbaiki lewat commit manual di repo. Usul: ya (viewer tidak punya tes seperti itu).
- **K2.** Python tidak ikut (sympy terlalu besar). Usul: ya. **Lanjutan (tidak sekarang):** suite `argus-ledger` kecil, cakupan
  Python untuk repo kecil dicatat di `PENDING.md`.
- **K3.** Draf lama yang belum di-approve diperiksa dengan aturan baru. Usul: ya (saat ini tidak ada).
