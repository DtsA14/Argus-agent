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
