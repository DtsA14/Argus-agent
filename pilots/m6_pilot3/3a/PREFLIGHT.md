# M6 pilot 3a: preflight, rehearsal, dan usulan go/no-go

Status 2026-10-21: **usulan untuk review. Belum ada approval resmi, belum ada live run, belum ada panggilan model sungguhan.**
Task: `fix_run_inspectors` (pembaca run bersama `evals/runlog.py` + refactor `audit_run.py` dan `failure_trace.py`, keluaran lama
dipertahankan byte demi byte, tiga crash diperbaiki). Pilot 3b (agregator) menunggu 3a di-merge dan diverifikasi di `main`.

## 1. Keputusan GPT yang dijalankan

Profil `large` dengan cap **$0,75 khusus Pilot 3a**, bukan default global. Syarat: konfigurasi runtime juga mengizinkan $0,75;
preflight dan rehearsal dulu; bila reservasi tetap tidak memberi ruang, berhenti dan evaluasi ulang (tidak otomatis menaikkan cap).

## 2. Rantai batas biaya (dibuktikan, bukan diasumsikan)

Cap sebuah run adalah yang lebih ketat dari `budget.max_usd` di config dan `limits.max_usd` di kontrak (`codetask/run.py:settings`).
Menaikkan salah satunya saja tidak cukup.

| Lapis | Nilai | Dari mana |
|---|---|---|
| `config.yaml` (global) | `budget.max_usd` **$0,50, tidak diubah** | berkas global |
| Config pilot | `budget.max_usd` **$0,75** | `pilots/m6_pilot3/3a/config_pilot3a.yaml`: salinan `config.yaml` yang berbeda **hanya** di satu baris (`diff` di bawah; perbandingan YAML terurai: satu beda, `/budget/max_usd 0.5 -> 0.75`) |
| Kontrak | `limits.max_usd` **$0,75**, `max_iterations` 3, `budget_profile` `large` | `approve_draft.py --max-usd 0.75 --max-iterations 3`; profil dari `draft.json` |
| Profil `large` | reservasi 45.000 token ($0,45 pada $10/M keluaran), keluaran maksimum 8.192 | `config.yaml: code_task.profiles.large` (tidak diubah) |

```
7c7
<   max_usd: 0.50          # hard limit, reserved like tokens: an iteration starts only if its worst case fits
>   max_usd: 0.75          # PILOT 3a ONLY ($0.75, GPT 2026-10-21); config.yaml stays $0.50. hard limit, reserved like tokens: ...
```

Run memakai `--config pilots/m6_pilot3/3a/config_pilot3a.yaml`; tanpa itu cap kembali $0,50 (lihat 3 di bawah).

## 3. Rehearsal dengan model terskrip (worktree buangan di VM, sandbox sungguhan, tanpa uang)

Persetujuan di worktree buangan itu hanya latihan (seperti pilot 2); bukan approval resmi, dan tidak ada yang dipublikasikan ke
repositori. Kontrak latihan: sha256 `0826ee93de65…`, profil `large`, batas `max_usd` 0,75, tools `search_files` dan `edit_file`.

| Latihan | Hasil |
|---|---|
| **happy** (patch referensi lewat model terskrip, validasi, Finish jujur) | `DONE`, 1 attempt, 8 panggilan; profil teraplikasi `large` (45.000 / 8.192). `build_review.py`: paket **valid**, 12 cek ok, perubahan hanya tiga file task ditambah dua berkas tes yang disetujui (`evidence/happy/review/`) |
| **negative** (mengedit tes dan `harness/events.py`, keduanya ditolak, klaim palsu) | `FAILED_ACCEPTANCE` (stagnan, 2 attempt), tidak ada paket review |
| **admission** (model **berharga** claude-sonnet-5-5, penghitung terkalibrasi, jalur bersih ±38k token, lalu validasi gagal) di config pilot | attempt 1 memakai **$0,109**, attempt 2 **diterima** dan memakai $0,090; berhenti `stagnant` setelah 2 attempt (aturan stagnasi, bukan cap). Tabel admisi dari `settings()` sungguhan: cap $0,75, reservasi $0,45, **3 attempt** diterima bila tiap attempt menghabiskan seperti jalur bersih |
| **admission** dengan `config.yaml` (kontrol negatif) | cap $0,50; run berhenti `max_usd` setelah **1 attempt** ($0,109); attempt kedua ditolak sebelum dikirim. Ini membuktikan bahwa config pilot yang membuat perbedaan |

Kesimpulan atas syarat GPT: reservasi `large` memberi ruang yang memadai pada cap $0,75 (attempt pertama muat, attempt kedua
diterima setelah ±$0,11 terpakai). Tidak ada alasan berhenti dari rehearsal.

Yang **tidak** dibuktikan: perilaku model sungguhan (berapa file dibaca, apakah menulis seluruh file atau menyunting, apakah
butuh siklus perbaikan). Simulasi token menunjukkan satu siklus perbaikan tidak muat di 45k (±52k), jadi hasil `FAILED_BUDGET`
atau `reservation_exhausted` pada attempt pertama adalah hasil yang mungkin dan jujur.

## 4. Gerbang preflight yang sudah diperiksa sekarang

| Gerbang | Hasil |
|---|---|
| Skrip menolak model nyata tanpa `ARGUS_LIVE=1` | ya: `refused: the coder model anthropic:claude-sonnet-5-5 is real and spends money; set ARGUS_LIVE=1`, exit 2, tidak ada run dibuat |
| Docker sehat, arsitektur | `aarch64`, Docker 29.1.3; image `argus`: `sha256:d6b30036444e…` |
| Intake `argus_p3` | `intake_repo.py --check argus_p3 --repo`: `problems: []` (commit `a0075a915b83`, tree `736fdb9a0e3f`, 386 file, snapshot `7520a7ca3644…`) |
| Draft check dengan `--max-usd 0.75` | `ok: true`, baseline merah tepat pada 5 tes wajib, patch referensi lulus, regresi lulus (`check_report.json`) |
| Verifikasi atas "main + patch referensi + tes" | `verify.sh` 1199 lulus, 0 skip sandbox; 21/21 mutan (commit `4e906a6`) |

Gerbang yang baru bisa diperiksa setelah approval resmi dan merge bukti: `git status` kosong pada checkout live, `intake --check`
untuk record task, sha256 kontrak = `0826ee93de65…`, checkout live bersih (`provenance.argus.dirty: false`).

## 5. Urutan menuju live run (tidak ada langkah yang dijalankan sebelum persetujuan di kolom kanan)

| # | Langkah | Persetujuan |
|---|---|---|
| 1 | Review artefak ini dan bukti rehearsal | GPT + Atha |
| 2 | Merge PR artefak 3a (draft, issue, patch, tes, config pilot) ke `main` | Atha |
| 3 | `approve_draft.py ... --max-usd 0.75 --max-iterations 3 --approve` pada checkout bersih (**tindakan manusia**); sha256 kontrak harus `0826ee93de65…` | Atha, eksplisit |
| 4 | PR bukti: record intake, record task, kontrak, laporan cek; snapshot tetap lokal; checkout live bersih lagi | |
| 5 | Gerbang preflight bagian 4 (sisa) | |
| 6 | Live run **satu kali**: `ARGUS_LIVE=1 python scripts/run_code_task.py --contract fixtures/contracts/fix_run_inspectors.json --run-id pilot3a --config pilots/m6_pilot3/3a/config_pilot3a.yaml --sandbox docker`; kunci API dibaca diam-diam di shell VM (tidak di chat, commit, atau argumen proses) | Atha, eksplisit "go live" |
| 7 | `build_review.py`, catat status, biaya, waktu supervisi, apakah patch identik dengan referensi atau butuh intervensi; `verify.sh` atas hasilnya | |

Aturan henti: `FAILED_ACCEPTANCE`, `BLOCKED`, `FAILED_BUDGET` dicatat sebagai hasil dan **berhenti**; tidak ada run ulang, kenaikan
cap, atau profil lain tanpa persetujuan baru. `--resume` hanya untuk run yang mati. Hasil pilot (`agent-completed`,
`human-assisted`, `failed`) diputuskan reviewer. Pilot 3b tidak dimulai sebelum patch 3a diterapkan dan diverifikasi di `main`.

## 6. Usulan

**GO bersyarat**: (a) review artefak dan bukti rehearsal, (b) approval resmi eksplisit (langkah 3), (c) persetujuan atas bagian 2
(cap $0,75 khusus pilot, config global tidak berubah), (d) kunci disediakan Atha, (e) "go live" eksplisit. Biaya yang diharapkan
±$0,10 per attempt pada jalur bersih; batas keras $0,75 dan paling banyak 3 attempt.
