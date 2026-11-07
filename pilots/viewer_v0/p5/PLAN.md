# Pilot viewer v0 #5: rilis issue 016-020 (shadow batch 4)

**"Go live" Atha untuk rencana ini: "Ini dulu aja bro" atas tawaran PLAN deploy #5 (2026-11-06).** Claude menjalankan
langkah berurutan dari `~/pilot3a_live` (`main`), **satu langkah = satu perintah**, mencatat output di folder ini, dan
berhenti di langkah pertama yang tidak sesuai harapan, tanpa menambah atau mengulang langkah. Hanya staging; tanpa model;
container argus-ledger dan port 8000 tidak disentuh; unit proxy tidak diubah.

`A = ~/Argus-agent/.venv-verify/bin/python scripts/argus.py`; job 020 = `j20261106_085425_46a7` (APPLIED, commit
`0b02b87bad84` di `~/argus-viewer`, yang memuat issue 016-020; `public/`, `index.html`, `package.json` tidak berubah sejak
rilis 014). Rilis = `j20261106_085425_46a7-0b02b87bad84`.

| # | perintah | harapan |
|---|---|---|
| 0 | `$A stage viewer-status`; `docker ps` | viewer live `j20261106_043047_b160-8e8a2d790399`; container ledger `f81794a9979b` |
| 1 | `$A stage viewer-deploy j20261106_085425_46a7 --yes` | exit 0; live = rilis 020; rollback berikutnya = rilis 014 |
| 2 | `$A stage viewer-smoke` | exit 0, semua pass (lewat proxy 8710) |
| 3 | `curl` `/` dan `/api/jobs/j20261106_085425_46a7` di `127.0.0.1:8710` | 200 `index.html` dengan aset rilis 020 (`sw.js` `db58777a…`); 200 JSON `no-store` bila job itu sudah ada di snapshot, kalau belum 404 dari ledger juga sesuai (snapshot tiap 15 menit) |
| 4 | `$A stage monitor` | exit 0, `ok: true`, viewer rilis 020 |
| 5 | `$A stage viewer-status`; `$A stage status`; `docker ps` | viewer live rilis 020; ledger dan container sama dengan langkah 0 |

Sesudahnya di HP: tombol hapus search, `/` ke kotak search, `…, $x together` di baris jumlah job yang tampil, stage
termahal disorot di halaman job, Refresh abu-abu selama loading. Rollback: `$A stage viewer-rollback` (ke rilis 014),
butuh "go live" sendiri.
