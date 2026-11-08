# Pilot viewer v0 #13: rilis issue 030 (grafik biaya per hari)

**"Go live" dari izin sesi Atha (jalur cepat, termasuk go live; approve dan applied didelegasikan ke Claude, 2026-11-08).**
Claude menjalankan langkah berurutan dari `~/pilot3a_live` (`main`), **satu langkah = satu perintah**, mencatat output di
folder ini, dan berhenti di langkah pertama yang tidak sesuai harapan, tanpa menambah atau mengulang langkah. Hanya
staging; tanpa model; container argus-ledger dan port 8000 tidak disentuh; proxy tidak di-restart.

`A = ~/Argus-agent/.venv-verify/bin/python scripts/argus.py`; job 030 = `j20261108_183658_0644` (redraft d2) (APPLIED, argus-viewer
`fab5d8759215`, di atas rilis 029 `76c7189`; hanya `src/App.jsx` + tes baru). Rilis =
`j20261108_183658_0644-fab5d8759215`. Build lokal: class grafik ada di CSS; vitest 225/225. Job 030 pertama `j20261108_175354_be44` REJECTED (tes draf menyimpang dari issue).

| # | perintah | harapan |
|---|---|---|
| 0 | `$A stage viewer-status` | viewer live `j20261108_170846_c722-76c7189cecf3` |
| 1 | `$A stage viewer-deploy j20261108_183658_0644 --yes` | exit 0; live rilis 030; rollback berikutnya = rilis 029 |
| 2 | `$A stage viewer-smoke` | exit 0, semua pass |
| 3 | `$A stage monitor` | exit 0, `ok: true`, viewer rilis 030 |
| 4 | `$A stage viewer-status` | viewer live rilis 030, rollback → rilis 029 |

Sesudahnya di HP: kartu "Cost per day" dengan 14 batang di bawah empat kartu angka.
Rollback: `$A stage viewer-rollback` (ke rilis 029), butuh "go live" sendiri.
