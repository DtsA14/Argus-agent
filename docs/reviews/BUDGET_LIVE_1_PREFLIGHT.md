# Eksperimen budget 30k vs 45k: implementasi dan preflight (untuk review sebelum izin live)

Status: **menunggu review; belum ada izin live run.** 2026-10-17. Desain: `docs/reviews/DESIGN_BUDGET_45K.md` (PR #64,
revisi 1).

## 1. Implementasi (PR ini)

| Bagian | Isi | Dijaga oleh |
|---|---|---|
| Config lengan | `evals/budget_v1/config_30k.yaml` dan `config_45k.yaml`, dibuat dari `config.yaml` | tes: dibanding `config.yaml` hanya `code_task.attempt_tokens` dan `budget.max_usd` ($1.00) yang berbeda; antarlengan hanya `attempt_tokens` |
| Kontrak | `fixtures/contracts/ledger_cap1_{a,b,c}.json` | tes: dibanding `ledger_terms_{a,b,c}` hanya id dan `limits.max_usd` ($1.00) yang berbeda. Kontrak repo tidak berubah |
| Manifest | `evals/budget_v1/manifest.json` (di luar Eval Set v1) | tes: naskah reference dan wrong sama dengan `search_v1`; label tidak masuk ke kontrak |
| Admission | tanpa perubahan harness | tes dengan `settings` dan `admission` asli: attempt berikutnya diterima tepat selama pengeluaran ≤ $0.70 (30k) / ≤ $0.55 (45k), dan $0.01 di atasnya ditolak; yang dihitung pengeluaran, bukan reservasi; kedua lengan mendapat 3 attempt pada biaya yang masuk akal; hanya kasus patologis 45k yang kehilangan attempt ke-3 |
| `scripts/run_series.py` | entri berlengan (`a1@45`) → `--config` lengan itu; `--pairs`; `--max-usd-series` dicek per pasangan dari biaya ledger | tes: config per lengan; seri yang salah bentuk ditolak sebelum ada run; cap tidak pernah memotong pasangan dan tidak pernah terlampaui; pasangan dengan run `BLOCKED` ditandai `incomplete`; tanpa `--pairs` cap dicek per run |
| `scripts/analyze_series.py` | bukti pendukung per run (bagian 2 desain) | dicoba pada seri #2, dan hasilnya cocok dengan analisis manual di `M3_CLOSING.md` |

Loop agen, LLMCaller, acceptance, umpan balik, dan prompt tidak berubah.

**Verify:** `verify.sh` di VM pada `a3b52d2` lulus **900 tes, 0 skip**.

## 2. Yang dikunci untuk run

| | |
|---|---|
| Variabel | `attempt_tokens` 30.000 vs 45.000 (config lengan) |
| Sama di kedua lengan | commit; kontrak `ledger_cap1_*`; prompt sistem (A/B `9f9e718c…`, C `ee7af58d…`); prompt task attempt pertama (A/C `9a63d4ed…`, B `b337eea4…`, identik dengan `ledger_terms_*`); umpan balik attempt berikutnya; model Sonnet 5.5; `max_steps` 12; `stagnation_rounds` 2; `max_iterations` 3; cap $1.00 per run |
| Benchmark | `evals/budget_v1`, hash `cbd72ea1f9c8c484cbea7b591cf7c08fe11ae610a6ddf2f8fa9d0723d72ce593` |
| Kontrak beku (`contract_sha`) | A `d8f40b04…`, B `ab001c77…`, C `871bd71d…` |
| Run | 18: A/B/C × 3 per lengan, 9 pasangan |
| Urutan | seed 20261017 (sel diacak, lalu urutan lengan diacak di dalam setiap pasangan; 45k lebih dulu di 5 dari 9 pasangan) |
| Cap | $1.00 per run (config, kontrak, `--max-usd-per-run`); **cap seri $5.00** dicek per pasangan; saldo provider ≥ $5.00 sebelum run |
| Agen | main setelah PR ini di-merge. Kodenya identik dengan `a3b52d2`, ditambah dokumen dan bukti verify |

Urutannya:

```
c3@45, c3@30, b3@30, b3@45, a3@30, a3@45, c1@45, c1@30, c2@45, c2@30,
a2@45, a2@30, b1@45, b1@30, a1@30, a1@45, b2@30, b2@45
```

**Perintah** (di VM, kunci API hanya di subshell):

```
cd ~/Argus-agent && (set -a; . ~/.config/argus/env; set +a; ARGUS_LIVE=1 ARGUS_SANDBOX_IMAGE=$(cat .sandbox_image) \
  PYTHONPATH=. .venv-verify/bin/python scripts/run_series.py --manifest evals/budget_v1/manifest.json \
  --order c3@45,c3@30,b3@30,b3@45,a3@30,a3@45,c1@45,c1@30,c2@45,c2@30,a2@45,a2@30,b1@45,b1@30,a1@30,a1@45,b2@30,b2@45 \
  --task-prefix ledger_cap1_ --out runs/budget_live_1 --max-usd-per-run 1.00 --pairs --max-usd-series 5.00 \
  --arm-config 30=evals/budget_v1/config_30k.yaml --arm-config 45=evals/budget_v1/config_45k.yaml)
```

**Sumber biaya guard (dicek di kode dan tes, review PR #65).** Pengeluaran yang dijumlahkan guard dihitung di
memori driver dari laporan setiap run yang sudah selesai, bukan dari `series.json` atau estimasi config. Rantainya:
`report.json` `stats.usd_billed` = `result.json` `usd_billed` = `reconcile_ledger` atas ledger run itu.
- Itu biaya aktual setiap panggilan.
- Panggilan yang terpotong crash dihitung worst case.
- Panggilan yang ditolak bernilai $0.

Jalurnya sama di dry run dan live; yang berbeda hanya harga modelnya. Run yang biayanya hilang atau tidak lengkap
(`usd_billed` kosong atau `usd_complete` bukan true) **menghentikan seri**, tidak dihitung $0.

Tes yang menjaganya:
- batas tepat: pengeluaran + $2.00 = $5.00 masih boleh, dan setengah sen di atasnya tidak;
- biaya yang tidak diketahui menghentikan seri;
- pasangan yang run-nya menghentikan seri ditandai `incomplete`.

Empat mutan tertangkap: biaya tidak diketahui dianggap nol, guard hanya menyisakan satu run, guard mengabaikan
pengeluaran, dan run yang berhenti dianggap separuh pasangan yang sah.

**Aturan berhenti:**
- Seri berhenti jika `BLOCKED`, `FAILED_BUDGET`, exit bukan nol, tanpa laporan, tanpa status, atau biaya
  yang tidak diketahui.
- Sebuah pasangan tidak dimulai jika pengeluaran + $2.00 > $5.00.
- Tidak ada rerun, dan tidak ada cap yang dilewati.
- Pasangan `incomplete` atau `not run` tidak dipakai dalam perbandingan berpasangan.
- `FAILED_ACCEPTANCE` adalah data.

## 3. Dry run (biaya nol)

Seri lengkap dengan perintah di atas dalam mode `reference` (model palsu), pada `a3b52d2`:
- **18 dari 18 run**, **9 dari 9 pasangan `complete`**, tidak berhenti;
- setiap run memakai config lengannya (`report.json` mencatat `attempt_tokens` 45000 atau 30000);
- tool efektif A/B lima tool, C empat tool.

Tree tercatat "dirty" hanya karena log verify belum di-commit saat itu. Untuk live, VM harus pada main yang bersih.

## 4. Pemeriksaan sebelum live (dicentang di laporan hasil)

- [ ] VM pada main setelah merge, tree bersih, `runs/budget_live_1` belum ada, saldo ≥ $5.00
- [ ] hash benchmark, kontrak beku, dan prompt sama dengan tabel di atas
- [ ] tidak ada perubahan pada config lengan, kontrak, urutan, maupun aturan henti setelah review ini

## 5. Membaca hasil (dari desain, tidak berubah)

**Sinyal utama:** tingkat sukses 45k vs 30k, ditambah biaya per task sukses (dari ledger) dan tingkat kegagalan jujur.
- Setiap DONE divalidasi ulang secara independen, dan klaimnya diperiksa terhadap bukti.
- Satu klaim palsu adalah regresi kejujuran.

**Bukti pendukung per run:**
- apakah akar masalah dicapai;
- kapan fix pertama ditulis dan dengan berapa token;
- panggilan yang ditolak atau terpotong;
- attempt yang tidak diterima cap;
- biaya per attempt.

Semuanya deskriptif, bukan klasifikasi otomatis. Dengan 9 pasangan, ini sinyal diagnostik, bukan kesimpulan
statistik.
