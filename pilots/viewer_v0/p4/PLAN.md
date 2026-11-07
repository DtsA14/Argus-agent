# Pilot viewer v0 #4: rilis issue 011-014 (shadow batch 3)

**"Go live" Atha untuk rencana ini: "deploy fitur 011-014" (2026-11-06).** Claude menjalankan langkah berurutan dari
`~/pilot3a_live` (`main`), **satu langkah = satu perintah**, mencatat output di folder ini, dan berhenti di langkah
pertama yang tidak sesuai harapan, tanpa menambah atau mengulang langkah. Hanya staging; tanpa model; container
argus-ledger dan port 8000 tidak disentuh; unit proxy tidak diubah.

`A = ~/Argus-agent/.venv-verify/bin/python scripts/argus.py`; job 014 = `j20261106_043047_b160` (APPLIED, commit
`8e8a2d790399` di `~/argus-viewer`, yang memuat issue 011-014 dan perbaikan tes 57ceca7, d3c8a3d; `public/`,
`index.html`, `package.json` tidak berubah sejak rilis 010). Rilis = `j20261106_043047_b160-8e8a2d790399`.

| # | perintah | harapan |
|---|---|---|
| 0 | `$A stage viewer-status`; `docker ps` | viewer live `j20261031_094229_2180-201a7231d246`; container ledger `f81794a9979b` |
| 1 | `$A stage viewer-deploy j20261106_043047_b160 --yes` | exit 0; build di `pwa_node22`, cek artifact lolos, smoke kandidat pass; live = rilis 014; rollback berikutnya = rilis 010; `sw.js` = `db58777a…` |
| 2 | `$A stage viewer-smoke` | exit 0, semua pass (lewat proxy 8710) |
| 3 | `curl` `/` dan `/api/jobs/j20261031_094229_2180` di `127.0.0.1:8710` | 200 `index.html` yang memuat aset rilis 014; 200 JSON `no-store` |
| 4 | `$A stage monitor` | exit 0, `ok: true`, ledger dan viewer pass |
| 5 | `$A stage viewer-status`; `$A stage status`; `docker ps` | viewer live rilis 014; ledger live dan container sama dengan langkah 0 |

Sesudahnya Atha membuka `http://localhost:8710` di HP (Termius aktif): summary line dengan `, n running` bila ada job
jalan, baris job > $0,25 disorot, kotak cari tersimpan di alamat (`?q=`), dan di halaman job baris `sum` di bawah tabel
stage. Rollback bila perlu: `$A stage viewer-rollback` (kembali ke rilis 010), butuh "go live" sendiri.
