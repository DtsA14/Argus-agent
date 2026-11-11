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
(`**/*.{test,spec}.?(c|m)[jt]s?(x)`, di luar direktori `exclude` bawaannya) tetapi tidak cocok dengan `VITEST_FILE` (mis. `*.spec.jsx`, `*.test.mjs`), draf vitest
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
Python tidak berubah. Dua baris prompt vitest lama yang bertentangan dengan F1 diganti: "a test that needs [network] ... do
not use it in a validation" (K1: tidak ada lagi pengecualian) dan "when the issue changes behaviour that an existing test
checks, leave that file out of the validations". Penggantinya: tetap sebut berkas itu, dan mulai `unverifiable` dengan
`EXISTING TEST CONFLICT: <file>::<test>`; manusia mengubah tes itu lewat commit sebelum task bisa dikerjakan (drafter
tidak punya tool menyerah; tanpa penanda ini agen akan gagal di tes lama dan memakai biayanya).

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

Mutants (`verification/vitest_full_regression_mutants.py`): cek F1 dihapus; F1b dihapus; direktori yang dikecualikan vitest dihitung; hanya validasi pertama dihitung; tes baru dihitung
sebagai lama; berlaku juga untuk Python; prompt lama dikembalikan. Lalu review (`/code-review medium`), verify.sh, "merge".

F1a tidak di-mutasi: `check()` hanya menerima snapshot intake (tidak ada argumen repo), jadi working tree tidak terjangkau
dari cek ini; mutan "baca working tree" tidak bisa ditulis tanpa menambah argumen.

**Code review (medium, 2026-10-31), dipertahankan dengan alasan:** (a) berkas lama dengan `test.skip`/`todo` tidak pernah
lulus karena drafter memasang `max_skipped: 0`; (b) penanda `EXISTING TEST CONFLICT` hanya catatan, harness tidak
memblok approve; (c) nama berkas dengan titik di depan atau spasi ditolak F1b. Ketiganya fail closed sesuai K1 dan tidak ada
di `argus-viewer`; diperbaiki lewat commit manual bila muncul. Diperbaiki: batas 15 berkas per validasi di prompt, hint tes
network dikembalikan, direktori `exclude` bawaan vitest (`node_modules`, `dist`, `cypress`, `.git`, ...) bukan tes repo,
`VITEST_LIKE` di samping `VITEST_FILE`.

## 4. Biaya

Run tambahan per validasi: viewer seluruh suite ±3 detik. Drafter yang lupa satu berkas mendapat pesan F1 dan memakai satu submit
(dari 5).

## 5. Keputusan untuk Atha

- **K1.** Tanpa pengecualian: tes lama yang tidak bisa jalan di sandbox (mis. butuh network) membuat draf vitest selalu ditolak,
  diperbaiki lewat commit manual di repo. Usul: ya (viewer tidak punya tes seperti itu).
- **K2.** Python tidak ikut (sympy terlalu besar). Usul: ya. **Lanjutan (tidak sekarang):** suite `argus-ledger` kecil, cakupan
  Python untuk repo kecil dicatat di `PENDING.md`.
- **K3.** Draf lama yang belum di-approve diperiksa dengan aturan baru. Usul: ya (saat ini tidak ada).

## 6. Amandemen 1 (2026-11-11): harness menyebut sendiri berkas tes lama yang tidak disebut drafter

Status: **Atha 2026-11-11 "Ok setuju breakdown nya"** (PENDING 3a, bagian 3a-1).

**Masalah.** Job viewer judul (`j20261111_073447_cc5a` d1) NO_DRAFT: 5 submit habis untuk kesalahan formulir, yang
terakhir `ReviseDraft` dengan satu validasi saja (field `validation` mengganti seluruh daftar), sehingga 46 berkas tes lama
"is in no validation". Ketiga kali di viewer (030, 031). Drafter juga memakai langkah membaca node id tes lama untuk
`must_pass` yang tidak diperlukan F1 (berkas yang disebut sudah wajib hijau seluruhnya, F2).

**F5.** Untuk draf vitest, harness sendiri menambahkan ke kontrak validasi `old_tests_<n>` (n = 1, 2, ...; nomor
berikutnya yang belum dipakai id lain) untuk setiap berkas tes lama (definisi F1a, termasuk pengecualian direktori F1)
yang tidak disebut validasi mana pun dari drafter: paling banyak 15 berkas per validasi, urut path, `must_pass` kosong,
`min_tests` = jumlah berkasnya (setiap berkas `*.test.*` punya setidaknya satu tes; `max_skipped` 0 seperti validasi lain),
batas waktu dan environment dari policy. Draf dibangun dengan validasi itu **sebelum** dicek (`dr.check`), jadi laporan,
record, sha draf yang di-approve manusia, paket review dan run agen memakai kontrak yang sama; tidak ada yang diubah
sesudah check atau approve. Ini membalik "Tidak dikerjakan: harness menyuntikkan validasi suite" di §2: kekhawatiran itu
(kontrak dan sha berubah sesudah diikat) tidak terjadi karena penyuntikan terjadi saat draf dibuat.

**F5a.** F1 tetap ada sebagai jaring pengaman (draf buatan tangan / `argus draft` tanpa drafter tetap harus menyebut
semua berkas). F1b tidak berubah. Python tidak berubah (F4).

**F5b. Prompt.** Baris "Name every existing test file (*.test.*) in a validation: the harness refuses a draft that leaves
one out ..." diganti: drafter hanya menyebut validasi untuk tes baru dan tes lama yang dekat dengan perubahan; berkas tes
lama lain dijalankan harness dalam validasi `old_tests_*` miliknya, dan seluruh suite lama tetap wajib hijau. Baris
`EXISTING TEST CONFLICT` tetap. Ditambah: bila validasi `old_tests_*` gagal pada kode sekarang, sebut berkas yang gagal di
validasi drafter sendiri (berkas itu keluar dari `old_tests_*`) dan, bila tidak bisa lolos di sandbox, mulai `unverifiable`
dengan `EXISTING TEST CONFLICT`.

**Code review (2026-11-11).** Diperbaiki: id validasi yang bukan teks tidak lagi membuat submit crash (kontrak yang
menolaknya); prompt menjelaskan validasi `old_tests_*` yang gagal. Tidak diubah: daftar berkas dari
`fixtures/repos/<intake>` (sama dengan yang dipakai `check` untuk F1; intake dibekukan dan dicek `intake.check`);
berkas tes symlink (F1 sudah mewajibkannya sebelum amandemen ini, dan intake menolak symlink); hash ganda per submit
(repo viewer kecil).

**Tidak dikerjakan di 3a-1:** `ReviseDraft` per `id` (F5 sudah menutup kerugiannya: validasi yang hilang karena revisi
berarti berkasnya kembali ke `old_tests_*`; ganti per id juga membuat validasi dengan id salah tidak bisa dibuang). Perbaikan
formulir lain (id huruf kecil, tes baru otomatis protected, glob protected yang tidak cocok, petunjuk node id lengkap)
adalah 3a-2.

**Tes wajib (mutants).** Berkas yang tidak disebut masuk `old_tests_*`, yang disebut tidak; potong 15 dan urutan path;
nomor id melompati id drafter yang sama; `min_tests`, `must_pass` kosong, policy; tes baru dan direktori yang dikecualikan
tidak masuk; draf Python tanpa validasi tambahan; draf yang dibangun = draf yang dicek dan di-record (sha); revisi dengan
satu validasi tetap lolos F1; prompt.
