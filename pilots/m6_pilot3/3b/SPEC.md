# Pilot 3b: agregator `scripts/pilot_report.py` (spesifikasi untuk review)

Status 2026-10-22: **spesifikasi; belum ada draf, tes, patch referensi, atau run.** Dasar: `pilots/m6_pilot3/SPEC.md` (spesifikasi gabungan
Pilot 3; bagian 4–6 tentang agregator milik 3b) dan keputusan reviewer 2026-10-21: 3b dimulai setelah patch 3a diterapkan dan
diverifikasi di `main`. Itu terpenuhi: PR #137 (`cf537c1`, patch agen `pilot3a5` tanpa perubahan, `verify.sh` 1.291 lulus); pilot 3a
**agent-completed**.

Pertanyaan pilot: bisakah coder menambah **satu keluaran baru dengan definisi eksplisit** di atas pembaca bersama yang sudah ada,
dengan acceptance deterministik; dan (pertanyaan B dari D5 yang belum terjawab di `pilot3a5`) apakah dua putaran perbaikan muat
dalam satu attempt bila dibutuhkan.

## 1. Apa yang sudah ada di `main` (dan berubah sejak spesifikasi gabungan)

- `evals/runlog.py` (ditulis agen di `pilot3a5`): `read_events(run_dir) -> (events, skipped)`, `read_result(run_dir)` (None bila tidak ada),
  `read_memo(run_dir)`, `skipped_line(n)`. `audit_run.py` dan `failure_trace.py` sudah memakainya.
- `evals/score.py` `cost_is_known(stats)`: biaya diketahui hanya bila `usd_billed` ada **dan** `usd_complete is True`.
- `tests/test_run_inspectors.py` `build(root, base)`: membangun run sintetis F1–F5, F5c, F7, F8 dan `wrap` dengan `run_code_task` dan model
  palsu (tanpa biaya, tanpa Docker). Bisa diimpor oleh tes 3b.
- **Koreksi spesifikasi gabungan:** bagian 5 menyebut `events_skipped` "dari `result.json` bila ada". `result.json` tidak punya kunci itu
  (diperiksa pada `pilot3a5`: `attempt, attempts, blocked_reason, budget_profile, cache, contract_sha, llm_calls, llm_calls_unknown,
  loop_policy, provenance, run_id, status, stop_reason, tools, usd_billed, usd_complete, verdict`). Di 3b `events_skipped` selalu dihitung
  dari log dengan `read_events`.

## 2. Task

**Satu berkas baru:** `scripts/pilot_report.py`. Semua yang lain dilindungi, termasuk `evals/runlog.py` dan `evals/score.py` (keduanya
dipakai apa adanya). Agregator tidak membaca keluaran teks skrip lain; ia membaca direktori run lewat `evals/runlog.py`.

## 3. Kontrak `scripts/pilot_report.py`

`python scripts/pilot_report.py RUN_DIR [RUN_DIR ...] [--supervision FILE.json]` mencetak **satu objek JSON** ke stdout (`indent=2`,
urutan kunci persis seperti di bawah, `ensure_ascii=False`), lalu newline. Exit 0.

**Exit 2** (pesan satu baris di stderr, stdout kosong) bila:
- tidak ada argumen run;
- sebuah argumen bukan direktori run: bukan direktori, atau tidak berisi `events.jsonl`;
- berkas supervisi tidak bisa dibaca atau tidak valid (bagian 3c).

### 3a. Per run (`"runs"`, urut seperti argumen)

| Kunci | Definisi |
|---|---|
| `run_id` | nama direktori (`Path(arg).name`) |
| `status` | `result.json["status"]`; `"NO_RESULT"` bila `read_result` memberi `None` |
| `done` | `status == "DONE"` |
| `attempts` | `result.json["attempts"]`; `null` untuk `NO_RESULT` |
| `llm_calls` | `result.json["llm_calls"]`; `null` untuk `NO_RESULT` |
| `usd_billed` | `result.json["usd_billed"]` apa adanya (angka atau `null`); `null` untuk `NO_RESULT` |
| `cost_known` | `cost_is_known(result)` dari `evals/score.py`; `false` untuk `NO_RESULT` |
| `events_skipped` | `skipped` dari `read_events(run_dir)` (selalu dari log) |
| `supervision_minutes` | nilai dari berkas supervisi untuk `run_id`; `null` bila tidak ada berkas atau tidak ada nilai untuk run itu (**tidak pernah 0 sebagai pengganti**) |

### 3b. Agregat (setelah `"runs"`, urutan ini)

| Kunci | Definisi tepat |
|---|---|
| `runs_total` | jumlah argumen run |
| `done` | jumlah run dengan `done` |
| `no_result` | jumlah run `NO_RESULT` |
| `success_rate` | `done / (runs_total - no_result)`, dibulatkan 4 desimal; `null` bila penyebutnya 0. `NO_RESULT` bukan sukses dan bukan gagal |
| `usd_known_total` | jumlah `usd_billed` **hanya** atas run dengan `cost_known` (semua status, yang gagal ikut); dijumlahkan dalam nano-dolar bulat (`round(x * 1e9)`) lalu dibagi `1e9` dan dibulatkan 6 desimal; `0.0` bila tidak ada run yang diketahui biayanya |
| `usd_unknown_runs` | jumlah run dengan `cost_known == false` (termasuk `NO_RESULT`) |
| `cost_per_success` | `usd_known_total / (jumlah run DONE yang cost_known)`, 6 desimal; `null` bila pembaginya 0. Tidak pernah 0 karena data hilang, tidak pernah tak hingga |
| `cost_complete` | `usd_unknown_runs == 0` |
| `attempts` | `{"mean": rata-rata 3 desimal, "median": statistics.median}` atas run **DONE**; `null` bila tidak ada run DONE |
| `attempts_distribution` | `{"<jumlah attempt>": jumlah run}` atas run yang punya `result.json`, kunci string urut naik secara numerik |
| `supervision` | `{"runs_with_data": n, "total": jumlah, "mean": rata-rata 2 desimal}` atas run yang punya nilai; bila `n == 0`, `total` dan `mean` bernilai `null` |
| `events_skipped` | jumlah semua `events_skipped` |

`agent-completed` / `human-assisted` / `failed` (status pilot) **bukan** keluaran agregator: itu keputusan reviewer.

### 3c. Berkas supervisi

Objek JSON `{run_id: menit}`. Valid hanya bila: objek (bukan list atau skalar); setiap nilai angka `int` atau `float` yang bukan `bool`,
terhingga, dan ≥ 0; setiap kunci adalah `run_id` dari salah satu argumen (kunci yang tidak dikenal = salah ketik, ditolak). Run yang
tidak ada di berkas: `supervision_minutes` `null`.

## 4. Fixture dan tes (dibuat saat tes berjalan; tanpa biaya, tanpa Docker)

Tes baru `tests/test_pilot_report.py` (dilindungi, disetujui bersama task) memakai `build()` dari `tests/test_run_inspectors.py` lalu
menyalin dan mengubah salinannya:

| Fixture | Asal | Mengunci |
|---|---|---|
| F1, F2, F3, F5 | `build()` | `DONE` 1 attempt; `DONE` 2 attempt; `FAILED_ACCEPTANCE` (stagnan); di-resume setelah crash |
| F4 | `build()` | `BLOCKED` sebelum panggilan model: `llm_calls` 0, `attempts` 0 |
| F5c | `build()` | satu baris log terpotong: `events_skipped` 1 |
| F6a/b/c | salinan F1 dengan `result.json` diubah: `usd_complete: false` dengan `usd_billed` parsial; tanpa `usd_billed`; tanpa kunci `usd_complete` | biaya tak diketahui, tidak pernah 0; `usd_billed` ditampilkan apa adanya |
| F7 | `build()` (tanpa `result.json`) | `NO_RESULT` |
| S | berkas supervisi: lengkap, sebagian, tidak ada; tidak valid: negatif, string, `true`, list, `NaN`, kunci tidak dikenal | menit hilang `null`; berkas tidak valid exit 2 |

Tes wajib (gagal di baseline karena skrip belum ada: gagal karena exit code dan isi keluaran, bukan error impor):
- keluaran JSON persis untuk satu himpunan (F1, F2, F3, F4, F5c, F6a, F7) dengan dan tanpa supervisi, nilai yang diharapkan ditulis
  dari definisi bagian 3 di tes (bukan direkam dari implementasi);
- kasus tepi: tidak ada run DONE (`cost_per_success` dan `attempts` `null`); semua biaya tak diketahui (`usd_known_total` 0.0,
  `cost_complete` false); hanya `NO_RESULT` (`success_rate` null); supervisi sebagian dan kosong;
- exit 2: tanpa argumen; argumen bukan direktori; direktori tanpa `events.jsonl`; setiap jenis berkas supervisi tidak valid.

Penjaga (lulus di baseline): `tests/test_run_inspectors.py` dan `tests/test_run_inspectors_data.py` tetap lulus (pembaca bersama dan
kedua inspektor tidak berubah).

Mutan yang harus dibunuh tes (dijalankan atas patch referensi sebelum dibekukan): biaya tak diketahui dihitung 0; `cost_per_success`
membagi dengan semua run DONE (bukan hanya yang biayanya diketahui); `success_rate` menghitung `NO_RESULT` sebagai gagal; menit hilang 0;
`done` sebagai `status != "FAILED_ACCEPTANCE"`; supervisi tidak valid diterima (masing-masing jenis); `bool` diterima sebagai menit;
`events_skipped` dari `result.json` (selalu 0); urutan kunci berubah; median diganti mean; pembulatan berubah; `attempts_distribution`
tanpa run yang tidak DONE.

## 5. Validasi kontrak (lingkungan sandbox `argus`)

- `report`: `pytest tests/test_pilot_report.py`, semua tes wajib di `must_pass`.
- `regression`: `pytest tests/test_run_inspectors.py tests/test_run_inspectors_data.py tests/test_eval_cost.py tests/test_run_stats.py`
  (pembaca bersama, kedua inspektor, `cost_is_known`).

## 6. Anggaran dan config

Sama dengan pilot D5 (`pilot3a5`): profil `large_usd` ($0,45 per attempt, masukan ≤ 40.000 per panggilan), cap $0,75, 3 iterasi, Sonnet
5.5, validasi otomatis menyala, prompt caching menyala. Task ini lebih kecil dari 3a (satu berkas baru; yang perlu dibaca: `evals/runlog.py`
1,4 KB, `evals/score.py` 9,8 KB, tes baru, dan `build()` di `tests/test_run_inspectors.py` 8,6 KB). Dengan caching, `pilot3a5` menghabiskan
$0,15 untuk 8 panggilan; perkiraan untuk 3b di bawah itu, kecuali agen butuh banyak putaran perbaikan. Simulasi token tidak dibuat lagi:
D1 (USD) dan D5 (caching) membuat batas yang mengikat adalah USD, dan `pilot3a5` memberi angka nyata per panggilan.

## 7. Urutan

1. Review spesifikasi ini (keputusan bagian 8).
2. Intake `main` sebagai basis baru (`argus_p6`, exclude `verification` dan `pilots` seperti `argus_p3`); draf: kontrak (scope, validasi,
   alat), tes baru, issue; patch referensi `pilot_report.py` dari gue; cek draf tanpa `--approve` (baseline merah tepat pada tes wajib,
   patch referensi hijau, regresi hijau); mutan atas patch referensi.
3. `--approve` oleh Atha; config pilot, gerbang `go_live.sh`, tes gerbang, preflight dengan kriteria ditulis sebelum run.
4. Run live satu kali dengan "go live" Atha; laporan; bila `DONE`, patch diterapkan ke `main` tanpa perubahan setelah review dan `verify.sh`.

## 8. Keputusan yang diminta

1. **K1:** scope satu berkas baru (`scripts/pilot_report.py`); `evals/runlog.py` dan `evals/score.py` dilindungi.
2. **K2:** kontrak bagian 3, termasuk koreksi dari spesifikasi gabungan: `events_skipped` selalu dari log; nama kunci agregat `runs_total`
   (bukan `runs`, supaya tidak bentrok dengan daftar per run); `attempts_distribution` dipisah dari `attempts`; jumlah uang dalam nano-dolar
   bulat; pembulatan 4/6/3/2 desimal; kunci supervisi yang tidak dikenal ditolak.
3. **K3:** tidak ada field baru di luar bagian 3 (mis. data cache dari D5 tidak masuk), supaya task tetap kecil.
4. **K4:** anggaran dan config sama dengan pilot D5 (bagian 6).
5. **K5:** basis = intake `main` setelah spesifikasi ini di-merge (`argus_p6`).
6. **K6:** kriteria pilot ditulis di preflight sebelum run; minimal: `DONE`, perubahan hanya di `scripts/pilot_report.py`, patch diterapkan
   tanpa perubahan dan `verify.sh` lulus untuk `agent-completed`; dicatat jumlah putaran perbaikan (pertanyaan B D5).
