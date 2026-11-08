# Pilot viewer v0 #8: rilis issue 025 (jam dibuat dalam WIB di halaman job)

**"Go live" Atha 2026-11-08 ("Y dan go live", bersama applied 025).** Claude menjalankan langkah berurutan dari
`~/pilot3a_live` (`main`), **satu langkah = satu perintah**, mencatat output di folder ini, dan berhenti di langkah pertama
yang tidak sesuai harapan, tanpa menambah atau mengulang langkah. Hanya staging; tanpa model; container argus-ledger dan
port 8000 tidak disentuh; unit proxy tidak diubah dan tidak di-restart (`router/stage_viewer.py` tidak berubah).

`A = ~/Argus-agent/.venv-verify/bin/python scripts/argus.py`; job 025 = `j20261108_064429_31e1` (APPLIED, argus-viewer
`ed26eae5cdaa`, di atas rilis 024 `8517174`; `public/`, `index.html`, `package.json` tidak berubah). Rilis =
`j20261108_064429_31e1-ed26eae5cdaa`.

| # | perintah | harapan |
|---|---|---|
| 0 | `$A stage viewer-status` | viewer live `j20261108_031013_808b-85171747a5fd` |
| 1 | `$A stage viewer-deploy j20261108_064429_31e1 --yes` | exit 0; live rilis 025; rollback berikutnya = rilis 024 |
| 2 | `$A stage viewer-smoke` | exit 0, semua pass |
| 3 | `$A stage monitor` | exit 0, `ok: true`, viewer rilis 025 |
| 4 | `$A stage viewer-status` | viewer live rilis 025, rollback → rilis 024 |

Sesudahnya di HP: halaman job punya baris "Dibuat: … WIB (… lalu)" di bawah `created …`. Rollback: `$A stage
viewer-rollback` (ke rilis 024), butuh "go live" sendiri.
