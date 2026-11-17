# Pending

Daftar kerja Argus yang **masih terbuka**, disusun menurut arah 2026-11-15. Status milestone dan ADR beserta buktinya ada di
[`docs/Reconciliation.md`](docs/Reconciliation.md) (satu-satunya tempat status). Riwayat butir yang selesai (bukti, angka, PR) dan butir
yang tidak lagi berkaitan dengan arah: [`docs/reviews/PENDING_ARCHIVE_2026-11-16.md`](docs/reviews/PENDING_ARCHIVE_2026-11-16.md)
(salinan utuh sebelum dirapikan 2026-11-16: rincian VF O1, `argus apply`, antrean dan tahap PRD),
[`PENDING_ARCHIVE_2026-11-15.md`](docs/reviews/PENDING_ARCHIVE_2026-11-15.md) (salinan utuh sebelum arah 2026-11-15), [`PENDING_ARCHIVE_2026-10-30.md`](docs/reviews/PENDING_ARCHIVE_2026-10-30.md),
[`PENDING_ARCHIVE_2026-10-22.md`](docs/reviews/PENDING_ARCHIVE_2026-10-22.md) dan `docs/reviews/`.

Terakhir diperbarui: 2026-11-16 (dirapikan: urutan inti selesai dibangun, butir `[x]` diringkas dan rinciannya pindah ke arsip
2026-11-16, tiga pertentangan dikoreksi, butir baru "uji lepas tangan", "catat pelaku" dan "gerbang contoh angka"). Tidak ada butir
yang diubah statusnya selain koreksi itu. Butir yang menyebut "arsip" punya rincian lengkap di arsip 2026-11-16 atau 2026-11-15.

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

- **Urutan inti (Atha, 2026-11-15: "Terima urutan"): selesai dibangun 2026-11-16.** VF O1 kenari dan nonce (#550) → `argus apply`
  (#552, #553) → antrean PRD (bagian A #555, tahap PRD B1 #559, penulis PRD B2 #566 dan #568). Yang tersisa dari urutan itu: assistant
  atas Argus sendiri di permukaan (lapis 1), belum dimulai. **Yang beres mesinnya, bukan klaimnya:** "bisa ditinggal" belum terbukti
  (lihat "Inti 2"). **Berikutnya (usul Claude 2026-11-16; Atha meminta rapikan `PENDING` dan prompt untuk uji lepas tangan):** ukur
  yang sudah dibangun, yaitu uji lepas tangan (ditunda 2026-11-16, terlalu berat), catat pelaku, gerbang contoh angka. Operator rantai dan pekerjaan baru di jalur riset
  tetap tidak ada di urutan; dibahas lagi paling cepat di titik cek.
- **Aturan main arah (Atha, 2026-11-15: "2 minggu, 1 hari"):**
  1. Satu angka di repo: **persen issue yang sampai staging tanpa campur tangan Claude** (belum diukur, lihat "Ukuran").
  2. Arah hanya diubah di **titik cek tetap, tiap 2 minggu; yang pertama 2026-11-29**. Ide arah atau kemampuan baru di antaranya
     dicatat di "Parkiran sampai titik cek" di bawah, tidak langsung dikerjakan.
  3. Jatah eksplorasi permukaan: **1 hari per minggu**; sisanya inti (dihitung dengan waktu kerja kurang lebih 8 jam per hari).
  4. Permintaan yang chat belum bisa dicatat di "Log permintaan yang chat belum bisa" di bawah; kemampuan permukaan berikutnya
     dipilih dari log itu di titik cek.
- **"Daya saing" untuk siapa (Atha, 2026-11-15: "Portofolio/karier"):** bukti dan angka cukup; production dan pengguna kedua tetap di
  "Ditunda sampai ada bukti kebutuhan". Bisa dibuka lagi di titik cek.
- **Peninjau jalur ketat: sementara Opus sejak 2026-11-16 (Atha: "Ganti reviewer ke opus bro, limit fable gw hampir abis"); kembali ke Fable bila limitnya pulih dan Atha bilang.** Aturan lama di bawah:
  **Peninjau jalur ketat (Atha 2026-11-15: "Reviewer pake fable aja 1"):** satu peninjau, Fable, untuk spek dan diff jalur ketat (Opus tidak lagi diminta). Dasarnya tiga sampel Opus dan Fable
  atas artefak yang sama (spek VF O1, diff VF O1, spek `argus apply`): hampir semua temuan keduanya nyata dan diverifikasi dengan menjalankan, masing-masing menemukan hal yang tidak ditemukan
  yang lain (n = 3, bukan kesimpulan statistik); Claude menyarankan keduanya, Atha memilih satu. Dikaji lagi di titik cek 2026-11-29 dengan jumlah temuan unik per PR.
- **Keputusan lain yang berlaku** (rinci di arsip 2026-11-16): `argus apply` K1–K7 (Atha 2026-11-15; `--read-sha` wajib, tanpa push,
  merge atau deploy); antrean D1–D3 (Atha 2026-11-15: berhenti di kegagalan pertama, batas uang per antrean, Atha menyetujui tiap
  draf dan tiap patch); penulis PRD D5–D9 (Atha 2026-11-16: terminal dulu, Haiku, 5 issue, giliran $0,30 / job $1,50, Claude tidak
  menulis issue selama tiga PRD pertama).

Cara menilai butir baru: apakah ia membuat kerja lebih terbukti, biaya lebih terkunci, atau Argus lebih bisa ditinggal? Bila tidak,
ia masuk "Ditunda sampai ada bukti kebutuhan".

## Ringkasan

| | Status | Rinci |
|---|---|---|
| Fondasi (M1–M3, budget, ledger, crash-resume, sandbox) | `[x]` | Reconciliation bagian 1 |
| Jalur kode, issue sampai staging (M6, M9 staging) | `[x]` MVP | repo Argus, sympy (SWE), `argus-ledger`, `argus-viewer`; dua aplikasi di staging; repo luar `athena` (backend saja, tidak di staging Argus) |
| **Bisa ditinggal** (tanpa Claude di tengah) | `[~]` | mesinnya ada (VF O1, `argus apply`, antrean, tahap PRD, penulis PRD; empat pilot n = 1); **belum terbukti**: di semua pilot Claude menjalankan perintah dan membaca draf serta patch; angka utama baru batas atas 23,8% (`verification/scoreboard-2026-11-15.json`) |
| Permukaan: chat | `[~]` | C1–C4 live di 8711 (Issue, Riset, Keputusan, Status); C5 terbuka |
| Kemampuan lain di permukaan (riset, lainnya) | `[~]` riset | riset: pekerjaan baru tidak dimulai (di luar urutan inti); lainnya belum dimulai |
| M5 observability | `[~]` | ledger, inspektor, papan skor; angka "tanpa campur tangan Claude" baru batas atas (pelaku tidak tercatat); eval set tidak jenuh |
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

**Dicek 2026-11-16 terhadap `main` (#574):** `router/apply.py`, `router/queue.py`, `router/prd_job.py`, `codetask/prd_writer.py` dan
`tests/test_vf_canary.py` ada. Belum dicek ulang sejak 2026-11-15: apakah `viewer-smoke` ikut gerbang `viewer-deploy`
(`router/stage_viewer.py`), dan penolakan key yang tetap meninggalkan job `NEW` (`start_code` membuat job sebelum pemeriksaan key di
`live()`). Pengecekan bentuk key hanya mengenal Anthropic (`KEY_SHAPE`, `router/job.py`).

### Keputusan Atha yang ditunggu

- [ ] **GATE-10** (tidak darurat, 2026-11-14): P1 memindai tes yang ditulis agen sendiri dengan pola deteksi, sehingga tes jujur yang
  menyebut `sys.modules` dan `pytest` berakhir `FAILED_ACCEPTANCE` tanpa retry. Usul Opus: persempit sedikit (sekitar 15 baris,
  jalur ketat). Risiko kecil; ditunda (arsip, butir "Fase 3 dan batch kedua").
- [ ] **Probe aplikasi dari nol** (`docs/reviews/FABLE_GREENFIELD_PROBE_PROPOSAL.md`): aplikasinya dan "ok"; saran Fable dan Claude:
  sesudah eksperimen repo luar.
- [ ] **Riset 2026-11-16 terhadap aturan "pekerjaan riset baru tidak dimulai":** satu job riset (aturan ARB/ARA BEI) dan pilot
  research → issue → kode dijalankan 2026-11-16. Tidak tercatat apakah itu jatah hari eksplorasi (1 hari per minggu) atau pengecualian;
  Atha yang menentukan, supaya aturan main arah tetap bisa dipegang.
- [ ] **Port 443 mesin ini dibuka ke luar untuk backend athena** (2026-11-16, lihat "Pekerjaan operasional"): catatan Claude: ini
  menyentuh pemicu "M9 production" (akses tanpa Termius) yang tercatat ditunda dengan spek dan persetujuan terpisah. Athena bukan
  staging Argus, jadi mungkin memang di luar aturan itu; Atha yang menentukan, dan security list Oracle belum diperiksa.

### Inti 1: kerja terbukti

- [x] **VF O1 kenari dan nonce** (#550, 2026-11-15; `verify_at` PASS, mutan 39/39; rinci di arsip 2026-11-16). **Batas yang
  diterima, jangan dikutip lebih lebar:** hanya menutup cetak-lalu-keluar dan penambalan global yang ikut mengenai kenari; pemalsu
  yang terbatas pada sesi 1 atau pada tes kontrak (F1 sampai F3) atau yang membaca nonce dari argv (F6) lolos (xfail-strict di
  `tests/test_vf_canary.py`). **Aturan "jangan apply job `DONE` tanpa dibaca" tetap berlaku.** Proyek jujur dengan hook
  `pytest_report_teststatus` kustom bisa kena G4.
- [ ] **Pemalsu yang masih lolos (F1–F3, F6):** selama ini terbuka, setiap patch harus dibaca manusia, dan itu batas atas dari "bisa
  ditinggal". Belum ada spek lanjutan.
- [ ] **Gerbang contoh angka di issue = tahap T1 dari "Tahapan tanpa pusing Atha" (Inti 2)** (temuan terpenting pilot athena 2026-11-16, `pilots/research_to_issue_v0/`): tidak ada gerbang yang mencocokkan contoh angka di issue dengan kode; penulis issue salah di empat angka (entry 0,5 sebenarnya `ZeroDivisionError`; 1,5 dibulatkan ke 2; 1,2 dibulatkan ke 1 dan diblok; stop "47,0" sebenarnya 45,0) dan Claude yang menangkapnya dengan menjalankan fungsinya (lantai di-set 1,0 di memori). Batas yang dinyatakan: contoh yang hanya benar sesudah perubahan tidak bisa diverifikasi nilainya sebelum kodenya ada; gerbang tiga tingkat di bawah (T1). Jalur ketat (mengubah apa yang diterima sebagai issue).
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

- [ ] **Tahapan "tanpa pusing Atha" (perbaikan arah, bukan perubahan arah: Atha 2026-11-16 "ini masuknya perbaikan arah bukan merubah arah hehe").** Ukuran yang diperbaiki: dari "persen issue tanpa campur tangan Claude" ke dua hal yang bisa diukur: (1) **Claude sebagai operator** per job menyusut (mengetik perintah, membaca dan menyaring untuk Atha, menangkap kesalahan); dicatat per PRD di `RESULT.md` dan **dipisah dari Claude sebagai pembangun Argus** (diagnosis, perbaikan lewat jalur ketat, environment, firewall), yang tidak perlu dihilangkan; (2) **Atha menilai kartu dengan benar** (T3). Alasan: semua gerbang Argus dibuat untuk pembaca kode (draf 22 KB, patch, sha); Atha tidak membaca kode, jadi "dibaca manusia" selama ini berarti "dibaca Claude". Yang Atha setujui seharusnya contoh dan biaya dalam bahasa domain, bukan patch. **Yang tetap jujur:** contoh membuktikan perilaku, bukan bahwa kodenya bersih; pembaca patch tetap Claude (dicatat sebagai tahap, bukan manusia), atau model peninjau di dalam Argus yang harus diuji dulu dengan cacat yang ditanam (bukti lama: judge 0 dari 5 bug di review sendiri #326, uji GLM kosong). Tidak ada repo baru sampai T6 (athena tetap).
  - [ ] **T0 catatan keputusan** (ini; `docs/Reconciliation.md` bagian 7).
  - [ ] **T1 gerbang contoh** (`docs/reviews/SPEC_EXAMPLE_GATE.md`, jalur ketat; **PR 1 ter-merge (#586), PR 2 (gerbang intake, audit sesudah agent, apply/applied menolak, `--allow-failed-examples`) ter-merge 2026-11-17; PR 3 (penulis issue dan PRD: bidang `examples`/`no_examples`, alat `RunExample`, pin image, kartu chat) ter-merge dan dideploy 2026-11-17; log publik diperbaiki 2026-11-17 (PR menunggu merge: `repro`, `repro_patched`, `apply_started`, `not_confirmed` masuk `LOG_WHAT`; 45 dari 66 job di direktori CLI dan semua job chat berikutnya tadinya terbuang dari snapshot); pilot ulang Rp1 selesai 2026-11-17 (`pilots/example_gate_rp1_v0/RESULT.md`: penulis dengan `RunExample` menulis stop 45,0 yang benar, $0,0177; tiga angka salah tulisan tangan diblok di intake dengan nilai asli, $0; n=1, audit sesudah agent belum diuji pada kasus ini)**): issue membawa contoh yang bisa dijalankan; tiga tingkat: (A) contoh "tidak berubah" dijalankan di commit dasar sekarang; (B) contoh "kalau konstanta X diubah" dijalankan di commit dasar lewat alat `RunExample` yang dipegang penulis di gilirannya (penimpaan konstanta tingkat modul, sandbox, tanpa jaringan); (C) contoh "sesudah perubahan" diaudit pada kode akhir oleh harness, **terpisah dari tes drafter** (drafter bisa melemahkan tes tanpa ketahuan). Batas: contoh tingkat C yang salah baru ketahuan sesudah agent jalan. Keluar bila: empat angka salah issue Rp1 terlihat salah oleh penulis di gilirannya (tingkat B) atau ditandai oleh audit (tingkat C), tidak ada yang lolos diam-diam; mutan; `verify_at`. Data kartu (contoh, nilai hasil jalan, status tiap contoh) terstruktur supaya T2 bisa menampilkannya.
  - [x] **T2 kartu baca-saja di chat** (selesai dan dideploy 2026-11-17, `docs/reviews/SPEC_CHAT_CARDS.md` rev 1, `router/cards.py`; batas: kunci yang disusun lewat kode tidak terlihat mesin, hanya yang terpecah sebagai teks; JS tanpa tes runtime, hanya cek sintaks node dan tes statis) (PRD, antrean, contoh dengan status mesin; hanya status, tanpa tombol): contoh di kartu diambil dari hasil jalan mesin, bukan parafrase model (kalimat bahasa biasa dari penulis ditandai "ditulis model").
  - [ ] **T3 uji kartu cacat-ditanam** (**diubah bentuknya 2026-11-17 setelah Atha masih pusing membaca kartu T2: kartu persetujuan dalam bahasa biasa, `docs/reviews/SPEC_KARTU_SETUJU.md` rev 1, Opus GO WITH FIXES, menunggu persetujuan Atha atas D1-D6; kartu dibangun dulu, lalu ujinya 5 baik + 5 cacat diacak**; teks lama di bawah): 5 kartu buruk ditanam (contoh salah, biaya melonjak, tujuan menyimpang, dan sejenisnya) di antara kartu baik; lulus bila Atha menolak 4 dari 5 dari HP; catat juga kartu baik yang salah ditolak. Gagal = kartu dirancang ulang, tombol approve dari HP tetap ditahan (aturan lama rencana Fable 2026-11-11).
  - [ ] **T4 kartu aksi** (`prd approve`, `queue go`, approve draf, apply) di chat: hanya sesudah T3 lulus.
  - [ ] **T5 penyambung satu-prompt** (research -> penulis PRD -> antrean), gerbangnya adalah kartu T2/T4 (lihat Parkiran "Penyambung satu-prompt").
  - [ ] **T6** `argus env init`, environment node, repo baru (lihat Parkiran).
  Menggantikan butir "Uji lepas tangan" di bawah (diganti T3).
- [ ] **Uji lepas tangan — DITUNDA dan digantikan oleh T3 di atas (Atha 2026-11-16: "terlalu berat, apalagi buat gw yang ga paham teknis"; dua PRD pilot lanjut dengan aturan biasa, Claude membaca dan meringkas).** Alasan beratnya, supaya tidak diulang: satu draf mentah 22 KB dan satu patch 14 KB per issue (pilot Rp1), sekitar 46 menit untuk 3 issue dengan ringkasan Claude (pilot antrean ledger), kira-kira 2-3 jam membaca mentah di HP untuk dua PRD, dan angkanya hanya sah kalau Atha benar-benar membaca. Dibuka lagi bila ada cara membaca yang ringan di HP (tampilan potongan dengan aturan tetap, atau tampilan chat untuk PRD) dan Atha mau. Sementara itu, pada pilot biasa Claude mencatat **koreksi Claude** (apa yang Claude tangkap atau perbaiki di issue, draf, patch) di `RESULT.md` pilotnya sebagai ukuran kasar, bukan sebagai angka "tanpa campur tangan". Isi usul semula (usul Claude 2026-11-16; Atha meminta promptnya, `docs/reviews/PROMPT_HANDSOFF_PILOT_2026-11-16.md`): dua
  PRD pilot yang tersisa (rencana tiga, satu selesai) dijalankan dengan Atha menulis keinginannya (cukup besar untuk beberapa issue
  berurutan) dan Atha sendiri yang membaca dan memutuskan `approve` dan `apply`; Claude hanya menjadi tangan (mengetik perintah yang
  Atha sebut, menampilkan draf atau patch tanpa komentar) dan tidak membaca, menilai, menyarankan atau memperbaiki lebih dulu; tiap
  kali Atha meminta penilaian atau perbaikan, itu dicatat sebagai satu campur tangan beserta alasannya. Keluaran: jumlah campur tangan Claude per issue, menit
  Atha per gerbang, dan apakah aturan urutan antar-issue (`creates` sebelum `touches`) jalan di kasus nyata. Sesudahnya Claude membaca
  semua patch (aturan "jangan apply tanpa dibaca" tetap dipenuhi oleh Atha saat uji; pembacaan Claude adalah pembanding, dicatat
  terpisah).
- [x] **`argus apply`** (#552, #553, 2026-11-15; `router/apply.py`; `verify_at` PASS, mutan 40/40; rinci di arsip 2026-11-16).
  **Batas yang diterima:** `--read-sha` hanya membuktikan seseorang menyalin sha yang `status` cetak, bukan bahwa patch dibaca; repo
  target dan `.git`-nya dianggap tepercaya; kunci per repo bergantung pada `jobs_dir` yang sama; `core.excludesFile` global membuat
  berkas ter-ignore terbaca "tree kotor" (aman, membingungkan).
  - [ ] kartu apply di chat (K6); `argus applied --amend <commit>` hanya untuk `APPLIED` yang belum di-deploy (kasus viewer 021)
- [~] **"PRD sampai staging"** (Atha 2026-11-12): antrean, tahap PRD dan penulis PRD ter-merge; rinci, keputusan dan batas di arsip
  2026-11-16.
  - [x] **Bagian A, antrean** (#555, `router/queue.py`, `SPEC_PRD_QUEUE.md` rev 2): satu repo, daftar issue tetap, berhenti di
    kegagalan pertama, batas uang per antrean, tidak pernah memanggil `approve` atau `apply`. Pilot v0 (`pilots/queue_pilot_v0/`,
    n = 1): tiga issue ledger `APPLIED`, $0,1092, live sebagai Stage 19.
  - [x] **Bagian B1, tahap PRD** (#559, `SPEC_PRD_STAGE.md` rev 1): `argus prd check` (baca saja) dan `argus prd approve --sha`.
    **Batas:** hanya jalur dan field yang ditulis atau terlihat di teks; jalur yang disusun dari potongan, ditulis `/API/`, `%2F`
    atau `get /x` lolos.
  - [x] **Bagian B2, penulis PRD** (#566, #568, `SPEC_PRD_WRITER.md` rev 1): `argus prd new|reply` (Haiku 5.5).
  - [~] **Pilot di repo luar `athena`** (2026-11-16, n = 1 tiap satu, dipisah dari angka papan skor): antrean 3 issue `APPLIED`,
    $0,1297 (`pilots/queue_pilot_athena/RESULT.md`); penulis PRD pertama, 1 issue `APPLIED`, $0,0527 (`pilots/prd_writer_v0/`);
    research → issue → kode dengan tangan, $0,2252 (`pilots/research_to_issue_v0/`). **Yang tidak ditunjukkan:** aturan urutan
    antar-issue belum pernah jalan di kasus nyata (PRD satu item); keinginan awal ditulis Claude, bukan Atha; di semua pilot Claude
    menjalankan perintah dan membaca PRD, draf dan patch; perilaku saat item gagal; mutu Haiku terhadap tulisan Claude (n kecil,
    pembanding tanpa `issue_gate`); frontend athena (tanpa node; `ScanResultCard.jsx` masih menulis Rp50).
  - [ ] dua PRD pilot lagi: lihat "Uji lepas tangan" di atas
  - [ ] tes CLI `queue new` dan `queue step` dengan konfigurasi sungguhan
  - [ ] lima commit athena belum di-push (`649e0c5`, `08700e9`, `dc98df1`, `c82cd47`, `705db5b`); mencatat kenapa venv Argus tanpa
    `fastapi` (tes ledger dijalankan di image sandbox)
  - [ ] kegagalan provider pada job `prd` berakhir `BLOCKED` terminal (lihat parkiran): usulnya dikerjakan sebelum pilot berikutnya
- [x] **Ketergantungan tersembunyi ketiga dan keempat (Stage 19 `/api/scoreboard/models`, Stage 20 `/api/budget/jobs`): ditutup 2026-11-16.** Proxy meneruskan kedua jalur (`SPEC_PROXY_LEDGER_PATHS`, #580; go live jalan A, `pilots/staging_proxy_paths/steps.md`: 200 lewat 8710, `?week=` dan `?kind=` tetap 404 karena proxy tidak meneruskan query). **Sisa:** tidak ada halaman viewer yang memakai keduanya (JSON mentah di peramban lewat SSH forward); filter minggu tidak bisa lewat proxy (butuh aturan query sendiri dan spek); `~/pilot3a_live` tertinggal 36 commit dari `main` dengan **satu berkas bertahap** (`router/stage_viewer.py`, sama dengan `e2ee6c0`) dan `argus-chat` di 8711 masih menjalankan kode lama (jalan A: pembaruan penuh dan restart chat belum diputuskan). **`~/argus-ledger` tidak punya remote** (push tidak mungkin; repo hanya lokal), dan commit `0780f1e`, `e008f98` hanya ada di sana.

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
- [ ] **Catat pelaku approve dan apply** (usul Claude 2026-11-16): `method=apply` mencatat bahwa perintahnya dipakai, bukan siapa yang
  mengetik; selama `by` = `$USER`, angka utama tidak bisa memisahkan Atha dari Claude. Usul: penanda pelaku yang dinyatakan saat
  perintah dijalankan (bukan ditebak), dicatat di `job.json` dan dibaca papan skor. Menyentuh `job.json` dan jalur approve: jalur
  ketat, belum dispek. Sampai ada, uji lepas tangan mencatat pelaku dengan tangan di `RESULT.md`-nya.
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

- [~] **Riset (`argus research`): pekerjaan baru tidak dimulai** (tidak ada di urutan inti yang diterima Atha 2026-11-15; dibahas lagi paling cepat di titik cek 2026-11-29; satu job dan satu pilot dijalankan 2026-11-16, lihat "Keputusan Atha yang ditunggu"); tetap tersedia sebagai mode di chat (C3) dan sebagai tahap opsional
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

- **`argus env init <repo>`** (Atha 2026-11-15, "#1 masuk parkiran"): satu perintah tanpa model yang membuat environment sandbox untuk repo luar: membaca dependensi repo, memilih versi yang lebih tua dari dua minggu, mengambil hash dari wheel di image dasar, membangun dan
  mengecek image, menjalankan tes baseline di sandbox dan melaporkan yang gagal di-import. Latar: `athena_py312` dibuat dengan tangan dalam sekitar 10 langkah (resolve, tanggal PyPI, unduh, hash, build, cek, baseline; dua dependensi tersembunyi, `yfinance` dan `tzdata`, baru
  ketahuan dari baseline). Tempatnya terhadap arah: membuat "bisa ditinggal" berlaku untuk repo luar tanpa melonggarkan sandbox tanpa jaringan dan pin berhash (dua pilihan lain, satu image gemuk dan install saat job jalan, ditolak). Bukan pengganti pekerjaan berjalan; dibahas
  di titik cek 2026-11-29 dengan angka pembanding (waktu membuat `ledger_py312` dan `athena_py312` dengan tangan).
- **Gerbang lint, type-check dan impor-bersih per repo** (Atha 2026-11-15, dari video pendek "tiap agent push kode ada lima hal yang dicek": lint, type-check, test, build tanpa DB dan env, schema = migration): Argus sudah punya cek 3 (tes, lebih ketat) dan sebagian cek 4 (sandbox tanpa jaringan dan tanpa kredensial), tidak punya cek 1 dan 2 (grep kode: nol `ruff`, `mypy`, `eslint`, `tsc` di gerbang),
  cek 5 tidak relevan (tidak ada repo dengan DB). Usulan: gerbang yang menolak, tanpa model, opt-in lewat konfigurasi repo (`ruff`, `mypy`, `eslint` hanya bila repo punya konfigurasinya; athena dan ledger belum), plus "impor modul utama dengan environment kosong" untuk cek 4.
  `docs/reviews/ACCEPTANCE_GENERAL.md:56` sudah memperbolehkan "tes, build, lint, atau skrip cek" sebagai perintah validasi di kontrak, tetapi drafter hanya menulis pytest dan vitest. Tempatnya terhadap arah: inti ("kerja terbukti"). Dibahas di titik cek 2026-11-29 bersama `argus env init` (keduanya: repo luar tanpa kerja tangan).
- **Environment node untuk repo dengan frontend** (Atha 2026-11-16, setelah pilot athena): sandbox hanya punya Python, jadi issue yang mengubah `frontend/` tidak bisa divalidasi (athena punya `package-lock.json`, `vitest`, `oxlint`, `vite build`; `node_modules` tidak ada). Pilot athena membatasi issue 3 ke backend karena itu. Usulan: environment terpisah atau gabungan dengan node, paket dari lockfile, tanpa jaringan saat jalan, image dikunci digest, `check_env_image.py`; dibuat saat ada issue frontend nyata (mis. tampilan time-stop di tab Journal), bukan sebelumnya. Satu keluarga dengan `argus env init` dan gerbang lint.
- **Kegagalan provider pada job `prd`** (Atha 2026-11-16, "catet dulu"): saat ini `BLOCKED` terminal (tabel `LEGAL`, sama dengan job `issue`), jadi provider yang sempat gagal mematikan percakapan dan uang yang sudah dibayar. Usul: petakan `llm_failed` ke `WRITE_FAILED` (bisa di-`reply`) di `run_prd_writer`, satu baris, tanpa mengubah `LEGAL`; `BLOCKED` tetap untuk uang, keadaan repo dan salinan snapshot. Alternatif yang ditolak: `BLOCKED -> WRITING` (mengaburkan arti BLOCKED). Dikerjakan sebelum atau sesudah pilot pertama sesuai hasilnya.
- **Penyambung satu-prompt: research → penulis PRD/issue → antrean** (Atha 2026-11-16: "sekali nulis prompt langsung bisa semua kerja"): sekarang tiap langkah satu perintah (`research`, `issue new` atau `prd new`, `prd approve`, `queue go`, `queue step`, `approve`, `apply`). Usulan: satu perintah penyambung yang menjalankan urutannya dan berhenti hanya di gerbang manusia: (1) sesudah research, "pakai laporan ini?" (isi laporan dari web tidak tepercaya; pilot research 2026-11-16 punya dua sumber yang bertentangan), (2) approve PRD dan uang, (3) approve tiap draf, (4) apply tiap patch; tiap gerbang satu ketukan di chat dengan notifikasi, bukan satu perintah. Yang otomatis: laporan jadi pesan pertama penulis, `prd check`, antrean `PENDING`, `queue step`. Gerbang manusia tidak dihapus ("jangan apply job tanpa dibaca"). Belum diketahui: kualitas penulis PRD untuk pekerjaan besar (data baru satu PRD satu issue, $0,0527), biaya dan titik macet satu rantai penuh, tampilan chat (8711; catatan asli menulis 8712, port pembangunan yang sudah mati) untuk PRD dan research. Tempatnya terhadap arah: kelanjutan langsung "bisa ditinggal", bukan arah baru; spek ditulis sesudah perubahan Rp1 (jalur issue biasa) mengukur satu rantai nyata, dengan angka dari pilot research, PRD, dan athena.
- **PRD untuk repo dari nol** (Atha 2026-11-17, "catat dulu di parkiran"): penulis PRD sekarang tidak bisa memulai repo kosong; ini bagian dari T6, spek penuhnya ditulis sesudah T3 (kita lalu tahu apakah Atha bisa menilai PRD dari HP). Yang dibutuhkan menurut gerbang yang ada: (1) `touches` tiap item harus teks yang ada di kode hari ini atau yang dibuat item sebelumnya lewat `creates`, jadi item pertama di repo kosong tidak punya apa pun untuk disentuh dan ditolak; (2) repo terdaftar di `issue_writer.repos` (config, jalur ketat) dengan environment sandbox yang imejnya sudah dibangun dan lulus `check_env_image.py` (sekarang hanya athena, ledger, viewer; imejnya dibangun dengan tangan, lihat `argus env init` di atas); (3) pin `.sandbox_image_<env>*` ada di checkout yang melayani chat (git-ignored; ditemukan 2026-11-17 hilang di `pilot3a_live`, disalin dari checkout lain); (4) tes lama untuk cek bentrok dan commit dasar yang punya satu tes yang lulus; (5) kerangka minimal sebagai titik awal: satu paket, satu fungsi, satu tes yang lulus, `pyproject`/`package.json` dan `.argus/protected` bila environment mensyaratkan. Jalan pintas sebelum T6: Atha atau satu job biasa membuat kerangka itu, repo didaftarkan, environment dibangun dengan tangan, lalu PRD mengerjakan fitur-fiturnya. Tempatnya terhadap arah: Inti 2 (T6), bukan inti kerja terbukti; tidak dikerjakan sebelum T3 selesai.
- **Gerbang contoh angka di issue:** dipindah ke tahap T1 (lihat "Tahapan tanpa pusing Atha" di Inti 2); catatan awal Atha 2026-11-16 "no.2 catat di parkiran".

## Log permintaan yang chat belum bisa

Satu baris per permintaan: tanggal, apa yang diminta, kenapa chat belum bisa. Kemampuan permukaan berikutnya dipilih dari sini di
titik cek.

- (kosong)

## Pekerjaan operasional (Atha, di luar repo)

- [ ] **Periksa ulang aturan ARB/ARA BEI pada 2 Januari 2027** (research 2026-11-16, `jobs/j20261116_081333_0a18/REPORT.md`): ARB 7% (dan Rp11-14 jadi Rp1) hanya berlaku sampai 31 Desember 2026 menurut OJK; apa yang berlaku mulai 2027 tidak jelas (satu judul Katadata menyebut ARB 35%). `DEFAULT_SLIPPAGE_BUFFER_PCT = 0.15` di athena sengaja tidak diubah sampai itu jelas. Sumber primer (idx.co.id) belum ditemukan; semua angka masih dari media dan sekuritas.
- [ ] **Firewall mesin ini, port 443 (2026-11-16):** `/etc/iptables/rules.v4` kini memuat `ACCEPT tcp 443` (sebelumnya tidak ada; backend athena tidak terjangkau dari luar sampai itu dibuka, PWA memberi `no-response`). Cadangan berkas lama: `/tmp/claude-1001/rules.v4.bak-20261116` (hilang bila /tmp dibersihkan; **pindahkan ke tempat yang awet**). Belum diuji lewat boot ulang; security list di konsol Oracle tidak diperiksa.

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
