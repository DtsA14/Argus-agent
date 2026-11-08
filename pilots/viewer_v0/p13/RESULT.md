# Hasil pilot viewer v0 #13: rilis 030, 2026-11-08

"Go live" dari izin sesi Atha. $0 (tanpa model). Issue 030 butuh tiga draf:
- `j20261108_175354_be44`: draf di-approve Claude, tetapi tesnya menyimpang dari issue (bulan Indonesia, $1,555 → $1.55,
  hari berbiaya kecil tinggi 0) dan agen membengkokkan pembulatan (ke ganjil) agar lulus; Claude menolak sebelum applied
  (**REJECTED**, $0,1168). Pelajaran: sebelum approve, cocokkan nilai yang diharapkan tes dengan contoh issue.
- `j20261108_183658_0644` d1: issue diperketat dengan contoh eksplisit; drafter gagal format kontrak 5 kali (NO_DRAFT,
  $0,0370). d2 (redraft): sehat, contoh tes cocok dengan issue, di-approve Claude; agen $0,0153 (1 percobaan, 25 langkah).
  Patch dibaca; vitest penuh 225/225; class grafik ada di CSS.

| # | hasil | log |
|---|---|---|
| 0 | ok: viewer rilis 029 | `step0.log` |
| 1 | ok: live `j20261108_183658_0644-fab5d8759215`, rollback → rilis 029 | `step1.log` |
| 2 | ok: viewer-smoke 12/12 | `step2.log` |
| 3 | ok: monitor `ok: true`, viewer rilis 030 (18:57:40Z) | `step3.log` |
| 4 | ok: viewer rilis 030, rollback → 029 | `step4.log` |
