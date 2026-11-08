# Pilot viewer v0 #11: rilis issue 028 (empat kartu angka di halaman daftar)

**"Go live" dari izin sesi Atha (jalur cepat, termasuk go live; approve dan applied didelegasikan ke Claude, 2026-11-08).**
Claude menjalankan langkah berurutan dari `~/pilot3a_live` (`main`), **satu langkah = satu perintah**, mencatat output di
folder ini, dan berhenti di langkah pertama yang tidak sesuai harapan, tanpa menambah atau mengulang langkah. Hanya
staging; tanpa model; container argus-ledger dan port 8000 tidak disentuh; proxy tidak di-restart.

`A = ~/Argus-agent/.venv-verify/bin/python scripts/argus.py`; job 028 = `j20261108_165011_d3c5` (APPLIED, argus-viewer
`040ce1ed1964`, di atas rilis 027 `06aeee7`; hanya `src/App.jsx` + tes baru). Rilis =
`j20261108_165011_d3c5-040ce1ed1964`. Build lokal: class Tailwind kartu ada di CSS; vitest 203/203.

| # | perintah | harapan |
|---|---|---|
| 0 | `$A stage viewer-status` | viewer live `j20261108_162504_124b-06aeee76b1c4` |
| 1 | `$A stage viewer-deploy j20261108_165011_d3c5 --yes` | exit 0; live rilis 028; rollback berikutnya = rilis 027 |
| 2 | `$A stage viewer-smoke` | exit 0, semua pass |
| 3 | `$A stage monitor` | exit 0, `ok: true`, viewer rilis 028 |
| 4 | `$A stage viewer-status` | viewer live rilis 028, rollback → rilis 027 |

Sesudahnya di HP: empat kartu (Jobs, Total cost, Last 14 days, Average / job) di bawah baris ringkasan halaman daftar.
Rollback: `$A stage viewer-rollback` (ke rilis 027), butuh "go live" sendiri.
