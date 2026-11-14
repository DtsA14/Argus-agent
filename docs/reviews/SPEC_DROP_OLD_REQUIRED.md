# Spec DROP-OLD-REQUIRED: the harness drops old tests from `must_pass` of an appended file instead of refusing the draft

Status: **draf spec, minta review Opus; bila GO dibangun segera; merge hanya atas kata Atha atau bila `verify_at` hijau dan Claude yakin, sesuai alur baku strict-lane.** Ditulis Claude, 2026-11-14.
Dasar: `pilots/outside_v2/batch3/SUBMITS_ANALYSIS.md` (data dan batasnya), `docs/reviews/SPEC_DRAFTER_FORM_FIXES.md` (pola normalisasi yang diikuti), K1 di `docs/reviews/SPEC_APPEND_TESTS.md`.

## 0. Masalah (terukur)

Sejak APPEND-TESTS (#506) drafter butuh hampir dua kali lipat submit: **2 sampai 3 per isu (total 20) menjadi 4 sampai 5 (total 37; sesudah INSERT-INTO 38)**, dengan batas 5. Satu draf dari sembilan sudah berakhir `DRAFT_FAILED` (`submits_exhausted`, #1247) dan run ulangnya lolos persis di submit kelima. Penyebab terbanyak di percakapan drafter: K1, "required <node> is already a test of tests/test_more.py in the intake: an appended file adds new tests": **73 baris di putaran append dan 86 di putaran `into_class`**, alasan lain paling banyak 9. Pola: drafter mendaftarkan tes **lama** berkas itu (`NumericRangeTests::test_basic`, ...) di `must_pass` untuk melindunginya, K1 menolak, dan drafter menghabiskan submit untuk membenahi sesuatu yang tidak mengubah apa yang dijamin: tes lama itu tetap dijalankan oleh validasi yang menjalankan berkas utuh (aturan "changed test ... is run whole by a pytest validation").

## 1. Perubahan

Normalisasi P4 di `codetask/drafter.py` `normalize_args` (yang sudah mengoreksi id validasi, tes baru yang tidak dilindungi, dan glob proteksi yang tak cocok; perubahannya dilaporkan ke drafter sebagai "The harness changed your draft: ..." dan dicatat di `draft_normalized`):

1. Untuk setiap entri `changed_tests` **yang membawa `append`** (dengan atau tanpa `into_class`; entri `content` tidak tersentuh), baca teks intake berkas itu.
2. Hitung tes yang **sudah ada di intake secara statis**: fungsi `test*` tingkat modul (`test_x`), metode `test*` tiap kelas tingkat atas (`Kelas::test_x`) **ditambah yang diwarisi dari kelas dasar di berkas yang sama** (rekursif, aman dari siklus; memakai `_inherited_names`).
3. Dari `must_pass` **setiap validasi**, buang node yang path-nya sama dengan berkas itu dan yang fungsinya (`func_key`, tanpa `[param]`) ada di himpunan itu. Catatan per node untuk drafter: "`<node>` is an existing test of `<path>`: it is no longer required (an appended file requires only new tests; the old test still runs in the validation that runs the file whole)".
4. Tidak berubah: aturan K1 (`appended_required_problems`) **tetap menolak** node yang tidak terlihat secara statis tetapi dikoleksi sungguhan (tes berparameter yang namanya cocok sudah ditangkap lewat `func_key`; tes warisan dari berkas lain, tes yang dibuat dinamis); semua pemeriksaan APPEND-TESTS dan INSERT-INTO; aturan bahwa tes baru wajib merah lewat assertion; entri `content` (ekspektasi yang berubah tetap butuh `content` utuh).
5. `must_pass` yang menjadi kosong dibiarkan kosong (kunci opsional di kontrak, `acceptance/contract.py:38-40`); validasi yang menjalankan berkas utuh tetap ada karena `static_problems` menuntutnya.

Mengapa ini tidak melemahkan jaminan: (a) tes lama itu tidak pernah menjadi tes yang "berubah" (entri `append` tidak mengubah tes lama: `redefined_problems`, `insertion_problems` dan `function_problems` menegakkannya); (b) validasi yang menjalankan berkas utuh menuntut semuanya lolos (kecuali yang memang di-skip oleh intake), jadi tes lama yang gagal tetap menggagalkan draf; (c) `must_pass` hanya menaikkan tuntutan "node ini harus ada dan lolos"; membuangnya tidak membuat tes lama bisa hilang karena K1 (`lost_problems`) tetap memeriksa koleksi. Yang berubah hanya: draf tidak lagi ditolak karena sebuah daftar yang berlebihan.

Risiko yang dipikirkan: **(i)** drafter menulis nama tes lama padahal maksudnya tes barunya (salah ketik nama): node itu dibuang, lalu draf tidak punya tes baru yang wajib, dan `_adds_a_test` menolaknya dengan pesan "needs a required node that is a test the intake does not have", ditambah catatan normalisasi yang menyebutkan node mana yang dibuang. **(ii)** model belajar menulis daftar apa saja: tidak ada akibat jaminan (butir b). **(iii)** statis versus koleksi: sebuah node yang statis dianggap lama tetapi sebenarnya baru? Mustahil: sebuah nama yang sudah ada di intake tidak bisa didefinisikan baru oleh blok (daftar putih INSERT-INTO dan `redefined_problems`).

## 2. Verifikasi

- **Tes** (`tests/test_drop_old_required.py`): node lama berkas append dibuang dari tiap validasi dan dicatat; node baru tetap; node berkas lain tidak tersentuh; entri `content` tidak tersentuh; tes berparameter lama dibuang lewat `func_key`; warisan di berkas yang sama (dua tingkat) dibuang; warisan dari berkas lain **tidak** dibuang (K1 menolaknya); metode di bawah `if`/`for` di kelas; kelas bersarang tidak dihitung; `must_pass` kosong; berkas yang tidak ada atau tidak ter-parse: tidak ada perubahan dan tidak ada crash; args yang bukan dict atau `validation` bukan list: dibiarkan; urutan stabil dan input tidak diubah; `draft_normalized` memuat catatan; draf yang tadinya ditolak K1 kini lolos; draf yang hanya mewajibkan tes lama kini ditolak oleh `_adds_a_test` dengan catatan; ekuivalensi sha rute `append` dan `content` tetap (normalisasi memengaruhi args, bukan draf yang dibangun).
- **Mutan** (`verification/drop_old_required_mutants.py`): tiap kondisi dilemahkan satu per satu.
- **Tes sandbox nyata**: satu draf yang mendaftarkan tes lama di `must_pass` lolos `dr.check` sesudah normalisasi.
- Satu review Opus atas spec ini dan satu atas kodenya; satu `verify_at` penuh pada commit akhir.
- **Efek pada perilaku diukur terpisah** (draf-saja, 8 isu, sekitar $0,09, butuh persetujuan uang Atha): jumlah submit (dasar 38 untuk 8 isu dengan `into_class`, 37 dengan append saja, 20 sebelum), draf yang diterima (dasar 7 dari 8, lalu 8 dari 8 dengan run ulang), dan baris penolakan K1 (dasar 86). Mundur: satu revert (hanya normalisasi args).

## 3. Sengaja tidak dikerjakan

- Menaikkan batas submit (5): itu menutupi gejala dan menaikkan biaya; dicatat sebagai alternatif bila normalisasi tidak cukup.
- Mengubah K1 atau memperlonggarnya untuk entri `content`.
- Petunjuk lewat prompt saja (prompt sudah berkata "wajibkan hanya tes baru", model tetap melanggar).
- Alasan penolakan lain di data (validasi lebih dari 16 argumen, tes baru yang tidak merah, berkas tidak dijalankan utuh): bukan bagian ini.

## 4. Batas yang diketahui

Angka-angka berasal dari satu repositori, satu model (DeepSeek flash), satu run per isu, dan dihitung dari percakapan tersimpan dengan ekspresi reguler (baris per node, bukan per submit). Perkiraan bahwa normalisasi memangkas sebagian besar penolakan belum diukur. Analisis statis tidak menangkap tes yang dihasilkan dinamis (tidak ada di more-itertools); K1 koleksi tetap menjadi jaring pengaman untuk itu.
