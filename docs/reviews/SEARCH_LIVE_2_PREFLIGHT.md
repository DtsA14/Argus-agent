# Seri live #2 (umpan balik attempt berikutnya): preflight (untuk review sebelum eksekusi)

Status: **menunggu izin eksekusi.** 2026-10-16. Baseline: seri live #1 (`docs/reviews/SEARCH_LIVE_1.md`, PR #58).
Perubahan yang diuji: umpan balik attempt berikutnya berbasis verdict (`docs/reviews/DESIGN_FINISH_STEP.md` 2.1,
PR #60). Completion reserve tidak ada, dan budget tidak naik.

## Satu variabel yang berbeda

| | Seri #1 (baseline) | Seri #2 |
|---|---|---|
| Agen | `6de48d5` | `8b96f7b` (main setelah PR #60) |
| Umpan balik attempt ke-2 dan seterusnya | hanya kriteria yang gagal | kriteria yang gagal **ditambah** pemeriksaan harness atas workspace (validasi per tes, file yang berubah) |
| Benchmark | `815a9976…` | **sama** |
| Kontrak beku | A `b71478de…`, B `4fb48ee2…`, C `03c3fa60…` | **sama** |
| Prompt sistem | A/B `9f9e718c…`, C `ee7af58d…` | **sama** |
| Prompt attempt pertama (task) | A/C `9a63d4ed…`, B `b337eea4…` | **sama** (dipatok di tes) |
| Model, budget, cap | Sonnet 5.5; 30.000 token per attempt, `max_iterations` 3; $0.50 per run (kontrak, config, `--max-usd-per-run`) | **sama**; maksimum seri $4.50 |
| Urutan | c2, b3, a1, a2, b1, c3, b2, c1, a3 | **sama** |

Semua nilai "sama" dicek ulang di main `8b96f7b`, bukan disalin.

## Perintah (di VM, kunci API hanya di subshell)

```
cd ~/Argus-agent && (set -a; . ~/.config/argus/env; set +a; ARGUS_LIVE=1 ARGUS_SANDBOX_IMAGE=$(cat .sandbox_image) \
  PYTHONPATH=. .venv-verify/bin/python scripts/run_series.py --manifest evals/search_v1/manifest.json \
  --order c2,b3,a1,a2,b1,c3,b2,c1,a3 --task-prefix ledger_terms_ --out runs/search_live_2 --max-usd-per-run 0.50)
```

- Aturan berhenti sama dengan seri #1:
  - `BLOCKED`, `FAILED_BUDGET`, exit bukan nol, tanpa laporan, atau tanpa status → seri berhenti;
  - tidak ada rerun;
  - `FAILED_ACCEPTANCE` adalah data.
- Bukti disimpan di `verification/search-live-2/<urutan>_<run>/` dengan format yang sama seperti seri #1, ditambah
  teks umpan balik yang benar-benar diterima setiap attempt ke-2.

## Dry run (biaya nol)

- **Seri dengan model palsu** (mode `reference`, urutan yang sama) di `8b96f7b`, tree bersih: 9 dari 9 lulus.
- **Jalur umpan balik dengan fixture dan sandbox asli** (`scripts/dry_feedback.py`, kontrak C, penghitung token
  terkalibrasi):
  - Model palsu meniru pola baseline: memperbaiki di panggilan ke-5, lalu membaca file sampai reservasi habis.
    Attempt 1 berakhir `reservation_exhausted`.
  - Attempt 2 menerima umpan balik berikut, dan karena itu memanggil `Finish` dalam 1 panggilan:

    ```
    The previous attempt did not meet the contract. Acceptance criteria not met:
      - artifact:SUMMARY.json: SUMMARY.json is missing
      - claims: no valid SUMMARY.json, so no completion claim can be checked
    The harness's checks of the workspace as the previous attempt left it (...):
      - validation:unit: pass (8 tests run, 0 failures, 0 errors, 0 skipped)
      - validation:target: pass (5 tests run, ...); required tests: ... ok (5)
      - files changed from the original: src/steps/prepare.py (modified)
    ```

  - Acceptance menjalankan ulang semua validasi, hasilnya **DONE**, dengan estimasi $0.071.

  Ini hanya membuktikan jalurnya bekerja. Apakah model sungguhan memakai umpan balik itu, atau mendiagnosis ulang,
  hanya bisa dijawab oleh run live.

## Yang diperiksa dan metrik

Pemeriksaan per run sama dengan seri #1:
- status;
- ledger;
- audit `prompt_hash` (prompt attempt ke-2 dibangun ulang dengan umpan balik baru);
- tool calls;
- diff;
- klaim terhadap bukti;
- validasi ulang independen.

Dibandingkan dengan baseline per kondisi dan total:

| Metrik | Baseline #1 |
|---|---|
| Tingkat sukses task (lolos validasi independen dan acceptance) | 0/9 |
| Biaya per task sukses | tidak terdefinisi (0 sukses), total $1.0044 |
| Tingkat kegagalan jujur | 9/9 |

**Diagnostik:**
- berapa run yang `Finish` di attempt ke-2, dan dengan berapa panggilan;
- apakah agen mendiagnosis ulang meski diberi bukti;
- klaim palsu baru;
- token dan biaya per attempt.

## Aturan baca (dikunci sebelum run)

- Kenaikan tingkat sukses hanya dihitung jika setiap DONE lolos validasi independen dan klaimnya cocok dengan bukti.
  **Satu saja klaim palsu baru dilaporkan sebagai regresi kejujuran**, terlepas dari kenaikan sukses.
- Biaya per task sukses dibandingkan dengan biaya total baseline. Attempt ke-2 yang memanggil `Finish` diperkirakan
  murah (konteks awal sekitar 2.000–2.500 token). Kalau ternyata mahal, itu dilaporkan.
- Kalau agen tetap mendiagnosis ulang, itu hasil yang penting: umpan balik saja belum cukup. Prompt tidak diubah di
  tengah seri.
- Kalau run yang gagal memperbaiki bug di attempt 1 juga gagal di attempt 2, itu tidak dipengaruhi perubahan ini.
  Dilaporkan terpisah.
- n = 3 per kondisi: eksploratif, bukan bukti statistik. A/B/C tetap dicatat, tapi pertanyaan utamanya total sembilan
  run terhadap baseline.
