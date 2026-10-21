# Rekonsiliasi `FUTURE_ARCHITECTURE.md` dan `PENDING.md`

Status: **laporan; urutan dan arah disetujui GPT dan Atha pada 2026-10-21** (keputusan di bagian 8). Ditulis 2026-10-21. Basis: `main` pada `8fb3517` (setelah pilot M6 pertama).
Tanpa perubahan kode. Status di bawah berasal dari catatan `PENDING.md` dan dokumen di `docs/reviews/`, bukan dijalankan
ulang; tiga klaim diverifikasi langsung ke kode dan ditandai.

## 1. Milestone dan statusnya di kedua dokumen

| Milestone | `FUTURE_ARCHITECTURE.md` (rencana) | `PENDING.md` (status) | Selaras? |
|---|---|---|---|
| M1–M2 | tidak disebut | selesai | n/a |
| M3 evaluasi | andal, grounding, output rusak, kalibrasi | `[x]` ditutup (`M3_CLOSING.md`) | ya |
| **M4** | **multi-agent paralel** dengan dependensi | `[ ]` belum mulai. Tetapi `docs/reviews/REVIEW_M4_SLICE1A.md` dan `REVIEW_M4_SLICE1B.md`, serta docstring `codetask/` dan `acceptance/contract.py`, memakai label "M4 slice 1" untuk **agen tunggal task umum** | **konflik nama** |
| M5 | observability dan benchmark single vs multi-agent | `[ ]`; isinya tersebar di "Milestone 4+" | **dua daftar berbeda** |
| M6 | repo → PR | roadmap `[ ]`, bagian M6 W0–W5 `[x]`, pilot 1 `[x]` | **PENDING bertentangan dengan dirinya sendiri** |
| M7–M9 | registry/policy/MCP; penemuan tool; deployment terkendali | `[ ]` | ya |

## 2. Konflik yang benar-benar ada

1. **Label "M4".** Kode dan review yang sudah selesai (agen tunggal task umum) dinamai "M4 slice 1", padahal M4 di
   spesifikasi adalah multi-agent paralel. Pembaca `REVIEW_M4_SLICE1B.md` bisa mengira multi-agent sudah dimulai.
   Usul: ganti nama menjadi "general tasks" atau "M4-prep" di dokumen.
2. **Status M6 di `PENDING.md` basi dan kontradiktif.**
   - Header bagian M6 masih menulis "implementasi ditahan sampai rencana, kriteria acceptance, dan preflight disetujui".
   - `[ ] Review rencana M6` belum dicentang, padahal W0–W5 dan pilot sudah di `main`.
   - Roadmap `- [ ] M6` belum dicentang.
   - `W2 (rencana awal)` masih `[ ]` berdampingan dengan W2a `[x]` dan W2b `[ ]` (pecahan dari W2 itu).
3. **Catatan "diselaraskan saat M6 selesai" jatuh tempo.** `PENDING.md` menulis sendiri bahwa roadmap spesifikasi dan
   daftar "Milestone 4+" akan diselaraskan setelah M6. Tabrakan konkretnya:
   - "Approval manusia untuk aksi berisiko" sama dengan ADR-007.
   - "Tracing / dashboard" sama dengan M5.
   - "Eval set 10–20 task, single vs multi-agent" sama dengan M5.
   - "Deploy harness sebagai service di OCI" **bukan** M9: M9 adalah Argus men-deploy produk buatannya, bukan men-deploy
     Argus sendiri.
4. **ADR dicatat "belum diperiksa", padahal sebagian sudah ada di kode.** Di `PENDING.md` semua ADR `[ ]` polos, dan
   header spesifikasi menyatakan belum dicek terhadap kode. Dari gap analysis (`M6_GAP_ANALYSIS.md`) dan bukti pilot,
   untuk code task:

   | ADR | Kenyataan di kode |
   |---|---|
   | 004 durable, idempotensi, budget | **Sebagian besar ada**: reservasi dari ledger, `durability="sync"`, memo per langkah, resume lintas proses. Belum: idempotency key sisi provider |
   | 006 quality gate | **Ada**: kontrak beku, verdict dengan bukti, validasi ulang independen. Belum: gate non-kode |
   | 007 keamanan dan approval | **Sebagian**: allowlist tool, scope, path jail, sandbox. Belum: layanan approval dan policy |
   | 005 artifact | **Sebagian**: run dir, hash, provenance, paket review (W3). Belum: store dan versioning |
   | 002 workflow bertipe | **Sebagian**: `nodes/plan.py` memvalidasi rencana untuk graph laporan data, dan draf W2a bertipe. Belum: planner untuk code task |
   | 001 registry, 003 memori | belum |

5. **Item `[ ]` yang kemungkinan basi, bukan pekerjaan terbuka:** "Sign-off M1" dan "Review rencana M3". Keduanya milestone
   yang sudah ditutup. Belum bisa dipastikan apakah sign-off itu pernah terjadi: **belum terverifikasi**, bukan "selesai".
6. **Struktur bagian 1, 3, 4 `PENDING.md` basi.** Isinya masih M2 (2b/2c/2d) yang sudah menjadi sejarah. Bukan konflik isi,
   tetapi membuat dokumen sulit dibaca sebagai daftar kerja.

## 3. Terbukti, rencana, dan asumsi

**Terbukti dengan bukti (tercatat di `PENDING.md` dan `docs/reviews/`):**
- Agen tunggal menyelesaikan task kecil dan menengah: `Slice 1` live $0.0217; baseline lintas task **16/16** dan 4/4
  gagal jujur ($0.65). Hasil ini membuat suite v1 **jenuh**: cocok untuk regresi, tidak untuk mengukur batas kemampuan.
- Budget menjadi pengikat: 30k 3/9 vs 45k 9/9. Umpan balik antar-attempt menaikkan sukses 0/9 menjadi 4/9.
- Kejujuran: 0 klaim palsu di semua eksperimen live, termasuk tiga task negatif (tiga observasi, bukan statistik).
- Self-hosting: `argus_self_1` gagal jujur ($0.1627), `argus_self_2` `DONE` di attempt 3 ($0.1853).
- **M6 jalur penuh:** W0–W5 di `main`; pilot 1 `agent-completed`: `DONE` 1 attempt, 4 panggilan, **$0.0575**, patch identik
  dengan patch referensi manusia, `verify.sh` 1154 lulus dan 0 skip sandbox, supervisi ~10 menit (estimasi).
- Tool pencarian read-only dipakai tetapi tidak mengubah sukses (~2% hemat token).

**Belum terbukti, atau hanya rencana:**
- Tingkat sukses umum. Pilot 1 hanya satu task kecil, dan tidak membedakan: patch persis sama dengan referensi menandakan
  task mudah.
- Repo selain Argus. Athena butuh image sandbox per proyek; JS (bulking-app) belum bisa divalidasi sama sekali.
- Drafter model (W2b), planner penuh, M4 multi-agent, approval, registry, memori, deployment.
- Idempotency di sisi provider.

## 4. Pekerjaan terbuka nyata (di luar roadmap besar)

| Item | Sumber | Catatan |
|---|---|---|
| `evals/runner.py:126` menghitung biaya tak diketahui sebagai `$0` (`usd_billed or 0.0`) | PENDING `[ ]`; **diverifikasi di kode** | Melanggar aturan "biaya tidak diketahui adalah `null`, bukan 0" (`AGENTS.md`). Kecil, tetapi menyentuh uang |
| Tes eval di sandbox terlalu banyak (`verify.sh` makin lama) | PENDING `[ ]` | Efisiensi |
| Perluasan benchmark dari kegagalan nyata, lalu bekukan hash v1 | PENDING `[ ]` | Berhubungan langsung dengan pertanyaan eksperimen berikutnya |
| `intake_repo.py --check <task> --repo` memberi mismatch palsu untuk record task | temuan pilot 1; belum di PENDING (kini dicatat di catatan pilot) | Membandingkan dengan tree commit tanpa tes yang disetujui |
| Judul `PR.md` terpotong di tengah kata | temuan pilot 1 | Kosmetik |
| `is_peak` (`models/pricing.py`) salah untuk jendela jam yang melewati tengah malam | temuan baru, **diverifikasi** (jendela 22–4 UTC: jam 23 dan 2 sama-sama `False`) | **Laten, bukan aktif**: jendela di `config.yaml` (1–4 dan 6–10 UTC) tidak melewati tengah malam. Menyentuh uang, jadi bukan task pilot |

## 5. Urutan milestone yang direkomendasikan, dengan dependensi

1. **Selaraskan dokumen** (docs saja, tanpa biaya): perbaiki status M6, ganti nama label "M4 slice", satukan "Milestone 4+"
   dengan M4–M9 spesifikasi, tandai ADR sebagian-ada dengan buktinya, tulis ulang bagian 1, 3, 4 `PENDING.md`.
   Dependensi: tidak ada.
2. **Tutup utang kecil yang menyentuh uang:** runner eval fail-closed untuk biaya tak diketahui, dengan tes yang gagal di
   kode lama. Dependensi: tidak ada; proses ketat karena menyentuh uang (tes, mutan, `verify.sh`).
3. **Tetapkan satu pertanyaan eksperimen** (bagian 6). Ini menentukan isi langkah berikutnya.
4. **M7 (registry dan policy) dan M4 (multi-agent) ditunda.** Syaratnya adalah bukti hambatan, dan sejauh ini tidak ada.
   Manusia masih membuka PR, jadi layanan approval belum dibutuhkan.
5. **M8, M9, dan capability pack:** prasyaratnya belum ada.

## 6. Apakah pilot M6 kedua diperlukan?

Tergantung pertanyaannya.

- **"Di mana batas kemampuan coder dan berapa biayanya?"** Ya, pilot kedua bernilai, asal berbeda bermakna dari pilot 1.
  Pilot 1 tidak menjawabnya karena terlalu kecil. Opsi: task multi-file di Argus (murah, jalurnya sudah terbukti), atau
  repo lain seperti Athena (lebih informatif soal generalisasi, tetapi butuh image sandbox per proyek, dan batas
  `.gitattributes` di `REVIEW_M6_W3.md` perlu dicek untuk repo itu).
- **"Siap ke multi-agent atau tool governance?"** Tidak ada bukti yang menuntutnya. Jangan dibuka sekarang.
- **Pilot kedua hanya untuk memakai W2b (drafter model):** tidak disarankan. Baseline hijau di W2a mewajibkan **patch
  referensi buatan manusia**. Model boleh menyusun draf dan tes, tetapi manusia tetap harus menyelesaikan task-nya sendiri
  untuk membuktikan kriterianya bisa dipenuhi, jadi bagian yang mahal tetap manual. Di pilot 1 bagian mahal itu adalah
  penyusunan draf, tes, dan patch referensi; supervisi manusia hanya ~10 menit.

**Rekomendasi:** kerjakan langkah 1 dan 2 dulu (murah, tanpa model berbayar). Pilih pilot kedua hanya jika pertanyaannya
adalah batas kemampuan coder, dengan task multi-file di Argus sebagai langkah pertama yang aman.

## 7. Keputusan yang dibutuhkan

1. Apakah urutan di bagian 5 disetujui?
2. Apakah pertanyaan eksperimen berikutnya adalah "batas kemampuan coder"?
3. Apakah label "M4 slice 1" diganti nama di dokumen (docs saja)?

## 8. Keputusan (GPT dan Atha, 2026-10-21)

1. **Urutan di bagian 5: disetujui, dengan satu perubahan.** Perbaikan biaya eval yang tak diketahui dikerjakan sebagai
   task terpisah dengan tes regresi ketat, dan **tidak boleh otomatis diubah menjadi angka atau perilaku tertentu**
   sebelum kontrak data dan semua pemakai `evals/runner.py` diperiksa. Prinsipnya: biaya yang tidak diketahui tetap
   unknown, tidak pernah diam-diam dianggap nol. M4 dan M7 ditunda; M8, M9, dan capability pack tetap di parking lot.
2. **Pertanyaan eksperimen berikutnya:** seberapa baik coder menyelesaikan task **multi-file nyata** dengan kriteria
   acceptance deterministik, dan berapa biaya serta supervisi manusia yang dibutuhkan. Task multi-file di repo Argus
   sendiri (bukan Athena dulu). `.gitattributes` dan batas patch diperiksa sebelum task disetujui. Dicatat per pilot:
   hasil dan acceptance, biaya/attempt/panggilan, waktu supervisi, apakah patch identik dengan referensi atau butuh
   intervensi, dan kegagalan jujur versus klaim sukses yang tidak didukung.
3. **Label "M4 slice 1": diganti nama menjadi "general-task agent"** (preferensi GPT), karena M4 di spesifikasi berarti
   multi-agent paralel. Dilaksanakan 2026-10-21: `REVIEW_M4_SLICE1A.md` dan `REVIEW_M4_SLICE1B.md` menjadi
   `REVIEW_GENERAL_TASK_1A.md` dan `REVIEW_GENERAL_TASK_1B.md`, dan rujukannya di `PENDING.md` dan `codetask/__init__.py`
   (docstring) diperbarui. Bagian 1 dan 2 di atas menyebut nama lama sebagai kondisi saat laporan ditulis.
4. **Urutan kerja:** (1) merge laporan ini; (2) rapikan `PENDING.md` dan label milestone, dengan status dibedakan menjadi
   selesai, sebagian tersedia, belum diverifikasi, dan belum dimulai; (3) task terpisah untuk biaya yang tak diketahui;
   (4) Claude mengusulkan maksimal tiga kandidat pilot multi-file, tanpa implementasi; (5) pilih satu dan bekukan
   acceptance criteria sebelum membuat draf.


## 9. Pembaruan setelah pilot 2–5 (2026-10-22)

Bagian 1–8 di atas adalah laporan 2026-10-21 dan tidak ditulis ulang. Bagian ini mencatat apa yang berubah sejak itu. Sumber: `PENDING.md`, `pilots/*/`, dan `verification/`.

### 9.1 Pilot M6 yang sudah dijalankan (semuanya Argus sendiri, model Sonnet 5.5)

| Pilot | Task | Hasil | Biaya live | Catatan |
|---|---|---|---|---|
| 1 | `run_stats` melewati baris bukan-JSON | `agent-completed` | $0,0575 | 1 attempt, patch identik dengan referensi |
| 2 | validasi `--impl` di `main.py` (2 file) | `agent-completed` | $0,0795 | 2 attempt; attempt 1 `reservation_exhausted` di profil `default`, pulih lewat umpan balik |
| 3a | pembaca run bersama + refactor 2 skrip (3 file) | **`failed`** | $0,2000 | 2 attempt, keduanya `reservation_exhausted`; 9 dari 16 tes lulus; satu impor yang kurang menggagalkan dua tes wajib |
| 4 | `is_peak` melewati tengah malam (1 fungsi) | 2 dari 2 `DONE` (`pilot4c` sengaja tidak dijalankan) | $0,0289 + $0,0289 | patch **byte-identik** di dua run; diterapkan di PR #109 |
| 5a | `is_peak` gagal tertutup (1 fungsi, spesifikasi lebih ketat) | `DONE` | $0,0426 | 1 attempt; patch menunggu merge di PR #115 |

Total biaya live pilot 1–5a ±$0,44. Waktu supervisi: ~10 menit (estimasi) untuk pilot 1 dan 2; **unknown** untuk 3a–5a (tidak dicatat saat berjalan).

### 9.2 Yang kini terbukti, dan yang belum

**Lebih kuat dari sebelumnya (tetap sampel kecil, bukan tingkat sukses):**
- Task satu fungsi dengan acceptance deterministik: tiga run berturut-turut (4a, 4b, 5a) `DONE` di attempt pertama, masing-masing 3 panggilan dan di bawah $0,05; pada pilot 4 hasilnya byte-identik antar run.
- Acceptance dibekukan sebelum coder (tes merah di baseline karena assertion, tes pembeda, patch referensi, mutan, `verify.sh`) membuat hasil agen bisa dinilai tanpa bergantung pada kesan: patch agen dibandingkan dengan referensi pada ratusan ribu kasus.
- Kegagalan jujur dan terbaca: 3a gagal dengan jejak lengkap (`failure_trace.py`, `audit_run.py`), tanpa klaim palsu, dan penyebabnya (reservasi token yang dimakan bacaan ekstra) sesuai dengan arah simulasi.

**Pelajaran dari 3a yang berubah menjadi praktik:**
- Simulasi token wajib memasukkan skenario "agen membaca semua berkas yang terkait"; satu bacaan ekstra (modul data emas 15 KB yang saya anggap tidak dibaca) mengubah hasil 3a.
- Task yang terlalu besar untuk satu attempt dipecah, bukan diberi budget lebih besar; cap pilot ($0,75) dan profil `large` dipakai hanya per pilot, `config.yaml` tetap $0,50; `reservation_exhausted` dicatat sebagai hasil, tidak dikejar dengan menaikkan budget.
- Jalur operasional (skrip go-live) diikat ke kontrak, hash, config, dan batas, diuji, dan berada di repo.
- Celah spesifikasi menjadi pilihan model, bukan acak: `utc_hours` yang hilang diisi `False` pada dua run identik; Pilot 5 menutupnya dengan aturan eksplisit.

**Belum terbukti:**
- Tingkat sukses umum; batas ukuran task. Antara satu fungsi (3 dari 3 `DONE`) dan tiga file (gagal) belum ada titik ukur; Pilot 2 (dua file) `DONE` di attempt kedua.
- Dua hipotesis harness yang muncul dari 3a dan **belum diuji**: umpan balik yang mengarahkan perbaikan kegagalan validasi lebih dulu (di 3a agen melihat `NameError` dua kali dan tidak memperbaikinya), dan `ReadFile` dengan rentang baris untuk berkas besar. Hanya ada satu pengamatan; perubahan harness inti baru layak bila pola itu terulang.
- Repo selain Argus (Athena butuh image sandbox per proyek; JS belum bisa divalidasi); drafter model (W2b); M4/M7+.

### 9.3 Utang yang ditutup dan yang masih terbuka

Ditutup sejak laporan: biaya tak diketahui di jalur eval (PR #96), `Checks.add` (PR #94), crash `runner.py` saat resume (PR #98), `is_peak` melewati tengah malam (Pilot 4, PR #109), `is_peak` gagal tertutup (Pilot 5; PR #115).
Masih terbuka: judul `PR.md` terpotong di tengah kata (kosmetik; berkas `codetask/review.py` 30 KB, jadi juga kandidat uji "berkas besar"); `intake_repo.py --check <task> --repo` memberi mismatch palsu untuk record task; skrip offline lain yang masih memakai `json.loads` per baris
(dipersempit menjadi `audit_run.py` dan `failure_trace.py`, yang dicakup 3a); tes eval di sandbox yang membuat `verify.sh` makin lama (kini ±13 menit); perluasan benchmark dari kegagalan nyata.

### 9.4 Arah berikutnya (usulan; keputusan di reviewer dan Atha)

1. Merge PR #115 (patch Pilot 5a, byte-identik) setelah reviewer membaca diff.
2. Satu pilot untuk mengukur batas ukuran task, bukan menaikkan budget: kandidat terdekat adalah "3a-lite" (pembaca run bersama + `failure_trace.py` saja, dua file; acceptance 3a sudah ada dan hanya dipersempit), dengan simulasi token yang sama ketatnya.
3. Menunda perubahan harness (umpan balik, rentang baris) sampai ada pola kegagalan yang terulang.
4. Mulai mencatat waktu supervisi saat run berjalan.
