# Deploy argus-ledger Stage 19 (issues 021-023: `GET /scoreboard/models`, `cost_usd` with a total, `?kind=`) ke staging

Hasil pilot `argus queue` v0 (`pilots/queue_pilot_v0/RESULT.md`). **"Go live" Atha 2026-11-15 ("Go live untuk staging")**, untuk PLAN.md ini. Claude menjalankan langkah berurutan, **satu langkah = satu perintah**, mencatat output di `steps.md` di folder ini,
dan berhenti di langkah pertama yang tidak sesuai harapan, tanpa menambah atau mengulang langkah. Hanya staging; tanpa model; port 8000 tidak disentuh; unit proxy dan monitor tidak diubah dan tidak di-restart; `~/pilot3a_live` tidak disentuh.

`A = /home/ubuntu/Argus-agent/.venv-verify/bin/python /home/ubuntu/Argus-agent/scripts/argus.py` (checkout Argus-agent, `jobs/` miliknya: tiga job pilot ada di sana, bukan di `~/pilot3a_live/jobs`). Job yang dideploy = **`j20261115_181548_0bc4`** (issue 023, APPLIED, argus-ledger `88c31e1`, yang memuat 021 `3633c98`
dan 022 `f230474` di atas Stage 18 `1aeb82d`). Rilis = `j20261115_181548_0bc4-88c31e13e60f.up2` di runtime `ledger_staging_up2`. Viewer tidak berubah.

**Ketergantungan tersembunyi yang sudah diketahui (bukan bagian rencana ini):** proxy viewer meneruskan hanya jalur di regex `API` (`router/stage_viewer.py:76`: `summary`, `scoreboard`, `jobs`, `jobs/<id>`, `jobs/<id>/draft`), jadi `/api/scoreboard/models` lewat 8710 akan **404** walau ledger sehat; tidak ada halaman viewer yang memakainya. Memperbaikinya = perubahan jalur ketat + restart proxy,
dengan "go live" sendiri. Langkah 5 memeriksa ledger lewat soketnya sendiri; langkah 6 mencatat 404 itu sebagai harapan.
Data snapshot (`~/argus-staging/data`) dibangun dari `~/pilot3a_live/jobs`, yang tidak memuat tiga job pilot; angka yang dibandingkan di langkah 5 adalah snapshot itu.

| # | perintah | harapan |
|---|---|---|
| 0 | `$A stage status`; `docker ps` | ledger live Stage 18 `j20261112_053107_1929-1aeb82d3e220.up2`, `last monitor: pass`; satu container |
| 1 | `$A stage check j20261115_181548_0bc4 --env ledger_py312_up2` | exit 0, `stage check PASS` (seluruh tes ledger di `88c31e1`, di image yang dipin) |
| 2 | `$A stage deploy j20261115_181548_0bc4 --runtime ledger_staging_up2 --yes` | exit 0; live rilis Stage 19, smoke pass; rollback → Stage 18 `.up2` |
| 3 | `$A stage viewer-smoke` | exit 0, semua pass (lewat proxy 8710) |
| 4 | `$A stage monitor` | exit 0, `ok: true`, ledger Stage 19, viewer rilis `11ce2049bfc4` |
| 5 | `python pilots/staging_stage19/probe.py` (baca saja, lewat soket rilis) | semua `ok`: kunci dan urutan, total = jumlah entri = `cost_nano` `/summary`, tiga jenis berjumlah total tanpa filter, `?kind=nope` dan `?kind=` 400, `evil.example` 400 |
| 6 | `curl -s -o /dev/null -w %{http_code} 127.0.0.1:8710/api/scoreboard/models` | **404** (ketergantungan di atas, dicatat bukan diperbaiki); `/api/scoreboard` dan `/api/summary` tetap 200 |
| 7 | `$A stage status`; `docker ps` | ledger live Stage 19, rollback → Stage 18; satu container; `docker inspect`: `NetworkMode=none`, `ReadonlyRootfs=true`, `CapDrop=[ALL]`, user `1001:1001`, `no-new-privileges`, `/data` read-only |

Rollback (bukan bagian rencana ini, butuh "go live" sendiri): `$A stage rollback --yes` (ledger → Stage 18).
