# Pending

Daftar kerja Argus yang **masih terbuka**. Status milestone dan ADR beserta buktinya ada di [`docs/Reconciliation.md`](docs/Reconciliation.md)
(satu-satunya tempat status). Riwayat butir yang sudah selesai (bukti, angka, PR): [`docs/reviews/PENDING_ARCHIVE_2026-10-30.md`](docs/reviews/PENDING_ARCHIVE_2026-10-30.md)
(sampai 2026-10-30), [`docs/reviews/PENDING_ARCHIVE_2026-10-22.md`](docs/reviews/PENDING_ARCHIVE_2026-10-22.md) (sebelumnya) dan `docs/reviews/`.

Terakhir diperbarui: 2026-10-30 malam, jalur cepat sesudahnya (#268) (viewer PWA live di HP Atha: #256, #257, #261, #263–#266; staging namespace #258;
notifikasi monitor #259/#260). Dirapikan: semua butir `[x]` pindah ke arsip 2026-10-30.

Jalur cepat 2026-10-30 (#268): `audit_run.py` membangun ulang balasan yang ditolak harness (tanpa tool call → `NUDGE`, call
tidak valid, `Finish` bersama call lain; teksnya satu fungsi `rejected_reply` di `codetask/agent.py`); layar batas drafter,
riset, `resume` agen, dan `retry` menyebut environment dan image; prompt drafter: satu entri `changed_tests` per berkas lama,
berkas baru di `new_tests`; `scripts/pin_status.py`. Ditutup tanpa kode (sudah ada): judul `PR.md` dipotong di batas kata
(83a75d5), `estimate misses` per tahap di `status` (#240 E3), larangan `git` di prompt drafter.

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
  dan patch lalu `argus applied`. `argus-viewer`: berkas yang dilindungi di `.argus/protected`, dipaksa harness (#270).
- **Staging:** satu "go live" per `PLAN.md` yang ter-commit; **satu langkah = satu perintah**; berhenti di langkah pertama yang
  meleset; lanjut butuh "go live" baru. Data viewer = snapshot terakhir (monitor tiap 15 menit).

## Terbuka sekarang

### Keputusan Atha yang ditunggu

- [ ] **UI kontrol interaktif** (Atha 2026-10-30, scope dibahas di chat): fase 0 spek `SPEC_CONTROL_UI` (service kontrol
  terpisah `127.0.0.1:8711`, proxy viewer tetap GET-only, CSRF/Origin, audit di `job.json`, batas biaya server-side), fase 1
  halaman review draf read-only (jalur cepat), fase 2 aksi tanpa biaya (`reject`/`abandon`), fase 3 aksi berbayar, fase 4
  tombol staging. Pertanyaan terbuka: siapa yang approve, batas $ via UI, "go live" lewat tombol, port 8711 + `permitopen`
  kedua di kunci HP, waktunya terhadap up2
- [~] **Shadow mode** (usul Claude 2026-10-30). **Batch 1 dihentikan 2026-10-31** (Atha) setelah 2 job, 2 blok nyata, keduanya
  lolos gerbang harness: (1) `097d` issue 003 bertentangan dengan tes lama `jobs-list` yang dilindungi (query satu halaman), agen
  menyembunyikan teks `<option>` di `<span>` (HTML tidak valid, vitest hijau, React hanya `console.error`); (2) `0e27` drafter
  membuang `jobs-list.test.jsx` dari regresi, patch merusak tes lama itu dan tetap REVIEW_READY. Biaya $0.0654. Log:
  `~/argus-viewer-issues/SHADOW.md`. Kesimpulan: review Claude masih perlu untuk kelas ini. Urutan sesudahnya (Atha "Ok"):
  - [x] Tweak 1 (repo `argus-viewer` 56b7e00, manual): tes 001/002 mencari di sel tabel/link, bukan query satu halaman
  - [x] Tweak 2 (repo `argus-viewer` 56b7e00): `vitest.setup.js` (dilindungi) menggagalkan tes pada `console.error`; terbukti
    lewat `run_validation` harness: patch hack `097d` merah
  - [x] Tweak 3 (jalur ketat, #273, SPEC_VITEST_FULL_REGRESSION): draf vitest wajib menyebut setiap berkas tes lama di commit
    job; berkas mirip tes yang tidak bisa dijalankan harness ditolak; prompt `EXISTING TEST CONFLICT`. Mutants 14/14,
    review medium (6 diperbaiki, 3 dipertahankan), verify.sh PASS 95cbee4
  - [ ] Lanjutan K2 (tidak sekarang): cakupan Python untuk repo kecil (`argus-ledger`)
  - [ ] Reviewer Argus (fitur baru, rencana ke Atha sebelum kode): model murah menilai draf + patch + hasil semua tes; di shadow
    batch 2 berdampingan dengan Claude (Claude menilai tanpa melihat vonisnya); ukuran: blok asli yang lolos dari reviewer
  - [ ] Catatan pelajaran per repo (`.argus/lessons.md`): hanya bila batch 2 menunjukkan pola berulang yang tidak bisa jadi
    cek; pelajaran masuk hanya bila replay job lama membuktikannya atau disetujui. Tidak: aturan yang ditulis dan dipakai sendiri
  - [x] **Shadow batch 2** (2026-10-31, harness 900711d): 10 job, $0.2791; 8 bersih di-apply (`argus-viewer` 9273316..201a723,
    issue 003-010); 1 blok Claude (`1808`, `<th scope=row>` agar tes lama tetap hijau, sebelum gerbang); 1 berhenti di gerbang
    `EXISTING TEST CONFLICT` (`3f45`, konflik nyata, tanpa biaya agen). Sesudah gerbang: 7 job, 0 blok yang butuh Claude.
    Semua henti berasal dari tes lama yang rapuh (diperbaiki manual 8b905f9, 379550d). Belum: deploy rilis viewer ini
    (PLAN staging + "go live")
  - [x] Gerbang penanda di harness (#275, SPEC_CONFLICT_GATE): `argus approve`, `dr.approve` dan `argus retry` menolak draf
    berpenanda `EXISTING TEST CONFLICT` (huruf dan pemisah apa pun) sebelum apa pun; `status` menampilkan baris `conflict:`.
    Mutants 12/12, review medium (8 diperbaiki), verify.sh PASS
  Batas: `--max-usd 1.00` per job (drafter memesan $0.70/percobaan, agen $0.50; $0.25 BLOCKED di $0), berhenti bila biaya
  nyata job > $0.25 atau batch > $1.50. PR `stage_data` (isi draf ke snapshot, UI fase 1) ditunda sampai sesudah up2

### Terjadwal

- [ ] **up2** mulai 2026-11-07: starlette 1.10.0, fastapi 0.162.0 (aturan 2 minggu), environment `*_up2`, PLAN.md + satu
  "go live" (`docs/reviews/SPEC_DEP_UPGRADE_V0.md`)

### Gap dari pekerjaan 2026-10-30

- [x] **Berkas yang dilindungi dipaksa harness** (jalur ketat, `docs/reviews/SPEC_PROTECTED_FILES.md`, #270; keputusan Atha
  2026-10-31: `.argus/protected`, wajib untuk `pwa_node22`, `changed_tests` pada berkas di daftar ditolak, tanpa mengejar
  up2): daftar dibaca dari commit dan dibekukan di record intake, dipaksa di cek draf, tools agen, dan paket review; hapus/
  rename/symlink (P8). Security review tanpa temuan; code review medium 9 temuan (7 diperbaiki, mis. daftar job vs record task, BOM,
  direktori tanpa `/**`); 27 tes, mutants 22/22, verify.sh PASS ab85a73. Merged #270 (1288ea0, squash). `argus-viewer` pindah
  ke `.argus/protected` (1481c44, 21 glob, dibaca harness dari commit); `check_protected.py` pensiun (disimpan sebagai riwayat). Prasyarat shadow mode dan UI approve
- [~] **Pin image per checkout disalin manual.** `~/pilot3a_live` butuh `.sandbox_image_pwa_node22*` dari `~/Argus-agent`
  (job 001 ditolak sekali); `verify.sh` menulis pin baru hanya di checkout tempat ia jalan (`.sandbox_image_argus` sudah
  berbeda antar checkout). **Preflight ada** (jalur cepat 2026-10-30): `scripts/pin_status.py [--against DIR] [ENV ...]`
  dari checkout yang menjalankan job (pin, image ada di Docker, cek lolos, sama dengan checkout lain). Sinkronisasinya
  sendiri (satu lokasi pin) belum
- [ ] **Smoke kandidat viewer tidak menguji lingkungan unit systemd** (pilot viewer #1: `PrivateTmp` lolos deploy, gagal di
  unit). Tes opsi unit ada (#263); smoke live lewat 8710 hanya di `viewer-smoke`/monitor, bukan gerbang deploy
- [ ] **Kunci HP di `authorized_keys` VM** (2026-10-30): `restrict,port-forwarding,permitopen="127.0.0.1:8710"`, perintah
  paksa `sleep`; dites. Bukan di repo; dicatat di sini agar dicabut bila HP hilang (`~/.ssh/authorized_keys`, baris
  `iphone-viewer`)
- [ ] `argus code` yang ditolak karena key (tanpa `--key-file`) tetap membuat job `NEW` (`j20261030_164146_9b3d`, di-abandon);
  layar penolakan tidak menyebutnya. Kecil, tetapi menyentuh jalur key (`live()`): jalur ketat

### Kemampuan agen (jalur cepat, kandidat)

- [ ] **Gate "tes menelan traceback" salah tolak** (argus-ledger 008): pesan tes yang mengharapkan exception, dan `TypeError` di
  titik panggilan, dianggap menelan. Usul jalur ketat: catat exception yang benar-benar di-raise di kode repo selama red check
  (`sys.monitoring` RAISE, Python ≥ 3.12)
- [ ] Tes lama yang diubah drafter otomatis wajib (`22456` d1); `swe_grade.py` mencatat nama tes draf yang gagal di atas
  patch maintainer (penilai: jalur ketat)
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

Selesai 2026-10-30 (Atha): kunci API pilot lama dicabut, sisa kunci di VM dibersihkan (cek key manual router #3 tidak
diperlukan lagi: kuncinya sudah dicabut). Kunci HP `iphone-viewer` tetap dipakai.
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
