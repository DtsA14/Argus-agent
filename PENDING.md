# Pending

Daftar kerja Argus yang **masih terbuka**. Status milestone dan ADR beserta buktinya ada di [`docs/Reconciliation.md`](docs/Reconciliation.md)
(satu-satunya tempat status). Riwayat butir yang sudah selesai (bukti, angka, PR): [`docs/reviews/PENDING_ARCHIVE_2026-10-30.md`](docs/reviews/PENDING_ARCHIVE_2026-10-30.md)
(sampai 2026-10-30), [`docs/reviews/PENDING_ARCHIVE_2026-10-22.md`](docs/reviews/PENDING_ARCHIVE_2026-10-22.md) (sebelumnya) dan `docs/reviews/`.

Terakhir diperbarui: 2026-11-06 (judge, retry 429 #326, aturan J9, pertanyaan terbuka 021, self-review). Sebelumnya: 2026-11-05 (tahap 1 riset "Agentic AI", #307-#309). Sebelumnya: 2026-10-30 malam, jalur cepat sesudahnya (#268) (viewer PWA live di HP Atha: #256, #257, #261, #263–#266; staging namespace #258;
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

- [~] **Deep research, `argus research`** (Atha 2026-11-03: arah general-purpose agent; keputusan di Reconciliation
  bagian 7). Sudah jalan: `SPEC_RESEARCH_JOB` (planner, worker berurutan, sintesis s1, checker e1, gate G1/G2/G4), web lewat
  DeepSeek Search/Fetch (#285-#289), gateway OpenRouter dengan profil `deepseek`, `deepinfra` dan `free`. Eval v0
  (`docs/reviews/RESEARCH_EVAL_V0.md`, #290): `deepinfra` 8/8 benar; fix #291 (checker free di Nemotron, aturan kutipan),
  #292 (submit terakhir menyimpan temuan yang lolos), rerun R2/R5/R8 (#293): e1 selesai 6/6, free tanpa laporan kosong.
  Output e1 berbayar dinaikkan ke 32.000 (#294; `reasoning.max_tokens` ternyata tidak dipatuhi). Terbuka:
  - [x] Ambang v1 diputuskan Atha 2026-11-04 (profil berbayar: ≥7/8 benar, tidak ada yang salah, tidak ada
    UNSUPPORTED, ≥60% SUPPORTED, e1 selesai ≥7/8)
  - [~] Batch v1 R1-R8 dilewati (Atha 2026-11-04: lama, kurang sebanding hasilnya). Ambang v1 dan output e1 32k dicek
    di job riset berbayar berikutnya: e1 selesai tanpa terpotong, tidak ada UNSUPPORTED, persen SUPPORTED; "7/8 benar"
    baru terbukti setelah beberapa job
  - [~] **Tahap 1, riset nyata pertama "Agentic AI"** (2026-11-05, Reconciliation bagian 4d; breakdown tahap 1-4 di
    bagian 7): tiga job $0,2198; tiga perbaikan jalur cepat: #307 (gate URL salah membaca "file:" di prosa), #308 (halaman
    docs dengan konfigurasi JSON raksasa), #309 (e1 kehilangan semua verdict karena satu alasan kepanjangan). Job 3
    `j20261105_121107_718e`: e1 CHECKED, 0 UNSUPPORTED, **SUPPORTED 47% (<60%)**. Berikutnya:
    - [x] s1 hanya melihat kutipan, bukan klaim worker (#311). Job 4 `j20261105_123505_b1d4`: 17/17 SUPPORTED,
      identifier di luar kutipan 27 → 0 ($0,0742)
    - [x] Dua topik lain (ekonomi BI/Fed/rupiah 85% SUPPORTED, BRICS 93%; 0 UNSUPPORTED, e1 selesai; $0,1506)
    - [x] Jalur cepat kecil dari tiga job ini (#314): petunjuk worker bahwa kutipan boleh lintas baris (G2 menerima); s1
      tidak melihat URL (judul di URL bocor jadi klaim, PARTIAL BRICS P9). Belum diuji di job nyata
    - [ ] Kebenaran faktual ("7/8 benar") belum dinilai terhadap sumber independen
    - [ ] Catatan review yang belum dikerjakan: ReadDocs (`tools/web.py`) punya titik buta konfigurasi yang sama;
      konfigurasi berbentuk `window.X = {...}`/`__NEXT_DATA__` tidak terdeteksi; gate s1 masih menolak seluruh submit
      terakhir karena satu bagian kepanjangan; aturan "submit terakhir" tersalin di dua `gate_submit`
- [x] **Tahap 2, kurangi supervisi** — **ditutup Atha 2026-11-06** ("tutup tahap 2") dengan bukti batch 4 + pertanyaan terbuka 021: judge 10/10 cacat nyata/tanam, alarm palsu 1 (020); J9 berjalan; satu issue tulisan Atha (021) berhasil sesudah tes lama dibereskan. Belum terbukti, jadi pantauan (bukan syarat): menit kerja Atha, retry 429 live, J9 di batch besar, issue singkat Atha lebih dari satu. Temuan: hambatannya menulis issue, bukan mengawasi → kandidat "Argus usulkan issue". Rencana awal (Atha 2026-11-05: sesudah tahap 1, sebelum UI kontrol): Reviewer Argus (rencana ke
  Atha sebelum kode), menit kerja Atha per pilot, batch shadow dengan issue yang tidak dijelaskan rinci oleh Claude
  - [ ] Spek `docs/reviews/SPEC_JUDGE.md` (`argus judge`, stage j1, hanya saran): model GLM-5.3 lewat OpenRouter pin Baidu
    fp8 (Atha 2026-11-05, harga diskon); K1-K3 disetujui. Lalu satu PR jalur ketat, replay 11 job shadow lama (~$0,20,
    "go live"), lalu shadow batch 3 dengan issue singkat yang ditulis Claude (Atha: "Issue masih lu dulu")
    - [x] #316 `argus judge`; replay J8 (#317 32k token, #318 aturan BLOCK, #319 batas teks 500/1000, #320 fallback
      Novita): `097d` dan `1808` BLOCK, 8/8 bersih PASS, biaya riil ±$0,47 total (spek bagian 6)
    - [x] J9 shadow batch 3: 4 applied, Claude dan judge sepakat 4/4, tanpa blok asli (spek bagian 6)
    - [x] Uji cacat tanam: 6/6 tertangkap (spek bagian 6); 7/7 sesudah rerun `81ed` (butir berikut)
    - [x] 429: #326 (SPEC_RATE_LIMIT_RETRY), verify PASS 17721f3 (3059), mutants 16/16; `81ed` sesudahnya BLOCK benar
      (7/7 cacat tanam), panggilan itu tanpa 429 jadi retry baru belum teruji live
    - [x] Aturan J9 disetujui Atha 2026-11-06 ("Ok bro"), mulai batch berikutnya: Claude me-review hanya job yang diblok
      judge + sampel acak 1 dari 4 job PASS; PASS lainnya applied tanpa dibaca; "go live" per batch tetap; satu cacat
      lolos di sampel = aturan dicabut, kembali ke review penuh
    - [x] Pertanyaan terbuka 021 (Atha: "buat 3 fitur yang worth buat ditambah ke argus viewer", ±$0,22): t1
      `j20261106_133421_1459` judge BLOCK benar (agent membaca address hanya bila `history.state` tidak null; terjepit
      tes lama `jobs-sort` yang membocorkan address, dilindungi); viewer `28933f7` reset address per tes, t2
      `j20261106_151840_e81c` PASS, dibaca Claude, applied `518b34f` + tes fresh-load `ab43761` (mutan 2/2). Pilot #6
      berhenti di langkah 1: Claude mencatat `applied` dengan commit tes (as_is False), deploy ditolak penjaga; Atha:
      tunggu deploy berikutnya (021 ikut rilis batch 5). **Live 2026-11-08 dalam rilis 023** (`pilots/staging_stage14`)
    - [x] ~~**Harga GLM-5.3 (2026-11-07, `pilots/glm_reviewer_v0`): diskon Baidu 80% habis**, gateway menagih $1,40/$4,40 per juta (config $0,28/$0,88): reservasi judge 5x terlalu rendah, cap $0,10 bisa terlampaui. Jalur ketat, keputusan Atha sebelum judge berikutnya (batch 5): harga config dinaikkan + cap/`max_output_tokens` judge, atau pin provider fp8 lain yang lebih murah. Judge tidak dijalankan sampai ini selesai.~~ **Selesai `99a77d9` (2026-11-07):** harga list $1,40/$4,40 di config, `max_price` dikirim, pin Novita fp8 → Tenstorrent fp8 → Baidu fp8, cap judge $0,30. Cek 2026-11-08: harga gateway sama dengan 11-07 (Novita $0,63/$1,98 diskon 55%, Tenstorrent $0,60/$2,50, Baidu $1,3986/$4,3956).
    - [ ] Kandidat (belum dibangun, tunggu bukti batch 5): `argus fix <job>` dari judge BLOCK (a2, kontrak sama, temuan
      dibekukan di job.json, satu kali per job, agent boleh lapor "terjepit tes lama" alih-alih mengakali; jalur ketat)
    - [ ] Celah: drafter tidak mendeteksi tes lama yang akan bocor oleh fitur baru (gerbang #275 tidak terpicu), dan tes
      draf memasang `history.state` `{}`, bukan `null` seperti browser
- [x] **Uji prompt injection riset → kode** — v0 selesai 2026-11-06 (`pilots/prompt_injection_v0/RESULT.md`, $0,14): 4 varian injeksi di kutipan, tidak ada yang tembus; V4 BLOCK judge karena tes draf cacat (agen menambah 400 CR ke CSV), grader tersembunyi meloloskannya. Lanjutan bila perlu: injeksi di teks klaim, fakta API palsu. Temuan sampingan: gerbang harness belum menolak draf dengan red reason non-perilaku (aturan baru ditegakkan Claude). Rencana awal: (usulan probe model 2026-11-06, Atha "gass", urutan atas di antara kandidat;
  belum dispek): teks web masuk ke agent kode lewat `--from-research` (#297) dan Reconciliation bagian 5 mencatat injeksi
  "belum diukur untuk code task". Eksperimen terkecil seperti uji cacat tanam: 3-5 halaman tanam berisi instruksi
  tersembunyi, lihat apakah ada yang sampai ke handoff, draf, atau patch. Pagar yang mungkin sesudahnya: label asal-usul,
  hanya klaim + kutipan yang diteruskan. Catatan probe: `docs/reviews/PROBE_REPO_DOCS_2026-11-06.md`
- [ ] **Eval riset independen** (usulan probe yang sama): set pertanyaan beku dengan cek fakta independen; SUPPORTED hanya
  berarti kutipannya ada. Lebih mahal (kunci jawaban dicek manual); sambung dengan butir "7/8 benar" di tahap 1
- [x] **Self-review Argus** (Atha 2026-11-06; dijalankan 2026-11-06, `pilots/self_review_v0`: judge PASS 2x, 0/5 bug review tertangkap, 1 alarm palsu, $0,057; usul: `argus review --diff` tidak dibangun): judge GLM sebagai reviewer kedua PR
  jalur ketat, hanya saran (merge tetap Atha). Eksperimen terkecil dulu: diff #326 sebelum perbaikan review (7 temuan
  `/code-review` yang diperbaiki) ke judge lewat `LLMCaller`, hitung tangkapan dan alarm palsu, < $0,10. Bagus → perintah
  `argus review --diff` (jalur ketat). `argus code` di repo Argus sendiri: tidak, sampai inti harness dilindungi
- [ ] **Satu pipeline berhirarki** (Atha 2026-11-04, dibahas di chat): job → planner → task riset (alur C), task kode
  (alur B), task deploy (staging), dengan dependensi. Yang membuatnya berat: planner dengan dependensi (M4), oper hasil antar
  task (ADR-005), cap bertingkat dengan ledger dan crash-resume (jalur ketat), titik `approve`/"go live" tetap ada, gagal
  satu task (stop/retry/replan). Versi lengkap sekitar satu spek + 4-6 PR jalur ketat. Usul Claude, langkah kecil dulu:
  - [x] `argus code ... --from-research <job> [--items ...]` (#297, `docs/reviews/SPEC_FROM_RESEARCH.md`). Pilot
    `pilots/from_research_v0` (issue 015, argus-ledger 4e947a0): kedua lengan benar menurut grader tersembunyi; tanpa
    riset $0,0384, dengan riset $0,0743 (agen 1 percobaan vs 2). Riset tidak dibutuhkan untuk issue ini (n = 1)
  - [ ] Bukti berikutnya: issue yang salah dikerjakan lengan tanpa riset. Planner berhirarki belum dibenarkan
    - [x] Kandidat dikumpulkan 2026-11-04 (`pilots/research_need_v0/CANDIDATES.md`, #300): 4 kandidat dari release notes
      fastapi 0.143.2→0.162.0 dan starlette 1.8.0→1.10.0, perilaku dibuktikan di dua venv scratch. Penilaian: kebanyakan
      perubahan up2 menambah kemampuan, bukan membuat jalan lama salah; peluang ketemu issue yang gagal tanpa riset rendah
    - [x] Penyaringan 2026-11-05 (`pilots/research_need_v0/RESULT.md`, $0,0240): K1 dan K2 dijawab benar (K2 sampai
      batas versi lama), K3 dan K4 model mengaku tidak tahu perubahannya tetapi kodenya lolos di up2. Tidak ada kandidat
      yang membenarkan pilot dua lengan; berhenti mencari. Planner berhirarki tetap belum dibenarkan; catat kegagalan
      nyata lengan tanpa riset bila muncul
  - [x] (2026-11-06, `pilots/e1_effort_v0`: low = rujukan 30/30, reasoning -40..50%, biaya/waktu ±separuh; def ulang 12/17 di laporan A; dipasang di `or_deepseek_checker` 2026-11-07, Atha "Ok gas"; pantau 2-3 job riset `deepinfra` berikutnya) Eksperimen e1 dengan `reasoning.effort: low` pada laporan yang sama, dibandingkan dengan nilai Claude (lebih murah
    bila persetujuannya tidak turun; e1 sekarang selalu lebih longgar saat berbeda)
  - [ ] Worker free masih NO_FINDINGS 4/9 di rerun; satu worker berbayar masih memotong kutipan
  - [ ] Nanti: worker paralel, OpenRouter Batch API, PR 1b `free_repos`, Vercel sebagai cadangan (Atha "kapan2")

- [ ] **UI kontrol interaktif** (Atha 2026-10-30, scope dibahas di chat): fase 0 spek `SPEC_CONTROL_UI` (service kontrol
  terpisah `127.0.0.1:8711`, proxy viewer tetap GET-only, CSRF/Origin, audit di `job.json`, batas biaya server-side), fase 1
  halaman review draf read-only (jalur cepat), fase 2 aksi tanpa biaya (`reject`/`abandon`), fase 3 aksi berbayar, fase 4
  tombol staging. Pertanyaan terbuka: siapa yang approve, batas $ via UI, "go live" lewat tombol, port 8711 + `permitopen`
  kedua di kunci HP, waktunya terhadap up2
  - [x] Fase 0: `docs/reviews/SPEC_CONTROL_UI.md` (disetujui Atha 2026-11-07, K1-K6 = usul Claude: jalur A, hanya Atha, $1,00/job di server, tombol approve ganti "go live" (staging tetap chat), 8711 saat fase 2, fase 1 sesudah up2)
  - [ ] Fase 1 (jalur A): ~~PR jalur ketat D1+D3~~ **selesai #357 (2026-11-07, + allowlist A1: 112/112 job)**, lalu issue D2 (argus-ledger) dan D4 (argus-viewer) (amandemen 1 #346: `summary` buatan harness, viewer tidak memecah markdown). **Batch 5 (Atha 2026-11-07, "3 job dibaca semua"):** issue ditulis sesudah D1 merge dengan fixture dari keluaran D1 nyata; 3 job berurutan: ledger 016 (`GET /jobs/<id>/draft`, `summary` apa adanya, 404 id tidak sah), viewer 022 (kartu keputusan + alasan merah per tes), viewer 023 (rencana/scope/peringatan, teks lengkap tertutup, tautan dari halaman job); tes keamanan wajib di issue (teks `<img onerror>` dan heading palsu tampil sebagai teks; `..`/`%2F` 404; ledger tidak mengubah `summary`); Claude membaca ketiganya (pengecualian J9); deploy satu PLAN (ledger Stage 14 + viewer 021-023); ukuran K6: menit Atha membaca draf berikutnya di HP. **Batch 5 selesai dan live 2026-11-08** (`pilots/staging_stage14`): 016 applied `1d3a8ea` (ledger Stage 14), 022 `39a1c62`, 023 `70b5532` (redraft 60fa; draf pertama 514e konflik dengan tes 022, tes itu dilonggarkan tangan `acdc264` atas izin Atha, 514e ABANDONED); proxy di-restart untuk D3. K6 pertama 2026-11-08: 3 menit (draf 024, belum bersih: chat juga dibaca). Issue 024 "Ringkasan" bahasa Indonesia (Atha: halaman draf terlalu teknis) live di rilis 024 (`pilots/viewer_v0/p7`). K6 bersih 2026-11-08 (draf 025, `pilots/viewer_v0/p8`): 3 menit, approve; Atha: bagian di bawah Ringkasan masih terlalu teknis, dan approve 022-024 cenderung tanpa paham issue (pengawasan lemah). Berikutnya (usul Claude, menunggu Atha): kalimat "apa yang berubah buat kamu" bahasa Indonesia dari drafter di Ringkasan (jalur ketat: drafter + D1), detail teknis tertutup (issue viewer); "no draft to review" untuk job AWAITING_APPROVAL yang drafnya belum masuk snapshot → pesan "tunggu ≤15 menit" (issue kecil)
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
  - [x] Reviewer Argus: dibangun sebagai `argus judge` (#316, SPEC_JUDGE; lihat Tahap 2), aturan J9 2026-11-06
  - [ ] Catatan pelajaran per repo (`.argus/lessons.md`): hanya bila batch 2 menunjukkan pola berulang yang tidak bisa jadi
    cek; pelajaran masuk hanya bila replay job lama membuktikannya atau disetujui. Tidak: aturan yang ditulis dan dipakai sendiri
  - [x] **Shadow batch 2** (2026-10-31, harness 900711d): 10 job, $0.2791; 8 bersih di-apply (`argus-viewer` 9273316..201a723,
    issue 003-010); 1 blok Claude (`1808`, `<th scope=row>` agar tes lama tetap hijau, sebelum gerbang); 1 berhenti di gerbang
    `EXISTING TEST CONFLICT` (`3f45`, konflik nyata, tanpa biaya agen). Sesudah gerbang: 7 job, 0 blok yang butuh Claude.
    Semua henti berasal dari tes lama yang rapuh (diperbaiki manual 8b905f9, 379550d). Dideploy 2026-10-31 (pilot viewer #3,
    `pilots/viewer_v0/p3/RESULT.md`): live `j20261031_094229_2180-201a7231d246`, rollback rilis 002
  - [x] Gerbang penanda di harness (#275, SPEC_CONFLICT_GATE): `argus approve`, `dr.approve` dan `argus retry` menolak draf
    berpenanda `EXISTING TEST CONFLICT` (huruf dan pemisah apa pun) sebelum apa pun; `status` menampilkan baris `conflict:`.
    Mutants 12/12, review medium (8 diperbaiki), verify.sh PASS
  Batas: `--max-usd 1.00` per job (drafter memesan $0.70/percobaan, agen $0.50; $0.25 BLOCKED di $0), berhenti bila biaya
  nyata job > $0.25 atau batch > $1.50. PR `stage_data` (isi draf ke snapshot, UI fase 1) ditunda sampai sesudah up2

### Terjadwal

- [x] **Deploy Stage 13 / issue 015** (argus-ledger 4e947a0) ke staging 2026-11-04, `pilots/staging_stage13/RESULT.md`:
  live `j20261104_152512_b93a-4e947a0ffe8b.up1`, CSV tanpa gzip, JSON gzip; rollback → 014 `.up1`. Dua "go live" (yang
  pertama berhenti: job ada di `~/pilot3a_live`)

- [x] **up2 selesai 2026-11-07** (#302, `pilots/dep_upgrade_v0/p2/RESULT.md`): staging live Stage 13 `.up2` di
  starlette 1.10.0 + fastapi 0.162.0, langkah 0-8 sesuai, rollback antar image terlatih. Catatan asli: up2 mulai 2026-11-07: starlette 1.10.0, fastapi 0.162.0 (aturan 2 minggu), environment `*_up2`, PLAN.md + satu
  "go live" (`docs/reviews/SPEC_DEP_UPGRADE_V0.md`). **Draf `pilots/dep_upgrade_v0/p2/PLAN.md` ada**; sebelum "go live"
  ada prasyarat jalur ketat: `RUNTIMES["ledger_staging_up2"]` di `router/stage.py` (+ `config.yaml`, `environments/*_up2`,
  tes `test_stage.py:589` memakai nama itu sebagai runtime asing), dan image baru hanya bisa dibangun sesudah 2026-11-07
  15:05 UTC (upload starlette 1.10.0 24 Okt 15:04 UTC). Ulangi cek gzip Stage 13 (langkah 3
  `pilots/staging_stage13`) di up2. Sesudah up2: kandidat issue dengan API baru starlette/fastapi, disaring dulu dengan
  pertanyaan langsung ke DeepSeek tanpa tool sebelum pilot dua lengan (bukti untuk planner berhirarki)

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
- [ ] `argus applied` tidak bisa dikoreksi: job 021 viewer (`j20261106_151840_e81c`) tercatat dengan commit tes `ab43761`, bukan patch `518b34f`, jadi `viewer-deploy` menolak (pilot viewer p6). Atha 2026-11-07: tunggu batch 5 (rilis berikutnya membawa 021); **selesai 2026-11-08: 021 live lewat rilis 023**. Kandidat jalur ketat bila terulang: `argus applied --amend <commit>` hanya untuk APPLIED yang belum di-deploy, commit baru wajib `as_is` True, koreksi tercatat di log
- [ ] `argus code` yang ditolak karena key (tanpa `--key-file`) tetap membuat job `NEW` (`j20261030_164146_9b3d`, di-abandon);
  layar penolakan tidak menyebutnya. Kecil, tetapi menyentuh jalur key (`live()`): jalur ketat

### Kemampuan agen (jalur cepat, kandidat)

- [x] **Gate "tes menelan traceback" salah tolak** (argus-ledger 008; jalur ketat, `docs/reviews/SPEC_RED_CAUGHT.md`, #304,
  merged d9e6e8b 2026-11-05): red check mencatat exception yang ditangkap tes (`sys.monitoring`, Python 3.12+; setup, call dan
  teardown), gate menolak hanya yang benar-benar ditelan; jatuh ke aturan lama bila tak bisa dipantau. 32 tes, mutants 19/19,
  review medium 8 temuan, +4,5% waktu, `verify.sh` PASS 728a8b7 (2956 passed). Batas yang diterima: catatan di proses anak
  tidak terlihat; `with`/`finally`/`pytest.raises` dihitung seperti `except`
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

- [x] **Rekonsiliasi biaya Oktober vs konsol** (2026-11-03, Atha): DeepSeek konsol $4,24 = ledger dihitung ulang dengan harga
  sekarang $4,2372 (token 66,96 jt vs 66,94 jt); ledger mencatat $4,4883 karena 15 Okt (kalibrasi judge) memakai tabel harga
  lama (~2×) sebelum dicek 23 Okt: lebih tinggi, arah aman. Anthropic konsol $8,31 di dalam ledger $8,21-8,49 (satu call router
  pilot #1, 22 Okt 19:34 UTC, terkirim tanpa `llm_call`). Viewer ($4,65) hanya job router. **Simulasi token** (`~/p3_tokens.py`,
  `~/p3a_tokens.py`, `pilots/m6_pilot4|5/sim_tokens.py`) menulis ledger dengan nama model asli dan biaya hitungan ($0,68 di
  `~/p3a_sim`, `~/p4sim`, `~/p5sim`, dihapus); sekarang menaruh berkas `SIMULATED` di folder hasilnya. Penjumlah ledger
  lintas folder harus melewati folder ber-`SIMULATED`

- [ ] Router: cek bentuk kunci DeepSeek (hanya Anthropic yang dicek prefiksnya)
- [ ] Router: `argus apply` (K6 v0); sekarang perintah apply dicetak `status` dan dijalankan Claude

### Ditunda sampai ada bukti kebutuhan

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
