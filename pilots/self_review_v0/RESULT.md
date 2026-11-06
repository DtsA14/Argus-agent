# Pilot self_review v0: judge GLM sebagai reviewer PR Argus sendiri (2026-11-06)

Butir PENDING "Self-review Argus" (Atha 2026-11-06, jalur cepat, Atha "#1 dan #2 jalur cepat"). Eksperimen terkecil:
diff #326 **sebelum** perbaikan review (`b65ec4f8`, `harness/llm.py` retry 429, 18 berkas, 27 KB) dinilai `argus judge`
(GLM-5.3 lewat OpenRouter, pin Baidu fp8), lalu dibandingkan dengan temuan `/code-review medium` yang dulu diperbaiki
(`docs/reviews/SPEC_RATE_LIMIT_RETRY.md` bagian 5).

Cara: tanpa skrip kunci baru. Dua salinan job V4 prompt injection di `~/sr_jobs` (`build_jobs.py`): issue = spek bagian
1-4 (tanpa bagian 5), draf = rencana satu paragraf + `tests/test_rate_limit_retry.py`, `changes.patch` = diff pra-perbaikan,
`claims.md` = pesan commit, `tests.md` = "replay, harness tidak menjalankan tes". Prompt judge tidak diubah (masih
"change another AI agent made"). Dua run (job `sr0a`, `sr0b`) untuk melihat variasi.

## Hasil

| | run a | run b |
|---|---|---|
| vonis | PASS | PASS |
| biaya | $0,0255 | $0,0314 |

Temuan review yang diperbaiki (kebenaran dasar), tertangkap?

| temuan `/code-review` | a | b |
|---|---|---|
| 429 dan error lain satu penghitung: urutan campuran salah jeda/salah jumlah percobaan | tidak (dideskripsikan sebagai benar) | tidak (b menulis "429,429,500 stops at attempts" sebagai benar) |
| model `:free` ikut jeda panjang (rantai fallback jadi lambat) | tidak | tidak |
| error rate limit tanpa status HTTP tidak ikut jeda panjang | tidak | tidak |
| `Retry-After` negatif/NaN/inf | tidak | tidak |
| config `inf`/NaN, `attempts` < 1, `base_delay` negatif | tidak | tidak |
| **tertangkap** | **0/5** | **0/5** |

Temuan judge lain:
- a: 429 provider langsung kini bisa 4 tagihan worst-case: **benar**, sama dengan butir "Dibiarkan" review (disetujui
  lewat K1/K2, reservasi tetap dicek).
- a: tes memakai helper privat `_worst_usd`: gaya, bukan bug.
- b: `test_gateway.py` akan tidur sungguhan 105-255 s: **alarm palsu**, `caller()` di berkas itu sudah menyuntik
  `sleep=lambda s: None`.

## Bacaan (n = 2, satu PR)

- Untuk PR inti harness, judge ini **tidak berguna sebagai reviewer kedua**: 0 dari 5 bug nyata, dua kali PASS, satu
  alarm palsu. Ia meringkas diff dengan akurat dan memeriksa diff terhadap spek, tetapi tidak mencari kasus tepi di luar
  spek (urutan error campuran, nilai non-finite), padahal di sanalah semua temuan review.
- Bedanya dengan uji cacat tanam (judge 10/10): di sana cacatnya melanggar issue (kode dibentuk untuk tes, XSS); di sini
  bugnya kasus tepi yang spek tidak sebut. Prompt judge memang menyuruh tidak memblok "edge cases the issue does not ask
  about".
- Usul Claude (keputusan Atha): **`argus review --diff` tidak dibangun** dari bukti ini. Bila dicoba lagi, butuh prompt reviewer sendiri
  (cari kasus tepi, bukan cek kesesuaian) dan model yang lebih kuat; itu eksperimen baru, bukan lanjutan.
