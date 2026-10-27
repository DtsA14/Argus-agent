# Pilot SWE v0 batch 2: hasil

2026-10-24, job `j20261024_181455_d71c`, `sympy__sympy-24443` (satu-satunya dari tiga instance sympy berat yang layak di Python 3.12,
lihat `PREFLIGHT.md`). DeepSeek V4.1 Flash thinking, environment `sympy` (image `sha256:de306e046ab6…`, dipin). Artefak:
`sympy__sympy-24443/live/`, penilaian: `sympy__sympy-24443/grade.json`.

> **Oracle-assisted** (review Atha 2026-10-27): draf `d1` ditolak dan di-redraft **karena** tes drafter gagal di atas patch resmi
> maintainer, yang dijalankan sebelum approve. Itu menyaring draf dengan jawaban yang tidak ada di repo nyata. Hasil batch ini tidak
> dicampur dengan batch tanpa bocoran (batch 3 dan sesudahnya).

## Hasil: `resolved` setelah satu redraft, satu perbaikan harness (#200), dan `retry`

| Tahap | Hasil | Biaya | Catatan |
|---|---|---|---|
| `d1` drafter | `DRAFTED`, 1 submit | $0,0152 | **tidak di-approve**: satu tes (hijau di baseline) menuntut `_check_homomorphism` mengembalikan false untuk input cacat (`Permutation(1, 3)` berukuran 4 di grup berukuran 5); dengan patch maintainer itu `KeyError`, jadi tes drafter di atas patch resmi 2/3 |
| `d2` redraft | `DRAFTED`, 1 submit | $0,0126 | tes negatif cacat hilang; tes drafter di atas patch resmi **2/2**; di-approve |
| `a1` agen | `FAILED_ACCEPTANCE` (stagnan, 2 attempt) | $0,0207 | kedua attempt **`output_truncated`** di langkah 3: thinking memakai 7.858 dan 8.192 dari 8.192 token output, balasan terpotong sebelum panggilan tool apa pun |
| #200 | `max_output_tokens` per model (DeepSeek 32.000 di profil USD) dan petunjuk setelah `output_truncated` | – | spek, 7 tes, mutan 7/7, verify PASS |
| `a2` retry | `DONE`, 1 attempt, 8 langkah | $0,0122 | carry dari `a1` (`output_truncated`, tanpa menulis); satu `edit_file` (menulis ulang `_image()`, 41 baris), validasi otomatis, `RunValidation`, `Finish` |
| Penilai | **`resolved: true`** (`FAIL_TO_PASS` 1/1, `PASS_TO_PASS` 1/1) | – | tes drafter di atas patch resmi: pass |
| **Job** | **REVIEW_READY**, dinilai resolved | **$0,0606** dari cap $1,00 | |

**Batch 2: 1/1 `resolved`**, tetapi baru setelah redraft (keputusan Atha) dan retry yang didahului perbaikan harness. Bukan hasil
sekali jalan, dan tidak dihitung bersama batch 1 seolah sama.

## Yang dipelajari

- **Cek tes drafter di atas patch resmi sebelum approve menangkap draf yang mengunci perilaku di luar issue** (`d1`). Tanpa cek itu,
  agen akan dipaksa memenuhi syarat yang perbaikan maintainer sendiri tidak penuhi. Cek ini dijalankan di sisi Claude (tanpa biaya
  model, tes resmi tetap tersembunyi dari drafter dan agen), bukan bagian dari harness.
- **Mode gagal baru: thinking menghabiskan jatah output** (`a1`). Harness menolak menjalankan balasan terpotong dan berhenti di
  `stagnant` dengan biaya kecil, sesuai rancangan, tapi attempt 2 tidak diberi tahu apa yang terjadi.
- **`a2` berhasil, tapi penyebabnya belum bisa dipisahkan:** balasan terbesar `a2` hanya 5.519 token output (4.902 reasoning), di
  bawah batas lama 8.192. Jadi pada run ini bukan batas 32.000 yang menentukan; yang berbeda adalah petunjuk carry ("balasan pendek,
  `EditFile` bertahap") dan variasi model. Satu run tidak bisa memisahkannya (sama seperti router #3).
- Patch agen berbeda dari patch maintainer dan lebih ringkas di `_image()` (pemetaan simbol presentasi ke gambar generator), sesuai
  saran issue "the whole thing can be greatly simplified"; dinilai dengan tes resmi.

## Batas klaim

Sama dengan batch 1: harness, bukan model; penilaian ala SWE-bench (Python 3.12, penilai milik Argus); instance publik.

## Supervisi

Keputusan Atha untuk run: "go live" (`code`), "y" (redraft, setelah ringkasan yang menunjukkan masalah `d1`), "y" (approve `d2`),
"merge" + "y" (retry, setelah #200) = **4**, plus review spek/kode #200. Waktu dari ringkasan `d2` dikirim sampai "y":
`review_times.txt`.
