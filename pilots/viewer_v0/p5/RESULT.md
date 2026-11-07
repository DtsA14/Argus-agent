# Pilot viewer v0 #5: hasil (2026-11-06)

Semua langkah 0-5 sesuai PLAN, tanpa penyimpangan, $0 (tanpa model).

- 0: live `j20261106_043047_b160-8e8a2d790399`, container ledger `f81794a9979b`.
- 1: `viewer-deploy j20261106_085425_46a7` exit 0; live `j20261106_085425_46a7-0b02b87bad84`, rollback = rilis 014.
- 2: `viewer-smoke` exit 0, 12/12 ok.
- 3: `/` 200 `no-cache`, aset `index-03LZb3YW.js` (memuat kode issue 019) dan `index-MECTdHPY.css`; `sw.js` `db58777a4104…`
  (tetap); `/api/jobs/j20261106_085425_46a7` 404 karena job itu belum ada di snapshot (diperkirakan di PLAN).
- 4: `stage monitor` exit 0, `ok: true`, viewer rilis 020.
- 5: viewer live rilis 020; ledger `j20261104_152512_b93a-4e947a0ffe8b.up1`, container sama.
