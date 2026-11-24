# Pending

**Semua butir terbuka (belum `[x]`) dan urutan kerjanya: [`PENDING_PRIORITAS.md`](PENDING_PRIORITAS.md)** (dipindah dari berkas ini 2026-11-24; salinan utuh sebelum dipindah: [`PENDING_ARCHIVE_2026-11-24.md`](docs/reviews/PENDING_ARCHIVE_2026-11-24.md)). Berkas ini menyimpan arah, aturan, riwayat selesai dan catatan.

Arah, aturan dan riwayat Argus, disusun menurut arah 2026-11-15. Status milestone dan ADR beserta buktinya ada di
[`docs/Reconciliation.md`](docs/Reconciliation.md) (satu-satunya tempat status). Riwayat butir yang selesai (bukti, angka, PR) dan butir
yang tidak lagi berkaitan dengan arah: [`docs/reviews/PENDING_ARCHIVE_2026-11-16.md`](docs/reviews/PENDING_ARCHIVE_2026-11-16.md)
(salinan utuh sebelum dirapikan 2026-11-16: rincian VF O1, `argus apply`, antrean dan tahap PRD),
[`PENDING_ARCHIVE_2026-11-15.md`](docs/reviews/PENDING_ARCHIVE_2026-11-15.md) (salinan utuh sebelum arah 2026-11-15), [`PENDING_ARCHIVE_2026-10-30.md`](docs/reviews/PENDING_ARCHIVE_2026-10-30.md),
[`PENDING_ARCHIVE_2026-10-22.md`](docs/reviews/PENDING_ARCHIVE_2026-10-22.md) dan `docs/reviews/`.

Terakhir diperbarui: 2026-11-24 (butir terbuka dipindah ke `PENDING_PRIORITAS.md`). Sebelumnya 2026-11-22 (ditambah "Peta" di bawah, butir selesai bagian bulking-app diringkas; teks utuh di arsip 2026-11-22). Sebelumnya 2026-11-16 (dirapikan: urutan inti selesai dibangun, butir `[x]` diringkas dan rinciannya pindah ke arsip
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

## Peta (disusun ulang 2026-11-22)

Peta ini hanya penunjuk; teks butirnya tetap di bagian masing-masing di bawah. Salinan utuh sebelum disusun ulang:
[`PENDING_ARCHIVE_2026-11-22.md`](docs/reviews/PENDING_ARCHIVE_2026-11-22.md). Pembagian ini penilaian Claude, bukan keputusan Atha.

1. **Selesai dan terbukti** (urutan inti yang diterima 2026-11-15): jalur kode, antrean, tahap PRD, penulis PRD, `argus apply` (kini membuat cabang `argus/<job>` sendiri, #674), chat C1–C4, T4a (PRD dan antrean dari chat), pengerasan builder (T6 PR1), pilot bulking-app 2 issue (PR #5 merged; PR #6 menunggu Atha).
2. **Menunggu bukti dari kerja nyata** (tutup lewat pilot, bukan dibangun lebih dulu): bagian "Inti 1", butir mutu patch (B ke A), mutu drafter dan agen, Vitest v0 (tes lama tidak bisa diubah), stage mutan di job kode, agen menunggu sandbox, "tes untuk kode yang sudah ada" tidak lolos gerbang draf (bagian bulking-app).
3. **Ditahan sengaja:** T4b (apply, approve draf, `queue step` dari chat), "Approve dari HP lewat chat", riset baru, chat sebagai mandor (parkiran, titik cek 2026-11-29), T6 PR2–5 dan merampingkan environment (sampai ada repo Python dengan dependensi nyata).
4. **Pembersih kecil** (kandidat issue murah): papan skor terpotong di HP, pesan "no draft to review", sinkronisasi pin image antar checkout, catat pelaku approve dan apply, `web.environments` memuat `bulking_node22`, celah kecil T4a (bagian bulking-app).
5. **Jaga-jaga, belum bisa dipicu:** idempotency key provider, R2 `ReportNoRepro`, operator rantai tetap, batasan yang diterima.
6. **Angka "bisa ditinggal"** (bagian "Angka bisa ditinggal" di bawah): 0 dari 2 issue, titik awal untuk titik cek 2026-11-29.
7. **Pengingat bertanggal dan operasional** (bagian "Pekerjaan operasional"): periksa ulang aturan ARB/ARA BEI 2 Januari 2027; sertifikat Let's Encrypt athena habis 2027-01-16 (port 80 ditutup); kunci HP `iphone-viewer` di `authorized_keys`.

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

**Butir terbuka dan temuan yang belum dicek (viewer-smoke, key `NEW`, dst.) ada di [`PENDING_PRIORITAS.md`](PENDING_PRIORITAS.md) bagian 2** (kategori B sampai J). Dicek 2026-11-16 terhadap `main` (#574): `router/apply.py`, `router/queue.py`, `router/prd_job.py`, `codetask/prd_writer.py` dan `tests/test_vf_canary.py` ada.

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
- **Butir `[ ]` dan `[~]` Inti 1 (pemalsu F1–F6, approve patch akhir, jangkar Atha, R2, RC b, Paket 3, tes lama bocor, stage mutan, mutu patch dan drafter, Vitest, verifikasi) pindah ke PRIORITAS kategori B (2026-11-24).**
- [x] **(SUDAH DIBANGUN, lihat butir T1 di bawah: #586, #587, #588, pilot Rp1 2026-11-17; teks di bawah adalah temuan awalnya, bukan keadaan sekarang)** Gerbang contoh angka di issue = tahap T1 dari "Tahapan tanpa pusing Atha" (Inti 2)** (temuan terpenting pilot athena 2026-11-16, `pilots/research_to_issue_v0/`): tidak ada gerbang yang mencocokkan contoh angka di issue dengan kode; penulis issue salah di empat angka (entry 0,5 sebenarnya `ZeroDivisionError`; 1,5 dibulatkan ke 2; 1,2 dibulatkan ke 1 dan diblok; stop "47,0" sebenarnya 45,0) dan Claude yang menangkapnya dengan menjalankan fungsinya (lantai di-set 1,0 di memori). Batas yang dinyatakan: contoh yang hanya benar sesudah perubahan tidak bisa diverifikasi nilainya sebelum kodenya ada; gerbang tiga tingkat di bawah (T1). Jalur ketat (mengubah apa yang diterima sebagai issue).

### Inti 2: bisa ditinggal (tanpa Claude di tengah)

- **Inti 2 (tahap T0–T6, apply K6, uji lepas tangan, PRD sampai staging, `argus fix`, rantai, pin image, smoke viewer, celah penulis issue, agen menunggu sandbox) pindah ke PRIORITAS kategori C (2026-11-24).** Selesai di bagian ini: T2 kartu baca-saja (2026-11-17); `argus apply` (di atas); PRD bagian A, B1, B2 (#555, #559, #566, #568).
- [x] **Ketergantungan tersembunyi ketiga dan keempat (Stage 19 `/api/scoreboard/models`, Stage 20 `/api/budget/jobs`): ditutup 2026-11-16.** Proxy meneruskan kedua jalur (`SPEC_PROXY_LEDGER_PATHS`, #580; go live jalan A, `pilots/staging_proxy_paths/steps.md`: 200 lewat 8710, `?week=` dan `?kind=` tetap 404 karena proxy tidak meneruskan query). **Sisa:** tidak ada halaman viewer yang memakai keduanya (JSON mentah di peramban lewat SSH forward); filter minggu tidak bisa lewat proxy (butuh aturan query sendiri dan spek); `~/pilot3a_live` tertinggal 36 commit dari `main` dengan **satu berkas bertahap** (`router/stage_viewer.py`, sama dengan `e2ee6c0`) dan `argus-chat` di 8711 masih menjalankan kode lama (jalan A: pembaruan penuh dan restart chat belum diputuskan). **`~/argus-ledger` tidak punya remote** (push tidak mungkin; repo hanya lokal), dan commit `0780f1e`, `e008f98` hanya ada di sana.

### Inti 3: biaya terkunci

- **Inti 3 (biaya terkunci): E1, key `NEW`, idempotency pindah ke PRIORITAS kategori D (2026-11-24).**

### Ukuran (M5)

- **Ukuran (M5): angka utama batas atas, catat pelaku, supervisi, eval set, efek petunjuk berhenti pindah ke PRIORITAS kategori E (2026-11-24).** Angka batas atas 2026-11-15: 23,8% (`verification/scoreboard-2026-11-15.json`).

### Permukaan: chat (pintu depan)

- **Permukaan chat: CHAT-APP (a)(b), assistant, approve dari HP, papan skor HP, "no draft", streaming pindah ke PRIORITAS kategori F (2026-11-24).**

### Permukaan: kemampuan lain (satu per satu, hanya dengan gerbang)

- **Kemampuan lain (riset, prompt injection, kemampuan berikutnya) pindah ke PRIORITAS kategori G (2026-11-24).**

## Parkiran sampai titik cek (berikutnya: 2026-11-29)

Ide arah atau kemampuan baru yang muncul di antara titik cek: tanggal, kata-kata Atha, tempatnya terhadap arah. Tidak dikerjakan
sebelum titik cek, kecuali Atha berkata ia mengganti pekerjaan yang sedang berjalan.

- **Parkiran (mandor, `env init`, gerbang lint, environment node, error provider `prd`, penyambung satu-prompt, PRD dari nol, screenshot UI, `argus applied` manual, tampilan chat, paralel) pindah ke PRIORITAS kategori C, F dan H (2026-11-24); titik cek tetap 2026-11-29.** Catatan hasil T3 (yang bukan butir kerja) tetap di bawah.
- **Status T3 (2026-11-18)**: dibangun dan live: kartu rencana, kartu pasang (`GET /api/approve/code/<job>`, syarat a-i, tanda cakupan mesin, dua pembaca berlabel), `argus apply` menolak tanpa catatan pembaca patch dan (untuk item antrean PRD) tanpa catatan pembaca angka. **Belum**: T3a (Atha menilai 6 cacat + 6 baik; logistik tampilan belum diputuskan: 12 kartu di instansi chat terpisah, kartu pasang terjangkau lewat item antrean REVIEW_READY), T3b lengkap, tombol T4.
  - **T3b hasil (smoke test, bukan tingkat kesalahan)**: `scripts/t3b_fixtures.py` (16 set: 8 cacat ditanam, 8 baik; kunci di balik hash di `<root>.key`) dan `argus t3b-run` (pembaca = model Argus lewat `LLMCaller`, batas total sendiri). Putaran Sonnet (subagen, templat lama): 8/8 cacat tertangkap di dua bacaan, tetapi 4/8 set baik ditandai (format angka "1.000" ambigu, g4 bukan set baik yang bersih, keluhan di luar tugas); setelah itu templat dapat aturan 6 (gaya angka Indonesia) dan 7 (hanya angka dan aturannya), g4 diperbaiki. Putaran GLM-5.3 (templat baru, set baru, hash kunci `e65f7c5b9e7c01df37b9430fa2efd92322820fa65b65529b5bde172f1495e6c0`): 8/8 cacat tertangkap di dua bacaan dengan alasan yang benar, 0/8 set baik ditandai; dua bacaan awal terpotong di batas keluaran (GLM berpikir) dan diulang dengan batas 8000. Biaya: $0,477 menurut ledger (batas atas), $0,215 tagihan gateway (Novita fp8, diskon 55% masih berlaku 2026-11-18). **Belum lulus resmi**: dua set riwayat nyata (kasus Rp1; perbaikan bug di `git log` athena) belum ada, jadi `score` mencetak INCOMPLETE; `verification/reader_tests.json` belum ditulis, jadi kartu tetap menulis "pembaca belum diuji". Catatan: uji ini menilai model, bukan kartu: pembaca kartu tetap sesi Claude (spek rev 2); pakai model Argus sebagai pembaca kartu = spek rev 3 + keputusan Atha (D8). Sonnet belum diulang dengan templat baru. `reader_tests.json` perlu mencatat modelnya (hasil uji berlaku per model).
  - [x] **Perbandingan effort GLM-5.3 sebagai pembaca angka (2026-11-18)**: thinking bawaan 8/8 cacat tertangkap dan 0/8 set baik dialarmi, token berpikir rata-rata 2.794, biaya ledger $0,477 untuk 32 bacaan; `--effort medium` rata-rata 55 token berpikir (praktis tanpa berpikir), $0,075, 1 luputan nyata (salah hitung 10.000.000-3.000.000=6.000.000, dijawab `ok`) dan dua catatan benar tanpa angka yang seharusnya: FAIL. Keputusan: pembaca memakai thinking bawaan, tidak diturunkan; hasil uji berlaku per model dan per effort (catat di `reader_tests.json`).
- **Hasil T3b resmi, putaran 1 dan 2 (2026-11-18; Atha: "catat dulu aja jangan uji ulang")**: 20 set (10 cacat, 10 baik; 2 cacat dan 2 baik dari riwayat nyata athena), GLM-5.3 `--effort high`, dua bacaan per set. **Putaran 1** (hash kunci `1eda75d2...728c`, tanpa DOMAIN.md): 10/10 cacat tertangkap di dua bacaan (A lantai Rp50 basi dan B buffer ARB 15% yang kini 7% termasuk), tetapi 2/10 set baik dialarmi (g9, g10: rumus stop dan ukuran posisi tidak tertulis di dokumen mana pun, jadi pembaca benar menurut aturan 4) = FAIL. **Putaran 2** (hash `d9b998fa...9d97`, dengan draf `DOMAIN.md` athena, set dan contoh sama; perubahan dibuat setelah melihat putaran 1): 0/10 set baik dialarmi, 9/10 cacat tertangkap di dua bacaan, satu luput nyata: d6 (sisa batas) dijawab `ok` di bacaan ke-2 karena salah hitung "10.000.000 - 3.000.000 = 6.000.000" = FAIL. Gabungan semua bacaan `high` (3 uji): 56 bacaan cacat, 1 luput (1,8%), 56 bacaan baik dengan DOMAIN.md: 0 alarm. Biaya: $0,170 + $0,136 (ledger, batas atas; tagihan gateway sekitar separuhnya). `reader_tests.json` TIDAK ditulis: kartu tetap menulis "pembaca belum diuji". Tidak diuji ulang atas permintaan Atha.
- **T3b putaran 3, aturan rev 3 (2026-11-18, resmi, set segar, hash kunci `924ad977...ad1b` dicatat sebelum bacaan)**: GLM-5.3 `--effort high`, dua bacaan per set, 20 set, biaya ledger $0,199 (batas atas). **FAIL** menurut aturan yang ditetapkan sebelumnya: (a) d6 (sisa batas) dijawab `ok` di KEDUA bacaan, keduanya dengan hitungan salah yang sama ("10.000.000 - 3.000.000 = 6.000.000"); (b) 2 dari 18 bacaan cacat luput; h2 bacaan ke-2 tidak tercatat karena jalur menolak sumber yang diberi keterangan tambahan di dalam tanda kurung ("dokumen repo: DOMAIN.md (rumus ...)"), bukan karena salah baca; (c) 1 set baik dialarmi (g5, satu bacaan), dalam batas; (d) set riwayat nyata lengkap. Temuan penting: kesalahan hitung itu **konsisten, bukan acak**: tiga dari tiga putaran `high` salah pada set d6 dengan angka yang sama, jadi dua bacaan GLM tidak independen untuk kesalahan ini dan perkiraan 0,03% dari dua bacaan tidak berlaku. `reader_tests.json` TIDAK ditulis. Tidak diuji ulang. Dua bacaan oleh model yang sama menangkap alarm palsu dan luput acak, bukan kelemahan sistematis; untuk itu perlu pembaca berbeda (Claude) atau hitungan oleh mesin.
- **Pembaca patch = pasangan model Argus, lulus uji (2026-11-18; Atha: "Ok deepseek aja", "Ok gass bro")**: `argus patch-read-run <job>` (Hy4 Flash lalu, bila `ok`, DeepSeek V4.1 Flash 1017; `ok` butuh dua bacaan dua id; spek 13.5, PR #624, templat #626). Uji `router/patch_trial.py` (31 kasus: 17 cacat, 14 baik): putaran resmi 1 FAIL (c) (y1 dan g4 cacat bahan uji), putaran 2 FAIL (a)(b) (x1, tes tanpa import, lolos semua bacaan), probe di luar putaran (aturan 2(f) menutup x1; Hy4 penuh tidak lebih baik, 39x biaya), **putaran 3 PASS** (hash kunci `971ca88f...`, templat `05ce799f...`): (a) semua cacat tertangkap, (b) 0 dari 34 putaran cacat `ok`, (c) 0 kasus baik dialarmi, (d) 1 dari 124 balasan tidak terpakai, (e) semua bacaan sah. Biaya seluruh uji pembaca patch sekitar $0,5. `verification/reader_tests.json` ditulis untuk `athena` (bahan: `verification/patch_pair_trial_2026-11-18.md`): kartu pasang menulis "pembaca patch sudah diuji" hanya bila dua pembaca kartu persis pasangan itu dan hash templat dan instruksi sama. Batas jujur: kasus ditulis Claude; Hy4 Flash sendirian meloloskan x1 dua kali dan x6 sekali di putaran ini, jadi lulusnya bersandar pada DeepSeek sebagai bacaan kedua, yang satu keluarga dengan penulis patch Argus (DeepSeek V4.1 Flash); lulus adalah uji asap. Pembaca angka domain TETAP belum teruji (T3b gagal tiga putaran). Arah dari sini (Atha: "langkahnya udah kayak mau bikin app skala enterprise"): berhenti membangun infrastruktur uji pembaca; berikutnya T3a (Atha menilai 12 kartu); validasi lebih jujur dari kasus buatan = catat kecocokan catatan pembaca dengan hasil job nyata (patch dibatalkan, dikembalikan, terbukti salah). Kelalaian tercatat: `#622` dan `#624` di-merge pada vonis `verify_at` prematur (baris RESULT pertama, PASS; baris terakhir FAIL karena pin image sandbox tidak ada di worktree baru); ditutup oleh `verify_at` bersih untuk #625 dan #626 (6.369 dan 6.370 lulus, 0 sandbox dilewati).
- **Gerbang contoh angka di issue:** dipindah ke tahap T1 (lihat "Tahapan tanpa pusing Atha" di Inti 2); catatan awal Atha 2026-11-16 "no.2 catat di parkiran".

## Log permintaan yang chat belum bisa

Satu baris per permintaan: tanggal, apa yang diminta, kenapa chat belum bisa. Kemampuan permukaan berikutnya dipilih dari sini di
titik cek.

- (kosong)

## Pekerjaan operasional (Atha, di luar repo)

- **Pengingat bertanggal dan operasional (ARB 2 Jan 2027, sertifikat 2027-01-16, kunci HP, systemd) pindah ke PRIORITAS kategori I (2026-11-24).**
- [x] **Firewall mesin ini, port 443 (2026-11-16, ditutup lagi 2026-11-21 atas kata Atha "Tutup lagi"):** aturan `ACCEPT tcp 443` dicabut dari iptables yang hidup dan dari `/etc/iptables/rules.v4` (cadangan sebelum perubahan: `/etc/iptables/rules.v4.bak-20261121-port443`); aturan SSH (22) tidak disentuh dan masih mendengarkan; nginx tetap hidup di mesin (443 lokal masih menjawab) tetapi tidak terjangkau dari luar. **Akibatnya:** backend athena dan PWA-nya tidak terjangkau dari internet lagi (dikehendaki Atha). **Catatan:** port **80** masih terbuka di firewall (nginx); tidak disebut Atha, tidak disentuh, perlu keputusan bila mau ditutup juga. Cadangan lama 2026-11-16 di `/tmp` sudah tidak relevan. Belum diuji lewat boot ulang (aturan file sudah konsisten dengan yang hidup); security list Oracle tidak diperiksa (seharusnya lebih ketat atau sama).


## Ditunda sampai ada bukti kebutuhan

Syarat buka ulang dari `docs/reviews/FABLE_PLAN_2026-11-11.md` bagian 4, kecuali disebut lain.

- **Seluruh daftar "Ditunda" (M4, M7, M8, M9, capability pack, artifact store, git agen, ENV lanjutan, ringkasan validasi) pindah ke PRIORITAS kategori J (2026-11-24).**

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

- **Kandidat terbuka dari pilot ledger-cli dan bulking-app pindah ke PRIORITAS kategori F, G dan H (2026-11-24).**
- [x] **Tingkat per temuan di pembaca patch** (usul Atha 2026-11-20, dari pilot ledger-browser; jalur ketat karena menyentuh gerbang patch): (1) pembaca memberi tiap temuan tingkat `blocker` (salah terhadap issue atau merusak sesuatu) atau `nit` (sudut jarang); hanya blocker yang menutup patch, nit ditulis dan tampil di kartu untuk Atha; (2) templat pembaca: acuannya teks issue, bukan kebiasaan umum (tanggal bersepasi: issue bilang "strict", ledger-cli menerimanya); (3) `queue retry` hanya untuk blocker. Bukti: dari 16 patch yang dibaca dua pembaca argus, pembaca 2 (DeepSeek 1017) berkata concerns 6 kali (5 ok/concerns, 1 concerns/concerns), pembaca 1 (Hy4 Flash) sekali; pada issue 1 ledger-browser 3 dari 3, tiap putaran sudut baru (kutip, tanggal bersepasi, tahun 0-99, baris kosong) sementara tes tersembunyi lulus 22 dari 22; tiap putaran ulang 10-15 menit, dan temuan yang keliru ikut ke penulis draf (draf 3 menulis tes "tanggal bersepasi ditolak" dan membuang dua tes kutip yang benar). Catatan: sampai ini dibangun, aturan sementara (Atha 2026-11-20): auto-approve draf, retry paling banyak 2x, tidak ada retry ke-3, lalu terapkan dengan tangan (`git apply` + `argus applied`) dan catat alasannya. **Urutan (Atha 2026-11-21): dibangun sesudah `--accept-concerns` (#650, ter-merge) dan uang antrean (#651, ter-merge); `--accept-concerns REASON` adalah jalan darurat sementara.** **Dibangun 2026-11-21 (#654, `docs/reviews/SPEC_PATCH_READER_SEVERITY.md`): satu tingkat per bacaan (bukan per temuan); pasangan dua pembaca Argus yang semua keberatannya `nit` lolos seperti `ok` dan nit dicatat (log, status, kartu); retry hanya membawa blocker. Uji cacat tanam LULUS (`pilots/patch_reader_severity_v0/RESULT.md`), tetapi tidak ada bacaan yang bilang `nit` di uji itu: efek pada sudut remeh dari pilot baru terukur di job nyata. Ukur dan laporkan pada beberapa job pertama.**
- [x] **Antrean kehabisan uang karena retry (pilot ledger-browser 2026-11-20)**: job yang sudah diterapkan dihitung sebesar batas penuh ($1,00), bukan biaya sungguhan (sekitar $0,01), jadi antrean 3 issue x $1,00 berhenti di issue 3 ("uang tersisa $0,9769, satu job butuh $1,00") setelah dua issue diterapkan dan dua retry; biaya nyata total sekitar $0,10. Tanpa operator, Atha melihat kartu STOPPED di chat tanpa tombol dan tanpa langkah berikutnya (tutup antrean, `prd reply --rebase`, persetujuan rencana dan uang baru, semua perintah terminal). Usul, urut murah ke mahal: (a) teks langkah berikutnya di kartu STOPPED (jalur ringan); (b) hitung job yang diterapkan sebesar biaya sungguhan (jalur ketat: aturan uang); (c) satu tombol "lanjutkan sisa issue" yang menyiapkan rencana baru dan meminta persetujuan uang (jalur ketat: persetujuan di chat). **Dibangun 2026-11-21 (#651, spek `SPEC_QUEUE_MONEY`): job APPLIED dihitung sebesar biaya nyata; judge sesudahnya dihitung saat terjadi (bisa menambah sampai $0,30 per job di atas `max_usd`); kartu STOPPED memuat langkah berikutnya per penyebab. Tombol "lanjutkan sisa issue" tidak dibangun (ditunda sampai ada penghentian uang nyata).**

- [x] **`argus apply --accept-concerns "ALASAN"`** (Atha 2026-11-21, #650, `docs/reviews/SPEC_APPLY_ACCEPT_CONCERNS.md`): menerapkan patch yang dua pembacanya (dua id berbeda) salah satunya `concerns`, lewat semua cek apply lain; alasan 10-500 karakter dari manusia dicatat di log job, trailer commit `Accepted-concerns:` dan `argus status`. Hanya CLI, bukan tombol chat.
## Angka "bisa ditinggal": keputusan di tengah per issue (mulai 2026-11-22)

Ukuran usul Claude, diterima Atha 2026-11-22 ("Ok catat bro"), untuk titik cek 2026-11-29. **Definisi:** dari kemauan Atha sampai PR, hitung tiap keputusan yang diambil seseorang di tengah (bukan merge akhir, yang selalu Atha). Dicatat per langkah: siapa yang memutuskan, Atha (A) atau Claude (C). Sebuah issue disebut **bisa ditinggal** bila semua keputusan di tengahnya diambil mesin atau gerbang, tanpa Claude membaca atau menyetujui sesuatu. Alasan Atha: produk tetap tujuan utama; "belajar" hanya cara memandang supaya tidak frustrasi bila Argus lama jadi.

| Issue (bulking-app) | Keputusan di tengah | Siapa | Bisa ditinggal? |
|---|---|---|---|
| 1: tes `targetEngine` (PR #5, 2026-11-21) | prompt PRD, setuju uang antrean, jalan tulis tes tangan (draf ditolak gerbang), baca dan apply tangan, merge | Atha: prompt, uang, pilih jalan "A"; Claude: tulis tes, baca, apply; merge: Atha | tidak |
| 2: penjaga stabilitas TDEE (PR #6, 2026-11-22) | setuju prompt, setuju PRD dan uang, baca draf lalu approve draf, baca patch, apply, tes di image, push dan PR | Atha: prompt ("Run") dan uang ("Go sampai apply"); Claude: approve draf, baca patch (dua pembaca otomatis sepakat ok), apply, PR; merge: Atha | tidak |
| NEXUS-lite tahap 1 (3 issue, PR #1, 2026-11-22) | prompt, setujui rencana, kontradiksi sinkron/asinkron, 3 draf, 3 patch, 3 apply | Atha: prompt dan satu keputusan jalur (2); Claude: 2 tinjau PRD, 3 approve draf, 3 baca patch, 3 apply, temuan kontradiksi (12); gerbang: semua lolos | tidak |
| NEXUS-lite tahap 4 (5 issue UI/PWA, PR #4, 2026-11-22) | prompt PRD, 5 draf, 6 patch (issue 3 dua kali), 5 apply, pembaca terpotong, 402 | Atha: prompt, izin pembaca kedua, reject issue 3, naikkan batas key (4); Claude: tinjau PRD (2 kontradiksi), 6 approve draf, 6 baca patch, 5 apply, bukti keberatan pembaca keliru, diagnosis 402 yang awalnya salah; gerbang: semua lolos | tidak |

Catatan: angka pasti per langkah (berapa kali Atha dihubungi) belum dicatat otomatis; tabel ini dibuat dari ingatan sesi dan harus dibaca sebagai perkiraan. Keputusan yang masih memakai Claude: baca draf, baca patch, apply (T4b ditahan karena itu). Titik awal hari ini: **0 issue bisa ditinggal dari 2**; setelah NEXUS-lite tahap 1: **0 dari 5**; setelah tahap 4: **0 dari 10** (tahap 4: pembaca patch salah dua kali pada issue 3, satu kali terpotong pada issue 1, penyedia 402 tidak terbaca).

## Pilot bulking-app dan kemampuan Argus (2026-11-21)

- [x] **P2a: PRD dari chat** (#660) — rincian di `docs/reviews/PENDING_ARCHIVE_2026-11-22.md`.
- [x] **Pilot pertama bulking-app** (#656, #657) — rincian di `docs/reviews/PENDING_ARCHIVE_2026-11-22.md`.
- [x] **`argus apply` menolak tes baru yang cocok dengan `.argus/protected`** (#671) — rincian di `docs/reviews/PENDING_ARCHIVE_2026-11-22.md`.
- **Butir terbuka pilot bulking-app dan NEXUS-lite pindah ke PRIORITAS kategori H dan bagian 1 (2026-11-24).**
- [x] **T4a: tombol rencana di chat** (#663, #664) — rincian di `docs/reviews/PENDING_ARCHIVE_2026-11-22.md`.
- [x] **T3 ringan (3 baik + 3 cacat; hasil 4 dari 6, Atha lanjut)** — rincian di `docs/reviews/PENDING_ARCHIVE_2026-11-22.md`.
- [x] **Selesai (Atha 2026-11-21): PR #5 bulking-app merged; chip PRD dan tombol rencana dicoba dari HP; saldo DeepSeek untuk riset diisi** — rincian di `docs/reviews/PENDING_ARCHIVE_2026-11-22.md`.
- [x] **Pilot bulking-app issue 2: penjaga stabilitas TDEE adaptif** (2026-11-22; PR #6 bulking-app menunggu merge Atha; biaya sekitar $0,07) — rincian di `docs/reviews/PENDING_ARCHIVE_2026-11-22.md`.
- [x] **`argus apply` meng-commit ke cabang yang sedang aktif (main), tidak membuat cabang baru** (#674) — rincian di `docs/reviews/PENDING_ARCHIVE_2026-11-22.md`.
- [x] **Drafter menulis tes yang mustahil lulus** (pilot NEXUS-lite, `import(new URL(…, import.meta.url))` di jsdom jadi http:// dan ditolak; agen menghabiskan 30 langkah): satu pola ditutup di #684 (aturan prompt drafter + penolakan statis; tinjau Opus, mutan 17/17, `verify_at` PASS).
- [x] **A': agen berhenti pada laporan tes draf yang mustahil lulus, redraft setelahnya, re-approve sebagai `task2`** (2026-11-22, `aa99252`, `docs/reviews/SPEC_DRAFT_TEST_CONFLICT.md`; tinjau Opus GO WITH CHANGES dengan 9 temuan diterapkan, mutan 22 dari 22, regresi 1.023 lulus, `verify_at` PASS): menutup sebagian dua butir di bawah (percobaan kedua otomatis setelah `report_conflict`, dan redraft setelah agen gagal) untuk kasus "tes draf mustahil lulus". **Belum:** agen yang dihentikan manual masih tertinggal `AGENT_RUNNING`; laporan konflik tentang tes lama (bukan tes draf) tetap menjalankan percobaan kedua; green probe umum.
- [x] **Catatan hook (2026-11-21):** — rincian di `docs/reviews/PENDING_ARCHIVE_2026-11-22.md`.
- [x] **T6 PR1 (pengerasan builder, 2026-11-21, #670; spek T6 rev 1 di-merge sebagai catatan #668):** (#670, #668) — rincian di `docs/reviews/PENDING_ARCHIVE_2026-11-22.md`.
