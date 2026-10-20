# M6 W3: paket review tanpa LLM

Status: **implementasi untuk review.** 2026-10-20. Rencana: `docs/reviews/M6_PLAN.md` W3. Tanpa model, tanpa run live.
Kode: `codetask/review.py`, `scripts/build_review.py`, `tests/test_review.py`.

## 1. Apa yang dihasilkan

Untuk run berstatus `DONE`, `python scripts/build_review.py --run runs/<id> [--repo PATH]` menulis `runs/<id>/review/`:

| File | Isi |
|---|---|
| `changes.patch` | patch Git dari tree commit dasar ke workspace akhir agen (`SUMMARY.json` tidak ikut). Untuk task yang disetujui, tes baru ikut sebagai file baru, jadi ini seluruh isi PR |
| `tests.md` | setiap kriteria verdict, dan setiap validasi kontrak yang dijalankan **ulang** di sandbox pada commit dasar + patch |
| `claims.md` | klaim agen dan verdict harness atas tiap klaim, ringkasan bebas agen (diberi label bukan bukti), dan catatan "tidak diverifikasi otomatis" dari persetujuan |
| `provenance.json` | repo, commit dasar dan tree, commit Argus (dan apakah berubah), sha256 kontrak, model, biaya dari ledger, hash patch, dan setiap cek dengan hasilnya |
| `PR.md` | draf deskripsi PR; kalau paket tidak valid, baris pertamanya `NOT READY` dengan alasannya |

Paket ditulis ke direktori sementara lalu di-rename, tidak pernah menimpa paket yang ada, dan tidak memuat timestamp:
membangun dua kali menghasilkan byte yang sama (dikunci tes). Exit code skrip: 0 valid, 1 ditulis tapi tidak valid,
2 ditolak (run bukan `DONE`, paket sudah ada).

## 2. Penyimpangan dari rencana (dan alasannya)

1. **Patch dari tree commit dasar, bukan dari snapshot intake.** Untuk task, snapshot sudah berisi tes yang disetujui.
   Patch dari snapshot tidak memuat tes itu, padahal PR harus memuatnya. Patch dari tree commit dasar memuat tes itu
   sebagai file baru, jadi satu `git apply` pada checkout commit dasar menghasilkan seluruh PR. Tes yang disetujui
   ditandai `approved_test` dan dicek harus persis sama dengan hash di record.
2. **Tree commit dasar dibangun ulang dengan `write_tree` milik intake, bukan `git worktree add`.** Isi yang sama
   (tanpa pengecualian intake, tanpa konversi `.gitattributes`), tanpa menambah worktree ke `.git` repo pengguna.
   Tree-nya dicocokkan dengan `tree` di record.

## 3. Cek yang menentukan `valid`

Berurutan; cek yang gagal menghentikan cek berikutnya (dicatat sebagai gagal, tidak diam-diam dilewati).

| Cek | Apa yang dibuktikan |
|---|---|
| `contract_frozen` | kontrak beku di run dir masih punya hash yang tercatat |
| `verdict_passed` | verdict terakhir `pass` **dan** berlaku untuk workspace akhir persis (digest workspace sama) |
| `summary_bound` | `SUMMARY.json` dibaca **sekali**, hash-nya sama dengan `summary_sha256` di verdict, dan teks yang diterbitkan di `claims.md` / `PR.md` berasal dari bytes yang sama (tidak dibaca ulang saat build) |
| `input_unchanged` | repo input masih sama dengan saat run mulai (hash snapshot) dan lolos cek record intake. Tanpa record intake tidak ada commit dasar, jadi tidak ada paket |
| `base_commit` | commit dasar yang dibangun ulang dari repo, ditambah tes yang disetujui, sama persis dengan input (path, isi, bit executable); tree-nya sama dengan record; input tidak sudah berisi `SUMMARY.json` |
| `changes_in_scope` | yang diubah agen ada di scope `writable`, tidak `protected`, bukan path yang dikecualikan intake, bukan di dalam `.git`, dan semuanya file biasa. Dihitung sendiri, tidak mengandalkan verdict |
| `changes_match_verdict` | daftar file berubah sama persis dengan daftar di verdict (perubahan mode saja tidak terlihat verdict, jadi ditolak) |
| `patch_made` | patch tidak kosong (tak ada perubahan berarti tak ada paket) |
| `patch_applies` | `git apply --check` lalu `git apply` pada rebuild bersih commit dasar, seperti yang dilakukan reviewer |
| `final_state_identical` | seluruh file (path, isi, bit executable) di tree hasil apply sama persis dengan workspace akhir, termasuk file yang tidak berubah, jadi file yang seharusnya terhapus tapi tertinggal ikut tertangkap |
| `revalidation_matches` | tiap validasi kontrak, dijalankan ulang di sandbox pada tree hasil apply, lulus dan mengulang hasil verdict (status, jumlah tes, hasil tiap tes wajib) |
| `workspace_stable` | setelah semua cek di atas selesai, workspace run masih persis keadaan yang dilihat verdict (digest sama): tidak ada yang menulis ke dalamnya selama paket dibangun |

Cara membuat patch (`make_patch`): tree commit dasar disalin ke repo Git baru dengan satu commit; lalu **dicerminkan**:
semua file dihapus, isi workspace akhir disalin masuk, `git add -A -f` (file yang di-`.gitignore` tetap ikut), dan
`git diff --cached --binary --full-index --no-renames`. Git berjalan tanpa config pengguna atau sistem, tanpa hook, dan
dengan atribut dimatikan (`* -text -ident -filter` di `.git/info/attributes`, yang mengalahkan `.gitattributes` repo),
jadi tidak ada byte yang dikonversi. Tidak ada kode repo yang dijalankan.

## 4. Tes dan mutan

`tests/test_review.py` (46 tes): run dibuat tangan dari intake sungguhan atas repo Git kecil, verdict nyata dari
`evaluate`, validasi yang membaca tree yang diberikan (tanpa sandbox); satu tes dengan sandbox `argus` sungguhan;
dua tes end-to-end dengan model palsu lewat `run_code_task` (VM).

- file baru, berubah, **terhapus**, di-`.gitignore`, binary, CRLF dengan `.gitattributes` yang mengonversi, bit
  executable, nama file dengan `|`;
- penolakan: run bukan `DONE`, paket sudah ada, build gagal tidak meninggalkan sisa, verdict gagal, workspace berubah
  setelah verdict, kontrak beku berubah, input berubah, tanpa record intake, repo tanpa commit dasar, tree tidak cocok,
  perubahan di file protected / di luar writable / di path yang dikecualikan / di dalam `.git` / symlink (juga bila
  file verdict diedit menjadi `pass`), tes yang disetujui diubah, tes baru yang sudah ada di commit dasar, perubahan
  mode saja, tidak ada perubahan, verdict yang menyebut file lain;
- patch yang diverifikasi, tidak dipercaya: mirror yang tidak menghapus, patch yang tidak bisa diterapkan, patch yang
  mengubah file yang tidak disentuh agen, validasi ulang pada tree hasil apply (bukan workspace run, tanpa
  `SUMMARY.json` dan `.git`), hasil segar yang berbeda dari verdict, validasi segar gagal atau diblok;
- markdown: ringkasan agen tidak bisa menutup fence-nya; `|` di sel tidak merusak tabel; catatan "tidak diverifikasi
  otomatis" tampil dan tidak pernah menjadi kriteria;
- end-to-end: task yang disetujui, model palsu memperbaiki, paket valid, biaya dan model sama dengan ledger; agen yang
  mencoba mengubah tes yang disetujui ditolak tool-nya, run `FAILED_ACCEPTANCE`, tidak ada paket.

Mutan (`verification/mutants-w3-38305ca.log`): **47/47 tertangkap** pada commit `38305ca`, dan **50/50** pada `7ca1935` setelah perbaikan review di bagian 4a (`verification/mutants-w3-7ca1935.log`). Putaran pertama 42/47;
lima yang lolos adalah celah tes, bukan kode yang ekuivalen, dan ditutup dengan tes baru:
- cek `intake.check` dan cek hash run pada `input_unchanged` saling menutupi bila satu-satunya tes mengubah input
  (sekarang dua tes yang masing-masing hanya bisa ditangkap salah satunya);
- patch kosong (`patch_made`) tidak pernah dicapai karena cek "tidak ada perubahan" lebih dulu, dan `git apply` atas
  patch kosong gagal juga, jadi paket tetap tidak valid tetapi dengan nama cek yang lain; sekarang dikunci dengan nama cek;
- validasi segar yang gagal atau diblok ditandai lewat dua baris yang tumpang tindih; sekarang pesannya dikunci;
- `must_pass` yang berbeda dengan hitungan dan hasil yang sama tidak dibandingkan; sekarang ada tesnya.
Mutan mencakup: cermin yang tidak menghapus, `add` tanpa `-f`, atribut Git aktif, patch tanpa `--binary`, `SUMMARY.json`
di patch, setiap cek pada tabel di atas dilepas satu per satu, perbandingan tree yang hanya untuk file berubah,
validasi ulang pada workspace run (bukan tree hasil apply), paket untuk run bukan DONE, paket ditimpa, sisa build
gagal, fence dan `|` di markdown, catatan "tidak diverifikasi otomatis" hilang, model/biaya hilang, bit executable
diabaikan, dan banner NOT READY hilang.

## 4a. Temuan review GPT dan perbaikannya

GPT (membaca extract `verify()` dan `build()`) tidak menemukan jalur scope yang lolos, tetapi menunjuk satu risiko
konsistensi waktu: `build()` membaca `SUMMARY.json` lagi setelah `verify()`, dan workspace tidak dicek ulang setelah
patch dibuat. Direproduksi dulu sebagai tes yang gagal (paket tetap `valid` bila `SUMMARY.json` atau file sumber
ditulis ulang setelah patch dibuat), lalu diperbaiki dengan dua cek: `summary_bound` dan `workspace_stable`. Patch
yang diterbitkan tidak pernah berbeda dari yang diverifikasi (bytes yang sama dikembalikan `verify()`); yang
ditutup adalah teks klaim dari keadaan lain dan paket yang menyatakan `valid` untuk workspace yang sudah berubah.

Verify penuh pada `7ca1935`: 1150 passed, 0 sandbox skip, tree bersih (`verification/verify-20261020T164449Z-aarch64.log`).

## 5. Batas

- Paket persis pada level byte yang di-commit. Repo yang `.gitattributes`-nya mengonversi akhir baris atau menjalankan
  filter saat checkout bisa menampilkan patch yang sama secara berbeda di working tree reviewer; tidak terdeteksi
  (repo Argus tidak punya `.gitattributes`).
- Validasi ulang memakai sandbox dan image yang sama dengan run. Hasil segar yang berbeda karena tes flaky membuat
  paket tidak valid, dan itu disengaja: pilot butuh tes yang stabil.
- `--repo` harus repo yang memuat commit dasar (default: checkout Argus). Commit yang tidak ada di sana ditolak.
- Status hasil pilot (agent-completed / human-assisted / failed) tetap keputusan reviewer; `PR.md` hanya menjelaskan
  syaratnya. Argus tidak membuka PR.
- Biaya dibaca dari ledger; kalau ada model tak berharga, `usd_complete` false dan `PR.md` mengatakannya.
- `workspace_stable` menjamin workspace sama dengan yang dilihat verdict **pada akhir `verify()`**, bukan pada detik
  paket dipublikasikan: masih ada jendela kecil sampai rename `review.tmp` menjadi `review/`. Patch dan teks yang
  diterbitkan sudah dibuat dari keadaan yang diperiksa, jadi perubahan di jendela itu tidak mengubah isi paket, tetapi
  `valid` menyatakan snapshot yang diperiksa. Cukup untuk pilot internal (tidak ada proses lain yang menulis ke run
  dir). Kalau suatu saat workspace bisa diubah proses yang tidak dipercaya secara bersamaan, perlu snapshot immutable
  atau kunci; tidak ditambahkan sekarang (disetujui GPT 2026-10-21 untuk scope pilot).
