# Pilot viewer v0 #12: rilis issue 029 (label status berwarna di daftar job)

**"Go live" dari izin sesi Atha (jalur cepat, termasuk go live; approve dan applied didelegasikan ke Claude, 2026-11-08).**
Claude menjalankan langkah berurutan dari `~/pilot3a_live` (`main`), **satu langkah = satu perintah**, mencatat output di
folder ini, dan berhenti di langkah pertama yang tidak sesuai harapan, tanpa menambah atau mengulang langkah. Hanya
staging; tanpa model; container argus-ledger dan port 8000 tidak disentuh; proxy tidak di-restart.

`A = ~/Argus-agent/.venv-verify/bin/python scripts/argus.py`; job 029 = `j20261108_170846_c722` (APPLIED, argus-viewer
`76c7189cecf3`, di atas rilis 028 `040ce1e`; hanya `src/App.jsx` + tes baru). Rilis =
`j20261108_170846_c722-76c7189cecf3`. Build lokal: class label ada di CSS; vitest 209/209.

| # | perintah | harapan |
|---|---|---|
| 0 | `$A stage viewer-status` | viewer live `j20261108_165011_d3c5-040ce1ed1964` |
| 1 | `$A stage viewer-deploy j20261108_170846_c722 --yes` | exit 0; live rilis 029; rollback berikutnya = rilis 028 |
| 2 | `$A stage viewer-smoke` | exit 0, semua pass |
| 3 | `$A stage monitor` | exit 0, `ok: true`, viewer rilis 029 |
| 4 | `$A stage viewer-status` | viewer live rilis 029, rollback → rilis 028 |

Sesudahnya di HP: status tiap job di daftar tampil sebagai label berwarna per kelompok.
Rollback: `$A stage viewer-rollback` (ke rilis 028), butuh "go live" sendiri.
