# Pilot viewer v0 #7: rilis issue 024 (Ringkasan bahasa Indonesia di halaman draf)

**Menunggu "go live" Atha.** Claude menjalankan langkah berurutan dari `~/pilot3a_live` (`main`), **satu langkah = satu
perintah**, mencatat output di folder ini, dan berhenti di langkah pertama yang tidak sesuai harapan, tanpa menambah atau
mengulang langkah. Hanya staging; tanpa model; container argus-ledger dan port 8000 tidak disentuh; unit proxy tidak diubah
dan tidak perlu di-restart (`router/stage_viewer.py` tidak berubah sejak restart 2026-11-08).

`A = ~/Argus-agent/.venv-verify/bin/python scripts/argus.py`; job 024 = `j20261108_031013_808b` (APPLIED, argus-viewer
`85171747a5fd`, di atas rilis 023 `70b5532`; `public/`, `index.html`, `package.json` tidak berubah). Rilis =
`j20261108_031013_808b-85171747a5fd`.

| # | perintah | harapan |
|---|---|---|
| 0 | `$A stage viewer-status`; `docker ps` | viewer live `j20261107_174855_60fa-70b553214782`; satu container ledger Stage 14 `.up2` |
| 1 | `$A stage viewer-deploy j20261108_031013_808b --yes` | exit 0; live rilis 024; rollback berikutnya = rilis 023 |
| 2 | `$A stage viewer-smoke` | exit 0, semua pass |
| 3 | `curl` di `127.0.0.1:8710`: `/jobs/j20261108_031013_808b/draft`, `/api/jobs/j20261108_031013_808b/draft` | 200 `index.html` rilis 024; 200 JSON dengan `draft_sha256` mulai `e3f709d8fb09` |
| 4 | `$A stage monitor` | exit 0, `ok: true`, viewer rilis 024 |
| 5 | `$A stage viewer-status`; `docker ps` | viewer live rilis 024; container ledger sama dengan langkah 0 |

Sesudahnya di HP: halaman draf punya kotak "Ringkasan" di atas kartu. Rollback: `$A stage viewer-rollback` (ke rilis 023),
butuh "go live" sendiri.
