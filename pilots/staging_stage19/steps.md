# Langkah (2026-11-15, Claude, "go live" Atha: "Go live untuk staging")

| # | hasil |
|---|---|
| 0 | live Stage 18 `j20261112_053107_1929-1aeb82d3e220.up2`, monitor pass 18:45:49Z; satu container staging (ditambah `argus-test-ledger-*`, bukan staging) |
| 1 | `stage check PASS: commit 88c31e13e60f in ledger_py312_up2 sha256:3e48cd98c8de, 199 tests` |
| 2 | exit 0; live `j20261115_181548_0bc4-88c31e13e60f.up2`, smoke pass 18:50:57Z; rollback → Stage 18 |
| 3 | `viewer-smoke` exit 0, semua ok (lewat 8710; `/api/summary` 157 job) |
| 4 | **meleset pada percobaan pertama (salah rencana)**: `stage monitor` dijalankan dari checkout Argus-agent (`jobs/` miliknya 55 job, 38 ditolak format), refresh menolak menerbitkan ("38 of 55 jobs excluded (more than half)"), snapshot lama utuh, smoke ledger 4/4 dan viewer ok, `ok: false`, rc 1; `stage status` menulis `last monitor: FAIL (1 failed in a row)` (alert ntfy baru sesudah 3 gagal). Rencana seharusnya menjalankannya dari `~/pilot3a_live`, `jobs/` yang dipakai timer. Atha: "Lanjut langkah 4-7". Diulang dari `~/pilot3a_live`: 18:53:53Z `ok: true`, refresh 157 job, rilis Stage 19 |
| 5 | `probe.py`: 13 cek ok. Kunci dan urutan, entri `model, calls, cost_nano, cost_usd`, urutan biaya, total = jumlah entri = `/summary` `cost_nano` (8284146297 = 8284146297); `?kind=code` 4408 panggilan 7433747026 nano, `research` 1074 / 738600097, `issue` 121 / 111799174, tiganya berjumlah total tanpa filter; `?kind=nope` dan `?kind=` 400 `{"detail": "unknown kind: ..."}`; `evil.example` 400 |
| 6 | `127.0.0.1:8710/api/scoreboard/models` → **404** (seperti diprediksi: regex `API`, `router/stage_viewer.py:76`); `/api/scoreboard` 200, `/api/summary` 200 |
| 7 | live Stage 19, rollback → Stage 18, monitor pass 18:53:53Z, satu container staging: `net=none`, `ReadonlyRootfs=true`, `CapDrop=[ALL]`, user `1001:1001`, `no-new-privileges`, `/data` = `data/pub:/data:ro`, `/app` dan `/entry` read-only, soket di `/run/argus` |

Keadaan: ledger Stage 19 live dan sehat. Viewer tidak berubah (rilis `11ce2049bfc4`). Tidak ada halaman viewer yang memakai `/models`; menjangkaunya lewat proxy butuh perubahan regex `API` (jalur ketat, restart proxy, "go live" sendiri).
Pelajaran untuk bagian B spek antrean PRD: pemeriksaan jalur Argus harus mencocokkan jalur baru dengan regex proxy sebelum issue ditulis (ketergantungan tersembunyi ketiga setelah snapshot dan proxy di probe 2026-11-12), dan rencana langkah yang menjalankan `stage monitor` harus menyebut checkout asalnya.
