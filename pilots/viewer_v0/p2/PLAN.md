# Pilot viewer v0 #2: rilis issue 002 (halaman job)

**Satu "go live" Atha untuk rencana ini** (U4). Claude menjalankan langkah berurutan dari `~/pilot3a_live` (`main`),
**satu langkah = satu perintah**, mencatat output di folder ini, dan berhenti di langkah pertama yang tidak sesuai
harapan, tanpa menambah atau mengulang langkah. Hanya staging; tanpa model; container argus-ledger dan port 8000 tidak
disentuh; unit proxy tidak diubah (melayani `current` yang baru tanpa restart).

`A = ~/Argus-agent/.venv-verify/bin/python scripts/argus.py`; job 002 = `j20261030_173255_6793` (APPLIED, commit
`ab4cbd7cd8ae` di `~/argus-viewer`). Rilis = `j20261030_173255_6793-ab4cbd7cd8ae`.

| # | perintah | harapan |
|---|---|---|
| 0 | `$A stage viewer-status`; `docker ps` | viewer live `j20261030_164214_d603-e794a53775be`; container ledger `1af21f1a2fc5` |
| 1 | `$A stage viewer-deploy j20261030_173255_6793 --yes` | exit 0; smoke kandidat pass; live = rilis 002; rollback berikutnya = rilis 001; `sw.js` = `db58777a…` |
| 2 | `$A stage viewer-smoke` | exit 0, semua pass (lewat proxy 8710 yang sudah jalan) |
| 3 | `curl` `/jobs/j20261030_173255_6793` dan `/api/jobs/j20261030_173255_6793` di `127.0.0.1:8710` | 200 `index.html` rilis 002; 200 JSON `no-store` |
| 4 | `$A stage monitor` | exit 0, `ok: true`, ledger dan viewer pass |
| 5 | `$A stage viewer-status`; `$A stage status`; `docker ps` | viewer live rilis 002; ledger live dan container sama dengan langkah 0 |

Sesudahnya Atha membuka `http://localhost:8710` di HP (Termius aktif), menekan satu id job, dan halaman job tampil.
