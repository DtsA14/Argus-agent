# Pilot viewer v0 #6: rilis issue 021 (pertanyaan terbuka)

**"Go live" Atha untuk rencana ini: "Gas" atas usulan apply + tes fresh-load + deploy pilot #6 (2026-11-06).** Claude
menjalankan langkah berurutan dari `~/pilot3a_live` (`main`), **satu langkah = satu perintah**, mencatat output di folder
ini, dan berhenti di langkah pertama yang tidak sesuai harapan, tanpa menambah atau mengulang langkah. Hanya staging; tanpa
model; container argus-ledger dan port 8000 tidak disentuh; unit proxy tidak diubah.

`A = ~/Argus-agent/.venv-verify/bin/python scripts/argus.py`; job 021 = `j20261106_151840_e81c` (APPLIED, commit
`ab4376154948` di `~/argus-viewer`: patch job di `518b34f` plus tes fresh-load; `public/`, `index.html`, `package.json`
tidak berubah sejak rilis 020). Rilis = `j20261106_151840_e81c-ab4376154948`.

| # | perintah | harapan |
|---|---|---|
| 0 | `$A stage viewer-status`; `docker ps` | viewer live `j20261106_085425_46a7-0b02b87bad84`; container ledger `f81794a9979b` |
| 1 | `$A stage viewer-deploy j20261106_151840_e81c --yes` | exit 0; live = rilis 021; rollback berikutnya = rilis 020 |
| 2 | `$A stage viewer-smoke` | exit 0, semua pass (lewat proxy 8710) |
| 3 | `curl` `/` dan `/?state=APPLIED` di `127.0.0.1:8710` | 200 `index.html` dengan aset rilis 021 untuk keduanya |
| 4 | `$A stage monitor` | exit 0, `ok: true`, viewer rilis 021 |
| 5 | `$A stage viewer-status`; `$A stage status`; `docker ps` | viewer live rilis 021; ledger dan container sama dengan langkah 0 |

Sesudahnya di HP: pilih state lalu reload, filter tetap (address `?state=`); checkbox `expensive only`; halaman job yang
running memuat ulang sendiri tiap 30 s. Rollback: `$A stage viewer-rollback` (ke rilis 020), butuh "go live" sendiri.
