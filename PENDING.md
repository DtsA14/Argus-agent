# Pending

Daftar kerja Argus yang **masih terbuka**. Status milestone dan ADR beserta buktinya ada di [`docs/Reconciliation.md`](docs/Reconciliation.md)
(satu-satunya tempat status). Riwayat butir yang sudah selesai (bukti, angka, PR): [`docs/reviews/PENDING_ARCHIVE_2026-10-30.md`](docs/reviews/PENDING_ARCHIVE_2026-10-30.md)
(sampai 2026-10-30), [`docs/reviews/PENDING_ARCHIVE_2026-10-22.md`](docs/reviews/PENDING_ARCHIVE_2026-10-22.md) (sebelumnya) dan `docs/reviews/`.

Terakhir diperbarui: 2026-10-30 malam (viewer PWA live di HP Atha: #256, #257, #261, #263–#266; staging namespace #258;
notifikasi monitor #259/#260). Dirapikan: semua butir `[x]` pindah ke arsip 2026-10-30.

Legenda: `[ ]` belum dimulai · `[~]` sebagian · `[x]` selesai (dipindah ke arsip saat daftar ini dirapikan berikutnya).

## Ringkasan

| | Status | Rinci |
|---|---|---|
| M1–M3, general-task agent | `[x]` | Reconciliation bagian 1 |
| M6 repo → PR | `[x]` MVP | repo Argus, sympy (SWE), `argus-ledger` (Python), `argus-viewer` (JS, vitest) |
| M9 deployment terkendali | `[~]` staging | dua aplikasi di staging, monitor + notifikasi; production belum (keputusan 2026-10-30: tetap staging) |
| M5 observability | `[~]` | ledger, inspektor, `pilot_report.py`, keputusan manusia di `job.json`; belum: tracing, benchmark tidak jenuh |
| M4, M7, M8, capability pack | `[ ]` | ditunda sampai ada bukti kebutuhan |

## Cara kerja (berlaku)

- **Dua jalur** (2026-10-28): ketat (uang/ledger, crash-resume, sandbox, key, grader, staging: spek, mutants, review,
  `verify.sh`, "merge" Atha; urutan: tes → review → mutants → verify) dan cepat (kemampuan agen dan aplikasi latihan: Claude
  merge sendiri). Satu PR jalur ketat pada satu waktu.
- **Aplikasi latihan** (`argus-ledger`, `argus-viewer`): issue ditulis Claude, "go live" per job dari Atha, Claude review draf
  dan patch lalu `argus applied`. `argus-viewer`: `PROTECTED` + `~/argus-viewer-issues/check_protected.py` saat approve
  (`draft`) dan sebelum apply (`patch`).
- **Staging:** satu "go live" per `PLAN.md` yang ter-commit; **satu langkah = satu perintah**; berhenti di langkah pertama yang
  meleset; lanjut butuh "go live" baru. Data viewer = snapshot terakhir (monitor tiap 15 menit).

## Terbuka sekarang

### Keputusan Atha yang ditunggu

- [ ] **UI kontrol interaktif** (Atha 2026-10-30, scope dibahas di chat): fase 0 spek `SPEC_CONTROL_UI` (service kontrol
  terpisah `127.0.0.1:8711`, proxy viewer tetap GET-only, CSRF/Origin, audit di `job.json`, batas biaya server-side), fase 1
  halaman review draf read-only (jalur cepat), fase 2 aksi tanpa biaya (`reject`/`abandon`), fase 3 aksi berbayar, fase 4
  tombol staging. Pertanyaan terbuka: siapa yang approve, batas $ via UI, "go live" lewat tombol, port 8711 + `permitopen`
  kedua di kunci HP, waktunya terhadap up2
- [ ] **Shadow mode** (usul Claude 2026-10-30): satu kelas task (issue viewer read-only) jalan otomatis draf → patch dengan
  cek otomatis; Claude menilai sesudahnya "akan diblok?"; 0 blok dalam ±10 job → kelas itu jalan tanpa Claude di dalam batas
  biaya harness. Prasyarat: `check_protected` pindah ke harness (lihat bawah)

### Terjadwal

- [ ] **up2** mulai 2026-11-07: starlette 1.10.0, fastapi 0.162.0 (aturan 2 minggu), environment `*_up2`, PLAN.md + satu
  "go live" (`docs/reviews/SPEC_DEP_UPGRADE_V0.md`)

### Gap dari pekerjaan 2026-10-30

- [ ] **Berkas yang dilindungi belum dipaksa harness.** `argus-viewer` bergantung pada skrip di luar repo yang dijalankan Claude;
  aturan drafter vitest hanya melarang config/`package.json`/`.npmrc` writable. Kandidat jalur ketat: daftar `PROTECTED` per
  repo dibaca harness dari commit base, dicek di cek draf dan di paket review. Prasyarat shadow mode dan UI approve
- [ ] **Pin image per checkout disalin manual.** `~/pilot3a_live` butuh `.sandbox_image_pwa_node22*` dari `~/Argus-agent`
  (job 001 ditolak sekali); `verify.sh` membangun ulang image dan menulis pin baru hanya di checkout tempat ia jalan
  (`.sandbox_image_argus` sudah berbeda antar checkout). Kandidat: satu lokasi pin di luar checkout, atau cek di preflight
- [ ] **Smoke kandidat viewer tidak menguji lingkungan unit systemd** (pilot viewer #1: `PrivateTmp` lolos deploy, gagal di
  unit). Tes opsi unit ada (#263); smoke live lewat 8710 hanya di `viewer-smoke`/monitor, bukan gerbang deploy
- [ ] **Kunci HP di `authorized_keys` VM** (2026-10-30): `restrict,port-forwarding,permitopen="127.0.0.1:8710"`, perintah
  paksa `sleep`; dites. Bukan di repo; dicatat di sini agar dicabut bila HP hilang (`~/.ssh/authorized_keys`, baris
  `iphone-viewer`)
- [ ] `argus code` yang ditolak karena key (tanpa `--key-file`) tetap membuat job `NEW` (`j20261030_164146_9b3d`, di-abandon);
  layar penolakan tidak menyebutnya. Kecil, jalur cepat

### Kemampuan agen (jalur cepat, kandidat)

- [ ] **Gate "tes menelan traceback" salah tolak** (argus-ledger 008): pesan tes yang mengharapkan exception, dan `TypeError` di
  titik panggilan, dianggap menelan. Usul jalur ketat: catat exception yang benar-benar di-raise di kode repo selama red check
  (`sys.monitoring` RAISE, Python ≥ 3.12)
- [ ] `estimate_miss` per run di `status` (H3 spek margin); `swe_grade.py` mencatat nama tes draf yang gagal di atas patch
  maintainer; tes lama yang diubah drafter otomatis wajib (`22456` d1)
- [ ] Drafter: entri `changed_tests` duplikat/kosong atau berkas baru di `changed_tests` (W2b-3); regresi yang butuh `git`
  (w2b2d3); masing-masing satu submit terbuang
- [ ] Kandidat sisa batch 5 / `21379`: drafter mencari titik nilai salah pertama kali muncul (`20428`); gerbang writable
  lebar vs regresi sempit; drafter membaca sampai dipaksa berhenti
- [ ] Vitest v0: tes lama tidak bisa diubah (`changed_tests` hanya Python), tanpa `-t`; dibuka bila task viewer membutuhkannya
- [ ] Tahap 3b: interaksi JS di browser + Playwright (image dengan Chromium; ±2–3 PR jalur ketat), bila ada kebutuhan

### Pengukuran (M5)

- [ ] **Supervisi per pilot:** jumlah keputusan manusia dihitung Claude di setiap RESULT; **menit kerja Atha** ditanya sekali di
  akhir pilot ("skip" = `unknown`). (Waktu terminal `go_live.sh` tidak berlaku lagi: persetujuan pindah ke chat, `--yes`)
- [ ] **Eval set yang tidak jenuh:** Eval Set v1 16/16 hanya regresi; instance SWE terkontaminasi. Perluas dari kegagalan nyata,
  bekukan hash
- [ ] Efek petunjuk berhenti (`context_limit` #188, `output_truncated` #200, `max_steps` tanpa menulis #204) belum terpisah dari
  variasi model; langkah submit (#211) dan pertanyaan scope (#208) belum pernah terpakai live; peringatan konteks 70% belum muncul
- [ ] **Pertanyaan B D5:** ≥ 2 putaran perbaikan dalam satu attempt; perlu task yang menuntutnya
- [ ] Approve tanpa oracle lebih lama (batch 3: ±5–7 menit per draf, batch 1 median 45 detik): ringkasan yang membantu menilai
  isi tes; kandidatnya halaman review draf (UI kontrol fase 1)

### Kecil / rendah

- [ ] `scripts/audit_run.py` belum menyisipkan pesan `NUDGE` saat membangun ulang langkah (belum terjadi live)
- [ ] `check_against_repo` record task tidak membandingkan bit executable tes (baris dari patch agen #189); hapus atau tes
- [ ] Judul `PR.md` dipotong 80 karakter di tengah kata
- [ ] Layar batas tahap drafter dan `retry`/resume tidak menyebut environment dan image (preflight chat menghitungnya)
- [ ] Router: cek bentuk kunci DeepSeek (hanya Anthropic yang dicek prefiksnya)
- [ ] Router: `argus apply` (K6 v0); sekarang perintah apply dicetak `status` dan dijalankan Claude

### Ditunda sampai ada bukti kebutuhan

- [ ] Mesin pencari (tahap 2 akses web): hanya bila ReadDocs terbukti kurang; ReadDocs belum pernah dipakai agen (K7, riset 013)
- [ ] Deep research (gate kutipan klaim ↔ sumber); `argus research` bersama Alur A
- [ ] Alur A: bug yang jawabannya tidak ada di ingatan model; task agen dua lengan untuk upgrade yang butuh API baru
- [ ] Ringkasan validasi untuk agen (subagen penguji ringan), bila `context_limit` karena output validasi
- [ ] D4: batas ListFiles + daftar berkas di issue
- [ ] Email Agensi.io (marketplace skill): nanti, eksperimen dibatasi waktu

## Pekerjaan operasional (Atha, di luar repo)

- [ ] Cabut kunci API yang dipakai untuk pilot 3a v2, D5, dan 3b di dashboard provider
- [ ] Bersihkan sisa kunci di riwayat shell dan berkas env di VM; hapus SSH key tambahan yang tidak dipakai lagi (kunci HP
  `iphone-viewer` tetap dipakai)
- [ ] Cek key manual router pilot #3 (`grep -rlF -f ...`, kriteria 4); dari PC
- [ ] Deploy harness sebagai service (systemd): operasional, bukan M9 (staging monitor dan proxy viewer sudah unit `--user`)

## Parking lot (roadmap `docs/FUTURE_ARCHITECTURE.md`)

- [ ] M4 penjadwalan multi-agent dengan dependensi
- [ ] M5 sisanya: tracing/dashboard, benchmark single vs multi-agent, model worker per biaya task yang lulus
- [ ] M7 registry kapabilitas dan policy (ADR-001), layanan approval di kode (ADR-007; dibuka bersama UI kontrol fase 2–3 atau
  `argus apply`), adapter MCP
- [ ] M8 penemuan tool dan memori prosedural (ADR-003)
- [ ] M9 production sungguhan (DNS/TLS, pengguna, kredensial): butuh spek dan persetujuan terpisah; pemicu: pengguna kedua,
  akses tanpa Termius, atau latihan deploy production
- [ ] Idempotency key sisi provider (ADR-004); artifact store dengan versioning (ADR-005)
- [ ] Capability pack gambar, video/audio, game, dengan gate non-kode (ADR-006)
- [ ] Git untuk agen otonom (diskusi 2026-10-24, rincian di arsip): sandbox tetap tanpa git; history read-only, repo sintetis,
  lalu branch/commit/push hanya dari harness

## Batasan yang diterima

- `budget.max_seconds` hanya soft limit di graf riset; **code task tidak punya batas waktu dinding** (`DESIGN_AUTO_VALIDATION.md`)
- Tarif konteks panjang Haiku 5.5 (> 100.000 token) tidak dimodelkan; role Haiku yang panggilannya bisa melewatinya ditolak (`ConfigError`)
- Prompt caching hanya Anthropic, TTL 5 menit, mati bawaan; bukan untuk Haiku 5.5 (D5)
- Cap USD untuk model non-Anthropic bertumpu pada perkiraan token heuristik: bukan batas finansial mutlak
- Viewer offline = layar kosong (aset ber-hash tidak di-cache oleh `sw.js` yang dipin); pemindaian browser storage berbasis
  teks tidak menangkap akses yang disamarkan (SPEC_PWA_VIEWER A3)
- Empat skrip eksperimen lama (`analyze_series.py`, `sim_admission.py`, `dry_feedback.py`, `measure_context.py`) masih membaca log dengan
  `json.loads` per baris; diarsipkan apa adanya
