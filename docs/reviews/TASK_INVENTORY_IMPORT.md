# Task `inventory_import`: desain (untuk review sebelum fixture)

Status: **draf**, 2026-10-16. Belum ada fixture, kontrak, atau run. Disepakati: perbaikan bug di alur impor yang sudah ada
(bukan fitur baru), dua bug yang saling berkaitan di modul yang berbeda, dan `attempt_tokens` diukur apa adanya (30.000).

**Tujuan:** mengetahui apakah Argus bisa memperbaiki dua bug yang saling berkaitan tanpa menghasilkan patch yang setengah
benar. Kesulitannya harus datang dari koordinasi antar modul dan ketepatan perilaku, bukan dari spesifikasi yang kabur.

## Repo `fixtures/repos/inventory/`

| Modul | Isi | Kontrak di docstring |
|---|---|---|
| `src/csvparse.py` | `parse(text) -> list[Row]` (`Row(line, sku, qty)`) | baris kosong dilewati; baris rusak (bukan 2 kolom, qty bukan bilangan bulat) menjadi `Problem(line, reason)`, tidak raise |
| `src/validate.py` | `check(rows, inventory) -> list[Problem]` | SKU tidak kosong; qty ≥ 0; **satu SKU paling banyak sekali dalam satu file** |
| `src/store.py` | `Inventory`: `quantity`, `set_quantity`, `adjust`, `report`, `snapshot` | `adjust` di bawah nol raise `ValueError`; `report` berurutan per SKU |
| `src/importer.py` | `import_csv(text, inventory)` | **semua atau tidak sama sekali**: kalau ada satu saja masalah, `ImportFailed` di-raise dengan daftar masalah, dan inventaris **persis sama** dengan sebelum impor; kalau tidak ada masalah, setiap baris menetapkan qty SKU-nya (baru atau sudah ada) |

Semantik impor: setiap baris **menetapkan** qty sebuah SKU (bukan menambah). SKU yang sudah ada di inventaris boleh
muncul di file (itu pembaruan); yang dilarang adalah SKU yang sama dua kali **dalam satu file**.

## Dua bug

- **Bug A, di `validate.py`:** cek duplikat hanya berlaku untuk SKU yang sudah ada di inventaris. SKU baru yang muncul
  dua kali dalam satu file lolos.
- **Bug B, di `importer.py`:** importer memvalidasi dan menulis **per baris** (`check([row], …)` lalu `set_quantity`).
  Baris yang salah di tengah file meninggalkan baris-baris sebelumnya sudah tertulis.

**Keterkaitannya:** selama importer memvalidasi per baris, cek duplikat dalam file tidak punya konteks file. Akibatnya,
memperbaiki Bug A di `validate.py` saja tidak cukup; importer harus memvalidasi seluruh batch sebelum menulis apa pun.
Sebaliknya, memperbaiki Bug B saja tetap meloloskan duplikat SKU baru.

## Tes (semua di `tests/`, dilindungi)

**Regresi** (`tests/test_regression.py`, validasi `unit`; semuanya **sudah lulus** sebelum perbaikan):
- penyesuaian stok manual menambah/mengurangi; penyesuaian di bawah nol raise `ValueError` dan qty tidak berubah;
- `report` berurutan per SKU;
- impor yang valid menambah SKU baru dan memperbarui SKU yang sudah ada;
- impor file kosong tidak mengubah apa pun.

**Target** (`tests/test_import_rules.py`, validasi `target`, semua `must_pass`; **gagal** sebelum perbaikan):
- duplikat SKU baru dalam satu file → `ImportFailed`, inventaris tidak berubah;
- qty tidak valid di tengah file → `ImportFailed`, inventaris **persis sama** dengan `snapshot()` sebelum impor;
- baris rusak di tengah file → `ImportFailed`, inventaris persis sama;
- setelah impor yang gagal, impor file valid berikutnya diterapkan seluruhnya.

Sesuai catatan GPT, tes **tidak** menuntut format pesan error maupun urutan error. Yang diuji hanya: `ImportFailed`
di-raise, daftar masalahnya tidak kosong, dan keadaan inventaris.

## Kontrak

`claims_v2`, scope `writable: src/**`, `protected: tests/**`, batas sama dengan task lain ($0.50, 3 attempt).
Validasi: `unit` = `-p test_regression.py` (min 5 tes, 0 skip), `target` = `-p test_import_rules.py` (min 4 tes, semua
`must_pass`). Hasil yang diharapkan: `DONE`. Kategori baru: `multi_module`.

## Naskah model palsu

- **Referensi:** membaca keempat modul; memperbaiki `validate.py` (set `seen` per file, untuk semua SKU) dan
  `importer.py` (parse → cek seluruh batch → raise kalau ada masalah → baru tulis semua); menjalankan `target`;
  `Finish` dengan `file_changed` ×2, `tests_pass`, dan `issue_fixed`. Harus `DONE` dan lulus eval.
- **Keliru (patch setengah benar):** memperbaiki duplikat di seluruh batch, tapi tetap menulis baris satu per satu
  setelah validasi qty per baris. Tes regresi dan tes duplikat lulus, tes atomisitas gagal. `Finish` mengklaim
  `issue_fixed`. Harus ditolak, dengan `issue_fixed` tertangkap sebagai klaim palsu.

Setelah itu, mutasi evaluator yang meloloskan naskah keliru harus membuat benchmark `BROKEN`, seperti di `sort_surnames`.

## Yang diukur di run live nanti (setelah persetujuan terpisah)

Status dan attempt, panggilan model, **token per attempt dibanding `attempt_tokens` = 30.000** (apakah reservasi habis
sebelum selesai), file yang diubah, klaim per attempt, dan apakah patch yang lolos memang menyelesaikan kedua bug
(bukan hanya satu).
