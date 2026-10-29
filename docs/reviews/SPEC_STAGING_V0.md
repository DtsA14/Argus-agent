# Spek: staging v0, target deployment minimal untuk argus-ledger

Status: **disetujui Atha 2026-10-29** (§5). Jalur ketat: langkah pertama Argus yang punya efek di luar sandbox
(container yang terus berjalan di VM). Berlaku penuh AGENTS.md: spek → tes yang gagal di kode lama → kode → mutants →
`/code-review medium` + `/security-review` → `verify.sh` sekali → "merge" Atha.

## 1. Kenapa, dan batasnya

Tujuan: rute end-to-end riset → handoff → draft → agen → review → **release candidate → staging → smoke → rollback**.
Hari ini Argus berhenti di review package; argus-ledger tidak pernah berjalan sebagai server (hanya TestClient di sandbox,
`uvicorn` tidak ada di image). Staging ini dibangun **tanpa model**: tidak ada biaya model, dan agen tidak pernah mendapat
tool deploy. Deploy adalah langkah harness yang dijalankan manusia (atau Claude sesudah "go live"), sesudah `applied`.

Bukan production: tidak ada pengguna, tidak ada DNS/TLS, tidak ada kredensial. API Athena di port 8000 VM yang sama tidak
disentuh (nama container, port, dan direktori sendiri).

## 2. Perubahan

**S1. Image runtime `ledger_staging`** (environment baru di `environments/ledger_staging/`): base sama dengan
`ledger_py312` (digest dipin), requirements = semua pin `ledger_py312` + `uvicorn` dan dependensinya (`click`), versi
terbaru yang semua berkasnya diunggah ≥ 2 minggu sebelum build, dengan hash. Dibangun dengan
`scripts/build_env_from_base.sh` dan dicek `scripts/check_env_image.py` seperti environment lain. Tetap distroless (tanpa
shell, pip, git).

**S2. Release candidate.** `argus stage build <job>` untuk job `APPLIED`: commit target = commit `applied`. Harness:
`git archive <commit>` repo target → direktori rilis `~/argus-staging/releases/<job>/src` (read-only), entry module dari
harness `staging_app.py` (bukan dari repo: `app = create_app("/data/jobs", allowed_hosts=["staging.local"])`), data
fixture `~/argus-staging/data/jobs` (salinan job sintetis dari tes, bukan job nyata). Dicatat di
`~/argus-staging/releases.jsonl`: job, commit, sha256 tree sumber, image id runtime, waktu. Tidak ada image baru per rilis:
sumber di-mount read-only ke image runtime yang sudah dicek.

**S3. Deploy staging.** `argus stage deploy <job>` (layar konfirmasi + "go live", seperti `live()` tetapi tanpa key):
container `argus-staging-ledger` dengan `--network none`, `--read-only`, `--cap-drop ALL`,
`--security-opt no-new-privileges`, user non-root, batas memori/pids, mount `src` dan `data` read-only, satu direktori
socket tulis. Uvicorn mendengar di **Unix socket** (`--uds /run/argus/app.sock`), bukan TCP: tidak ada jaringan sama
sekali, dan smoke test datang dari luar container (host) lewat socket. Container sebelumnya dihentikan hanya sesudah yang
baru lolos smoke (lihat S4); keduanya tidak pernah memakai socket yang sama (direktori per rilis).

**S4. Smoke test.** Harness memanggil lewat socket dengan `Host: staging.local`: `GET /summary` → 200 JSON dengan kunci
`jobs, cost_nano, cost_usd, skipped`; `GET /jobs` → 200 list; `GET /ui` → 200 HTML; `Host: evil.example` → 400
(pengaman issue 013 di production setting). Ditambah cek per task bila kontrak menyebutnya (v0: tidak). Gagal → container
baru dihentikan, yang lama tetap berjalan, rilis dicatat `smoke_failed`.

**S5. Rollback.** `argus stage rollback`: jalankan rilis `live` sebelumnya dari `releases.jsonl` (sumbernya masih ada,
read-only), smoke test yang sama, lalu hentikan yang sekarang. Rollback **diuji**: tes otomatis dan sekali di pilot.

**S6. Status.** `argus stage status`: rilis yang live (job, commit, sejak), hasil smoke terakhir, rilis sebelumnya untuk
rollback. Log container (`docker logs`, 200 baris terakhir) disalin ke direktori rilis sesudah smoke dan sesudah stop.

## 3. Yang dijamin (dan dites; mutants)

1. Hanya commit job `APPLIED` yang bisa di-build; sumber = `git archive` commit itu (sha256 tree dicatat dan dicek saat
   deploy; berubah → ditolak).
2. Container berjalan tanpa jaringan dan read-only (dicek dari `docker inspect` sesudah start; berbeda → dihentikan dan
   ditolak).
3. Smoke gagal → yang lama tetap live, yang baru dihentikan.
4. Rollback mengembalikan rilis sebelumnya dan lolos smoke; tanpa rilis sebelumnya → ditolak.
5. Tidak ada perintah yang menyentuh container, port, atau direktori lain (nama tetap `argus-staging-ledger*`).
6. Agen, drafter, dan riset tidak punya tool stage; `stage` tidak memanggil model.

## 4. Pilot sesudah merge (butuh "go live")

1. Deploy fix 013 (job `j20261029_115742_bffd`, commit `804e13a`): smoke lolos, termasuk `evil.example` → 400.
2. Deploy rilis kedua (misalnya commit sebelumnya `324012a` sebagai job lama yang applied, atau rilis berikut), lalu
   **rollback** ke 013 dan smoke lagi.
3. Sesudah itu baru task upgrade dependency dua lengan melewati staging (spek terpisah; image environment baru).

## 5. Keputusan Atha (2026-10-29)

1. **Unix socket tanpa jaringan** untuk pilot pertama: permukaan serangan minimal; jaringan tidak ditambah hanya demi
   kemiripan dengan production.
2. **Job sintetis dari fixture tes**, bukan salinan job nyata; fixture cukup untuk jalur sukses, gagal, dan rollback.
3. **Claude boleh men-deploy sesudah "go live" untuk setiap deployment**, hanya ke staging, hanya artefak yang sudah
   direview, dan rollback harus tersedia. Production sungguhan butuh persetujuan terpisah dari Atha.

Tujuan pilot: membuktikan research → coding → acceptance → deployment staging end-to-end dengan akses minimum dan hasil
yang bisa diverifikasi.

## 6. Implementasi (2026-10-29)

- `environments/ledger_staging/` (S1): pin `ledger_py312` + `uvicorn==0.54.0`, `click==8.5.0` (berkas diunggah sebelum
  2026-10-15, wheel py3 dengan hash). Image `sha256:4ab2ff53a34f…` dibangun `build_env_from_base.sh`, lolos
  `check_env_image.py` (isolasi, tanpa shell/git/pip, versi). Terdaftar di `sandbox.environments`, **tidak** di
  `web.environments`.
- `router/stage.py`: `deploy` = build (sekali, lalu dicek setiap kali) + konfirmasi + start + `docker inspect` + smoke +
  switch; `rollback`; `status`. Hanya job `APPLIED` dengan `as_is: true` (patch yang direview, apa adanya). Rilis dibangun
  dari `git archive` commit itu, read-only; entry `staging_app.py` dari harness; data = salinan baru
  `fixtures/staging/jobs` per start, read-only. Container `argus-staging-ledger-<rilis>` dengan label rilis; hanya nama
  itu yang pernah dihentikan.
- Isolasi diperiksa dari `docker inspect` sebelum smoke: `NetworkMode none`, root read-only, `CapDrop ALL` tanpa
  `CapAdd`, `no-new-privileges`, tidak privileged, user bukan root, image = image runtime yang dicek, label rilis, tepat
  empat mount (`/app`, `/entry`, `/data` read-only; `/run/argus` tulis). Selain itu: dihentikan dan ditolak.
- Smoke (S4) dari host lewat socket: `/summary` = angka fixture persis (2 job, 2.500.000 nano), `/jobs` = dua id,
  `/ui` HTML, `Host: evil.example` → 400. Socket dihubungkan lewat fd direktori (`/proc/self/fd`), karena path socket
  maksimal 107 byte.
- CLI: `argus stage deploy <job> [--yes]`, `argus stage rollback [--yes]`, `argus stage status`. `--yes` = "go live" di
  chat (tidak ada key di langkah ini).
- Tes `tests/test_stage.py` (30, modul sandbox: dilewati = gagal di `verify.sh`): penolakan job, sumber yang berubah,
  nama container asing, setiap syarat isolasi, setiap cek smoke, konfirmasi; dengan docker sungguhan: deploy, rilis
  rusak gagal smoke dan yang lama tetap live, rilis kedua, rollback, tanpa rilis sebelumnya ditolak, dan dari dalam
  container tidak ada jaringan dan tidak bisa menulis. Mutants 21/21.
