# Pilot viewer v0 #9: rilis issue 026 (kalimat drafter untuk orang awam, bagian teknis dilipat)

**"Go live" Atha diminta sesudah applied 026 (2026-11-08).** Claude menjalankan langkah berurutan dari
`~/pilot3a_live` (`main`), **satu langkah = satu perintah**, mencatat output di folder ini, dan berhenti di langkah pertama
yang tidak sesuai harapan, tanpa menambah atau mengulang langkah. Hanya staging; tanpa model; container argus-ledger dan
port 8000 tidak disentuh; unit proxy tidak diubah dan tidak di-restart (`router/stage_viewer.py` tidak berubah sejak p8).

`A = ~/Argus-agent/.venv-verify/bin/python scripts/argus.py`; job 026 = `j20261108_103705_ffce` (APPLIED, argus-viewer
`10329bd9e0e3`, di atas rilis 025 `ed26eae`; hanya `src/` berubah). Rilis = `j20261108_103705_ffce-10329bd9e0e3`.
`summary.for_human` sudah diterbitkan oleh D1 sejak #367 (dc5368b); draf lama membawa `null`.

| # | perintah | harapan |
|---|---|---|
| 0 | `$A stage viewer-status` | viewer live `j20261108_064429_31e1-ed26eae5cdaa` |
| 1 | `$A stage viewer-deploy j20261108_103705_ffce --yes` | exit 0; live rilis 026; rollback berikutnya = rilis 025 |
| 2 | `$A stage viewer-smoke` | exit 0, semua pass |
| 3 | `$A stage monitor` | exit 0, `ok: true`, viewer rilis 026 |
| 4 | `$A stage viewer-status` | viewer live rilis 026, rollback → rilis 025 |

Sesudahnya di HP: halaman draf membuka dengan kotak Ringkasan yang baris pertamanya "🗣️ Yang akan kamu lihat: …" (atau
"Drafter tidak menulis penjelasan…" untuk draf lama), kartu keputusan, lalu satu lipatan tertutup "Detail teknis". Rollback:
`$A stage viewer-rollback` (ke rilis 025), butuh "go live" sendiri.
