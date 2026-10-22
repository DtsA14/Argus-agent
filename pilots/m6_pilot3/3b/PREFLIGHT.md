# Pilot 3b: preflight (ditulis sebelum run)

Status 2026-10-22: **persiapan; belum ada approval atau run.** Spesifikasi: `3b/SPEC.md` (K1–K6 disetujui Atha). Task: agregator
`scripts/pilot_report.py` di atas `evals/runlog.py` (tulisan agen di `pilot3a5`).

## 1. Artefak dan cek (tanpa biaya)

| | |
|---|---|
| Basis | intake `argus_p6` = `main` `f37aaba` (423 berkas, snapshot `6954b618bf78…`; exclude `verification`, `pilots`), `fixtures/intake/argus_p6.json` |
| Issue | `3b/issue.txt` (1.712 karakter; batas kontrak 2.000) |
| Draf | `3b/draft.json`: writable hanya `scripts/pilot_report.py`; `evals/runlog.py`, `evals/score.py`, kedua inspektor dan semua yang lain dilindungi; alat tambahan `search_files`, `edit_file`; profil `large_usd`; tes baru `tests/test_pilot_report.py` (= `3b/new_test.py`) |
| Validasi | `report`: `tests/test_pilot_report.py`, 17 tes wajib; `regression`: kedua tes inspektor 3a, `test_eval_cost.py`, `test_run_stats.py` (≥ 30 tes) |
| Patch referensi | `3b/reference.patch` (= `3b/reference/scripts/pilot_report.py`, 110 baris, satu berkas baru) |
| Cek draf tanpa `--approve` | `3b/check_report.json`: **ok**, tanpa masalah; baseline: `report` gagal tepat pada 17 tes wajib, `regression` lulus; referensi: keduanya lulus, hanya `scripts/pilot_report.py` ditambah. sha256 kontrak bila disetujui: **`bff30d351f1c`** |
| Mutan atas referensi | `3b/mutants.log`: **20/20** terbunuh (biaya tak diketahui dihitung, pembagi biaya per sukses, `NO_RESULT` sebagai gagal, menit hilang 0, `done`, setiap jenis berkas supervisi tidak valid, `events_skipped` dari `result.json`, urutan kunci, median, pembulatan, distribusi, stderr, direktori tanpa log) |
| Tes di baseline | 17 gagal, semuanya karena assertion (skrip belum ada: exit code dan isi keluaran) |

Nilai yang diharapkan di tes ditulis dari definisi issue: status, attempt, dan jumlah panggilan sebagai literal; `usd_billed` tiap run dibaca
dari `result.json`-nya sendiri (masukan laporan; biaya `f5`/`f5c` adalah kasus terburuk panggilan yang terputus crash dan bergantung pada
penghitungan token); agregat dihitung di tes dengan rumus issue, terpisah dari skrip.

## 2. Config dan gerbang

- `3b/config_pilot3b.yaml`: `config.yaml` + empat selisih yang sama dengan pilot D5 (`max_usd` 0,75, `max_tokens` 1.200.000,
  `auto_validate` true, `prompt_cache.enabled` true).
- `3b/go_live.sh`: gerbang D5 untuk task `pilot_report` (satu berkas writable), sha256 kontrak diisi setelah approval
  (`SET_AFTER_APPROVAL` menolak sampai saat itu), run id `pilot3b[1-9]`. Tes gerbang dijalankan setelah approval, seperti v2 dan D5.

## 3. Ekspektasi (sebelum run)

Task lebih kecil dari 3a: satu berkas baru, tanpa refactor. Yang mungkin dibaca agen: tes baru (±11 KB), `build()` di
`tests/test_run_inspectors.py` (8,6 KB), `evals/runlog.py` (1,4 KB), `evals/score.py` (9,8 KB). Dengan caching, `pilot3a5` menghabiskan
$0,15 untuk 8 panggilan dengan masukan sampai 36.000; perkiraan 3b **$0,08–0,20**, satu attempt. Yang paling mungkin gagal di putaran
pertama: detail format (urutan kunci, pembulatan, median sebagai float, pesan stderr), jadi validasi otomatis kemungkinan dipakai lebih
dari sekali.

## 4. Kriteria (ditetapkan sebelum run, tidak diubah sesudahnya)

1. **Berhasil:** `DONE`; perubahan hanya `scripts/pilot_report.py` (dijaga scope); paket review (`build_review.py`) valid.
   `agent-completed` hanya bila patch diterapkan ke `main` tanpa perubahan dan `verify.sh` lulus.
2. **Gagal:** selain itu. Status apa pun dicatat dan **berhenti**: tidak ada run ulang, kenaikan cap, atau perubahan config tanpa
   persetujuan baru. `--resume` hanya untuk run yang mati.
3. **Dicatat (pertanyaan B dari D5):** jumlah putaran perbaikan (validasi otomatis sesudah tulisan yang gagal, lalu tulisan berikutnya) dan
   apakah ≥ 2 putaran terjadi dalam satu attempt; biaya per panggilan, read/write cache dan penghematan; langkah sebelum tulisan pertama;
   puncak masukan; pemanggilan `RunValidation` setelah validasi otomatis; durasi sandbox per `origin`.

## 5. Urutan

| # | Langkah | Persetujuan |
|---|---|---|
| 1 | Merge PR ini (draf, issue, tes, patch referensi, cek, mutan, record intake, config, gerbang, preflight) | Atha |
| 2 | Checkout live ke `main`; `approve_draft.py --draft pilots/m6_pilot3/3b/draft.json --task pilot_report --issue-file pilots/m6_pilot3/3b/issue.txt --max-usd 0.75 --max-iterations 3 --reference-patch pilots/m6_pilot3/3b/reference.patch --approve`; sha256 harus `bff30d351f1c` | **Atha, "approve"** |
| 3 | sha di gerbang, tes gerbang, PR bukti, merge; `go_live.sh --check-only` | Atha |
| 4 | Run live **satu kali**: `bash ~/pilot3a_live/pilots/m6_pilot3/3b/go_live.sh pilot3b1` (kunci di-paste sekali) | **Atha, "go live"** |
| 5 | Laporan menurut bagian 4; bila `DONE`, review dan penerapan patch | |
