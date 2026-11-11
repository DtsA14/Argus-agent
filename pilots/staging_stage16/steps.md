# Langkah (2026-11-11, Claude)

| # | hasil |
|---|---|
| 0 | live Stage 15 `j20261110_170837_da17-b712363c860b.up2`, monitor pass 07:15:31Z; satu container `240860d8cdcf` |
| 1 | `stage check PASS: commit 9bac6ededa97 in ledger_py312_up2 sha256:3e48cd98c8de, 160 tests` |
| 2 | exit 0; live `j20261111_071510_9c2c-9bac6ededa97.up2`, smoke pass 07:23:51Z; rollback → Stage 15. Container `d867fda9a340`: NetworkMode none, ReadonlyRootfs true, CapDrop ALL, user 1001:1001, no-new-privileges, `/data` = `data/pub` ro |
| 3 | `viewer-smoke` exit 0, semua ok |
| 4 | `monitor` exit 0, `ok: true`, ledger Stage 16, viewer `j20261110_173806_dd3b-49b11ec9d9c0` (041); `/jobs` item pertama sudah punya `title` |
| 5 | `/api/jobs` 200: 143 job, 139 dengan `title` (semua tepat sesudah `created_at`), 4 job `issue` tanpa; `/api/jobs/j20261111_071510_9c2c` 200, kunci `job, state, created_at, title, stages…` |
| 6 | live Stage 16, rollback → Stage 15; satu container |

Semua sesuai harapan. Berikutnya: issue viewer (balasan ke `j20261111_043029_53f7`).
