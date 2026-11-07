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

## Investigasi penyebab (2026-11-07, tanpa biaya)

Sumber: semua 123 panggilan GLM di ledger job judge (`runs/*-j*/events.jsonl`), parameter yang dikirim, dan
`openrouter.ai/api/v1/models/z-ai/glm-5.3/endpoints`.

1. **Ekor panjang reasoning, sudah terlihat di judge.** Langkah pertama judge memakai 2.088 sampai 28.830 token reasoning,
   tergantung tugas, bukan ukuran input. PR yang sama (#326, sr0a/sr0b, input 10,7 ribu token) sudah 25.332 dan 26.566.
   Probe memberi input dua kali lebih besar (21,5 ribu) dan tugas terbuka ("telusuri kode", sampai 8 temuan), jadi lewat
   32.000 sesuai pola itu, bukan anomali.
2. **Reasoning tidak dibatasi terpisah.** Kita tidak mengirim `reasoning` (effort atau `max_tokens`), padahal endpoint
   Baidu mendukung `reasoning`/`reasoning_effort`. `max_tokens` 32.000 mencakup reasoning dan jawaban, jadi model yang
   berpikir lama tidak menyisakan ruang untuk menjawab. Temperatur tidak dikirim (`ChatOpenAI` default None), jadi bawaan
   provider; bukan penyebab yang terlihat.
3. **Isi reasoning tidak tersimpan**, jadi tidak bisa dibedakan antara berputar-putar (loop) dan kerja yang memang panjang.
   `probe.py` hanya menyimpan `content`.
4. Judge selesai karena alurnya memaksa jawaban lewat tool `SubmitVerdict` dalam beberapa langkah, dan 2 panggilan 16k yang
   kepotong (5 November) diulang. Probe hanya punya satu panggilan, tanpa ulang.

Waktu diskon habis: sr0a/sr0b (2026-11-06 sekitar 20:00 UTC) masih rasio 1,0; probe (2026-11-07 06:00 UTC) 5,0.

Bila dicoba lagi (bukan usul sekarang, harga penuh sekitar $0,10): `reasoning: {max_tokens: 16000}` agar jawaban selalu
punya ruang, input dipersempit ke fungsi yang diubah, dan reasoning disimpan untuk melihat apakah berputar.
Untuk judge (bagian dari keputusan harga di PENDING): ekor 28,8 ribu token di langkah pertama dekat batas 32.000, dan
pada harga penuh satu panggilan seperti itu sekitar $0,15, di atas cap judge $0,10.
