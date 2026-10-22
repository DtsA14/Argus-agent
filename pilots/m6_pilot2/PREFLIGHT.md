# M6 pilot 2: preflight dan usulan go/no-go

Status 2026-10-21: **usulan untuk review. Belum ada approval resmi, belum ada live run, belum ada panggilan model
sungguhan.** Task: validasi `--impl` di `main.py` (`SPEC.md`). Pola dan aturan sama dengan `pilots/m6_pilot1/PREFLIGHT.md`.

## 1. Task dan artefak

`fix_impl_flag`: `--impl` yang tidak valid harus ditolak sebelum run dibuat (`config error:`, exit 1, tanpa traceback).
Hanya `main.py` dan `models/registry.py` writable. 13 tes: 7 wajib (merah di baseline karena assertion, tanpa error) dan
6 penjaga. Patch referensi manusia +22/−4 baris. 11/11 mutan tertangkap. Keempat keputusan GPT ada di `SPEC.md` bagian 6.

## 2. Latihan dengan model palsu (worktree buangan di VM, sandbox sungguhan, tanpa uang)

| Latihan | Hasil |
|---|---|
| **Jalur bahagia**: intake → draf → `--approve` (latihan) → run scripted → `build_review.py` | `DONE`, 1 attempt, 8 panggilan scripted, 1m47s. Paket **valid**, 12 cek ok, validasi ulang `target` (13 tes) dan `regression` (18 tes) lulus. `changes.patch` mengubah `main.py`, `models/registry.py`, dan menambah tes yang disetujui (`evidence/happy/`) |
| **Jalur negatif**: agen mencoba mengedit tes yang dilindungi dan `graph.py` (keduanya ditolak), lalu mengklaim sukses | `FAILED_ACCEPTANCE` (stagnan setelah 2 attempt), tidak ada paket review ("not DONE"), workspace tidak berubah selain `SUMMARY.json` (`evidence/negative/`) |

Bukti 18/18 dan 13/13 dari keluaran mentah sandbox (bukan hanya `must_pass` di `check_report.json`): `evidence/validation_raw.txt`.

Catatan: patch latihan sama dengan patch referensi kecuali satu komentar di akhir baris `IMPL_NODES` (skrip latihan tidak
menyalinnya); secara fungsi identik. Paket latihan mencatat `argus.dirty: true` karena worktree latihan punya file yang
di-stage; run live harus dari checkout bersih (`dirty: false`). Validasi pilot ini lebih lama dari pilot 1 (tes menjalankan
`main.py` sebagai subprocess), jadi satu run bisa memakan beberapa menit waktu dinding; `timeout_s` 240 per validasi cukup.

## 3. Konfigurasi live yang diusulkan (sama dengan pilot 1)

| Hal | Nilai |
|---|---|
| Model coder | `anthropic:claude-sonnet-5-5` ($2 masukan / $10 keluaran per 1M token) |
| Profil | `default` (30.000 token reservasi per attempt, output maksimum 4.096) |
| Cap biaya | **`max_usd` $0.50** (config dan kontrak), tidak dinaikkan; reservasi per attempt $0.30, jadi attempt ke-2 hanya masuk kalau attempt ke-1 menghabiskan ≤ $0.20 |
| `max_iterations` | 3 |
| Tools | config + `search_files`, `edit_file` dari kontrak |
| Perkiraan biaya | di bawah $0.15 (pilot 1: $0.0575 untuk 4 panggilan; task ini membaca dua berkas dan memakai tiga penyuntingan). Hanya perbandingan, bukan jaminan; batas kerasnya $0.50 |
| Aturan henti | stagnan 2 attempt, `max_iterations`, cap biaya, tool/validasi di luar scope ditolak; tanpa pengulangan otomatis |
| Syarat menjalankan | `ARGUS_LIVE=1` dan `ANTHROPIC_API_KEY` dibaca diam-diam di shell VM (tidak di chat, commit, atau argumen proses) |

## 4. Keadaan checkout bersih (sebelum approval, diperiksa)

Worktree `~/pilot2_live` pada `main` `66a32d0`, `git status` kosong. Intake `argus_p2` (`--commit cc8a2fd`, tanpa `verification`
dan `pilots`) cocok dengan yang dicek: commit `cc8a2fda4b29b9e862d8f1a2d0e3a750d2a35c95`, tree
`99feeb0c95e88faaee7d5ad10d21904611ec794d`, 379 file, snapshot `363964f8f392c72efca0a4911acfd64d288b4dcfe726c029ac5c21271b3ac2a8`;
`intake --check`: `problems: []`. Cek draf di checkout itu: `ok: true`, draft sha, tes yang ditambahkan, baseline, dan referensi
identik dengan `check_report.json`; sha256 kontrak
`295e95147779c5e8fa0526600afb5cc6f0195f2f54a9d4e5c0d36bf8eef9d23e`. Belum ada kontrak atau repo task yang dipublikasikan.

## 5. Urutan menuju live run (tidak ada langkah yang dijalankan sebelum persetujuan di kolom kanan)

| # | Langkah | Persetujuan |
|---|---|---|
| 1 | Review artefak final dan paket latihan | Atha + GPT |
| 2 | `approve_draft.py ... --approve` di `~/pilot2_live` (**tindakan manusia**); hash kontrak harus `295e9514...` | Atha, eksplisit |
| 3 | Commit record intake `argus_p2`, record task, kontrak, dan laporan cek ke `main` lewat PR bukti; snapshot tetap lokal; hapus empat file lokalnya lalu `git pull` sehingga checkout bersih | |
| 4 | Gerbang preflight: `git status` kosong, `intake --check` untuk keduanya, sha256 kontrak, image arm64, Docker sehat, skrip menolak tanpa `ARGUS_LIVE` | |
| 5 | Live run **satu kali** (`--run-id pilot2`), kunci dibaca diam-diam | Atha, eksplisit "go live" |
| 6 | `build_review.py`, catat status, biaya, waktu supervisi, apakah patch identik dengan referensi atau butuh intervensi, kegagalan jujur vs klaim tak didukung | |

Aturan setelah run sama dengan pilot 1: `FAILED_ACCEPTANCE`, `BLOCKED`, atau `FAILED_BUDGET` (termasuk karena thinking
menghabiskan jatah output) dicatat sebagai hasil dan **berhenti**; tidak ada run ulang, profil `large`, atau kenaikan cap tanpa
persetujuan baru. `--resume` hanya untuk run yang mati; satu percobaan yang mati sebelum panggilan model (0 `llm_call_started`)
dilanjutkan dengan `--resume` pada run id yang sama. Run dihitung sebagai pilot hanya bila `provenance.argus.dirty: false`.

## 6. Interpretasi hasil nanti

Pilot ini menguji validasi CLI lintas dua berkas dengan acceptance deterministik. Keberhasilan adalah bukti bagus untuk alur
M6 pada task kedua, tetapi **bukan** bukti kemampuan coding lintas berkas yang lebih kompleks; kegagalan jujur sama
informatifnya. Satu run adalah bukti kelayakan, bukan tingkat sukses.

## 7. Usulan

**GO bersyarat**, sama seperti pilot 1: (a) review artefak final, (b) approval resmi eksplisit, (c) persetujuan atas bagian 3,
(d) kunci disediakan Atha, (e) paket latihan ditinjau. Yang tidak dibuktikan latihan: perilaku model sungguhan (apakah ia memilih
tempat validasi yang benar, memakai `edit_file` dengan benar, dan tidak terpotong oleh thinking di batas 4.096 token).
