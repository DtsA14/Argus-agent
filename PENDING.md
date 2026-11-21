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

- [x] **GATE-10** (**Atha 2026-11-21: biarkan** — tidak diperbaiki sampai mengganggu pekerjaan nyata; tidak darurat, 2026-11-14): P1 memindai tes yang ditulis agen sendiri dengan pola deteksi, sehingga tes jujur yang
  menyebut `sys.modules` dan `pytest` berakhir `FAILED_ACCEPTANCE` tanpa retry. Usul Opus: persempit sedikit (sekitar 15 baris,
  jalur ketat). Risiko kecil; ditunda (arsip, butir "Fase 3 dan batch kedua").
- [x] **Probe aplikasi dari nol** (**Atha 2026-11-21: tutup** — sebagian terjawab oleh pilot ledger-cli; proyek baru nyata Atha kelak jadi probenya) (`docs/reviews/FABLE_GREENFIELD_PROBE_PROPOSAL.md`): aplikasinya dan "ok"; saran Fable dan Claude:
  sesudah eksperimen repo luar.
- [x] **Riset 2026-11-16 terhadap aturan "pekerjaan riset baru tidak dimulai"** (**Atha 2026-11-21: pengecualian**, bukan jatah hari eksplorasi): satu job riset (aturan ARB/ARA BEI) dan pilot
  research → issue → kode dijalankan 2026-11-16. Tidak tercatat apakah itu jatah hari eksplorasi (1 hari per minggu) atau pengecualian;
  Atha yang menentukan, supaya aturan main arah tetap bisa dipegang.
- [x] **Port 443 mesin ini dibuka ke luar untuk backend athena** (**Atha 2026-11-21: tutup lagi; dilakukan Claude hari itu**, lihat "Pekerjaan operasional") (2026-11-16, lihat "Pekerjaan operasional"): catatan Claude: ini
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
- [x] **(SUDAH DIBANGUN, lihat butir T1 di bawah: #586, #587, #588, pilot Rp1 2026-11-17; teks di bawah adalah temuan awalnya, bukan keadaan sekarang)** Gerbang contoh angka di issue = tahap T1 dari "Tahapan tanpa pusing Atha" (Inti 2)** (temuan terpenting pilot athena 2026-11-16, `pilots/research_to_issue_v0/`): tidak ada gerbang yang mencocokkan contoh angka di issue dengan kode; penulis issue salah di empat angka (entry 0,5 sebenarnya `ZeroDivisionError`; 1,5 dibulatkan ke 2; 1,2 dibulatkan ke 1 dan diblok; stop "47,0" sebenarnya 45,0) dan Claude yang menangkapnya dengan menjalankan fungsinya (lantai di-set 1,0 di memori). Batas yang dinyatakan: contoh yang hanya benar sesudah perubahan tidak bisa diverifikasi nilainya sebelum kodenya ada; gerbang tiga tingkat di bawah (T1). Jalur ketat (mengubah apa yang diterima sebagai issue).
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
  - [ ] **T3 uji kartu cacat-ditanam** (**diubah bentuknya 2026-11-17 setelah Atha masih pusing membaca kartu T2: kartu persetujuan dalam bahasa biasa, `docs/reviews/SPEC_KARTU_SETUJU.md` rev 1, Opus GO WITH FIXES, D1-D6 disetujui Atha 2026-11-17; kartu dibangun dulu, lalu ujinya 5 baik + 5 cacat diacak**; teks lama di bawah): 5 kartu buruk ditanam (contoh salah, biaya melonjak, tujuan menyimpang, dan sejenisnya) di antara kartu baik; lulus bila Atha menolak 4 dari 5 dari HP; catat juga kartu baik yang salah ditolak. Gagal = kartu dirancang ulang, tombol approve dari HP tetap ditahan (aturan lama rencana Fable 2026-11-11).
  - [~] **T4 kartu aksi** (`prd approve`, `queue go`, approve draf, apply) di chat: **T4a dibangun 2026-11-21** (lihat "Pilot bulking-app dan kemampuan Argus"): `prd_approve` dan `queue_go`; T3 dilewati (versi ringan 4 dari 6, Atha memutuskan lanjut). **Sisa:** `queue_go` hanya placeholder di halaman (Atha); `queue step`, approve draf dan apply dari chat (T4b) ditahan sampai kartu pasang membuat tanda mesin tidak bisa terlewat dan tombol mati secara mekanis.
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

- **Mandor di chat: ngobrol, usulan rute, kartu langkah berikutnya** (Atha 2026-11-21, "chat pengen bisa diajak brainstorming dan mengorkestrasi ... seperti proyek manajer/mandor"; **diparkir sampai titik cek 2026-11-29**, Atha: "gw mencoba komitmen"). Spek `docs/reviews/SPEC_CHAT_MANAGER.md` rev 1 (tinjau Opus GO WITH CHANGES, 17 amandemen), enam PR jalur ketat; yang sudah dibangun dari spek ini: **P2a** (`prd_new` dari chat diketik manusia, `prd new --via ui`, PRD dihitung di batas harian, dispatch `execute` eksplisit). Tempatnya terhadap arah: permukaan (chat), kemampuan baru. Prasyarat yang dicatat tinjau: PRD dan sesi mandor masuk batas harian (P2a menutup yang PRD), satu sesi = satu job dengan batas tetap dan TTL, `why` model tidak masuk kartu konfirmasi, uji rute `route_eval_v0` memilih model sebelum dibangun, amandemen tertulis atas SPEC_CHAT_APP 11.5 (jatah sesi). Pemicu buka: setelah P2a dan pilot bulking-app dipakai, ada kesulitan nyata yang mandor selesaikan (mis. memilih rute dan menyusun permintaan dengan tangan berulang).
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
- **Screenshot sebelum dan sesudah untuk perubahan UI** (Atha 2026-11-17, "untuk UI kayaknya enak kalo ada gambar"): kartu angka tidak cocok untuk repo UI (viewer, `frontend/` athena), dan Atha tidak menilai domain athena dan tidak mau menghitung; yang bisa ia nilai dengan mata adalah gambar. Usulan: sandbox tanpa jaringan merender halaman di browser tanpa kepala pada commit dasar dan pada kode akhir, dan kartu pasang menampilkan dua gambar berdampingan, ditandai keluaran mesin. Butuh environment node (lihat "Environment node untuk repo dengan frontend") dan browser tanpa kepala di image; gambar itu data tak tepercaya dan tidak boleh memuat teks halaman sebagai instruksi. Tempatnya terhadap arah: "kerja terbukti" untuk repo UI. Dibahas di titik cek 2026-11-29 bersama environment node; sampai itu, kartu viewer hanya punya tujuan, biaya, daftar file dan tes.
- **Pembagian penilaian kartu T3** (Atha 2026-11-17, "gw kurang ngerti domain athena dan males hitung-hitungan"): disetujui Atha 2026-11-17 ("Ok setuju bro"), spek rev 2: Atha menilai tujuan, biaya dan cakupan; pembaca Claude (Opus, hanya-baca, tercatat sebagai tahap Claude) menilai angka domain; mesin memeriksa kode memberi angka itu. Uji 5+5 lalu menguji Atha pada cacat tujuan/biaya/cakupan dan pembaca Claude pada angka domain yang ditanam. SPEC_KARTU_SETUJU rev 2 (D7), tinjauan Opus GO WITH FIXES diterapkan; menunggu kata Atha untuk merge spek.
- **Status T3 (2026-11-18)**: dibangun dan live: kartu rencana, kartu pasang (`GET /api/approve/code/<job>`, syarat a-i, tanda cakupan mesin, dua pembaca berlabel), `argus apply` menolak tanpa catatan pembaca patch dan (untuk item antrean PRD) tanpa catatan pembaca angka. **Belum**: T3a (Atha menilai 6 cacat + 6 baik; logistik tampilan belum diputuskan: 12 kartu di instansi chat terpisah, kartu pasang terjangkau lewat item antrean REVIEW_READY), T3b lengkap, tombol T4.
  - **T3b hasil (smoke test, bukan tingkat kesalahan)**: `scripts/t3b_fixtures.py` (16 set: 8 cacat ditanam, 8 baik; kunci di balik hash di `<root>.key`) dan `argus t3b-run` (pembaca = model Argus lewat `LLMCaller`, batas total sendiri). Putaran Sonnet (subagen, templat lama): 8/8 cacat tertangkap di dua bacaan, tetapi 4/8 set baik ditandai (format angka "1.000" ambigu, g4 bukan set baik yang bersih, keluhan di luar tugas); setelah itu templat dapat aturan 6 (gaya angka Indonesia) dan 7 (hanya angka dan aturannya), g4 diperbaiki. Putaran GLM-5.3 (templat baru, set baru, hash kunci `e65f7c5b9e7c01df37b9430fa2efd92322820fa65b65529b5bde172f1495e6c0`): 8/8 cacat tertangkap di dua bacaan dengan alasan yang benar, 0/8 set baik ditandai; dua bacaan awal terpotong di batas keluaran (GLM berpikir) dan diulang dengan batas 8000. Biaya: $0,477 menurut ledger (batas atas), $0,215 tagihan gateway (Novita fp8, diskon 55% masih berlaku 2026-11-18). **Belum lulus resmi**: dua set riwayat nyata (kasus Rp1; perbaikan bug di `git log` athena) belum ada, jadi `score` mencetak INCOMPLETE; `verification/reader_tests.json` belum ditulis, jadi kartu tetap menulis "pembaca belum diuji". Catatan: uji ini menilai model, bukan kartu: pembaca kartu tetap sesi Claude (spek rev 2); pakai model Argus sebagai pembaca kartu = spek rev 3 + keputusan Atha (D8). Sonnet belum diulang dengan templat baru. `reader_tests.json` perlu mencatat modelnya (hasil uji berlaku per model).
- **Antrian kerja T3 (Atha 2026-11-18, "A dan B setelah masuk antrian kerjaan"; dikerjakan sesudah pekerjaan yang sedang jalan, bukan sekarang)**:
  - [ ] **Dua set riwayat nyata untuk T3b** (syarat spek bagian 8 supaya `score` bisa resmi dan `verification/reader_tests.json` boleh ditulis; Atha menyetujui pilihannya): **A** lantai harga Rp50 yang kedaluwarsa: permintaan Atha asli 16 November ("harga minimum sekarang Rp1, ubah semua yang mengira Rp50", `pilots/example_gate_rp1_v0/message.txt`), dokumen athena `CLAUDE.md` pada commit `c82cd47` yang masih menulis "price floor Rp50", contoh cacat "harga 50 diblokir"; jawaban benar pembaca `concerns`. **B** buffer ARB yang basi: permintaan "pakai ARB sesuai aturan BEI sekarang, 7% untuk harga di atas Rp10 (19 Okt-31 Des 2026, Kep-00157/BEI/10-2026)", dokumen mengutip keputusan itu, contoh memakai 15% (nilai default athena `DEFAULT_SLIPPAGE_BUFFER_PCT`, dari Kep-00003/BEI/04-2025); jawaban benar `concerns`, angka seharusnya 7%. Cadangan: kejadian Agustus, buffer 20% (tebakan) jadi 15% (commit `34f633b`). Angka di contoh dihitung dari kode athena sungguhan pada commit itu, bukan dikarang. Setelah masuk: bangun ulang folder, 4 bacaan tambahan dengan thinking bawaan (±$0,03), lalu `score` resmi.
  - [ ] **C (catatan, bukan set uji)**: aturan jarak stop (1,5x ATR dikali penyesuaian, pembulatan tick) hanya ada di kode athena, tidak di dokumen mana pun; di pilot Rp1 pertama penulis menulis "stop 47,0" padahal kode memberi 45,0 dan "1,5 jadi 1.000.000 lembar" padahal 1.304.300; mesin menangkapnya karena menjalankan kode. Pembaca tanpa kode hanya bisa bilang "aturan tidak tertulis" (dan itu juga untuk angka yang benar): sebagian aturan angka tidak terjangkau pembaca sama sekali.
  - [ ] **Temuan untuk athena (butuh kata Atha, jalur issue/PRD sendiri)**: `DEFAULT_SLIPPAGE_BUFFER_PCT = 0.15` basi untuk saham di atas Rp10: ARB 7% asimetris 19 Okt-31 Des 2026 (Kep-00157/BEI/10-2026), Rp11-Rp14 ARB Rp1 (Kep-00158/BEI/10-2026, 20 Okt), dievaluasi lagi sesudah 31 Des; sumber berita (bisnis.com, ajaib.co.id), dokumen SK aslinya belum dibaca. Perlu juga diputuskan: konstanta yang berlaku sementara.
  - [x] **Perbandingan effort GLM-5.3 sebagai pembaca angka (2026-11-18)**: thinking bawaan 8/8 cacat tertangkap dan 0/8 set baik dialarmi, token berpikir rata-rata 2.794, biaya ledger $0,477 untuk 32 bacaan; `--effort medium` rata-rata 55 token berpikir (praktis tanpa berpikir), $0,075, 1 luputan nyata (salah hitung 10.000.000-3.000.000=6.000.000, dijawab `ok`) dan dua catatan benar tanpa angka yang seharusnya: FAIL. Keputusan: pembaca memakai thinking bawaan, tidak diturunkan; hasil uji berlaku per model dan per effort (catat di `reader_tests.json`).
- **Hasil T3b resmi, putaran 1 dan 2 (2026-11-18; Atha: "catat dulu aja jangan uji ulang")**: 20 set (10 cacat, 10 baik; 2 cacat dan 2 baik dari riwayat nyata athena), GLM-5.3 `--effort high`, dua bacaan per set. **Putaran 1** (hash kunci `1eda75d2...728c`, tanpa DOMAIN.md): 10/10 cacat tertangkap di dua bacaan (A lantai Rp50 basi dan B buffer ARB 15% yang kini 7% termasuk), tetapi 2/10 set baik dialarmi (g9, g10: rumus stop dan ukuran posisi tidak tertulis di dokumen mana pun, jadi pembaca benar menurut aturan 4) = FAIL. **Putaran 2** (hash `d9b998fa...9d97`, dengan draf `DOMAIN.md` athena, set dan contoh sama; perubahan dibuat setelah melihat putaran 1): 0/10 set baik dialarmi, 9/10 cacat tertangkap di dua bacaan, satu luput nyata: d6 (sisa batas) dijawab `ok` di bacaan ke-2 karena salah hitung "10.000.000 - 3.000.000 = 6.000.000" = FAIL. Gabungan semua bacaan `high` (3 uji): 56 bacaan cacat, 1 luput (1,8%), 56 bacaan baik dengan DOMAIN.md: 0 alarm. Biaya: $0,170 + $0,136 (ledger, batas atas; tagihan gateway sekitar separuhnya). `reader_tests.json` TIDAK ditulis: kartu tetap menulis "pembaca belum diuji". Tidak diuji ulang atas permintaan Atha.
- **T3b putaran 3, aturan rev 3 (2026-11-18, resmi, set segar, hash kunci `924ad977...ad1b` dicatat sebelum bacaan)**: GLM-5.3 `--effort high`, dua bacaan per set, 20 set, biaya ledger $0,199 (batas atas). **FAIL** menurut aturan yang ditetapkan sebelumnya: (a) d6 (sisa batas) dijawab `ok` di KEDUA bacaan, keduanya dengan hitungan salah yang sama ("10.000.000 - 3.000.000 = 6.000.000"); (b) 2 dari 18 bacaan cacat luput; h2 bacaan ke-2 tidak tercatat karena jalur menolak sumber yang diberi keterangan tambahan di dalam tanda kurung ("dokumen repo: DOMAIN.md (rumus ...)"), bukan karena salah baca; (c) 1 set baik dialarmi (g5, satu bacaan), dalam batas; (d) set riwayat nyata lengkap. Temuan penting: kesalahan hitung itu **konsisten, bukan acak**: tiga dari tiga putaran `high` salah pada set d6 dengan angka yang sama, jadi dua bacaan GLM tidak independen untuk kesalahan ini dan perkiraan 0,03% dari dua bacaan tidak berlaku. `reader_tests.json` TIDAK ditulis. Tidak diuji ulang. Dua bacaan oleh model yang sama menangkap alarm palsu dan luput acak, bukan kelemahan sistematis; untuk itu perlu pembaca berbeda (Claude) atau hitungan oleh mesin.
  - [ ] **Setelah putaran 3**: (1) jalur `examples-read` dan `t3b-run` sebaiknya memotong keterangan dalam tanda kurung dari sumber (atau pembaca diberi tahu bentuk persis); (2) pilihan Atha: pembaca kartu = Claude (spek rev 2/3 apa adanya) dan uji T3b dengan pembaca Claude, atau GLM dengan penghitung mesin untuk aritmetika contoh (mesin sudah punya angka `expect` dan hasil kode; "sisa" adalah selisih yang bisa dihitung kode).
- **Pembaca patch = pasangan model Argus, lulus uji (2026-11-18; Atha: "Ok deepseek aja", "Ok gass bro")**: `argus patch-read-run <job>` (Hy4 Flash lalu, bila `ok`, DeepSeek V4.1 Flash 1017; `ok` butuh dua bacaan dua id; spek 13.5, PR #624, templat #626). Uji `router/patch_trial.py` (31 kasus: 17 cacat, 14 baik): putaran resmi 1 FAIL (c) (y1 dan g4 cacat bahan uji), putaran 2 FAIL (a)(b) (x1, tes tanpa import, lolos semua bacaan), probe di luar putaran (aturan 2(f) menutup x1; Hy4 penuh tidak lebih baik, 39x biaya), **putaran 3 PASS** (hash kunci `971ca88f...`, templat `05ce799f...`): (a) semua cacat tertangkap, (b) 0 dari 34 putaran cacat `ok`, (c) 0 kasus baik dialarmi, (d) 1 dari 124 balasan tidak terpakai, (e) semua bacaan sah. Biaya seluruh uji pembaca patch sekitar $0,5. `verification/reader_tests.json` ditulis untuk `athena` (bahan: `verification/patch_pair_trial_2026-11-18.md`): kartu pasang menulis "pembaca patch sudah diuji" hanya bila dua pembaca kartu persis pasangan itu dan hash templat dan instruksi sama. Batas jujur: kasus ditulis Claude; Hy4 Flash sendirian meloloskan x1 dua kali dan x6 sekali di putaran ini, jadi lulusnya bersandar pada DeepSeek sebagai bacaan kedua, yang satu keluarga dengan penulis patch Argus (DeepSeek V4.1 Flash); lulus adalah uji asap. Pembaca angka domain TETAP belum teruji (T3b gagal tiga putaran). Arah dari sini (Atha: "langkahnya udah kayak mau bikin app skala enterprise"): berhenti membangun infrastruktur uji pembaca; berikutnya T3a (Atha menilai 12 kartu); validasi lebih jujur dari kasus buatan = catat kecocokan catatan pembaca dengan hasil job nyata (patch dibatalkan, dikembalikan, terbukti salah). Kelalaian tercatat: `#622` dan `#624` di-merge pada vonis `verify_at` prematur (baris RESULT pertama, PASS; baris terakhir FAIL karena pin image sandbox tidak ada di worktree baru); ditutup oleh `verify_at` bersih untuk #625 dan #626 (6.369 dan 6.370 lulus, 0 sandbox dilewati).
  - [ ] **Spek rev 3 (butuh keputusan Atha)**: (1) `ok` pembaca angka hanya dihitung bila **dua bacaan independen sama-sama `ok`**, satu `concerns` menutup kartu (tingkat luput 1,8% per bacaan menjadi sekitar 0,03% untuk dua bacaan yang sama-sama luput; biaya dua kali $0,003-0,007 per item). (2) Aturan lulus uji T3b untuk model stokastik: bukan "semua cacat di kedua bacaan" melainkan misalnya "tiap cacat tertangkap minimal satu bacaan dan tingkat luput <= 5%", ditetapkan SEBELUM uji berikutnya. (3) Pembaca dari model Argus (GLM) = keputusan D8 (spek rev 3 + hasil uji per model dan per effort di `reader_tests.json`).
  - [ ] **`DOMAIN.md` athena ke repo athena (butuh kata Atha dan tinjauannya)**: draf ada di `verification/t3b_history/athena/DOMAIN.md` (ditulis Claude dari kode, angka dicocokkan dengan kode; CLAUDE.md athena masih menulis "price floor Rp50", basi sejak 16 Nov). Berlaku untuk semua repo sebagai pola: repo yang punya aturan angka butuh dokumen aturan tertulis, kalau tidak pembaca hanya bisa bilang "aturan tidak tertulis". Usul (belum disetujui): kartu menulis "repo ini tidak punya DOMAIN.md" bila PRD menyentuh angka.
  - [ ] **T3a (Atha menilai 6 cacat + 6 baik)**: belum dikerjakan; ini gerbang T3 yang sungguhan tersisa selain pembaca. Logistik tampilan belum diputuskan (instansi chat terpisah untuk 12 kartu).
- **`argus applied` (jalur manual) dan catatan baca patch** (Atha 2026-11-17, "masukin pending dulu aja, ga begitu urgent"): `argus apply` menolak tanpa catatan baca `ok` (T3 PR 3), tetapi `argus applied <job> --commit <sha>` (patch dipasang dengan `git apply` sendiri, lalu dicatat) tidak memeriksanya; pada saat itu patch sudah di repo, jadi menolak mencatat tidak mencegah apa pun dan merusak jalur pemulihan. Usul Claude, belum dikerjakan: jangan blokir, tetapi catat: `applied` menulis bidang `reader` bila ada catatan yang cocok, dan kartu pasang dan `status` menulis "patch read: tidak ada (dipasang manual)", supaya tidak ada klaim "dibaca" yang palsu. Alternatif yang lebih ketat (Atha boleh pilih): jalur manual wajib catatan kecuali dengan flag eksplisit yang dicatat. Ditemukan di tinjauan Opus PR 3 (m1).
- **Tampilan chat Argus dibuat seperti aplikasi Claude di HP** (Atha 2026-11-17, "simpen diparkiran. Ui/ux nya pengen dibuat model gini"; acuan: `docs/refs/chat_ui_reference_2026-11-17.png`, tangkapan layar sesi Remote Control di aplikasi Claude): satu aliran percakapan, bukan halaman terpisah per mode. Unsur yang terlihat di acuan: bilah atas (tombol kembali, judul dengan subjudul, indikator berjalan, menu "..."); penanda waktu di tengah aliran; pesan pengguna sebagai gelembung membulat di kanan, jawaban sebagai teks lebar tanpa gelembung dengan huruf besar yang nyaman dibaca; kegiatan alat dilipat menjadi satu baris yang bisa dibuka ("Running agent >"); tombol panah melayang untuk lompat ke bawah; kolom ketik membulat dengan tombol "+" di kiri dan kirim di kanan; bilah tab melayang di bawah (Chat, Projects, Code, Artifacts) dengan tab aktif berlatar kapsul. Pemetaan usul ke Argus (belum dikerjakan): chip mode sekarang (Status, Issue, Riset, Keputusan, Kartu) menjadi bilah tab bawah; kartu rencana dan pasang muncul sebagai pesan di aliran; log tahap mesin dilipat per baris; ringkasan penulis tetap bertanda "ditulis model". Syarat: `app.js`, `index.html` dan `app.css` dipin hash-nya (`STATIC_SHA256`), tes UI lama mengunci baris JS tertentu, dan JS tanpa tes runtime (hanya cek sintaks node); penggantian tampilan sebesar ini perlu spek pendek, tes statis dan, bila bisa, tangkapan layar sebelum dan sesudah (lihat "Screenshot sebelum dan sesudah"). Dibahas di titik cek 2026-11-29; polish kecil kartu rencana (lipat ringkasan penulis, label argumen lebih pendek) bisa ikut di sana.
- **Gerbang contoh angka di issue:** dipindah ke tahap T1 (lihat "Tahapan tanpa pusing Atha" di Inti 2); catatan awal Atha 2026-11-16 "no.2 catat di parkiran".

## Log permintaan yang chat belum bisa

Satu baris per permintaan: tanggal, apa yang diminta, kenapa chat belum bisa. Kemampuan permukaan berikutnya dipilih dari sini di
titik cek.

- (kosong)

## Pekerjaan operasional (Atha, di luar repo)

- [ ] **Periksa ulang aturan ARB/ARA BEI pada 2 Januari 2027** (research 2026-11-16, `jobs/j20261116_081333_0a18/REPORT.md`): ARB 7% (dan Rp11-14 jadi Rp1) hanya berlaku sampai 31 Desember 2026 menurut OJK; apa yang berlaku mulai 2027 tidak jelas (satu judul Katadata menyebut ARB 35%). `DEFAULT_SLIPPAGE_BUFFER_PCT = 0.15` di athena sengaja tidak diubah sampai itu jelas. Sumber primer (idx.co.id) belum ditemukan; semua angka masih dari media dan sekuritas.
- [x] **Firewall mesin ini, port 443 (2026-11-16, ditutup lagi 2026-11-21 atas kata Atha "Tutup lagi"):** aturan `ACCEPT tcp 443` dicabut dari iptables yang hidup dan dari `/etc/iptables/rules.v4` (cadangan sebelum perubahan: `/etc/iptables/rules.v4.bak-20261121-port443`); aturan SSH (22) tidak disentuh dan masih mendengarkan; nginx tetap hidup di mesin (443 lokal masih menjawab) tetapi tidak terjangkau dari luar. **Akibatnya:** backend athena dan PWA-nya tidak terjangkau dari internet lagi (dikehendaki Atha). **Catatan:** port **80** masih terbuka di firewall (nginx); tidak disebut Atha, tidak disentuh, perlu keputusan bila mau ditutup juga. Cadangan lama 2026-11-16 di `/tmp` sudah tidak relevan. Belum diuji lewat boot ulang (aturan file sudah konsisten dengan yang hidup); security list Oracle tidak diperiksa (seharusnya lebih ketat atau sama).

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

## Kandidat dari pilot web ledger-cli (2026-11-20)

- [ ] **Saran model untuk keberatan pembaca angka** (usul Atha 2026-11-20, hanya dicatat): satu model lain menilai keberatan yang sedang diterima (`bawaan wajar` atau `mengubah perilaku`, satu baris) dan kartu menampilkannya di dekat keputusan Atha. Saran bukan keputusan: `examples-accept` tetap butuh alasan Atha. Keputusan Atha 2026-11-20: model yang meneruskan sendiri tidak dipakai (penulis, pembaca dan penilai model sejenis; keberatan "aturan ini bukan dari Atha" hanya bisa dijawab Atha). Kemungkinan lanjutan: daftar aturan yang boleh lolos otomatis, ditulis Atha sekali.
- [ ] Bundel pembaca angka menampilkan pesan revisi PRD yang ditulis operator (Claude) sebagai "kata-kata manusia"; tandai pesan operator.
- [ ] Kartu rencana: tandai permintaan yang ditulis operator "Claude (operator)" dan tampilkan lebih pendek.
- [x] **Tingkat per temuan di pembaca patch** (usul Atha 2026-11-20, dari pilot ledger-browser; jalur ketat karena menyentuh gerbang patch): (1) pembaca memberi tiap temuan tingkat `blocker` (salah terhadap issue atau merusak sesuatu) atau `nit` (sudut jarang); hanya blocker yang menutup patch, nit ditulis dan tampil di kartu untuk Atha; (2) templat pembaca: acuannya teks issue, bukan kebiasaan umum (tanggal bersepasi: issue bilang "strict", ledger-cli menerimanya); (3) `queue retry` hanya untuk blocker. Bukti: dari 16 patch yang dibaca dua pembaca argus, pembaca 2 (DeepSeek 1017) berkata concerns 6 kali (5 ok/concerns, 1 concerns/concerns), pembaca 1 (Hy4 Flash) sekali; pada issue 1 ledger-browser 3 dari 3, tiap putaran sudut baru (kutip, tanggal bersepasi, tahun 0-99, baris kosong) sementara tes tersembunyi lulus 22 dari 22; tiap putaran ulang 10-15 menit, dan temuan yang keliru ikut ke penulis draf (draf 3 menulis tes "tanggal bersepasi ditolak" dan membuang dua tes kutip yang benar). Catatan: sampai ini dibangun, aturan sementara (Atha 2026-11-20): auto-approve draf, retry paling banyak 2x, tidak ada retry ke-3, lalu terapkan dengan tangan (`git apply` + `argus applied`) dan catat alasannya. **Urutan (Atha 2026-11-21): dibangun sesudah `--accept-concerns` (#650, ter-merge) dan uang antrean (#651, ter-merge); `--accept-concerns REASON` adalah jalan darurat sementara.** **Dibangun 2026-11-21 (#654, `docs/reviews/SPEC_PATCH_READER_SEVERITY.md`): satu tingkat per bacaan (bukan per temuan); pasangan dua pembaca Argus yang semua keberatannya `nit` lolos seperti `ok` dan nit dicatat (log, status, kartu); retry hanya membawa blocker. Uji cacat tanam LULUS (`pilots/patch_reader_severity_v0/RESULT.md`), tetapi tidak ada bacaan yang bilang `nit` di uji itu: efek pada sudut remeh dari pilot baru terukur di job nyata. Ukur dan laporkan pada beberapa job pertama.**
- [x] **Antrean kehabisan uang karena retry (pilot ledger-browser 2026-11-20)**: job yang sudah diterapkan dihitung sebesar batas penuh ($1,00), bukan biaya sungguhan (sekitar $0,01), jadi antrean 3 issue x $1,00 berhenti di issue 3 ("uang tersisa $0,9769, satu job butuh $1,00") setelah dua issue diterapkan dan dua retry; biaya nyata total sekitar $0,10. Tanpa operator, Atha melihat kartu STOPPED di chat tanpa tombol dan tanpa langkah berikutnya (tutup antrean, `prd reply --rebase`, persetujuan rencana dan uang baru, semua perintah terminal). Usul, urut murah ke mahal: (a) teks langkah berikutnya di kartu STOPPED (jalur ringan); (b) hitung job yang diterapkan sebesar biaya sungguhan (jalur ketat: aturan uang); (c) satu tombol "lanjutkan sisa issue" yang menyiapkan rencana baru dan meminta persetujuan uang (jalur ketat: persetujuan di chat). **Dibangun 2026-11-21 (#651, spek `SPEC_QUEUE_MONEY`): job APPLIED dihitung sebesar biaya nyata; judge sesudahnya dihitung saat terjadi (bisa menambah sampai $0,30 per job di atas `max_usd`); kartu STOPPED memuat langkah berikutnya per penyebab. Tombol "lanjutkan sisa issue" tidak dibangun (ditunda sampai ada penghentian uang nyata).**
- [ ] **Rujukan repo lain di penulis PRD** sudah dibangun (`prd new --ref`, #646); kartu rencana dan halaman chat belum menampilkan rujukannya (hanya layar konfirmasi dan `argus status`).

- [x] **`argus apply --accept-concerns "ALASAN"`** (Atha 2026-11-21, #650, `docs/reviews/SPEC_APPLY_ACCEPT_CONCERNS.md`): menerapkan patch yang dua pembacanya (dua id berbeda) salah satunya `concerns`, lewat semua cek apply lain; alasan 10-500 karakter dari manusia dicatat di log job, trailer commit `Accepted-concerns:` dan `argus status`. Hanya CLI, bukan tombol chat.
- [ ] **Dua slot kunci chat** (#653, 2026-11-21): `ARGUS_CHAT_KEY_FILE` (kode) dan `ARGUS_CHAT_RESEARCH_KEY_FILE` (riset, DeepSeek) terpisah; kunci kode sekarang OpenRouter. Riset dari chat butuh saldo DeepSeek.
## Pilot bulking-app dan kemampuan Argus (2026-11-21)

- [x] **P2a: PRD dari chat** (2026-11-21, #660; `SPEC_CHAT_MANAGER` rev 1 bagian 15; Atha "Gass bro"; tinjau Opus spek dan kode GO WITH CHANGES, mutan 27 dari 27, `verify_at` PASS 6731 lulus): chip PRD di chat, aksi `prd_new` diketik manusia (hanya `{repo, message}`, kartu dari `pj.screen_facts` yang sama dengan layar terminal), `argus prd new --via ui` dengan id berbentuk id harness, job PRD dihitung di batas harian (direktori, pending, jaring audit), dan `execute` dengan dispatch eksplisit (aksi tak dikenal tidak lagi jatuh ke `issue start`). **D5 SPEC_PRD_WRITER dibuka.** Yang belum: balasan PRD (`prd_reply`), `prd check/approve`, `queue go/step`, apply dan buka PR dari chat tetap terminal; penolakan CLI sebelum job dibuat (antrean menunggu, repo berubah) tidak tampil di chat (catatan tinjau; kartu bilang hanya terlihat di terminal); job PRD yang ditolak sesudah kunci job dibuat (ABANDONED, `via ui`) tetap terhitung $1,50 selama 24 jam tanpa ada biaya. Chat di-restart di main 67b4c8d.
- [x] **Pilot pertama bulking-app** (repo privat Atha, React 18 + Vite; Atha mengizinkan kode ke model lewat OpenRouter 2026-11-21): environment `bulking_node22` (#656: Vite 6 + vitest 3, karena harness memakai `configLoader runner` yang tidak ada di Vite 5), pendaftaran repo (#657), kerangka tes di bulking-app (PR #3), issue "tren berat butuh 3+ catatan per jendela 7 hari" dari PRD sampai PR #4, tanpa retry; biaya sekitar $0,015. Issue berikutnya dipilih dari `pending.md` bulking-app (mikro yang belum dilacak; tes `targetEngine.js`).
- [x] **`argus apply` menolak tes baru yang cocok dengan `.argus/protected`** (ditemukan di pilot bulking-app 2026-11-21; **ditutup 2026-11-21, #671**, `SPEC_PROTECTED_FILES` bagian 10, `router/protected_files.py`): berkas yang cocok daftar menghentikan patch kecuali ditambah (`change: A`), bernama tes (`test_*.py`, `*_test.py`, `*.test.js|jsx|ts|tsx`, bukan `conftest.py`) dan `approved_test` (dinyatakan draf yang disetujui, isi sama); `apply` juga mencocokkan `change: A` dengan bacaan git sendiri (status A, mode lama 000000; tinjau Opus R1), kartu pasang menampilkan tes baru yang lolos dengan tanda sendiri. Tinjau Opus GO WITH CHANGES, mutan 16/18 (dua setara), `verify_at` PASS 6824. **Batas yang diketahui:** `argus applied` (jalur tangan) tidak memeriksa berkas terlindungi; glob direktori seperti `public/**` tetap mengizinkan tes baru yang disetujui di dalamnya; kartu bisa hijau untuk paket palsu yang ditolak `apply`; perbandingan hash blob dengan `approved_tests(record)` saat apply ditunda. Argus-viewer dan ledger-browser yang dulu mungkin kena yang sama kini tercakup.
- [ ] **Issue "tes untuk kode yang sudah ada" tidak bisa lewat gerbang draf** (pilot bulking-app, 2026-11-21, `targetEngine.js`; PRD dari chat job `j20261121_150231_cbce`, antrean `q20261121T151037Z-3529` ditutup): drafter `NO_DRAFT` `submits_exhausted` (7 submit, $0,057), karena gerbang draf menuntut tes yang gagal di commit dasar dan tes untuk kode yang sudah ada lulus semua ("baseline 14 tes, 0 gagal"). Biaya sampai gagal sekitar $0,11 (PRD dua giliran $0,035). Angka PRD benar (diverifikasi tangan terhadap `recipes.js` dan `ingredients.json`). Jalan keluar yang dipakai: Claude menulis berkas tes langsung, dijalankan di image sandbox, dan PR di repo Atha (bulking-app #5, 13 tes, tiga mutan kode terbunuh). **Celah:** menambah cakupan tes pada repo luar yang belum punya tes adalah pekerjaan wajar; perlu jenis issue sendiri ("karakterisasi": tes harus lulus di commit dasar, kode tidak boleh berubah, diff hanya berkas tes baru, pemeriksa mesin memastikan tidak ada perubahan di luar berkas tes) atau cabang gerbang yang membedakannya. Jalur ketat (gerbang draf). Belum dibangun: menunggu bukti kedua dan titik cek 2026-11-29. Dua pelajaran kecil dari pilot: `git pull` di repo target sesudah PRD dibuat menggeser HEAD dan membuat `prd reply` menolak (jalan resmi: `--rebase`, catatan lama dibuang), dan `queue close --note` diperlukan sebelum PRD baru di repo yang sama.
- [x] **T4a: tombol rencana di chat** (2026-11-21; `docs/reviews/SPEC_CHAT_T4A.md` rev 1, tinjau Opus spek dan kode GO WITH CHANGES; mutan 54 dari 55, satu setara; `verify_at` PASS 6803; PR #663 aksi dan CLI, #664 halaman; Atha "Ok gass", K3 A, "bikin placeholdernya dulu" untuk tombol jalankan antrean, "gabung pr1 dan pr2"): `queue go --via ui --reason-file` (`approved.via/at/reason`; aturan alasan satu modul dengan `apply --accept-concerns`), aksi chat `prd_approve` (gratis) dan `queue_go` (uang). Klien hanya mengirim id job PRD (plus `ack` dan `reason` bila tanda mesin meminta); server membaca folder, antrean, sha penuh dan uang, mengikat antrean ke folder giliran terakhir, dan menolak di server: pembaca belum `ok` untuk tiap item bercontoh (termasuk `tidak_terbaca`), himpunan `ack` untuk item tanpa contoh baru, biaya >= 3x atau tanpa acuan tanpa alasan diketik, rencana sedang ditulis ulang, folder digantikan atau basi. Tanpa kunci, tanpa model, tanpa git saat prepare. Uang antrean yang disetujui via UI dihitung di batas harian (pindai direktori, pending, jaring audit); **`chat.daily_cap_usd` $7,00** di `config.yaml` (Atha K3 A; sebelumnya bawaan $2,00; pagar bukan pemakaian). Halaman: tanda mesin di atas semua fakta kartu konfirmasi, "Setujui rencana" hidup, "Jalankan antrean (belum aktif)" placeholder; `GET /api/approve/prd/<id>` membawa `t4`. **Celah yang diketahui:** `queue go` dari terminal tidak menegakkan aturan pembaca dan biaya (chat yang menegakkan); satu `queue.json` rusak (atau direktori antrean setengah jadi) di `queues_dir` menahan kedua tombol dan semua aksi berbayar chat sampai dibuang (dinyatakan, pesan menyebut id antreannya); `queue_go` yang timeout tetap dihitung pending 10 menit; CLI memblokir server satu-utas sampai 30 detik; antrean terus berjalan sesudah jendela 24 jam; `prd_approve` tidak menampilkan kenapa sebuah plan tidak siap selain pesan server. Lalu: verifikasi pertama gagal karena `tests/test_budget_experiment.py` membandingkan `config.yaml` dengan config lama (bagian `chat:` baru perlu diabaikan), pelajaran lama "ubah nilai config: grep tes yang menurunkan angka" terulang. **Belum dicoba di HP;** dua catatan: tombol baru aman ditekan hanya pada rencana yang memang mau diteruskan (membuat antrean PENDING), dan PRD tes `targetEngine` lama (job `j20261121_150231_cbce`) masih menawarkannya.
- [x] **T3 ringan (Atha 2026-11-21, "males", jadi 3 baik + 3 cacat, bukan 12):** enam kartu fixture buatan Claude (rencana: tujuan menyimpang, biaya 5x, dua baik; pasang: cakupan, satu baik), diacak, kunci di-hash sebelum dikirim (`5e376b33...6188`, berkas `~/bulk_pilot/t3_key.json`). **Hasil 4 dari 6, GAGAL menurut aturan yang ditulis dulu** (semua cacat ditolak, paling banyak satu baik ditolak): tujuan menyimpang dan biaya ditolak dengan alasan benar; **kartu pasang cacat cakupan diterima** ("audit hijau, dua pembaca ok") padahal baris "Ditandai mesin" menulis `package.json` (dilindungi) dan `Settings.jsx` (di luar issue); satu kartu rencana baik ditolak karena teks pengingat di ringkasan beda dari permintaan (kartu fixture ambigu, penolakannya bisa dibela). Waktu sekitar 10 menit untuk 6 kartu. **Keputusan Atha ("Ok gass"): lewati T3 penuh, bangun T4a (kartu rencana: `prd approve`, `queue go`); apply dari chat (T4b) ditahan sampai kartu pasang membuat tanda mesin tidak bisa terlewat dan tombol mati secara mekanis.** Batas jujur: kartu fixture, bukan keluaran pembuat kartu; n = 1 orang, 6 kartu.
- [x] **Selesai (Atha 2026-11-21):** PR #5 bulking-app (13 tes `targetEngine`) di-merge (dicek: MERGED); chip PRD dan tombol rencana dari HP dicoba; saldo DeepSeek untuk riset dari chat diisi. (Dua yang terakhir atas kata Atha, tidak diperiksa Claude.)
- [ ] **Merampingkan environment (usul Atha 2026-11-21 "digabung aja ... hapus yang double", dijawab: satu environment gabungan TIDAK aman; hanya dicatat):** versi paket sengaja beda per repo (FastAPI 0.141.1 athena, 0.143.0 `ledger_py312`, 0.143.2 `up1`, 0.162.0 `up2`; React 19 `pwa_node22` lawan React 18 `bulking_node22`), tes harus jalan terhadap versi repo itu sendiri; image gabungan memperbesar isi sandbox (permukaan serangan); menghapus image `ledger_*` merusak `verify_at` ("sandbox tests skipped: 0"); disk bukan masalah (image total sekitar 4 GB, disk 35%); biayanya perawatan (tiap environment dibangun ulang bila ada celah paket). Yang realistis, PR strict kecil, sebaiknya dikerjakan bersamaan dengan pembaruan keamanan paket supaya bangun ulangnya sekali jalan: **(A)** gabung `ledger_staging*` ke `ledger_py312*` (bedanya hanya `uvicorn`; tiga environment, tiga pin dan catatan pemeriksaan hilang; image tes sedikit lebih besar); **(B)** pensiunkan tahap `up1` (`ledger_py312_up1`, `ledger_staging_up1`; jalur upgrade sudah dibuktikan 2026-11-07, tiap satu hanya dipakai satu tes). Hanya lima environment dipakai repo nyata (`ledger_py312_up2`, `ledger_py312`, `athena_py312`, `pwa_node22`, `bulking_node22`), plus `sympy*` (evaluasi) dan `argus` (dirinya sendiri). Belum dibangun, tidak mendesak.
- [ ] **`web.environments` belum memuat `bulking_node22`**: `approve --web` ditolak untuk repo itu. Tidak perlu untuk logika murni; tambahkan (keputusan config terpisah) hanya bila issue butuh dokumentasi.
- [x] **Catatan hook (2026-11-21):** `~/.claude/hooks/argus_guard.sh` sudah mengizinkan Claude memakai `argus.py ... --key-file openrouter=~/.config/argus/openrouter_key` (juga `deepseek=`) dan hanya itu; bentuk lain (sed, ls, `--key-file ~/...` tanpa penyedia untuk OpenRouter) ditolak. Jadi langkah dengan kunci (penulis PRD, drafter, agen, pembaca patch) bisa dijalankan Claude tanpa melonggarkan hook; kuncinya tidak pernah dibaca. Satu kekeliruan di sesi: job id harus diawali `j` huruf kecil/angka/`_` (bukan `bulk-trend-1`).
- [ ] **Kemampuan Argus mendekati operator (usul Atha 2026-11-21, hanya dicatat; urutan saran Claude, belum diputuskan):** (1) aksi "buka PR" setelah apply, token GitHub yang hanya boleh membuat branch dan PR; (2) pilot kedua bulking-app sampai PR terbuka; (3) merge otomatis hanya untuk repo pilot terdaftar, dengan syarat tertulis (semua gerbang, CI hijau, dua pembaca, tanpa berkas terlindungi), token merge terpisah; Argus sendiri tetap lewat manusia; (4) browser terisolasi hanya-baca (tanpa login, daftar domain, tangkapan layar) bila ada kebutuhan nyata, prasyarat: uji prompt injection lanjutan (lihat "Permukaan: kemampuan lain"). `--web` (ReadDocs untuk agen kode, host di `web.hosts`) dan riset (`argus research`) adalah dua hal berbeda dan keduanya bukan browser.
- [x] **T6 PR1 (pengerasan builder, 2026-11-21, #670; spek T6 rev 1 di-merge sebagai catatan #668):** `scripts/build_env_from_base.sh` memakai `--only-binary :all:`, `--index-url https://pypi.org/simple` dan `--isolated`; delapan environment Python dibangun ulang, rootfs identik semua; mutan 9/9; `verify_at` PASS 6808. **PR2-5 (resolver offline dst.) tidak dibangun dan tidak disetujui;** menunggu repo Python nyata dengan dependensi nyata.
