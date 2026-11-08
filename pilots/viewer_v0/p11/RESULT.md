# Hasil pilot viewer v0 #11: rilis 028, 2026-11-08

"Go live" dari izin sesi Atha. $0 (tanpa model). Job 028: draf $0,0383 + agen $0,0168 (1 percobaan, 27 langkah); **approve
dan applied oleh Claude** (delegasi Atha 2026-11-08 untuk jalur cepat; K6 dijeda). Draf: 8 merah semua AssertionError,
writable hanya `src/App.jsx`, tanpa konflik. Patch dibaca; vitest penuh 203/203; build lokal memuat class Tailwind kartu.

| # | hasil | log |
|---|---|---|
| 0 | ok: viewer rilis 027 | `step0.log` |
| 1 | ok: live `j20261108_165011_d3c5-040ce1ed1964`, rollback → rilis 027 | `step1.log` |
| 2 | ok: viewer-smoke 12/12 | `step2.log` |
| 3 | ok: monitor `ok: true`, viewer rilis 028 (17:05:07Z) | `step3.log` |
| 4 | ok: viewer rilis 028, rollback → 027 | `step4.log` |

Catatan tampilan: tanpa preflight, `<p>` di kartu memakai margin bawaan browser (kartu lebih tinggi dari mockup);
dirapikan di issue berikutnya bila perlu.
