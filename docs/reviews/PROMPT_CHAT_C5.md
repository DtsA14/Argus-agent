# Prompt untuk sesi C5 (chat app: poles, pensiun kode kontrol, penyempurnaan)

Tempel isi bagian "PROMPT" di bawah ke sesi Claude yang baru (di VM Argus, direktori `~/Argus-agent`). Ditulis 2026-11-15 sesudah C1-C4 live.

---

## PROMPT

Kamu melanjutkan aplikasi chat Argus di VM ini. Atha menulis bahasa Indonesia santai; jawab dalam bahasa Indonesia yang singkat, jujur soal apa yang sudah live dan apa yang belum, dan jangan mengulang ringkasan panjang. Dia membaca dari HP.

### 1. Keadaan sekarang (sudah live, jangan dibangun ulang)

Aplikasi chat (`router/chat.py`, `router/chat_actions.py`, `router/chat_static/{index.html,app.js,app.css}`, kode tepercaya yang ditulis Claude, bukan agen Argus) berjalan sebagai `argus-chat.service` di **127.0.0.1:8711** (dulu 8712). Viewer (`argus-viewer`, ditulis agen) tetap di 8710, baca-saja, dan menaut ke chat lewat tautan **Decide** `http://localhost:8711/jobs/<id>`. `argus-control` (layanan lama di 8711) sudah dimatikan dan di-disable; kodenya masih ada di repo.

Fitur: **Status** (daftar job), **Issue** (penulis issue: issue baru, balasan, Start, abandon), **Riset** (`argus research`, laporan sebagai teks), **Keputusan** (reject/abandon job kode/riset, kolom alasan di tiap kartu). Semua aksi lewat dua langkah `POST /api/prepare` lalu `POST /api/confirm` (token satu kali, terikat kartu yang dibangun server dari data hidup, jeda minimal 1 detik, audit di `~/.local/state/argus-chat/audit.jsonl`); CLI di belakangnya (`argus issue|research|reject|abandon ... --via ui`) tetap gerbang sebenarnya. Batas harian eksposur $2,00 (config `chat.daily_cap_usd`, bawaan 2.0) menghitung `max_usd` penuh tiap job yang dimulai dari UI selama 24 jam.

Dibaca dulu: `docs/reviews/SPEC_CHAT_APP.md` (bagian 3, 11, 12, 12.10, 12.11, 13, 13.7, 13.8; amandemen mengikat dan menggantikan bagian 1-10 bila bertentangan), bagian "Chat app" di `AGENTS.md`, entri CHAT-APP di `PENDING.md`.

Peta kode yang perlu: `Actions` (`prepare`, `confirm`, `execute`, `build*`, `exposure`, pembaca `read_issue`, `research_thread`, `decisions`, `_spent`, `_sha`), `Handler`/`server(chat, port, public)`/`names_for`/`csp`, `scripts/chat_cutover.sh` (check, apply, post, rollback), tes `tests/test_chat*.py` (+ `test_chat_decide.py`, `test_chat_research*.py`, `test_chat_ui.py`), mutan `verification/chat_c{1,2a,2b,3,4}_mutants.py`.

### 2. Aturan kerja (dari Atha; ikuti persis)

- **Jalur ketat** untuk kode chat yang menyentuh server, gerbang, uang, token, CLI: spek → review Opus (subagent baca-saja, `model: opus`) atas spek → tes dulu → kode → **review Opus atas kode, perbaiki** → **baru mutan, sekali** (urutan ini keputusan Atha 2026-11-15; sebelum mutan, cek semua anchor cocok tepat sekali tanpa menjalankan tes) → `bash scripts/precheck.sh` → **satu** `bash scripts/verify_at.sh <branch>` sendirian → PR. **Jangan merge** sebelum Atha berkata merge untuk item itu (kecuali dia bilang merge termasuk).
- **Jalur ringan** (perubahan halaman kecil yang tidak menyentuh server atau gerbang, ala jalur advisory di AGENTS.md): tes yang tersentuh, satu review Opus ringkas, `precheck`; tanpa mutan dan tanpa `verify_at` penuh. Kalau ragu, pakai jalur ketat.
- PR hanya-dokumen, PENDING, pilot dan deploy boleh langsung di-merge.
- **Jangan menjalankan apa pun yang berat di samping `verify_at`** (mutan, tes besar). Cek `ps` bahwa tak ada verify lain hidup. Jalankan `precheck` dulu, baru verify. Verdict = baris `RESULT:` **terakhir** di log (baris `RESULT: PASS` lebih awal itu cek image). Log bukti `verification/verify-*.log` disalin ke branch PR.
- Menunggu proses di latar: **tunggu PID-nya** (`while kill -0 PID; do sleep 20; done`) atau tunggu baris `RESULT` di log; jangan `pgrep -f` atau `pkill -f` dengan pola yang juga ada di perintahmu sendiri (menggantung/membunuh shell). Pasang pemantau yang juga berhenti bila log berisi `Traceback`.
- **Jangan pernah menulis atau menyebut file kunci API** di perintah (hook menolaknya). Atha yang memasang drop-in kunci. Restart service dan edit unit systemd: bilang dulu, kerjakan hanya atas kata Atha; `~/.ssh/authorized_keys` dan forward Termius hanya Atha.
- Tidak ada node di VM: cek sintaks JS dengan image docker `argus-precheck-pwa:node22` (`docker run --rm --network none -v <repo>/router/chat_static:/s:ro --entrypoint node argus-precheck-pwa:node22 --check /s/app.js`). File statis dipin sha256-nya di `router/chat.py` (`STATIC_SHA256`): ubah file, hitung ulang pin di PR yang sama.
- Uang sungguhan (job riset $1,00, job kode, giliran penulis) hanya dengan persetujuan Atha untuk jumlahnya; yang menekan Konfirmasi adalah Atha.
- Memori: baca `/home/ubuntu/.claude/projects/-home-ubuntu/memory/MEMORY.md`.
- Viewer (`~/argus-viewer`) jangan diubah; itu pekerjaan agen Argus lewat job.

### 3. Lingkup C5 (urut; tanyakan ke Atha dulu urutan dan tiga keputusan di bagian 4)

**A. Pensiun kode `control` (jalur ketat).** Hapus `router/control.py`, `router/control_issues.py`, `tests/test_control.py`, `tests/test_control_issues.py`, mutan `verification/control_*_mutants.py` dan bagian yang memakai `router/control_issues.py` di `verification/issue_writer_*_mutants.py`, subperintah `argus control serve` di `scripts/argus.py`, `deploy/systemd/argus-control.service`, blok `control:` di `config.yaml` (`message_body_max` hanya dipakai `control_issues.py`; cek lagi), dan rujukan di docs. **Sebelum menghapus, pindahkan simbol yang dipakai chat**: dari `control.py`: `cli` (dipanggil sebagai `control_cli`), `strip_refused`, `reason_problem`, `draft_sha12`, `Unreadable`, `allowed`, `REJECTABLE`, `NOT_ABANDONABLE`, `ABANDON_DEFAULT`, `UI_ID`; dari `control_issues.py`: `Spawner`, `issue_cli`, `normalize`, `last_line`. Rumah baru yang masuk akal: modul kecil `router/chat_runs.py` (Spawner, issue_cli, research_cli, cli) dan `router/decisions.py` (aturan state/alasan/sha). `tests/test_chat_decide.py` meng-impor `tests/test_control.py` (`make_job`, `sha12`, `DRAFT`): pindahkan helper itu ke tes chat sebelum menghapus, dan **jangan kehilangan jaminan F9 yang sudah dipindahkan** (lihat 13.7 butir 12). Jangan menyentuh `~/.config/systemd/user/argus-control.service.d` (milik Atha). Hapus rujukan usang di `PENDING.md`, `docs/Reconciliation.md`, `AGENTS.md`, komentar `deploy/systemd/argus-chat.service`, dan `docs/reviews/SPEC_CHAT_APP.md` bagian 2 (catat sebagai amandemen, jangan menulis ulang sejarah).

**B. Batas baca `Chat.thread` (jalur ketat, 11.13 dan 12.11 butir 1).** `Chat.thread` (detail Status semua jenis job) memakai `sd._one` yang membaca setiap ledger dan berkas draf sampai `READ_MAX` 16 MiB meski hanya sebagian yang ditampilkan, di server satu-utas. Batasi: berkas tetap, teks sekitar 256 KB, ledger per fd dengan batas (seperti `Actions._spent`), tanpa membaca berkas draf yang dibuang. Tes: symlink, berkas besar, tanpa 500.

**C. `--no-draft` di CLI reject/abandon (jalur ketat, `router/job.py`, 13.7 butir 3).** Tanpa draf, `--sha` kosong dilewati CLI sehingga draf yang baru muncul antara `confirm` chat dan kunci CLI tidak diperiksa. Tambah `--no-draft` (ditolak di bawah kunci bila `_last_draft` ada), dan chat mengirimnya bila sha kartu kosong. Spek singkat + tes CLI + mutan; ini mengubah `router/job.py` (hati-hati: jalur uang/keputusan).

**D. Pesan berbahasa Indonesia (jalur ringan atau ketat tergantung cara; keputusan Atha).** Contoh keluhan nyata: "Tidak bisa disiapkan: a reason is required". Server mengembalikan `{"refused": teks Inggris}`; teks CLI diteruskan. Usul: tambahkan `gate` ke jawaban penolakan dan petakan `gate` + status ke kalimat Indonesia di halaman, dengan teks server sebagai cadangan; jangan menerjemahkan teks yang datang dari CLI atau model.

**E. Penyempurnaan yang diusulkan (tiap butir kecil; minta pilihan Atha):**
1. Tampilkan sisa batas harian: di kartu konfirmasi ("eksposur hari ini $X dari $2,00") dan pesan "batas harian penuh, bebas sekitar jam HH:MM" saat `prepare` ditolak karena batas (sekarang hanya teks Inggris tanpa waktu).
2. Kartu keputusan menampilkan ringkasan draf (`for_human`) dari `draft.json` sebagai teks, supaya keputusan tidak harus membuka viewer. Teks agen: hanya `textContent`, lewat `scrub`, dipotong; ini fitur baru yang memperlebar apa yang chat membaca, jadi jalur ketat.
3. Status riset yang berjalan lama: jajak lebih cepat (15 detik) hanya untuk job yang sedang berjalan, dan tombol muat ulang manual.
4. Empty state, pesan jaringan putus, dan layar sempit (tabel stage di detail Status sudah terpotong di HP: ganti kartu).
5. Tes riset **sungguhan** dari HP: satu pertanyaan kecil, saat batas harian muat lagi (batas penuh sampai sekitar 2026-11-16 02:30 UTC karena tes C2c); Atha yang menekan Konfirmasi; setelah itu periksa job, audit, biaya, dan laporan.

### 4. Tanyakan ke Atha sebelum mulai

1. Urutan A-E, dan apakah B dan C dijadikan satu PR atau terpisah.
2. Untuk D: peta `gate` → kalimat di halaman (usul gue) atau terjemahan di server?
3. Untuk E2 (ringkasan draf di kartu keputusan): mau, atau cukup tautan viewer?

### 5. Yang jangan dilakukan

Jangan menyentuh `authorized_keys`, file kunci, drop-in kunci, atau `~/argus-viewer`. Jangan me-restart `argus-chat` atau menjalankan `scripts/chat_cutover.sh ... --yes` tanpa kata Atha (rollback ke 8712 + `argus-control` hanya bila perlu, dan itu tidak mungkin lagi setelah A menghapus kodenya: nyatakan itu ke Atha sebelum A di-merge, dan ubah `chat_cutover.sh` / catatannya yang menyebut rollback). Jangan membuat PR yang mengubah banyak hal sekaligus; satu butir per PR.

### 6. Selesai berarti

Tiap butir: tes lulus, `precheck` PASS, (ketat) `verify_at` PASS dengan log di PR, PR dibuka dengan ringkasan jujur (apa dicoba, apa belum), menunggu kata merge dari Atha. Setelah A di-merge: `PENDING.md` diperbarui, dan `argus chat serve` masih jalan di 8711 dengan Decide dari viewer tetap bekerja (`scripts/chat_cutover.sh post <job>`).
