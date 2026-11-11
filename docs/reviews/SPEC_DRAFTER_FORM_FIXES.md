# Spek: harness memperbaiki kesalahan formulir draf sebelum memeriksanya (PENDING 3a-2)

Status: **Atha 2026-11-11 "Ok setuju breakdown nya", "3a-2 bro"**. Jalur ketat (drafter, kontrak).

## 1. Masalah

Job viewer judul: d1 (`j20261111_073447_cc5a-d1`) memakai 4 dari 5 submit, d2 (sesudah 3a-1, #429) 3 dari 5, untuk
kesalahan formulir yang tidak menyangkut tes sama sekali:

- `contract: validation[1]: id must be a lower-case name` (id dengan huruf besar atau `-`);
- `new test src/jobs-title.test.jsx must be protected and not writable` (tes baru lupa dimasukkan ke protected);
- `contract: protected glob 'src/**/*.test.jsx' matches no input file` (d1: delapan glob seperti `src/*.test.ts`);
- `existing test src/jobs-clear-search.test.jsx::empties the search box ... must pass on the baseline, is None` (nama
  tanpa awalan `describe`; untuk "did not run" harness sudah menyebut nama lengkapnya, `named_like`, di sini belum).

Ukuran: submit yang ditolak karena formulir per draf viewer (d1 4, d2 3); target 0 untuk keempat jenis ini.

## 2. Perubahan

Harness mengubah argumen submit **sebelum** draf dibangun dan dicek, menyimpan argumen yang sudah diubah sebagai dasar
`ReviseDraft` berikutnya, dan menyebut setiap perubahan di jawaban submit ("The harness changed your draft: ...") serta di
event `draft_normalized`. Draf yang dicek, di-record (sha) dan di-approve manusia adalah draf yang sudah diubah; tidak ada
yang berubah sesudah check.

**P1. Id validasi.** Id string yang tidak cocok `ID` (`^[a-z][a-z0-9_]{0,31}$`) diubah: huruf kecil, karakter selain
`[a-z0-9_]` jadi `_`, awalan `v_` bila tidak mulai dengan huruf, dipotong 32. Bila hasilnya sudah dipakai validasi lain,
id dibiarkan (kontrak menolaknya seperti sekarang). Id yang bukan string dibiarkan.

**P2. Tes baru protected.** Path tes baru (string) yang tidak cocok satu pun glob `scope.protected` ditambahkan ke
`protected`. Tes baru yang cocok glob `writable` tetap ditolak (agen tidak boleh bisa menulisnya; harness tidak
mempersempit writable).

**P3. Glob protected yang tidak melindungi apa pun.** Glob `scope.protected` yang tidak cocok dengan berkas input mana pun
(berkas intake ditambah tes baru, sama dengan `check_scope_against`) dibuang. Glob yang menamai direktori (cocok dengan
awalan berkas) tidak dibuang: pesan lama yang menyarankan `dir/**` tetap. Glob yang ditolak `check_glob` (absolut, `..`,
backslash, kosong) tidak dibuang. **Glob hanya dibuang bila setiap berkas tes lama (nama vitest `*.test.*` atau pytest
`test_*.py`, `*_test.py`, `conftest.py`) tetap terlindungi tanpa glob itu**, dan sisanya tidak kosong, dan berkas intake
terbaca: glob salah ketik yang dimaksudkan untuk tes lama (`test/**` untuk `tests/`) tetap ditolak kontrak, jadi drafter
melihat apa yang terlewat (code review 2026-11-11: membuangnya diam-diam akan meloloskan draf dengan tes lama tidak
terlindungi).

**P4. Nama tes lama.** Penolakan `existing test <id> must pass on the baseline, is None` menyebut nama lengkap tes yang
berjalan di berkas yang sama dan berakhir dengan judul itu (`named_like`, maks 3), seperti "did not run".

**P4** juga untuk tes baru yang "was not collected" karena namanya tanpa awalan `describe`. Jawaban "keep it" (draf yang
ditahan) juga menyebut perubahan.

**Code review (2026-11-11), tidak diubah:** hash snapshot intake per submit (repo kecil); `named_like` dihitung dua kali
(evidence dan alasan); perbaikan di akar (harness memberi id sendiri, tes baru selalu protected tanpa disebut) lebih besar,
dicatat bila aturan formulir baru muncul lagi.

**Tidak berubah:** writable, validasi, tes, isi lain; draf Python mendapat P1, P2, P3, P4 juga (aturan formulir sama);
versi alat SubmitDraft/ReviseDraft naik ke "5".

## 3. Tes wajib (mutants)

P1: huruf besar, `-`, angka di depan, terlalu panjang, bentrok dengan id lain dibiarkan, bukan string dibiarkan. P2:
ditambah hanya bila belum cocok; writable tetap ditolak. P3: glob tanpa berkas dibuang, glob tes baru dipertahankan, glob
direktori tidak dibuang. Argumen yang diubah menjadi dasar ReviseDraft; jawaban submit dan event menyebut perubahan; draf
yang dicek = draf yang diubah. P4: nama lengkap disebut. Versi alat.
