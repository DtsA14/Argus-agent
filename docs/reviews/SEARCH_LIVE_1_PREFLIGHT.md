# Eksperimen live search-value #1: preflight final (untuk review sebelum eksekusi)

Status: **menunggu izin eksekusi.** 2026-10-16. Desain dan hasil simulasi: `docs/reviews/TASK_SEARCH_VALUE.md`.
Fixture sudah di main (PR #56).

## Yang dikunci

| | |
|---|---|
| Kondisi | A: search tersedia; B: search + satu kalimat netral; C: tanpa search, semua tool lain sama |
| Run | 3 per kondisi, 9 total, satu kali masing-masing. Tidak ada rerun manual |
| Model | `anthropic:claude-sonnet-5-5` (input $2, output $10 per juta, dari `config.yaml`) |
| Budget token | `attempt_tokens` 30.000, `max_steps` 12, `stagnation_rounds` 2, `max_iterations` 3. Semuanya dari `config.yaml`, sama untuk semua kondisi |
| Cap biaya | kontrak $0.50 (`limits.max_usd`, sama di A/B/C), config `budget.max_usd` $0.50, `--max-total-usd 0.50` per run. **Maksimum seri: 9 × $0.50 = $4.50.** Itu batas, bukan target |
| Benchmark | `evals/search_v1/manifest.json`, hash `815a997630051763c1ba4dc304a6758a81e3776f78dda656b1fda43bafc0ab26` |
| Kontrak beku (`contract_sha`) | A `b71478de…dccd8e`, B `4fb48ee2…bfa19612`, C `03c3fa60…2843f2e0` |
| Prompt sistem efektif | A dan B `9f9e718c7ae339f8666475159e8867e97c048e4c3c48ae8421435389f61882a6` (lima tool). C `ee7af58da465bd579f4f82ba9547cfefbc441577f89b04a101fdd123ee0d3bc0` (empat tool) |
| Tool efektif | A/B `list_files, read_file, write_file, run_validation, search_files`; C tanpa `search_files` |
| Agen | main setelah PR preflight ini di-merge (hanya menambah skrip dan dokumen). Hash benchmark dan prompt di atas tidak bergantung pada commit itu, dan dicek ulang per run |

`system_prompt_sha256` di `report.json` adalah hash prompt default (`ee7af58d…`), juga untuk A dan B. Prompt efektif per
panggilan diaudit dari ledger dengan `scripts/audit_run.py`: setiap `prompt_hash` harus cocok dengan percakapan yang
dibangun ulang memakai prompt efektif kondisinya. Kalau ada yang tidak cocok, itu anomali.

## Urutan acak (dikunci)

`random.Random(20261016).shuffle(["a1","a2","a3","b1","b2","b3","c1","c2","c3"])`:

**c2, b3, a1, a2, b1, c3, b2, c1, a3**

## Perintah (di VM, kunci API hanya di subshell)

```
cd ~/Argus-agent && (set -a; . ~/.config/argus/env; set +a; ARGUS_LIVE=1 ARGUS_SANDBOX_IMAGE=$(cat .sandbox_image) \
  PYTHONPATH=. .venv-verify/bin/python scripts/run_series.py --manifest evals/search_v1/manifest.json \
  --order c2,b3,a1,a2,b1,c3,b2,c1,a3 --task-prefix ledger_terms_ --out runs/search_live_1 --max-usd-per-run 0.50)
```

- `scripts/run_series.py` menjalankan setiap run lewat `scripts/run_eval.py --mode live`, dengan `--max-total-usd 0.50`
  per run, ke direktori sendiri `runs/search_live_1/<urutan>_<run>`.
- `run_eval` menolak direktori yang tidak kosong, sehingga hasil tidak pernah tercampur atau dipakai ulang.
- **Seri berhenti** pada run pertama yang memenuhi salah satu kondisi ini:
  - berakhir `BLOCKED` atau `FAILED_BUDGET`;
  - `run_eval` keluar dengan kode bukan nol, **walaupun laporannya ada**;
  - tanpa laporan;
  - task tanpa status.

  Run sisanya tidak dijalankan dan tidak diulang. `series.json` selalu ditulis, dengan `stopped` (run dan alasan,
  termasuk stderr untuk exit bukan nol). Di mode live, `run_eval` keluar 0 untuk setiap hasil yang terskor,
  termasuk `FAILED_ACCEPTANCE`, jadi exit bukan nol tidak pernah merupakan hasil. `FAILED_ACCEPTANCE` adalah data dan
  tidak menghentikan seri.
- Tes `tests/test_run_series.py` (run_eval diganti tiruan) mencakup:
  - exit bukan nol dengan laporan ada → seri berhenti, run berikutnya tidak dijalankan, `series.json` berisi
    alasannya;
  - `FAILED_ACCEPTANCE` → seri lanjut;
  - `BLOCKED`, `FAILED_BUDGET`, tanpa status, tanpa laporan, dan exit 2 → seri berhenti;
  - urutan yang berulang ditolak.

  Dua mutan tertangkap: tanpa cek exit code (2 tes gagal) dan `series.json` tidak ditulis saat berhenti (6 tes gagal).
- Dry run dengan model palsu (mode `reference`, urutan yang sama) di main `207faaf`: 9 dari 9 lulus dalam 45 detik.
  Jalur berhenti juga diuji: run pertama ditolak, sehingga run kedua tidak dijalankan dan `series.json` tetap
  tertulis.

Bukti disalin ke `verification/search-live-1/<urutan>_<run>/`, dengan format yang sama seperti live #7: report, events,
result, verdict, diff, SUMMARY, dan audit.

## Yang diperiksa per run

1. Status akhir dan `stop_reason`, persis dari `result.json`. Penolakan reservasi dicatat terpisah dari status task.
2. Ledger: token dan biaya per panggilan dan per attempt; `llm_call_started` = `llm_call`.
3. Audit prompt: setiap `prompt_hash` cocok dengan prompt efektif kondisinya; tool efektif dari `tools_effective`.
4. Tool calls: apakah search dipakai, query-nya, file yang dibaca, dan berapa tool per langkah.
5. Diff workspace: file yang berubah, apakah perbaikan di akar masalah, dan tes yang dilindungi tidak tersentuh.
6. Klaim di `SUMMARY.json` dicocokkan dengan diff dan validasi.
7. Validasi dijalankan ulang secara independen di sandbox Docker pada salinan workspace akhir.

## Metrik

**Utama, per kondisi:**
- **tingkat sukses task**: run yang lolos validasi independen;
- **biaya per task sukses**: biaya aktual dibagi jumlah task sukses yang tervalidasi;
- **tingkat kegagalan jujur**: proporsi kegagalan tanpa klaim keberhasilan palsu.

**Diagnostik:** token, token per task sukses, jumlah panggilan, file yang dibaca, query search, dan akhir attempt.

## Aturan baca (dikunci sebelum run)

- Search menghemat lebih dari 10% token: sinyal awal positif, dengan mengingat galat ±10% dan n = 3.
- Penghematan 10% atau kurang: belum cukup untuk membenarkan kompleksitas tool berdasarkan eksperimen ini.
- Search mengubah gagal menjadi sukses pada 30.000: nilai operasional yang penting.
- A tidak memakai search: hasil penting, dicatat apa adanya. Instruksi tidak diubah setelah melihatnya.
- Hasil tidak konsisten, atau model tidak mengikuti strategi yang diprediksi: dilaporkan apa adanya. Fixture tidak
  direkayasa ulang.
- Dengan 3 run per kondisi, ini eksperimen eksploratif, bukan bukti statistik.
- Prompt, fixture, kriteria, dan konfigurasi tidak diubah di tengah eksperimen.
