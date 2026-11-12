# Langkah (2026-11-12, Claude, "go live" Atha)

| # | hasil |
|---|---|
| 0 | live Stage 17 `j20261111_114930_18a2-f2852daab505.up2`, monitor pass 06:15:31Z; satu container `5853928e827c` |
| 1 | `stage check PASS: commit 1aeb82d3e220 in ledger_py312_up2 sha256:3e48cd98c8de, 176 tests` |
| 2 | exit 0; live `j20261112_053107_1929-1aeb82d3e220.up2`, smoke pass 06:31:43Z; rollback → Stage 17. Container: net none, ReadonlyRootfs true, CapDrop ALL, user 1001:1001, no-new-privileges, `/data` read-only; satu container |
| 3 | `viewer-smoke` exit 0, semua ok |
| 4 | `monitor` exit 0, `ok: true`, release Stage 18, 156 job |
| 5 | **meleset**: `GET 127.0.0.1:8710/api/scoreboard` → **404** `{"error": ...}`. Penyebab (dibaca, tidak diubah): proxy viewer meneruskan hanya `/api/summary`, `/api/jobs`, `/api/jobs/<id>`, `/api/jobs/<id>/draft` (`router/stage_viewer.py:76`, regex `API`); `scoreboard` tidak ada di daftar itu. Berhenti di langkah ini sesuai rencana; langkah 6 tidak dijalankan |

Keadaan: ledger Stage 18 live dan sehat (langkah 0-4 lolos); rollback ke Stage 17 tersedia dan tidak diperlukan. Viewer rilis 045 tidak berubah; halaman `/scoreboard` dan tautannya (S3, S4) belum dirilis.
Berikutnya: menambah `scoreboard` ke daftar proxy (strict, `router/stage_viewer.py`; perubahan di sisi Argus, bukan di ledger atau viewer), lalu "go live" untuk memulai ulang proxy dan merilis viewer.
