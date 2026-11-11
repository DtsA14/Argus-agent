# Spek: peringatan tes lama yang akan pecah (`leaks`), sebelum approve

Status: **usulan Claude 2026-11-11** (Atha: "deteksi tes lama bocor"; bagian kedua dari tiga sesudah #436). Jalur ketat: menyentuh
cek draf dan layar approve. Berlaku AGENTS.md: tes yang gagal di kode lama → kode → review → mutants → `verify_at` → "merge".
Tanpa model, tanpa uang. **Penasihat, bukan penolak** (lihat §4).

## 1. Masalah (bukti)

Probe rantai (`pilots/chain_probe_v0`, issue 019): fitur menambah key `max_usd` ke JSON. Tes lama yang membandingkan daftar key
atau dict persis harus ikut berubah, tetapi tes lama terkunci untuk agen. Drafter melewatkan file yang berbeda di dua draf
berturut-turut (`test_title_in_jobs.py`, lalu `test_api.py`): $0,15 terbuang dan satu patch curang. Draf dan red check tampak
benar karena tes lama hanya pecah **sesudah** fitur ada, dan harness tidak punya patch referensi untuk melihatnya.

## 2. Usul

**L1. Deteksi (Python).** `acceptance/leaks.py: find(base_dir, draft, issue)`. Dari AST setiap berkas `.py` tes **baru atau
diubah** draf (`new_tests`, `changed_tests`) dikumpulkan himpunan string: list, tuple, set yang seluruh elemennya string, dan
dict yang seluruh kuncinya string, masing-masing dengan ≥ 4 elemen. Hal yang sama untuk setiap berkas tes lama di intake yang
draf tidak ubah. Satu berkas tes lama dicurigai bila ada himpunan lama `O` dan himpunan baru `N` dengan:
`O ⊂ N` (sejati), `1 ≤ |N − O| ≤ 2`, dan setiap anggota `N − O` adalah satu kata (`[A-Za-z0-9_]+`) yang muncul sebagai kata utuh di
teks issue. Artinya: tes baru mengharapkan bentuk lama ditambah sesuatu yang disebut issue, sementara tes lama masih
mengharapkan bentuk lama.

Bukti pengukuran (`/tmp` prototipe, tiga draf nyata issue 019 pada argus-ledger `9bac6ed`): tanpa syarat issue, 11-13 file
terflag per draf (kebanyakan `started_at/ended_at`); dengan syarat issue, tepat satu file per draf yang memang melewatkan
(`test_title_in_jobs.py`, `test_api.py`) dan **nol** untuk draf yang benar. Sampel kecil; karena itu penasihat.

Berkas tes lama = berkas yang `is_test_file` (acceptance/testdetect) di intake; berkas > 1 MiB dilewati; paling banyak 20 temuan.
Hasil per berkas (satu entri, himpunan pertama yang cocok): `{path, line, kind: list|dict, added: [...]}`, urut path.

**L2. Tempat tampil.** (a) `check()` menyimpan `report["leaks"]` (selalu ada, mungkin kosong); (b) `DRAFT_REVIEW.md`: bagian
`## Old tests that may break` bila ada: tiap entri dengan path, baris, dan `added`, dan kalimat "the draft does not change
these files, and the agent cannot (they are protected): add them to changed_tests, or the agent will fail on them"; tanpa
temuan, satu baris "No old test looks affected (a heuristic; Python key lists and dicts only)"; (c) layar approve dan
`argus status`: satu baris `old tests that may break (not changed by the draft): a.py, b.py: read DRAFT_REVIEW.md`, dihitung ulang
dari intake dan draf yang disetujui, bukan dibaca dari laporan drafter (seperti `changed_lines`).

## 3. Di luar cakupan

JS/vitest (belum ada AST; `src/*.test.jsx`), tes lama yang pecah karena alasan selain bentuk key/dict, penolakan draf (§4),
perbaikan otomatis draf. Draf yang menyebut berkas di `changed_tests` tidak dicurigai lagi, tanpa memeriksa isinya.

## 4. Kenapa penasihat dulu

Penolakan di cek draf menjadi umpan balik drafter; false positive yang tak bisa dihindari menghabiskan 5 submit dan berakhir
`NO_DRAFT`. Dengan sampel satu kasus kita belum tahu angka false positive. Ukur dulu di job-job nyata berikutnya (baris
`leaks` di `check_report.json`); bila tepat, usul berikutnya: tolak draf, dengan jalan keluar eksplisit.

## 5. Tes (gagal di kode lama)

1. tes baru berisi daftar key `N`, tes lama punya `O = N − {k}` dengan `k` di issue → temuan (list dan dict, masing-masing).
2. `k` tidak ada di issue → tidak ada temuan; `|N − O| = 3` → tidak ada; `|O| < 4` → tidak ada; `O = N` → tidak ada.
3. berkas lama yang diubah draf (`changed_tests`) tidak dicurigai; berkas bukan tes (`src/x.py`) tidak dipindai.
4. berkas lama tak bisa di-parse atau > 1 MiB → dilewati, tanpa error.
5. `check()` memuat `report["leaks"]`; `review_text` menampilkan bagian dan kalimatnya, dan baris "No old test looks affected".
6. layar approve dan `status` memuat baris, dihitung dari intake (draf di disk diubah → baris ikut berubah).
Mutants: syarat issue, `⊂`, batas `|N−O|`, ≥ 4, pengecualian `changed_tests`, filter berkas tes, batas ukuran, bagian review, baris approve.
