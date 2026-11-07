# Pilot viewer v0 #4: hasil (2026-11-06, ±05:00 UTC)

Go live: Atha "deploy fitur 011-014". Semua langkah 0-5 sesuai PLAN, tanpa penyimpangan, $0 (tanpa model).

- 0: live `j20261031_094229_2180-201a7231d246`, container ledger `f81794a9979b`.
- 1: `viewer-deploy j20261106_043047_b160` exit 0; live `j20261106_043047_b160-8e8a2d790399`, rollback = rilis 010.
- 2: `viewer-smoke` exit 0, 12/12 ok (76 job di snapshot).
- 3: `/` 200 `no-cache` dengan aset `index-BY466fXP.js` (memuat kode issue 012) dan `index-9R6eDnXZ.css`; `sw.js`
  sha256 `db58777a4104…` (tetap); `/api/jobs/j20261031_094229_2180` 200 `no-store`.
- 4: `stage monitor` exit 0, `ok: true`, viewer release 014.
- 5: viewer live rilis 014; ledger `j20261104_152512_b93a-4e947a0ffe8b.up1`, container sama.

Rollback: `stage viewer-rollback` (ke rilis 010), butuh "go live" sendiri.
