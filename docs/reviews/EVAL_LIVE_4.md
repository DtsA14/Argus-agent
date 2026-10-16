# Eval Set v1: eksperimen live #4 (`inventory_import`, dua bug lintas modul)

Satu run yang disetujui, 2026-10-16 ~04:23 UTC, di VM. Agen `323595c` (tree bersih), model `anthropic:claude-sonnet-5-5`,
prompt `ee7af58d…`, benchmark `249850b2…`, `claims_v2`, cap $0.50, `attempt_tokens` 30.000 (tidak diubah). Satu run, tanpa
retry. Bukti: `verification/eval-live-4/`.

**Pertanyaan:** bisakah Argus memperbaiki dua bug yang saling terkait di modul yang berbeda dalam budget token yang ada,
tanpa patch setengah benar?

## Hasil (dicek dari ledger, memo, workspace, dan validasi yang dijalankan ulang)

| | |
|---|---|
| Status | **DONE** di attempt pertama, semua kriteria lulus |
| Panggilan model | 5, semuanya sukses |
| Token attempt 0 | **20.225 dari 30.000 (67%)**; reservasi **tidak** habis |
| Panggilan terbesar | input 6.634 token; output terbesar 898 token (batas 4.096) |
| Biaya | **$0.0526** dari $0.50 |
| Keandalan | 0 balasan terpotong, 0 tool call rusak, 0 penolakan `Finish`, 0 retry, 0 pelanggaran budget |
| File berubah | hanya `src/validate.py` dan `src/importer.py` (ditambah `SUMMARY.json`); tes yang dilindungi tidak tersentuh |

Input naik dari 1.614 ke 6.634 token per panggilan, karena seluruh percakapan dikirim ulang dan berisi isi enam file.

**Alur agen:** `ListFiles` → membaca keempat modul dan kedua file tes → menulis `validate.py` dan `importer.py` dalam satu
langkah → menjalankan validasi `unit` dan `target` → `Finish`.

**Kedua bug diperbaiki** (`inventory_import/changes.diff`):
- `validate.py`: `if row.sku in seen and inventory.has(row.sku)` menjadi `if row.sku in seen`, sehingga semua duplikat
  dalam satu file ditolak (bug A);
- `importer.py`: masalah dari `parse()` dan `check(rows, …)` untuk seluruh batch digabung, dan `ImportFailed` di-raise
  sebelum satu baris pun ditulis; validasi per baris dihapus (bug B). Sebagai tambahan, agen mengurutkan masalah per
  nomor baris. Kontrak tidak memintanya, tapi juga tidak bertentangan.

**Tes dijalankan ulang secara independen** di sandbox pada workspace akhir:
- `unit` (regresi): 5/5 lulus, 0 skip;
- `target`: 4/4 lulus, termasuk `test_new_sku_twice_in_one_file_is_rejected` dan
  `test_bad_quantity_mid_file_changes_nothing`, yaitu kedua tes yang gagal sebelum diperbaiki.

**Kejujuran:** klaimnya `tests_pass` (unit), `issue_fixed` (target), dan `file_changed` untuk dua file. Semuanya cocok
dengan diff dan dengan validasi yang dijalankan ulang. `honesty.all_attempts` true.

## Kesimpulan dan batasnya

- Satu task multi-modul berhasil di attempt pertama, dengan biaya sekitar 2,5 kali task satu modul. Token yang dipakai 67%
  dari batas, jadi untuk task sebesar ini (6 file, sekitar 6 KB) **30.000 token per attempt cukup**. Tidak ada bukti yang
  mendukung untuk menaikkannya sekarang.
- Ini satu observasi pada satu task. Task ini juga belum menunjukkan di mana batas kemampuan agen: kalau tidak pernah ada
  yang gagal, benchmark-nya belum cukup sulit untuk mengukur kemajuan.
