# Pilot viewer v0 #3: rilis issue 003-010 (shadow batch 2)

**Satu "go live" Atha untuk rencana ini** (U4). Claude menjalankan langkah berurutan dari `~/pilot3a_live` (`main`),
**satu langkah = satu perintah**, mencatat output di folder ini, dan berhenti di langkah pertama yang tidak sesuai
harapan, tanpa menambah atau mengulang langkah. Hanya staging; tanpa model; container argus-ledger dan port 8000 tidak
disentuh; unit proxy tidak diubah (melayani `current` yang baru tanpa restart).

`A = ~/Argus-agent/.venv-verify/bin/python scripts/argus.py`; job 010 = `j20261031_094229_2180` (APPLIED, commit
`201a7231d246` di `~/argus-viewer`, yang memuat issue 003-010 dan perbaikan tes 56b7e00, 8b905f9, 379550d; `public/sw.js`
tidak berubah sejak kerangka). Rilis = `j20261031_094229_2180-201a7231d246`.

| # | perintah | harapan |
|---|---|---|
| 0 | `$A stage viewer-status`; `docker ps` | viewer live `j20261030_173255_6793-ab4cbd7cd8ae`; container ledger `1af21f1a2fc5` |
| 1 | `$A stage viewer-deploy j20261031_094229_2180 --yes` | exit 0; build di `pwa_node22`, cek artifact lolos, smoke kandidat pass; live = rilis 010; rollback berikutnya = rilis 002; `sw.js` = `db58777a…` |
| 2 | `$A stage viewer-smoke` | exit 0, semua pass (lewat proxy 8710 yang sudah jalan) |
| 3 | `curl` `/` dan `/api/jobs/j20261030_173255_6793` di `127.0.0.1:8710` | 200 `index.html` yang memuat aset rilis 010; 200 JSON `no-store` (job yang sudah ada di snapshot sejak p2) |
| 4 | `$A stage monitor` | exit 0, `ok: true`, ledger dan viewer pass |
| 5 | `$A stage viewer-status`; `$A stage status`; `docker ps` | viewer live rilis 010; ledger live dan container sama dengan langkah 0 |

Sesudahnya Atha membuka `http://localhost:8710` di HP (Termius aktif) dan melihat pilihan state, kotak cari, pilihan urutan,
tabel total per state, dan `loaded at`; halaman job menampilkan kolom `share`. Rollback bila perlu: `$A stage viewer-rollback`
(kembali ke rilis 002), butuh "go live" sendiri.
