# Spek: harga peak di batas jendela, dan peringatan peak di router

Status: **disetujui Atha 2026-10-29** (§7). Jalur ketat: P1 dan P2 menyentuh worst case sebelum kirim dan biaya di
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

**P1. Worst case sebelum kirim selalu memakai ×peak** untuk provider yang punya jendela peak (`peak_multiplier` di
`_worst_usd` dan `_output_cap`), apa pun jamnya, sama seperti estimasi budget node (`harness/budget.py`). Tidak ada lagi
ketergantungan pada lama panggilan: biaya satu panggilan tidak pernah melebihi worst case-nya karena jam berganti.
Model tanpa jendela (Anthropic) tidak berubah.
- Biayanya: reservasi USD di jam off-peak terasa separuh. Dari data, tidak ada yang terhambat: seandainya worst case
  selalu ×2, **0 dari 1.182** panggilan agen dan **0 dari 837** panggilan drafter akan dibatasi USD lebih awal (ruang
  paling sempit di drafter masih 3,2× output yang terjadi). Batas token dan input tidak tersentuh.

**P2. Biaya aktual = pengali tertinggi antara waktu mulai dan waktu selesai.** Waktu mulai dibaca tepat sebelum
`llm_call_started`, waktu selesai sesudah balasan. Ledger jadi tidak pernah di bawah tagihan untuk kedua aturan
penagihan; kalau DeepSeek menagih menurut waktu selesai, kadang lebih mahal di catatan (arah yang aman). Field baru di
`llm_call` ok: `peak` (bool, pengali yang dipakai > 1). Karena pengali aktual ≤ ×peak, biaya ≤ worst case (P1).

**P3. Peringatan peak di router.** Layar konfirmasi `argus code`, `approve`, `retry`, `redraft`, dan `resume` (teks yang
juga dicatat sebagai `limits_shown`) mendapat satu baris bila model stage itu sedang di jam peak, atau jam peak mulai
dalam 30 menit:
`peak: deepseek is at 2x now (until 04:00 UTC = 11:00 WIB); off-peak costs about half` atau
`peak: deepseek goes to 2x at 01:00 UTC = 08:00 WIB; ...`. Hanya peringatan: tidak menolak dan tidak menunda
(`refuse_peak` kalibrasi tidak berubah).

## 5. Tes (masing-masing harus gagal kalau jaminannya dirusak; mutants)

1. Worst case dan `max_tokens` sebelum kirim sama di jam peak, off-peak hari kerja, dan Sabtu (semua ×peak). Gagal kalau
   `_worst_usd` atau `_output_cap` memakai pengali saat ini.
2. Batas jendela: mulai 00:59:30 (off-peak), selesai 01:00:10 (clock palsu): biaya di ledger ×2 dan ≤ worst case di
   `llm_call_started`; reservasi tidak terlampaui.
3. P2: mulai 03:59:50 (peak), selesai 04:00:20: biaya ×2 dan `peak: true`. Gagal kalau biaya memakai waktu selesai saja.
   Kebalikannya (mulai off-peak, selesai peak) juga ×2.
4. Seluruhnya off-peak: biaya ×1 dan `peak: false` (perubahan tidak menaikkan biaya yang tercatat).
5. Model tanpa jendela: worst case dan biaya tidak berubah.
6. P3: Kamis 02:00 UTC memuat `until 04:00 UTC = 11:00 WIB`; 00:45 UTC memuat `at 01:00 UTC = 08:00 WIB`; 00:20 dan
   12:00 UTC dan Sabtu 02:00 tidak memuat baris `peak:`; baris itu ada di `limits_shown`.

Verifikasi: mutants untuk tes 1–6, `/code-review medium` + `/security-review`, `verify.sh` penuh sekali di commit final,
lalu "merge" Atha.

## 6. Yang tidak diubah, dan batas klaim

- Jendela dan pengali di `config.yaml`, `harness/budget.py` (sudah selalu ×peak), estimasi `cache_totals` (hanya
  laporan).
- Libur nasional Tiongkok tetap tidak dimodelkan (perkiraan lebih mahal, aman).
- Untuk token, counter heuristik tetap bukan cap absolut (AGENTS.md); P1 hanya menutup celah jam.

## 7. Keputusan Atha (2026-10-29)

1. P1: worst case **selalu ×peak** (bukan jangkauan 900 s): sederhana dan absolut, tanpa hambatan terukur.
2. P3: **peringatan saja**, tanpa `--allow-peak`. "Jangan sampai ngirit tapi menghambat kerja Argus."
3. Jadwal batch: Claude menunda run ke off-peak bila tidak mendesak; bukan aturan keras.
