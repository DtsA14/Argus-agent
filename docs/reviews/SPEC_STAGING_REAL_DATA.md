# Spek: staging argus-ledger dengan data Argus asli, dan monitoring sesudah deploy

Status: **draf; arah disetujui Atha 2026-10-30** (opsi a: tetap tanpa jaringan). Jalur ketat (`router/stage.py`,
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

## 5. Keputusan untuk Atha

1. **Timer monitoring:** `systemd --user` timer tiap **15 menit** *(saran)*, atau cron, atau tanpa timer (monitor manual).
2. **Issue 014** ditulis Claude (seperti 001–013) *(saran)*, atau oleh Atha.
