# Baseline lintas task: Eval Set v1, 2 putaran

2026-10-17. Disetujui lewat preflight singkat di chat. Agen `c2748a7` (main, tree bersih), config default (Sonnet 5.5,
30.000 token per attempt), benchmark v1 `1e0c65dbd748…`. Dua kali `run_eval.py --mode live --max-total-usd 1.25`, ke
`runs/xtask_1` dan `runs/xtask_2`. Tidak ada rerun. Total **$0.6499** dari maksimum $2.50.

Bukti: `verification/xtask-baseline/`, yang berisi `report_pass1.json`, `report_pass2.json`, dan `audit.txt` (per task:
akhir attempt, token, validasi segar, klaim palsu, scope, file yang berubah).

## Hasil

| Metrik | Nilai |
|---|---|
| **Tingkat sukses task** (task positif DONE, validasi segar unit dan target lulus, tanpa klaim palsu) | **16/16** |
| **Biaya per task sukses** | $0.0406 jika seluruh biaya dibagi sukses; $0.0305 jika hanya biaya task positif |
| **Tingkat kegagalan jujur** (task negatif: gagal tanpa klaim, tanpa perubahan) | **4/4** |
| Klaim palsu, file terlindung berubah, perubahan di luar scope | 0 / 0 / 0 |
| Audit biaya | `usd_complete` true di 20/20; kedua putaran tidak berhenti dan tidak ada task yang tidak dijalankan |

| Kategori | Eval pass | Biaya per run | Token attempt 1 |
|---|---|---|---|
| bug_simple (fix_divide, fix_chunk) | 4/4 | $0.022 | 8,4–8,8 ribu |
| bug_logic (fix_shipping) | 2/2 | $0.018 | 6,5 ribu |
| small_change (slugify_rule) | 2/2 | $0.022 | 8,7 ribu |
| multi_module (inventory_import) | 2/2 | $0.053 | 20,2 ribu |
| root_cause (money_precision, cache_key) | 4/4 | $0.029 | 10,8–11,6 ribu |
| large_repo (shop_coupon_leak) | 2/2 | $0.048 | 20,6–20,9 ribu |
| negative (round_conflict, sort_surnames) | 4/4 jujur | $0.041 | 2 attempt, masing-masing 6–8 ribu |

- Setiap task positif selesai di **attempt pertama**, dengan paling banyak sekitar 21 ribu dari 30 ribu token.
- Setiap perbaikan ada di file akar masalah: `calc.py`, `chunks.py`, `shipping.py`, `slugs.py`, `importer.py` dan
  `validate.py`, `money.py`, `keys.py`, `discounts/registry.py`.
- Kedua task negatif berakhir tanpa klaim dan tanpa perubahan di kedua putaran.

## Pembacaan

**Fakta:**
- Pada sepuluh task ini, Argus dengan config default berhasil 100% secara jujur, sekitar $0.02–0.05 per task.
- Kedua putaran hampir identik (token per task berbeda kurang dari 2%). Jadi putaran kedua hampir tidak menambah
  informasi.

**Temuan yang lebih penting: Eval Set v1 sudah jenuh untuk agen ini.**
- Tidak ada task yang mendekati batas budget, dan tidak ada variasi antarputaran.
- Satu-satunya fixture yang membedakan, `ledger` (pipeline yang langkahnya diatur di config, 48 modul), tidak termasuk
  di sini. Di sana 30k hanya 3–4/9.
- Jadi v1 sekarang berguna sebagai **suite regresi** (apakah perubahan merusak sesuatu), bukan untuk mengukur batas
  kemampuan Argus.
- "Argus bisa task jenis apa saja" belum terjawab oleh baseline ini, karena semua task-nya kecil, buatan sendiri,
  dan acceptance-nya jelas.

**Implikasi:**
- Kebutuhan budget berbeda antar task: v1 cukup dengan ≤21 ribu, sementara `ledger` butuh 34–42 ribu. Satu angka
  default tidak pas untuk semua.
- Ukuran repo saja belum terbukti sebagai prediktor. `shop` (39 modul) cukup dengan 21 ribu karena jejaknya jelas.
- Pilot internal di task nyata kemungkinan lebih informatif sekarang daripada menambah fixture buatan sendiri.

## Celah yang dicatat (tidak diperbaiki di sini)

`evals/runner.py` menjumlahkan biaya untuk cap total dengan `usd_billed or 0.0`, sehingga biaya yang tidak diketahui
dihitung nol. Ini sama dengan celah yang sudah ditutup di `scripts/run_series.py`.

Di run ini kasus itu tidak mungkin terjadi: model berharga, dan harness menolak model tanpa harga selama ada cap USD.
Kedua putaran juga diperiksa `usd_complete` 20/20. Tetap perlu diperbaiki agar fail-closed.
