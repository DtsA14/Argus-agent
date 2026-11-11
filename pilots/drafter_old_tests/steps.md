# Langkah (2026-11-11, Claude, "go live" Atha)

| # | hasil |
|---|---|
| 0 | `~/pilot3a_live` `ba5aa99` (#427), bersih; tidak ada job `DRAFTING`/`AGENT_RUNNING`; `j20261111_073447_cc5a` DRAFT_FAILED, $0,0441 dari $1,00 |
| 1 | `pull --ff-only` → `0e98eee` (merge #429) |
| 2 | redraft: d2 `DRAFTED` $0,0253 (5 submit: 3 ditolak, 1 pertanyaan merah, 1 diterima) |
| 3 | kontrak d2: `target`, `whenwib`, `cards` dari drafter + `old_tests_1` (15), `old_tests_2` (15), `old_tests_3` (14) dari harness = 44 berkas lama, masing-masing sekali |

Penolakan d2 (semua formulir, sasaran 3a-2): id validasi bukan huruf kecil; tes baru belum protected; glob protected
`src/**/*.test.jsx` tidak cocok. Kesalahan yang menghabiskan d1 (ReviseDraft satu validasi, 46 berkas hilang) tidak muncul.

Sesudahnya (jalur cepat): Claude membaca draf `ff9e8950ea33` (5 tes merah `AssertionError`, sesuai contoh issue, tes lama
protected, tidak ada tes lama diubah), approve; agen 1 percobaan 16 langkah $0,0137; patch `7a64066c…` diterapkan sebagai
argus-viewer `9e78ed1` (Issue 042), `applied`; `viewer-deploy` → live `j20261111_073447_cc5a-9e78ed13b03f`, rollback → 041;
`viewer-smoke` 12/12 ok. Total job $0,0831.
