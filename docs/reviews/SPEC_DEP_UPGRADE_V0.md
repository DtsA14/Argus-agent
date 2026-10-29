# Spek: upgrade dependency v0 untuk argus-ledger, lewat staging

Status: **disetujui Atha 2026-10-29** (§6). Jalur ketat untuk U3 (kode staging); U1, U2 dan U4 tidak mengubah
jaminan AGENTS.md. Alur: spek → tes yang gagal di kode lama → kode → mutants → `/code-review medium` + `/security-review`
→ `verify.sh` sekali → "merge" Atha.

## 1. Cek awal (Claude, 2026-10-29, tanpa model)

Rencana awalnya: task upgrade dependency dua lengan (dengan dan tanpa riset), dengan harapan versi baru merusak sesuatu
yang tidak ada di ingatan model. Sebelum menulis spek, Claude mencoba versi terbaru di venv lokal (scratchpad):

- PyPI hari ini: starlette 1.10.0 (2026-10-24), fastapi 0.162.0 (10-23), httpx2 2.16.0 (10-21). Yang dipakai sekarang
  (`ledger_py312`): starlette 1.8.0, fastapi 0.143.0, httpx 0.28.1.
- Tes argus-ledger di `804e13a` dengan starlette 1.10.0 + fastapi 0.162.0: **124/124 lolos**. Satu warning baru:
  `StarletteDeprecationWarning: Using httpx with starlette.testclient is deprecated; install httpx2 instead.`
- Dengan `httpx2` terpasang: **124/124 lolos dengan `-W error::DeprecationWarning`**, tanpa warning.
- argus-ledger tidak mengimpor `httpx` sendiri dan tidak punya berkas dependency; versinya ditentukan image environment.
- Yang sudah boleh dipakai hari ini (semua berkas ≥ 2 minggu): starlette 1.8.0 juga memakai `httpx2` bila terpasang;
  starlette 1.8.0 + fastapi 0.143.2 + httpx2 2.13.1 tanpa `httpx`: **124/124 lolos dengan `-W error::DeprecationWarning`**.

**Kesimpulan:** upgrade ini **tidak butuh perubahan kode** di argus-ledger. Task agen dua lengan tidak punya apa-apa
untuk diperbaiki, jadi tidak mengukur apa pun. Pekerjaan nyatanya ada di harness: image baru, bukti tes di image baru,
dan staging yang bisa men-deploy serta me-rollback **antar image runtime**. Itu yang belum bisa: `router/stage.py` memakai
satu image (`ENVIRONMENT = "ledger_staging"`) untuk deploy *dan* rollback, jadi rollback sesudah upgrade akan
menjalankan rilis lama di image baru, bukan di image yang dulu lolos smoke.

## 2. Tujuan dan batas

Upgrade stack argus-ledger ke versi baru seperti di production: image baru dibangun dan dicek, tes repo lolos di image
itu, rilis jalan di staging di atas image baru, dan rollback mengembalikan **kode dan image** lama sekaligus. Tanpa model,
tanpa biaya model. Hanya staging; athena-api (port 8000) tidak disentuh.

Bukan bagian spek ini: task agen dua lengan (ditunda sampai ada upgrade yang benar-benar merusak sesuatu, lihat §7).

## 3. Perubahan

**U1. Environment baru `ledger_py312_up1` dan `ledger_staging_up1`** (`environments/…`), dibangun dengan
`scripts/build_env_from_base.sh` dan dicek `scripts/check_env_image.py` seperti sekarang. Pin = `ledger_py312`, kecuali
fastapi 0.143.0 → 0.143.2, dan `httpx` 0.28.1 (+ httpcore, certifi) diganti `httpx2` 2.13.1 (+ httpcore2 2.13.1,
truststore 0.10.5); staging + uvicorn/click seperti `ledger_staging`. Semua berkas diunggah sebelum 2026-10-16 (aturan 2
minggu tetap). Environment lama tetap ada (rollback butuh image-nya). Tidak masuk `web.environments` (§6.3).
Upgrade 2 (`up2`: starlette 1.10.0, fastapi 0.162.0) mulai **2026-11-07**, dengan langkah yang sama (§6.1).

**U2. Bukti tes di image baru (tanpa model).** Harness menjalankan suite repo pada commit rilis di sandbox
`ledger_py312_up1` (flag isolasi sama dengan validasi job), dengan `-W error::DeprecationWarning`, dan mencatat hasilnya
(commit, image id, jumlah lolos/gagal, waktu) di `~/argus-staging/env_checks.jsonl`. Perintah: `argus stage check <job>
--env ledger_py312_up1`.

**U3. Rilis = (commit, image runtime).** (jalur ketat)
- `argus stage deploy <job> [--runtime ledger_staging_up1]`; default tetap `ledger_staging`. Image runtime yang dipakai
  dicatat di rekaman rilis (`releases.jsonl`: environment dan image id).
- Nama rilis memuat environment runtime, sehingga commit yang sama di dua image adalah dua rilis berbeda.
- `rollback` menjalankan rilis sebelumnya **dengan image yang tercatat di rekamannya**, bukan image default. Image itu
  harus masih ada dan masih lolos `check_env_image` (pin di config sama dengan id tercatat); bila tidak → ditolak, yang
  live tetap jalan.
- `docker inspect` membandingkan image container dengan image **rilis itu**.
- Deploy dengan runtime selain default ditolak kecuali ada catatan U2 yang lolos untuk commit itu di environment sandbox
  pasangannya (`ledger_staging_up1` ↔ `ledger_py312_up1`, pasangan di `RUNTIMES` di `router/stage.py`: menambah runtime adalah
  perubahan kode jalur ketat). Runtime di luar `RUNTIMES` (mis. `argus`, `ledger_py312_up1`) ditolak. Tidak ada kombinasi yang belum dites
  yang bisa live.
- `status` menampilkan environment runtime untuk rilis live dan rilis rollback.

**U4. "Go live" per rencana, bukan per perintah** (permintaan Atha 2026-10-29: pilot staging #1 butuh 4 "go live").
Claude menulis rencana pilot sebagai daftar langkah persis (perintah dan hasil yang diharapkan) di
`pilots/<pilot>/PLAN.md` dan commit dulu. Satu "go live" Atha berlaku untuk **seluruh rencana itu**. Claude berhenti di
langkah pertama yang tidak sesuai harapan (exit ≠ 0, smoke gagal, `docker inspect` beda, `status` beda), tidak
menambah atau mengulang langkah, dan melapor. Langkah sesudah berhenti butuh "go live" baru. Ini aturan kerja (memory), bukan kode: `--yes` tetap per perintah. Hanya staging; production tetap butuh persetujuan terpisah.

## 4. Yang dijamin (dan dites; mutants)

1. Rollback menjalankan rilis sebelumnya di image yang tercatat untuk rilis itu (tes: deploy A di image 1, deploy B di
   image 2, rollback → container A berjalan dari image 1).
2. Image tercatat hilang atau tidak lagi lolos cek → rollback/deploy ditolak, yang live tetap jalan.
3. Runtime non-default tanpa catatan U2 yang lolos untuk commit itu → deploy ditolak sebelum build/start.
4. `docker inspect` dengan image yang bukan image rilis → container baru dihentikan, yang lama tetap live.
5. Semua jaminan staging v0 (§3 SPEC_STAGING_V0) tetap berlaku; tes lama tidak diubah kecuali nama rilis.

## 5. Pilot sesudah merge (satu "go live" untuk PLAN.md)

1. Image `ledger_py312_up1` dan `ledger_staging_up1` sudah dibangun dan lolos cek (2026-10-29, §7).
2. `stage check j20261029_115742_bffd --env ledger_py312_up1` → 124 lolos, tanpa deprecation.
3. `stage deploy j20261029_115742_bffd --runtime ledger_staging_up1` → smoke pass, inspect image up1.
4. `stage rollback` → 013 di image `ledger_staging` lama, smoke pass, inspect image lama.
5. `stage deploy … --runtime ledger_staging_up1` lagi → staging berakhir di stack baru.

## 6. Keputusan Atha (2026-10-29)

1. **Versi: upgrade sekarang dengan yang sudah 2 minggu** (`up1`: httpx2 + fastapi 0.143.2); starlette 1.10.0 menyusul
   sebagai `up2` mulai 2026-11-07. Aturan 2 minggu tidak dikecualikan.
2. **Satu "go live" per PLAN.md yang ter-commit** (U4), dengan aturan berhenti di langkah pertama yang meleset.
3. **`ledger_py312_up1` tidak masuk `web.environments`** sampai ada job yang butuh.

## 7. Implementasi (2026-10-29)

- U1: `environments/ledger_py312_up1/` dan `environments/ledger_staging_up1/` (README per environment), entri di
  `config.yaml`. Image `ledger_py312_up1` `sha256:59288cff2053…`, `ledger_staging_up1` `sha256:4edca09d1842…`, keduanya
  lolos `check_env_image.py` (isolasi, klasifikasi, red check, koleksi, tanpa shell/git/pip, versi).
- U2: `argus stage check <job> --env E` (`router/stage.check`): `git archive` commit applied (dicek terhadap tree
  commit), pytest di sandbox E dengan flag validasi (workspace read-only, `PYTEST_FIXED`) plus
  `-W error::DeprecationWarning`. Lolos hanya bila exit 0, outcome OK, output konsisten, ≥ 1 tes, tidak ada yang skip,
  tidak timeout/terpotong. Dicatat di `~/argus-staging/env_checks.jsonl` (lolos atau tidak); salinan sumber dihapus.
  Exit CLI 0 lolos, 1 gagal, 2 ditolak. Dicoba (staging sementara) pada 013 (`804e13a`) di `ledger_py312_up1`: 124 lolos.
- U3: `RUNTIMES` di `router/stage.py`; nama rilis `<job>-<commit12>` (default) atau `<job>-<commit12>.up1`; rekaman
  `built` menyimpan `runtime` dan `image`. Deploy: runtime harus di `RUNTIMES` dan lolos `check_env_image`; selain default
  butuh `stage check` terakhir untuk (commit, environment pasangan, image sandbox sekarang) yang lolos; rilis yang sudah
  dibangun untuk image lain ditolak sebelum konfirmasi. Rollback: runtime dan image dari rekaman rilis itu; image berubah →
  ditolak, yang live tetap. Rilis staging v0 (tanpa `image`) berjalan di image pin `ledger_staging` sekarang. `status`
  menyebut runtime.
- Tes `tests/test_stage.py` (+15): rollback maju-mundur antar runtime memakai image rekaman; image berubah ditolak (juga
  deploy ulang); lima variasi check yang tidak cukup; runtime asing; check hanya di environment pasangan yang ter-resolve;
  dengan docker: check lolos, gagal karena deprecation, gagal karena skip, dan deploy → upgrade → rollback di container
  sungguhan dengan `docker inspect` image. Mutants 18/18. Suite `tests/` (-n 4 --dist loadgroup): 1946 passed.
- Dihapus karena tidak terjangkau (mutant selamat): cek runtime di `image_changed` (runtime bagian dari nama rilis) dan
  cek keanggotaan `RUNTIMES` di `tested`/`release_name` (sudah di `runtime_image`, yang dipanggil lebih dulu).

## 8. Task agen dua lengan (ditunda)

Pertanyaan Alur A tetap terbuka: apakah riset membantu bila jawaban **tidak** ada di ingatan model? Upgrade ini tidak
menjawabnya karena tidak ada yang rusak. Kandidat yang lebih tepat: issue yang benar-benar membutuhkan API rilis baru
(mis. fitur yang hanya ada di `httpx2` atau starlette 1.10), atau upgrade berikutnya yang memang merusak tes. Dicatat di
PENDING.md sebagai kandidat, tanpa jadwal.
