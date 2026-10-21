# M6 pilot 4: preflight, rehearsal, dan usulan go/no-go

Status 2026-10-21: **usulan untuk review. Belum ada approval resmi, belum ada live run, belum ada panggilan model sungguhan.**
Task: `fix_is_peak` (`models/pricing.py::is_peak` untuk jendela yang melewati tengah malam; `SPEC.md`). Pilot 3b tidak dimulai.

## 1. Keputusan reviewer yang dijalankan

Profil `large` dengan cap **$0,75 khusus Pilot 4**, bukan default global (konfigurasi `config_pilot4.yaml`). Skenario "agen membaca semua pemakai"
dicatat sebagai risiko; tidak ada kenaikan budget otomatis. Tiga live run: **satu per satu**, review hasil dan biaya sebelum run berikutnya.

## 2. Rantai batas biaya

| Lapis | Nilai | Dari mana |
|---|---|---|
| `config.yaml` (global) | `budget.max_usd` **$0,50, tidak diubah** | berkas global |
| Config pilot | `budget.max_usd` **$0,75** | `pilots/m6_pilot4/config_pilot4.yaml`: salinan `config.yaml` yang berbeda **hanya** pada nilai itu (perbandingan YAML terurai: satu beda, `/budget/max_usd 0.5 -> 0.75`; `diff` dengan akhir baris dinormalkan: satu baris) |
| Kontrak | `limits.max_usd` **$0,75**, `max_iterations` **3**, `budget_profile` `large`, tools `search_files` + `edit_file` | `approve_draft.py --max-usd 0.75 --max-iterations 3`; profil dari `draft.json` |
| Profil `large` | reservasi 45.000 token ($0,45), keluaran maksimum 8.192 | `config.yaml: code_task.profiles.large` (tidak diubah) |

Cap run adalah yang lebih ketat dari config dan kontrak (`codetask/run.py:settings`); jumlah attempt paling banyak `max_iterations` 3.

## 3. Rehearsal dengan model terskrip (worktree buangan di VM, sandbox sungguhan, tanpa uang)

Persetujuan di worktree buangan itu hanya latihan (kontrak latihan sha256 `1c3a063a3ab2…`); tidak ada yang dipublikasikan ke repositori.

| Latihan | Hasil |
|---|---|
| **happy** (baca, sunting seperti patch referensi, validasi `target` dan `regression`, Finish jujur) | `DONE`, 1 attempt, 6 panggilan; profil teraplikasi `large` (45.000 / 8.192). `build_review.py`: paket **valid**, 12 dari 12 cek ok; perubahan hanya `models/pricing.py` dan tes yang disetujui (`evidence/review/`) |
| **negative** (menyunting tes yang dilindungi dan `config.yaml`: ditolak; klaim palsu) | `FAILED_ACCEPTANCE` (stagnan, 2 attempt), tidak ada paket review |
| **admission** (model **berharga**, penghitung terkalibrasi, membaca `pricing.py`, tes baru, `test_models.py`; tidak mengubah apa pun) di config pilot | attempt 1 **$0,066**, attempt 2 **diterima** ($0,071); berhenti `stagnant` setelah 2 attempt. Secara biaya cap $0,75 cukup untuk lebih dari 3 attempt pada pengeluaran seperti ini (hitungan: 5), jadi yang membatasi adalah `max_iterations` 3 dan aturan stagnasi |
| **admission** dengan `config.yaml` (kontrol negatif) | cap $0,50; berhenti `max_usd` setelah **1 attempt**; attempt kedua ditolak sebelum dikirim. Config pilot yang membuat perbedaan |

Syarat reviewer terpenuhi: reservasi `large` memberi ruang pada $0,75; tidak ada alasan untuk berhenti.

Yang **tidak** dibuktikan: perilaku model sungguhan. Simulasi (`TOKEN_SIMULATION.md`) menunjukkan agen yang mengejar semua pemakai `is_peak`
tidak muat di profil mana pun; hasil `reservation_exhausted` adalah hasil yang mungkin dan jujur.

## 4. Gerbang preflight yang sudah diperiksa sekarang

| Gerbang | Hasil |
|---|---|
| Skrip menolak model nyata tanpa `ARGUS_LIVE=1` | ya: `refused: ... set ARGUS_LIVE=1`, exit 2, tidak ada run dibuat |
| Docker | aarch64, 29.1.3 |
| Intake `argus_p4` | `intake_repo.py --check argus_p4`: `problems: []` (commit `983a4ee1d633`, 390 file, snapshot `ffae1c0dd347…`; hash sama di host Windows dan VM) |
| Draft check dengan `--max-usd 0.75`, profil `large` | `ok: true`, baseline merah tepat pada 6 tes wajib, patch referensi lulus, hanya `models/pricing.py` berubah, regresi 17 tes lulus (`check_report.json`) |
| Verifikasi atas "base + patch referensi + tes" | `verify.sh` 1196 lulus, 0 skip sandbox; 16/16 mutan (commit `8cc2897`) |

Gerbang yang baru bisa diperiksa setelah merge dan approval resmi: checkout live bersih (`git status` kosong, `provenance.argus.dirty: false`),
`intake --check` untuk record task, sha256 kontrak `1c3a063a3ab2…`.

## 5. Urutan menuju live run (tidak ada langkah yang dijalankan sebelum persetujuan di kolom kanan)

| # | Langkah | Persetujuan |
|---|---|---|
| 1 | Review artefak ini dan bukti rehearsal | reviewer + Atha |
| 2 | Merge PR artefak (draft, issue, patch, tes, config pilot) ke `main`; `verify.sh` pada `main` | Atha |
| 3 | `approve_draft.py ... --max-usd 0.75 --max-iterations 3 --approve` pada checkout bersih (**tindakan manusia**); sha256 kontrak harus `1c3a063a3ab2…` | Atha, eksplisit |
| 4 | PR bukti (record intake, record task, kontrak, laporan cek); snapshot tetap lokal; checkout live bersih | |
| 5 | Gerbang preflight bagian 4 (sisa) | |
| 6 | Live run **satu**: `ARGUS_LIVE=1 python scripts/run_code_task.py --contract fixtures/contracts/fix_is_peak.json --run-id pilot4a --config pilots/m6_pilot4/config_pilot4.yaml --sandbox docker`; kunci API diketik Atha di shell VM dengan `read -rs`, diperiksa dengan `echo ${#ANTHROPIC_API_KEY}` (harus lebih dari 0) | Atha, eksplisit "go live" |
| 7 | Review run 1 (status, biaya, penyebab); baru putuskan run 2 (`pilot4b`) dan 3 (`pilot4c`), masing-masing dengan "go live" sendiri | reviewer + Atha |

Aturan henti: `FAILED_ACCEPTANCE`, `BLOCKED`, `FAILED_BUDGET`, `reservation_exhausted` dicatat sebagai hasil jujur; tidak ada kenaikan cap atau
profil di antara run. `--resume` hanya untuk run yang mati sebelum selesai (satu percobaan yang mati sebelum panggilan model dilanjutkan dengan
`--resume` pada run id yang sama). Laporan akhir: "x dari 3 `DONE`", biaya total, dan penyebab tiap kegagalan; tiga run adalah indikasi awal,
bukan tingkat keberhasilan. Patch tiap run yang `DONE` dibaca manusia karena menyentuh kode harga.

## 6. Usulan

**GO bersyarat**: (a) review artefak dan bukti rehearsal, (b) approval resmi eksplisit (langkah 3), (c) persetujuan atas bagian 2, (d) kunci disediakan
Atha, (e) "go live" eksplisit per run. Biaya yang diharapkan di bawah $0,15 per run; batas keras $0,75 dan paling banyak 3 attempt.
