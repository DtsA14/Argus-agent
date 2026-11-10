# Pilot viewer v0 #19: rilis issue 040 (tautan "see all" di bawah kartu Waiting for you, halaman /waiting)

**"Go live" dari delegasi jalur cepat (approve, applied dan deploy viewer didelegasikan ke Claude, 2026-11-08).** Issue
pertama yang ditulis dari chatbox HP (job issue j20261109_162802_3ff8, issue `1d141ed0121a`, Start oleh Atha via 8711).
Langkah berurutan dari `~/pilot3a_live`, satu langkah = satu perintah, berhenti di penyimpangan pertama. Hanya staging;
tanpa model; ledger dan port 8000 tidak disentuh; proxy tidak di-restart.

Di atas rilis 039 `9fd6376`: `f68bc4c` job 040 `j20261110_051346_9f15` (draf pertama `7e0734a8ad04`, agen 1 percobaan,
25 langkah, $0,038 total). Patch sha256 `4041542519ef`. Validasi fresh: target 13, seeall 5, seluruh 43 berkas tes lama pass.

| # | perintah | harapan |
|---|---|---|
| 0 | `$A stage viewer-status` | viewer live rilis 039 (`9fd6376`) |
| 1 | `$A stage viewer-deploy j20261110_051346_9f15 --yes` | exit 0; live rilis 040; rollback = rilis 039 |
| 2 | `$A stage viewer-smoke` | exit 0, semua pass |
| 3 | `$A stage monitor` | exit 0, `ok: true`, viewer rilis 040 |
| 4 | `$A stage viewer-status` | viewer live rilis 040, rollback → rilis 039 |
