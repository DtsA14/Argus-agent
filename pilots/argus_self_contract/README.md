# Pilot self-hosting #3: `argus_self_3` (validasi konsistensi `must_pass` di `acceptance/contract.py`)

2026-10-17. Satu run yang disetujui, tanpa rerun.

## Setup

| | |
|---|---|
| Harness | `f51a8b2` (main dengan #69–#71), tree bersih |
| Snapshot | 173 file dari `f51a8b2`, tanpa `verification/`, `fixtures/repos/` dan `pilots/`; 16 kontrak di `fixtures/contracts` ikut |
| Kontrak | `evidence/contract3_input.json` (sha256 `ef8642b2…`). Hanya `acceptance/contract.py` yang boleh ditulis; `pilot_tests/**` dilindungi; `tools: ["edit_file"]` |
| Budget | 30.000 token per attempt, 3 attempt, cap $0.50, `max_output_tokens` 4.096 (sama dengan pilot 1 dan 2) |

**Tes (`pilot_tests/`), berbasis ground truth.** Sembilan kombinasi `-s`/`-t`/`-p`/`-k` dijalankan ke unittest sungguhan.
- **Target (7):**
  - setiap tes yang benar-benar ditemukan harus diterima;
  - 23 tes yang ada tapi tidak terjangkau oleh opsinya harus ditolak, dengan `validation[i]` dan id tesnya;
  - duplikat ditolak;
  - nama yang bukan id unittest ditolak;
  - hanya tes yang bermasalah yang dilaporkan;
  - tanpa `must_pass` tidak ada yang berubah;
  - tes yang filenya mungkin tidak ada **tidak boleh** ditolak, karena validator statis tidak membaca file.
- **Regresi (7):** 16 kontrak repo tetap valid, ditambah aturan validasi yang sudah ada.

**Sebelum run:**
- Di sandbox asli, kode sekarang gagal di target dan lulus di regresi; fix referensi lulus keduanya.
- Lima varian keliru tertangkap (`check_variants.py`).
- Dry run dengan model palsu: dua `EditFile` → DONE.
- Tes awal kami sendiri sempat salah: kami mengira id yang sama selalu menunjuk file yang sama, padahal itu tergantung
  direktori top-level. Tes diperbaiki sebelum izin live.

## Hasil

**`FAILED_ACCEPTANCE`**, stagnan setelah 2 attempt. Biaya **$0.1797**.
- 6 panggilan; `prompt_hash` 6/6 cocok; biaya lengkap.
- Workspace **tidak berubah**, tidak ada `SUMMARY.json`, tidak ada klaim, scope terjaga. Gagal secara jujur.
- Bukti ada di `evidence/`; `caps.txt` berisi batas output per panggilan.

| Attempt, langkah | Input | Batas output | Output | Thinking | Stop | Tool call |
|---|---|---|---|---|---|---|
| 1, 1–2 | 2.120, 8.430 | 4.096 | 82, 178 | 0 | `tool_use` | `ListFiles`, membaca `contract.py`, tes pilot, `validation.py`, helpers |
| 1, 3 | 14.652 | 4.096 | 4.096 | **4.096** | `max_tokens` | **tidak ada** |
| 2, 1–2 | 2.648, 8.958 | 4.096 | 82, 178 | 0 | `tool_use` | jalur baca yang sama |
| 2, 3 | 15.180 | **2.954** | 2.954 | **2.954** | `max_tokens` | **tidak ada** |

## Diagnosis

**Penyebabnya bukan alat edit dan bukan diagnosis yang salah arah.** Model menghabiskan **seluruh** jatah output
langkah ketiga untuk thinking, dan tidak sempat mengeluarkan satu tool call pun. `EditFile` tidak pernah terpakai.
Task ini lebih sulit dari bug parser, jadi pikirannya lebih panjang.

**Dua batas saling mengunci:**
- **Batas output per balasan (4.096):** di attempt 1, thinking memakai 100% dan masih terpotong.
- **Sisa reservasi attempt:** setelah input sekitar 15 ribu token di langkah ketiga (kontrak, tes pilot,
  `validation.py`), attempt hanya tersisa **4.538** (attempt 1) dan **2.954** (attempt 2). Harness memotong batas
  output ke sisa itu, sehingga attempt 2 bahkan lebih sempit.
- Akibatnya, **menaikkan `max_output_tokens` saja hampir tidak berpengaruh di 30k**: batasnya menjadi
  min(8.192, 4.538) = 4.538.
- Di pilot 2, input langkah yang sama hanya sekitar 9–10 ribu, sehingga tersisa sekitar 10 ribu dan edit-nya muat.

Umpan balik attempt ke-2 (kriteria yang gagal, validasi target gagal) tidak mengubah strategi: jalur bacanya sama
persis.

**Tidak bisa dipastikan:** apa isi pikirannya, dan apakah ia akan menemukan implementasi yang benar dengan ruang lebih.
Thinking hanya tersimpan sebagai signature.

## Pilihan berikutnya (untuk diputuskan, tidak ada yang dikerjakan)

1. **Satu run dengan profil task besar:** `attempt_tokens` 45.000 **dan** `max_output_tokens` 8.192.
   - Ini dua angka, tapi satu variabel ruang: batas output tidak berpengaruh tanpa ruang attempt, dan ruang attempt
     tidak membantu jika satu balasan tetap dibatasi 4.096.
   - Datanya: eksperimen budget (45k menang 9/9 vs 3/9) dan pilot ini (thinking 100% di batas).
   - Preseden: evaluator sudah 8.192 karena thinking.
2. **Membatasi thinking** (budget thinking dari provider). Ruang untuk tool call terjaga, tapi bisa menurunkan kualitas
   pada task yang memang butuh berpikir. Perlu desain sendiri.
3. **Berhenti di sini** dan mencatat bahwa task dengan konteks sekitar 15 ribu dan penalaran berat tidak muat di 30k/4.096.
