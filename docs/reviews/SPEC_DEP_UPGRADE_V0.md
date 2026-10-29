# Spek: upgrade dependency v0 untuk argus-ledger, lewat staging

Status: **draf, menunggu keputusan Atha (§6)**. Jalur ketat untuk U3 (kode staging); U1, U2 dan U4 tidak mengubah
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
`scripts/build_env_from_base.sh` dan dicek `scripts/check_env_image.py` seperti sekarang. Pin: starlette 1.10.0,
fastapi 0.162.0, `httpx2` menggantikan `httpx` (dicek: tidak ada impor `httpx` di repo), dependensi lain hasil resolusi;
staging + uvicorn/click seperti `ledger_staging`. Aturan "semua berkas diunggah ≥ 2 minggu sebelum build" tetap: starlette
1.10.0 baru boleh dipakai mulai **2026-11-07** (lihat §6.1). Environment lama tetap ada (rollback butuh image-nya).
`ledger_py312_up1` boleh masuk `web.environments` hanya bila Atha memutuskan (§6.3); default tidak.

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
  pasangannya (`ledger_staging_up1` ↔ `ledger_py312_up1`, pasangan ditulis di config). Tidak ada kombinasi yang belum dites
  yang bisa live.
- `status` menampilkan environment runtime untuk rilis live dan rilis rollback.

**U4. "Go live" per rencana, bukan per perintah** (permintaan Atha 2026-10-29: pilot staging #1 butuh 4 "go live").
Claude menulis rencana pilot sebagai daftar langkah persis (perintah dan hasil yang diharapkan) di
`pilots/<pilot>/PLAN.md` dan commit dulu. Satu "go live" Atha berlaku untuk **seluruh rencana itu**. Claude berhenti di
langkah pertama yang tidak sesuai harapan (exit ≠ 0, smoke gagal, `docker inspect` beda, `status` beda), tidak
menambah atau mengulang langkah, dan melapor. Langkah sesudah berhenti butuh "go live" baru. Ini aturan kerja (memory +
AGENTS.md), bukan kode: `--yes` tetap per perintah. Hanya staging; production tetap butuh persetujuan terpisah.

## 4. Yang dijamin (dan dites; mutants)

1. Rollback menjalankan rilis sebelumnya di image yang tercatat untuk rilis itu (tes: deploy A di image 1, deploy B di
   image 2, rollback → container A berjalan dari image 1).
2. Image tercatat hilang atau tidak lagi lolos cek → rollback/deploy ditolak, yang live tetap jalan.
3. Runtime non-default tanpa catatan U2 yang lolos untuk commit itu → deploy ditolak sebelum build/start.
4. `docker inspect` dengan image yang bukan image rilis → container baru dihentikan, yang lama tetap live.
5. Semua jaminan staging v0 (§3 SPEC_STAGING_V0) tetap berlaku; tes lama tidak diubah kecuali nama rilis.

## 5. Pilot sesudah merge (satu "go live" untuk PLAN.md)

Mulai 2026-11-07 (bila §6.1 = tunggu):
1. Bangun dan cek `ledger_py312_up1` dan `ledger_staging_up1` (tanpa model).
2. `stage check j20261029_115742_bffd --env ledger_py312_up1` → 124 lolos, tanpa deprecation.
3. `stage deploy j20261029_115742_bffd --runtime ledger_staging_up1` → smoke pass, inspect image up1.
4. `stage rollback` → 013 di image `ledger_staging` lama, smoke pass, inspect image lama.
5. `stage deploy … --runtime ledger_staging_up1` lagi → staging berakhir di stack baru.

## 6. Keputusan untuk Atha

1. **Versi:** (a) tunggu sampai 2026-11-07 agar starlette 1.10.0 memenuhi aturan 2 minggu *(saran Claude)*; atau
   (b) bangun sekarang dengan versi yang sudah 2 minggu (starlette tetap 1.8.0, upgrade hampir kosong); atau (c)
   pengecualian aturan 2 minggu untuk pilot ini. Kode U3 bisa dikerjakan dan dites sekarang dengan image tes, apa pun
   pilihannya.
2. **"Go live" per rencana (U4)**: setuju satu "go live" per PLAN.md yang ter-commit, dengan aturan berhenti di atas?
3. **Riset di image baru:** `ledger_py312_up1` masuk `web.environments` (supaya job riset bisa pakai stack baru)? Saran:
   belum, sampai ada job yang butuh.

## 7. Task agen dua lengan (ditunda)

Pertanyaan Alur A tetap terbuka: apakah riset membantu bila jawaban **tidak** ada di ingatan model? Upgrade ini tidak
menjawabnya karena tidak ada yang rusak. Kandidat yang lebih tepat: issue yang benar-benar membutuhkan API rilis baru
(mis. fitur yang hanya ada di `httpx2` atau starlette 1.10), atau upgrade berikutnya yang memang merusak tes. Dicatat di
PENDING.md sebagai kandidat, tanpa jadwal.
