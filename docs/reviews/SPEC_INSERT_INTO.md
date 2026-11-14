# Spec INSERT-INTO: tests the drafter adds go into an existing test class (not a new class at the end of the file)

Status: **dibangun; review Opus atas spec (GO WITH FIXES, B1 sampai B5) dan atas kode (penyerang, GO WITH FIXES, dua blocker) sudah diterapkan; merge hanya bila `verify_at` hijau dan Claude tidak ragu (Atha 2026-11-14: "kalau udah yakin, setelah verify lulus langsung merge juga gpp")** (alur baku strict-lane, Atha 2026-11-14: merge menunggu kata "merge"). Ditulis Claude.
Dasar: `pilots/outside_v2/batch3/APPEND_READ.md` (pembacaan buta Opus), `APPEND_MEASUREMENT.md`, dan `SPEC_DRAFTER_STYLE.md` (ditarik; bagian 4 mencatat bahwa hanya `insert_into` yang dapat memperbaiki penempatan).

## 0. Masalah (terukur)

APPEND-TESTS (#506) memindahkan tes draf ke berkas lama (8 dari 8 isu batch 3, dasar 0 dari 8), tetapi **selalu di akhir berkas dan selalu sebagai kelas TestCase baru** (8 dari 8 blok menulis tepat satu kelas baru; pembaca buta: 7 dari 8 draf bernilai B dengan alasan "kelas baru alih-alih memperluas `SplitBeforeTest`, `NumericRangeTests`, `InterleaveEvenlyTests`, `ValueChainTests`..."). Maintainer menaruh tes baru **di kelas yang menguji fungsi yang sama** (6 dari 8 blok maintainer bernilai A). `append` hanya menambah di akhir berkas (`acceptance/changed.py:from_append`), jadi prompt tidak dapat memperbaikinya (SPEC_DRAFTER_STYLE bagian 4).

Dasar pengukuran penempatan: dari 8 draf batch 3 yang diulang, **0 dari 8 menaruh tesnya di kelas yang sudah ada**.

## 1. Rancangan

Sebuah entri `changed_tests` dari drafter boleh membawa **`into_class`** bersama `append`: `{path, append, into_class: "SplitBeforeTest"}`. Harness menyisipkan blok **di akhir badan kelas itu** (sesudah pernyataan terakhirnya) dan menyimpan hasilnya sebagai `content` seperti biasa (draf hanya berisi `content`, sehingga sha sama lewat rute mana pun, aturan APPEND-TESTS tetap).

Aturan (semuanya diperiksa harness, bukan prompt; direvisi sesudah review Opus 2026-11-14, B1 sampai B5):
1. `into_class` hanya dengan `append` (bukan `content`, tanpa `removed`/`modified`). Nama = **kelas tingkat atas** yang **terikat tepat sekali** di modul: tidak ada `ClassDef`/`def`/penugasan/`del`/impor lain dengan nama itu di mana pun (termasuk di dalam `if`, `try`, `for`, atau `A = deco(A)` sesudahnya), tanpa dekorator kelas, bukan bersarang atau bernama bertitik. Tidak ada, ganda, atau berdekorator berarti ditolak dengan pesan.
2. **Daftar putih isi blok (B2):** sesudah `textwrap.dedent`, blok hanya boleh berisi **`def test*` atau `async def test*`**, tanpa dekorator, dengan nilai bawaan argumen hanya konstanta. **Tidak** ada penugasan tingkat kelas, pembantu non-tes, nama dunder, `setUp`/`tearDown`/`setUpClass`/`tearDownClass`/`run`/`__init__`, `import`, kelas, atau kode tingkat atas. Impor yang dibutuhkan harus sudah ada di berkas (bila tidak, append biasa di akhir berkas, seperti sekarang). Alasan: sebuah nama TestCase atau pembantu di dalam kelas mengubah cara **semua tes lama kelas itu** berjalan.
3. **Nama (B2):** tak satu pun nama metode blok boleh sudah ada di kelas itu, **atau sudah dikoleksi dari intake sebagai `path::Kelas::nama`** (itu menangkap tes warisan dari mixin: `PeekableTests(PeekableMixinTests, TestCase)` akan menimpa tes warisan tanpa mengubah id node), dan tak boleh ganda di dalam blok.
4. **Penyisipan (B3, B5):** blok di-dedent lalu diberi indentasi badan kelas (indentasi pernyataan pertama badannya; **spasi saja**; tab, `\r`, `\f`, `\v` dan kelas satu baris ditolak; garis dipisah dengan `split("\n")`, bukan `splitlines()`), satu baris kosong sebelum metode pertama, tepat sesudah baris terakhir kelas (`end_lineno` kelas). **Hasil diverifikasi dengan AST**: `ast.dump` pernyataan yang disisipkan di hasil harus sama dengan `ast.dump` blok yang di-dedent (indentasi ulang mengubah nilai string tiga-kutip dan sambungan `\`; yang berubah nilainya ditolak).
5. **Predikat penyisipan struktural (B1, B4)**, bukan "satu `i` mana pun": `insertion(old, new)` mem-parse keduanya; AST modul baru harus sama dengan yang lama **kecuali** tepat satu kelas tingkat atas yang badannya bertambah pernyataan di akhir (atau modul bertambah pernyataan di akhir: append lama), dan teks hasil harus sama dengan teks lama ditambah tepat baris-baris pernyataan itu (satu baris kosong di depan). Semua pemeriksaan APPEND-TESTS yang bergantung pada `pure_addition` memakai predikat ini: `added_bytes` (`len(new)-len(old)` untuk sisipan), `redefined_problems` (untuk sisipan: nama metode, bukan nama tingkat atas; wilayah sisipan yang berindentasi tidak di-parse sendiri), aturan K1 (`acceptance/draft.py:355`), `_adds_a_test`, `_appended` dan `review_text` (`codetask/drafter.py:1003`, `:1025`, `:1049`), batas 50.000 byte untuk wilayah tambahan dan 1 MiB untuk berkas, dan `new_tests` kosong bila ada sisipan yang menambah tes. Daftar putih butir 2 dan 3 berlaku untuk pernyataan yang disisipkan **apa pun rutenya** (`append` atau `content`).
6. **Menutup lubang APPEND-TESTS yang sudah ada** (ditemukan Opus; sisipan tidak boleh memperlebarnya): `redefined_problems` untuk append di akhir berkas juga menghitung **nama yang diimpor** intake (sebuah `def split_before` menimpa fungsi yang diimpor untuk tes lama) dan menolak **penugasan ke atribut atau subskrip di tingkat atas** (`SplitBeforeTest.test_a = ...`, `TestCase.assertEqual = ...`, `mod.f = fake`).
7. Kunci `__main__`: sisipan ke kelas yang berakhir **sebelum** `if __name__ == "__main__"` diizinkan (kelasnya harus berakhir sebelum guard); aturan APPEND-TESTS atas append di akhir berkas ber-`__main__` tetap.
8. Satu entri per berkas (batas lama); isu yang butuh tes di dua kelas memakai satu kelas.
9. Id node wajib `path::Kelas::test_x` (sah di `NODE`).

Perubahan prompt drafter: deskripsi `ChangedTest.into_class` dan satu kalimat pada aturan append ("bila berkas punya kelas tes untuk fungsi yang dibahas isu, beri namanya di `into_class` dan tulis hanya metodenya; bila tidak ada kelas yang cocok, append biasa"). Pemeriksaan harness di atas yang menegakkan, prompt hanya mengarahkan.

Tampilan untuk manusia: `review_text` dan `_appended` menampilkan metode yang disisipkan sebagai tes baru ("disisipkan ke kelas X"), bukan berkas yang berubah.

## 2. Verifikasi

- **Tes** (`tests/test_insert_into.py`): tiap aturan 1 sampai 8 dengan kasus lolos dan gagal; kelas di tengah berkas dengan kelas lain sesudahnya; kelas terakhir dengan blok `__main__` sesudahnya; komentar di antara kelas; dekorator di kelas; docstring-only class; kelas dengan metode berbaris tab; ekuivalensi sha (sisipan dan rute `content` penuh menghasilkan draf yang sama); hasil selalu bisa di-parse dan semua tes lama tetap ada (perbandingan AST bagian yang tak disentuh).
- **Tes sandbox nyata** (modul sendiri dengan teks "SANDBOX NOT AVAILABLE"): pytest dan `python -m unittest` pada berkas yang disisipi menemukan dan menjalankan metode baru di kelas yang ada; node id berbentuk `path::Kelas::test_x`.
- **Mutan** (`verification/insert_into_mutants.py`): tiap aturan dilemahkan satu per satu; semua harus terbunuh.
- Review Opus atas spec ini dan atas kodenya; satu `verify_at` penuh pada commit akhir (pra-cek dulu: `bash scripts/precheck.sh`). **Tidak di-merge sampai Atha bilang "merge".**
- **Efek pada perilaku diukur terpisah sesudahnya** (draf-saja, 8 isu batch 3, sekitar $0,08, butuh persetujuan uang Atha): berapa dari 8 draf menyisipkan ke kelas yang sudah ada (dasar 0), draf yang diterima harness tetap 8 dari 8, tanpa kenaikan putaran revisi, dan pembacaan buta ulang bila hasilnya menarik.

### 2.1 Tes tambahan dari review

Tiap lubang yang ditemukan Opus mendapat tes dan mutan: tes warisan dari mixin ditimpa, `run`/`setUp`/`cls`, sisipan berbasis `content` tepat setelah impor (menyamar sebagai penambahan), nilai string yang berubah karena indentasi ulang, daerah rakus awalan/akhiran (`test_a2` sebelum `test_c`), `\f` dan `\x85`, kelas terakhir di berkas, kelas dengan `A = deco(A)` sesudahnya, kelas berdekorator, berkas tanpa baris akhir, impor yang tertimpa oleh append, dan penugasan atribut tingkat atas. Tes sandbox nyata memakai kelas mixin. Perkiraan ukuran dari Opus: 250 sampai 320 baris kode (`acceptance/changed.py` 180 sampai 220, `draft.py` sekitar 10, `drafter.py` 40 sampai 60) dan 450 sampai 600 baris tes.

## 3. Sengaja tidak dikerjakan

- Pembantu non-tes, penugasan tingkat kelas, dekorator, dan `setUp` dalam blok sisipan (daftar putih butir 2).
- Menyisipkan di antara metode (mis. dekat tes terkait) atau mengubah metode yang ada; hanya akhir badan kelas.
- Kelas bersarang atau bernama bertitik, beberapa kelas per berkas, fungsi tingkat atas yang disisipkan sebelum fungsi tertentu (repositori pytest murni tetap memakai append di akhir).
- Aturan gaya (`try/except`, `subTest`): ditarik di SPEC_DRAFTER_STYLE.
- Impor baru lewat penyisipan.

## 4. Batas yang diketahui

Penyisipan ke kelas dasar menambah tesnya ke setiap subkelas; node tambahan itu tidak wajib sehingga baseline menolak drafnya (aman, pesannya membingungkan). Tes baru kini jalan sebelum kelas sesudahnya (urutan pytest) atau di antara metode lama (unittest mengurutkan nama), sehingga keadaan global yang diubahnya bisa mencapai tes lama; daftar putih tidak menutup itu.

Satu repositori (more-itertools: tes `unittest`) menjadi dasar; repositori pytest dengan kelas `Test*` tercakup, tetapi tidak diukur. Model bisa memilih kelas yang salah (harness hanya memastikan kelas itu ada, bukan bahwa ia yang paling tepat). Penyisipan di akhir kelas belum "dekat tes terkait" (nilai A maintainer mungkin juga menuntut itu). Berkas dengan beberapa definisi kelas bernama sama ditolak.

## 5. Hasil review penyerang atas kode (Opus, 2026-11-14) dan perubahannya

Dua blocker nyata, keduanya diperbaiki dengan tes dan mutan:
1. **Anotasi dieksekusi saat kelas dibuat** (`def test_new(self) -> locals().__setitem__("test_a", ...)` membuat tes lama no-op, lolos K1 karena AST fungsi lama sama). **Aturan 2 ditambah: tanpa anotasi sama sekali** (argumen, `*args`, `**kwargs`, kembalian) **dan tanpa parameter tipe**.
2. **Lubang append lama yang aturan 6 klaim tutup tetapi tidak**: `from operator import eq as check`, `if True: def check`, `try: def check`, `(check := ...)`, `for check in`, `with ... as check`, `except ... as check`, `del check`, `match ... case check`, dekorator `@(check := ...)`. Aturan 6 sekarang menghitung **setiap nama yang dikaitkan modul tambahan di lingkup modul** (tidak masuk badan fungsi, lambda, kelas, atau variabel komprehensi; `:=` di komprehensi mengikat di modul) dan memotongnya dengan nama intake; impor ulang yang **sama** (sumber sama) boleh; `from x import *` ditolak.

Should-fix yang diterapkan: peringatan K3 "changes module-level code" tidak lagi muncul untuk sisipan ke kelas yang namanya bukan `Test*` (semua kelas more-itertools); nama yang diikat di badan kelas di bawah `if`/`for`/`try`/`with` dan **nama dari kelas dasar di berkas yang sama** (rekursif, aman dari siklus) ikut dianggap ada (termasuk atribut non-tes seperti `testing = False`); `\r`, `\x0b`, `\x0c` ditolak juga pada rute `content` bila ada sisipan kelas.

Yang **tidak** ditutup (dicatat, bukan bug): aturan 6 adalah **pemeriksaan nama, bukan sandbox**: kode tingkat atas di append yang memanggil sesuatu (`setattr(SomeTests, "test_x", ...)`, `globals().update(...)`, dekorator ber-efek-samping, `BarTests.x = ...` di dalam badan kelas baru) tidak terlihat; sebuah berkas `new_tests` dapat melakukan hal yang sama dengan mengimpor modulnya, jadi ini tidak melemahkan apa yang sudah ada. `async def test_*` di TestCase unittest tidak pernah jalan dan selalu lolos (aman hanya karena baseline menolak tes wajib yang lolos). Sisipan yang bentuknya tidak persis (satu baris kosong sebelum blok) jatuh ke rute `content` umum, tanpa daftar putih, seperti sebelum cabang ini (berkas di bawah 50 KB, diff penuh, `new_tests` wajib). Penyisipan menggeser nomor baris kelas sesudahnya (hanya tes yang memeriksa sumbernya sendiri akan melihatnya).

**Tes lama yang dilonggarkan** (satu): `tests/test_append_tests.py::test_the_added_code_must_parse_on_its_own` menerima salah satu dari dua pesan ("does not parse on its own" atau "only `def test*` methods"): konten `OLD + "\n\n\n    indented = 1\n"` kini dibaca sebagai penyisipan `indented = 1` ke kelas `T` dan ditolak daftar putih, bukan oleh parse; draf tetap ditolak.

**Mutan:** 98 pola; 88 terbunuh, 10 ekuivalen terdokumentasi dengan alasan dan eksperimen (di `verification/insert_into_mutants.py`, `EQUIVALENT`): pertahanan berlapis yang menolak kasus yang sama, bukan tes yang kurang.

## 6. Bukti akhir (2026-11-14)

`verify_at` penuh pada commit kode `e7f0fc4`: **4336 lolos, 1 xfailed, 0 tes sandbox dilewati, `RESULT: PASS`**, 750 s (log `verification/verify-20261114T063421Z-aarch64.log`; dua grup sandbox: `sandbox_a` 595 s, `sandbox_b` 740 s). Tes baru: `tests/test_insert_into.py` (162), `tests/test_insert_into_sandbox.py` (3, di grup sandbox nyata). Mutan: 88 dari 88 yang dapat dibunuh terbunuh, 10 ekuivalen terdokumentasi.

**Belum terukur: perilaku model.** Tes membuktikan harness (apa yang diterima dan ditolak), bukan bahwa drafter memakai `into_class` dengan benar. Ukuran yang akan dipakai (draf-saja, 8 isu batch 3, sekitar $0,08, butuh persetujuan uang Atha): berapa dari 8 draf menyisipkan ke kelas yang sudah ada (dasar 0 dari 8), draf yang diterima tetap 8 dari 8, tidak ada kenaikan putaran revisi, kelas yang dipilih dibandingkan dengan kelas yang dipakai PR maintainer (delapan kasus diketahui). Mundur: satu `git revert` (field opsional; draf lama tidak berubah).
