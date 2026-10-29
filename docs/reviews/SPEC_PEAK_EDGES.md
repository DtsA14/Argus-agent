# Spek: harga peak di batas jendela, dan peringatan peak di router

Status: **draf untuk keputusan Atha**, 2026-10-29. Jalur ketat: P1 dan P2 menyentuh worst case sebelum kirim dan biaya di
ledger (`harness/llm.py`). P3 hanya tampilan di layar konfirmasi router.

## 1. Keadaan sekarang

`config.yaml`: DeepSeek ×2 (cache hit juga) pada hari kerja **01–04 dan 06–10 UTC** (08–11 dan 13–17 WIB). Libur nasional
Tiongkok tidak dimodelkan, jadi di hari itu kita memperkirakan lebih mahal, arah yang aman. Pengali dipakai di tiga tempat:
worst case sebelum kirim (`_worst_usd`, `_output_cap`), biaya aktual di ledger (`cost_usd`), dan estimasi budget node
(`harness/budget.py`, selalu ×peak).

Yang jadi masalah: `LLMCaller` membaca `self._now()` dua kali. Worst case dihitung dengan pengali **saat dikirim**, biaya
aktual dengan pengali **saat selesai**.

## 2. Data (2026-10-29, semua ledger di VM)

- 2.315 panggilan DeepSeek `ok`. **839 (36%) selesai di jam peak.** Di job router, $1,81 dari $3,45 (53%) dibayar dengan
  harga peak; kalau semuanya off-peak, kita hemat ±$0,91.
- **0 panggilan** yang mulai dan selesai di sisi jendela yang berbeda.
- Latensi panggilan: p50 2 s, p99 68 s, **maks 606 s** (`j20261028_065812_5cb1-a2`). `timeout_s` coder 120, jadi
  `timeout_s` **bukan** batas lama satu panggilan dan tidak bisa dipakai sebagai jangkauan ke depan.
- Belum terverifikasi: apakah DeepSeek menagih menurut waktu mulai atau waktu selesai request. Halaman dokumen yang dicek
  2026-10-29 tidak menyebutnya. Spek ini dibuat supaya benar untuk **kedua** aturan.

## 3. Celah

1. **Worst case terlalu rendah (jaminan uang).** Panggilan yang dikirim pukul 00:59:30 UTC dengan worst case ×1, lalu
   selesai pukul 01:00:10 (peak), tercatat ×2. Biayanya bisa sampai 2× worst case, dan bisa melewati reservasi. AGENTS.md:
   "a request must be refused before sending when it does not fit".
2. **Ledger bisa di bawah tagihan.** Panggilan yang mulai pukul 03:59:50 (peak) dan selesai 04:00:20 (off-peak) tercatat
   ×1. Kalau DeepSeek menagih menurut waktu mulai, tagihannya ×2: ledger lebih rendah dari uang yang sebenarnya keluar.

## 4. Perubahan

**P1. Worst case memakai pengali tertinggi di `[sekarang, sekarang + H]`.** `H` = `llm.peak_lookahead_s`, default **900 s**
(di atas latensi maksimum terukur, 606 s). `models/pricing.py` mendapat `max_multiplier(price, window, start, seconds)`:
pengali peak bila ada satu saat di rentang itu yang jatuh di jendela, lalu dipakai `_worst_usd` dan `_output_cap`.
Akibatnya, mendekati 01:00 dan 06:00 UTC, reservasi sudah memakai harga peak 15 menit lebih awal.
- Panggilan yang masih berjalan lebih lama dari `H` dan menyeberang ke peak tetap bisa lewat. Guard `budget_violation`
  tetap menjadi pengaman kedua, dan kasus itu tercatat. Ini dinyatakan sebagai batas klaim, bukan jaminan absolut.

**P2. Biaya aktual = pengali tertinggi antara waktu mulai dan waktu selesai.** `cost_usd` untuk satu panggilan dihitung
dengan `max(multiplier(start), multiplier(end))` (start = saat `llm_call_started`). Ledger jadi tidak pernah di bawah
tagihan untuk kedua aturan penagihan. Kalau DeepSeek ternyata menagih menurut waktu selesai, pilihan ini kadang
memperkirakan lebih mahal, arah yang aman. Field baru di `llm_call`: `peak` (bool, pengali yang dipakai > 1).

**P3. Peringatan peak di router.** Layar konfirmasi `argus code`, `approve`, `retry`, dan `redraft` (teks yang juga
dicatat sebagai `limits_shown`) mendapat satu baris bila sekarang, atau dalam `H` ke depan, jam peak model stage itu:
`peak: DeepSeek is at 2x now (until 04:00 UTC = 11:00 WIB); off-peak saves about half`. Hanya peringatan: tidak menolak
dan tidak menunda (`refuse_peak` kalibrasi tidak berubah). Waktu WIB ditulis supaya Atha tidak perlu menghitung.

## 5. Tes (masing-masing harus gagal kalau jaminannya dirusak; mutants)

1. `max_multiplier`: 00:59:30 dengan H 900 → 2; 00:44:00 → 1; Sabtu 00:59:30 → 1; 03:59:59 → 2; rentang yang melewati dua
   jendela (03:55 dengan H 9.000) → 2.
2. Worst case sebelum kirim pada 00:59:30 (off-peak) memakai ×2. Gagal kalau `_worst_usd` atau `_output_cap` memakai
   pengali saat ini.
3. Replay batas: panggilan mulai 00:59:30, selesai 01:00:10 (clock palsu). Biaya di ledger ≤ worst case sebelum kirim, dan
   reservasi tidak terlampaui.
4. P2: panggilan mulai 03:59:50 (peak), selesai 04:00:20. Biaya di ledger = harga ×2 dan `peak: true`. Gagal kalau biaya
   memakai waktu selesai saja.
5. Panggilan yang seluruhnya off-peak dan jauh dari jendela: biaya dan worst case tidak berubah dari sekarang (×1). Ini
   penjaga supaya perubahan tidak menaikkan harga di jam biasa.
6. P3: layar konfirmasi pada 02:00 UTC hari Kamis memuat baris `peak:` dengan `04:00 UTC = 11:00 WIB`; pada 12:00 UTC tidak;
   pada 00:50 UTC (peak dalam H) memuat baris yang menyebut mulai 01:00 UTC.

Verifikasi: mutants untuk tes 1–5, `/code-review medium` + `/security-review`, `verify.sh` penuh sekali di commit final,
lalu "merge" Atha.

## 6. Yang tidak diubah, dan batas klaim

- Jendela dan pengali di `config.yaml`, model Anthropic (tanpa jendela peak), `harness/budget.py` (sudah selalu ×peak).
- Libur nasional Tiongkok tetap tidak dimodelkan (perkiraan lebih mahal, aman).
- "Ditolak sebelum kirim" tetap bergantung pada lama panggilan ≤ H untuk harga. Yang absolut hanya bila worst case selalu
  memakai ×peak (lihat pertanyaan 1).

## 7. Pertanyaan untuk Atha

1. P1: jangkauan **H = 900 s** (usul; menyisakan sedikit celah untuk panggilan > 15 menit), atau worst case **selalu
   ×peak**? Selalu ×peak berarti absolut, tetapi reservasi USD off-peak tinggal separuh: `_output_cap` dan sisa attempt
   lebih cepat terbatas. Sejauh ini USD jarang mengikat ($0,036 dari $0,45 di `24562`).
2. P3: peringatan saja (usul), atau `argus code`/`approve` menolak di jam peak kecuali ada `--allow-peak` (seperti kalibrasi)?
3. Batch berikutnya dijadwalkan off-peak: di luar 08–11 dan 13–17 WIB pada hari kerja?
