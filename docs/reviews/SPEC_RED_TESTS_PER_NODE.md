# Spec: alasan merah per tes dari red check, bukan dari ekor output (dari `argus-ledger` tahap 2 dan 3a)

Status: **draf, menunggu keputusan Atha** (K1–K4 di bagian 6). Asal: review draf `argus-ledger` tahap 2 (`j20261028_103452_6a83-d1`)
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

Plugin menambah dua field per node yang gagal di fase `call` (field lama tidak berubah):

- `message`: `str(exc)` (untuk `pytest.fail`: pesannya), maksimal **500** karakter, dipotong dengan `...`.
- `repo_paths`: path relatif (terhadap `/workspace`, tanpa `site-packages`, aturan `inside()` yang sama) dari **semua** frame traceback
  exception itu **dan rantainya** (`__cause__`, dan `__context__` kecuali `__suppress_context__`; kedalaman maks 5), unik, urutan
  pertama muncul, maksimal **20**. Ini setara dengan "baris lokasi" di seksi pytest, karena pytest juga mencetak rantai.

pytest di dalam plugin dijalankan dengan `--tb=no --disable-warnings`: output teksnya tidak dibaca (hanya JSON sesudah nonce), dan
tanpa traceback dan ringkasan warning stdout jauh dari batas 64 KiB sandbox. Keduanya hanya mengubah tampilan: `filterwarnings` dari
konfigurasi repo tetap berlaku, jadi hasil tes sama dengan validasi. Bila output tetap terpotong, red check tetap menolak seperti
sekarang ("the run timed out or its output was cut").

Data ini dari proses yang menjalankan kode yang dites, sama seperti sebelumnya: pemalsuan dari dalam dibatasi sandbox, tidak dideteksi.

### 2.2 Gate tes yang menelan traceback dinilai per node dari red check (K2)

`swallowed_problems` tidak lagi membaca ekor. Untuk setiap node wajib di `red_check` dengan `assertion: true`:

- ditolak bila (a) `message` menyebut nama exception lain (`\b[A-Z]\w*(?:Error|Exception)\b`, selain `AssertionError`; regex yang sama)
  dan (b) tidak ada path di `repo_paths` yang merupakan kode repo (aturan `_test_path` yang sama: bukan berkas tes, `tests/`,
  `testing/`, `*_test.py`, `conftest.py`, bukan `protected`);
- **fail-closed:** node dengan `assertion: true` yang tidak punya field `message` atau `repo_paths` (bukan list) menjadi problem
  "how it fails could not be read", tidak dilewati;
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

- **Pesan > 500 karakter** yang menyebut nama exception di bagian yang dipotong lolos dari 2.2(a). Lebih sempit dari sekarang (ekor
  2.000 karakter untuk semua tes); batasnya disebut di docstring.
- **Ukuran JSON:** 50 node × (500 + 20 path) masih bisa melewati 64 KiB pada kasus ekstrem; hasilnya penolakan (fail-closed), bukan lolos.
- Sengaja **bukan** `-p no:warnings`: plugin itu juga menerapkan `filterwarnings` repo, jadi mematikannya bisa membuat tes yang gagal
  karena warning-sebagai-error di validasi berperilaku lain di red check. `--disable-warnings` hanya menyembunyikan ringkasan.

## 4. Tes (gagal di kode lama; mutan)

Fixture: `check_report.json` asli kedua draf (disalin ke `fixtures/drafts/`), red check palsu, dan satu repo kecil di sandbox.

1. Red check di sandbox (modul sandbox, tidak di-skip): tes yang menangkap `ValueError` lalu `assert False, f"raised {e!r}"` di luar
   `except` → `message` memuat `ValueError`, `repo_paths` hanya berkas tes; tes yang `raise AssertionError(...) from e` → `repo_paths`
   memuat modul repo; pesan 2.000 karakter dipotong ke 500; output tanpa traceback teks (`--tb=no`).
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
