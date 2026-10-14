# Permintaan review: fase 2a (wrapper LLM + budget USD)

Commit: `a856654` di `main` (sebelumnya `4ee4cef`). Diff: `git diff 4ee4cef a856654`.
Bukti: `verification/verify-20261014T083017Z-x86_64.log` (252 tes lulus di venv bersih).

## File utama
- `harness/llm.py`: `LLMCaller` dan `Reservation` (inti review)
- `harness/budget.py`: budget USD tingkat run, `node_usd_estimates`
- `models/registry.py`: `max_retries=0` untuk semua provider
- `runner.py`: `recursion_limit` mengikuti `max_iterations`, `usd_used` / `usd_billed` di result
- `tests/test_llm_wrapper.py`: 78 tes

## Klaim yang minta dicek
1. Request yang tidak muat di sisa reservasi (token atau USD) ditolak **sebelum** dikirim.
2. `max_tokens` yang dikirim = batas paling ketat dari: batas role, sisa token, sisa USD (termasuk pengali jam sibuk DeepSeek).
3. Setiap percobaan tercatat sebagai `llm_call`; percobaan gagal di-charge worst case; total ledger = total yang di-charge ke reservasi.
4. Retry tersembunyi SDK dimatikan, jadi tidak ada percobaan di luar ledger.
5. Budget USD tingkat run: iterasi baru hanya mulai kalau biaya terburuknya muat.

## Batasan yang kami sadari (mohon dinilai apakah bisa diterima)
- Hitungan token input untuk OpenAI/DeepSeek adalah heuristik (karakter/3 × 1,2). Kalau meleset ke bawah,
  kelebihan tetap ditagih dan dicatat sebagai `estimate_miss`. Untuk Anthropic hitungannya eksak (API `count_tokens`),
  tapi itu panggilan jaringan tambahan per request.
- Percobaan gagal di-charge worst case (input + max_tokens). Aman, tapi bisa membuat retry cepat ditolak karena reservasi habis.
- Thread safety: satu `Reservation` dipakai satu node run; belum ada reservasi bersama antar worker paralel.

## Pertanyaan
- Apakah ada jalur di mana biaya bisa keluar tanpa tercatat atau tanpa dicek?
- Apakah kebijakan worst case untuk percobaan gagal terlalu konservatif?
- Ada yang harus diubah di antarmuka `call(messages, reservation, tools)` sebelum 2b memakainya?
