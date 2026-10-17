# Pilot self-hosting #1: `argus_self_1` (Argus memperbaiki `parse_unittest` di repo-nya sendiri)

2026-10-17. Satu run yang disetujui, tanpa rerun.

| | |
|---|---|
| Basis | `c2748a7`, snapshot 154 file (tanpa `verification/` dan `fixtures/`) di `fixtures/repos/argus_self` pada VM |
| Model, budget | Sonnet 5.5, 30.000 token per attempt, `max_iterations` 3, cap $0.50 |
| Kontrak | `contract.json` (sha256 file `6fd765ea…`, kontrak beku `725b14f1…`): hanya `acceptance/validation.py` yang boleh ditulis; `pilot_tests/**` dilindungi |
| Tes | `pilot_tests/`: target 6 dan regresi 5. Baseline di sandbox asli: target gagal, regresi lulus. Fix referensi lulus keduanya. Dua fix keliru ditolak (`check_variants.py`) |

## Hasil

**`FAILED_ACCEPTANCE`**, stagnan setelah 2 attempt. Biaya **$0.1627**. 6 panggilan; `llm_call_started` = `llm_call`;
`prompt_hash` 6/6 cocok; biaya lengkap.

- Workspace **tidak berubah**: diff kosong.
- Tidak ada `SUMMARY.json`, tidak ada klaim, jadi gagal secara jujur. Tidak ada pelanggaran scope.
- Bukti ada di `evidence/`: ledger, verdict, dan audit per panggilan.

## Diagnosis: bukan budget attempt, bukan diagnosis yang salah arah, tapi **batas output satu balasan**

Kedua attempt identik:

1. Membaca `acceptance/validation.py` dan menjalankan `ListFiles`.
2. Membaca ketiga file tes pilot.
3. Memanggil `WriteFile` untuk menulis ulang `acceptance/validation.py` **utuh**. Balasannya terpotong tepat di
   **4.096 token output**, yaitu `max_output_tokens` coder di `config.yaml`. Harness tidak menjalankan tool call yang
   terpotong (sesuai desain), dan attempt berakhir `output_truncated`.

**Yang bisa dipastikan:**
- Setiap attempt hanya memakai sekitar 16 ribu dari 30 ribu token. Budget attempt **tidak** mengikat.
- Agen langsung menuju file yang benar setelah membaca tes. Tapi isi perbaikannya **tidak bisa diaudit**, lihat di
  bawah.
- File aslinya 7.065 karakter. Sebagai argumen JSON (escape) ditambah kode baru, penulisan ulang utuh mendekati atau
  melewati 4.096 token.
- Attempt kedua menerima umpan balik "target gagal" dan mengulang strategi yang sama persis, lalu terpotong di titik
  yang sama.

**Celah diagnostik:** memo hanya menyimpan argumen tool call yang berhasil diurai. Argumen `content` yang terpotong
hilang, jadi yang tersisa hanya `path`. Kita tidak bisa melihat apa yang sedang ditulis agen.

## Ini pola yang berulang, bukan kejadian tunggal

Seri live #2 run b3 (`docs/reviews/SEARCH_LIVE_2.md`) juga terpotong saat `WriteFile` menulis ulang file utuh. Di sana
penyebabnya sisa reservasi; di sini batas output per balasan.

Untuk repo nyata dengan file berukuran wajar, **menulis ulang file utuh dalam satu balasan** adalah batas keras,
bahkan untuk perbaikan satu fungsi.

## Pilihan (untuk diputuskan; tidak ada yang dikerjakan)

1. **Naikkan `max_output_tokens` coder**, misalnya ke 8.192. Ini perubahan config, murah, dan menutup kasus ini. Tapi
   hanya menggeser batas: file 15 KB akan terpotong lagi, dan output tetap mahal ($10 per juta).
2. **Tool edit**: mengganti potongan teks yang unik di sebuah file, bukan menulis ulang utuh.
   - Output kecil dan murah, konteks lebih kecil, dan menyelesaikan masalah untuk file besar.
   - Ini perubahan tool di harness, jadi perlu desain dan tes. Termasuk keamanan path dan kunci memo yang
     membawa versi tool.
3. **Simpan teks mentah balasan yang terpotong** (secara terbatas) agar kegagalan seperti ini bisa diaudit. Ini
   perubahan kecil di jalur ledger atau memo.

Usul: 2 dan 3. Opsi 1 hanya sebagai pembanding cepat jika diperlukan. Pilot ini sendiri tidak diulang tanpa
persetujuan baru.

## Koreksi diagnosis (2026-10-17, setelah review)

Metadata usage yang tersimpan di memo menunjukkan bahwa kedua balasan yang terpotong **memakai sebagian besar jatah
output untuk thinking** (penalaran internal model, hanya tersimpan sebagai signature):

| Balasan terpotong | Output | Thinking (`output_token_details.reasoning`) | Tersisa untuk `WriteFile` |
|---|---|---|---|
| attempt 1, langkah 3 | 4.096 | **2.505** (61%) | sekitar 1.590 |
| attempt 2, langkah 3 | 4.096 | **3.093** (75%) | sekitar 1.000 |

Jadi kalimat di atas, "penulisan ulang utuh mendekati atau melewati 4.096 token", **tidak tepat**. File 7 KB butuh
sekitar 2–2,5 ribu token. Yang terpotong adalah **thinking ditambah penulisan file utuh**. Panggilan lain (membaca file)
tidak memakai thinking sama sekali.

**Isi `content` yang terpotong memang tidak dikembalikan API:** blok `tool_use` hanya berisi `path`. Karena itu
penyimpanannya tidak mungkin tanpa streaming, dan sebagai gantinya ledger kini mencatat `reasoning_tokens` dan
`stop_reason` per panggilan.

**Keputusan setelah koreksi (review):**
- tool edit (`EditFile`) dan pencatatan ledger dikerjakan;
- pilot berikutnya hanya dengan `EditFile` dan `max_output_tokens` tetap 4.096;
- menaikkan batas output menjadi hipotesis terpisah.

## Pilot self-hosting #2: `argus_self_2` (dengan `EditFile`)

2026-10-17. Satu run yang disetujui. Harness `e38cc48`, snapshot yang sama (`validation.py` identik), dan kontrak
`contract2.json` yang hanya menambah `tools: ["edit_file"]`. Budget dan batas output tetap: 30.000 token per attempt,
3 attempt, cap $0.50, `max_output_tokens` 4.096. Bukti: `evidence_2/`.

**Hasil: DONE di attempt ke-3, $0.1853.**
- 8 panggilan dan 1 penolakan reservasi.
- `prompt_hash` 9/9 cocok dengan prompt efektif `fc0d0ce1…`.
- Biaya lengkap. Scope terjaga: hanya `acceptance/validation.py` yang berubah.

| Attempt | Yang terjadi (ledger: `reasoning_tokens`, `stop_reason`) |
|---|---|
| 1 | dua `EditFile` dalam satu balasan, tetap terpotong: output 4.096 dengan thinking 3.147, `max_tokens` |
| 2 | satu `EditFile` berhasil (output 3.901, thinking 2.948, `tool_use`), ditambah `RunValidation` target dan unit. Panggilan berikutnya ditolak reservasi (butuh input 14.545, sisa 6.452) |
| 3 | umpan balik berbasis verdict (M3): validasi lulus, hanya `SUMMARY.json` yang kurang. Baca file lalu `Finish` (output 725) → **DONE** |

**Perbandingan dengan pilot 1** (hanya `EditFile` yang berbeda):
- pilot 1 gagal karena kedua penulisan ulang file utuh terpotong;
- di pilot 2 sebuah edit berhasil di attempt ke-2, dan umpan balik verdict menyelesaikannya.

Ini bukti kausal awal untuk task ini, bukan bukti umum. Thinking tetap memakai 2,9–3,1 ribu dari 4.096 token di
langkah yang sulit, dan attempt 1 tetap terpotong walaupun memakai `EditFile`.

**Verifikasi independen:**
- tes target 6/6 dan regresi 5/5 dijalankan ulang di luar workspace;
- kasus tambahan lulus: skip lalu fail → FAIL; fail lalu skip → FAIL; error, fail, error → ERROR; docstring ditambah
  subTest gagal → FAIL;
- diff yang byte-identik diterapkan ke branch dari main: tes parser dan codetask 133 lulus, ditambah `verify.sh`
  penuh.

**Satu celah yang ditemukan, juga ada di fix referensi kami:** subTest berbentuk pesan, `subTest("case a")` (dicetak
`[case a]`), tetap menghasilkan status `''` (`msg_subtests.py`).
- Ini **tidak membuat aman menjadi bahaya**: `''` tetap bukan `ok`, sehingga acceptance tetap menggagalkannya, sama
  seperti sebelum fix.
- Tapi perbaikannya **belum lengkap**. Penyebabnya celah di tes yang kami tulis, karena tes terlindung tidak mencakup
  bentuk `[msg]`. Agen memenuhi kontrak seperti yang tertulis.
