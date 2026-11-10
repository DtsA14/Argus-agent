# Pilot viewer v0 #20: rilis issue 041 (durasi tiap stage di sel status halaman job)

**"Go live" dari delegasi jalur cepat (2026-11-08).** Issue dari chatbox HP (job issue j20261110_165623_7672, issue
`5ecf8a413020`, Start oleh Atha via 8711), membutuhkan ledger Stage 15 (`pilots/staging_stage15`, live 2026-11-10).
Langkah berurutan dari `~/pilot3a_live`, satu langkah = satu perintah, berhenti di penyimpangan pertama. Hanya staging;
tanpa model; ledger dan port 8000 tidak disentuh; proxy tidak di-restart.

Di atas rilis 040 `f68bc4c`: `49b11ec` job 041 `j20261110_173806_dd3b` (draf pertama `c0549a56c173`, agen 1 percobaan,
10 langkah, $0,026 total). Validasi fresh: tes baru dan seluruh 45 berkas tes lama pass.

| # | perintah | harapan |
|---|---|---|
| 0 | `$A stage viewer-status` | viewer live rilis 040 (`f68bc4c`) |
| 1 | `$A stage viewer-deploy j20261110_173806_dd3b --yes` | exit 0; live rilis 041; rollback = rilis 040 |
| 2 | `$A stage viewer-smoke` | exit 0, semua pass |
| 3 | `$A stage monitor` | exit 0, `ok: true`, viewer rilis 041, ledger Stage 15 |
| 4 | `$A stage viewer-status` | viewer live rilis 041, rollback → rilis 040 |
