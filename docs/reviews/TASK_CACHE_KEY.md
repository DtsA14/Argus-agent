# Task `cache_key`: desain (untuk review sebelum fixture)

Status: **draf**, 2026-10-16. Belum ada fixture, kontrak, atau run. Disepakati: eksperimen A (diagnosis dengan petunjuk
yang berjauhan, repo sedang). Ukuran repo dan jarak petunjuk **tidak** diubah sekaligus. `attempt_tokens` tetap 30.000.
Pengukuran B (kapasitas navigasi, dengan model palsu) dikerjakan setelah ini, terpisah.

**Tujuan:** mengukur diagnosis ketika baris yang salah **terlihat wajar** walaupun dibaca. Bug ini muncul dari interaksi
(state bersama, yaitu cache), bukan dari satu baris yang mencurigakan. Petunjuk tentang perilaku yang benar ada di modul
lain, tidak di samping bug-nya.

Pelajaran dari live #5: repo dengan 4 modul dibaca habis dalam satu langkah, jadi "jarak" antar file tidak berarti.
Repo 6–8 modul juga masih muat dibaca sekaligus. Yang membuat task ini lebih sulit adalah **sifat bug-nya**, bukan
ukurannya.

## Repo `fixtures/repos/reports/` (7 modul)

| Modul | Isi |
|---|---|
| `src/db.py` | data pesanan di memori (pelanggan, periode, mata uang, sen), `total(customer, period, currency)`, dan penghitung query `db.queries` |
| `src/cache.py` | cache umum: `get_or_compute(key, fn)`, dengan statistik hit dan miss |
| `src/keys.py` | `report_key(customer, period, currency)`. **Bug:** mengembalikan `(customer, period)`. Baris ini terlihat wajar: tidak ada komentar, tidak ada TODO, docstring-nya pendek ("Cache key for a customer's report in a period.") |
| `src/reports.py` | `revenue(customer, period, currency)` lewat cache dengan `report_key`. **Kontrak ada di sini, bukan di `keys.py`:** "Reports are per customer, period and currency; amounts in different currencies are never mixed." |
| `src/invoices.py` | pemanggil **kedua** cache yang sama: `invoiced(customer, period, currency)` dengan key `("invoice",) + report_key(…)` |
| `src/fmt.py` | format jumlah per mata uang. Ini jalur yang sekilas masuk akal untuk disalahkan |
| `src/api.py` | `get_report(customer, period, currency)` menggabungkan `revenue`, `invoiced`, dan `fmt`. Gejalanya terlihat di sini |

**Issue yang dilihat agen** (hanya gejala): "Customers with orders in two currencies sometimes get incorrect totals from
get_report: the USD report can show the EUR amounts. Fix it. Do not change the tests." Issue tidak menyebut cache atau
key.

**Jalur yang sekilas masuk akal:** format mata uang (`fmt.py`), filter query (`db.py`), atau urutan di `api.py`. Semuanya
benar. Bug-nya hanya terlihat kalau agen menyadari bahwa cache dipakai bersama dan key-nya tidak memuat mata uang.

## Tes (semua di `tests/`, dilindungi)

**Regresi** (validasi `unit`; semuanya **sudah lulus** sekarang):
- laporan dan invoice untuk pelanggan dengan satu mata uang benar;
- **cache tetap bekerja:** permintaan yang sama dua kali hanya menghasilkan satu query ke `db` (`db.queries`);
- format per mata uang benar.

**Target** (validasi `target`, semua `must_pass`; **gagal** sekarang):
- `get_report` EUR lalu USD untuk pelanggan dan periode yang sama → angka USD yang benar;
- `invoiced` EUR lalu USD → angka USD yang benar (pemanggil kedua cache);
- setelah EUR dan USD masing-masing diminta sekali, mengulang keduanya tidak menambah query `db`. Ini memastikan cache
  tetap dipakai per mata uang dan tidak dimatikan.

Nilai harapan ditulis sebagai literal integer sen, bukan dihitung dengan kode yang sedang diuji.

## Naskah model palsu

- **Referensi:** memperbaiki `report_key` supaya memuat mata uang; menjalankan `target`; klaim `file_changed`
  (`src/keys.py`), `tests_pass`, dan `issue_fixed`. Harus `DONE` dan lulus eval.
- **Keliru (tambalan lokal):** mem-bypass cache di `reports.py` (menghitung `revenue` langsung). Tes `get_report`
  untuk revenue mungkin lulus, tapi `invoiced` tetap salah karena pemanggil kedua masih memakai key yang salah, dan
  regresi "cache tetap bekerja" gagal. Klaim `issue_fixed` dan `tests_pass` palsu.
- Mutasi validasi yang meloloskan tambalan lokal harus membuat benchmark `BROKEN`.

Sebelum naskah ditulis, setiap varian (bug asli, referensi, tambalan lokal, dan "matikan cache sama sekali") diukur dulu
terhadap kedua file tes, seperti di `inventory_import` dan `money_precision`.

## Batas yang dinyatakan

- Issue menyebut dua mata uang. Itu petunjuk ke "sesuatu yang membedakan mata uang", tapi bukan ke cache. Tanpa
  petunjuk itu, task-nya menjadi tebakan.
- Agen tetap bisa membaca ketujuh modul sekaligus. Yang diuji adalah apakah ia bisa menghubungkan kontrak di
  `reports.py`, pemakaian cache bersama, dan key yang kurang lengkap di `keys.py`, bukan apakah ia menemukan filenya.
