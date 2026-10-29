# Spek: counter heuristik menghitung `reasoning_content` yang dikirim, dan `estimate_miss` di `status`

Status: **draf untuk keputusan Atha**, 2026-10-29. Jalur ketat: menyentuh cek sebelum kirim di `harness/llm.py` (uang).
Asal: kandidat (c) batch 5 (H3 di `SPEC_HEURISTIC_INPUT_MARGIN.md`, "hanya tampilan"). Data untuk H3 menunjukkan
penyebabnya bukan margin, melainkan bug penghitungan; jadi spek ini lebih luas dari H3. **Scope creep yang disengaja**,
ditandai di sini sebelum ada kode.

## 1. Kejadian

`sympy__sympy-19954` batch 5, job `j20261029_002951_8b7e`, stage `a2`, attempt 1 (margin DeepSeek sudah 2,5):

| Langkah | `est_input` | input tagihan | tagihan / est | reasoning kumulatif sebelum langkah (karakter) |
|---|---|---|---|---|
| 15 | 36.316 | 32.185 | 0,89 | 81.814 |
| 21 | 39.676 | 49.251 | 1,24 | 146.782 |
| 22 | 39.980 | 64.534 | **1,61** | 208.378 (langkah 21 sendiri: 61.596) |
| 25 | 42.061 | 80.493 | **1,91** | 268.676 |

Dari langkah 21 ke 22, tagihan naik ±15.000 token, sementara `est_input` hampir diam. Kenaikan itu sama dengan reasoning
langkah 21 (61.596 karakter ≈ 15.000 token).

## 2. Penyebab

`models/registry.py` (`ArgusChatDeepSeek._get_request_payload`) mengirim balik `reasoning_content` dari **setiap** balasan
assistant sebelumnya. Mode thinking DeepSeek dengan tools mewajibkannya (HTTP 400 kalau tidak). Counter heuristik
(`harness/llm.py`, `heuristic_counter` → `_text`) menghitung content, tool call, dan id, tetapi **tidak** `reasoning_content`
(yang ada di `additional_kwargs`). Jadi teks yang dikirim lebih banyak daripada teks yang dihitung, dan selisihnya terus
tumbuh selama attempt berjalan.

Akibatnya jaminan AGENTS.md "permintaan ditolak sebelum kirim bila tidak muat di reservasi" bergantung pada margin, bukan
pada hitungan. Margin 2,5 (#217) menutup sebagian besar kasus, tetapi sumbernya tetap ada. `FAILED_BUDGET` di `24562`
(dev set 1) dan `19954` a1 (batch 5) cocok dengan pola ini. Batas yang kena sejauh ini batas token, tetapi worst case USD
memakai est yang sama.

## 3. Data (semua job router, `~/pilot3a_live/jobs/j202610*`, 2.006 panggilan DeepSeek `ok` dengan memo)

Rasio input tagihan / perkiraan. Kolom "dengan reasoning" menambahkan reasoning semua balasan sebelumnya dalam attempt yang
sama (dari memo) ke perkiraan, dengan rumus counter yang sama (karakter / 3 × margin):

| Perkiraan | p99 | maks | > 1 |
|---|---|---|---|
| sekarang (`est_input`, margin 1,2 lalu 2,5) | 1,42 | **1,91** | **134** |
| dengan reasoning, margin 1,0 | 1,00 | 1,02 | 22 |
| dengan reasoning, margin 1,2 | 0,83 | 0,85 | 0 |
| dengan reasoning, margin 1,5 | 0,67 | 0,68 | 0 |
| dengan reasoning, margin 2,5 | 0,40 | 0,41 | 0 |

Catatan: margin per run diperkirakan dari tanggal #217 (pagi 2026-10-28). Run di sekitar batas itu bisa salah kelompok;
tes replay (bagian 5) memakai angka persis.

Input tagihan terbesar sejauh ini: agen 108.065 token (95 dari 1.181 panggilan > 50.000), drafter 127.856 (176 dari 825
> 50.000). Semuanya diterima provider.

## 4. Perubahan

**E1. Counter heuristik menghitung semua yang dikirim.** `_text` dipakai oleh counter **dan** `prompt_hash`. Jadi counter
mendapat fungsinya sendiri, `_sent_text(m)` = `_text(m)` + `additional_kwargs["reasoning_content"]` bila ada. `prompt_hash`
dan kunci memo **tidak berubah**, karena run lama harus tetap bisa di-resume dari memo-nya. Reasoning sebuah langkah sudah
ditentukan oleh balasan yang di-commit sebelum langkah berikutnya, jadi identitas input tetap utuh (bagian 6).

**E2. Margin dan batas input mengikuti hitungan yang benar** (override router, sama seperti #217; `config.yaml` dan eval
tetap):
- `llm.input_margin_by_model` DeepSeek: 2,5 → **1,5** (maks terukur 0,68; cadangan ±47%).
- Batas input ditulis dalam satuan est. Karena est sekarang ikut menghitung reasoning, angkanya dihitung dari batas token
  **mentah** yang dimaksud:
  - agen `code_task.max_input_tokens_by_model`: **150.000** est = 100.000 mentah × 1,5. Saat ini batas mentah efektifnya
    50.000 (125.000 / 2,5) di atas hitungan yang kurang. Kalau dibiarkan 50.000 dengan hitungan yang benar, 95 panggilan agen
    yang dulu lolos akan kena `context_limit`.
  - drafter `drafter.max_input_tokens`: 416.000 → **250.000** est (≈ 166.000 mentah × 1,5, sama dengan batas mentahnya
    sekarang).
  - `large_usd.attempt_tokens` 1.200.000 tidak berubah.

**E3. `estimate_miss` di `status` (H3 asli).** `argus status` menulis satu baris per stage yang ledger-nya memuat event
`estimate_miss`: `estimate misses: <n> of <calls> calls, max <input/est>` (dua desimal). Stage tanpa miss: tidak ada baris.
Hanya tampilan, membaca ledger yang sudah ada.

## 5. Tes (masing-masing harus gagal kalau jaminannya dirusak; mutants)

1. Counter heuristik: sebuah AIMessage dengan `reasoning_content` 60.000 karakter menaikkan est sebesar ≥ 60.000 / 3 × margin.
   Gagal kalau reasoning tidak dihitung.
2. **Counter ⊇ payload:** untuk percakapan dengan reasoning, tool call, dan tool result, setiap string di payload
   `ArgusChatDeepSeek._get_request_payload` (tanpa kirim) ikut terhitung di `_sent_text`. Gagal kalau ada field baru yang
   dikirim tetapi tidak dihitung. Ini penjaga struktural, supaya bug yang sama tidak muncul lagi dari field lain.
3. `prompt_hash` tidak berubah oleh `reasoning_content`, dan hash percakapan lama sama dengan sebelumnya (resume memo lama).
4. Replay langkah 22 `19954` a2 (panjang reasoning kumulatif seperti di memo, sintetis): dengan E1 + margin 1,5, worst case
   sebelum kirim ≥ input tagihan 64.534 + output; tanpa E1 gagal.
5. Override router: margin DeepSeek 1,5, batas agen 150.000, drafter 250.000; `config.yaml` tidak berubah.
6. `status`: stage dengan 3 `estimate_miss` dari 10 panggilan menulis `estimate misses: 3 of 10 calls, max 1.91`; stage tanpa
   miss tidak menulis baris itu.

Verifikasi: mutants untuk tes 1–4, `/code-review medium` + `/security-review`, `verify.sh` penuh sekali di commit final,
lalu "merge" Atha.

## 6. Yang tidak diubah, dan batas klaim

- `prompt_hash` dan kunci memo: reasoning tidak masuk hash (keputusan lama di `registry.py`). Aman karena balasan langkah k
  di-commit sebelum langkah k+1 dibentuk. Konteks yang berbeda hanya di reasoning tidak bisa terjadi tanpa balasan baru,
  dan balasan baru berarti langkah k belum di-commit, jadi langkah k+1 juga belum ada di memo.
- Guard `EstimateExceeded` tetap ada sebagai pengaman kedua.
- Counter heuristik tetap **bukan batas finansial absolut** (AGENTS.md). Spek ini menutup satu sumber selisih yang terukur,
  bukan semua kemungkinan. Model Anthropic memakai counter exact dan tidak terpengaruh.
- Biaya: est lebih jujur, dan margin turun dari 2,5 ke 1,5. Panggilan awal (tanpa reasoning) memesan lebih sedikit dari
  sekarang, panggilan akhir lebih banyak. Uang sebenarnya tidak berubah.

## 7. Pertanyaan untuk Atha

1. Scope: E1 + E2 + E3 dalam satu PR jalur ketat (usul), atau E3 dulu (cepat) dan E1/E2 terpisah?
2. Margin DeepSeek sesudah E1: **1,5** (usul), 1,2 (maks terukur 0,85, cadangan 15%), atau tetap 2,5 (aman, tetapi batas
   input harus naik ke 250.000 / 416.000 est supaya konteks tidak menyusut)?
3. Batas mentah agen 100.000 token (usul; maks yang pernah diterima 108.065) atau tetap 50.000 (lebih banyak `context_limit`)?
