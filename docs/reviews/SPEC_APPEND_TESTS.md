# Spec APPEND-TESTS: tes baru boleh ditambahkan ke berkas tes yang sudah ada

Status: **dibangun di branch ini (tes dan kode), menunggu review, mutan, `verify_at` dan "merge" Atha (strict lane).** Disetujui "go" oleh Atha 2026-11-13 dengan tiga catatan kecil (sudah dibetulkan). Ditulis Claude 2026-11-13.
Dasar: `acceptance/changed.py` (W2a-ext, `SPEC_W2A_EXT_CHANGED_TESTS.md`), `acceptance/draft.py`, `codetask/drafter.py`.

## 0. Masalah (terukur)

Batch 3 (`pilots/outside_v2/batch3/RESULTS.md`): **8 dari 8 patch akhir membawa tes di berkas baru** (`tests/test_split_empty_maxsplit.py`, ...), padahal more-itertools menaruh tes di
`tests/test_more.py` dan `tests/test_recipes.py`. Delapan verdict Claude, tiga bacaan pembaca delegasi, dan dua penilai buta (Opus, Fable) menandainya sebagai "letak tes"; karena itu semua patch bernilai B atau `reject`,
dan nilai itu tidak lagi membedakan patch bagus dari jelek (tes pemelihara: 6 dari 6 lolos).

Penyebabnya ada di **drafter**, bukan agen: tes itu ditulis oleh drafter, dan skemanya memaksa berkas baru:
- `NewTest.path`: "A new tests file ... (never an existing file)"; `draft.py:143` menolak draf tanpa satu pun `new_tests`.
- Satu-satunya jalan menambah tes ke berkas yang ada, `changed_tests`, menuntut **"The complete new file content"**. `tests/test_more.py` panjangnya 7.516 baris; menulis ulang seluruhnya sebagai
  keluaran drafter tidak muat dan tidak layak, jadi drafter selalu memilih berkas baru.

## 1. Usulan

`ChangedTest` boleh membawa **`append`** sebagai ganti `content`: kode tes yang ditambahkan di **akhir** berkas yang sudah ada. Harness yang menyusun isi lengkapnya; semua pemeriksaan sesudahnya
bekerja pada isi lengkap itu, seperti sekarang.

```json
"changed_tests": [{"path": "tests/test_more.py", "append": "class SplitEmptyMaxsplitTests(TestCase):\n    def test_...(self): ..."}]
```

### Aturan

1. **Tepat satu** dari `content` atau `append` per entri (selain itu ditolak). `removed` dan `modified` tetap hanya berlaku untuk `content` (dengan `append`, tidak ada tes lama yang berubah, jadi keduanya harus kosong).
2. **Urutan dan batas ukuran.** (a) Bentuk dan ukuran **blok `append`**: paling banyak `MAX_TEST_BYTES` (50.000 byte, `draft.py:60`), sama seperti `content` dan `new_tests` sekarang. (b) **Penyusunan deterministik**, sekali:
   `content = teks_intake.rstrip("\n") + "\n\n\n" + append.strip("\n") + "\n"` (dua baris kosong, PEP 8). `teks_intake` dibaca dari intake (bukan dari model). (c) Batas untuk **`content` hasil gabungan** bukan 50.000: paling banyak
   `len(teks_intake.encode("utf-8")) + MAX_TEST_BYTES` byte dan tidak lebih dari 1 MiB (1.048.576 byte); semua batas ukuran dihitung dalam **byte UTF-8**, bukan karakter (seperti `leaks.py`). Alasannya terukur: `tests/test_more.py` berukuran 259.039 byte; batas 50.000 pada isi gabungan akan menolak berkas itu selamanya, tepat pada kasus
   yang mau diperbaiki. `content` yang diberikan drafter sendiri (tanpa `append`) tetap dibatasi 50.000 seperti sekarang. (d) Baru sesudah itu semua pemeriksaan lain. Draf yang tersimpan,
   kontrak, sha persetujuan, dan patch semuanya memakai `content` lengkap; `append` disimpan juga supaya manusia melihat **hanya blok yang ditambahkan** sebagai diff (`unified()` tidak berubah: diff antara intake dan `content`
   memang hanya blok itu).
3. **Pemeriksaan yang sudah ada tetap berlaku pada `content`**: berkas harus ada di intake, protected dan tidak writable, dijalankan utuh oleh sebuah validasi, K1 (tidak ada tes lama yang hilang, termasuk karena
   kelas atau fungsi baru bernama sama yang menimpa yang lama), tambahan 1 (tidak ada fungsi lama yang berubah diam-diam), tambahan 2 (tidak ada skip atau xfail baru).
4. **Syarat baru untuk `append`:** setiap simpul `must_pass` pada berkas itu harus **tidak ada di intake**, dihitung dari **koleksi pytest versi intake di sandbox yang sudah dipakai K1** (`before` di `lost_problems`), bukan dari AST: simpul wajib yang
   ada di `before` ditolak (tes lama yang diwajibkan berarti `modified`, yang tidak boleh di jalur `append`). Satu mekanisme untuk K1 dan syarat ini, supaya keduanya tidak bisa berbeda pendapat tentang apa yang "sudah ada". Dan harus ada
   sekurang-kurangnya satu simpul wajib yang merah karena assert pada kode sekarang (red check yang sama dengan tes baru: tidak diubah).
5. **Berkas dengan blok `__main__` ditolak untuk `append`.** Bila teks intake punya `if __name__ == "__main__":` di level atas (diperiksa dengan AST: `If` yang membandingkan `__name__` dengan `"__main__"`), `append` ditolak, karena tes yang
   ditempel sesudah blok itu tidak ikut saat berkas dijalankan sebagai skrip (di pytest tidak masalah, tapi aturannya dibuat sederhana dan tidak bergantung pada cara berkas dijalankan). more-itertools tidak punya blok ini; dua berkas tes boltons
   (`test_listutils.py`, `test_statsutils_histogram.py`) punya. Drafter yang ditolak memakai `new_tests` atau `content`.
6. **Pelonggaran `draft.py:143`:** draf valid bila `new_tests` tidak kosong **atau** ada entri `changed_tests` dengan `append` yang punya simpul wajib. Draf lama (tanpa `append`) divalidasi persis seperti sekarang.
7. **Prompt drafter** (`codetask/drafter.py`, aturan tentang tes): "Tambahkan tes ke berkas tes yang sudah menguji modul itu dengan `append`, mengikuti gaya berkasnya (unittest atau pytest), dan tulis sendiri
   impor yang dibutuhkannya di blok itu. Berkas baru (`new_tests`) hanya bila tidak ada berkas tes yang cocok."
8. **Tidak berubah:** agen (tes tetap protected), acceptance, baseline merah, vitest (drafter vitest tetap `new_tests` saja), batas `MAX_FILES`, dan batas ukuran untuk `content` dan `new_tests` dari drafter (batas isi gabungan di aturan 2(c) hanya untuk entri `append`).

### Yang sengaja tidak disentuh

- **Pembungkus `try/except ... raise AssertionError`** di tes: tujuh dari delapan patch memilikinya, dan ditandai penilai sebagai perapian kedua. Itu **perintah eksplisit** di prompt drafter (supaya traceback menunjuk
  asal kesalahan untuk agen). Mengubahnya mengorbankan umpan balik agen; itu keputusan terpisah dan tidak bagian dari spek ini.
- Ukuran tes: delapan patch membawa 18 sampai 118 baris tes. Tidak diatur di sini.

## 2. Risiko

| Risiko | Penanganan |
|---|---|
| Blok `append` memakai nama atau impor yang tidak ada di berkas | blok menulis impornya sendiri (aturan 7); red check dan validasi penuh di sandbox menangkap `NameError`/`ImportError` sebagai kegagalan non-assert (sudah ditolak oleh W2a red-by-assertion) |
| Kelas atau fungsi baru menimpa yang lama | K1 (tes lama hilang) menolak |
| Gaya campur (pytest di berkas unittest) | tidak dicek secara mekanis; manusia melihat diff yang hanya blok tambahan |
| Berkas intake sangat besar | batas terpisah untuk blok (50.000) dan isi gabungan (intake + 50.000, paling banyak 1 MiB), aturan 2; ada tes untuk berkas intake di atas 50.000 byte |
| Berkas dengan `__main__` di akhir | `append` ditolak (aturan 5) |
| Drafter tetap memilih berkas baru | tidak dipaksa: `new_tests` tetap sah; hasilnya diukur (bagian 4) |

## 3. Rencana pengerjaan (strict lane)

1. Tes yang gagal dulu: bentuk entri (`content` xor `append`), **berkas intake lebih besar dari 50.000 byte diterima** (dan blok `append` lebih besar dari 50.000 ditolak; isi gabungan di atas batas atasnya ditolak), **berkas dengan `__main__` ditolak**, penyusunan tepat, `append` + `removed`/`modified` ditolak, simpul wajib tua ditolak (lewat koleksi yang sama dengan K1), K1 menolak penimpaan, draf tanpa `new_tests` tapi dengan
   `append` valid, draf lama tidak berubah, vitest tidak berubah, sha/kontrak memakai `content` lengkap.
2. Kode: `acceptance/changed.py` (bentuk dan penyusunan), `acceptance/draft.py` (pelonggaran), `codetask/drafter.py` (skema dan prompt).
   Tambahan atas catatan review: **sha**. `materialize` (`draft.py:316`) menulis `t["content"]`, jadi penyusunan dari `append` terjadi **sebelum** draf masuk ke `materialize` dan ke perhitungan sha; ada tes bahwa
   draf `append` dan draf `content` dengan isi gabungan yang setara menghasilkan **sha draf dan sha kontrak yang sama**.
3. Review, mutan (`verification/append_tests_mutants.py`), `verify_at`, lalu menunggu "merge" Atha.

## 4. Pengukuran sesudahnya (butuh persetujuan uang Atha)

Jalankan ulang drafter pada delapan issue batch 3 (biaya draf sekitar $0,005 sampai $0,016 per issue; **hanya tahap draf, tanpa agen**, sekitar $0,10 total) dan hitung berapa draf yang memakai `append` ke berkas tes
yang ada dibanding berkas baru, dan apakah draf itu lolos pemeriksaan harness. **Yang diukur secara mekanis hanya itu: berkas tes tujuan sudah ada di intake.** Pengukuran ini **tidak** menunjukkan bahwa tanda "letak tes" hilang dari
penilaian: konvensi more-itertools menambah *method* ke kelas yang ada (misalnya `NumericRangeTests.test_reversed_empty`), sedangkan `append` menghasilkan kelas baru di akhir berkas. Apakah penilai masih menandainya hanya bisa dilihat dari
membaca patch sesudah agen jalan (satu batch kecil, dengan persetujuan uang terpisah).

## 5. Batas yang diketahui

- Satu repositori (more-itertools) memperlihatkan masalah ini; konvensi letak tes repositori lain tidak diperiksa.
- **`append` lebih baik daripada berkas baru, tapi belum tentu "letak yang benar".** Menambah method ke kelas yang sudah ada (`insert_into: {class}`) adalah langkah berikutnya yang lebih dekat ke konvensi, dan lebih rumit (penyisipan ke tengah
  berkas, K1 dan AST pada kelas yang berubah); **sengaja tidak di spek ini**, dan baru layak dipertimbangkan bila pembacaan patch sesudah `append` masih menandainya.
- Spek ini menyelesaikan "letak tes", bukan "gaya tes" (pembungkus, jumlah tes) atau cacat perilaku seperti `len()` O(n) di #1247, yang hanya ketahuan lewat membaca.

## 6. Penyimpangan dari spek saat dibangun (dicatat karena menyentuh janji di atas)

Dua hal dari kode yang tidak terlihat saat spek ditulis. Keduanya mengubah **di mana** sebuah aturan dijaga, bukan **apa** yang dijaga.

1. **Draf yang tersimpan hanya memuat `content`, tidak ada penanda "ini berasal dari append".** Alasannya catatan review tentang sha: draf `append` dan draf `content` yang setara menghasilkan **byte yang sama**, jadi sha draf dan sha
   kontrak identik (ada tesnya). Konsekuensinya, `append` hidup hanya di argumen drafter (`submit` menyimpannya untuk `ReviseDraft`), dan pemeriksaan yang tadinya bergantung pada "entri ini append" kini bergantung pada **struktur**:
   sebuah berkas yang diubah adalah *penambahan murni* (`pure_addition`: teks intake tanpa newline akhirnya tetap menjadi awal berkas baru dan ada tambahan sesudahnya). Berkas yang kebetulan berbentuk begitu lewat jalur `content` juga
   diperlakukan sama; itu konsisten dan tidak melonggarkan apa pun.
2. **Aturan ukuran dan aturan "tanpa `new_tests`" pindah dari `validate_draft` ke `static_problems`**, karena yang pertama tidak punya teks intake dan yang kedua punya.
   - Bentuk draf (`validate_draft`): batas untuk isi berkas yang diubah menjadi **1 MiB** (`MAX_CHANGED_BYTES`), bukan 50.000. Tes lama `test_draft.py` yang memeriksa 60.000 byte di tingkat ini diubah ke 1 MiB + 1.
   - `static_problems`: isi berkas yang **bukan** penambahan murni tetap dibatasi 50.000 byte (jaminan lama, kini di sini); penambahan murni boleh menambah paling banyak `MAX_BLOCK_BYTES + APPEND_OVERHEAD` = 50.004 byte
     (`added_bytes`: byte UTF-8 dari bagian setelah teks intake tanpa newline akhir), berapa pun ukuran totalnya. `APPEND_OVERHEAD = 4` adalah pemisah `"\n\n\n"` dan newline penutup, supaya blok yang tepat 50.000 byte lolos.
   - Draf tanpa `new_tests` lolos bentuk bila `changed_tests` tidak kosong; `static_problems` lalu menuntut sebuah penambahan murni dengan simpul wajib yang **bukan** tes di versi intake. Di tingkat ini "bukan tes di intake" dihitung dengan AST
     yang mengenali semua kelas (`_defined_tests`; `functions()` yang lama hanya mengenali kelas berawalan `Test`, sedangkan pytest juga mengoleksi `unittest.TestCase` dengan nama apa pun, seperti di more-itertools). Otoritasnya tetap
     **koleksi K1** (aturan 4), yang berjalan di sandbox sesudahnya.
3. **Aturan 4 (K1)** dijalankan di `collection_problems` untuk setiap berkas yang penambahan murni: simpul wajib yang sudah dikoleksi dari versi intake ditolak, dibandingkan per fungsinya (id berparameter dihitung sebagai tesnya).
   Ada tes di sandbox sungguhan (draf yang lolos sampai `approve`, dan draf yang ditolak K1).
4. **Yang tidak berubah:** tes lama selain satu baris di atas, vitest, jalur `content` untuk tes yang berubah ekspektasinya.

Tes: `tests/test_append_tests.py` (64, dua di antaranya memakai sandbox).
