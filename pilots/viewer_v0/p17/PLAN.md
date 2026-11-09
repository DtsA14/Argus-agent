# Pilot viewer v0 #17: rilis issue 037 (tanggal WIB di kartu job, legenda Job status rata kiri)

**"Go live" dari izin sesi Atha (jalur cepat; approve dan applied didelegasikan ke Claude).** Atha 2026-11-09: "Ok tanpa
judul dulu". Langkah berurutan dari `~/pilot3a_live`, satu langkah = satu perintah, berhenti di penyimpangan pertama.
Hanya staging; tanpa model; ledger dan port 8000 tidak disentuh; proxy tidak di-restart.

Di atas rilis 036 `2839c6d`: `a7c4ab8` tangan (tes 032: sel job boleh punya kelas tambahan; draf pertama
`j20261109_040637_b7ab` konflik karenanya, ditolak), `f129a3b` job 037 `j20261109_041109_a714`. Rilis =
`j20261109_041109_a714-f129a3bed28e`. vitest 279/279.

| # | perintah | harapan |
|---|---|---|
| 0 | `$A stage viewer-status` | viewer live `j20261109_034712_4409-2839c6d619df` |
| 1 | `$A stage viewer-deploy j20261109_041109_a714 --yes` | exit 0; live rilis 037; rollback = rilis 036 |
| 2 | `$A stage viewer-smoke` | exit 0, semua pass |
| 3 | `$A stage monitor` | exit 0, `ok: true`, viewer rilis 037 |
| 4 | `$A stage viewer-status` | viewer live rilis 037, rollback → rilis 036 |
