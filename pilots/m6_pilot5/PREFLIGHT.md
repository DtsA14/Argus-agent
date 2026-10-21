# M6 pilot 5: preflight, rehearsal, dan usulan go/no-go

Status 2026-10-21: **usulan untuk review. Belum ada approval resmi, belum ada live run, belum ada panggilan model sungguhan.**
Task: `fix_window_strict` (`models/pricing.py::is_peak` menolak jendela dan waktu yang tidak bisa dibaca dengan aman; `SPEC.md`, keputusan D1–D4 di bagian 6). Basis `716d1dd`.

## 1. Keputusan reviewer yang dijalankan (D5)

Profil `large` dengan cap **$0,75 khusus Pilot 5**; cap global `config.yaml` tetap $0,50 (`config_pilot5.yaml` berbeda satu nilai). Batas yang dikunci reviewer:
- `reservation_exhausted` tetap kegagalan eksperimen: tidak menaikkan budget dan tidak mengulang otomatis untuk mengejar `DONE`.
- Cap $0,75 hanya untuk pilot ini, bukan default baru.
- Skenario "baca semua pemakai `is_peak`" tetap risiko terbuka; scope tidak diperluas untuk mengejarnya.
- Tidak ada izin live; keputusan live terpisah setelah rehearsal dan semua pemeriksaan.

## 2. Konfigurasi efektif (dihitung oleh fungsi yang sama dengan yang dipakai run, bukan hanya nilai di YAML)

`rehearse.py effective` (profil diterapkan oleh `codetask.run.apply_profile`, cap = yang lebih ketat dari config dan kontrak lewat `codetask.run.settings`):

| | config pilot (`config_pilot5.yaml`) | `config.yaml` (kontrol) |
|---|---|---|
| profil di kontrak / yang diterapkan | `large` / `large` | `large` / `large` |
| reservasi satu attempt | **45.000 token = $0,45**, keluaran maksimum coder 8.192 | sama |
| `budget.max_usd` di config | **0,75** | 0,50 |
| `limits.max_usd` di kontrak | 0,75 | 0,75 |
| **cap run efektif** | **$0,75** | **$0,50** |
| `max_iterations` | 3 | 3 |

Jumlah attempt yang mungkin (reservasi $0,45 tiap attempt; attempt diterima bila terpakai + $0,45 ≤ cap; paling banyak 3):

| Satu attempt menghabiskan | cap pilot $0,75 | `config.yaml` $0,50 |
|---|---|---|
| $0,06 (jalur bersih) | 3 | 1 |
| $0,11 (tipikal) | 3 | 1 |
| $0,20 | 2 | 1 |
| $0,30 | 2 | 1 |
| $0,45 (seluruh reservasi) | 1 | 1 |

Jadi di bawah cap global reservasi `large` hanya memberi satu attempt; cap pilot yang memberi lebih dari satu. Ini dilaporkan, bukan disembunyikan.

Bukti dari run sungguhan (bukan hanya hitungan): pada rehearsal `admission` di config pilot, attempt 2 **diterima** dan dijalankan ($0,0716 lalu $0,0779); dengan `config.yaml`, run berhenti `max_usd`
setelah **1 attempt** ($0,0716), attempt kedua ditolak sebelum dikirim. Event `budget_profile` di tiap run mencatat `large`, 45.000, 8.192.

## 3. Rehearsal dengan model terskrip (worktree buangan di VM, sandbox sungguhan, tanpa uang)

Persetujuan di worktree buangan hanya latihan (kontrak latihan sha256 `a05548186f86…`); tidak ada yang dipublikasikan.

| Latihan | Hasil |
|---|---|
| **happy** (baca `pricing.py` dan tes strict, sunting seperti patch referensi, validasi `target` dan `regression`, Finish jujur) | `DONE`, 1 attempt, 6 panggilan; profil `large`. Paket review (`build_review.py`): **valid, 12 dari 12 cek**; perubahan hanya `models/pricing.py` dan tes yang disetujui; `target` 14 dari 14 tes lulus, juga pada tree bersih dari commit dasar + patch ("Fresh") |
| **negative** (menyunting tes strict dan `config.yaml`: ditolak; klaim palsu) | `FAILED_ACCEPTANCE` (stagnan, 2 attempt), tidak ada paket review; workspace akhir sama dengan snapshot kecuali `SUMMARY.json` (`evidence/audit_output.txt`) |
| **admission** (model **berharga**, penghitung terkalibrasi, membaca jalur "typical", tidak mengubah apa pun) | lihat bagian 2; 2 attempt, $0,1495 total |
| **admission** dengan `config.yaml` | berhenti `max_usd` setelah 1 attempt |

Batas rehearsal: model terskrip membuktikan alur harness, bukan kemampuan model sungguhan. Angka biaya rehearsal adalah mekanisme admisi, bukan jaminan biaya; pada 3a biaya nyata dua attempt $0,20.

## 4. Gerbang preflight yang sudah diperiksa sekarang

| Gerbang | Hasil |
|---|---|
| Skrip menolak model nyata tanpa `ARGUS_LIVE=1` | ya: `refused: ... set ARGUS_LIVE=1`, exit 2, tidak ada run dibuat |
| Docker | aarch64, 29.1.3 |
| Kunci API di sesi SSH baru | panjang 0 (tidak tersimpan; diketik Atha lewat `~/go_live.sh`) |
| Intake `argus_p5` | `problems: []` (commit `716d1dd22787`, 395 file, snapshot `f11324aa0368…`; hash sama di host Windows dan VM) |
| Draft check dengan `--max-usd 0.75`, profil `large` | `ok: true`, baseline merah tepat pada 10 tes wajib, patch referensi lulus, hanya `models/pricing.py` berubah, regresi 30 tes lulus |
| `verify.sh` atas "base + patch referensi + tes" | **1210 lulus, 0 skip sandbox** (1196 + 14); 29/29 mutan |

Yang baru bisa diperiksa setelah merge dan approval resmi: `verify.sh` pada `main` yang baru, checkout live bersih (`dirty: false`), `intake --check` untuk record task, sha256 kontrak `a05548186f86…`.

## 5. Urutan menuju live run (tidak ada langkah yang dijalankan sebelum persetujuan di kolom kanan)

| # | Langkah | Persetujuan |
|---|---|---|
| 1 | Review rehearsal dan dokumen ini | reviewer + Atha |
| 2 | Merge PR #112 (artefak), `verify.sh` pada `main` | reviewer |
| 3 | Cek ulang hash kontrak dan intake (draft check identik dengan `check_report.json`) | |
| 4 | `approve_draft.py ... --max-usd 0.75 --max-iterations 3 --approve` pada checkout bersih; sha256 kontrak `a05548186f86…` | Atha, eksplisit |
| 5 | PR record task; checkout live bersih | |
| 6 | Keputusan live **terpisah**; satu run (`pilot5a`) lewat `pilots/m6_pilot5/go_live.sh` (di repo, direview di PR; lihat bagian 7), kunci diketik Atha | Atha, "go live" eksplisit |

Aturan henti: `FAILED_ACCEPTANCE`, `BLOCKED`, `FAILED_BUDGET`, `reservation_exhausted` dicatat sebagai hasil jujur; tanpa kenaikan cap, profil, atau pengulangan otomatis. `--resume` hanya untuk run yang mati
sebelum selesai. Patch yang `DONE` dibaca manusia karena menyentuh kode harga (termasuk uji pembeda terhadap referensi).

## 7. Skrip pembantu `pilots/m6_pilot5/go_live.sh` (jalur operasional, diikat ke Pilot 5)

Sebelumnya `~/go_live.sh` di VM terikat ke kontrak Pilot 4 dan berada di luar repo. Sekarang skrip ada di repo, nilai yang diharapkan tertulis di dalamnya (bukan dibaca dari lingkungan), dan `~/go_live.sh` lama
dinonaktifkan (`~/go_live_pilot4_retired.sh`, tanpa izin eksekusi). Perintah: `bash pilots/m6_pilot5/go_live.sh --check-only` (semua gerbang, tidak meminta kunci, tidak ada run) dan
`bash pilots/m6_pilot5/go_live.sh pilot5a` (gerbang, lalu meminta kunci dan menjalankan SATU run).

Gerbang (semua harus lolos, kalau tidak, tidak ada yang dimulai): checkout live bersih; kontrak `fix_window_strict` dengan sha256 `a05548186f86…`, profil `large`, batas $0,75 dan 3 iterasi, writable hanya `models/pricing.py`;
`config_pilot5.yaml` sha256 `6bb6703d…` dan berbeda dari `config.yaml` **hanya** pada `budget.max_usd` 0,5 → 0,75; batas efektif (profil `large`, 45.000 token, $0,45 per attempt, cap $0,75, 3 attempt);
tanpa `ARGUS_LIVE=1` runner menolak dan tidak membuat direktori run; id run berbentuk `pilot5<huruf>` dan belum ada; kunci tidak kosong.

Diuji di worktree buangan (`evidence/go_live_tests.txt`): lolos pada keadaan benar (dua kali) dan **menolak** hash kontrak yang salah, profil yang salah, cap config `$1,00`, `config.yaml` yang diubah di tempat lain
(config pilot utuh), tree kotor, id run yang sudah ada, id run salah bentuk (termasuk percobaan injeksi), kunci kosong (tanpa run), dan tanpa argumen. Draft check ulang di commit terbaru: `ok: true`,
identik dengan `check_report.json`.
