# Pilot viewer v0 #3: hasil

**Selesai 2026-10-31 14:17 UTC, satu "go live" Atha, semua langkah sesuai harapan, $0 (tanpa model).**

| # | hasil |
|---|---|
| 0 | viewer live rilis 002 (`j20261030_173255_6793-ab4cbd7cd8ae`), container ledger `1af21f1a2fc5` |
| 1 | `viewer-deploy` exit 0: live = `j20261031_094229_2180-201a7231d246`, rollback = rilis 002; `sw.js` `db58777a…` (dicek dengan `sha256sum`, dicatat di log langkah 1) |
| 2 | `viewer-smoke` exit 0, 12/12 pass |
| 3 | `/` 200 dengan aset `index-DJUcRAHg.js` (sama dengan smoke); `/api/jobs/j20261030_173255_6793` 200 JSON `no-store` |
| 4 | `stage monitor` exit 0, `ok: true`, snapshot 71 job, ledger dan viewer pass |
| 5 | viewer live rilis 010; ledger `…1f31e34c1ff2.up1` dan container `1af21f1a2fc5` tidak berubah |

Keputusan Atha: 1 ("go live"). Catatan: langkah 1 tidak mencetak hash `sw.js` sendiri; `sha256sum` dijalankan sebagai
pemeriksaan baca-saja dari harapan langkah itu, bukan langkah baru.

Live: issue 003-010 (pilihan state, cari, total per state, auto-refresh + sorotan running, urutan biaya, `loaded at`, kolom
`share`, judul tab). Rollback: `$A stage viewer-rollback` (ke rilis 002), butuh "go live" sendiri.
