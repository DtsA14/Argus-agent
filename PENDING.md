# Pending

Daftar kerja Argus yang **masih terbuka**. Status milestone dan ADR beserta buktinya ada di [`docs/Reconciliation.md`](docs/Reconciliation.md)
(satu-satunya tempat status); riwayat semua butir yang sudah selesai (bukti, angka, PR) ada di
[`docs/reviews/PENDING_ARCHIVE_2026-10-22.md`](docs/reviews/PENDING_ARCHIVE_2026-10-22.md) dan `docs/reviews/`.

Terakhir diperbarui: 2026-10-22 (pilot 3a dan 3b `agent-completed`; dokumen dirapikan).

Legenda: `[ ]` belum dimulai · `[~]` sebagian · `[x]` selesai (dipindah ke arsip saat daftar ini dirapikan berikutnya).

## Ringkasan

| | Status | Rinci |
|---|---|---|
| M1–M3, general-task agent | `[x]` | Reconciliation bagian 1 |
| M6 repo → PR | `[x]` MVP | 10 run live pilot, 6 task `agent-completed`, $1,29 total (Reconciliation bagian 4) |
| M5 observability | `[~]` | ledger, inspektor, `pilot_report.py`; belum: tracing, supervisi, benchmark tidak jenuh |
| M4, M7, M8, M9, capability pack | `[ ]` | ditunda sampai ada bukti kebutuhan (keputusan 2026-10-21) |
| ADR-002, 004, 005, 006, 007 | `[~]` | ada untuk code task (Reconciliation bagian 2) |
| ADR-001, 003 | `[ ]` | target M7 dan M8 |

## Terbuka sekarang

Urutan menurut nilai (Reconciliation bagian 6); keputusan urutan berikutnya di Reconciliation bagian 7.

- [ ] **Supervisi manusia per pilot, versi ringan** (diputuskan Atha 2026-10-22; M5/M6), mulai pilot berikutnya:
  1. **jumlah titik keputusan manusia** (jawaban spesifikasi, approve, go live, merge, intervensi tak terduga), dihitung Claude dari PR dan
     alur pilot;
  2. **waktu terminal** dicatat otomatis oleh `go_live.sh` (mulai, kunci diketik, run selesai), ke log di luar repo;
  3. **menit kerja Atha opsional**: ditanya sekali di akhir pilot, satu angka kasar; "skip" dicatat `unknown`.
  Tujuannya: apakah Argus menghemat waktu manusia, bukan hanya biaya model. Pilot 3a–3b tetap `unknown`
- [ ] **Repo selain Argus** (M6): semua pilot di repo Argus. Athena butuh image sandbox per proyek; JS (bulking-app) belum bisa divalidasi
- [ ] **Pertanyaan B dari D5:** apakah ≥ 2 putaran perbaikan muat dalam satu attempt. `pilot3a5` dan `pilot3b1` tidak membutuhkannya; perlu
  task yang memang menuntut beberapa putaran
- [ ] **Eval set yang tidak jenuh** (M5): v1 16/16 hanya untuk regresi. Perluas dari kegagalan nyata (mis. 3a v1), lalu bekukan hash; eval set
  10–20 task dengan biaya per task yang lulus
- [ ] `scripts/audit_run.py` belum menyisipkan pesan `NUDGE` (balasan tanpa tool call) saat membangun ulang langkah; belum pernah terjadi di
  run live
- [ ] `intake_repo.py --check <task> --repo` memberi mismatch palsu untuk record task (membandingkan dengan tree commit tanpa tes yang
  disetujui); tanpa `--repo` benar
- [ ] Judul `PR.md` (paket review) dipotong 80 karakter di tengah kata; kosmetik
- [~] **W2b** drafter model (`docs/reviews/REVIEW_M6_W2B.md`): kode dan tes selesai, patch referensi opsional (K1). Berikutnya
  pilot **W2b-1** (ulang issue 3b di `argus_p6`, cek bocoran di preflight), lalu **W2b-2** end-to-end di task baru (spec bagian 7)
  - **W2b-1 `w2b1d1` gagal** (2026-10-22, $0,16): `SubmitDraft` terpotong di output 8.192, 6.108 di antaranya thinking; isi tes
    belum tertulis (`pilots/m6_w2b/w2b1/live/w2b1d1/RESULT.md`). Keputusan berikutnya menunggu Atha (output lebih besar, thinking
    dibatasi, atau tes lewat tool terpisah)
  - **W2b-1 `w2b1d2` gagal** ($0,22; output 16.384): submit 1 nyaris lolos (23 node merah karena assertion, satu tes gagal
    tanpa diwajibkan), lalu kirim ulang ditolak `input_limit` (45.035 > 40.000). Celah: penolakan tidak menyebut tes yang gagal di luar
    `must_pass` (`pilots/m6_w2b/w2b1/live/w2b1d2/RESULT.md`)
  - **W2b-1 `w2b1d3` berhasil** ($0,29; ReviseDraft, attempt $0,70, input 64k): `DRAFTED` dalam 2 submit. Tes drafter lulus terhadap
    `scripts/pilot_report.py` di `main` (20/20) dan menangkap 19/20 mutan referensi 3b (manusia 20/20; tanpa run BLOCKED). Draf tanpa
    `budget_profile` dan regresi longgar. W2b-1 total $0,67 untuk 3 run. Berikutnya: drafter memilih profil, lalu W2b-2
  - **W2b-2 selesai: `pr_title2` agent-completed tanpa patch referensi** (2026-10-23, PR #160): issue → drafter (3 run, $0,47) →
    approve `--no-reference` → agen (DONE, $0,08) → patch ke `main` tanpa perubahan → `verify.sh` lulus. Total $0,54, ±17 keputusan,
    5 menit Atha (`pilots/m6_w2b/w2b2/RESULT.md`). Perbaikan yang dipicu: profil wajib (#155), `edit_file` + cek tulis ulang (#157),
    batas sandbox, petunjuk, 5 submit (#158)
- [x] **W2a-ext: `changed_tests`** (`docs/reviews/SPEC_W2A_EXT_CHANGED_TESTS.md`, `acceptance/changed.py`): draf boleh mengubah tes
    lama. Tidak ada tes lama yang hilang (koleksi di sandbox) atau fungsi tes yang berubah (AST) tanpa `removed`/`modified` + alasan;
    tidak ada skip/xfail baru (kontrak `no_skip`); hanya `test_*.py`. 25 tes baru gagal di kode lama, mutan 26/26 (2026-10-23)
- [x] **Pilot W2b-3 `success_rate_all`** (2026-10-23): berhasil pada run 3 (job $0,0216, agen 1 attempt). Run 1 dan 2
    menemukan dua celah harness, ditutup oleh #179 (merah karena assertion) dan #180 (cek setup di cek draf).
    `pilots/m6_w2b/w2b3/RESULT.md`
- [ ] Drafter beberapa kali mengirim entri `changed_tests` duplikat atau kosong, dan file tes baru di `changed_tests`
    (W2b-3); penolakannya benar, tapi satu submit terbuang. Mungkin perlu contoh di prompt
- [x] **`pilot_report.py` `success_rate`**: ditambah `success_rate_all` (W2b-3)
- [ ] Drafter masih mencoba regresi yang butuh `git` (w2b2d3) walau prompt menyebut batas sandbox; satu submit terbuang
- [ ] **Router v0** (`docs/reviews/SPEC_ROUTER_V0.md`, K2–K7 disetujui 2026-10-23): `argus code` sebagai satu job (cap per job $1,00,
    kunci per job, cap tahap dicatat saat mulai, approve terikat ke sha draf). Belum dikoding
- [ ] `argus research` **ditunda** (K1 router v0): dibuat bersama Alur A yang menerima prompt bebas; saat itu bentuk job dan ledger
    diseragamkan
- [ ] **D4** batas ListFiles + daftar berkas di issue: **ditunda** (2026-10-22); dibuka bila ada task yang kehabisan anggaran dengan caching
  menyala
- Pengamatan, belum tindakan: di `pilot3b1` agen memanggil `RunValidation` di balasan yang sama dengan tulisannya, sebelum validasi otomatis
  jalan (validasi dijalankan dua kali, ±9 detik). Prompt sistem sengaja tidak menyebut validasi otomatis (D3 K4). Satu pengamatan

## Selesai, belum masuk arsip

- [x] **Pilot `argus_self_3`** (2026-10-17, PR #72; `pilots/argus_self_contract/README.md`, validasi `must_pass`, $0.1797): gagal jujur,
  workspace tidak berubah. Thinking memakai **100%** output di langkah ketiga (4.096 dan 2.954), tanpa tool call; batas output terkunci
  oleh sisa reservasi attempt (±4,5 ribu setelah input 15 ribu). Keputusan yang dibukanya ("profil task besar, batasi thinking, atau
  berhenti") terjawab oleh pekerjaan sesudahnya: profil `large` (M6 W5, keluaran 8.192) dan `large_usd` (D1)

## Pekerjaan operasional (Atha, di luar repo)

- [ ] Cabut kunci API yang dipakai untuk pilot 3a v2, D5, dan 3b di dashboard provider
- [ ] Bersihkan sisa kunci di riwayat shell dan berkas env di VM; hapus SSH key tambahan yang tidak dipakai lagi
- [ ] Deploy harness sebagai service (systemd): operasional, **bukan** M9

## Parking lot (roadmap `docs/FUTURE_ARCHITECTURE.md`)

Ditunda sampai ada bukti kebutuhan; status dan gap di Reconciliation bagian 1–2.

- [ ] M4 penjadwalan multi-agent dengan dependensi
- [ ] M5 sisanya: tracing/dashboard, benchmark single vs multi-agent, model kandidat worker (Haiku 5.5 vs DeepSeek) per biaya task yang lulus
- [ ] M7 registry kapabilitas dan policy (ADR-001), layanan approval di kode (ADR-007), adapter MCP
- [ ] M8 penemuan tool dan memori prosedural (ADR-003)
- [ ] M9 deployment terkendali
- [ ] Idempotency key sisi provider (ADR-004)
- [ ] Artifact store dengan versioning (ADR-005)
- [ ] Capability pack gambar, video/audio, game, dengan gate non-kode (ADR-006)

## Batasan yang diterima

- `budget.max_seconds` hanya soft limit di graf riset; **code task tidak punya batas waktu dinding** (`DESIGN_AUTO_VALIDATION.md`)
- Tarif konteks panjang Haiku 5.5 (> 100.000 token) tidak dimodelkan; role Haiku yang panggilannya bisa melewatinya ditolak (`ConfigError`)
- Prompt caching hanya Anthropic, TTL 5 menit, mati bawaan; bukan untuk Haiku 5.5 (D5)
- Empat skrip eksperimen lama (`analyze_series.py`, `sim_admission.py`, `dry_feedback.py`, `measure_context.py`) masih membaca log dengan
  `json.loads` per baris; diarsipkan apa adanya (pilot 3 spesifikasi bagian 2)
