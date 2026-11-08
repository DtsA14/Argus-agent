# Pilot viewer v0 #10: rilis issue 027 (tema warna dari token Tailwind) + setup Tailwind

**"Go live" dari izin sesi Atha (jalur cepat, termasuk go live), sesudah "Y kalo udah ok" untuk applied 027 (2026-11-08).**
Claude menjalankan langkah berurutan dari `~/pilot3a_live` (`main`), **satu langkah = satu perintah**, mencatat output di
folder ini, dan berhenti di langkah pertama yang tidak sesuai harapan, tanpa menambah atau mengulang langkah. Hanya
staging; tanpa model; container argus-ledger dan port 8000 tidak disentuh; proxy tidak di-restart (`router/stage_viewer.py`
tidak berubah).

`A = ~/Argus-agent/.venv-verify/bin/python scripts/argus.py`; job 027 = `j20261108_162504_124b` (APPLIED, argus-viewer
`06aeee76b1c4`, di atas `1ddc449` = setup Tailwind tangan, di atas rilis 026 `10329bd`). Rilis =
`j20261108_162504_124b-06aeee76b1c4`. **Rilis pertama di image `pwa_node22` baru** `87a74d68` (#370, Tailwind 4.3.3);
build lokal di clone ber-patch: CSS memuat `--color-*`, vitest 195/195. Rollback ke 026 memasang `dist` lama (dibangun di
image `9ac2fb43`), tanpa build ulang.

| # | perintah | harapan |
|---|---|---|
| 0 | `$A stage viewer-status` | viewer live `j20261108_103705_ffce-10329bd9e0e3` |
| 1 | `$A stage viewer-deploy j20261108_162504_124b --yes` | exit 0; live rilis 027 di image `87a74d68`; rollback berikutnya = rilis 026 |
| 2 | `$A stage viewer-smoke` | exit 0, semua pass |
| 3 | `$A stage monitor` | exit 0, `ok: true`, viewer rilis 027 |
| 4 | `$A stage viewer-status` | viewer live rilis 027, rollback → rilis 026 |

Sesudahnya di HP: latar lebih gelap, kartu bersudut bulat, aksen biru; tata letak sama. Rollback: `$A stage
viewer-rollback` (ke rilis 026), butuh "go live" sendiri.
