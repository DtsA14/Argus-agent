# Task repo besar dengan `search_files`: desain (untuk review sebelum fixture)

Status: **draf**, 2026-10-16. Belum ada fixture, kontrak, atau run. Arah dari review PR #50: satu task repo besar,
`search_files` aktif **hanya untuk task itu**, dan tiga kondisi pembanding diukur dengan model palsu sebelum ada
preflight live.

## 1. Satu keputusan dulu: bagaimana `search_files` aktif untuk satu task saja

Allowlist agen sekarang berasal dari config global (`tools.coder`), jadi tidak bisa dibedakan per task. Pilihannya:

| | Cara | Kelebihan | Kekurangan |
|---|---|---|---|
| **A (usulku)** | field opsional di kontrak, misalnya `"tools": ["search_files"]`, yang **menambah** allowlist config hanya untuk run itu. Harness memvalidasinya: hanya tool yang terdaftar di `GATED`, tanpa duplikat. Tool tidak bisa dicabut lewat kontrak, karena agen tidak menulis kontrak. | ikut dibekukan bersama kontrak dan tercatat di hash benchmark; task lama tidak berubah sama sekali; mudah diaudit | perubahan kecil di skema kontrak dan validasinya (perlu tes dan mutasi) |
| B | runner eval menimpa config untuk task tertentu | tidak menyentuh kontrak | tersembunyi di luar artefak beku, dan run lewat CLI biasa tidak sama dengan run lewat eval |

Usulku **A**, karena alat yang boleh dipakai agen adalah bagian dari kontrak task, dan kontrak sudah menjadi tempat
yang dibekukan dan diaudit.

## 2. Repo `fixtures/repos/shop/` (sekitar 40 modul, masing-masing 2–3 KB)

Toko kecil dengan banyak modul yang masuk akal: `catalog/`, `pricing/`, `discounts/`, `tax/`, `shipping/`,
`checkout/`, `quotes/`, `inventory/`, `notifications/`, `reports/`, dan sebagainya. Sebagian besar modul tidak terkait
dengan bug. Ukurannya sengaja di atas kapasitas "baca semua" yang terukur (PR #48: sekitar 10 file 3 KB), supaya
kondisi tanpa pencarian benar-benar kehabisan budget.

**Bug (akar masalah, tanpa jejak sintaksis):** `discounts/registry.py` punya `active_rules(customer)` yang
mengembalikan list modul `RULES` itu sendiri. `checkout/cart.py` lalu menambahkan aturan kupon ke list yang
dikembalikan, sehingga **registry global ikut termutasi**. Pelanggan berikutnya di proses yang sama mendapat diskon
kupon yang bukan haknya.
- Baris `return RULES` terlihat wajar: tidak ada parameter yang tidak dipakai, tidak ada default yang mutable, dan
  tidak ada TODO.
- Kontraknya ada di docstring `discounts/registry.py` ("callers get their own list and may extend it").
- Ada pemanggil kedua, `quotes/estimate.py`, yang juga menambahkan aturan ke list yang dikembalikan.

**Issue (hanya gejala):** "A customer sometimes gets a coupon discount at checkout without entering a coupon, usually
right after another customer used one. Fix it. Do not change the tests."

**Tes:**
- regresi (dilindungi, lulus sekarang): kupon untuk pelanggan yang memakainya, harga tanpa kupon, quote biasa, dan
  modul lain;
- target (dilindungi, gagal sekarang): dua checkout berurutan (dengan lalu tanpa kupon) memberi harga yang benar; quote
  setelah checkout berkupon juga benar; urutan dibalik juga diuji.
- Nilai harapan ditulis sebagai literal sen.

**Perbaikan referensi:** `active_rules` mengembalikan salinan (`list(RULES)`), sesuai kontraknya. Kedua pemanggil
langsung aman.

**Naskah keliru (tambalan dangkal):** menyalin list hanya di `checkout/cart.py`. Checkout jadi benar, tapi quote
setelah checkout berkupon tetap salah, karena `quotes/estimate.py` masih memutasi registry. Hanya `issue_fixed` yang
palsu. Mutan validasi yang meloloskannya harus membuat benchmark `BROKEN`, seperti task sebelumnya.

## 3. Tiga kondisi pembanding (model palsu, jalur harness asli)

Pola pencariannya eksplisit dan realistis: model palsu **tidak** langsung tahu nama `active_rules`.

| Kondisi | Pola |
|---|---|
| **Tanpa pencarian** (baseline) | `search_files` tidak diizinkan; `ListFiles`, lalu membaca file sebanyak mungkin. Diperkirakan habis budget |
| **Pencarian efektif** | `SearchFiles("coupon")` (banyak hasil, terpotong) → `SearchFiles("coupon", path="checkout")` → baca `checkout/cart.py` → lihat `active_rules(` → `SearchFiles("def active_rules")` → baca `discounts/registry.py` → perbaiki |
| **Pencarian tidak efektif** | dimulai dari `SearchFiles("discount")` (terlalu umum), membaca satu modul yang salah (`pricing/` atau `tax/`), lalu `SearchFiles("coupon", path="checkout")`, dan seterusnya seperti pencarian efektif |

Yang diukur per kondisi: total token, biaya estimasi, file yang dibaca, jumlah pencarian, status akhir, dan
acceptance. Kondisi pencarian memakai perbaikan referensi, sehingga acceptance-nya diharapkan `DONE`. Kondisi baseline
diharapkan berakhir `reservation_exhausted`, lalu `FAILED_ACCEPTANCE`.

Selain itu, mode `reference` dan `wrong` di eval berjalan seperti biasa dengan validasi sandbox sungguhan, ditambah
mutasi.

## 4. Batas yang dinyatakan

- Model palsu tetap mengikuti naskah. Pola "tidak efektif" adalah satu contoh yang realistis, bukan perilaku model
  sungguhan.
- Simbol `active_rules` tetap bisa ditemukan agen sungguhan lewat baris `active_rules(` di `checkout/cart.py`. Itu
  memang jalur diagnosis yang wajar, dan yang diuji adalah apakah ia menempuh jalur itu dalam budget.
