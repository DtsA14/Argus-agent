# Pilot dependency upgrade v0 #1: argus-ledger 013 ke stack up1, rollback, dan kembali

Spek: `docs/reviews/SPEC_DEP_UPGRADE_V0.md` (merged #246, af341ee). Satu "go live" Atha berlaku untuk **seluruh rencana
ini** (U4). Claude menjalankan langkah berurutan dari `~/pilot3a_live` (`main`), mencatat output tiap langkah di folder
ini, dan **berhenti di langkah pertama yang tidak sesuai harapan** (exit ≠ 0, smoke gagal, `docker inspect` beda,
`status` beda): tidak menambah atau mengulang langkah, lalu melapor. Hanya staging; tanpa model; athena-api (port 8000)
tidak disentuh.

`A = .venv-verify/bin/python scripts/argus.py`, job 013 = `j20261029_115742_bffd` (argus-ledger `804e13a`).
Image: `ledger_staging` (v0) `sha256:4ab2ff53a34f…`, `ledger_staging_up1` `sha256:4edca09d1842…`,
`ledger_py312_up1` `sha256:59288cff2053…`.

Setelah setiap langkah yang menjalankan container, Claude memeriksa `docker inspect` container live: `NetworkMode=none`,
`ReadonlyRootfs=true`, `CapDrop=[ALL]`, user `1001:1001`, `no-new-privileges`, dan **Image** seperti tertulis; tepat satu
container `argus-staging-ledger-*` berjalan; port 8000 tetap menjawab.

| # | perintah | harapan |
|---|---|---|
| 0 | `$A stage status` | live `j20261029_115742_bffd-804e13a33c44`, runtime `ledger_staging`; rollback → `j20261029_054325_6606-324012a60a7a` |
| 1 | `$A stage check j20261029_115742_bffd --env ledger_py312_up1` | exit 0, `stage check PASS`, 124 tests, image `sha256:59288cff2053` |
| 2 | `$A stage deploy j20261029_115742_bffd --runtime ledger_staging_up1 --yes` | exit 0; layar menyebut `tested: stage check passed`; live `…-804e13a33c44.up1`, smoke pass; Image `4edca09d1842`; rollback → `…-804e13a33c44` on `ledger_staging` |
| 3 | `$A stage rollback --yes` | exit 0; live `…-804e13a33c44` (runtime `ledger_staging`), smoke pass; Image `4ab2ff53a34f` (rilis v0 di image v0) |
| 4 | `$A stage deploy j20261029_115742_bffd --runtime ledger_staging_up1 --yes` | exit 0; rilis `.up1` yang sudah dibangun dipakai lagi (check langkah 1 masih yang terakhir); live `…-804e13a33c44.up1`, smoke pass; Image `4edca09d1842` |
| 5 | `$A stage status` | live `…-804e13a33c44.up1`, runtime `ledger_staging_up1`; rollback → `…-804e13a33c44` on `ledger_staging` |

Sesudahnya: `RESULT.md` di folder ini dan PENDING.md (jalur cepat, Claude merge sendiri).
