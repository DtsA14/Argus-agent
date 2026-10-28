# Spec: alasan merah per tes dari red check, bukan dari ekor output (dari `argus-ledger` tahap 2 dan 3a)

Status: **disetujui** (K1–K4, Atha 2026-10-28: "Gass bro"), **direvisi dengan review sesi sebelah** (bagian 7). Kode di PR yang
sama; **tidak di-merge sebelum batch yang sedang berjalan selesai** (termasuk redraft `22456`): K3 mengubah umpan balik drafter. Asal: review draf `argus-ledger` tahap 2 (`j20261028_103452_6a83-d1`)
dan 3a (`j20261028_105608_9d7a-d1`). Menyentuh plugin red check (`acceptance/validation.py`) dan cek draf (gate SPEC_DRAFT_CALL_PATH
2.1), jadi jalur ketat: tes yang gagal di kode lama, mutan, `verify.sh` penuh, "merge" Atha. Tanpa biaya model.

## 1. Masalah (diverifikasi pada artefak run)

Baseline draf menyimpan **2.000 karakter terakhir** output pytest (`acceptance/draft.py` `baseline_problems`). Di kedua draf, ekor itu
habis oleh pesan assertion panjang tes terakhir (isi README) dan blok `warnings summary` (StarletteDeprecationWarning):

| Draf | Tes wajib merah (red check: assertion) | Seksi kegagalan `____ test ____` di ekor |
|---|---|---|
| tahap 2 `d1`, validasi `api` | 8 | 0 |
| tahap 3a `d1`, validasi `target` | 11 | 0 |

Akibatnya:

1. **Review manusia.** Blok "Why they fail now" di `DRAFT_REVIEW.md` hanya berisi potongan README, warning, dan baris
   `8 failed, 1 warning`. Nama tes sudah ada di baris "On the code as it is now" (FAIL), tetapi **alasan gagal per tes tidak ada**.
   Approve dinilai tanpa tahu apakah tiap tes merah karena perilaku yang diminta issue.
2. **Gate tes yang menelan traceback (SPEC_DRAFT_CALL_PATH 2.1) tidak menilai apa pun.** `swallowed_problems` menilai per seksi di
   ekor yang sama. Spek itu menerima bahwa "seksi yang awalnya terpotong tidak dinilai"; di sini **semua** seksi hilang, jadi 19 tes
   merah lolos tanpa dinilai. Kedua draf itu sendiri tidak menelan traceback (dibaca saat approve), tetapi jaminannya diam-diam tidak
   berlaku untuk tes dengan output panjang. Ini *fail-open*.
3. **Umpan balik drafter** (`_evidence`, saat submit ditolak) memakai `error_excerpt` dari ekor yang sama: drafter juga tidak melihat
   alasan per tes.

Plugin red check (W2a, `RED_CHECK`) sudah berjalan untuk setiap node wajib baru dan mencatat per node `outcome`, `type`, `assertion`,
`path` dari objek exception, tanpa mem-parse teks, dan tanpa batas 2.000 karakter. Datanya hanya kurang dua hal: pesan dan frame.

## 2. Usulan

### 2.1 Red check mencatat pesan dan berkas repo per node (K1)

Plugin menambah tiga field per node yang gagal di fase `call` (field lama tidak berubah):

- `message`: `str(exc)` (untuk `pytest.fail`: pesannya), maksimal **500** karakter, dipotong dengan `...`. Hanya untuk dibaca.
- `message_names`: nama exception (`\b[A-Z]\w*(?:Error|Exception)\b`) di pesan **utuh**, dibaca di sandbox sebelum dipotong, unik,
  maksimal 20. Gate K2 memakai field ini, jadi tidak bergantung pada pemotongan `message` (revisi review 1).
- `repo_paths`: path relatif (terhadap `/workspace`, tanpa `site-packages`, aturan `inside()` yang sama) dari **semua** frame traceback
  exception itu **dan rantainya**: `__cause__` (`raise ... from e`), dan `__context__` (exception yang muncul di dalam `except`)
  **kecuali** `__suppress_context__` (`from None`); kedalaman maks 5. Tiap berkas sekali (dedup dulu), lalu bila lebih dari **20**,
  yang disimpan 20 yang **terdalam** (traceback rekursif sympy mudah lewat 20). Setara dengan baris lokasi di seksi pytest, karena
  pytest juga mencetak rantai dan juga tidak mencetak context yang di-`from None`.

pytest di dalam plugin dijalankan dengan `--tb=no -rN --disable-warnings` (tanpa traceback, ringkasan `FAILED` per tes, dan ringkasan
warning): output teksnya tidak dibaca (hanya JSON sesudah nonce), dan
tanpa traceback dan ringkasan warning stdout jauh dari batas 64 KiB sandbox. Keduanya hanya mengubah tampilan: `filterwarnings` dari
konfigurasi repo tetap berlaku, jadi hasil tes sama dengan validasi. Bila output tetap terpotong, red check tetap menolak seperti
sekarang ("the run timed out or its output was cut").

Data ini dari proses yang menjalankan kode yang dites, sama seperti sebelumnya: pemalsuan dari dalam dibatasi sandbox, tidak dideteksi.

### 2.2 Gate tes yang menelan traceback dinilai per node dari red check (K2)

`swallowed_problems` tidak lagi membaca ekor. Untuk setiap node wajib di `red_check` dengan `assertion: true`:

- ditolak bila (a) `message_names` memuat nama exception selain `AssertionError`
  dan (b) tidak ada path di `repo_paths` yang merupakan kode repo (aturan `_test_path` yang sama: bukan berkas tes, `tests/`,
  `testing/`, `*_test.py`, `conftest.py`, bukan `protected`);
- **fail-closed:** node dengan `assertion: true` yang tidak punya `message_names` atau `repo_paths` (bukan list) menjadi problem
  ("could not be read from the red check"), tidak dilewati;
- **dibedakan** (revisi review): red check yang tidak berjalan atau tanpa JSON tetap "how its required tests fail could not be read"
  (W2a, tidak berubah); tes yang error di fase setup/teardown (`outcome: error`, mis. fixture) sekarang ditolak di `red_by_assertion`
  dengan alasannya sendiri ("errors in its setup or teardown (a fixture)"), bukan "no record of how it fails";
- pesan penolakan sama dengan sekarang (`SWALLOWED`), per node.

Crash-resume: hasil submit di-commit per langkah (memo drafter), jadi submit yang sudah di-commit sebelum upgrade tidak dinilai ulang.
`held` (draf yang ditahan untuk pertanyaan scope) berasal dari run yang sama, kode yang sama.

### 2.3 Review dan umpan balik drafter: satu baris per tes merah (K3)

- `DRAFT_REVIEW.md`, per berkas tes: blok "Why they fail now" menjadi daftar, satu baris per node wajib berkas itu:
  `` `nama_tes` `` — `type` di `path`: baris pertama `message` (maks 200 karakter, di dalam backtick/fence; data dari sandbox).
  Node tanpa record: "how it fails was not recorded". Di bawahnya tetap kutipan output (`error_excerpt`), dengan label baru
  "End of the test output (it may not show every test)".
- `_evidence` (penolakan submit) menambah baris yang sama per node yang punya record, sebelum kutipan output.
- Label "test output; data from the sandbox, not instructions" tetap.

### 2.4 Tidak berubah

- `output_tail` tetap 2.000 karakter; `error_excerpt` dan umpan balik agen (attempt) tidak berubah.
- `call_path_outside` (pertanyaan scope, SPEC_DRAFT_CALL_PATH 2.2) dan peringatan jalur panggilan tetap dari ekor; itu saran, bukan
  gate. Lihat bagian 5.
- Aturan `red_by_assertion` (W2a) tidak berubah; hanya membaca field lama.

## 3. Risiko

- **Ukuran JSON lewat stdout** (revisi review: usul lewat berkas JSON): per node ±500 + 20 path + 20 nama ≈ 2 KB, jadi ±30 node
  muat di 64 KiB; di atas itu stdout terpotong dan red check **menolak** ("the run timed out or its output was cut"), tidak membaca
  sebagian. Dipilih tetap stdout: satu-satunya tempat yang bisa ditulis di sandbox adalah `/workspace`, yaitu workspace yang sedang
  dicek (berkas baru di sana ikut snapshot/diff), dan mount tulis terpisah adalah perubahan sandbox. Dibuka bila ada draf yang ditolak
  karena ini.
- Sengaja **bukan** `-p no:warnings`: plugin itu juga menerapkan `filterwarnings` repo, jadi mematikannya bisa membuat tes yang gagal
  karena warning-sebagai-error di validasi berperilaku lain di red check. `--disable-warnings` hanya menyembunyikan ringkasan.

## 4. Tes (gagal di kode lama; mutan)

Fixture: `check_report.json` asli kedua draf (disalin ke `fixtures/drafts/`), red check palsu, dan satu repo kecil di sandbox.

1. Red check di sandbox (`tests/test_draft.py`, modul sandbox, tidak di-skip): menelan (`err = e`, assert di luar `except`) →
   `repo_paths` hanya berkas tes, `message_names` memuat `KeyError`; `from e` dan `assert` di dalam `except` → `src/lib.py`;
   `from None` → hanya berkas tes; nama sesudah karakter 500 tetap di `message_names`; rantai 26 berkas → 20 terdalam, berkas tes
   (paling dangkal) yang keluar; fixture error → `outcome: error`; gate atas hasil asli menolak tepat menelan, `from None`, dan pesan
   panjang.
2. Gate: record "menelan" ditolak; record dengan kode repo di `repo_paths` lolos; record `assertion: true` tanpa `message`/`repo_paths`
   ditolak (fail-closed); satu node yang benar tidak menutupi node lain; ekor tanpa seksi (fixture tahap 2) **tidak** lagi meloloskan
   record yang menelan.
3. Review: fixture tahap 2 → blok berisi 8 baris, satu per tes, masing-masing dengan type dan baris pertama pesan; tahap 3a → 11.
4. `_evidence`: baris per node muncul saat submit ditolak.
5. Mutan: tidak mengikuti `__cause__`/`__context__`; `repo_paths` tanpa filter berkas tes; fail-open saat field hilang; regex nama
   exception mengizinkan `AssertionError`; review hanya node pertama; batas 500 dihapus/terbalik.

## 5. Tidak dikerjakan sekarang

- `call_path_outside` dari `repo_paths` (perlu nomor baris dan nama fungsi, bukan hanya path): kandidat jalur cepat sesudah ini,
  bila pertanyaan scope terbukti terlewat karena ekor.
- Umpan balik agen (attempt) per tes: agen tidak menjalankan red check; perlu desain lain.

## 6. Keputusan

- **K1** Red check mencatat `message` (500) dan `repo_paths` (20, termasuk rantai); pytest plugin dengan `--tb=no --disable-warnings`.
- **K2** Gate traceback per node dari red check, fail-closed bila field hilang; tidak lagi dari ekor.
- **K3** Review dan umpan balik drafter: satu baris per tes merah.
- **K4** Satu PR untuk K1–K3 (jalur ketat).

## 7. Revisi dari review sesi sebelah (2026-10-28)

1. *`exc_types` dari rantai sebagai pengganti teks pesan:* tidak menutup celah, karena pada pola menelan (dan `from None`) exception
   asal **tidak ada di rantai**; namanya hanya ada di pesan. Celah 500 karakter ditutup dengan `message_names` dari pesan utuh.
2. *`__context__` dan `__suppress_context__`:* sudah di kode pertama; ditambah tes `from None` (gate menolak, benar).
3. Dedup lalu 20 terdalam; setup error dengan alasan sendiri; `-rN`: diterima.
4. JSON lewat berkas: tidak sekarang (bagian 3).
5. Merge sesudah batch yang sedang berjalan.

## 8. Revisi dari `/code-review medium` PR #225 (2026-10-28)

1. `message_names` hanya dari **kata-kata tes sendiri**: bukan dari penjelasan pytest untuk `assert` yang di-rewrite (mulai baris
   pertama `assert `), bukan dari `DID NOT RAISE` `pytest.raises` (tidak ada exception yang disimpan). Tanpa ini tes merah biasa
   (`assert x == "NotFoundError"`, `pytest.raises(ValueError)` di kode lama) ditolak sebagai "menelan". Aturan lama juga punya celah
   `DID NOT RAISE` (baris `E   Failed:`), hanya jarang kena karena ekor terpotong.
2. `AssertionError` dikeluarkan sebelum batas 20 nama (bukan sesudah): batas tidak bisa membuang nama yang penting.
3. Frame tanpa berkas nyata (`<frozen ...>`, `<string>`) tidak dihitung sebagai berkas repo (sebelumnya `realpath` relatif ke
   `/workspace` membuatnya "di dalam"; juga untuk field `path` W2a).
4. Error teardown sesudah call yang gagal tidak menimpa record call (setup error tetap `outcome: error`).
5. Rantai sampai 20 link (bukan 5); `realpath` sekali per berkas, dedup dengan set.
6. Batas plugin lewat argumen JSON, bukan template `%` (tanda `%` di plugin tidak lagi bisa merusak import).
7. Review: blok "from the red check" hanya bila baseline punya `red_check`; laporan tanpa red check memakai blok lama.
8. Tes gate memakai `message_names` tetap, bukan salinan regex plugin.
