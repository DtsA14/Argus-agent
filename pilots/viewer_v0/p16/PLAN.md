# Pilot viewer v0 #16: rilis issue 034 + 035 + 036 (Refresh ikon, Waiting for you, Job status)

**"Go live" dari izin sesi Atha (jalur cepat, termasuk go live; approve dan applied didelegasikan ke Claude).** Atha
2026-11-09 (screenshot mockup): "Waiting for you, job status, sama job id bikin kayak gini bro. Refresh ganti jadi
button". Claude menjalankan langkah berurutan dari `~/pilot3a_live` (`main`), **satu langkah = satu perintah**, mencatat
output di folder ini, dan berhenti di langkah pertama yang tidak sesuai harapan. Hanya staging; tanpa model; container
argus-ledger dan port 8000 tidak disentuh; proxy tidak di-restart.

`A = ~/Argus-agent/.venv-verify/bin/python scripts/argus.py`. Di atas rilis 033 `4955dc2`, argus-viewer (semua draf
pertama, agen 1 percobaan, tanpa konflik): `3fca807` 034 `j20261109_031821_e1e1`, `a90e03a` 035
`j20261109_033501_cafd`, `2839c6d` 036 `j20261109_034712_4409`. Rilis = `j20261109_034712_4409-2839c6d619df`.
Build lokal: class ada di CSS; vitest 273/273.

| # | perintah | harapan |
|---|---|---|
| 0 | `$A stage viewer-status` | viewer live `j20261109_023512_7b70-4955dc297319` |
| 1 | `$A stage viewer-deploy j20261109_034712_4409 --yes` | exit 0; live rilis 036; rollback berikutnya = rilis 033 |
| 2 | `$A stage viewer-smoke` | exit 0, semua pass |
| 3 | `$A stage monitor` | exit 0, `ok: true`, viewer rilis 036 |
| 4 | `$A stage viewer-status` | viewer live rilis 036, rollback → rilis 033 |

Sesudahnya di HP: tombol Refresh bulat di kanan atas; kartu "Waiting for you" di atas kartu angka; kartu "Job status"
dengan bar berwarna di bawah grafik biaya. Rollback: `$A stage viewer-rollback` (ke rilis 033), butuh "go live" sendiri.
