# Pilot viewer v0 #18: rilis issue 038 (tabel total dilipat jadi kartu "Cost by state", filter dalam satu kartu)

**"Go live" dari izin sesi Atha (jalur cepat; approve dan applied didelegasikan ke Claude).** Atha 2026-11-09: "Ok bro
mulai dari #1". Langkah berurutan dari `~/pilot3a_live`, satu langkah = satu perintah, berhenti di penyimpangan pertama.
Hanya staging; tanpa model; ledger dan port 8000 tidak disentuh; proxy tidak di-restart.

Di atas rilis 037 `f129a3b`: `2cecc3a` job 038 `j20261109_054636_f8c5` (draf pertama, agen 1 percobaan). Rilis =
`j20261109_054636_f8c5-2cecc3a5593e`. vitest 287/287.

| # | perintah | harapan |
|---|---|---|
| 0 | `$A stage viewer-status` | viewer live `j20261109_041109_a714-f129a3bed28e` |
| 1 | `$A stage viewer-deploy j20261109_054636_f8c5 --yes` | exit 0; live rilis 038; rollback = rilis 037 |
| 2 | `$A stage viewer-smoke` | exit 0, semua pass |
| 3 | `$A stage monitor` | exit 0, `ok: true`, viewer rilis 038 |
| 4 | `$A stage viewer-status` | viewer live rilis 038, rollback → rilis 037 |
