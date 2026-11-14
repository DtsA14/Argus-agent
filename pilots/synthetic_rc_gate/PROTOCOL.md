# PROTOKOL: kasus sintetis untuk RC (`ReportConflict`) dan GATE (hit deteksi tes terminal)

Status: **BERLAKU, disetujui Atha 2026-11-14 ("Ok setuju", termasuk angka 14 + 14 kasus dan penulis subagen Fable)**. Ditulis Claude 2026-11-14.
Dasar: urutan kerja Fable butir (5) di `PENDING.md`: "kasus sintetis RC dan GATE ditulis Atha atau sesi lain dari spek, dibekukan sebelum dijalankan, dengan kasus negatif (tes lama merah karena bug agen); nol kesalahan dari n kasus hanya membuktikan 'berfungsi' (batas atas kasar 3/n)". Tanpa model Argus, tanpa uang Argus.

## 1. Mengapa

RC dan GATE dibangun dan diuji oleh orang yang sama (Claude): tes-tesnya (`tests/test_report_conflict.py`, `test_conflict_gate.py`, `test_detection_terminal.py`, `test_test_detection.py`) dan mutannya membuktikan bahwa kode melakukan apa yang Claude kira spek minta. Mereka tidak membuktikan bahwa Claude membaca spek dengan benar, atau bahwa spek menangkap kasus yang sebenarnya muncul. Yang dibutuhkan: kasus yang ditulis oleh pihak yang **tidak melihat kode**, dibekukan sebelum dijalankan, termasuk kasus yang harus **ditolak**.

## 2. Siapa menulis, dan apa yang boleh dibaca penulis

Penulis: **sesi lain** (subagen model Fable, atau Atha). **Bukan Claude yang menulis kode RC/GATE.** Penulis hanya diberi:
`docs/reviews/FABLE_SPEC_REPORT_CONFLICT_v1.md`, `..._v2.md`, `SPEC_REPORT_CONFLICT_V3.md`, `SPEC_TEST_DETECTION_GATE.md`, `SPEC_TEST_DETECTION_TERMINAL.md`, format kontrak (`acceptance/contract.py` docstring bagian awal saja: bentuk `scope`, `validation`), dan format kasus di bagian 3. Penulis **tidak** diberi: `acceptance/conflict.py`, `acceptance/testdetect.py`, `codetask/run.py`, tes dan mutan yang ada, dan hasil apa pun dari kode.

## 3. Bentuk satu kasus (data, bukan kode)

Satu direktori `cases/<id>/` berisi:
- `input/`: repositori awal (berkas Python kecil, tes `pytest`), seperti yang dilihat agen.
- `workspace/`: berkas yang **berbeda atau baru** setelah agen bekerja (agen sintetis; tidak ada model yang dipanggil). Berkas yang tidak ada di sini sama dengan `input/`.
- `case.json`: `{id, spec_refs: ["V3 C1", ...], what: "satu kalimat", contract: {scope: {writable, protected}, validation: [...]}, agent: {end: "conflict_reported" | "finished", files: [...] }, expect: {...}}`. **Yang diperiksa mesin hanya `expect.decision` (RC) dan `expect.detection` serta `expect.terminal` (GATE)**; `reasons_include` dan `patterns` bersifat informasi untuk pembaca manusia (alasan bebas, tidak dicocokkan).
- Kunci `expect` untuk **RC**: `{"decision": "confirmed" | "unconfirmed" | "blocked", "reasons_include": ["<kondisi spek>", ...], "nodes": [...]}`. Untuk **GATE**: `{"detection": "hit" | "clean", "terminal": true | false, "patterns": [...]}`.
- `why.md`: mengapa kasus ini harus berakhir begitu, dengan merujuk **kalimat spek** (bukan kode).

## 4. Isi himpunan (usulan; Atha boleh mengubah angkanya sebelum penulis mulai)

**RC, 14 kasus**
- 5 **terkonfirmasi** yang benar: tes lama protected merah karena memang bertentangan dengan perilaku baru; ragam: satu berkas, dua berkas, gagal di dalam helper (C1), tes lama berparameter, laporan ke-5 berkas (batas).
- 9 **negatif** (harus tidak terkonfirmasi atau diblokir), satu per kondisi spek: agen mengubah berkas tes; agen mengubah `conftest.py` (SUPPORT_NAMES); tes merah karena exception di **kode produksi** (bug agen, C1 paragraf "tetap ditolak"); merah di berkas yang tidak disebut; berkas yang disebut tidak merah; tes baru wajib ikut merah; tes tidak stabil (merah di satu run, hijau di run lain); terlalu banyak node merah untuk dicacah (C5); agen tidak mengubah apa-apa selain `SUMMARY.json`.

**GATE, 14 kasus**
- 7 **hit** (kode produksi mengenali tes): ragam pola yang disebut `SPEC_TEST_DETECTION_GATE.md` (variabel lingkungan pytest, `"pytest" in sys.modules`, dan seterusnya), termasuk satu yang menyembunyikan polanya di helper dan satu bersama kegagalan validasi lain dan satu bersama laporan konflik (harus terminal dan tidak terkonfirmasi).
- 7 **bersih** yang **mirip** hit tetapi bukan: kata "pytest" di komentar atau string dokumentasi, kode yang membaca variabel lingkungan lain, pola yang hanya ada di berkas tes, dan seterusnya (kasus negatif yang menguji false positive).

Penulis boleh menambah kasus; jumlah akhir dan isi dicatat apa adanya.

## 5. Pembekuan dan aturan kejujuran

1. Kasus ditulis, **di-commit dalam satu PR (sha dicatat)**, dan baru sesudah itu pelari ditulis atau dijalankan. Pelari (Claude) tidak mengubah kasus.
2. **Kasus tidak diperbaiki sesudah melihat hasil.** Kalau sebuah kasus ternyata tidak valid (spek ambigu, `expect` tidak mungkin), kasus itu dicatat sebagai **"celah spek"** dengan alasannya dan dikeluarkan dari hitungan kesalahan, **bukan diedit**; Atha memutuskan apakah spek yang diperbaiki.
3. Pelari menjalankan kode sungguhan (`acceptance/conflict.py` verify dengan red check di sandbox, pemindai `testdetect`), tanpa model, lalu membandingkan `expect` dengan hasil. Satu kasus yang meleset adalah satu **kesalahan**; ditampilkan dengan kasusnya, bukan diringkas.
4. Laporan menyebut: n kasus, berapa positif dan negatif, kesalahan, celah spek, dan **batas atas kasar tingkat kesalahan (3/n, 95%)** bila nol kesalahan; kalimat yang boleh: "nol kesalahan dari n hanya membuktikan 'berfungsi' pada jenis kasus yang ditulis", bukan "benar".
5. Hasil dan kasus disimpan di repositori (`pilots/synthetic_rc_gate/`), sha pembekuan dicantumkan.

## 6. Urutan

1. Atha menyetujui protokol ini (dan angka di bagian 4).
2. Penulis (subagen Fable) menulis kasus RC dan GATE dari spek saja; Claude tidak membaca kasus sebelum dibekukan selain memeriksa bentuknya.
3. PR pembekuan (kasus saja). Atha boleh membaca sampel.
4. Claude menulis pelari (`pilots/synthetic_rc_gate/run.py`, bukan jalur ketat, tidak mengubah harness) dan menjalankannya; melaporkan per kasus.
5. Kesalahan dan celah spek dibawa ke Atha; perbaikan kode atau spek lewat jalur ketat tersendiri.

## 7. Biaya dan batas

Uang Argus: nol (tanpa model). Biaya: token subagen penulis dan beberapa menit sandbox. Batas yang diketahui: kasus sintetis kecil (Python, `pytest`), satu penulis (satu model), n sekitar 28; ia tidak menutup vitest, kasus dengan agen nyata, atau kombinasi di luar yang ditulis. Spek v3 sendiri mencatat batas RC yang sudah diketahui (konflik "sekarang raise" atau yang melibatkan `subTest` tidak terdeteksi).
