# Hasil: deploy batch 5 (ledger Stage 14 + viewer 021-023), 2026-11-08

Dua "go live" Atha (rencana awal, lalu revisi 1). $0 (tanpa model).

| # | hasil | log |
|---|---|---|
| 0 | ok: ledger Stage 13 `.up2`, viewer rilis 020, satu container | `step0_status.log` |
| 1 | ok: `stage check PASS` `1d3a8ea82356` di `ledger_py312_up2` `3e48cd98c8de`, 145 tests | `step1_check.log` |
| 2 | ok: live `j20261107_171214_be81-1d3a8ea82356.up2`, smoke pass; inspect sesuai (none, ro, cap ALL, 1001:1001, no-new-privileges, `/data` ro, image `6d8fc5cc3639`) | `step2_deploy.log`, `step2_inspect.log` |
| 3 | ok: viewer live `j20261107_174855_60fa-70b553214782`, rollback → rilis 020 | `step3_viewer_deploy.log` |
| 4 | ok: viewer-smoke semua pass | `step4_viewer_smoke.log` |
| 5 | ok: monitor `ok: true` (ledger Stage 14, viewer 023) | `step5_monitor.log` |
| 6 | **berhenti**: `/api/jobs/<id>/draft` → 404 `{"error": "not found"}` dari proxy (proxy berjalan sejak 2026-10-30, belum memuat regex D3 #357) | `step6_curl.log` |
| r1 | ok: `systemctl --user restart argus-stage-proxy`, active, listen hanya `127.0.0.1:8710` | `r1_restart.log` |
| r2 | ok: viewer-smoke 12/12 pass | `r2_viewer_smoke.log` |
| r3 | ok: draf 60fa 200, kunci tepat, `draft_sha256` `27312a728673`, summary dan review ada, judge null; job tanpa draf 404 `no draft: …`; halaman 200 | `r3_curl.log` |
| r4 | ok: ledger Stage 14 `.up2` (rollback → Stage 13 `.up2`), viewer rilis 023 (rollback → 020), satu container | `r4_status.log` |

Pelajaran: perubahan `router/stage_viewer.py` baru berlaku sesudah proxy di-restart; rencana deploy berikutnya yang
menyusul perubahan proxy harus memuat langkah restart.
