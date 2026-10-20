# M6 pilot 1: preflight dan usulan go/no-go

Status 2026-10-21: **usulan untuk review. Belum ada live run, belum ada panggilan model sungguhan, task belum
di-approve secara resmi.** Rencana dan kriteria go: `docs/reviews/M6_PLAN.md` bagian 4.

## 1. Task

`fix_run_stats`: `evals/score.py::run_stats()` melempar `JSONDecodeError` pada `events.jsonl` yang punya baris bukan
JSON (sisa run yang mati di tengah tulis lalu di-resume). Harus memakai aturan yang sama dengan
`harness.events.parse_lines`. Draf, tes baru, patch referensi, dan laporan cek ada di folder ini. Cek draf di sandbox
`argus`: `ok: true`, tiga tes wajib merah di baseline karena `JSONDecodeError`, patch referensi hijau.

## 2. Latihan dengan model palsu (bukti, di worktree buangan di VM, tanpa uang)

| Latihan | Hasil |
|---|---|
| **Jalur bahagia**: intake → draf → `--approve` (latihan) → run dengan model scripted di sandbox sungguhan → `scripts/build_review.py` | `DONE`, 1 attempt, 6 panggilan scripted. Paket **valid**, 12 cek ok. `changes.patch` = patch referensi + tes yang disetujui. Validasi segar `target` dan `regression` lulus (`evidence/happy/`) |
| **Jalur negatif**: agen mencoba mengedit tes yang dilindungi dan `harness/events.py` (keduanya ditolak), lalu mengklaim sukses | `FAILED_ACCEPTANCE` (stagnan setelah 2 attempt). Tidak ada paket review (`refused: ... not DONE`). Workspace tidak berubah selain `SUMMARY.json` (`evidence/negative/`) |

Catatan: latihan memakai worktree `~/pilot1` yang punya file pilot yang di-stage, jadi `provenance.json` mencatat
`argus.dirty: true`. Run live harus dari checkout bersih (`dirty: false`). Pemanggilan: `rehearse.py` di folder ini.

Kekasaran yang terlihat (tidak memblok): judul di `PR.md` diambil dari baris pertama issue dan dipotong 80 karakter di
tengah kata (issue ditulis satu baris panjang); reviewer mengedit judul, itu waktu supervisi, bukan perubahan kode.

## 3. Konfigurasi live yang diusulkan

| Hal | Nilai | Catatan |
|---|---|---|
| Model coder | `anthropic:claude-sonnet-5-5` ($2 masukan / $10 keluaran per 1M token) | default di `config.yaml` |
| Profil | `default` (30.000 token reservasi per attempt, output maksimum 4.096) | edit satu baris tidak butuh `large` |
| Cap biaya | **`max_usd` $0.50** (config dan kontrak), tidak dinaikkan | reservasi per attempt = $0.30, jadi attempt ke-2 hanya masuk kalau attempt ke-1 menghabiskan ≤ $0.20; praktis maksimal 2 attempt |
| `max_iterations` | 3 | |
| Tools | config + `search_files`, `edit_file` dari kontrak | `edit_file` penting: pilot `argus_self_1` gagal karena menulis ulang file utuh terpotong di 4.096 token |
| Perkiraan biaya | di bawah $0.15 | pembanding: `argus_self_1` $0.1627 (gagal, 2 attempt), `argus_self_2` $0.1853 (DONE di attempt 3). Task ini lebih kecil |
| Aturan henti | stagnan (kriteria gagal yang sama 2 attempt berturut-turut), `max_iterations`, cap biaya, tool/validasi di luar scope ditolak | tanpa pengulangan otomatis; run baru dengan uang hanya dengan persetujuan baru |
| Syarat menjalankan | `ARGUS_LIVE=1` dan `ANTHROPIC_API_KEY` | **kunci tidak ada di shell VM saat ini**; Atha menyediakannya saat run, tidak disimpan di repo |

## 4. Lingkungan

- VM aarch64 (OCI A1, 4 OCPU / 12 GB), Docker cgroup v2. Image `.sandbox_image` (python, arm64) dan
  `.sandbox_image_argus` (arm64, rootfs dari venv yang dipatok, tanpa jaringan) dipatok ke id isinya. Latihan memakai
  keduanya, jadi sandbox ARM64 bukan asumsi.
- Head: `main` pada `5ff64d0` sudah lulus `verify.sh` (1150 lulus, 0 skip sandbox). Branch pilot hanya menambah
  `pilots/m6_pilot1/` (tidak ada `.py` yang dikoleksi pytest; `conftest.py` mengabaikan `pilots/`), jadi verify penuh
  tidak diulang untuk itu.
- Intake dan hasil approval (`fixtures/intake/*.json`, `fixtures/contracts/fix_run_stats.json`, `fixtures/repos/argus_m6`,
  `fixtures/repos/fix_run_stats`) dibuat di VM dari draf di git dan tidak di-commit (snapshot ~373 file masing-masing).
  **Keputusan terbuka untuk GPT:** apakah record intake dan kontrak (kecil) di-commit sebagai bukti, dengan snapshot
  tetap lokal.

## 5. Prosedur pemulihan

- Run mati di tengah: `python scripts/run_code_task.py --contract fixtures/contracts/fix_run_stats.json --run-id <id>
  --resume --sandbox docker`. Hasil node yang sudah di-commit tidak dihitung ulang dan tidak dibeli ulang.
- Sandbox hilang di tengah: run `BLOCKED` (`sandbox_unavailable`), bukan lulus. Perbaiki sandbox, lalu `--resume`
  hanya bila statusnya masih `RUNNING`; status terminal tidak pernah berubah.
- `FAILED_ACCEPTANCE` / `FAILED_BUDGET`: tidak diulang otomatis. Catat sebagai hasil jujur dan putuskan bersama.
- Setelah `DONE`: `python scripts/build_review.py --run runs/<id> --repo <checkout>`; paket tidak valid tidak dipakai.

## 6. Kriteria go (M6_PLAN bagian 4) dan statusnya

| # | Kriteria | Status |
|---|---|---|
| 1 | W0 di-merge | dikonfirmasi Atha |
| 2 | Image dibangun ulang offline; tes target dua kali identik; baseline merah/hijau | W1 (bukti di `REVIEW_M6_W1.md`); baseline merah/hijau task ini: `check_report.json` |
| 3 | Draf kontrak dan tes disetujui manusia | **menunggu review akhir draf (Atha/GPT)** |
| 4 | Dry run model palsu menghasilkan paket lengkap, patch lolos verifikasi W3, paket ditinjau | latihan selesai (bagian 2); **paket menunggu ditinjau** |
| 5 | `verify.sh` lulus di head; cap, profil, aturan henti dikunci | verify lulus di `5ff64d0`; cap/profil/aturan: **usulan bagian 3, menunggu persetujuan** |

## 7. Usulan

**GO bersyarat**: semua mekanisme sudah terbukti dengan model palsu. Tinggal (a) approval akhir draf, (b) persetujuan
eksplisit atas bagian 3 (cap $0.50, profil `default`, aturan henti), (c) Atha menyediakan `ANTHROPIC_API_KEY` dan
`ARGUS_LIVE=1`, dan (d) review paket latihan. Hasil pilot dicatat dengan salah satu status `agent-completed`,
`human-assisted`, atau `failed`, plus biaya dan menit supervisi.

Yang tidak dibuktikan oleh latihan: perilaku model sungguhan (apakah ia menemukan `parse_lines`, memakai `edit_file`
dengan benar, dan tidak terpotong oleh thinking di batas 4.096 token). Itu justru yang diukur live pilot.

## 8. Urutan menuju live run (hasil review GPT 2026-10-21)

Tidak ada langkah di bawah yang dijalankan sebelum persetujuan yang disebut di kolom kanan.

| # | Langkah | Persetujuan |
|---|---|---|
| 1 | Review akhir draf dan paket latihan (`evidence/happy/`) | Atha + GPT |
| 2 | Merge `m6-pilot1-draft` ke `main` (hanya `pilots/m6_pilot1/`, tanpa kode yang dikoleksi pytest) | setelah 1 |
| 3 | Di VM, worktree **baru dan bersih** dari `main`; salin `.sandbox_image*`; `git status` harus kosong | |
| 4 | Intake dengan perintah yang sama (`--commit 5ff64d0`, tanpa `verification` dan `pilots`). Hash harus sama dengan yang dicek: tree `816b1bf3...`, snapshot `3c975a90...` | |
| 5 | `approve_draft.py ... --approve` (**tindakan manusia**). Hash kontrak harus `c75cecee...` | Atha, eksplisit |
| 6 | Commit **record intake, record task, kontrak, dan laporan cek** (file kecil) ke `main` lewat PR bukti; snapshot 373 file tetap lokal (`.git/info/exclude`). Di VM hapus keempat file lokalnya lalu `git pull`, supaya checkout bersih dan commit Argus run memuat jejak audit | |
| 7 | Gerbang preflight: `git status --porcelain --untracked-files=no` kosong; `intake_repo.py --check` untuk `argus_m6` dan `fix_run_stats`; sha256 kontrak sama; kedua image arm64 ada; `docker info` sehat | |
| 8 | Live run **satu kali**: kunci dibaca diam-diam di shell VM (`read -rs ANTHROPIC_API_KEY; export ANTHROPIC_API_KEY`, tidak masuk riwayat, tidak ke chat, tidak ke commit), lalu `ARGUS_LIVE=1 python scripts/run_code_task.py --contract fixtures/contracts/fix_run_stats.json --run-id pilot1 --sandbox docker` | Atha, eksplisit "go live" |
| 9 | `build_review.py`, catat status, biaya, menit supervisi | |

Batas yang harus tetap tertulis: record yang di-commit **bukan** bukti bahwa snapshot lokal bisa direkonstruksi persis.
Hash hanya mendeteksi ketidakcocokan; untuk mereproduksi run yang sama snapshot lokal (atau intake ulang dari commit
dasar dengan exclude yang sama, yang menghasilkan hash yang sama) tetap diperlukan.

**Syarat provenance:** run dihitung sebagai pilot hanya bila `result.json` memuat `provenance.argus.dirty: false`
(file bertrack tidak berubah; checkout bersih dari langkah 3 dan 6). Paket latihan (`dirty: true`) bukan bukti run
dari checkout bersih.

**Aturan setelah run (tidak ada pengecualian):**
- `FAILED_ACCEPTANCE`, `BLOCKED`, atau `FAILED_BUDGET`, termasuk karena thinking menghabiskan jatah output sebelum tool
  dipanggil, dicatat sebagai hasil pilot dan **berhenti**. Tidak ada run ulang, tidak ada profil `large`, tidak ada
  kenaikan cap tanpa persetujuan baru dan alasan tertulis.
- `--resume` hanya untuk run yang mati (crash); ia tidak membeli ulang hasil yang sudah di-commit dan tetap di bawah cap
  yang sama.
- Cap $0.50 adalah batas keras, bukan prediksi biaya. Perkiraan di bawah $0.15 hanya perbandingan dengan pilot lama.
- Patch final tetap ditinjau manusia sebelum merge; paket valid bukan pengganti review.

