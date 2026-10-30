# Spek: staging argus-ledger dengan data Argus asli, dan monitoring sesudah deploy

Status: **disetujui Atha 2026-10-30** (opsi a: tetap tanpa jaringan; keputusan dan tambahan di §5, §6). Jalur ketat (`router/stage.py`,
data asli). Menutup gap M9 "data staging sintetis" dan "tidak ada monitoring setelah deploy selain smoke", dan sebagian
gap M5 (dashboard biaya dan keputusan dari ledger asli).

## 1. Cek awal (Claude, 2026-10-30)

- `jobs/` di `~/pilot3a_live`: 54 job, 5,0 GB, tetapi yang dibaca argus-ledger (`job.json` + `runs/*/events.jsonl`)
  hanya **6,7 MB**; sisanya salinan repo target (`root/`) yang tidak ikut.
- Isi event: hanya metadata (token, biaya, status, langkah, sandbox); **tidak ada teks model, prompt, atau isi berkas**.
  `job.json`: issue, path lokal, log keputusan. Pindai pola key (`sk-…`, `sk-ant-…`, `api_key=…`): **0 temuan**.
- argus-ledger `summary` di salinan itu: 54 job, $4,1768. Harness (`router.job.spent_nano` per job, kode terpisah):
  54 job, 4.176.849.024 nano = **sama**. Jadi smoke di data asli bisa membandingkan angka argus-ledger dengan
  perhitungan harness sendiri.

## 2. Perubahan

**D1. Snapshot data asli** (`argus stage refresh`, tanpa model): salin **hanya** `jobs/<id>/job.json` dan
`jobs/<id>/runs/<run>/events.jsonl` (berkas biasa, bukan symlink, id dan nama run sesuai pola Argus) ke
`~/argus-staging/data/snap-<UTC>/jobs`, read-only. Ditolak (snapshot dibuang, yang lama tetap) bila ada pola key.
`~/argus-staging/data/jobs` adalah symlink relatif ke `snap-<UTC>/jobs` terbaru, ditukar atomik (`rename`); dua
snapshot terakhir disimpan.

**D2. Container membaca snapshot**, bukan fixture: `/data` = `~/argus-staging/data` read-only (bukan lagi salinan
fixture per rilis). Entry harness **tidak berubah** (`create_app("/data/jobs", …)`): `/data/jobs` adalah symlink ke
snapshot terbaru dan dibaca per request, jadi refresh terlihat tanpa restart. Karena entry sama, rilis lama (6606, 013,
013 `.up1`) tetap bisa di-rollback dan langsung melayani data asli. Fixture `fixtures/staging/jobs` tetap untuk tes.

**D3. Smoke dari snapshot:** angka yang diharapkan dihitung harness dari snapshot yang sama, saat smoke:
`/summary` = {jobs: jumlah job, cost_nano: Σ `spent_nano`, skipped: 0}; `/jobs` = himpunan id snapshot; `/ui` HTML;
`Host: evil.example` → 400. Berbeda → smoke gagal (bug di argus-ledger *atau* di definisi biaya; keduanya perlu dilihat).

**D4. Monitoring** (`argus stage monitor`, tanpa model): refresh (D1) lalu smoke (D3) terhadap rilis live, tanpa
mengubah container. Hasil di `~/argus-staging/monitor.jsonl` (waktu, rilis, snapshot, lolos/gagal per cek, angka);
`stage status` menampilkan monitor terakhir dan berapa gagal berturut-turut. Dijalankan berkala oleh timer (§5.1).
Gagal → hanya dicatat dan terlihat di `status`; **tidak ada rollback otomatis**.

**D5. Laporan untuk Atha** (opsi a): `argus stage report` mengambil `/summary`, `/jobs` dan `/ui` lewat socket dan
menyimpan HTML statis + ringkasan teks di `~/argus-staging/reports/<UTC>/`; Claude mengirimkan berkasnya ke Atha. Tidak
ada port, tidak ada jaringan.

## 3. Yang dijamin (dites; mutants)

1. Snapshot hanya berisi `job.json` dan `events.jsonl` berpola Argus; symlink, berkas lain, dan path di luar `jobs/`
   tidak pernah tersalin; pola key → refresh ditolak, snapshot lama tetap `current`.
2. Container tetap tanpa jaringan, read-only, `/data` read-only (dicek `docker inspect`, seperti sekarang).
3. Smoke gagal bila jumlah job, id, atau `cost_nano` argus-ledger berbeda dari perhitungan harness.
4. `monitor` tidak pernah memulai, menghentikan, atau mengganti container; gagal → tercatat, status menyebutnya.
5. `report` hanya membaca lewat socket.

## 4. Pilot (satu PLAN.md, satu "go live")

Refresh → deploy ulang 013 `.up1` (rilis yang sama, sekarang dengan `/data` asli) → smoke angka asli → monitor
sekali → report dikirim ke Atha → pasang timer → cek monitor pertama dari timer. Sesudahnya (jalur cepat, "go live" per
job): issue 014 untuk agen Argus, mis. ringkasan keputusan manusia per job dari `job.json` (confirmed, approved, retry,
applied) di `/jobs/<id>` dan `/ui`.

## 5. Keputusan Atha (2026-10-30)

1. **Timer `systemd --user` tiap 15 menit.** Tidak boleh ada eksekusi tumpang tindih. Refresh gagal → snapshot valid
   terakhir tetap dipakai dan container tidak diubah.
2. **Issue 014 ditulis Claude**, mengikuti format issue sebelumnya.
3. Sebelum implementasi ditambahkan (§6): allowlist schema field (tidak hanya pola secret), snapshot konsisten dan
   divalidasi sebelum dipublikasikan dengan penggantian symlink atomik, perlindungan refresh bersamaan, HTML escaping dan
   pembatasan akses report, kegagalan monitoring tidak mengganggu container atau snapshot aktif.
4. Sesudah implementasi: tes kegagalan dan concurrency, security review, `verify.sh`. **Tidak di-merge sebelum Atha
   mereview.**

## 6. Tambahan (dijamin dan dites; mutants)

**A1. Allowlist schema, bukan hanya pemindaian.** Snapshot adalah **proyeksi**, bukan salinan: harness membaca setiap
berkas, membangun objek baru hanya dari field yang diizinkan, memeriksa tipe dan pola setiap field, lalu menulis JSON
baru. Field lain tidak pernah ditulis. Pemindaian pola key tetap dijalankan atas hasil proyeksi (lapis kedua).
- `job.json`: `job` (pola id Argus), `kind`, `state` (`^[A-Z_]{1,30}$`), `created_at` (timestamp UTC), `max_usd`
  (angka/string desimal); `stages`: nama `^[a-z][a-z0-9_]{0,20}$` → {`kind`, `run_id` (pola run), `status`,
  `started_at`, `ended_at`, `usd`}; `log`: daftar {`at`, `what` (∈ himpunan tetap: created, intaken, state, approved,
  limits_shown, confirmed, confirmed_by_flag, key_typed, key_from_file, retry, redraft, staged, research_ok, applied),
  `old`, `new`, `stage`}. **Dibuang:** `inputs` (issue, repo, path), `approval`, `intake`, `environment_image`, catatan
  bebas (`reason`, `note`, `screen`, `path`, `files`, `commit`, sha), semua field lain.
- `events.jsonl`: hanya `llm_call_started` {`call_id`, `worst_usd_nano`, `worst_tokens`, `model`, `node`, `role`, `ts`},
  `llm_call` {`call_id`, `status`, `usd_nano`, `tokens`, `input_tokens`, `output_tokens`, `cache_read`, `est_input`,
  `model`, `node`, `role`, `ts`}, `attempt_end` {`reason` (`^[a-z_]{1,40}$`), `steps`, `node`, `ts`}. Event lain
  dibuang. Bilangan: int ≥ 0 (atau null bila Argus menulis null); string: pola tetap dan panjang maksimum.
- Field yang diizinkan dengan tipe/pola salah → **job itu dikeluarkan** dari snapshot dan dicatat di manifest
  (`excluded`: id + sebab, tanpa isi); snapshot tetap terbit dengan job lain.

**A2. Konsistensi dan validasi sebelum publikasi.** Satu job dibaca utuh: `job.json` dibaca sebelum dan sesudah semua
`events.jsonl`-nya (sha sama dan ukuran log tidak menyusut), kalau tidak diulang (maks. 3) lalu dikeluarkan. Baris
terakhir log yang terpotong diabaikan (penulis yang sedang menulis). Lalu, **sebelum publikasi**, di direktori
sementara: setiap job proyeksi divalidasi ulang terhadap schema; **biaya per job dari proyeksi = biaya dari berkas
asli** (`reconcile_ledger`, kode harness), berbeda → job dikeluarkan; pindai pola key; manifest (`manifest.json`: waktu,
jumlah job, total nano, `excluded`, sha per berkas). Gagal di tahap mana pun → direktori sementara dihapus, `jobs` tetap
menunjuk snapshot lama. Lolos → direktori di-rename ke `snap-<UTC>`, dibuat read-only, lalu symlink baru dibuat dan
di-`rename` atas `data/jobs` (atomik). Snapshot yang ditunjuk `jobs` tidak pernah dihapus.

**A3. Tidak ada refresh/monitor bersamaan.** `refresh` dan `monitor` memegang `flock` non-blocking pada
`~/argus-staging/data/.refresh.lock`; sibuk → keluar dengan catatan `skipped: busy`, tanpa menyentuh apa pun. Unit
systemd `Type=oneshot` (systemd tidak memulai instance kedua selagi yang pertama aktif) dengan `TimeoutStartSec`. Smoke
saat deploy/rollback juga memegang lock ini (menunggu ≤ 60 s), sehingga snapshot tidak berganti di tengah smoke.

**A4. Report: escaping dan akses.** Report dibangun harness dari JSON `/summary` dan `/jobs` (bukan menyalin HTML
aplikasi), setiap nilai lewat `html.escape`, tanpa script, dengan `<meta http-equiv="Content-Security-Policy"
content="default-src 'none'; style-src 'unsafe-inline'">`. Direktori `reports/` 0700, berkas 0600; 10 report terakhir
disimpan. Isinya hanya field proyeksi (A1).

**A5. Monitoring tidak mengganggu.** `monitor` tidak pernah memanggil docker untuk start/stop/rm, tidak pernah menulis
`state.json`, dan tidak menghapus snapshot aktif. Refresh gagal → smoke tetap dijalankan atas snapshot aktif dan keduanya
dicatat. Smoke gagal → dicatat; tidak ada rollback atau restart otomatis. Monitor yang crash meninggalkan direktori
sementara saja (dibersihkan refresh berikutnya).
