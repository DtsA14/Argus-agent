# Spec APPEND-TESTS: tes baru boleh ditambahkan ke berkas tes yang sudah ada

Status: **usulan, menunggu persetujuan Atha (strict lane).** Ditulis Claude 2026-11-13.
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
2. **Penyusunan deterministik**, sekali, sebelum pemeriksaan lain: `content = teks_intake.rstrip("\n") + "\n\n\n" + append.strip("\n") + "\n"`. `teks_intake` dibaca dari intake (bukan dari model). Draf yang tersimpan,
   kontrak, sha persetujuan, dan patch semuanya memakai `content` lengkap; `append` disimpan juga supaya manusia melihat **hanya blok yang ditambahkan** sebagai diff (`unified()` tidak berubah: diff antara intake dan `content`
   memang hanya blok itu).
3. **Pemeriksaan yang sudah ada tetap berlaku pada `content`**: berkas harus ada di intake, protected dan tidak writable, dijalankan utuh oleh sebuah validasi, K1 (tidak ada tes lama yang hilang, termasuk karena
   kelas atau fungsi baru bernama sama yang menimpa yang lama), tambahan 1 (tidak ada fungsi lama yang berubah diam-diam), tambahan 2 (tidak ada skip atau xfail baru).
4. **Syarat baru untuk `append`:** setiap simpul `must_pass` pada berkas itu harus **tidak ada di intake** (tes baru; tes lama yang diwajibkan berarti `modified`, yang tidak boleh di jalur `append`), dan harus ada
   sekurang-kurangnya satu simpul wajib yang merah karena assert pada kode sekarang (red check yang sama dengan tes baru: tidak diubah).
5. **Pelonggaran `draft.py:143`:** draf valid bila `new_tests` tidak kosong **atau** ada entri `changed_tests` dengan `append` yang punya simpul wajib. Draf lama (tanpa `append`) divalidasi persis seperti sekarang.
6. **Prompt drafter** (`codetask/drafter.py`, aturan tentang tes): "Tambahkan tes ke berkas tes yang sudah menguji modul itu dengan `append`, mengikuti gaya berkasnya (unittest atau pytest), dan tulis sendiri
   impor yang dibutuhkannya di blok itu. Berkas baru (`new_tests`) hanya bila tidak ada berkas tes yang cocok."
7. **Tidak berubah:** agen (tes tetap protected), acceptance, baseline merah, vitest (drafter vitest tetap `new_tests` saja), batas `MAX_FILES`, batas ukuran.

### Yang sengaja tidak disentuh

- **Pembungkus `try/except ... raise AssertionError`** di tes: tujuh dari delapan patch memilikinya, dan ditandai penilai sebagai perapian kedua. Itu **perintah eksplisit** di prompt drafter (supaya traceback menunjuk
  asal kesalahan untuk agen). Mengubahnya mengorbankan umpan balik agen; itu keputusan terpisah dan tidak bagian dari spek ini.
- Ukuran tes: delapan patch membawa 18 sampai 118 baris tes. Tidak diatur di sini.

## 2. Risiko

| Risiko | Penanganan |
|---|---|
| Blok `append` memakai nama atau impor yang tidak ada di berkas | blok menulis impornya sendiri (aturan 6); red check dan validasi penuh di sandbox menangkap `NameError`/`ImportError` sebagai kegagalan non-assert (sudah ditolak oleh W2a red-by-assertion) |
| Kelas atau fungsi baru menimpa yang lama | K1 (tes lama hilang) menolak |
| Gaya campur (pytest di berkas unittest) | tidak dicek secara mekanis; manusia melihat diff yang hanya blok tambahan |
| Berkas intake sangat besar | hanya dibaca untuk digabung; batas ukuran `content` hasil gabungan sama dengan sekarang dan harus diperiksa (test_more.py 7.516 baris harus muat) |
| Drafter tetap memilih berkas baru | tidak dipaksa: `new_tests` tetap sah; hasilnya diukur (bagian 4) |

## 3. Rencana pengerjaan (strict lane)

1. Tes yang gagal dulu: bentuk entri (`content` xor `append`), penyusunan tepat, `append` + `removed`/`modified` ditolak, simpul wajib tua ditolak, K1 menolak penimpaan, draf tanpa `new_tests` tapi dengan
   `append` valid, draf lama tidak berubah, vitest tidak berubah, sha/kontrak memakai `content` lengkap.
2. Kode: `acceptance/changed.py` (bentuk dan penyusunan), `acceptance/draft.py` (pelonggaran), `codetask/drafter.py` (skema dan prompt).
3. Review, mutan (`verification/append_tests_mutants.py`), `verify_at`, lalu menunggu "merge" Atha.

## 4. Pengukuran sesudahnya (butuh persetujuan uang Atha)

Jalankan ulang drafter pada delapan issue batch 3 (biaya draf sekitar $0,005 sampai $0,016 per issue; **hanya tahap draf, tanpa agen**, sekitar $0,10 total) dan hitung berapa draf yang memakai `append` ke berkas tes
yang ada dibanding berkas baru, dan apakah draf itu lolos pemeriksaan harness. Keberhasilannya diukur pada hal itu saja, bukan pada nilai patch.

## 5. Batas yang diketahui

- Satu repositori (more-itertools) memperlihatkan masalah ini; konvensi letak tes repositori lain tidak diperiksa.
- Spek ini menyelesaikan "letak tes", bukan "gaya tes" (pembungkus, jumlah tes) atau cacat perilaku seperti `len()` O(n) di #1247, yang hanya ketahuan lewat membaca.
