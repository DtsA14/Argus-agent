# Task repo besar dengan `search_files`: desain (untuk review sebelum fixture)

Status: desain disetujui (PR #51); fixture dan pengukuran model palsu selesai (bagian 5), 2026-10-16.
Arah dari review PR #50: satu task repo besar,
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

## 5. Hasil (model palsu, sandbox asli, biaya nol)

Fixture `fixtures/repos/shop/` (39 modul, sekitar 90 KB), kontrak `shop_coupon_leak` dengan `"tools": ["search_files"]`.
Semua run di VM (aarch64) dengan sandbox Docker sungguhan. Biaya di bawah adalah **estimasi** dari penghitung token
terkalibrasi (MEASURE_CONTEXT_B, galat ≤ 10%) dan harga Sonnet, bukan tagihan.

### Benchmark-nya sendiri

| Varian kode | Tes target (5) |
|---|---|
| bug asli | 5 gagal |
| referensi: `active_rules` mengembalikan salinan | semua lulus |
| tambalan dangkal: salin hanya di `checkout/cart.py` | 2 gagal (quote setelah checkout berkupon, dan sebaliknya) |
| salin di kedua pemanggil | semua lulus |

Baris terakhir adalah **perbaikan alternatif yang sah**: ia memenuhi tes, walaupun tidak memperbaiki kontrak
`active_rules` di sumbernya. Benchmark menerimanya, dan itu disengaja: yang dinilai adalah perilaku, bukan lokasi patch.

- Mode `reference`: PASS, `DONE`, jujur, 7 panggilan, $0.0056.
- Mode `wrong` (tambalan dangkal + klaim `issue_fixed`): `FAILED_ACCEPTANCE`, tertangkap hanya pada `issue_fixed`,
  benchmark OK.
- **Mutan validasi** (`judge_result` selalu `pass`): tambalan dangkal lolos `DONE`, dan eval melaporkan
  **benchmark `BROKEN`**. Mutan dikembalikan sesudahnya.

### Empat kondisi (`scripts/measure_context.py shop`, loop agen dan `run_code_task` penuh)

| Kondisi | Hasil | Attempt | Token per attempt | File dibaca | Pencarian | Estimasi biaya |
|---|---|---|---|---|---|---|
| tanpa pencarian, naif (urutan listing, 5 file per langkah) | `FAILED_ACCEPTANCE` (stagnan) | 2, keduanya `reservation_exhausted` | 27.829 / 28.136 | 24 | 0 | $0.119 |
| tanpa pencarian, terinformasi (hanya `checkout/`, `discounts/`, `quotes/`, `pricing/`) | `FAILED_ACCEPTANCE` (stagnan) | 2, keduanya `reservation_exhausted` | 26.868 / 27.177 | 26 | 0 | $0.116 |
| pencarian efektif | **`DONE`** | 1 | **28.436** | 2 | 3 | $0.061 |
| pencarian tidak efektif (mulai dari `"discount"`, membaca `pricing/rounding.py`) | `FAILED_ACCEPTANCE` (stagnan) | 2, keduanya `reservation_exhausted` | 27.170 / 27.662 | 6 | 6 | $0.117 |

Syarat review terpenuhi: baseline terinformasi hanya membaca empat direktori yang relevan (13 file per attempt), dan
tetap habis karena biaya konteks, bukan karena membaca file tak terkait tanpa batas.

### Yang ditunjukkan data (fakta, lalu hipotesis)

**Fakta:**
1. Di repo ini, tanpa pencarian, task tidak selesai dalam budget, bahkan kalau model tahu direktori mana yang relevan.
   Dengan pencarian dan jalur yang hampir optimal, task selesai di attempt pertama dengan biaya sekitar setengahnya.
2. **Marginnya sangat tipis.** Jalur efektif memakai 9 panggilan dan 28.436 dari 30.000 token, menyisakan 1.564 token.
   Itu kurang dari satu langkah tambahan (input per panggilan sudah 3–4 ribu token di akhir).
3. Satu belokan saja sudah cukup untuk gagal: kondisi tidak efektif hanya menambah satu pencarian umum dan satu file
   salah (sekitar 2,6 KB). Panggilan ke-9 (`RunValidation` setelah menulis) ditolak sebelum mengirim, karena butuh
   input sekitar 4.540 token sementara sisa reservasi 2.830.
4. Pengikatnya adalah **jumlah langkah**, bukan isi file. Biaya tetap per panggilan (system prompt, issue, skema tool)
   sekitar 1.770 token, dan dikirim ulang di setiap panggilan: 9 × 1.770 ≈ 16 ribu, lebih dari separuh input jalur
   efektif.

**Asumsi:** model palsu memanggil satu tool per langkah. Model sungguhan bisa memanggil beberapa tool dalam satu
langkah (di live #4–#6 agen membaca beberapa file sekaligus), sehingga jumlah langkahnya bisa lebih sedikit.

**Hipotesis untuk live (belum diuji):** dengan `attempt_tokens` 30.000, task ini hanya lulus kalau agen menemukan jalur
yang hampir optimal di attempt pertama, atau memanggil beberapa tool per langkah. Hasil live `FAILED_ACCEPTANCE`
karena `reservation_exhausted` adalah hasil eksperimen yang sah, bukan anomali harness.

### Keputusan yang terbuka (tidak diubah di PR ini)

- Apakah budget per attempt dibiarkan 30.000 untuk preflight live (mengukur agen apa adanya), atau task ini diberi
  margin lebih. Usulku dibiarkan dulu: yang ingin kita ukur adalah apakah agen menempuh jalur itu dalam budget yang
  sama dengan task lain. Mengubah budget atau prompt adalah keputusan terpisah setelah ada data live.
- Preflight live tetap menunggu persetujuan eksplisit.
