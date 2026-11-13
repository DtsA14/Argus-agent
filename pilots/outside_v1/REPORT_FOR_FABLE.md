# Laporan 2026-11-12 sampai 13 untuk Fable: eksperimen repo luar, fase 3, dan batch kedua

Ditulis oleh Claude (Sonnet 5.5) untuk dibaca Fable, atas permintaan Atha. Isinya fakta dengan sumbernya, apa yang salah selama pengerjaan, dan **pertanyaan terbuka di bagian 8** yang butuh penilaian Fable. Semua angka disalin dari berkas di `pilots/outside_v0/`, `pilots/outside_v1/`, `verification/` dan dari `job.json` tiap job; yang tidak ada sumbernya ditandai sebagai dugaan. Penilaian buta batch kedua **sudah masuk** (Opus 5.5, bagian 10).

## 0. Ringkasan dalam delapan baris

1. **Eksperimen repo luar (batch 1, 10 issue boltons dan more-itertools):** 3 dari 10 instance cacat karena cara gue memilih commit dasar dan karena issue-nya sudah beres di dasar; dari **7 yang sah, 6 A dan 1 C** (nilai buta Fable 5.2, dikonfirmasi tes pemelihara untuk 5 dari 6; satu A hanya berdasar bacaan). Kasus terburuk 5 A dari 10, tepat di garis sukses. Biaya sekitar $1,9. Menit manusia per A **tidak terukur**.
2. **Fase 3 dibuka dan dikerjakan dalam sehari:** REPRO R1, FIX-C, RC `ReportConflict`, GATE, probe VF, dan O2. Semuanya ter-merge, masing-masing dengan mutan dan satu `verify_at` PASS, tanpa satu pun job nyata sebelum batch kedua.
3. **Probe VF membuktikan lubang D5:** forger yang menulis ke deskriptor stdout asli lolos validasi pytest. O2 (pola forger di gerbang deteksi) menutup sebagian di verdict, validasinya sendiri masih `pass`.
4. **Batch kedua (8 job, kontrol 3 + baru 5):** semua `REVIEW_READY`, semua 1 attempt, **nol** redraft, retry, `ReportConflict`, atau penghentian GATE. Tes pemelihara: **6 dari 8 resolved**, 2 tidak bisa dinilai dengan tes (boltons#322: nama API di issue beda dengan di fix; boltons#393: tes PR sudah lulus di dasar). Biaya total **$0,96**; judge menghabiskan sekitar **77%** uang itu. Waktu mesin rata-rata 2m06s per job (batch 1: 6m53s).
5. **Kontrol #1344 berbalik:** di batch 1 patch akhirnya salah (kunci panjang modulo 7, judge BLOCK, dua stage agen); di batch 2 resolved dalam satu attempt. Satu sampel: tidak bisa dibedakan antara efek harness atau prompt dan variasi acak.
6. **RC dan GATE belum pernah kena kasus nyata** (nol pemakaian, nol penghentian). Jadi tidak ada angka salah-tangkap atau salah-lapor; yang ada hanya bukti bahwa keduanya tidak merusak jalur normal pada 8 job.
7. **Pemeriksa validitas gue sendiri punya cacat** (menghitung tes milik PR lain sebagai bukti bahwa issue masih terbuka); ketahuan saat penilaian dan diperbaiki, dampaknya dua instance. Bagian 6.
8. **Delapan pertanyaan terbuka** di bagian 8; yang paling menentukan arah: (a) bagaimana membuktikan RC dan GATE tanpa kasus alami, (b) apa yang dilakukan dengan judge, (c) apa yang dihitung sebagai "pengawasan manusia" supaya klaim "tanpa pengawasan" bisa diuji.

## 1. Batch 1: eksperimen repo luar (sudah dilaporkan, diringkas)

Sumber: `pilots/outside_v0/PREFLIGHT.md`, `RESULT.md`. Sepuluh issue (boltons 5, more-itertools 5), dua batch kerja, harness beku, judge di tiap job, tiap draf yang diterima harness di-approve (verdict Claude dicatat dulu), biaya total sekitar $1,9.

| Hal | Hasil |
|---|---|
| Instance cacat | boltons#343 (PR di-merge dengan rebase, basis dari `merge^1` ternyata sudah memuat fix), #261 (repro sudah lolos di basis), #480 (repro sudah lolos di basis). Tiga-tiganya karena aturan pemilihan gue (PREFLIGHT), bukan Argus. |
| 7 sah | **6 A, 1 C** menurut penilai buta (Fable 5.2, sesi baru, dari paket acak, sebelum kunci dibuka). 5 A punya tes pemelihara yang gagal di dasar dan lulus dengan patch; boltons#439 A hanya berdasar bacaan (tes pemelihara tidak membedakan). C: more-itertools#1344 (kunci panjang modulo 7). |
| Garis protokol | kill 2 atau kurang A dari 10, sukses 5 atau lebih. Kasus terburuk (3 cacat dihitung gagal, #439 bukan A) = 5 dari 10. Setengah garis "10 menit manusia per A" **tidak terverifikasi**. |
| Biaya per A | sekitar $0,3 (batas $0,50). |
| Judge | PASS 4, NOT_JUDGED 5, BLOCK 1; PASS pada patch yang salah arah (boltons#480), BLOCK pada patch yang memang salah (#1344). |
| Pembacaan Claude sebelum approve | cocok dengan nilai buta di 9 dari 10; luput di boltons#343 (regresi pada metode publik `get_invocation_str`), dan untuk #1344 gue membaca rencana drafnya, bukan patch akhirnya. |

Temuan tentang Argus dari batch 1: (1) **tidak ada hasil "tidak bisa direproduksi"**: pada issue yang sudah beres Argus menulis perubahan lain dan lolos; (2) judge tidak bisa jadi gerbang; (3) pytest tanpa plugin tidak melaporkan kegagalan `subTest` (more-itertools#1344 dan #1275 tampak hijau; dinilai dengan `python -m unittest`).

## 2. Fase 3: apa yang dibangun (semua ter-merge ke `main`)

| Item | PR | Isi singkat | Bukti |
|---|---|---|---|
| REPRO R1 | #468, #469, #470 | contoh Python di issue dijalankan di commit dasar (sandbox, tanpa jaringan), hasil tampil di layar approve dan `status`: `ran clean, last output "..."`, `raised ...`, `not run (...)`. Hanya tampilan, tidak pernah menolak. `SPEC_REPRO_V0.md` | mutan 58/60 dan 59/60; `verify_at` PASS 3732 dan 3755 |
| FIX-C | #472 | `EventLog.emit` di-fsync (1,4 ms per event); `harness/redact.py`: nilai key yang diberikan ke klien disembunyikan di event dan `LLMCallFailed`. Bagian kedua D2 (baris rusak jadi galat) **sengaja tidak dikerjakan** dengan alasan di `SPEC_FIX_C.md`. Efek samping: fsync melebarkan balapan di simulasi crash (event `result_committed` saudara hilang); `CRASH_GRACE_S = 0.2` s hanya di jalur simulasi | mutan 27/27; `verify_at` PASS 3778 setelah satu putaran gagal |
| RC | #473 | tool `ReportConflict(files)`; `acceptance/conflict.py` memverifikasi dari bukti harness (semua kriteria non-validasi lulus, daftar merah lengkap, merah tepat di berkas yang disebut, berkas itu terlindungi dan tak disentuh dan bukan tes draf, tes wajib lain hijau, ada perubahan, baseline lulus di input, dua kali merah stabil di workspace, per validasi runner sendiri). Terkonfirmasi = `BLOCKED/test_conflict`, tak pernah pass. Gangguan sandbox dibedakan lewat nilai kembali. `retry --not-a-conflict` (hanya manusia). `SPEC_REPORT_CONFLICT_V3.md` disetujui Atha | mutan 77/77; `verify_at` PASS 3818 |
| GATE | #474 | hit `scope:no_test_detection` mengakhiri run (`FAILED_ACCEPTANCE/test_detection`), tak diumpankan ke agen, ditampilkan ke manusia (path, baris, pola, bukan teks baris). `SPEC_TEST_DETECTION_TERMINAL.md` | mutan 13/13; `verify_at` PASS 3852 |
| VF probe A10 | #475 | fixture forger, tes sandbox `xfail(strict)`, `SPEC_VF_CANARY.md`. **D5 terbukti** (bagian 3) | tidak ada perubahan harness |
| VF O2 | #477 | pola forger di gerbang deteksi: `os._exit(`, `os.abort(`, `os.kill(os.getpid()`, `os.write(1\|2,` dan `os.write(sys.stdout.fileno(),`, `S_ISFIFO`, `/proc/self`; Atha menerima false positive `os._exit` di kode produksi | mutan 18/18; `verify_at` PASS 3885 + 1 xfailed |

Proses yang dipakai tiap PR: tes yang gagal di kode lama, kode, `/code-review medium` (sub-agen), `/security-review`, mutan di worktree terpisah, satu `verify_at` sendirian, PR; PR jalur uang atau sandbox menunggu "merge" Atha. Sejak 2026-11-12 (usul Atha): **suite non-sandbox penuh dijalankan sebelum `verify_at`**.

## 3. Probe VF: lubang D5 terbukti (rinci)

Fixture `fixtures/forgers/pytest_pipe_forger`: satu tes yang merah dengan jujur (`f()` mengembalikan 2, tes menuntut 1), dan `src/app.py` yang saat diimpor menulis laporan pytest yang konsisten ke setiap pipa yang dipegang prosesnya, lalu `os._exit(0)`.

| Forger | Hasil |
|---|---|
| `sys.stdout.write(...)` lalu `os._exit(0)` | gagal ("no pytest summary"): pytest menangkap sys.stdout dan fd 1 saat impor |
| tulis ke deskriptor asli (pipa yang tersisa) | **lolos**: `pass`, `tests_run 1`, `outcome OK`, `consistent True`, `must_pass ok`, `exit_code 0` (environment `ledger_py312_up2` dan `argus`) |

Konsekuensi: `DONE` dan `REVIEW_READY` bukan bukti perilaku bagi agen yang sengaja memalsukan. Yang masih melindungi: manusia membaca patch, gerbang deteksi (O2 menutup dua bentuk ini di verdict), hakim, dan penilaian eksperimen luar lewat tes pemelihara di sandbox terpisah. Belum ada contoh forger sungguhan di data kita. O1 (kanari dan nonce) belum dikerjakan; manfaatnya terbatas pada forger yang tidak menarget kanari.

## 4. Batch 2: rancangan

Sumber: `pilots/outside_v1/PREFLIGHT.md` (dibekukan di #479 sebelum job pertama). Delapan job, `--max-usd 1.00` tiap job, cap batch $6, harness beku, judge di tiap job (sebagai data), aturan sama dengan batch 1 (satu redraft, satu retry, setiap draf yang diterima harness di-approve).

* **Kontrol (3):** issue sah dari batch 1 dengan dasar yang sama (more-itertools#1304 dulu A, #1344 dulu C, boltons#383 dulu A), untuk melihat apakah prompt dan harness baru menggeser hasil.
* **Baru (5), aturan mekanis:** ditutup oleh PR ter-merge di repo yang sama, ditutup sejak 2025-11-12, bukan satu dari sepuluh batch 1 dan bukan PR yang sama dengan mereka; tes dan sumber ada, diff sumber paling 150, tanpa konfigurasi dependensi, satu issue per PR; **dasar = induk dari commit pertama PR** (pelajaran #343); **valid = ada tes pemelihara yang gagal di dasar dan lulus di fix** (`validity.py`, dijalankan di sandbox, isinya tidak dibaca); paling baru per repo: more-itertools#1284, #1277, #1257 dan boltons#393, #322 (hanya dua yang memenuhi syarat di boltons).
* Dicatat sebelum job: baris R1 per job, pemakaian `ReportConflict`, penghentian GATE (dengan pembacaan Claude: tangkapan benar atau salah), pemakaian `--not-a-conflict`, perbandingan kontrol dengan batch 1, biaya, menit manusia.

## 5. Batch 2: hasil per job

Waktu dari `job.json` (resolusi detik; `mesin` = draft + agen; `dinding` = job dibuat sampai tahap terakhir selesai, termasuk judge). Biaya dari ledger job (status setelah judge). "Tes pemelihara" = tes dari PR fix itu, di sandbox, dengan F2P dibatasi pada fungsi tes yang **ditambahkan PR itu** (lihat bagian 6).

| Job | Jenis | Draf, attempt | R1 (isi baris) | Judge | Biaya | Tes pemelihara | Mesin / dinding |
|---|---|---|---|---|---|---|---|
| more-itertools#1284 (bucket, kunci hantu) | baru | 1, 1 | `not run` (tiga blok sesi `>>>`; alasan sama diulang tiga kali) | NOT_JUDGED | $0,169 | **resolved** (F2P 4/4, P2P 609/609) | 1m46s / 11m26s |
| more-itertools#1277 (`zip_broadcast` membuka dua kali) | baru | 1, 1 | `raised RuntimeError: input already opened` (bug tereproduksi) | PASS | $0,044 | **resolved** (1/1, 604/604) | 1m58s / 4m35s |
| more-itertools#1257 (`None` dikira habis) | baru | 1, 1 | `ran clean, last output "1"` (itu justru bug: seharusnya `ValueError`) | PASS | $0,150 | **resolved** (2/2, 600/600) | 1m59s / 5m03s |
| boltons#393 (`research` pada tuple identik) | baru | 1, 1 | `ran clean` (tak informatif: contoh hanya mendefinisikan fungsi tes) | PASS | $0,162 | **tidak ada sinyal**: tes baru PR (`test_research_custom_enter`) sudah lulus di dasar; P2P 40/40 | 2m56s / 12m05s |
| boltons#322 (`human_list`, fitur) | baru | 1, 1 | `not run` (sesi `>>>`) | PASS | $0,055 | **tidak bisa dinilai**: issue menyebut `human_list`, tes pemelihara mengimpor nama lain (disimpulkan dari nama tesnya `test_human_readable_list` dan dari 0 tes terkumpul; isi fix tidak dibaca) | 2m04s / 3m50s |
| more-itertools#1304 | kontrol (dulu A) | 1, 1 | `raised ValueError: Stop argument for islice()...` | PASS | $0,099 | **resolved** (2/2, 617/617) | 1m30s / 6m47s |
| more-itertools#1344 | kontrol (dulu **C**) | 1, **1** (dulu 1, lalu retry) | `raised OverflowError` | NOT_JUDGED | $0,179 | **resolved** (2/2, 624/624) (dulu: gagal tes hash) | 2m11s / 11m53s |
| boltons#383 | kontrol (dulu A) | 1, 1 | `no runnable example in the issue` | PASS | $0,100 | **resolved** (2/2, 6/6) | 2m27s / 7m13s |

Total: biaya **$0,958**, waktu mesin 16m51s, dinding 62m52s. Rata-rata per job: draft 1m23s, agen 0m44s, judge 5m20s, mesin 2m06s, dinding 7m52s (batch 1: mesin 6m53s, dinding 16m48s; rata-rata batch 1 ditarik satu job, #1344, dengan 29m45s mesin karena dua stage agen). Rincian biaya (dari catatan tiap stage): drafter sekitar $0,15 total (sekitar 2,4 kali biaya agen; $0,01 sampai $0,03 per job), agen sekitar $0,06 total ($0,003 sampai $0,02 per job), **judge sekitar $0,74 (77%)**. Judge: PASS 6, NOT_JUDGED 2 (batch 1: PASS 4, NOT_JUDGED 5, BLOCK 1).

Pembacaan Claude **sebelum approve** (hanya rencana drafnya, bukan patch akhir): kedelapan on-target. Catatan: pada batch 1 pembacaan rencana tidak cukup untuk #1344. Nilai buta batch 2: bagian 10.

**Pemakaian fitur baru pada 8 job:** `ReportConflict` 0, penghentian GATE 0, `--not-a-conflict` 0, redraft 0, retry 0, `NO_DRAFT` 0. R1: `raised` 3 (#1277, #1304, #1344), `ran clean` 2 (#1257, #393), `not run` karena `>>>` 2 (#1284, #322), tanpa contoh 1 (#383). Kegunaan R1 saat approve **belum dinilai Atha** (gue yang meng-approve; menit Atha di batch ini hanya keputusan "go live" dan pesan-pesannya).

## 6. Kesalahan dan cacat selama pengerjaan (jujur)

1. **Aturan pemilihan batch 1:** dasar dari `merge^1` salah untuk PR yang di-merge dengan rebase (#343), dan issue yang sudah beres di dasar tidak digugurkan (#261, #480). Diperbaiki di PREFLIGHT batch 2.
2. **Pembacaan gue luput** untuk boltons#343 (regresi API publik) dan untuk #1344 gue membaca rencana, bukan patch akhir.
3. **Pemeriksa validitas batch 2 cacat:** `validity.py` menjalankan semua berkas tes yang berubah antara dasar dan merge, dan basis lebih tua dari ujung `master`; tes milik PR lain pada berkas yang sama dihitung sebagai bukti "issue masih terbuka". Ketahuan saat penilaian: dua instance tidak lolos kriteria yang benar. Yang sudah dibekukan di PREFLIGHT mengklaim "semua 15 kandidat valid"; **klaim itu salah untuk boltons#393 (F2P sebenarnya 0)** dan boltons#322 lolos pemeriksaan tetapi tak bisa dinilai karena nama API.
4. **`verify_at` terbuang dua kali** (FIX-C: balapan fsync di simulasi crash; GATE: skrip mutan bernama `test_*.py` dikoleksi pytest), sekitar 40 menit; Atha mengusulkan kembali ke suite non-sandbox dulu (dicatat di memori).
5. **#475 di-merge tanpa suite penuh**, dan tes penjaga xdist `test_xdist_groups.py` belum mengenal modul sandbox barunya, jadi `main` merah di suite non-sandbox sampai #477 memperbaikinya.
6. **R1:** (a) `python -I` tak mengenali `/workspace` (semua contoh gagal `ModuleNotFoundError`), ketemu saat uji nyata; (b) setelah dipakai nyata terlihat alasan "not run" diulang per blok (UX), dan "ran clean" ambigu (#1257: clean = bug; #393: tak informatif).
7. **Batas yang sudah diketahui dan diterima:** pemindaian per baris di gerbang; red check pada kode agen bisa dimanipulasi agen untuk "membuat" konflik (hasilnya hanya berhenti ke manusia); forger yang menyamarkan panggilan; O1 belum ada.

## 7. Yang belum dikerjakan

* ~~Penilaian buta batch 2~~: sudah masuk (bagian 10).
* Pembacaan Claude atas patch akhir batch 2 (hanya rencana yang dibaca).
* R2 `ReportNoRepro` (butuh data R1; sekarang ada 8 baris R1 pertama), RC bagian (b) (`redraft --from-conflict`, state `CONFLICT`, gerbang approve), VF O1.
* Menit Atha per job; "go live" menunggu Atha tiap batch.

## 8. Pertanyaan terbuka untuk Fable

**P1. Bagaimana membuktikan RC dan GATE tanpa kasus alami?** Dua batch (18 job) belum pernah memicu `ReportConflict` atau penghentian GATE. Delapan job lagi kemungkinan sama. Pilihan: (a) menunggu kasus alami (bisa lama), (b) menyiapkan issue sintetis dengan tes lama yang benar-benar bertentangan (misalnya fitur yang mengubah bentuk keluaran yang dikunci tes lama; ada contoh nyata di `chain_probe`), (c) uji gerbang dengan "tawaran menggoda" (issue yang jelas mendorong deteksi pytest). Mana yang menurut Fable memberi bukti yang jujur tanpa menjadi tes yang gue tulis agar lolos sendiri? Dan berapa banyak yang cukup untuk bilang apa-apa tentang tingkat salah-tangkap/salah-lapor?

**P2. Apa yang dilakukan dengan judge?** Biaya 77% dari uang, NOT_JUDGED 7 dari 18 job, PASS pada patch salah (boltons#480) dan BLOCK pada patch salah (#1344) di batch 1; di batch 2 PASS 6 dan NOT_JUDGED 2, tanpa pembanding sampai penilaian buta masuk. Opsi: tetap sebagai data, dimatikan default (hemat sekitar $0,09 per job), diganti sesuatu yang murah dan lebih informatif (misalnya menampilkan R1 dan hasil tes baru draf, bukan penilaian model), atau diperbaiki penyebab NOT_JUDGED. Apa yang akan Fable lakukan, dan data apa yang masih perlu?

**P3. Apakah kontrol yang berbalik berarti sesuatu?** #1344: dulu C (retry, dua stage agen, judge BLOCK), sekarang resolved dalam satu attempt. Satu sampel. Berapa pengulangan kontrol yang cukup untuk memisahkan efek harness/prompt dari variasi acak (biaya sekitar $0,15 per job, 5 pengulangan x 3 kontrol sekitar $2,3)? Atau lebih baik tidak membaca apa pun dari kontrol dan memperlakukannya hanya sebagai regresi (tidak ada yang memburuk)?

**P4. Perbaikan aturan validitas.** Dua instance dari lima baru tidak bisa dinilai dengan tes (nama API di issue beda dengan di fix; tes baru PR sudah lulus di dasar). Apakah aturan "F2P dibatasi pada tes yang ditambahkan PR itu" cukup, dan apakah instance fitur (issue menyebut API tapi fix memakai nama lain) harus dikeluarkan secara mekanis (misalnya: tes pemelihara tidak boleh gagal di impor pada pohon dasar yang ditambah jawaban yang mengikuti issue, tidak bisa dicek tanpa jawaban), atau diterima sebagai keterbatasan dan dinilai hanya dengan rubrik? Bagaimana mendeteksi "tes tidak membedakan" (bo-393, #439 di batch 1) sejak awal, sebelum memilih issue?

**P5. R1: lanjutkan, ubah, atau hentikan?** Data pertama: 8 baris; 3 `raised` yang jelas berguna, 2 `ran clean` yang ambigu, 2 `not run` karena sesi `>>>`, 1 tanpa contoh. Pertanyaan produk: apakah menampilkan **nilai yang diharapkan issue** (misalnya komentar `# expected ...` atau blok `>>>`) di samping keluaran sudah cukup, atau itu pekerjaan model (R2)? Apakah sesi `>>>` (doctest) layak dijalankan (extractor doctest)? Dan syarat apa pada data yang membuka R2 (`ReportNoRepro`, yang mengubah masukan drafter)?

**P6. Bagaimana mengukur "pengawasan manusia"?** Klaim yang ingin diuji produk ini adalah mengurangi pengawasan. Menit Atha per job hanya terukur kasar sejauh ini; di batch 2 sebenarnya hampir nol karena gue meng-approve atas dasar bacaan sendiri (berarti "pengawasan" dilakukan model yang sama yang menulis). Apa ukuran yang bisa diaudit: menit Atha untuk approve dan membaca patch, jumlah keputusan, atau tingkat patch yang Atha tolak setelah gue setujui? Dan bagaimana menghindari bahwa gue (yang menulis dan meng-review) menjadi satu-satunya pengawas?

**P7. Penilai buta: independensi dan biaya.** Nilai buta sejauh ini dari Fable 5.2 (satu model). Apakah cukup, atau perlu penilai kedua (model lain atau manusia) untuk sebagian sampel untuk menghitung kesepakatan? Rubrik A/B/C dari protokol juga tidak mengukur "dibaca manusia 10 menit"; haruskah B didefinisikan ulang?

**P8. Kontaminasi data latih.** Semua issue ditutup Des 2025 sampai Okt 2026. Model DeepSeek (drafter dan agen) mungkin pernah melihat sebagian. Apakah layak menyaring issue yang ditutup **sesudah** batas pengetahuan model yang dipakai (batas DeepSeek yang dipakai belum gue periksa; ini dugaan yang perlu diverifikasi), atau mengganti sebagian dengan issue yang ditulis sesudah batch ini dijalankan, supaya hasil tidak bisa karena hafalan?

**Hal yang gue minta Fable periksa langsung (bukan pertanyaan terbuka):** (a) apakah verifikasi `acceptance/conflict.py` memuat satu lubang yang gue tidak lihat (khususnya agen yang membuat tes lama merah hanya di bawah invokasi red check milik harness; gue mencatatnya sebagai batas yang diterima); (b) apakah pola O2 punya false positive yang terlewat pada repo yang kita tangani (boltons, more-itertools, ledger, viewer); (c) apakah redaksi FIX-C melewatkan jalur teks error yang tidak lewat `EventLog` atau `LLMCallFailed` (mis. `job.json` stop_reason dari pengecualian lain).

## 10. Penilaian buta batch 2 (Opus 5.5, sesi baru, paket acak Q01-Q08, sebelum kunci dibuka) dan temuan cacat harness

| Patch | Job | Nilai buta | Alasan penilai (ringkas) | Tes pemelihara |
|---|---|---|---|---|
| Q01 | boltons#322 (`human_list`, fitur) | **B** | nama dan signature sesuai issue; tes di root repo dan pembungkus yang mengubah exception jadi AssertionError, perlu dirapikan | tidak bisa dinilai (nama API fix beda) |
| Q02 | boltons#393 (`research`) | **C** | menulis ulang `research` jadi traversal manual (±50 baris) tanpa `remap`: deteksi loop lewat ancestors, objek bersama bisa ditelusuri berkali-kali (dapat meledak eksponensial), `new_parent` dari `enter` diabaikan; perubahan besar dan menyentuh logika | tidak ada sinyal (tes PR lulus di dasar) |
| Q03 | more-itertools#1304 (kontrol) | B | perbaikan benar; perubahan mode `more.py` yang tak terkait; tes di berkas baru, bukan di `IchunkedTests` | resolved 2/2 |
| Q04 | more-itertools#1344 (kontrol, dulu C) | B | `_len` di `__eq__` dan `__hash__` persis usulan issue; `len()` langsung tetap `OverflowError`; satu-satunya cacat: perubahan mode | resolved 2/2 |
| Q05 | boltons#383 (kontrol) | **A** | `os.fspath` di `AtomicSaver`, `iter_find_files`, `copy_tree`, `rotate_file`; terbatas pada PathLike; catatan kecil (satu baris docstring panjang, dua fungsi tak dites) | resolved 2/2 |
| Q06 | more-itertools#1277 | B | iterator pengecekan skalar disimpan dan dipakai ulang; hanya perubahan mode | resolved 1/1 |
| Q07 | more-itertools#1284 | B | `_cache` jadi `dict` biasa, kunci didaftar hanya bila item terlihat; perubahan mode | resolved 4/4 |
| Q08 | more-itertools#1257 | B | `y is None` diganti `len(indexes) == l` seperti usul issue; perubahan minimal; hanya perubahan mode | resolved 2/2 |

Hitungan mentah: **A 1, B 6, C 1**. Patch pertama dan batch 1 untuk kontrol yang sama: #1304 dulu A, #1344 dulu C, boltons#383 dulu A.

**Temuan cacat harness (diverifikasi, belum diperbaiki): editan agen menghilangkan bit eksekusi.** Lima dari lima patch more-itertools (kedua batch) membawa `old mode 100755 / new mode 100644` untuk `more_itertools/more.py`; ketiga patch boltons tidak (di upstream `boltons/*.py` mode 100644, `more.py` 100755). Sebabnya: `tools/fs.py` `PathJail.write_text` menulis berkas sementara dengan mode `0o644` lalu `os.replace`, jadi mode berkas yang diedit hilang. Akibat: patch menyertakan perubahan mode yang tak terkait bila diterapkan ke repo, dan penilai yang teliti mengurangi nilainya (Opus: B untuk lima patch, alasan utamanya hanya ini; Fable di batch 1 menganggapnya artefak dan mengabaikannya). Bila artefak ini diabaikan: Q03 sampai Q08 yang memenuhi A (Q03 tertahan hanya soal letak tes), dan hitungan menjadi **A 6, B 1 (Q01), C 1 (Q02)**. Claim ini adalah **dugaan yang perlu diverifikasi oleh orang yang membaca patch lagi**: gue hanya mengambil alasan penilai, bukan membaca ulang kelima patch.

Catatan interpretasi: (1) kedua patch yang bukan A/B-karena-mode ada di boltons: Q01 (fitur, API cocok issue, tes gagal impor di sisi pemelihara) dan Q02 (C: perubahan logika besar); (2) pada batch 2 pembacaan rencana oleh gue ("semua on-target") tidak menangkap Q02: rencana drafnya masuk akal, patch akhirnya menulis ulang traversal. Ini kasus kedua (setelah #1344 batch 1) di mana membaca rencana tidak cukup; (3) judge memberi PASS pada Q02 (boltons#393).

### Pertanyaan tambahan

**P9. Apakah artefak yang jelas dari harness (mode berkas) dihitung dalam nilai buta?** Penilai batch 1 mengabaikannya, penilai batch 2 menghitungnya; hasilnya A 1 versus A 6 dari patch yang sama. Aturan apa yang harus ditulis di rubrik supaya konsisten (misalnya: patch dibersihkan dari artefak harness dulu, atau artefak dihitung sebagai cacat Argus karena manusia yang menerapkan patch akan melihatnya)? Sementara itu cacat sumbernya (`write_text` menimpa mode) layak diperbaiki lebih dulu supaya pertanyaannya hilang di batch berikutnya.

## 9. Berkas

`pilots/outside_v0/` (PREFLIGHT, RESULT, skrip penilaian), `pilots/outside_v1/` (PREFLIGHT, `candidates.jsonl`, `validity.jsonl`, skrip, `jobs_summary.json`, `claude_preapprove_verdicts.txt`, `pr_test_names.json`, `grades/` keluaran penilaian tes per job, `TIMES_batch1.txt`, `TIMES_batch2.txt`, laporan ini), spek di `docs/reviews/` (`SPEC_REPRO_V0`, `SPEC_FIX_C`, `SPEC_REPORT_CONFLICT_V3`, `SPEC_TEST_DETECTION_TERMINAL`, `SPEC_VF_CANARY`), bukti `verify_at` dan mutan di `verification/`, papan status di `docs/reviews/FABLE_REVIEW_2026-11-11.md` bagian 0 dan `PENDING.md`.
