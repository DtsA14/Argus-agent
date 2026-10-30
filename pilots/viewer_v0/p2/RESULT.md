# Hasil pilot viewer v0 #2 (2026-10-30): rilis issue 002

Dua "go live" Atha (rencana, lalu lanjutan sesudah berhenti di langkah 3). Satu langkah = satu perintah.

| # | hasil | log |
|---|---|---|
| 0 | viewer live rilis 001; container ledger `1af21f1a2fc5` | `step0_status.log` |
| 1 | `viewer-deploy` exit 0: live `j20261030_173255_6793-ab4cbd7cd8ae`, rollback → rilis 001, `sw.js` = `db58777a…` | `step1_deploy.log` |
| 2 | `viewer-smoke` exit 0, semua pass (proxy tidak di-restart) | `step2_smoke.log` |
| 3 | **berhenti**: `/jobs/<id>` 200 `index.html` rilis 002 (sesuai), tetapi `/api/jobs/j20261030_173255_6793` 404 | `step3_curl.log` |

**Sebab langkah 3:** harapan rencana yang salah, bukan sistemnya. Snapshot data diambil 17:30:32 UTC (57 job), job 002
dibuat 17:32:55, jadi belum ada di snapshot; viewer melayani snapshot terakhir sesuai rancangan. Seharusnya rencana
memakai job yang sudah ada di snapshot.

Lanjutan ("go live"):

| # | hasil | log |
|---|---|---|
| 3b | `/api/jobs/j20261030_164214_d603` 200 JSON, `no-store` | `step3b_curl.log` |
| 4 | `stage monitor` exit 0, `ok: true`, snapshot 58 job, smoke ledger dan viewer pass | `step4_monitor.log` |
| 5 | viewer live rilis 002, rollback → 001; ledger live dan container `1af21f1a2fc5` sama dengan langkah 0 | `step5_status.log` |

Pelajaran: data viewer = snapshot terakhir (diperbarui monitor tiap 15 menit); rencana yang mengecek data harus memakai
yang sudah ada di snapshot.
