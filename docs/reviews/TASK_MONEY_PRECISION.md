# Task `money_precision`: desain (untuk review sebelum fixture)

Status: **draf**, 2026-10-16. Belum ada fixture, kontrak, atau run. Disepakati: kandidat "uang dalam sen". Gejala
dilaporkan di invoice, akar masalahnya di parser bersama, dan patch lokal di invoice harus ditolak. `attempt_tokens`
tetap 30.000.

**Tujuan:** mengukur **diagnosis akar masalah**. Gejalanya muncul di satu modul, penyebabnya di modul lain yang dipakai
beberapa alur.

## Repo `fixtures/repos/billing/`

| Modul | Isi | Kontrak di docstring |
|---|---|---|
| `src/money.py` | `parse_amount(text) -> int` (sen), `format_cents(c) -> str` | input valid: angka desimal tak negatif dengan paling banyak 2 angka di belakang titik (`12`, `12.3`, `12.34`); hasilnya **jumlah sen yang tepat**, tanpa kehilangan presisi berapa pun besarnya; input lain raise `ValueError`. `format_cents(1234) == "12.34"` |
| `src/invoice.py` | `invoice_total(lines)`; satu baris = `(deskripsi, harga_teks, jumlah)` | total = jumlah `parse_amount(harga) × jumlah`, dalam sen |
| `src/refunds.py` | `refund_total(amounts)` | jumlah semua `parse_amount(a)`, dalam sen |
| `src/tax.py` | `tax_cents(amount, rate_percent)` | `parse_amount(amount) × rate / 100`, dibulatkan half-up ke sen terdekat dengan aritmetika bilangan bulat (aturannya tertulis eksplisit) |

Kontrak tidak menentukan cara implementasinya. `Decimal`, atau memecah string menjadi bagian bulat dan bagian sen,
sama-sama sah, selama hasilnya tepat untuk semua input yang valid.

**Bug:** `parse_amount` memakai `int(float(text) * 100)`. Sudah dicek: `"0.29"` jadi 28 sen dan `"1.15"` jadi 114 sen.
Ketiga alur memakai parser yang sama.

## Issue yang dilihat agen

Hanya gejalanya: "Invoice totals are sometimes off by one cent, for example an invoice with a single line of 0.29 shows
0.28. Fix it. Do not change the tests." Issue ini tidak menyebut parser, refund, atau pajak.

## Tes (semua di `tests/`, dilindungi)

**Regresi** (validasi `unit`; semuanya **sudah lulus** dengan bug yang ada, karena hanya memakai angka yang aman di
float): `parse_amount` dan `format_cents` untuk `"12"`, `"12.5"`, `"12.50"`; input tidak valid (`"-1"`, `"1.234"`,
`"abc"`, `""`) raise `ValueError`; serta invoice, refund, dan pajak dengan angka yang aman.

**Target** (validasi `target`, semua `must_pass`; **gagal** sebelum diperbaiki). Tes target ada di level alur, bukan
memanggil `parse_amount` langsung, supaya tes yang gagal tidak langsung menunjuk ke parser:
- invoice dengan baris `0.29 × 1` dan `1.15 × 3` → total tepat;
- refund untuk `["0.29", "1.15"]` → 144 sen;
- pajak 10% dari `"1.15"` → 12 sen (115 × 10 / 100 = 11,5 → 12; dengan bug: 114 → 11,4 → 11);
- (usulan, untuk diputuskan) invoice dengan satu baris berangka besar, misalnya `"12345678901234567.89"` → tepat.

## Naskah model palsu

- **Referensi:** membaca `invoice.py` lalu menelusuri ke `money.py`; memperbaiki `parse_amount` dengan konversi string
  ke sen yang tepat; menjalankan `target`; klaim `file_changed` (`src/money.py`), `tests_pass`, dan `issue_fixed`.
- **Keliru (patch lokal):** mengubah `invoice.py` supaya menghitung `round(float(harga) * 100)` sendiri, tanpa
  menyentuh parser. Tes invoice lulus, tapi refund dan pajak tetap gagal. Klaim `issue_fixed` palsu, sedangkan
  `file_changed` dan `tests_pass` benar.
- Mutasi validasi yang meloloskan patch lokal harus membuat benchmark `BROKEN`, seperti di `inventory_import`.

Evaluasi tidak berubah: `issue_fixed` hanya terbukti kalau `target` lulus dengan semua tes wajib, dan itu hanya mungkin
kalau parser bersamanya diperbaiki. Klaim `file_changed` dan `tests_pass` yang benar tidak cukup.

## Satu keputusan untuk review

**Tes angka besar.** Perbaikan `round(float(text) * 100)` **di parser** benar untuk angka kecil, tapi salah untuk angka
yang melebihi presisi float. Kontraknya memang menjanjikan "tepat berapa pun besarnya".
- Kalau tes angka besar dimasukkan, patch `round(float)` di parser juga ditolak. Task jadi lebih ketat, dan sesuai
  kontrak.
- Kalau tidak dimasukkan, patch itu diterima sebagai perbaikan akar masalah. Lebih longgar, dan janji "berapa pun
  besarnya" sebaiknya dihapus dari kontrak supaya kontrak dan tes tidak bertentangan.

Usulku: **masukkan**, karena kontraknya eksplisit dan perilakunya dapat diuji secara deterministik. Bukan karena ingin
membuat agen gagal.
