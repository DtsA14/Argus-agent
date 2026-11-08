# Pilot viewer v0 #14: rilis issue 031 (tampilan halaman draf)

**"Go live" dari izin sesi Atha (jalur cepat, termasuk go live; approve dan applied didelegasikan ke Claude, 2026-11-08).**
Claude menjalankan langkah berurutan dari `~/pilot3a_live` (`main`), **satu langkah = satu perintah**, mencatat output di
folder ini, dan berhenti di langkah pertama yang tidak sesuai harapan, tanpa menambah atau mengulang langkah. Hanya
staging; tanpa model; container argus-ledger dan port 8000 tidak disentuh; proxy tidak di-restart.

`A = ~/Argus-agent/.venv-verify/bin/python scripts/argus.py`; job 031 = `j20261108_185802_6db8` (redraft d2) (APPLIED, argus-viewer
`c4f0352f2280`, di atas rilis 030 `fab5d87`; hanya `src/App.jsx` + tes baru). Rilis =
`j20261108_185802_6db8-c4f0352f2280`. Build lokal: class ada di CSS; vitest 236/236; tanpa konflik dengan tes 024/026.

| # | perintah | harapan |
|---|---|---|
| 0 | `$A stage viewer-status` | viewer live `j20261108_183658_0644-fab5d8759215` |
| 1 | `$A stage viewer-deploy j20261108_185802_6db8 --yes` | exit 0; live rilis 031; rollback berikutnya = rilis 030 |
| 2 | `$A stage viewer-smoke` | exit 0, semua pass |
| 3 | `$A stage monitor` | exit 0, `ok: true`, viewer rilis 031 |
| 4 | `$A stage viewer-status` | viewer live rilis 031, rollback → rilis 030 |

Sesudahnya di HP: halaman draf bergaya panel, kalimat drafter besar, label status, kode approve besar dengan tombol Copy.
Rollback: `$A stage viewer-rollback` (ke rilis 030), butuh "go live" sendiri.
