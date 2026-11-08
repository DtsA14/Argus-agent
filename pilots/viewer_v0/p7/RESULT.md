# Hasil pilot viewer v0 #7: rilis 024, 2026-11-08

Satu "go live" Atha. $0 (tanpa model). Job 024 sendiri: draf $0,0206 + agen $0,0116.

| # | hasil | log |
|---|---|---|
| 0 | ok: viewer rilis 023, satu container ledger Stage 14 `.up2` | `step0_status.log` |
| 1 | ok: live `j20261108_031013_808b-85171747a5fd`, rollback → rilis 023 | `step1_deploy.log` |
| 2 | ok: viewer-smoke 12/12 | `step2_smoke.log` |
| 3 | ok: halaman draf 200 `index.html` dengan aset rilis 024 (`index-CdSmyQzG.js`, memuat "Ringkasan"); API 200, kunci tepat, `draft_sha256` `e3f709d8fb09` | `step3_curl.log` |
| 4 | ok: monitor `ok: true`, viewer rilis 024 | `step4_monitor.log` |
| 5 | ok: viewer rilis 024; container ledger sama | `step5_status.log` |

Penyimpangan prosedur (bukan hasil): langkah 4 dan 5 dijalankan Claude dalam satu perintah (aturan: satu langkah = satu
perintah); langkah 4 lulus, jadi tidak ada langkah yang jalan sesudah kegagalan. Cek aset di langkah 3 adalah perintah baca
kedua dalam langkah yang sama.

K6 (SPEC_CONTROL_UI): Atha membaca draf 024 di HP (halaman draf rilis 023, belum ada Ringkasan) dan memutuskan dalam **3
menit** (batch 3: ±5-7 menit). Tidak bersih: ringkasan approve Claude di chat juga dibaca. Ukuran berikutnya: draf
sesudah rilis 024, Atha memutuskan dari HP sebelum membaca chat.
