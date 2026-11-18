# ATHENA: aturan angka (DOMAIN)

> DRAFT ditulis Claude dari kode `risk_management/risk_manager.py` (commit 705db5b, 2026-11-18). Belum ditinjau Atha. Setiap angka di bawah dicocokkan dengan hasil
> kode sungguhan. Dokumen ini ada supaya pembaca angka (Argus) punya aturan tertulis; kalau kode berubah, dokumen ini yang diperbarui bersama kodenya.

## Harga dan lantai harga
- Harga hanya boleh kelipatan tick (fraksi harga BEI, Kep-00023/BEI/04-2016): harga di bawah Rp200 tick Rp1; Rp200 sampai di bawah Rp500 tick Rp2; Rp500 sampai di bawah Rp2.000 tick Rp5; Rp2.000 sampai di bawah Rp5.000 tick Rp10; Rp5.000 ke atas tick Rp25.
- Harga entry dibulatkan ke tick terdekat.
- Lantai harga terendah di bursa ("gocap") adalah **Rp1** sejak 28 September 2026 (Kep-00136/BEI/09-2026); sebelumnya Rp50. Saham di harga lantai atau di bawahnya diblokir: ukuran posisi 0 lembar, `price_floor_blocked` ya.

## Stop loss dan take profit
- Jarak stop dasar = 1,5 x ATR. Pasar volatil tinggi: jarak dikali 1,3. Pasar volatil rendah: jarak dikali 0,85. Stop mentah = entry dikurang jarak itu.
- Stop dibulatkan ke BAWAH ke tick (supaya tidak lebih ketat dari hitungan), dan tidak boleh di bawah lantai harga (dijepit ke lantai).
- Take profit = entry ditambah 2 x jarak stop sebenarnya, dibulatkan ke ATAS ke tick.
- Contoh: entry 50, ATR 3, volatilitas normal: stop mentah 50 - 4,5 = 45,5, dibulatkan ke bawah ke tick Rp1 menjadi 45,0. Entry 1.000, ATR 20: stop mentah 970, tick Rp5, stop 970.

## Ukuran posisi
- Anggaran risiko = modal x 1,5%.
- Jarak stop untuk ukuran = nilai terbesar dari (jarak stop sebenarnya, jarak model ATR) dikali (1 + buffer ARB). Buffer ARB membuat posisi lebih kecil, bukan stop lebih jauh.
- Buffer ARB bawaan di kode: 15% (Kep-00003/BEI/04-2025). **Aturan BEI sekarang berbeda**: sejak 19 Oktober 2026 sampai 31 Desember 2026 batas ARB 7% untuk saham harga di atas Rp10 (Kep-00157/BEI/10-2026), dan saham harga Rp11 sampai Rp14 ARB-nya Rp1 (Kep-00158/BEI/10-2026). Nilai bawaan 15% di kode belum disesuaikan (status 2026-11-18).
- Lembar mentah = anggaran risiko dibagi jarak stop untuk ukuran. Dikali pengali keyakinan: HIGH 1,0; MEDIUM_HIGH 0,825; MEDIUM 0,675; MEDIUM_LOW 0,45; LOW 0,275. Lalu dibulatkan ke BAWAH ke kelipatan 100 lembar (1 lot = 100 lembar).
- Batas likuiditas: nilai posisi paling banyak 5% dari nilai transaksi harian rata-rata. Batas modal: nilai posisi paling banyak 10% dari modal. Yang lebih kecil berlaku.
- Contoh jarak: entry 1.000, ATR 20 (stop 970, jarak 30) dengan buffer 15%: jarak untuk ukuran 30 x 1,15 = 34,5; dengan buffer 7%: 30 x 1,07 = 32,1.

## Batas portofolio
- Rugi harian maksimum 3% dari modal (berhenti trading hari itu). Satu sektor paling banyak 30% dari portofolio.
