# Spec: agen yang kehabisan konteks, dan mengulang agen dalam job yang sama

Status: **spec, belum dikoding.** 2026-10-24. Dari router pilot #3 (`pilots/router_v0/p3/RESULT.md`) dan review Atha
(lima butir, bagian 2). **Keputusan yang diminta: bagian 6.**

## 1. Masalah (router pilot #3)

Job `j20261024_031449_052d`: drafnya bagus dan sudah di-approve (38 menit review), lalu agen gagal dalam 42 detik dan
$0,0092. Di kedua attempt agen **tidak menulis apa pun**. Ia membaca 8–9 berkas (`codetask/run.py`,
`acceptance/draft.py`, `scripts/approve_draft.py`, yang tidak diperlukan), lalu panggilan berikutnya ditolak karena
`max_input_tokens` (40.000) terlewati (`attempt_end: context_limit`).

- **Attempt 2 tidak tahu kenapa attempt 1 berhenti.** `feedback_from(verdict)` hanya memuat kriteria yang gagal, hasil
  validasi, dan berkas yang berubah ("none"). Alasan berhenti (`context_limit`) dan apa yang dibaca tidak ada, jadi
  attempt 2 mengulang pola yang sama persis.
- **Di dalam attempt tidak ada tanda** bahwa konteks hampir habis. Model baru tahu saat panggilan sudah ditolak, yaitu
  saat attempt sudah berakhir.
- **Batasnya per profil, bukan per model.** `large_usd.max_input_tokens` = 40.000 dipilih untuk Sonnet. Untuk
  DeepSeek, perkiraan heuristik (chars/3 × margin) lebih besar dari token sebenarnya (data bagian 4), jadi batas
  efektifnya ±29.000 token asli, padahal harga per panggilannya kecil.
- **Router tidak bisa mengulang agen.** `AGENT_FAILED` hanya bisa `abandon`. Mengulang berarti job baru, drafter baru,
  dan review draf baru, untuk draf yang sudah disetujui.
- **`status` tidak menyebut kenapa attempt berhenti.** `why: stagnant` benar, tapi penyebabnya (`context_limit`) hanya
  ada di `events.jsonl`.

Menaikkan batas saja tidak cukup (review Atha): agen yang membaca tanpa menulis akan membaca lebih banyak, dan attempt
berikutnya tetap mengulang polanya. Karena itu butir 1 dan 2 yang utama, butir 3 hanya pendukung.

## 2. Usulan

### 2.1 Feedback antar attempt memuat cara attempt sebelumnya berhenti

Attempt mengembalikan dua hal baru, yang ikut di hasil node `agent` (sudah di-commit sebagai `result_committed`, jadi
resume tidak menghitung ulang):
- `read`: path dari setiap `ReadFile` yang berhasil di attempt itu, urut pertama dibaca, unik, paling banyak 20;
- `wrote`: apakah workspace berubah selama attempt (digest akhir ≠ digest awal attempt). Digest awal sudah di-commit
  oleh D3 (`attempt_start`) bila auto-validate aktif; ini dijadikan selalu di-commit.

`feedback_from` menerima ringkasan attempt dan menambah `stopped: {end, steps, wrote, read}`. `task_prompt` menulis,
setelah bagian yang sudah ada:

```
How the previous attempt ended: <end> after <steps> steps; it changed no file.          (atau: it changed files)
```

dan **hanya bila** `end` = `context_limit` dan `wrote` = false:

```
It ran out of context before changing any file. Files it read: a.py, b.py, ...
The workspace is kept between attempts. Read only what the change needs, then write it: the writable files are
<scope.writable>. A call that does not fit max_input ends the attempt.
```

- Berkas writable diambil dari kontrak, **bukan** dari teks issue (tidak ada parsing bahasa).
- Feedback tanpa `stopped` (checkpoint lama) menghasilkan prompt yang sama seperti sekarang, jadi memo key langkah 0
  run lama tidak berubah.

### 2.2 Satu peringatan konteks di tengah attempt

Pola sama dengan pesan batas D3 (`AUTO_LIMIT`). Setelah hasil tool sebuah langkah di-commit, bila belum ada peringatan
di attempt ini, workspace belum berubah sejak awal attempt, dan **perkiraan input panggilan berikutnya** (fungsi
perkiraan yang sama dengan `LLMCaller`) > 70% `max_input_tokens`, harness menambah satu pesan:

```
Context: the next call is about <p>% of this attempt's input limit (<est> of <max>) and no file has been changed yet.
Write your change now; a call over the limit ends the attempt.
```

- Keputusan dan isi pesan **di-commit** seperti `after_step` D3 (key: node, task, iteration, step, parent LLM step,
  versi pesan), dan diambil dari memo saat resume. Alasannya sama dengan D3: saat resume workspace bisa sudah lewat
  langkah itu.
- Tidak ada panggilan model tambahan. Pesan hanya muncul bila `max_input_tokens` ditetapkan (profil USD).
- Ambang 70% ada di config (`code_task.context_notice_at: 0.7`); `null` mematikannya.

### 2.3 `max_input_tokens` per model

`code_task.max_input_tokens_by_model: {"deepseek:deepseek-flash": 60000, "deepseek:deepseek-v4-pro": 60000}`. Bila
model coder ada di daftar itu **dan** profil memakai `max_input_tokens`, angka model menggantikan angka profil. Model
lain (Sonnet) tetap memakai angka profil (40.000). Angka efektif dicatat di `budget_profile` run seperti sekarang.

- **Dasar 60.000** (ledger 14 run DeepSeek di `~/pilot3a_live/jobs`, 177 panggilan, est/aktual): coder median 1,34
  (min 1,03, maks 1,46); drafter median 1,37 (**min 0,89**, maks 1,54). Dengan 60.000 perkiraan, input sebenarnya
  ±45.000 di median dan paling banyak ±67.000 bila perkiraannya kurang, di bawah konteks model. Biaya terburuk per
  panggilan: 60.000 × $0,15 × 2 (peak) / 1M = **$0,018**. Reservasi attempt ($0,45) tetap yang membatasi uang.
- **Perkiraan token tidak diubah.** Minimum 0,89 berarti perkiraan kadang **lebih kecil** dari tagihan. Memangkas
  margin akan membuat cap uang bisa terlampaui. Yang diubah hanya batas input per panggilan.
- Drafter tidak berubah (sudah 64.000 sejak w2b1d2).

### 2.4 `argus retry <job>`: mengulang agen dalam job yang sama

- Hanya dari `AGENT_FAILED`. Transisi baru: `AGENT_FAILED → AGENT_RUNNING`.
- Tahap baru `a<n+1>` (`a2`, `a3`, …), run baru `<job>-a2` dengan workspace baru dari task yang sama. Cap tahap =
  `min(cap profil, sisa job)`, dicatat saat mulai, tidak dihitung ulang saat resume (aturan v0). Tidak cukup untuk satu
  attempt: `BLOCKED budget`, tanpa panggilan model.
- **Kontrak yang sama:** sha kontrak yang dijalankan harus sama dengan `approval.contract_sha256`. Bila berbeda,
  `BLOCKED contract_changed` (pemeriksaan `_agent` yang sudah ada). Draf tidak di-approve ulang; `max_iterations` dari
  approval.
- **Konfirmasi baru** lewat `live()`: layar batas menyebut tahap, cap, sisa job, dan alasan berhenti tahap sebelumnya.
  Lalu `[y/N]` atau `--yes` dengan `--key-file`, seperti tahap live lain. Kunci per job berlaku.
- `resume`, `status`, dan `list` memakai tahap agen **terakhir**, bukan `a1` yang ditulis langsung di kode.
- `next:` di `status` untuk `AGENT_FAILED` menjadi `argus retry <job>  |  argus abandon <job> "<why>"`.

### 2.5 `status` menampilkan cara setiap attempt berhenti

Untuk setiap tahap agen, dari `events.jsonl` run-nya (hanya dibaca, seperti `spent_nano`):

```
  a1 attempts: 1 context_limit after 6 steps, no file changed; 2 context_limit after 5 steps, no file changed
```

`no file changed` diambil dari hasil attempt bila ada (run baru), dan dihilangkan untuk run lama. Teksnya lewat
`clean()`.

## 3. Yang tidak berubah

Jalur uang (reservasi, ledger, refusal sebelum kirim), perkiraan token, aturan stagnan (dua attempt dengan kriteria
gagal yang sama), drafter, dan approve. Agen dengan model palsu dan run tanpa `max_input_tokens` berperilaku sama.

## 4. Data dasar

Rasio est/aktual dihitung dari setiap `llm_call` `status: ok` model DeepSeek dengan `input_tokens` > 0 di
`~/pilot3a_live/jobs/*/runs/*/events.jsonl` (2026-10-24). Skripnya disimpan bersama bukti PR kode, sehingga angkanya bisa
dihitung ulang.

## 5. Tes (gagal di kode lama; mutan)

1. **Feedback:** attempt yang berakhir `context_limit` tanpa menulis menghasilkan prompt attempt berikutnya yang memuat
   cara ia berhenti, berkas yang dibaca (urut, unik, ≤ 20), dan writable dari kontrak. Attempt yang menulis, atau
   berakhir karena hal lain, tidak mendapat petunjuk "ran out of context" tetapi tetap mendapat baris "How the previous
   attempt ended". Feedback lama (tanpa `stopped`) menghasilkan prompt yang sama persis seperti sekarang.
2. **Crash-resume feedback:** crash setelah attempt 1 di-commit, lalu resume: prompt attempt 2 sama dan tidak ada
   panggilan model yang dibeli ulang.
3. **Peringatan:** muncul tepat sekali saat perkiraan > 70% dan workspace belum berubah; tidak muncul setelah ada
   tulisan, tanpa `max_input_tokens`, atau dengan `context_notice_at: null`. Crash setelah keputusan di-commit lalu
   resume (workspace sudah berubah) menghasilkan pesan yang sama dari memo.
4. **Per model:** DeepSeek dengan `large_usd` mendapat 60.000; Sonnet tetap 40.000; profil tanpa `max_input_tokens`
   tetap tanpa batas input; angka efektif tercatat di `budget_profile`.
5. **Retry:** dari `AGENT_FAILED` membuat `a2` dengan run id baru, cap = `min(profil, sisa)` yang dicatat; ditolak dari
   state lain; `BLOCKED budget` tanpa panggilan model bila sisa kurang; kontrak berubah → `BLOCKED contract_changed`;
   konfirmasi "N" tidak memulai apa pun; kunci per job menolak perintah kedua; resume `a2` memakai cap tercatatnya;
   `status` dan `list` menghitung uang semua tahap agen.
6. **Status:** baris attempt per tahap agen (dengan `context_limit` dan `no file changed`), dibaca tanpa mengubah
   berkas apa pun.

Mutan untuk setiap baris di atas, lalu `verify.sh` penuh di latar belakang. Bukti di `verification/`. Sesudahnya job
`j20261024_031449_052d` diulang lewat `argus retry` (tahap `a2`), setelah Atha menulis "y".

## 6. Keputusan

| | Pertanyaan | Usul |
|---|---|---|
| K1 | Isi feedback | Cara berhenti selalu; petunjuk "ran out of context" + berkas dibaca + writable hanya untuk `context_limit` tanpa tulisan |
| K2 | Ambang peringatan | 70% dari `max_input_tokens`, sekali per attempt, hanya bila belum ada tulisan; di config |
| K3 | Angka per model | DeepSeek flash dan v4-pro 60.000; Sonnet tetap 40.000; perkiraan token tidak diubah |
| K4 | Nama perintah | `argus retry <job>` (hanya dari `AGENT_FAILED`, tahap `a<n+1>`, konfirmasi baru) |
| K5 | Urutan PR | Satu PR kode untuk 2.1–2.5, karena pilot ulang butuh semuanya; atau dua PR (agen 2.1–2.3, router 2.4–2.5) bila reviewnya terlalu besar |
