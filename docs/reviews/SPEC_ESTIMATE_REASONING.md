# Spek: counter heuristik menghitung `reasoning_content` yang dikirim, dan `estimate_miss` di `status`

Status: **disetujui** (Atha 2026-10-29: satu PR jalur ketat, margin 1,5, batas mentah agen 100.000). Jalur ketat: menyentuh
cek sebelum kirim di `harness/llm.py` (uang).
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
mendapat fungsinya sendiri, `_sent_text(m)` = `_text(m)` + seluruh `additional_kwargs` kecuali `tool_calls` (salinan provider
dari tool call yang sudah dihitung `_text`). Ini mencakup `reasoning_content` dan field lain yang mungkin dikirim adapter;
kelebihan hitung aman (est lebih besar), kekurangan tidak. `prompt_hash`
dan kunci memo **tidak berubah**, karena run lama harus tetap bisa di-resume dari memo-nya. Reasoning sebuah langkah sudah
ditentukan oleh balasan yang di-commit sebelum langkah berikutnya, jadi identitas input tetap utuh (bagian 6).

**E2. Margin dan batas input mengikuti hitungan yang benar** (override router, sama seperti #217; `config.yaml` dan eval
tetap):
- `llm.input_margin_by_model` DeepSeek: 2,5 → **1,5** (maks terukur 0,68; cadangan ±47%).
- Batas input ditulis dalam satuan est. Karena est sekarang ikut menghitung reasoning, angkanya dihitung dari batas token
  **mentah** yang dimaksud:
  - agen `code_task.max_input_tokens_by_model`: **150.000** est = 100.000 mentah × 1,5. **Ini mempertahankan perilaku lama,
    bukan menaikkan batas.** Di atas kertas batasnya 50.000 mentah (125.000 / 2,5), tetapi karena reasoning tidak terhitung,
    konteks yang benar-benar diterima agen sampai ±108.000 token. Kalau batas tetap 50.000 dengan hitungan yang benar, 95 dari
    1.181 panggilan agen yang dulu lolos akan diblokir (`context_limit`): perilaku agen berubah, dan batch sesudahnya tidak bisa
    dibandingkan dengan batch sebelumnya.
  - Context window: referensi API DeepSeek (`api-docs.deepseek.com/api/create-chat-completion`, dicek 2026-10-29) menyebut
    `max_tokens` "between 1 and 384K (393216)" dan "the total length of input tokens and generated tokens is limited by the
    model's context length". Jadi context > 393.216 token, dan 100.000 input + 32.000 `max_tokens` output (132.000) muat.
    Angka context-nya sendiri tidak tercantum di dokumen yang dicek. Input terbesar yang pernah diterima: 127.856.
  - drafter `drafter.max_input_tokens`: 416.000 → **250.000** est (≈ 166.000 mentah × 1,5, sama dengan batas mentahnya
    sekarang).
  - `large_usd.attempt_tokens` 1.200.000 tidak berubah.

**E3. `estimate_miss` di `status` (H3 asli).** `argus status` menulis satu baris per stage yang ledger-nya memuat event
`estimate_miss`: `estimate misses: <n> of <calls> calls, max <input/est>` (dua desimal). Stage tanpa miss: tidak ada baris.
Hanya tampilan, membaca ledger yang sudah ada.

## 5. Tes (masing-masing harus gagal kalau jaminannya dirusak; mutants)

1. Counter heuristik: sebuah AIMessage dengan `reasoning_content` 60.000 karakter menaikkan est sebesar ≥ 60.000 / 3 × margin.
   Gagal kalau reasoning tidak dihitung.
2. **Counter ⊇ payload, untuk semua adapter** (permintaan Atha: harness multi-provider). Setiap kind di
   `models.registry.BUILDERS` harus masuk salah satu kelompok: dihitung exact oleh provider (`anthropic`: counter API
   provider atas pesan yang sama), tidak pernah mengirim (`fake`), atau heuristik (`openai`, `openai_compatible`,
   `deepseek`). Kind baru yang belum ditempatkan membuat tes gagal. Untuk setiap adapter heuristik, payload
   `_get_request_payload` (dibangun tanpa kirim) dari percakapan dengan reasoning, tool call berargumen unicode, dan tool
   result: est pada margin 1,0 ≥ (jumlah karakter semua string di `messages` payload) / 3. Gagal kalau ada field yang
   dikirim tetapi tidak dihitung, dari adapter mana pun.
3. `prompt_hash` tidak berubah oleh `reasoning_content`, dan hash percakapan lama sama dengan sebelumnya (resume memo lama).
4. Replay dua langkah yang tercatat (bagian dihitung = `est_input` lama, reasoning kumulatif dari memo):
   - `24562` a2 attempt 3 langkah 18: est 33.003 pada 1,2, reasoning 79.307 karakter, sisa 46.859, tagihan 45.296 + 1.747.
     Dengan E1 + 1,5: est ≥ tagihan, dan panggilan ditolak sebelum kirim (dulu terkirim lalu lewat 184 token).
   - `19954` a2 attempt 1 langkah 22: est 39.980 pada 2,5, reasoning 208.378 karakter, tagihan 64.534: est ≥ tagihan.
   Tanpa E1 keduanya gagal. Tes lama `test_input_margin.py` yang mengunci margin 2,5, skala 2,5/1,2, dan replay tanpa
   reasoning diganti tes ini.
5. Override router: margin DeepSeek 1,5, batas agen 150.000, drafter 250.000; `config.yaml` tidak berubah.
6. `status`: stage dengan 3 `estimate_miss` dari 10 panggilan menulis `estimate misses: 3 of 10 calls, max 1.91`; stage tanpa
   miss tidak menulis baris itu.

Verifikasi: mutants untuk tes 1–4, `/code-review medium` + `/security-review`, `verify.sh` penuh sekali di commit final,
lalu "merge" Atha.

## 5a. Audit uang yang sudah keluar (permintaan Atha)

Semua ledger di VM (169 run: `~/*/runs`, `~/*/jobs/*/runs`), 2026-10-29:
- **USD: tidak ada yang lewat.** 0 `budget_violation` dengan `usd_used > usd_reserved`; 0 dari 2.533 panggilan `ok` dengan
  biaya tagihan > `worst_usd` sebelum kirim (DeepSeek maks 0,93×; Anthropic maks 1,00× di panggilan yang output-nya
  `max_tokens`, counter exact); 0 job lewat `max_usd`, 0 stage lewat `cap_usd`. Untuk DeepSeek ini **bukan** karena
  jaminannya bekerja: worst case USD menghitung semua input dengan harga penuh ($0,15/M), sedangkan hampir semua input yang
  tertagih adalah cache read ($0,003/M). Est yang terlalu rendah tertutup oleh selisih harga itu.
- **Token: dua reservasi lewat**, keduanya dihentikan oleh guard `EstimateExceeded` (pengaman kedua) dengan status
  `FAILED_BUDGET`:
  - `j20261028_051232_d2e8-a2` (`sympy__sympy-24562`, dev set 1): 400.184 dari 400.000 token, $0,0363 dari $0,45;
  - `j20261029_002951_8b7e-a1` (`sympy__sympy-19954`, batch 5): 1.210.037 dari 1.200.000 token, $0,1108 dari $0,45.
- 136 event `estimate_miss` di semua ledger (134 di 23 run router).

**Hasil yang tercemar:** kedua `FAILED_BUDGET` di atas dicatat sebagai **harness-affected** (aturan sama dengan `23824`),
terpisah dari kegagalan model, di `pilots/swe_v0/dev1/RESULT.md` dan `pilots/swe_v0/batch5/RESULT.md`. Angka batch tidak
diubah, dan instance itu tidak dijalankan ulang di batch yang sama sesudah fix (harness-nya sudah beda). Run ulang hanya
di batch berikutnya, sebagai data tersendiri.

## 6. Yang tidak diubah, dan batas klaim

- `prompt_hash` dan kunci memo: reasoning tidak masuk hash (keputusan lama di `registry.py`). Aman karena balasan langkah k
  di-commit sebelum langkah k+1 dibentuk. Konteks yang berbeda hanya di reasoning tidak bisa terjadi tanpa balasan baru,
  dan balasan baru berarti langkah k belum di-commit, jadi langkah k+1 juga belum ada di memo.
- Guard `EstimateExceeded` tetap ada sebagai pengaman kedua.
- Counter heuristik tetap **bukan batas finansial absolut** (AGENTS.md). Spek ini menutup satu sumber selisih yang terukur,
  bukan semua kemungkinan. Model Anthropic memakai counter exact dan tidak terpengaruh.
- Biaya: est lebih jujur, dan margin turun dari 2,5 ke 1,5. Panggilan awal (tanpa reasoning) memesan lebih sedikit dari
  sekarang, panggilan akhir lebih banyak. Uang sebenarnya tidak berubah.

## 7. Keputusan Atha (2026-10-29)

1. Satu PR jalur ketat: E3 baru berarti di atas counter yang benar; E3 duluan berarti angka di `status` berubah makna besok.
2. Margin 1,5: 0,85 pada 1,2 diukur dari 2.006 panggilan lama; jaminan uang tidak boleh bergantung pada task berikutnya
   yang mirip (kode lebih padat, teks non-Inggris). Cadangan ±32% murah.
3. Batas mentah agen 100.000: mempertahankan perilaku lama (lihat E2), bukan menaikkan batas.
4. Tambahan: tes penjaga untuk semua adapter (tes 2); audit uang (bagian 5a); hasil tercemar dicatat harness-affected.
