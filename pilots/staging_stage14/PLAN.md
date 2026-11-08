# Deploy batch 5: argus-ledger Stage 14 (issue 016) dan viewer 021-023 ke staging

**"Go live" Atha 2026-11-08 ("Go live", sesudah 023 applied).** Claude menjalankan langkah berurutan dari `~/pilot3a_live`
(`main`; job batch 5 ada di `jobs/` checkout itu), **satu langkah = satu perintah**, mencatat output di folder ini
(`stepN_*.log`), dan berhenti di langkah pertama yang tidak sesuai harapan (exit ≠ 0, smoke gagal, `docker inspect` beda,
`status` beda), tanpa menambah atau mengulang langkah. Hanya staging; tanpa model; port 8000 tidak disentuh; unit proxy
tidak diubah.

`A = ~/Argus-agent/.venv-verify/bin/python scripts/argus.py`.
- Ledger: job 016 = `j20261107_171214_be81` (APPLIED, argus-ledger `1d3a8ea`: Stage 13 + `GET /jobs/<id>/draft`).
  Rilis = `j20261107_171214_be81-1d3a8ea….up2` di runtime `ledger_staging_up2`.
- Viewer: job 023 = `j20261107_174855_60fa` (APPLIED, argus-viewer `70b5532`, di atas 022 `39a1c62`, tes 022 dilonggarkan
  `acdc264`, 021 `518b34f`/`ab43761`). `public/`, `index.html`, `package.json` tidak berubah sejak rilis 020 (`0b02b87`).
  Rilis = `j20261107_174855_60fa-70b553214782`.
- Urutan: ledger dulu (halaman draf viewer membaca `/api/jobs/<id>/draft`, yang dijawab ledger Stage 14).

Setelah langkah yang menjalankan container ledger: `docker inspect` (`NetworkMode=none`, `ReadonlyRootfs=true`,
`CapDrop=[ALL]`, user `1001:1001`, `no-new-privileges`, `/data` = `~/argus-staging/data/pub` read-only, Image
`6d8fc5cc3639`), tepat satu container `argus-staging-ledger-*`.

| # | perintah | harapan |
|---|---|---|
| 0 | `$A stage status`; `$A stage viewer-status`; `docker ps` | ledger live `j20261104_152512_b93a-4e947a0ffe8b.up2`, `last monitor: pass`; viewer live `j20261106_085425_46a7-0b02b87bad84`; satu container `ec3e9be57ebc` |
| 1 | `$A stage check j20261107_171214_be81 --env ledger_py312_up2` | exit 0, `stage check PASS`, 145 tests |
| 2 | `$A stage deploy j20261107_171214_be81 --runtime ledger_staging_up2 --yes` | exit 0; live `j20261107_171214_be81-1d3a8ea….up2`, smoke pass; rollback → Stage 13 `.up2` |
| 3 | `$A stage viewer-deploy j20261107_174855_60fa --yes` | exit 0; live rilis 023; rollback berikutnya = rilis 020 |
| 4 | `$A stage viewer-smoke` | exit 0, semua pass (lewat proxy 8710) |
| 5 | `$A stage monitor` | exit 0, `ok: true`, ledger Stage 14, viewer rilis 023 |
| 6 | `curl` di `127.0.0.1:8710`: `/api/jobs/j20261107_174855_60fa/draft`, `/api/jobs/j20261022_193403_3beb/draft`, `/jobs/j20261107_174855_60fa/draft` | 200 JSON, `draft_sha256` mulai `27312a728673`, kunci tepat `draft_sha256, summary, review, judge`; 404 `no draft` (job lama tanpa `draft/`); 200 `index.html` rilis 023 |
| 7 | `$A stage status`; `$A stage viewer-status`; `docker ps` | ledger live Stage 14 `.up2`, rollback → Stage 13 `.up2`; viewer live rilis 023; satu container |

Rollback (bukan bagian rencana ini, masing-masing butuh "go live" sendiri): `$A stage rollback --yes` (ledger → Stage 13
`.up2`), `$A stage viewer-rollback` (viewer → rilis 020).

Sesudahnya di HP: `/jobs/<id>/draft` untuk job yang menunggu approve (kartu keputusan, sha12, biaya, alasan merah, plan,
review penuh tertutup); link "draft review" di halaman job. Lalu `RESULT.md`, PENDING, memori (jalur cepat).

## Revisi 1 (2026-11-08 02:3x UTC)

"Go live" pertama berhenti di langkah 6: `/api/jobs/j20261107_174855_60fa/draft` → 404 `{"error": "not found"}` (404 milik
proxy, bukan ledger). Langkah 0-5 sesuai harapan: ledger Stage 14 `.up2` dan viewer rilis 023 live. Penyebab: proxy
`argus-stage-proxy` berjalan sejak 2026-10-30 17:02 dan belum memuat regex API D3 (#357); rencana ini lupa restart.
"Go live" kedua Atha 2026-11-08 untuk langkah lanjutan (unit proxy tidak diubah, hanya di-restart):

| # | perintah | harapan |
|---|---|---|
| r1 | `systemctl --user restart argus-stage-proxy` | exit 0; unit active, listen hanya `127.0.0.1:8710` |
| r2 | `$A stage viewer-smoke` | exit 0, semua pass |
| r3 | langkah 6 lagi | seperti langkah 6 |
| r4 | langkah 7 lagi | seperti langkah 7 |
