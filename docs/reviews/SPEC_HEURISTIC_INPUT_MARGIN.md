# Spec: margin input heuristik dari ledger, dan plafon token attempt `large_usd`

Status: **draf, menunggu review Atha** (jalur ketat: menyentuh cek sebelum kirim di `harness/llm.py` dan budget profile).
Pemicu: dev set sesudah #215/#216, `sympy__sympy-24562` job `j20261028_051232_d2e8`, retry `a2` berakhir `FAILED_BUDGET`.

## 1. Kejadian

Attempt ke-3 `a2` (DeepSeek V4.1 Flash, profil `large_usd`: plafon 400.000 token, $0,45):

| Langkah | sisa token sebelum kirim | `est_input` (heuristik) | `max_tokens` (cap) | input tagihan | output | kumulatif |
|---|---|---|---|---|---|---|
| 17 | 91.674 | 32.248 | 32.000 | 44.777 | 38 | 353.141 |
| 18 | 46.859 | 33.003 | **13.856** | **45.296** | 1.747 | **400.184** |
| 19 | −184 | 36.169 | – | – | – | refused |

Di langkah 18, worst case yang dicek sebelum kirim adalah `est_input + cap` = 33.003 + 13.856 = 46.859, pas dengan sisa.
Input yang ditagih ternyata 45.296, sekitar 1,37× perkiraan. Total attempt jadi lewat 184 token, dan guard
`EstimateExceeded` (`harness/guard.py:79`) menghentikan job: `agent reported 400184 tokens, estimate is 400000`.
Uang yang terpakai **$0,036 dari reservasi $0,45**. Hampir semua input berupa cache read (44.800 dari 45.296).

Jadi ada dua masalah terpisah:
1. **Jaminan "ditolak sebelum kirim bila tidak muat" bergantung pada `est_input ≥ input sebenarnya`.** Untuk counter
   heuristik itu tidak selalu benar, walaupun sudah ada `llm.input_margin: 1.2`. Yang kena di sini token. Secara prinsip
   **USD juga bisa kena**: `_worst_usd(est_in, cap)` memakai perkiraan yang sama. Di kasus ini USD aman hanya karena
   sisanya besar.
2. **Plafon token `large_usd` (400.000) sekarang yang mengikat, bukan USD.** Plafon ini disebut "only a safety ceiling"
   di `config.yaml`. Dengan 30 langkah (#215) dan input yang dikirim ulang setiap langkah, plafon itu tercapai di $0,036.

## 2. Data ledger

950 panggilan DeepSeek berstatus `ok` di semua job router (`~/pilot3a_live/jobs/j202610*`), rasio input tagihan /
`est_input` (`est_input` sudah termasuk margin 1,2):

| p50 | p90 | p99 | maks | rasio > 1,0 |
|---|---|---|---|---|
| 0,77 | 1,05 | 1,50 | **1,77** | 121 dari 950 (13%) |

Komentar di `config.yaml` (`code_task.max_input_tokens_by_model`) menyebut est/billed median 1,34–1,37 dengan minimum 0,89,
dari 14 run. Data baru: kode sympy yang padat menghasilkan lebih banyak token per karakter, dan 13% panggilan
diperkirakan terlalu rendah.

## 3. Perubahan yang diusulkan

**H1. Margin heuristik per model, dari ledger.** `llm.input_margin_by_model: {"deepseek:deepseek-flash": 2.2,
"deepseek:deepseek-v4-pro": 2.2}`. Model lain tetap memakai `input_margin` 1,2. Margin 2,2 = 1,2 × 1,77 (maksimum
terukur) × ±1,04 cadangan. Dengan itu est/tagihan ≥ 1 di semua 950 panggilan. Margin ini dipakai untuk worst case
token **dan** USD, sebelum kirim, di satu tempat (`provider_counter`). Anthropic tetap memakai counter exact.

Konsekuensinya, setiap panggilan DeepSeek memesan lebih banyak:
- `max_input_tokens` 60.000 (heuristik) akan tercapai lebih cepat, sekitar 27.000 token tagihan, bukan sekitar 45.000.
  Batas itu harus ikut dinaikkan ke ±100.000, supaya batas konteks sebenarnya tidak berubah. Konteks DeepSeek
  **tidak tercatat** di `config.yaml`/registry (yang ada hanya `max_input_tokens_by_model` dan cek long-context untuk
  Anthropic); jendela konteks model perlu dicek di dokumentasi provider sebelum angka ini dipakai.
- Worst case USD per panggilan naik kira-kira ×1,8. Itu tetap kecil (DeepSeek $0,15/M input), dan reservasi attempt
  USD yang mengikat.

**H2. Plafon token `large_usd`: 400.000 → 1.200.000.** USD ($0,45) kembali yang mengikat. 1,2 juta tetap di bawah
`budget.max_tokens` router (3 juta). Untuk Sonnet, 1,2 juta token input ≥ $3,6, jauh di atas $0,45, jadi plafon itu
tidak pernah tercapai lebih dulu.

**H3. Ledger merekam rasio.** `estimate_miss` sudah ditulis ketika input tagihan > perkiraan. Itu ditambah satu baris di
`status`/review (jumlah `estimate_miss` per run), supaya margin bisa dikalibrasi ulang dari data, bukan dari ingatan.

Yang **tidak** diubah: guard `EstimateExceeded` tetap menghentikan node yang melapor lebih dari reservasinya. Cek
sesudah ini tetap ada sebagai pengaman kedua, sesuai `AGENTS.md`.

## 4. Tes (masing-masing harus gagal bila jaminannya dirusak; mutants)

1. Counter heuristik dengan margin per model: model DeepSeek memakai 2,2, model tanpa entri memakai `input_margin`,
   Anthropic tetap exact.
2. Replay langkah 18 di atas (pesan dengan panjang yang menghasilkan est 33.003 pada margin lama): dengan H1, cap
   `max_tokens` dihitung dari est baru, dan worst case ≥ 45.296 + output. Dengan margin lama, tes ini gagal.
3. Worst case USD sebelum kirim memakai est dengan margin yang sama dengan worst case token. Satu tes yang gagal bila
   salah satunya memakai est mentah.
4. `large_usd.attempt_tokens == 1_200_000` dan ≤ `router.overrides["budget.max_tokens"]`. Profil lain tidak berubah.
5. `max_input_tokens_by_model` DeepSeek sama dengan nilai yang ditetapkan spek, dan tetap dibagi margin yang sama (est,
   bukan tagihan).

Verifikasi: `verify.sh` penuh (jalur ketat), mutants untuk tes 1–3.

## 5. Dampak dan batas klaim

- Tidak ada perubahan ke cara ledger mencatat atau ke rumus harga, hanya perkiraan input sebelum kirim.
- "Ditolak sebelum kirim" untuk model heuristik tetap **bukan batas finansial absolut** (`AGENTS.md`). Margin dari data
  menurunkan kemungkinannya; yang absolut tetap hanya counter exact.
- Eval lama (`evals/budget_v1`) memakai `config.yaml`. Kalau H1 masuk `config.yaml`, angka eval berubah. Pilihan: H1
  hanya lewat override router, sama seperti `max_steps` dan `validation_timeout_s`. **Usul: override router**, supaya
  eval tetap sebanding.

## 6. Pertanyaan untuk Atha

1. Margin 2,2 dari maksimum terukur, atau lebih konservatif, misalnya 2,5?
2. H1 lewat override router (usul), atau di `config.yaml` untuk semua?
3. H2 1,2 juta setuju?
