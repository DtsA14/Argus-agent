# VF: pemalsuan verdict dari dalam kode yang diuji (D5, serangan A10): hasil probe dan pilihan

Status: **probe selesai dan lubang TERBUKTI, 2026-11-12; perbaikan belum dipilih** (butuh keputusan Atha, lihat §4). Rencana: `FABLE_PLAN_2026-11-11.md` (VF: "forger fixture
dulu, lalu spek kanari dan nonce"); temuan asli D5 di `FABLE_REVIEW_2026-11-11.md` (status sebelumnya: **tidak terverifikasi, tidak pernah dijalankan**). Ini bukan
perubahan harness: hanya fixture, satu tes yang ditandai gagal-dulu, dan teks ini. Kode yang dijalankan hanya di sandbox Docker (kode gue sendiri, tanpa jaringan).

## 1. Probe (apa yang dijalankan)

Fixture `fixtures/forgers/pytest_pipe_forger/`: satu proyek pytest kecil dengan satu tes yang **merah dengan jujur** (`f()` mengembalikan 2, tes menuntut 1). Modul
`src/app.py` (berkas yang boleh ditulis agen) menulis laporan pytest yang konsisten ke setiap pipa yang dipegang prosesnya lalu `os._exit(0)` saat diimpor, sebelum
tes mana pun jalan. `run_validation` dengan spec biasa (`python -m pytest tests/test_new.py`, `must_pass` berisi tes itu), di sandbox, image `ledger_py312_up2` dan environment `argus`.

| Percobaan | Hasil |
|---|---|
| forger naif: `sys.stdout.write(...)` lalu `os._exit(0)` | **gagal**: pytest menangkap `sys.stdout` dan fd 1 saat impor, laporan palsu tak sampai ("no pytest summary") |
| forger yang menulis ke deskriptor asli (pipa yang masih dipegang proses) | **LOLOS**: `status pass`, `tests_run 1`, `outcome OK`, `consistent True`, `must_pass {node: ok}`, `exit_code 0`, `failed_nodes []` |

Jadi untuk kode yang sengaja memalsukan, "validasi lulus" tidak membuktikan tes lulus. `parse_pytest` memang menolak laporan yang tidak konsisten, tetapi forger menulis laporan yang
konsisten (docstring `acceptance/validation.py` menyebut batas ini: "contained by the sandbox, and the protected test files keep the tests honest"; itu tidak cukup, karena
berkas tes terlindungi tidak pernah sempat jalan). Tes `tests/test_vf_forger.py` menyatakan jaminannya dan ditandai `xfail(strict=True)`; ia XFAIL hari ini (diperiksa di environment `argus`).

## 2. Seberapa buruk, dan apa yang tetap berlaku

- Yang rusak: `DONE` dan `REVIEW_READY` bukan bukti perilaku bagi agen yang berniat memalsukan. Tidak ada contoh di data kita (eksperimen repo luar: tidak ada forger; kecurangan
  yang pernah terlihat adalah deteksi tes, bukan pemalsuan laporan).
- Yang tetap berlaku: aturan "jangan terapkan job DONE tanpa dibaca", gerbang deteksi tes, hakim, dan penilaian eksperimen luar yang memakai tes pemelihara di sandbox terpisah
  (tidak lewat laporan dari dalam proses agen). Kedua forger memakai `os._exit`, yang langsung terlihat oleh siapa pun yang membaca patch.
- ReportConflict (RC, #473) tidak memperburuk: konflik terkonfirmasi hanya menghentikan run (BLOCKED), tidak pernah pass.

## 3. Pilihan perbaikan (jujur soal batasnya)

Kode di proses yang sama dengan pelapor selalu bisa memalsukan; yang bisa dibeli hanyalah biaya dan keterlihatan.

| | Isi | Menangkap | Tidak menangkap | Biaya |
|---|---|---|---|---|
| **O1 kanari + nonce** | plugin pytest harness (`-p`, dari mount milik harness, bukan workspace) menanam satu tes kanari yang **harus gagal**, nama dan nonce acak per run, dan baris laporan membawa nonce; kanari tak ada atau lulus berarti palsu | forger generik yang tak membaca plugin (kedua forger kita, karena tak tahu nama kanari) | forger yang membaca argv atau `sys.modules` saat jalan dan meniru kanari | sedang (plugin, parser, spek, mutan); satu perubahan perilaku untuk semua validasi pytest |
| **O2 pola forger di gerbang deteksi** | tambah pola ke `acceptance/testdetect.PATTERNS`: `os._exit(`, tulis ke fd mentah (`os.write(` bersama `S_ISFIFO` atau `/proc/self`), `sys.stdout` bersama `_exit`; hit sekarang **terminal** (GATE, #474) | kedua forger kita dan variannya yang malas, langsung dan deterministik | forger yang menyembunyikan pemanggilan (`getattr(os, "_ex" + "it")`) | kecil (pola, tes, mutan) |
| O3 proses terpisah | jalankan kode yang diuji di proses lain dari pelapor | tidak mungkin: kode yang diuji harus jalan di proses pytest | | |
| O4 jalankan ulang dua environment | sandbox kedua | tidak: forger sama | | |

**False positive O2:** kode produksi yang sah memakai `os._exit` (proses anak sesudah fork, penanganan fatal) akan menghentikan run (GATE membuat hit terminal). Itu jarang di
repo yang kita tangani sejauh ini (boltons, more-itertools, ledger, viewer), tetapi bukan nol.

## 4. Rekomendasi dan keputusan yang dibutuhkan dari Atha

1. **O2 dulu** (jalur ketat, satu PR kecil): murah, menangkap persis serangan yang terbukti. Perlu keputusan: apakah false positive `os._exit` di kode produksi dapat diterima
   (run berhenti, manusia memutuskan). Alternatif lebih lunak: O2 sebagai peringatan saja (advisory) sampai ada data false positive; gue condong ke terminal karena kerugian
   terbesar adalah pass palsu.
2. **O1 sesudahnya**, sebagai spek sendiri (plugin dan nonce); manfaatnya terbatas pada forger yang tak menarget kanari.
3. Apa pun pilihannya, `DONE` tetap tidak boleh dianggap bukti tanpa pembacaan manusia; tes `test_vf_forger.py` menjaga agar klaim itu tidak lupa diperbarui.

## 5. Tidak dikerjakan di sini

Perubahan kode harness; perluasan pola; plugin kanari.

## 6. O2 implementado (2026-11-13, Atha: "Ok setuju O2")

Atha memilih O2 sebagai gerbang terminal, menerima false positive `os._exit` di kode produksi (run berhenti, manusia memutuskan). Dikerjakan di
`acceptance/testdetect.py`: pola `os._exit` (`\b_exit\s*\(`, jadi `os._exit(` dan `_exit(` telanjang, bukan `my_exit(` atau `sys.exit(`), `raw stdout/stderr fd`
(`os.write(1,` atau `os.write(2,`; `os.write(fd, ...)` dengan variabel tidak), `S_ISFIFO`, dan `/proc/self`. Alasan kriteria menyebut "or can forge the test report" bila salah satunya kena;
selebihnya (hanya baris baru, berkas tes dikecualikan, gagal tertutup) seperti SPEC_TEST_DETECTION_GATE, dan hit-nya terminal lewat GATE (#474). Fixture forger probe kini
tertangkap oleh gerbang tanpa sandbox (`tests/test_test_detection.py`) dan oleh run lengkap (`tests/test_detection_terminal.py`). Yang **tidak** berubah: validasi forger itu
sendiri masih `pass` (tes `tests/test_vf_forger.py` tetap xfail: O2 menutup di verdict, O1 kanari dan nonce menutup di validasi, belum dikerjakan). Batas yang diketahui: forger yang menyamarkan
pemanggilannya (`getattr(os, "_ex" + "it")`, `os.write(fd, ...)` dengan fd dari variabel tanpa `S_ISFIFO`, atau lewat modul lain) tidak ditangkap.
