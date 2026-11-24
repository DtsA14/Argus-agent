# Spec CHAT-MANAGER (rev 0): chat sebagai mandor yang diajak ngobrol dan mengarahkan ke job

Status: **rev 1** (tinjau Opus 2026-11-21: GO WITH CHANGES; amandemennya di bagian 13, mengikat dan menggantikan bagian 1-12 bila bertentangan; dua klaim terberatnya diperiksa Claude terhadap kode: `exposure()` hanya menghitung `research` dan `issue`, dan `execute` jatuh ke `issue start` untuk aksi tak dikenal). **P2a dibangun 2026-11-21 (Atha "Gass bro"; PRD dari chat, diketik manusia). Sisanya (P0, P1, P2b, P3, P4: mandor yang ngobrol dan merutekan) DIPARKIR sampai titik cek 2026-11-29 (Atha 2026-11-21: "masuk parkiran ... gw mencoba komitmen")**; tidak dikerjakan sebelum itu kecuali Atha berkata ia mengganti pekerjaan yang berjalan. Diminta Atha 2026-11-21 ("chat pengen bisa diajak brainstorming dan mengorkestrasi ... router yang pilih mau diarahkan ke job code/research"; "posisi chat seperti proyek manajer/mandor"; "Ok gass"). Ditulis Claude. Memenuhi bagian 8 `SPEC_CHAT_APP.md` (lapisan bahasa bebas; syaratnya mengikat di sini: alat = daftar tetap, model tidak pernah memegang `confirm`, token, atau kunci, keluaran model dirender sebagai teks) dan menjawab K3 (biaya) di bawah.

## 1. Tujuan dan bukan-tujuan

Satu percakapan di chat (8711) tempat Atha: (a) **ngobrol** (brainstorming tentang fitur, ukuran, pilihan), (b) mendapat **usulan rute** berupa kartu ke salah satu pipa yang sudah ada, dan (c) sesudah sebuah job selesai, mendapat **kartu langkah berikutnya**. Atha tetap penjadwal: tiap kartu dikonfirmasi satu ketukan.

Bukan tujuan (tiap butir spek sendiri, bila pernah): `queue go`/`approve`/`apply`/buka PR/merge dari chat (tetap terminal atau Claude; SPEC_CHAT_APP 13.7 butir 9 "never an approve" tidak berubah); planner berhirarki otomatis (M4; bukti belum ada, PENDING "Ditunda"); memori lintas sesi (M8; konteks di sini hanya ringkasan percakapan dan berkas tetap); aksi tanpa konfirmasi manusia; browser atau web bebas.

## 2. Arsitektur: chat tetap tanpa model dan tanpa kunci

`router/chat.py` tidak memegang kunci dan tidak menjalankan model (docstring modul). Itu dipertahankan: **giliran mandor adalah job Argus** `kind: "manager"`, dijalankan oleh proses anak CLI (`scripts/argus.py manager turn ...`) lewat `harness/llm.py` (`LLMCaller`, ledger, batas), pola yang sama dengan `research` dan penulis PRD. Berkas kunci disebut di environment service seperti slot yang ada (`ARGUS_CHAT_KEY_FILE`, `..._WRITER_`, `..._RESEARCH_`), ditambah slot `ARGUS_CHAT_MANAGER_KEY_FILE` (jatuh ke slot penulis bila tak diisi).

Satu percakapan = satu job `manager` (id `j...`), giliran ditambahkan seperti `prd reply`. Job menyimpan giliran, ledger biaya, dan **usulan** yang dibuat tiap giliran.

## 3. Tiga mode dalam satu percakapan

Model menjawab dengan **satu objek JSON ketat** per giliran (`strict_json`, kunci ganda ditolak): `{"say": "teks", "propose": null | {...}}`.

1. **Ngobrol.** `say` saja, `propose: null`. Tanpa aksi.
2. **Usulan rute.** `propose = {"route": R, "repo": nama|null, "text": "...", "why": "..."}` dengan R dari **menu tetap**: `research` (sudah ada: `research_new`), `prd` (aksi baru `prd_new`, bagian 4), `ask` (model butuh jawaban Atha; hanya `say`), `none` (tidak ada rute: Argus belum bisa; model menyebut sebabnya). Nilai lain ditolak kode; sesudah penolakan model diberi satu kesempatan ulang di giliran yang sama, lalu `none`.
3. **Langkah berikutnya.** Saat sebuah job yang lahir dari percakapan ini berubah state yang bermakna (riset `REPORT_READY`, PRD `AWAITING_HUMAN`, antrean `WAITING`/`STOPPED`), giliran mandor berikutnya menerima ringkasan dari **data harness** (bukan teks model) dan boleh mengusulkan rute lanjutan yang sama (mis. `prd` dengan `--from-research`). Tahap 3 ini PR terakhir (bagian 9).

## 4. Dari usulan ke kartu: kode yang membuat, bukan model

Model tidak membuat kartu. Kode memvalidasi `propose` (rute di menu, repo di `issue_writer.repos`, `text` ≤ 8 KB, scrub `stage_data`), lalu memanggil `prepare` yang sudah ada dengan aksi terkait; kartu konfirmasi dirender dari **data hidup** (SPEC_CHAT_APP 11.3, 11.6): repo, commit beku, environment, model, batas, dan **teks permintaan utuh**; `why` model ditampilkan sebagai teks berlabel "alasan mandor (model)". Atha dapat **mengedit teks atau rute** sebelum konfirmasi; yang dikonfirmasi adalah apa yang ada di kartu, token terikat digest kartu seperti sekarang. Tidak ada jalan model ke `confirm`.

Aksi baru **`prd_new`** (jalur ketat; hari ini job PRD hanya dari terminal, `chat_actions.py` "terminal-only until the chat page"): setara `argus prd new --repo R --message-file ...` lewat proses anak, `--yes` hanya dari `confirm`, id job `j...`, batas dari `prd_writer`. `research_new` tidak berubah.

## 5. Uang (menjawab K3)

Langganan Claude tidak dipakai; semua lewat OpenRouter, ditagih per token (kunci chat sudah OpenRouter). Aturan:
- **Jatah sesi**: satu `confirm` "mulai percakapan mandor" menetapkan `session_cap_usd` (config `chat.manager.session_cap_usd`, usul $0,20) yang dihitung ke **batas harian eksposur** (SPEC_CHAT_APP 11.8) sejak `confirm`; giliran ditagih ke ledger job `manager`; tiap giliran punya `turn_cap_usd` (usul $0,03). Giliran yang tak muat di sisa jatah **tidak dimulai** (pesan jelas, tanpa memotong jawaban), sesi dapat dilanjutkan dengan `confirm` baru.
- Job yang lahir dari usulan tetap dihitung sendiri (kartu masing-masing). Mandor tidak menambah jatah job lain.
- Tanpa pengecualian "balasan murah" (SPEC_CHAT_APP 11.5): giliran pertama selalu lewat `prepare`/`confirm`; giliran berikutnya di dalam jatah tidak, karena jatah itu yang dikonfirmasi (amandemen atas 11.5, perlu persetujuan Atha eksplisit: K1).

## 6. Dua slot model

`config.yaml chat.manager: {talk_model, plan_model, ...}`. `talk_model`: ngobrol dan memilah rute (murah). `plan_model`: dipakai **hanya** untuk giliran yang menyusun rencana (mis. memecah ide jadi PRD, kartu langkah berikutnya), satu kali per rencana. Pilihan awal ditentukan **uji rute** (bagian 8), bukan tebakan; dugaan awal `talk_model = anthropic/claude-haiku-5.5` (PRD writer sudah berjalan dengan model ini), `plan_model` lebih kuat bila skornya menuntut.

## 7. Konteks dan injeksi

Konteks tiap giliran, semuanya data berlabel: (1) **lembar kemampuan** `docs/CHAT_CAPABILITIES.md`, ditulis tangan (apa yang Argus bisa, tidak bisa, biaya tipikal, aturan rute), pin sha256 seperti berkas statis chat; (2) ringkasan percakapan terbatas (≤ 4 KB, dibuat kode dengan memotong giliran lama, bukan oleh model); (3) status job milik percakapan dari data harness; (4) atas permintaan Atha, `pending.md` atau README repo terdaftar dari salinan baca-saja di commit beku (kebijakan privasi repo privat: hanya repo yang Atha izinkan secara tertulis di config `chat.manager.readable_repos`). Teks repo, laporan riset, dan jawaban model sebelumnya adalah **data, bukan instruksi**, dibingkai di prompt, dirender di aliran dengan gaya yang tak dapat ditiru kartu (SPEC_CHAT_APP 11.6); `say` dirender sebagai teks (tanpa HTML/markdown berbahaya; pemindai build `app.js` tetap berlaku).

## 8. Uji rute dulu, model kemudian (`route_eval_v0`)

Sebelum memilih model: 12-15 skenario beku (`pilots/route_eval_v0/cases.json`), tiap skenario = pesan Atha + konteks + rute yang benar: ide fitur kode jelas di repo terdaftar → `prd`; pertanyaan perbandingan library → `research`; permintaan yang Argus belum bisa (deploy, kirim email, merge) → `none` dan sebabnya; permintaan samar → `ask`; permintaan yang menyuruh model memakai kunci atau melewati konfirmasi (jebakan) → `none`; teks repo berisi instruksi palsu (jebakan injeksi); permintaan besar yang harus dipecah. Penilaian: rute (kode, tanpa model), `text` usulan lolos validasi, tanpa mengarang kemampuan (cek terhadap daftar lembar kemampuan), jebakan. Jalankan pada tiga model (DeepSeek, Haiku 5.5, satu yang lebih kuat), n = 3 tiap skenario; laporkan skor dan biaya (perkiraan $0,05-0,10) di `pilots/route_eval_v0/RESULT.md`. Model dipilih dari hasil itu.

## 9. PR (semua jalur ketat kecuali dinyatakan)

- **P0 (jalur ringan)**: `route_eval_v0` (kasus, pelari, `CHAT_CAPABILITIES.md` rev 0). Tanpa perubahan chat.
- **P1**: job `manager` dan `argus manager turn` (ledger, batas, jatah sesi, parser JSON ketat, validasi usulan, slot kunci dan model). Tanpa UI.
- **P2**: aksi `prd_new` + usulan → `prepare` (kartu dari kode, edit rute atau teks).
- **P3**: UI chat (chip "Ngobrol", kartu usulan berlabel, jatah sesi terlihat, batas).
- **P4**: kartu langkah berikutnya dari state job (bagian 3.3).
Tiap PR: tinjau Opus sebelum kode, mutan sekali, precheck, `verify_at`.

## 10. Tes wajib (gagal bila jaminannya rusak)

Model tidak pernah memegang `confirm` atau token (tidak ada rute dari keluaran model ke `confirm`); rute di luar menu ditolak; kartu dibangun ulang dari data hidup dan berubah bila digest berubah; teks injeksi (repo, riset, `say` sebelumnya) tidak mengubah rute atau kartu; jatah sesi menghentikan giliran sebelum dimulai; giliran gagal bayar tidak meninggalkan job `manager` tanpa ledger; `say` dengan karakter tak terlihat/HTML dirender sebagai teks; `readable_repos` kosong berarti tidak ada isi repo ke model; JSON dengan kunci ganda atau bidang tambahan ditolak; audit satu baris per giliran tanpa teks pesan.

## 11. Keputusan untuk Atha

| | Pertanyaan | Usul Claude |
|---|---|---|
| K1 | Jatah sesi sebagai satu konfirmasi (amandemen atas SPEC_CHAT_APP 11.5) | ya, $0,20 per sesi, $0,03 per giliran, dalam batas harian $2,00 |
| K2 | Repo yang isinya boleh dibaca mandor | kosong dulu; tambah `bulking-app` hanya dengan kata Atha |
| K3 | Model | ditentukan uji rute (bagian 8), bukan sebelumnya. **Diputuskan Atha 2026-11-24: DeepSeek V4.1 Flash 1017 (`openrouter:deepseek/deepseek-v4.1-flash-1017`) untuk P1**, atas hasil `pilots/route_eval_v0/RESULT.md` (45/45, $0,008 per 45 panggilan; GLM dan Haiku tidak diperlukan menurut bukti itu); keputusan config P1, belum ada perubahan config |
| K4 | Urutan | P0 dulu; P1-P3 sesudah hasil uji; P4 paling akhir |

## 12. Yang belum dicek (rev 0 jujur)

Apakah `LLMCaller` menerima giliran obrolan bebas dengan JSON ketat tanpa perubahan (research dan PRD writer memakai alat, bukan obrolan); apakah kunci slot baru perlu perubahan `router/chat.py` selain `chat_actions.key_file`; bentuk persis ringkasan percakapan yang dibuat kode; apakah `prd_new` dari chat memerlukan perubahan `scripts/argus.py` (`--via`, seperti riset di 12.10 butir 9). Tinjau Opus diminta memeriksa terutama butir ini dan amandemen 11.5.

## 13. Amandemen dari tinjau Opus (2026-11-21, GO WITH CHANGES; mengikat)

1. **Satu job `manager` = satu sesi = satu konfirmasi; `max_usd` tetap sejak dibuat; tanpa top-up.** Sesi baru = job baru, ringkasan sebelumnya dibawa kode. CLI menolak giliran bila `created_at` lebih tua dari TTL sesi (usul 12 jam, di bawah jendela 24 jam eksposur). Mengganti kalimat "sesi dapat dilanjutkan dengan confirm baru" di bagian 5.
2. **Eksposur:** `exposure()` mendapat cabang `prd` dan `manager` (dari `created` `via: ui`, `max(max_usd, batas terkonfigurasi)`), `exposure_of` mengenal `prd_new` dan `manager_session` (giliran menambah 0: sudah di dalam batas yang dihitung), jaring audit (`audited_research`) diperluas ke keduanya. Tanpa ini model yang mengusulkan PRD dapat memulai job $1,50 tanpa batas harian.
3. **`argus prd new` mendapat `--via ui`**, `via` di catatan `created`, `--job-id` dicek `fullmatch` dan jendela waktu (pola `research.start`), dan `prd_job.new` memeriksa `via in rj.VIA`. Hal yang sama untuk `argus manager`. Catatan: SPEC_PRD_WRITER 2.1 melarang `--via` "sampai D5"; ini membuka D5 untuk PRD dari chat dan butuh kata Atha.
4. **Rute giliran bernama satu**, mis. `POST /api/manager/turn {session, message}`, dengan semua gerbang F3 (Host, Origin, Fetch-Metadata, JSON saja, kunci ketat, pesan ≤ 2000 karakter tanpa karakter C*/Zl/Zp lewat berkas pesan), satu baris audit **sebelum** spawn tanpa teks, argv tetap `argus manager turn JOB --message-file F --via ui --key-file K --yes`, ditolak bila job bukan `via ui`, kedaluwarsa, sibuk, atau sisa < `turn_cap`; CLI memeriksa ulang di bawah kunci job. SPEC_CHAT_APP bagian 1.3, 7 dan 11.5 serta aturan chat di AGENTS.md **diamandemen tertulis** menyebut rute dan batas ini (K1 Atha).
5. **Usulan = data di direktori job.** Halaman menampilkannya sebagai teks tak tepercaya dengan tombol "Siapkan"; tombol itu mengirim `/api/prepare` biasa dengan aksi, repo, dan pesan terisi (dapat diedit). Tidak ada kode khusus usulan di `prepare` atau `confirm`.
6. **`why` tidak masuk kartu konfirmasi** (SPEC_CHAT_APP 11.6); tampil di aliran bergaya keluaran model. Kartu memberi label "teks ditulis mandor (model); periksa sebelum konfirmasi" bila pesannya dari usulan, dan `source: "manager"` masuk kartu dan digest (audit membedakan dari ketikan Atha).
7. **Batas teks = milik aksi tujuan** (`build`): riset 20-2000, PRD `prd_writer.message_max` (4000), ditambah `scrub(text) == text`. "≤ 8 KB" dihapus.
8. **Kartu `prd_new` dari satu fungsi murni yang diekstrak dari `prd_job._screen`** (model, batas giliran, batas job, "berkas repo ke penyedia", baris runner); tulis "HEAD saat job dibuat" (prepare tidak menjalankan subproses: 11.10). Param tepat `{repo, message}`; argv memuat `--queues-dir`, tidak pernah `--ref`, `--rebase`, `--max-usd`, `--profile`; kunci slot penulis.
9. **`execute` memakai tabel dispatch eksplisit**: aksi tak dikenal melempar kesalahan, tidak pernah jatuh ke `issue start`.
10. **Giliran mandor = stage satu simpul** (`research/loop.run_stage`/`tool_loop`, satu alat paksa `Respond{say, propose}`) agar ada memo, ledger per-run di `runs/<job>-mN/` (yang dibaca `_spent`) dan penolakan kunci tak dikenal. Alternatif (panggilan polos ala `env_propose`) hanya bila spek menyatakan "tanpa resume; biaya ada di ledger" dan tes membuktikan tidak ada pembelian ulang.
11. **Jenis job `manager`:** tabel LEGAL dan `move`/`status`/`abandon`/`resume`/`list` di `router/job.py`; snapshot publik hanya bidang allowlist, tanpa judul dan tanpa percakapan (`stage_data`); viewer menoleransi jenis baru; `decision()` hanya menyebut namanya. Templat: SPEC_PRD_WRITER 4.2/4.6.
12. **`--from-research` tidak ada untuk `prd new`** (hanya `argus code`): dihapus dari bagian 3.3. Kartu langkah berikutnya untuk PRD `AWAITING_HUMAN` dan antrean hanya petunjuk terminal (teks saja: `argus prd check <folder>`).
13. **Batas giliran per slot** (`talk_turn_cap_usd`, `plan_turn_cap_usd`), tiap satu diperiksa dengan reservasi kasus terburuk sebelum panggilan.
14. **Bagian `chat:` di `config.yaml`** (`daily_cap_usd` eksplisit, `manager.*`). Kartu K1 menampilkan "sesi $0,20 + 1 PRD $1,50 = $1,70 dari $2,00": dengan batas bawaan $2,00, satu sesi mandor ditambah satu PRD sudah hampir menghabiskan hari; naikkan batas hanya dengan kata Atha.
15. **Urutan PR (menggantikan bagian 9):** **P2a dulu** (aksi `prd_new` yang diketik Atha + `--via` di CLI + eksposur + dispatch eksplisit; berguna sendiri, tanpa mandor); **P0** (prompt, parser, validator sebagai modul murni yang diimpor P1, plus `route_eval_v0` dan `CHAT_CAPABILITIES.md` dengan pin sha256 sendiri); **P1** (job `manager`, `argus manager turn`, aksi sesi, rute giliran, jenis job); **P2b** (usulan → isian `prepare`); **P3** (UI); **P4** (kartu langkah berikutnya). Tiap PR jalur ketat kecuali P0 bagian eval.
16. **Tes tambahan:** eksposur menghitung PRD dan manager (juga yang dimulai dari terminal dengan `--via ui`); dua `confirm` `prd_new` berturut-turut melewati batas; aksi tak dikenal tidak pernah ke `issue start`; rute giliran ditolak saat kedaluwarsa, sibuk, bukan via ui, sisa < batas, Origin asing, same-site, dan tidak pernah men-spawn selain `manager turn`; sesi lewat TTL ditolak CLI; crash sesudah balasan model dan sebelum commit lalu resume tidak membeli ulang; kartu `prd_new` sama dengan fakta `_screen`; konfigurasi berubah antara prepare dan confirm memberi 409; repo di luar allowlist (atau repo Argus) ditolak; usulan dengan kunci tambahan, JSON berpagar atau ganda ditolak; coba ulang satu kali lalu `none` dengan dua panggilan di ledger; percakapan mandor tidak pernah di snapshot publik; teks injeksi di repo yang menuntut rute, repo, atau parameter lain hanya mengubah teks kartu.
17. **Mutan** (40, daftar tinjau Opus): ditulis di spek kode tiap PR (M1-M20 untuk P1, M21-M40 untuk P2), dijalankan sekali sesudah tinjau kode.
