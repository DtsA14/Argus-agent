# Pilot dependency upgrade v0 #2 (DRAF): argus-ledger Stage 13 ke stack up2

**Status: draf, belum boleh dijalankan.** Tidak ada "go live" yang diminta sebelum bagian A selesai dan versi di bagian
C dicek ulang pada hari-H. Spek: `docs/reviews/SPEC_DEP_UPGRADE_V0.md` (§3 U1-U4, §6.1: up2 = starlette 1.10.0 + fastapi
0.162.0 mulai 2026-11-07).

Tujuan: staging berakhir di Stage 13 (argus-ledger `4e947a0`, job `j20261104_152512_b93a`) di atas starlette 1.10.0 +
fastapi 0.162.0, dengan cek gzip Stage 13 sebagai pembanding perilaku `GZipMiddleware`, dan rollback antar image
terlatih sekali lagi.

## A. Prasyarat (bukan bagian "go live"; urut)

1. **Jalur ketat, boleh dikerjakan sebelum 2026-11-07** (satu PR; "merge" Atha): `RUNTIMES["ledger_staging_up2"] =
   "ledger_py312_up2"` di `router/stage.py` ("menambah runtime adalah perubahan kode jalur ketat", spek U3); entri
   `ledger_py312_up2` dan `ledger_staging_up2` (`image: null`) di `config.yaml`; `environments/ledger_py312_up2/` dan
   `environments/ledger_staging_up2/` (`base`, `requirements.txt` dengan hash, `README`). Tes: `tests/test_stage.py:589`
   memakai `ledger_staging_up2` sebagai contoh **runtime asing yang ditolak**; harus diganti nama lain (mis.
   `ledger_staging_up9`), dan satu tes baru bahwa up2 diterima serta rollback up2 → up1 memakai image rekaman. Mutants
   dan review sesuai AGENTS.md; `verify.sh` sekali.
2. **Hanya sesudah 2026-11-07 15:05 UTC** (aturan 2 minggu, upload starlette 1.10.0 = 2026-10-24T15:04Z): bangun image
   (`bash scripts/build_env_from_base.sh ledger_py312_up2`, lalu `ledger_staging_up2`), `scripts/check_env_image.py` untuk
   keduanya. Setiap berkas di `requirements.txt` harus diunggah ≥ 14 hari sebelum build.
3. Pin image baru disalin ke `~/pilot3a_live` (`scripts/pin_status.py --against ~/Argus-agent ledger_py312_up2
   ledger_staging_up2`); PR dengan `pin` terbaru tidak perlu bila pin git-ignored.

## B. Rencana (satu "go live" Atha untuk seluruh bagian ini, U4)

Claude menjalankan langkah berurutan dari `~/pilot3a_live` (`main`; job pilot ada di `jobs/` checkout itu), mencatat output
tiap langkah di folder ini (`stepN_*.log`), dan **berhenti di langkah pertama yang tidak sesuai harapan** (exit ≠ 0, smoke
gagal, `docker inspect` beda, `status` beda): tanpa menambah atau mengulang langkah, lalu melapor. Hanya staging; tanpa
model; athena-api (port 8000) tidak disentuh. `A = .venv-verify/bin/python scripts/argus.py`, `J = j20261104_152512_b93a`.

Setelah setiap langkah yang menjalankan container: `docker inspect` (`NetworkMode=none`, `ReadonlyRootfs=true`,
`CapDrop=[ALL]`, user `1001:1001`, `no-new-privileges`, `/data` = `~/argus-staging/data/pub` read-only, **Image** seperti
tertulis), tepat satu container `argus-staging-ledger-*`.

| # | perintah | harapan |
|---|---|---|
| 0 | `$A stage status` | live `J-4e947a0ffe8b.up1` (runtime `ledger_staging_up1`), `last monitor: pass` |
| 1 | `$A stage check J --env ledger_py312_up2` | exit 0, `stage check PASS`, 137 tests (dengan `-W error::DeprecationWarning`) |
| 2 | `$A stage deploy J --runtime ledger_staging_up2 --yes` | exit 0; `tested: stage check passed`; live `J-4e947a0ffe8b.up2`, smoke pass; rollback → `J-4e947a0ffe8b.up1` |
| 3 | `.venv-verify/bin/python -I ~/Argus-agent/pilots/dep_upgrade_v0/p2/gzip_check.py J-4e947a0ffe8b.up2` | exit 0: `/jobs.csv` 200 tanpa `Content-Encoding`; `/jobs` 200 `gzip` |
| 4 | `$A stage monitor` | `ok: true` |
| 5 | `$A stage rollback --yes` | exit 0; live `J-4e947a0ffe8b.up1`, smoke pass; Image `4edca09d1842` (image up1 yang tercatat) |
| 6 | `$A stage deploy J --runtime ledger_staging_up2 --yes` | exit 0; rilis `.up2` yang sudah dibangun dipakai lagi (check langkah 1 masih terakhir); live `.up2`, smoke pass |
| 7 | langkah 3 lagi, lalu `$A stage monitor` | sama seperti langkah 3 dan 4 |
| 8 | `$A stage status` | live `J-4e947a0ffe8b.up2`, runtime `ledger_staging_up2`; rollback → `.up1` |

Langkah 5-7 (latihan rollback antar image) boleh dicoret Atha bila hanya ingin deploy; urutan lain tidak berubah.
Sesudahnya: `RESULT.md` di folder ini, PENDING.md, dan memori staging (jalur cepat, Claude merge sendiri).

## C. Dicek ulang pada hari-H sebelum meminta "go live"

- `git -C ~/pilot3a_live log -1` = main terbaru; bagian A sudah merge dan image up2 lolos `check_env_image`.
- `stage status` sama dengan langkah 0 (bila ada rilis lain sejak Stage 13, nama di tabel diganti).
- Versi di `requirements.txt` up2: starlette 1.10.0 dan fastapi 0.162.0 masih yang terbaru yang boleh (tidak ada rilis
  yang ditarik/yanked di PyPI); pin lain (anyio, pydantic, httpx2, …) ≥ 14 hari dan, sedapat mungkin, sama dengan up1.
- Perubahan breaking fastapi 0.143.2 → 0.162.0 yang menyentuh kode ledger: tidak ada yang dipakai (login membaca body
  sendiri dengan `parse_qs`, tanpa model form/query/body; lihat `pilots/research_need_v0/CANDIDATES.md`); `FastAPI(root_path=)`
  tidak dipakai.
