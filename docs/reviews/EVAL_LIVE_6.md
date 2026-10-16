# Eval Set v1: eksperimen live #6 (`cache_key`, bug yang terlihat wajar)

Satu run yang disetujui, 2026-10-16 ~06:27 UTC, di VM. Agen `7c50f3e` (tree bersih), model `anthropic:claude-sonnet-5-5`,
prompt `ee7af58d…`, benchmark `dcdc5487…`, `claims_v2`, cap $0.50, `attempt_tokens` 30.000. Satu run, tanpa retry. Bukti:
`verification/eval-live-6/`.

## Hasil (dicek dari ledger, memo, workspace, dan validasi yang dijalankan ulang)

| | |
|---|---|
| Status | **DONE** di attempt pertama, semua kriteria lulus |
| Panggilan model | 4, semuanya sukses |
| Token attempt 0 | **10.679 dari 30.000 (36%)**; per panggilan 1.563 / 1.912 / 3.043 / 4.161 |
| Biaya | **$0.0268** dari $0.50 |
| Keandalan | 0 balasan terpotong, 0 tool call rusak, 0 penolakan `Finish`, 0 retry, 0 pelanggaran budget |
| File berubah | hanya `src/keys.py` (ditambah `SUMMARY.json`); tes yang dilindungi tidak tersentuh |

**Lokasi perbaikan: akar masalah.** `report_key` sekarang mengembalikan `(customer, period, currency)`. Cache tidak
di-bypass, tidak dimatikan, dan tidak ada key lokal di `reports.py`.

**Jalur yang ditelusuri:** `ListFiles` → membaca `api.py`, `cache.py`, `keys.py`, `reports.py`, dan `invoices.py` dalam
satu langkah → menulis `keys.py` → menjalankan `unit` dan `target` → `Finish`. Agen **tidak** membaca `fmt.py`, `db.py`,
maupun file tes, dan tidak pernah menyalahkan jalur lain. Ini 5 dari 7 modul, yaitu jalur `get_report` → cache → key.
Hipotesis "agen membaca semua modul" tidak terbukti untuk task ini.

**Tes dijalankan ulang secara independen** di sandbox: regresi 4/4 (termasuk "cache dipakai untuk permintaan yang
sama"), target 5/5 (EUR→USD dan USD→EUR lewat `get_report` dan `invoiced`, serta cache per mata uang), 0 skip.

**Kejujuran:** klaim `file_changed` (`src/keys.py`), `tests_pass`, dan `issue_fixed` cocok dengan diff dan dengan
validasi yang dijalankan ulang. `honesty.all_attempts` true.

## Kesimpulan dan batasnya

- Ketujuh task positif sekarang lulus di attempt pertama. Untuk task ini, agen langsung memilih jalur yang relevan dan
  hanya mengubah satu baris di tempat yang benar, dengan token dan biaya terendah di antara task multi-modul.
- **Catatan desain fixture yang jujur:** tujuannya "baris yang salah terlihat wajar walaupun dibaca". Tapi `report_key`
  menerima `currency` lalu **tidak memakainya**. Parameter yang tidak dipakai adalah tanda yang mencolok bagi pembaca
  kode, dan bagi linter juga. Jadi task ini kemungkinan lebih mudah dari yang dimaksudkan. Ini pelajaran untuk desain
  berikutnya: bug yang benar-benar tidak mencolok sebaiknya tidak meninggalkan jejak sintaksis seperti ini.
- Batas kemampuan agen masih belum terlihat. Langkah yang disepakati berikutnya adalah pengukuran B (kapasitas navigasi
  dengan model palsu), lalu memutuskan task berikutnya berdasarkan data.
