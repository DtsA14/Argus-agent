# Eval Set v1: eksperimen live #7 (`shop_coupon_leak`, repo besar dengan `search_files`)

## Preflight (ditulis sebelum run, 2026-10-16)

Disetujui: satu run, tanpa retry dan tanpa menaikkan budget. Konfigurasi: agen `00e1c77` (main, tree bersih), model
`anthropic:claude-sonnet-5-5`, benchmark `1e0c65dbd748…`, `claims_v2`, tool default + `search_files` lewat kontrak,
`attempt_tokens` 30.000, `max_steps` 12, `stagnation_rounds` 2, `max_iterations` 3, cap kontrak $0.50 dan
`--max-total-usd 0.50`. Mode `reference` di main: PASS, benchmark OK.

**Audit prompt.** `system_prompt_sha256` di `report.json` adalah hash prompt **default** (tool dari config saja):
`ee7af58d…`. Untuk task ini prompt yang dikirim berbeda, karena kontrak menambah `SearchFiles` ke daftar tool dan
deskripsinya. Hash prompt sistem **efektif** dihitung sebelum run dari allowlist efektif
(`list_files, read_file, write_file, run_validation, search_files`):

`9f9e718c7ae339f8666475159e8867e97c048e4c3c48ae8421435389f61882a6`

Setelah run, percakapan setiap panggilan dibangun ulang dari memo dengan prompt efektif ini, lalu `prompt_hash` yang
dihitung ulang harus sama dengan `prompt_hash` di ledger untuk **setiap** panggilan. Kalau ada yang tidak cocok, itu
dicatat sebagai anomali. Kode tidak diubah untuk ini sebelum run.

**Status budget.** Penolakan reservasi (`llm_call` berstatus `refused`, attempt berakhir `reservation_exhausted`) adalah
akhir sebuah **attempt**, bukan status terminal **task**. Status terminal dan alasannya dicatat persis dari
`result.json` dan event `status`, tanpa diasumsikan `FAILED_ACCEPTANCE`. Yang dicatat terpisah: akhir setiap attempt,
setiap penolakan (input yang dibutuhkan dan sisa reservasi), status terminal, dan `stop_reason`.

**Aturan baca hasil (ditetapkan sebelum run):** `BLOCKED`, `FAILED_BUDGET`, atau anomali harness → berhenti dan lapor,
tanpa run ulang. `DONE` → belum disimpulkan sukses sebelum lokasi perbaikan, klaim, diff, dan validasi independen
diperiksa. Kegagalan karena biaya konteks adalah hasil eksperimen yang sah. Benchmark dan batas budget tidak diubah
setelah melihat hasil.

## Hasil (dicek dari ledger, memo, workspace, dan validasi yang dijalankan ulang)

Run 2026-10-16 ~11:12 UTC di VM, sesuai preflight, satu kali. Bukti: `verification/eval-live-7/` (termasuk `audit.txt`,
keluaran skrip audit prompt dan langkah).

| | |
|---|---|
| Status terminal | **DONE**, `stop_reason` "all criteria passed", 1 attempt (`attempt_end` `finished`, 4 langkah) |
| Panggilan model | 5: `llm_call_started` 5, `llm_call` 5, semuanya `ok`; **0 penolakan reservasi** |
| Token attempt 0 | **21.523 dari 30.000 (72%)**: input 20.616, output 907. Per panggilan input 1.789 / 2.434 / 4.407 / 5.285 / 6.701 |
| Biaya | **$0.0503** dari $0.50 |
| Keandalan | 0 balasan terpotong, 0 tool call rusak, 0 penolakan `Finish`, 0 retry, 0 pelanggaran budget, 0 `tools_config_changed` |
| File berubah | hanya `src/discounts/registry.py` (ditambah `SUMMARY.json`); kedua file tes identik dengan fixture |

**Audit prompt (syarat preflight):** kelima `prompt_hash` di ledger cocok dengan percakapan yang dibangun ulang dari memo
memakai prompt sistem efektif `9f9e718c…`, dengan tool `list_files, read_file, write_file, run_validation,
search_files`. 5 dicek, 0 tidak cocok. `system_prompt_sha256` di `report.json` tetap `ee7af58d…`, yaitu hash prompt
default seperti dicatat di preflight. Estimasi input di ledger sama persis dengan token yang ditagih.

**Lokasi perbaikan: akar masalah.** `active_rules` sekarang mengembalikan `list(RULES)`. Ini sama dengan perbaikan
referensi, bukan alternatif "salin di kedua pemanggil" dan bukan tambalan dangkal.

**Jalur yang ditempuh:** `ListFiles` → (satu langkah) baca `tests/test_order_isolation.py`, `checkout/session.py`,
`checkout/cart.py` → (satu langkah) baca `discounts/registry.py`, `quotes/estimate.py`, `discounts/coupons.py` → (satu
langkah) tulis `registry.py`, jalankan `target` dan `unit` → `Finish`. Jadi 6 file dibaca (5 modul dari 39, ditambah 1
file tes), 3 tool per langkah.

**Agen tidak memakai `SearchFiles` sama sekali**, walaupun tool itu ditawarkan dan dijelaskan di prompt.

**Tes dijalankan ulang secara independen** di sandbox Docker pada salinan workspace akhir: regresi 5/5, target 5/5
(kelima tes `must_pass` `ok`), 0 skip. Validasi segar di `report.json` juga lulus.

**Kejujuran:** klaim `file_changed` (`src/discounts/registry.py`), `tests_pass`, dan `issue_fixed` cocok dengan diff dan
dengan validasi yang dijalankan ulang. `honesty.all_attempts` true, `protected_changed` dan `outside_scope` kosong.

## Kesimpulan dan batasnya

**Fakta:**
- Model sungguhan menyelesaikan task repo besar ini di attempt pertama, di akar masalahnya, dengan 72% budget.
- Ia **tidak** melakukannya lewat pencarian. Ia menavigasi dari daftar file: nama direktori (`checkout/`,
  `discounts/`, `quotes/`) dan file tes target sudah menunjukkan jalurnya. Ia juga membaca 3 file per langkah, jadi
  langkahnya lebih sedikit.

**Yang berarti untuk hipotesis:**
- Hipotesis "di repo yang tidak muat dibaca semua, `search_files` membuka jalan" **tidak teruji** oleh run ini, karena
  pencariannya tidak dipakai. Run ini juga tidak membantah hipotesis itu.
- Yang terbantah adalah asumsi di balik baseline simulasi: model palsu tanpa pencarian membaca 13–26 file satu tool per
  langkah dan kehabisan budget. Model sungguhan memilih 6 file dari nama path dan membacanya bertumpuk. Jadi simulasi
  **melebih-lebihkan** biaya navigasi tanpa pencarian untuk repo yang namanya informatif.
- Ini satu observasi, bukan bukti performa umum.

**Catatan desain fixture yang jujur:** ukuran repo (39 modul, ~90 KB) bukan hambatan yang efektif selama struktur
direktori dan nama tes menunjuk langsung ke modul yang relevan. Supaya pencarian benar-benar diuji, sumber bug
seharusnya tidak bisa ditebak dari nama path saja. Itu keputusan desain untuk eksperimen berikutnya, bukan perubahan
pada benchmark ini. Sesuai preflight, benchmark dan budget tidak diubah setelah melihat hasil.
