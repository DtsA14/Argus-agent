# Pilot glm_reviewer v0: GLM-5.3 dengan prompt pemburu bug (2026-11-07)

Lanjutan `pilots/self_review_v0` (judge 0/5 bug review #326). Atha 2026-11-07 ("Probe glm ... lanjut sekarang"), Atha
menjalankan `probe.py` dan menempelkan kunci OpenRouter. Prompt pemburu bug, diff + `harness/llm.py` dan
`tests/test_gateway.py` utuh, spek bagian 1-4; satu panggilan verifikasi per temuan (maks 6). Role `code_judge` apa adanya
(GLM-5.3, pin Baidu fp8, reasoning default, `max_output_tokens` 32000).

## Hasil: tidak terukur, $0,1707

- Panggilan berburu: 21.486 token input, **32.000 token output semuanya reasoning**, `stop_reason: length`, balasan kosong,
  386 detik. Tidak ada temuan, jadi tidak ada panggilan verifikasi. Pertanyaan "prompt atau model" belum terjawab.
- Pola yang sama dengan replay judge 2026-11-05 (4/11 panggilan menghabiskan 16000 token untuk reasoning). Tanpa tool dan
  tanpa batas reasoning, GLM tidak berhenti berpikir pada input 78 KB.

## Temuan penting: diskon Baidu habis, GLM 5x lebih mahal

- Ledger: `usd_computed` $0,0342 (harga config $0,28/$0,88) vs `usd_reported` gateway **$0,1707** (`charged:
  gateway_reported`). Judge 2026-11-06 (V1-V4, sr0a/sr0b): rasio reported/computed 1,0.
- `openrouter.ai/api/v1/models/z-ai/glm-5.3/endpoints` 2026-11-07: Baidu fp8 $1,3986/$4,3956 per juta, diskon 0,001
  (2026-11-05: 80%). Harga config sekarang 5x terlalu rendah.
- Akibat: reservasi judge dihitung dengan harga lama, jadi cap judge $0,10 bisa terlampaui sampai sekitar 5x sebelum
  ledger mencatatnya (komentar config sudah menyebut risiko ini). Panggilan 32000 token output kini sekitar $0,17, di atas
  cap judge sendiri.
- Tindakan (jalur ketat, keputusan Atha): jangan jalankan `argus judge` sampai harga di config diperbaiki dan cap/pin
  diputuskan. Lihat PENDING.

Berkas: `probe.py`, `events.jsonl` (ledger, tanpa kunci), `out/hunt.md` (kosong).
