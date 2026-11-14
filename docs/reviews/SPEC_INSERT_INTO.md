# Spec INSERT-INTO: tests the drafter adds go into an existing test class (not a new class at the end of the file)

Status: **draf spec, minta review Opus; bila GO, dibangun segera, TANPA merge** (alur baku strict-lane, Atha 2026-11-14: merge menunggu kata "merge"). Ditulis Claude.
Dasar: `pilots/outside_v2/batch3/APPEND_READ.md` (pembacaan buta Opus), `APPEND_MEASUREMENT.md`, dan `SPEC_DRAFTER_STYLE.md` (ditarik; bagian 4 mencatat bahwa hanya `insert_into` yang dapat memperbaiki penempatan).

## 0. Masalah (terukur)

APPEND-TESTS (#506) memindahkan tes draf ke berkas lama (8 dari 8 isu batch 3, dasar 0 dari 8), tetapi **selalu di akhir berkas dan selalu sebagai kelas TestCase baru** (8 dari 8 blok menulis tepat satu kelas baru; pembaca buta: 7 dari 8 draf bernilai B dengan alasan "kelas baru alih-alih memperluas `SplitBeforeTest`, `NumericRangeTests`, `InterleaveEvenlyTests`, `ValueChainTests`..."). Maintainer menaruh tes baru **di kelas yang menguji fungsi yang sama** (6 dari 8 blok maintainer bernilai A). `append` hanya menambah di akhir berkas (`acceptance/changed.py:from_append`), jadi prompt tidak dapat memperbaikinya (SPEC_DRAFTER_STYLE bagian 4).

Dasar pengukuran penempatan: dari 8 draf batch 3 yang diulang, **0 dari 8 menaruh tesnya di kelas yang sudah ada**.

## 1. Rancangan

Sebuah entri `changed_tests` dari drafter boleh membawa **`into_class`** bersama `append`: `{path, append, into_class: "SplitBeforeTest"}`. Harness menyisipkan blok **di akhir badan kelas itu** (sesudah pernyataan terakhirnya) dan menyimpan hasilnya sebagai `content` seperti biasa (draf hanya berisi `content`, sehingga sha sama lewat rute mana pun, aturan APPEND-TESTS tetap).

Aturan (semuanya diperiksa harness, bukan prompt):
1. `into_class` hanya dengan `append` (bukan `content`, tanpa `removed`/`modified`). Nama = **kelas tingkat atas yang didefinisikan tepat sekali** di berkas (bukan bersarang, bukan di dalam `if`, bukan nama bertitik); tidak ada atau ganda berarti ditolak dengan pesan.
2. Blok, sesudah `textwrap.dedent`, hanya boleh memuat **fungsi/metode (`def`, `async def`, dengan dekorator) dan penugasan tingkat kelas**; **tanpa `import`, kelas, atau kode tingkat atas**. Impor yang dibutuhkan harus sudah ada di berkas (bila tidak, drafter memakai append biasa ke akhir berkas, seperti sekarang). Blok harus bisa di-parse sebagai badan kelas.
3. Penyisipan: blok di-dedent lalu diberi indentasi badan kelas (indentasi pernyataan pertama badannya; **spasi saja, tab ditolak**; kelas satu baris `class A: pass` ditolak; berkas dengan `\\r` ditolak), satu baris kosong sebelum metode pertama, tepat sesudah baris terakhir badan kelas (`end_lineno`); komentar dan baris kosong yang mengikuti kelas tetap sesudahnya.
4. **Tak satu pun nama yang didefinisikan blok boleh sudah ada di kelas itu** (metode dengan nama sama akan menimpa tes lama tanpa terlihat; analog `redefined_problems` untuk tingkat atas). Nama ganda di dalam blok ditolak.
5. **Hasil harus "penyisipan murni"**: `new == old[:i] + X + old[i:]` untuk satu `i` (diperiksa dari awalan dan akhiran bersama; `pure_addition` yang berbasis awalan, dipakai di `acceptance/draft.py:355` dan `codetask/drafter.py:1003`, digeneralisasi: append di akhir adalah kasus khusus). Setiap pemeriksaan APPEND-TESTS yang bergantung padanya berlaku sama: aturan K1 (node wajib bukan tes yang sudah dikoleksi; id berparameter dibandingkan lewat fungsinya), batas 50.000 byte untuk wilayah tambahan dan 1 MiB untuk seluruh berkas, `new_tests` boleh kosong bila ada penyisipan yang menambah tes, wilayah tambahan harus di-parse.
6. Kunci `__main__`: penyisipan ke dalam kelas yang berada **sebelum** blok `if __name__ == "__main__"` **diizinkan** (tes ikut jalan sebagai skrip); aturan APPEND-TESTS yang menolak append di akhir berkas ber-`__main__` tetap untuk append biasa. Tujuan: `new_tests` tidak lagi menjadi satu-satunya jalan untuk berkas ber-`__main__`.
7. Satu entri per berkas (batas lama); sebuah isu yang butuh tes di dua kelas tetap memakai satu kelas (batas yang dicatat, bukan dipecahkan).
8. Id node wajib `path::Kelas::test_x` (sudah sah di `NODE`).

Perubahan prompt drafter: deskripsi `ChangedTest.into_class` dan satu kalimat pada aturan append ("bila berkas punya kelas tes untuk fungsi yang dibahas isu, beri namanya di `into_class` dan tulis hanya metodenya; bila tidak ada kelas yang cocok, append biasa"). Pemeriksaan harness di atas yang menegakkan, prompt hanya mengarahkan.

Tampilan untuk manusia: `review_text` dan `_appended` menampilkan metode yang disisipkan sebagai tes baru ("disisipkan ke kelas X"), bukan berkas yang berubah.

## 2. Verifikasi

- **Tes** (`tests/test_insert_into.py`): tiap aturan 1 sampai 8 dengan kasus lolos dan gagal; kelas di tengah berkas dengan kelas lain sesudahnya; kelas terakhir dengan blok `__main__` sesudahnya; komentar di antara kelas; dekorator di kelas; docstring-only class; kelas dengan metode berbaris tab; ekuivalensi sha (sisipan dan rute `content` penuh menghasilkan draf yang sama); hasil selalu bisa di-parse dan semua tes lama tetap ada (perbandingan AST bagian yang tak disentuh).
- **Tes sandbox nyata** (modul sendiri dengan teks "SANDBOX NOT AVAILABLE"): pytest dan `python -m unittest` pada berkas yang disisipi menemukan dan menjalankan metode baru di kelas yang ada; node id berbentuk `path::Kelas::test_x`.
- **Mutan** (`verification/insert_into_mutants.py`): tiap aturan dilemahkan satu per satu; semua harus terbunuh.
- Review Opus atas spec ini dan atas kodenya; satu `verify_at` penuh pada commit akhir (pra-cek dulu: `bash scripts/precheck.sh`). **Tidak di-merge sampai Atha bilang "merge".**
- **Efek pada perilaku diukur terpisah sesudahnya** (draf-saja, 8 isu batch 3, sekitar $0,08, butuh persetujuan uang Atha): berapa dari 8 draf menyisipkan ke kelas yang sudah ada (dasar 0), draf yang diterima harness tetap 8 dari 8, tanpa kenaikan putaran revisi, dan pembacaan buta ulang bila hasilnya menarik.

## 3. Sengaja tidak dikerjakan

- Menyisipkan di antara metode (mis. dekat tes terkait) atau mengubah metode yang ada; hanya akhir badan kelas.
- Kelas bersarang atau bernama bertitik, beberapa kelas per berkas, fungsi tingkat atas yang disisipkan sebelum fungsi tertentu (repositori pytest murni tetap memakai append di akhir).
- Aturan gaya (`try/except`, `subTest`): ditarik di SPEC_DRAFTER_STYLE.
- Impor baru lewat penyisipan.

## 4. Batas yang diketahui

Satu repositori (more-itertools: tes `unittest`) menjadi dasar; repositori pytest dengan kelas `Test*` tercakup, tetapi tidak diukur. Model bisa memilih kelas yang salah (harness hanya memastikan kelas itu ada, bukan bahwa ia yang paling tepat). Penyisipan di akhir kelas belum "dekat tes terkait" (nilai A maintainer mungkin juga menuntut itu). Berkas dengan beberapa definisi kelas bernama sama ditolak.
