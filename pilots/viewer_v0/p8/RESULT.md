# Hasil pilot viewer v0 #8: rilis 025, 2026-11-08

Satu "go live" Atha. $0 (tanpa model). Job 025: draf $0,0275 + agen $0,0074.

| # | hasil | log |
|---|---|---|
| 0 | ok: viewer rilis 024 | `step0_status.log` |
| 1 | ok: live `j20261108_064429_31e1-ed26eae5cdaa`, rollback → rilis 024 | `step1_deploy.log` |
| 2 | ok: viewer-smoke 12/12 | `step2_smoke.log` |
| 3 | ok: monitor `ok: true`, viewer rilis 025 (07:38:43Z) | `step3_monitor.log` |
| 4 | ok: viewer rilis 025, rollback → 024 | `step4_status.log` |

K6 kedua (bersih: Atha memutuskan di HP dari halaman draf rilis 024 dengan kotak Ringkasan, sebelum ringkasan Claude):
**3 menit**, keputusan approve (sama dengan Claude). Kata Atha: masih bingung karena bagian di bawah Ringkasan terlalu
detail dan teknis. Catatan: draf pertama kali dibuka sebelum masuk snapshot ("no draft to review"; snapshot 06:45:33Z,
drafter selesai ±06:47Z), jadi Atha menunggu monitor 07:00Z.
