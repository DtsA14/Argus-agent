# Probe: model membaca dokumen rencana Argus sendiri (2026-11-06)

Atha: "coba cek future architecture.md, reconciliation.md dan pending.md, buat summary yang mencakup posisi argus sekarang
dan apa yang pengen lu develope?". Bukan job Argus: satu panggilan DeepSeek Flash (thinking) per probe lewat `LLMCaller`
(reservasi $0,05), dijalankan Atha dari terminal karena key diketik. Input: tiga dokumen dari `main`, ditandai data.

| probe | pertanyaan | input / output (reasoning) | biaya | waktu |
|---|---|---|---|---|
| 1 | kalimat Atha persis (`main` d381bfd) | 18.445 / 3.798 (1.583) | $0,0050 | ±1 menit |
| 2 | "menurut lu, apa 3 hal paling penting yang harus dikembangkan di Argus berikutnya, dan kenapa? Boleh beda dari rencana yang sudah ada. Sebutkan juga satu hal di rencana sekarang yang menurut lu sebaiknya tidak dikerjakan." (`main` c5cbf09, sesudah #334) | 18.634 / 10.654 (8.967) | $0,0092 | 74 s |

Penilaian Claude:
- Probe 1 akurat untuk posisi sekarang. Kesalahannya berasal dari dokumen yang basi atau bertentangan (worker "paralel",
  viewer "2 task", 6/6 vs 7/7), dan ia menemukan tanggal kepala dokumen yang tertinggal. Diperbaiki di #334. Ia menolak
  berpendapat ("bukan keinginan agen"), sebagian karena instruksi sistemnya.
- Probe 2: prioritas 3 (prompt injection riset → kode) adalah celah yang luput dari rencana; prioritas 1 (eval independen)
  sejalan dengan butir "7/8 benar"; prioritas 2 sebagian besar sudah ada (judge), ia salah baca karena butir lama
  "Reviewer Argus" belum dicentang (dicentang bersama catatan ini). Usulan menunda UI kontrol fase 2-4: setuju.
- Untuk dokumen ±47 KB satu panggilan cukup; `argus research` dengan sumber repo belum mendesak.

## Output probe 1

# Ringkasan: posisi Argus & rencana pengembangan

**Catatan status dokumen dulu.** `FUTURE_ARCHITECTURE.md` sendiri menulis bahwa isinya **draf spek, bukan deskripsi kode**; status resmi ada di `Reconciliation.md`. Tapi `Reconciliation.md` judulnya "2026-10-30" padahal isinya sudah sampai keputusan 2026-11-05, dan `PENDING.md` menulis "terakhir diperbarui 2026-11-05" padahal ada butir 2026-11-06 (aturan J9, `argus judge`). Jadi tanggal di kepala berkas tertinggal dari isinya — isi yang saya pakai di bawah.

## 1. Posisi sekarang (per 2026-11-05/06)

Arah resmi sejak **2026-11-03**: general-purpose agent, **dimulai dari deep research**, menggantikan arah "coding agent untuk production" (2026-10-28). Aplikasi latihan dan jalur kode tetap jalan.

| Lapisan | Status | Isi |
|---|---|---|
| **L0 fondasi** | `[x]` | budget/reservasi sebelum kirim, ledger, crash-resume, sandbox Docker, evaluator |
| **L1 kode** (`argus code`) | `[x]` MVP | repo → draf → `approve` → agen → review → `applied` → staging. PR/apply tetap oleh manusia/Claude (disengaja, `argus apply` belum ada) |
| **L2 riset** (`argus research`) | `[~]` | planner, worker web paralel, sintesis s1, checker e1, gate G1/G2/G4; web DeepSeek Search/Fetch lewat gateway OpenRouter (#285–#294) |
| **L3 gabungan** (`--from-research`) | `[~]` | urutan tetap, tanpa planner (#297) |
| **L4 hirarki** (job → planner → task riset/kode/deploy) | `[ ]` | butuh M4 + ADR-005, **belum dibenarkan bukti** |
| **L5 kemampuan baru** (gambar, video/audio, game, tool discovery) | `[ ]` | belum, gate non-kode ADR-006 belum ada |

**Milestone:** M1–M3 dan general-task agent selesai; **M6 repo→PR selesai MVP**; **M9 staging `[~]`** (production sengaja ditunda); **M4, M7, M8, capability pack `[ ]`** dan ditunda sampai ada bukti kebutuhan. **M5 `[~]`**: ledger per panggilan, inspektor, `pilot_report.py`, keputusan manusia di `job.json`; belum ada tracing/dashboard, benchmark single vs multi, eval set tidak jenuh.

**ADR:** 002 (workflow bertipe) dan 004 (durable/idempotensi/budget) `[~]` kuat; 005 dan 006 `[~]` (006 kuat khusus kode); **001, 003 `[ ]`**; 007 `[~]` — persetujuan "go live" masih di chat, tidak tercatat di job.

### Bukti nyata yang ada
- **SWE-bench sympy:** batch 3 3/4 tanpa bocoran ($0,2127), batch 4 3/5, batch 5 2/5 — sampel kecil, instance publik/kemungkinan terkontaminasi, penilai milik Argus sendiri.
- **Dogfooding:** `argus-ledger` (Python/FastAPI) 14 task; `argus-viewer` (React PWA + vitest) 2 task, $0,0198 + $0,0243, live di staging dan **dipakai Atha di HP**.
- **Riset nyata pertama "Agentic AI":** tiga job awal gagal berturut-turut lalu diperbaiki (#307 gate URL salah baca "file:", #308 halaman konfigurasi JSON raksasa, #309 alasan e1 kepanjangan). Job 3: e1 jalan, 0 UNSUPPORTED, **SUPPORTED 47% (<60%)**. #311 (s1 hanya lihat kutipan) → job 4 **17/17 SUPPORTED**, identifier di luar kutipan 27 → 0. Dua topik lain: ekonomi 85%, BRICS 93%, 0 UNSUPPORTED. Ambang v1: ≥7/8 benar, tidak ada yang salah, 0 UNSUPPORTED, ≥60% SUPPORTED, e1 selesai ≥7/8.
- **Tahap 2 sudah mulai:** `argus judge` (#316, GLM-5.3 lewat OpenRouter) — replay 11 job shadow ±$0,47, shadow batch 3 4/4 sepakat Claude, uji cacat tanam 6/6 tertangkap, retry 429 (#326) mutants 16/16. Aturan J9 disetujui 2026-11-06: Claude hanya me-review job yang diblok judge + sampel acak 1 dari 4 PASS.

## 2. Yang mau dikembangkan berikutnya

Urutan tahap sudah diputuskan Atha (2026-11-05): **1 → 2 → (3 hanya bila terbukti) → 4.**

**Tahap 1 — buktikan riset (sedang berjalan).**
- Beberapa job riset berbayar nyata terhadap ambang v1; "7/8 benar" **belum dinilai** terhadap sumber independen.
- Perbaiki worker free (NO_FINDINGS 4/9) dan worker berbayar yang masih memotong kutipan.
- Eksperimen e1 `reasoning.effort: low` dibanding nilai Claude.
- Catatan review yang belum dikerjakan: ReadDocs (`tools/web.py`) punya titik buta konfigurasi yang sama; konfigurasi `window.X = {...}`/`__NEXT_DATA__` tak terdeteksi; gate s1 masih menolak seluruh submit terakhir karena satu bagian kepanjangan; aturan "submit terakhir" tersalin di dua `gate_submit`.

**Tahap 2 — kurangi supervisi (dipilih Atha sebelum UI kontrol).**
- **Reviewer Argus / `argus judge`** sudah jalan; lanjutannya batch shadow dengan issue **singkat yang tidak dijelaskan rinci** oleh Claude (semua issue pilot selama ini ditulis Claude — sampel terlalu bersih).
- **Menit kerja Atha** per pilot: belum pernah ditanyakan.
- Kandidat `argus fix <job>` dari judge BLOCK (belum dibangun, tunggu bukti batch 5); jalur ketat.
- Celah: drafter tidak mendeteksi tes lama yang akan bocor oleh fitur baru (gerbang #275 tidak terpicu).

**Tahap 3 — satu pipeline berhirarki** (planner dengan dependensi/M4, oper hasil antar task/ADR-005, cap bertingkat, stop/retry/replan; ~1 spek + 4–6 PR jalur ketat). **Hanya kalau** ada issue yang salah dikerjakan lengan tanpa riset, atau kerja gabungan yang tak cukup dengan urutan tetap. Bukti yang ada justru **tidak** mendukung: pilot `from_research_v0` kedua lengan benar, riset 2× lebih mahal; pencarian kandidat di `research_need_v0` dihentikan karena tak ada kandidat.

**Tahap 4 — perluasan kemampuan:** satu pack per kali menurut nilai terukur, gate non-kode ADR-006 dulu, registry/policy formal (M7) saat jumlah tool menuntutnya.

**Jalur samping / operasional:** UI kontrol interaktif (fase 1 read-only bisa kapan saja; fase berbayar menunggu scope — siapa yang approve, batas $ via UI, "go live" lewat tombol, port 8711 + `permitopen` kedua); **up2 2026-11-07** (starlette 1.10.0 / fastapi 0.162.0, butuh `RUNTIMES["ledger_staging_up2"]` dulu); pin image per checkout masih disalin manual; smoke kandidat viewer tidak menguji unit systemd; self-review Argus untuk PR jalur ketat (eksperimen < $0,10).

**Ditunda secara eksplisit:** production sungguhan (pemicu: pengguna kedua, akses tanpa Termius, atau latihan deploy production), M4/M7/M8, memori berlapis, tool discovery, capability pack, idempotency key provider, artifact store.

## 3. Yang dokumen tidak menjawab

- **Tidak ada pernyataan preferensi pribadi saya** di ketiga dokumen. Semua isi "yang mau dikembangkan" di atas adalah **keputusan Atha** dan usulan Claude/GPT yang tercatat — bukan keinginan agen. Kalau pertanyaannya "menurut lu sebaiknya apa", itu tidak ada di dokumen dan saya tidak boleh mengarangnya sebagai fakta.
- **Tingkat keberhasilan umum di repo luar tanpa bocoran** tidak diketahui: SWE sample kecil, instance publik.
- **Efek petunjuk berhenti** (#188/#200/#204) belum terpisah dari variasi model.
- **Eval set v1 jenuh** (16/16, hanya regresi), jadi belum ada ukuran kemampuan yang tidak jenuh.
- **"7/8 benar"** untuk riset belum dinilai; yang ada baru persen SUPPORTED dan cek Claude atas kutipan.

## Output probe 2

Menurut saya, tiga prioritas berikut bukan yang paling terlihat seperti “fitur baru”, tapi yang paling menentukan apakah Argus bisa dipercaya dan dilepas. Saya akan menggeser fokus dari menambah kemampuan ke **bukti mutu, pengurangan supervisi, dan batas kepercayaan**.

## 1. Eval independen yang tidak jenuh — terutama untuk riset

Ini prioritas pertama saya. Dokumen menunjukkan angka keberhasilan Argus belum cukup untuk jadi dasar keputusan:

- **Eval Set v1 16/16 sudah jenuh**: `Reconciliation.md` bagian 1 baris M5 menyebut “Eval Set v1 jenuh: regresi saja”; `PENDING.md` bagian Pengukuran (M5) juga menulis “Eval Set v1 16/16 hanya regresi”.
- **SWE-bench kemungkinan terkontaminasi**: bagian 4b “Batas klaim” menyebut instance publik dan “kemungkinan terkontaminasi”; penilai juga milik Argus sendiri, bukan leaderboard.
- **Ambang riset v1 belum benar-benar terbukti**: batch v1 R1–R8 dilewati; job nyata pertama baru satu pertanyaan. Job 3 mencapai 47% SUPPORTED, job 4 menjadi 17/17 setelah #311, tetapi dokumen sendiri mencatat “n = 1 per lengan” dan “7/8 benar belum bisa dinilai dari satu pertanyaan” (bagian 4d).
- **SUPPORTED bukan berarti benar**: e1 menilai dukungan kutipan, bukan kebenaran fakta. Bagian 4d mencatat satu sumber sekunder yang kemungkinan keliru tetapi lolos karena kutipannya ada.

Karena itu, hal yang saya bangun berikutnya adalah **eval riset beku dengan cek fakta independen**, yang memisahkan: benar/salah faktual, dukungan kutipan, ada/tidaknya UNSUPPORTED, e1 selesai, biaya, dan latency. Tanpa ini, kita tidak bisa tahu apakah Reviewer Argus, UI kontrol, atau pipeline berhirarki benar-benar membantu. ADR-006 juga sudah menegaskan: jangan menetapkan ambang numerik sebelum baseline.

*Tebakan saya:* perlu belasan pertanyaan, bukan satu sampai tiga; angka pastinya harus muncul dari baseline, bukan saya karang.

## 2. Reviewer Argus + shadow mode + menit kerja manusia

Ini sudah ada di rencana sebagai “Tahap 2, kurangi supervisi”, dan saya setuju itu lebih penting daripada UI kontrol.

Buktinya:

- `Reconciliation.md` bagian 6 menempatkan “Supervisi dan melepas Argus” sebagai gap nomor 1: Claude masih menulis issue, mereview draf dan patch, dan men-deploy.
- Shadow batch 1 menemukan **2 blok nyata yang lolos gerbang harness** (`097d` dan `0e27`, `PENDING.md` bagian Shadow mode). Itu bukti bahwa “hijau” belum sama dengan “benar”.
- Shadow batch 2 terlihat bagus: 8 job bersih di-apply, 1 blok Claude, 1 berhenti di gerbang. Tapi J9 baru 4 job applied, Claude dan judge sepakat 4/4, “tanpa blok asli” — sampelnya masih kecil.
- `Reconciliation.md` bagian 4c juga mencatat “review Claude tidak mengubah hasil apa pun (sampel 2)”, jadi kita belum tahu di mana review manusia benar-benar bernilai.

Yang perlu dibangun: **Reviewer Argus murah yang menilai draf + patch + hasil tes, berdampingan dengan Claude yang menilai tanpa melihat vonisnya**, lalu ukur tingkat blok asli, alarm palsu, dan **menit kerja Atha**. `PENDING.md` bagian Pengukuran (M5) mencatat menit kerja Atha belum ditanyakan. Menurut saya, metrik “menit manusia per job yang benar” lebih penting daripada tambahan fitur.

*Yang saya tidak tahu:* berapa false alarm Reviewer Argus dan apakah model murah cukup baik. Itu justru harus diukur, bukan diasumsikan.

## 3. Batas kepercayaan untuk alur web/riset → kode

Ini poin yang menurut saya paling kurang terlihat di rencana, padahal risikonya nyata.

Arah resmi sekarang adalah `argus research`, dan `argus code --from-research` sudah diimplementasikan (#297). Artinya teks web masuk ke konteks yang kemudian bisa memengaruhi agen kode. Dokumen sudah mencatat risikonya:

- `PENDING.md` bagian “Risiko yang dicatat”: “isi web adalah data tidak tepercaya (prompt injection pada code task belum diukur)”.
- `Reconciliation.md` bagian 5, baris “Dokumen berbahaya, prompt injection”: statusnya `~`, dengan catatan “output sandbox berlabel data; teks dibersihkan dari karakter kontrol; belum diukur untuk code task”.
- ADR-007 di `FUTURE_ARCHITECTURE.md` sudah menyatakan discovered tools, external docs, project files, dan model output sebagai untrusted.

Yang saya bangun: label provenance/taint untuk konten riset, amplop “ini data, bukan instruksi”, Pembatasan apa yang boleh diteruskan dari riset ke task kode (klaim + kutipan, bukan perintah), dan tes dengan halaman web berisi prompt injection. Ini tidak perlu menunggu M7 penuh; bisa jadi penguatan kecil di jalur `--from-research`.

*Ini penilaian risiko, bukan temuan exploit:* dokumen tidak menunjukkan serangan nyata, tetapi juga tidak menunjukkan pengujiannya.

## Yang saya usulkan tidak dikerjakan sekarang: UI kontrol interaktif fase 2–4

Saya tidak akan menjadikan **UI kontrol interaktif untuk aksi berbayar/approval** sebagai proyek berikutnya. Fase 1 read-only boleh jalan sebagai side track kecil, tetapi fase 2–4 sebaiknya ditunda.

Alasannya:

- `PENDING.md` sendiri masih mencantumkan pertanyaan terbuka: siapa yang approve, batas biaya lewat UI, “go live” lewat tombol, port 8711 + `permitopen` kedua, dan waktunya terhadap up2.
- `Reconciliation.md` bagian 6 mencatat UI kontrol menyentuh ADR-007 (approval tercatat), key, dan CSRF.
- Saat ini “go live” lewat chat dan `--yes` masih bekerja. Membangun UI sebelum Reviewer Argus dan pengukuran menit manusia beresiko mengotomatiskan proses yang belum kita pahami, sekaligus menambah permukaan serangan.

Jadi urutan saya: **eval riset → Reviewer Argus/shadow + menit manusia → pengamanan riset→kode**, bukan UI kontrol atau pipeline berhirarki dulu. Pipeline berhirarki juga belum layak menurut dokumen, tetapi itu sudah eksplisit ditunda; UI kontrol justru terlihat seperti langkah berikutnya yang menggoda, dan itu yang saya hindari.

**Batas keyakinan:** saya tidak membaca kode atau `verification/`; jawaban ini berdasarkan dokumen. Saya menebak bahwa eval riset perlu diperbesar, bahwa Reviewer Argus akan menangkap sebagian blok, dan bahwa prompt injection belum diuji — ketiganya harus diverifikasi dengan pengukuran, bukan dianggap fakta.