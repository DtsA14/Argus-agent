# Pilot 3b, run `pilot3b1`: hasil

2026-10-22. Task `pilot_report` (kontrak `bff30d351f1c`), config `pilots/m6_pilot3/3b/config_pilot3b.yaml` (setup pilot D5), Argus
`400f3a5` (checkout bersih), Sonnet 5.5, D1 + D2 + D3 + D5. Kriteria ditulis sebelum run (`3b/PREFLIGHT.md` bagian 4).

## Ringkasan

| | |
|---|---|
| Status | **`DONE`** (all criteria passed) |
| Attempt | 1, berakhir `finished` di langkah 3 |
| Panggilan model | 4, 0 ditolak |
| Biaya | **$0,1103** (`usd_complete` true); tanpa cache ±$0,168 (hemat $0,057, 34%) |
| Perubahan | hanya `scripts/pilot_report.py` (baru, 137 baris) dan `SUMMARY.json` |
| Paket review | **valid**, 0 masalah; validasi segar `report` dan `regression` lulus |
| Audit | 4 hash diperiksa, 0 mismatch |

## Jalur (`timeline.txt`, `failure_trace.txt`)

| Langkah | Masukan | Read | Write | Keluaran | USD | Kumulatif | Apa |
|---|---|---|---|---|---|---|---|
| s0 | 3.465 | 0 | 3.461 | 134 | 0,0100 | 0,0100 | ListFiles, baca `evals/runlog.py`, SearchFiles `def cost_is_known` |
| s1 | 11.969 | 3.461 | 8.506 | 166 | 0,0233 | 0,0333 | baca tes baru, `evals/score.py`, `scripts/audit_run.py` |
| s2 | 22.068 | 11.967 | 10.099 | 3.170 | 0,0581 | 0,0914 | tulis `scripts/pilot_report.py` dan `RunValidation(report)` di balasan yang sama → lulus (9,2 detik); validasi otomatis: `report` lulus (9,2 detik), `regression` lulus (35,5 detik) |
| s3 | 27.774 | 22.066 | 5.704 | 243 | 0,0189 | 0,1103 | Finish |

Acceptance: `report` lulus (9,3 detik), `regression` lulus (35,6 detik), verdict `pass`.

## Kriteria (`3b/PREFLIGHT.md` bagian 4)

1. **Berhasil: terpenuhi untuk run.** `DONE`; perubahan hanya `scripts/pilot_report.py` (scope juga menjaganya); paket review valid.
   `agent-completed` menunggu penerapan patch ke `main` tanpa perubahan dan `verify.sh`.
3. **Dicatat:**
   - **Putaran perbaikan: 0.** Tulisan pertama lulus semua 17 tes wajib. Pertanyaan B dari D5 (apakah ≥ 2 putaran muat dalam satu attempt)
     **tetap belum teruji**: dua pilot berturut-turut tidak membutuhkannya.
   - Langkah sebelum tulisan pertama: 2. Puncak masukan 27.774 (taksiran). Tidak ada `budget_violation`, `estimate_overrun`,
     `cache_ttl_unexpected`, `llm_count_failed`, atau `tool_denied`.
   - **`RunValidation` dipanggil di balasan yang sama dengan tulisan**, sebelum validasi otomatis jalan, jadi `report` dijalankan dua kali
     (±9 detik terbuang, tanpa biaya model). Agen tidak tahu bahwa validasi otomatis akan berjalan: prompt sistem tidak menyebutnya
     (keputusan K4 D3). Satu pengamatan; dicatat, bukan diubah.
   - Penghematan cache 34% (`pilot3a5`: 64%): dengan hanya 4 panggilan, prefix yang dipakai ulang lebih sedikit.
   - Ekspektasi preflight ($0,08–0,20, satu attempt): terpenuhi.

## Patch agen (`agent_changes.diff`, `review/changes.patch`)

Hanya membaca berkas (tanpa jaringan, subprocess, atau tulisan). Dibanding patch referensi: argumen di-parse manual (juga
`--supervision=FILE`), `run_id` dari `basename(abspath(d))` (aman untuk jalur berakhiran `/`), `sys.path` diisi sendiri, satu variabel
tidak terpakai (`known`). Perilakunya lulus semua tes yang ditulis dari definisi issue.

## Status pilot

Usulan: **`agent-completed`** bila patch diterapkan ke `main` tanpa perubahan dan `verify.sh` lulus (keputusan Atha).
