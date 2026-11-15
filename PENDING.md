# Pending

Daftar kerja Argus yang **masih terbuka**, disusun menurut arah 2026-11-15. Status milestone dan ADR beserta buktinya ada di
[`docs/Reconciliation.md`](docs/Reconciliation.md) (satu-satunya tempat status). Riwayat butir yang selesai (bukti, angka, PR) dan butir
yang tidak lagi berkaitan dengan arah: [`docs/reviews/PENDING_ARCHIVE_2026-11-15.md`](docs/reviews/PENDING_ARCHIVE_2026-11-15.md)
(salinan utuh sampai 2026-11-15), [`PENDING_ARCHIVE_2026-10-30.md`](docs/reviews/PENDING_ARCHIVE_2026-10-30.md),
[`PENDING_ARCHIVE_2026-10-22.md`](docs/reviews/PENDING_ARCHIVE_2026-10-22.md) dan `docs/reviews/`.

Terakhir diperbarui: 2026-11-15 (angka papan skor sebagai batas atas; Inti 1–3 dicocokkan dengan kode dan git log: tiga butir Inti 1 basi dikoreksi, Inti 2 dan 3 tidak berubah; sebelumnya hari yang sama: tiga keputusan Atha: urutan inti diterima, aturan main arah, daya saing = portofolio/karier; sebelumnya hari yang sama: vonis fase 2: fase ditutup, garis A/B/C diganti; sebelumnya hari yang sama: arah baru; daftar ditulis ulang, tidak ada butir yang diubah statusnya: yang `[x]` pindah ke arsip, yang
terbuka dibawa ke sini atau dicatat di bagian "Diarsipkan 2026-11-15"). Butir di bawah yang menyebut "arsip" punya rincian lengkap di
arsip 2026-11-15.

Legenda: `[ ]` belum dimulai · `[~]` sebagian · `[x]` selesai (dipindah ke arsip saat daftar ini dirapikan berikutnya).

## Arah (Atha, 2026-11-15)

**"Spesialis di sifatnya, generalis di permukaannya."** Kekuatan yang dijaga dan dijual: **"agen yang bisa ditinggal: kerjanya
terbukti, biayanya terkunci."**

- **Sifat (inti, tempat Argus spesialis):** setiap pekerjaan selesai dengan bukti yang bisa diperiksa (gerbang, tes, verdict dengan
  bukti), di dalam batas biaya yang keras (reservasi sebelum kirim, ledger, crash-resume), dan tanpa manusia atau Claude di tengah
  selain persetujuan yang memang disengaja.
- **Permukaan (tempat Argus generalis):** satu pintu, yaitu chat (`router/chat.py`, `127.0.0.1:8711`). Kemampuan ditambah satu per
  satu di atas inti yang sama, dan hanya bila kemampuan itu bisa diberi gerbang atau kartu konfirmasi (prepare, lalu confirm).
- **Menggantikan** arah "general-purpose agent, dimulai dari deep research" (2026-11-03) dan "coding agent untuk production"
  (2026-10-28). Jalur kode adalah tempat sifat itu dibuktikan lebih dulu; riset menjadi salah satu kemampuan permukaan, bukan pilar.
- **Waktu kerja Atha:** kurang lebih 8 jam per hari, tergantung limit Claude (koreksi Atha 2026-11-15). Angka "4 jam Atha per minggu"
  di `docs/reviews/FABLE_PLAN_2026-11-11.md` diketik asal dan tidak berlaku; jadwal di bagian 8 rencana itu ikut tidak berlaku,
  urutan dan syarat buka ulangnya (bagian 2 dan 4) tetap.

- **Vonis fase 2, eksperimen repo luar (Atha, 2026-11-15): fase ditutup, garisnya diganti.** Hasilnya dicatat sebagai **"benar
  menurut tes, belum rapi menurut rubrik"**: tes pemelihara lolos 6 dari 8 (batch 2) dan 6 dari 6 (batch 3), tetapi nilai buta
  hampir semuanya B (batch 2 A1 B6 C1, batch 3 B semua); batch 1 dari 7 issue yang sah 6 A dan 1 C bila artefak mode diabaikan, 2 A
  bila dihitung (`pilots/outside_v0/RESULT.md`, `pilots/outside_v1/`, `pilots/outside_v2/batch3/RESULTS.md`). Ini **bukan vonis
  "sukses"** dan bukan "gagal": garis A/B/C untuk 10 issue (gagal ≤ 2 A, sukses ≥ 5) tidak dipakai lagi. **Ukuran penggantinya:**
  persen issue yang sampai staging tanpa campur tangan Claude (belum ada di papan skor, lihat "Ukuran"). Tidak ada butir yang
  menunggu vonis ini lagi; yang dulu menunggunya kini mengikuti urutan inti.

- **Urutan inti (Atha, 2026-11-15: "Terima urutan"):** VF O1 kenari dan nonce → `argus apply` → antrean PRD; di permukaan: assistant
  atas Argus sendiri (lapis 1). Antrean PRD dibuka sesudah kenari, nonce dan `argus apply` ada. Operator rantai dan pekerjaan baru di
  jalur riset tidak ada di urutan ini, jadi tetap tidak dimulai; dibahas lagi paling cepat di titik cek.
- **Aturan main arah (Atha, 2026-11-15: "2 minggu, 1 hari"):**
  1. Satu angka di repo: **persen issue yang sampai staging tanpa campur tangan Claude** (belum diukur, lihat "Ukuran").
  2. Arah hanya diubah di **titik cek tetap, tiap 2 minggu; yang pertama 2026-11-29**. Ide arah atau kemampuan baru di antaranya
     dicatat di "Parkiran sampai titik cek" di bawah, tidak langsung dikerjakan.
  3. Jatah eksplorasi permukaan: **1 hari per minggu**; sisanya inti (dihitung dengan waktu kerja kurang lebih 8 jam per hari).
  4. Permintaan yang chat belum bisa dicatat di "Log permintaan yang chat belum bisa" di bawah; kemampuan permukaan berikutnya
     dipilih dari log itu di titik cek.
- **"Daya saing" untuk siapa (Atha, 2026-11-15: "Portofolio/karier"):** bukti dan angka cukup; production dan pengguna kedua tetap di
  "Ditunda sampai ada bukti kebutuhan". Bisa dibuka lagi di titik cek.
- **Peninjau jalur ketat (Atha 2026-11-15: "Reviewer pake fable aja 1"):** satu peninjau, Fable, untuk spek dan diff jalur ketat (Opus tidak lagi diminta). Dasarnya tiga sampel Opus dan Fable
  atas artefak yang sama (spek VF O1, diff VF O1, spek `argus apply`): hampir semua temuan keduanya nyata dan diverifikasi dengan menjalankan, masing-masing menemukan hal yang tidak ditemukan
  yang lain (n = 3, bukan kesimpulan statistik); Claude menyarankan keduanya, Atha memilih satu. Dikaji lagi di titik cek 2026-11-29 dengan jumlah temuan unik per PR.
- **`argus apply` (Atha 2026-11-15: "K1-k7 setuju ... Merge semua PR. Langsung lanjut"):** spek `docs/reviews/SPEC_ARGUS_APPLY.md` rev 2 disetujui (K1 `--read-sha` wajib; K2 HEAD sama dengan `intake.commit`, tanpa
  `--onto-descendant`; K3 commit di cabang aktif; K4 tanpa push, merge atau deploy; K5 hook, filter, fsmonitor dan gpg tidak berjalan, konfigurasi lokal di luar daftar putih ditolak; K6 kartu chat menyusul; K7 dua PR:
  PR 1 memperbaiki `applied()` dan mencatat sha patch, PR 2 `argus apply`). Merge kedua PR diizinkan sesudah `verify_at` lulus.

Cara menilai butir baru: apakah ia membuat kerja lebih terbukti, biaya lebih terkunci, atau Argus lebih bisa ditinggal? Bila tidak,
ia masuk "Ditunda sampai ada bukti kebutuhan".

## Ringkasan

| | Status | Rinci |
|---|---|---|
| Fondasi (M1–M3, budget, ledger, crash-resume, sandbox) | `[x]` | Reconciliation bagian 1 |
| Jalur kode, issue sampai staging (M6, M9 staging) | `[x]` MVP | repo Argus, sympy (SWE), `argus-ledger`, `argus-viewer`; dua aplikasi di staging |
| **Bisa ditinggal** (tanpa Claude di tengah) | `[~]` | Claude masih mereview, meng-apply dan men-deploy; VF O1 dan `argus apply` ter-merge; antrean PRD dan angka "tanpa campur tangan Claude" belum ada |
| Permukaan: chat | `[~]` | C1–C4 live di 8711 (Issue, Riset, Keputusan, Status); C5 terbuka |
| Kemampuan lain di permukaan (riset, lainnya) | `[~]` riset | riset: pekerjaan baru tidak dimulai (di luar urutan inti); lainnya belum dimulai |
| M5 observability | `[~]` | ledger, inspektor, papan skor; belum: angka "tanpa campur tangan Claude", eval set tidak jenuh |
| M4, M7, M8, capability pack, production | `[ ]` | ditunda sampai ada bukti kebutuhan |

## Cara kerja (berlaku)

- **Dua jalur** (2026-10-28): ketat (uang/ledger, crash-resume, sandbox, key, grader, staging, chat: spek, review, mutan,
  `verify_at`, "merge" Atha; urutan: tes → review → mutan → verify) dan cepat (kemampuan agen dan aplikasi latihan: Claude merge
  sendiri). Satu PR jalur ketat pada satu waktu. Jalur penasihat: `AGENTS.md`.
- **Aplikasi latihan** (`argus-ledger`, `argus-viewer`): issue ditulis lewat chat di HP atau oleh Claude; Claude mereview draf dan
  patch, meng-apply dan merilis (jalur cepat didelegasikan 2026-11-08); berkas yang dilindungi di `.argus/protected` dipaksa harness.
- **Staging:** satu "go live" per `PLAN.md` yang ter-commit; satu langkah = satu perintah; berhenti di langkah pertama yang meleset.
  Izin tetap (2026-11-11) untuk deploy pull-only tanpa restart, staging, uang atau key.
- **Angka di dokumen status** disalin dari berkas hasil skrip di `verification/` dan menyebut berkasnya; angka tanpa sumber dihapus.
- **Pra-cek tes sandbox** sebelum `verify_at`: `bash scripts/precheck.sh [basis]` (Reconciliation bagian 7).

## Terbuka sekarang

**Dicek 2026-11-15 terhadap kode dan git log (Inti 1, 2 dan 3):** tiga butir Inti 1 sudah dikerjakan tetapi masih tercatat terbuka (butir judge dan R1b, kalimat
rerun di "Paket 3", baris `dN submits`); dikoreksi di bawah. Inti 2 dan 3: tidak ada pekerjaan yang terlewat. Dasarnya: grep tidak menemukan
`argus apply`, `applied --amend`, `argus fix`, `argus chain`, antrean atau tahap PRD, redraft otomatis, pembacaan `lock_sha256`, kontrak API di snapshot, ukuran
waktu sandbox per job, atau idempotency key di `scripts/`, `router/`, `codetask/`, `harness/`. Yang tidak bisa dipastikan dari grep: apakah `viewer-smoke` kini ikut
gerbang `viewer-deploy` (perintahnya ada di `router/stage_viewer.py`), dan penolakan key yang tetap meninggalkan job `NEW` (`start_code` membuat job sebelum
pemeriksaan key di `live()`; tidak diuji ulang). Pengecekan bentuk key hanya mengenal Anthropic (`KEY_SHAPE`, `router/job.py:80`).


### Keputusan Atha yang ditunggu

- [ ] **GATE-10** (tidak darurat, 2026-11-14): P1 memindai tes yang ditulis agen sendiri dengan pola deteksi, sehingga tes jujur yang
  menyebut `sys.modules` dan `pytest` berakhir `FAILED_ACCEPTANCE` tanpa retry. Usul Opus: persempit sedikit (sekitar 15 baris,
  jalur ketat). Risiko kecil; ditunda (arsip, butir "Fase 3 dan batch kedua").
- [ ] **Probe aplikasi dari nol** (`docs/reviews/FABLE_GREENFIELD_PROBE_PROPOSAL.md`): aplikasinya dan "ok"; saran Fable dan Claude:
  sesudah eksperimen repo luar.

### Inti 1: kerja terbukti

- [x] **VF O1 kenari dan nonce** (2026-11-15; `docs/reviews/SPEC_VF_O1_CANARY_NONCE.md` rev 2; PR `vf-o1-canary`): validasi pytest hanya dipercaya dengan catatan
  harness di belakang nonce per run, sesi kenari yang berakhir seperti seharusnya, dan catatan yang sepakat dengan laporan. `verify_at` PASS (5037 lulus, 4 xfail yang
  disengaja, 0 sandbox ter-skip; `verification/verify-20261115T084657Z-aarch64.log`), mutan 39/39 (`verification/vf_o1_mutants.log`), tinjauan Opus dan Fable atas
  spek dan diff. **Batas yang diterima, jangan dikutip lebih lebar:** hanya menutup cetak-lalu-keluar dan penambalan global yang ikut mengenai kenari; pemalsu yang terbatas
  pada sesi 1 atau pada tes kontrak (F1 sampai F3) atau yang membaca nonce dari argv (F6) lolos (xfail-strict di `tests/test_vf_canary.py`). **Aturan "jangan apply job `DONE`
  tanpa dibaca" tetap berlaku.** Proyek jujur dengan hook `pytest_report_teststatus` kustom bisa kena G4 (image kita tanpa plugin pytest).
- [~] **Approve atas patch akhir, bukan rencana** (sebagian besar dicakup `argus apply --read-sha` sejak 2026-11-15: apply hanya jalan dengan sha patch akhir; yang belum: alur approve draf tetap atas rencana, dan `--read-sha` bukan bukti membaca) (`pilots/outside_v2/PROTOCOL_FINAL_PATCH.md`): dipakai di batch 3; pembacaan acak 1
  dari 3 oleh pembaca yang didelegasikan Atha: 0 dari 3 terbalik, tidak bisa membedakan karena semuanya reject (`atha_verdicts.json`,
  #504). Belum menjadi alur baku di harness.
- [~] **Urutan Fable 2026-11-13, butir 3–4 (judge, R1b, validitas, rubrik)**: **sebagian besar selesai.** Judge mati sebagai bawaan (#485); R1b, issue
  dijalankan lagi pada pohon yang sudah di-patch, `raised` di dasar lalu `ran clean` (#485, `tests/test_repro_patched.py`); aturan validitas v2, F2P hanya dari
  tes yang ditambah PR (#487, dipakai di batch 3); semua patch batch 3 dinilai buta oleh Opus dan Fable (#505); cek batas pengetahuan DeepSeek
  (`knowledge_check.py` #495, hasil "no" di 10 probe; probe tidak bisa memisahkan ingatan dari kehati-hatian). **Tersisa:** Atha sendiri menilai 3 sampai 4 patch
  sebagai jangkar (tidak ada buktinya di git log; pembaca yang didelegasikan Atha tidak sama dengan penilaian Atha).
- [ ] **R2 `ReportNoRepro`** (hanya spek, `SPEC_REPRO_V0.md:25`): hanya bila ada perbandingan mekanis "harap X, dapat Y".
- [ ] **RC bagian (b)**: `--from-conflict` dan layar (`FABLE_SPEC_REPORT_CONFLICT_v1.md:95`; layar sebagian lewat `47bcce6`). Batas
  yang diketahui: RC tak bisa mengonfirmasi konflik "sekarang raise" atau yang melibatkan `subTest`.
- [ ] **Paket 3**: putaran kasus sintetis kedua untuk RC dan GATE (10 sampai 15 kasus, model dari keluarga lain, adversarial, hanya
  dari spek; daftar kasus di arsip). Rerun `pilots/synthetic_rc_gate/run.py` sesudah #527 **sudah dilakukan** (#529: 32 dari 35 cocok; GATE-10, -14 dan -16 berubah seperti amandemen; `RESULTS.md` sudah memuat perilaku baru).
- [~] **Tes lama bocor oleh fitur baru** (probe rantai, Reconciliation bagian 4e): gerbang `scope:no_test_detection` (#436) dan
  peringatan `leaks` (#437, penasihat, Python) ada. Belum:
  - [ ] pesan "terjepit tes lama" saat `FAILED_ACCEPTANCE` karena tes lama terkunci (retry tak menolong)
  - [ ] ukur false positive `leaks` di job ledger nyata berikutnya (sampel awal: 3 draf issue 019, 2 benar, 0 positif palsu); bila
    tepat, usul menolak draf dengan jalan keluar (spek baru); `leaks` membedakan "tidak dicek" dari "tidak ada" (B12)
  - [ ] `leaks` untuk JS/vitest; pola deteksi yang belum dikenal gerbang (`os.environ["TESTING"]`, nama modul pemanggil); false
    positive `NODE_ENV: 'test'` di config; tes draf memasang `history.state` `{}`, bukan `null` seperti browser
- [ ] **Stage mutan di job kode** (Atha 2026-11-11: "yang bikin mutant kalo nanti Argus lu lepas siapa?"): model memilih 5–15 mutan
  untuk baris yang diubah, harness menjalankannya di sandbox dan melaporkan yang lolos sebelum applied. Jalur ketat, belum dimulai.
- [ ] **Mutu patch: dari B ke A** (temuan fase 2: benar menurut tes, belum bisa di-merge tanpa dirapikan). Yang membuat B menurut
  catatan batch: letak tes (semua patch batch 3 menaruh tes di berkas baru; APPEND-TESTS #506 dan INSERT-INTO #514 sudah ter-merge,
  diukur pada data batch 3 di `pilots/outside_v2/batch3/` (`APPEND_MEASUREMENT`, `INTO_CLASS_MEASUREMENT`), belum pada batch baru), mode berkas (diperbaiki #482), pembungkus exception. Belum ada batch sesudah perbaikan itu.
- [ ] **Mutu drafter dan agen** (kandidat, dari batch SWE dan repo luar): tes lama yang diubah drafter otomatis wajib (`22456` d1);
  drafter mencari titik nilai salah pertama kali muncul (`20428`); gerbang writable lebar vs regresi sempit; over-spesifikasi di tes
  drafter (3 dari 8, pembacaan buta); DROP-OLD-REQUIRED (`SPEC_DROP_OLD_REQUIRED.md` bagian 5, sengaja dibiarkan terbuka); baris submits di status sudah ada (#519) tetapi menghitung jawaban pertanyaan merah sebagai submit; `remove_labeled` dengan label kosong perlu penjaga; kontaminasi
  data latih.
- [ ] **Vitest v0**: tes lama tidak bisa diubah (`changed_tests` hanya Python), tanpa `-t`; Playwright (tahap 3b) bila ada kebutuhan.
- [ ] **Verifikasi** (sisa SPEC_VERIFY_HARDENING): pangkas run kontainer di `tests/test_draft.py` (322 detik); penjaga untuk pemakaian
  `docker` langsung tanpa fixture bersama.

### Inti 2: bisa ditinggal (tanpa Claude di tengah)

- [x] **`argus apply`** (2026-11-15, spek `docs/reviews/SPEC_ARGUS_APPLY.md` rev 2 disetujui Atha, dua PR, keduanya ter-merge). PR 1 (#552): `applied()` membandingkan seperti paket menulis patch, sha256 patch dicatat di `job.json`,
  `_record_applied` tanpa kunci. **PR 2: `argus apply <job> --read-sha <sha>` (`router/apply.py`)**: patch dalam satu commit di cabang aktif repo target; konfigurasi lokal di luar daftar putih, `GIT_*` pemanggil, hook, filter, fsmonitor dan gpg
  tidak berjalan; patch yang menyentuh `.git`, `.gitattributes`, `.gitmodules`, symlink atau submodule ditolak; perbandingan byte `git diff --cached` dengan `changes.patch` sebelum perubahan pertama; gagal di tengah dibatalkan dan diperiksa,
  mati sesudah commit disembuhkan panggilan berikutnya; kunci per repo; tanpa push, merge, deploy atau model. `verify_at` PASS 5134 (`verification/verify-20261115T130852Z-aarch64.log`), mutan 40/40
  (`verification/apply_cmd_mutants.log`), tinjauan Fable atas spek dan diff. **Batas yang diterima:** `--read-sha` hanya membuktikan seseorang menyalin sha yang `status` cetak, bukan bahwa patch dibaca; repo target dan `.git`-nya dianggap tepercaya;
  kunci per repo bergantung pada `jobs_dir` yang sama; `core.excludesFile` global membuat berkas ter-ignore terbaca "tree kotor" (aman, membingungkan). Belum: kartu apply di chat (K6), `argus applied --amend`.
  Bersamanya yang dulu tercatat: (K6 v0): sekarang perintah apply dicetak `status` dan dijalankan Claude; di probe PRD ini sambungan yang
  paling terasa (`pilots/prd_probe_v0/RESULT.md`). Bersamanya: `argus applied --amend <commit>` hanya untuk `APPLIED` yang belum
  di-deploy (kasus viewer 021). Jalur ketat; membuka layanan approval di kode (ADR-007).
- [ ] **Arah "PRD sampai staging"** (Atha 2026-11-12): tahap PRD (obrolan menghasilkan `PRD.md` + daftar issue berurutan, di-approve
  sekali dengan sha), antrean berurutan (issue berikutnya jalan setelah yang sebelumnya `APPLIED`), `argus apply`. Probe manual
  selesai dan live 2026-11-12 (`pilots/prd_probe_v0/`, `GLUE_LOG.md`). Urutan inti diterima Atha 2026-11-15: dibuka sesudah kenari dan nonce dan `argus apply`, karena tanpa keduanya antrean tetap butuh Claude di tengah.
- [ ] **`argus fix <job>`** dari temuan yang dibekukan (kandidat; satu kali per job, agen boleh lapor "terjepit tes lama"); **redraft
  otomatis (3b)** sekali per job bila d1 `submits_exhausted` (ditunda Atha 2026-11-11 sampai kasusnya muncul lagi). Jalur ketat.
- [ ] **Operator rantai tetap** (`argus chain`: T1 → apply → S → T2): tunggu rantai lintas repo kedua dengan pola perekat yang sama.
- [~] **Pin image per checkout disalin manual**; preflight `scripts/pin_status.py` ada, sinkronisasi (satu lokasi pin) belum. Celah:
  `lock_sha256` image tidak dibaca (image basi vs lock baru tidak terdeteksi).
- [ ] **Smoke kandidat viewer tidak menguji lingkungan unit systemd** (smoke live lewat 8710 hanya di monitor, bukan gerbang deploy).
- [ ] **Celah penulis issue:** hanya membaca satu repo, tidak tahu data yang dikirim repo lain. Usul: daftar kontrak API ledger sebagai
  berkas baca di snapshot viewer.
- [ ] **Agen kode 90% waktu menunggu sandbox** (job 040: 527 dari 586 detik): ukur dulu jumlah dan durasi jalan tes per job.

### Inti 3: biaya terkunci

- [ ] **E1 batas yang diketahui** (diterima Atha 2026-11-11, `AGENTS.md`): biaya tak diketahui dihitung nol ke cap. Dibuka lagi bila
  penyedia langsung yang melaporkan token cache-write ditambahkan, atau `usd_complete = false` muncul di job nyata (perbaikan siap di
  branch `fix-b-e1-draft`).
- [ ] `argus code` yang ditolak karena key (tanpa `--key-file`) tetap membuat job `NEW`; router belum mengecek bentuk kunci DeepSeek.
  Jalur ketat (jalur key).
- [ ] Idempotency key sisi provider (ADR-004): dampak rendah selama tidak ada aksi eksternal selain panggilan model; **naik
  prioritas begitu ada kemampuan berefek ke luar** di permukaan.

### Ukuran (M5)

- [~] **Angka utama di papan skor: ada sebagai BATAS ATAS, belum tepat** (2026-11-15, `scripts/scoreboard.py`, `verification/scoreboard-2026-11-15.json`, jobs `~/pilot3a_live/jobs`):
  dari 126 job kode, **30 sampai staging tanpa retry, redraft, research ok atau steering dan diterapkan seperti yang direview = 23,8%** (batas atas dari "sampai staging tanpa campur tangan Claude"); 35 sampai staging (27,8%);
  66 applied (52,4%, 65 persis seperti direview); $0,1145 per perubahan; judge pada 7,9% job; `argus apply` belum dipakai (0). **Kenapa batas atas, bukan angkanya:** siapa yang approve, apply dan deploy tidak tercatat
  (`by` = `$USER`, sama untuk Atha dan Claude), jadi job di dalam himpunan itu masih bisa saja dikerjakan Claude dengan tangan; job di luarnya pasti butuh keputusan tambahan. Menjadi tepat bila approve bisa dari chat (`via=ui`,
  masih ditahan) dan apply tercatat `method=apply` (`argus apply`, sejak 2026-11-15): dihitung ulang di titik cek 2026-11-29, angkanya akan terpisah dari data lama.
- [ ] **Supervisi:** menit kerja Atha per pilot dan pemakaian Claude belum dicatat (satu baris per minggu yang dikutip papan skor).
- [ ] **Eval set yang tidak jenuh:** Eval Set v1 16/16 hanya regresi; instance SWE terkontaminasi. Perluas dari kegagalan nyata,
  bekukan hash.
- [ ] Efek petunjuk berhenti (#188, #200, #204) belum terpisah dari variasi model; pertanyaan B D5 (≥ 2 putaran perbaikan dalam satu
  attempt); approve tanpa oracle lebih lama (±5–7 menit per draf).

### Permukaan: chat (pintu depan)

- [~] **CHAT-APP** (`docs/reviews/SPEC_CHAT_APP.md`; kode tepercaya jalur ketat, bukan tulisan agen Argus). C1–C4 live; chat di
  `127.0.0.1:8711`, `argus-control` dimatikan. Rollback: `scripts/chat_cutover.sh rollback --yes`. Berikutnya, atas kata Atha:
  - [ ] (a) Atha mencabut `permitopen` 8712 dari kunci `iphone-viewer` dan forward 8712 di Termius (setelah Reject-Batal dicoba di HP)
  - [ ] (b) **C5 poles** (`docs/reviews/PROMPT_CHAT_C5.md`): hapus kode `control`, batas baca `Chat.thread` (11.13), pesan error
    berbahasa Indonesia, `--no-draft` di CLI reject/abandon, papan skor sebagai kartu, tes riset sungguhan dari HP (belum dicoba)
- [ ] **Assistant atas Argus sendiri** (usul Claude 2026-11-15, lapis 1): "apa yang menunggu gue", "kenapa job ini gagal", "berapa
  habis minggu ini", "jelaskan draf ini". Hanya membaca. Perlu amandemen spek chat lebih dulu: obrolan bebas memakai uang di tiap
  pesan, sedangkan aturan chat menuntut prepare lalu confirm untuk rute yang memakai uang (usul: satu konfirmasi untuk jatah sesi di
  dalam batas harian). Jalur ketat. Belum diputuskan.
- [ ] **Approve dari HP lewat chat** (dulu UI kontrol fase 3, desain F8): ditahan; syarat buka (rencana Fable 2026-11-11): Atha
  menolak 4 dari 5 draf buruk yang ditanam, lewat ringkasan di HP. Tombol staging (dulu fase 4): butuh operator kedua.
- [ ] Papan skor di HP: tabel terpotong (kolom `Terbuka` dan `Biaya`); perbaikan kecil di viewer lewat Argus (±$0,05–0,1).
- [ ] "no draft to review" untuk job `AWAITING_APPROVAL` yang drafnya belum masuk snapshot → pesan "tunggu ≤ 15 menit" (issue kecil).
- [ ] Jawaban huruf demi huruf (streaming; menyentuh `harness/llm.py`, jalur ketat uang). Ide issue ledger: biaya per model/role.

### Permukaan: kemampuan lain (satu per satu, hanya dengan gerbang)

- [~] **Riset (`argus research`): pekerjaan baru tidak dimulai** (tidak ada di urutan inti yang diterima Atha 2026-11-15; dibahas lagi paling cepat di titik cek 2026-11-29); tetap tersedia sebagai mode di chat (C3) dan sebagai tahap opsional
  untuk kode (`--from-research`). Yang terbuka saat dibuka lagi:
  - [ ] kebenaran faktual ("7/8 benar") belum dinilai terhadap sumber independen; **eval riset independen** (set pertanyaan beku
    dengan cek fakta independen; `SUPPORTED` hanya berarti kutipannya ada)
  - [ ] catatan review: ReadDocs (`tools/web.py`) punya titik buta konfigurasi yang sama; `window.X = {...}`/`__NEXT_DATA__` tidak
    terdeteksi; gate s1 menolak seluruh submit terakhir karena satu bagian kepanjangan; aturan "submit terakhir" tersalin di dua
    `gate_submit`; #314 belum diuji di job nyata
  - [ ] worker free masih NO_FINDINGS 4/9; satu worker berbayar masih memotong kutipan; pantau e1 `reasoning.effort: low` di 2–3 job
    `deepinfra` berikutnya
- [ ] **Uji prompt injection lanjutan:** v0 bersih (empat varian, n = 1 tiap varian, `pilots/prompt_injection_v0/RESULT.md`); 16
  rancangan di `FABLE_INJECTION_ATTACKS.md` belum dijalankan; injeksi di teks klaim dan fakta API palsu belum diuji. **Prasyarat**
  sebelum kemampuan apa pun yang membaca teks luar sambil memegang data pribadi.
- [ ] **Kemampuan berikutnya belum dipilih.** Kandidat yang dibahas 2026-11-15 (belum diputuskan): tanya-jawab cepat dengan web
  (pembungkus ringan riset); email dan kalender hanya-baca dengan draf balasan, tanpa mengirim. Tindakan berefek ke luar (kirim pesan,
  deploy production, transaksi, hapus data) selalu butuh persetujuan manusia (keputusan 2026-11-03) dan butuh memori, policy dan
  approval di kode (M8, M7, ADR-007) lebih dulu.

## Parkiran sampai titik cek (berikutnya: 2026-11-29)

Ide arah atau kemampuan baru yang muncul di antara titik cek: tanggal, kata-kata Atha, tempatnya terhadap arah. Tidak dikerjakan
sebelum titik cek, kecuali Atha berkata ia mengganti pekerjaan yang sedang berjalan.

- (kosong)

## Log permintaan yang chat belum bisa

Satu baris per permintaan: tanggal, apa yang diminta, kenapa chat belum bisa. Kemampuan permukaan berikutnya dipilih dari sini di
titik cek.

- (kosong)

## Pekerjaan operasional (Atha, di luar repo)

- [ ] **Kunci HP di `authorized_keys` VM**: baris `iphone-viewer` (`restrict,port-forwarding,permitopen=...`); dicatat agar dicabut
  bila HP hilang. Backup: `~/.ssh/authorized_keys.bak-20261114-chat`.
- [ ] Deploy harness sebagai service (systemd): operasional, bukan M9.

## Ditunda sampai ada bukti kebutuhan

Syarat buka ulang dari `docs/reviews/FABLE_PLAN_2026-11-11.md` bagian 4, kecuali disebut lain.

- [ ] **M4** penjadwalan multi-agent dengan dependensi (buka: kelas job yang gagal oleh satu agen dan lolos bila dipecah tangan);
  **planner berhirarki** (buka: dua rantai dengan perekat yang dinilai "tidak bisa diotomasi"; tiga probe sejauh ini tidak
  membenarkannya: `from_research_v0`, `research_need_v0`, `chain_probe_v0`)
- [ ] **M7** registry kapabilitas dan policy (ADR-001), adapter MCP (buka: approver kedua, atau jumlah tool membutuhkannya)
- [ ] **M8** penemuan tool dan memori (ADR-003) (buka: kegagalan berulang yang tidak bisa dijadikan cek); catatan pelajaran per repo
  (`.argus/lessons.md`) hanya bila replay job lama membuktikannya
- [ ] **M9 production** (DNS/TLS, pengguna, kredensial): spek dan persetujuan terpisah; pemicu: pengguna kedua, akses tanpa Termius,
  atau latihan deploy production
- [ ] **Capability pack** gambar, video/audio, game: gate non-kode (ADR-006) dulu; satu per kali
- [ ] Artifact store dengan versioning (ADR-005); M5 sisanya (tracing/dashboard, benchmark single vs multi-agent)
- [ ] Git untuk agen otonom: sandbox tetap tanpa git; history read-only, repo sintetis, lalu branch/commit/push hanya dari harness
- [ ] ENV lanjutan repo luar (cachetools: layout `src/`, repo ketiga), fase kedua eksperimen (issue yang benar-benar terbuka):
  belum diputuskan
- [ ] Ringkasan validasi untuk agen (bila `context_limit` karena output validasi); D4 batas ListFiles + daftar berkas di issue;
  cakupan Python untuk repo kecil (K2)

## Diarsipkan 2026-11-15 (tidak lagi berkaitan dengan arah; teks lengkap di arsip)

- **Deep research sebagai arah utama** dan urutan tahap 1–4 "general-purpose" (2026-11-05): diganti arah di atas. Riset tetap ada
  sebagai kemampuan permukaan; batch v1 R1–R8, worker paralel, OpenRouter Batch API, PR 1b `free_repos`, Vercel sebagai cadangan.
- **Satu pipeline berhirarki** sebagai arah (2026-11-04): kini hanya butir "Ditunda" dengan syarat buka.
- **UI kontrol** (`SPEC_CONTROL_UI`, fase 0–4, 8711): diserap chat (C4); layanan `argus-control` dimatikan 2026-11-15. Fase 3 dan 4
  hidup terus sebagai butir chat di atas.
- **Chatbox penulis issue** di UI kontrol (amandemen 1–5 `SPEC_ISSUE_WRITER`, optimasi kecepatan giliran, eksperimen model penulis):
  selesai atau dihentikan (rencana Fable: stop menyetel latensi penulis issue); mode Issue kini di chat.
- **Shadow mode** batch 1–2 dan **Tahap 2 "kurangi supervisi"** (ditutup Atha 2026-11-06): riwayat. `argus judge` tetap ada sebagai
  saran, tidak lagi bawaan (lihat butir "Urutan Fable 2026-11-13, butir 3–4").
- **Self-review Argus** (`argus review --diff` tidak dibangun), **Alur A** (bug yang jawabannya tidak ada di ingatan model; task dua
  lengan untuk upgrade), **Email Agensi.io** (marketplace skill).
- **Rencana Fable fase 1** (SB, FIX-A, FIX-B E2, ENV varian 1, GUARD, PRE) dan **fase 3 yang ter-merge** (REPRO R1, FIX-C, RC MVP,
  GATE, VF probe dan O2, APPEND-TESTS, SANDBOX-SPLIT, INSERT-INTO, MAX-SUBMITS, paket 2): selesai.
- Deploy Stage 13, up2, berkas yang dilindungi (#270), gate "tes menelan traceback" (#304), rekonsiliasi biaya Oktober: selesai.

## Batasan yang diterima

- `budget.max_seconds` hanya soft limit di graf riset; **code task tidak punya batas waktu dinding** (`DESIGN_AUTO_VALIDATION.md`)
- Tarif konteks panjang Haiku 5.5 (> 100.000 token) tidak dimodelkan; role Haiku yang panggilannya bisa melewatinya ditolak (`ConfigError`)
- Prompt caching hanya Anthropic, TTL 5 menit, mati bawaan; bukan untuk Haiku 5.5 (D5)
- Cap USD untuk model non-Anthropic bertumpu pada perkiraan token heuristik: bukan batas finansial mutlak
- Viewer offline = layar kosong (aset ber-hash tidak di-cache oleh `sw.js` yang dipin); pemindaian browser storage berbasis
  teks tidak menangkap akses yang disamarkan (SPEC_PWA_VIEWER A3)
- Empat skrip eksperimen lama (`analyze_series.py`, `sim_admission.py`, `dry_feedback.py`, `measure_context.py`) masih membaca log dengan
  `json.loads` per baris; diarsipkan apa adanya
