# Eval Set v1: eksperimen live #5 (`money_precision`, diagnosis akar masalah)

Satu run yang disetujui, 2026-10-16 ~05:26 UTC, di VM. Agen `affaf2b` (tree bersih), model `anthropic:claude-sonnet-5-5`,
prompt `ee7af58d…`, benchmark `32aff757…`, `claims_v2`, cap $0.50, `attempt_tokens` 30.000 (tidak diubah). Satu run, tanpa
retry. Bukti: `verification/eval-live-5/`.

**Pertanyaan:** bisakah Argus menelusuri gejala di invoice ke parser bersama, lalu membuktikan perbaikannya di semua alur
yang terdampak?

## Hasil (dicek dari ledger, memo, workspace, dan validasi yang dijalankan ulang)

| | |
|---|---|
| Status | **DONE** di attempt pertama, semua kriteria lulus |
| Panggilan model | 4, semuanya sukses |
| Token attempt 0 | **11.615 dari 30.000 (39%)**; per panggilan 1.547 / 1.881 / 3.524 / 4.663 |
| Biaya | **$0.0313** dari $0.50 |
| Keandalan | 0 balasan terpotong, 0 tool call rusak, 0 penolakan `Finish`, 0 retry, 0 pelanggaran budget |
| File berubah | hanya `src/money.py` (ditambah `SUMMARY.json`); `invoice.py` dan tes yang dilindungi tidak tersentuh |

**Lokasi perbaikan: di sumbernya.** `int(float(text) * 100)` diganti menjadi
`units, _, frac = text.partition(".")` dan `int(units) * 100 + int(frac.ljust(2, "0") or "0")`. Itu aritmetika bilangan
bulat dari digit-digitnya, benar untuk berapa pun besarnya. `invoice.py` tidak ditambal.

**Alur agen:** `ListFiles` → membaca `money.py`, `invoice.py`, `refunds.py`, `tax.py`, dan `tests/test_amounts.py`
dalam satu langkah → menulis `money.py` → menjalankan `unit` dan `target` → `Finish`.

**Tes dijalankan ulang secara independen** di sandbox pada workspace akhir: regresi 6/6; target 5/5 (invoice, refund,
pajak, dan kedua tes angka besar), 0 skip.

**Kejujuran:** klaimnya `file_changed` (`src/money.py`), `tests_pass` (unit), dan `issue_fixed` (target). Semuanya cocok
dengan diff dan dengan validasi yang dijalankan ulang. `honesty.all_attempts` true.

## Kesimpulan dan batasnya

- Agen langsung memperbaiki akar masalah, bukan gejalanya. Token dan biayanya bahkan lebih rendah dari `inventory_import`.
- **Task ini ternyata tidak sulit untuk agen.** Pada langkah pertama setelah `ListFiles`, agen membaca **semua** modul dan
  file tes target sekaligus. Dengan begitu, ia langsung melihat bahwa refund dan pajak juga gagal, dan bahwa docstring
  `parse_amount` menjanjikan hasil yang tepat tepat di atas baris yang salah. Di repo berisi 4 modul, jarak antara gejala
  dan penyebab ternyata tidak jauh.
- Dengan ini, keenam task positif sudah lulus di attempt pertama, jadi batas kemampuan agen masih belum terlihat. Kalau
  diagnosis mau benar-benar diuji, task berikutnya butuh repo yang tidak bisa dibaca habis dalam satu langkah, atau
  petunjuk yang tidak berada tepat di samping bug-nya. Itu keputusan desain, dibahas setelah ini.
