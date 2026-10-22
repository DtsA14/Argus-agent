# Spec D5: prompt caching (Anthropic)

Status: spec, belum dikoding. Syarat mulai: PR #131 dan #132 sudah di-merge (sudah, `5d828ed`). Ditulis oleh Atha/GPT; bagian 9 berisi hasil
verifikasi harga dan perilaku usage oleh Claude (2026-10-22), yang mengoreksi beberapa angka di bawah. **Keputusan yang diminta: bagian 10.**
Tujuan: menurunkan biaya **aktual** loop agen (konteks yang tumbuh dikirim ulang setiap langkah) **tanpa mengubah perilaku agen**. Dengan begitu pilot D5 bisa dibandingkan bersih dengan `pilot3a4`. D4 (batas ListFiles) tidak masuk di sini.

## 0. Fakta harga yang dipakai (verifikasi dulu)

| Model | input | cache write 5m | cache write 1h | cache read | output |
|---|---|---|---|---|---|
| Opus 5.5 | 4.00 | 5.00 (×1,25) | 8.00 (×2) | 0.20 (×0,05) | 20.00 |

- Sumber: artikel pihak ketiga yang mengutip halaman harga Anthropic. Halaman resmi tidak bisa dibuka dari sesi review.
- **Wajib:** cocokkan setiap angka dengan halaman harga resmi Anthropic sebelum masuk `config.yaml`. Catat tanggal pengecekannya di komentar config, seperti baris yang sudah ada.
- `cache_read` Opus 0.20 di config **sesuai** angka itu (×0,05, bukan ×0,1). Ini mengoreksi perkiraan "×0,1" di diskusi sebelumnya.
- Sonnet/Haiku 5.5: isi angka write dari halaman resmi. Kalau tidak bisa dipastikan, caching untuk model itu tetap **off** (lihat §2).
- Cek juga apakah ada tarif konteks panjang (ada klaim pihak ketiga tentang ×5 di atas 100k token untuk Haiku 5.5). Kalau ada, `max_input` harus tetap di bawah ambangnya, dengan tes yang gagal bila config melewatinya.

## 1. Cakupan

- Hanya provider `anthropic`, lewat `cache_control` eksplisit. DeepSeek/OpenAI caching otomatis tanpa biaya tulis: tidak ada perubahan perilaku, tetapi field ledger baru (§4) tetap diisi.
- TTL hanya **5m**. 1h tidak dipakai di D5 (×2 tidak sepadan, jeda antar langkah termasuk validasi D3 sekitar 38 dtk).
- Config: `llm.prompt_cache: {enabled: false, ttl: 5m}`, bisa di-override per role. Default **off**; dinyalakan eksplisit untuk pilot.

## 2. Harga dan config

- Tambah `cache_write_5m` per model di `prices`.
- `prompt_cache.enabled` + model `anthropic` tanpa `cache_write_5m` (dan `max_usd` finite) → **ConfigError saat start**, bukan diam-diam dianggap harga input. Prinsipnya sama dengan model tanpa harga.
- `cost_usd(price, *, input_tokens, output_tokens, cache_read_tokens=0, cache_write_tokens=0, ...)`:
  `fresh·input + cache_write·write_5m + cache_read·read + output·output`, dalam integer nano-dollar.
  **Hati-hati double count:** pastikan dari respons nyata apakah `input_tokens` versi LangChain (`usage_metadata`) sudah *termasuk* cache read/creation (via `input_token_details`) atau terpisah seperti API mentah. Kunci dengan tes dari respons rekaman.

## 3. Reservasi (tolak sebelum kirim)

- Skenario terburuk per token input = `max(input, cache_write_5m)`, karena seluruh prefix bisa jadi ditulis ulang (cache miss atau kedaluwarsa). Cache hit **tidak boleh** diasumsikan dalam cek sebelum kirim maupun dalam cap output.
- Reservasi node/iterasi ("dearer of input/output") ikut memasukkan `cache_write_5m` dalam `max(...)`.
- `reconcile_ledger` (`unknown_after_crash`) memakai tarif terburuk yang sama.
- Konsekuensi yang disengaja: cek per panggilan sedikit lebih ketat. Penghematan muncul di biaya aktual yang di-charge setelah respons.

## 4. Ledger

- `llm_call` mencatat `cache_read` dan `cache_creation` terpisah (sekarang hanya `cache_read`). `usd_nano` dihitung dari ketiganya.
- Field yang tidak dilaporkan provider → `null`, bukan 0.
- `result.json`: total `cache_read_tokens`, `cache_creation_tokens`, dan biaya yang dihemat dibanding tanpa cache (dihitung, ditandai sebagai estimasi).

## 5. Penempatan breakpoint

- Dipasang di `LLMCaller` saat mengirim, **bukan** disimpan di pesan. Maksimal 4 breakpoint (batas Anthropic); D5 memakai 2:
  1. akhir blok statis (tools + system);
  2. blok terakhir dari riwayat percakapan (prefix bergulir, sehingga langkah berikutnya membaca semua yang sebelumnya).
- Di bawah panjang minimum yang bisa di-cache, provider tidak meng-cache dan tidak error. Itu wajar, dan tercatat sebagai `cache_creation` = 0.

## 6. Invariant yang tidak boleh berubah

- `prompt_hash`, kunci memo langkah, dan `audit_run.py` dihitung dari konten **tanpa** penanda cache. Run dengan caching on/off menghasilkan hash yang sama, sehingga memo lama tetap berlaku dan audit `pilot3a4` tetap 9/9.
- Semua aturan budget di AGENTS.md tetap: ledger `llm_call_started` → `llm_call`, charge walau penulisan ledger gagal, nano-dollar.

## 7. Tes (setiap tes harus gagal di kode lama; mutation-check)

1. Matematika harga: fresh + write + read + output → nano persis. Mutan: write dihargai sebagai input → gagal.
2. Cap output memakai tarif write. Mutan: pakai tarif input → node dengan sisa pas-pasan lolos padahal harus ditolak.
3. Model `anthropic` + cache on + tanpa `cache_write_5m` → ConfigError; nothing sent.
4. Ledger: `cache_creation` dan `cache_read` terpisah, `null` bila tidak ada.
5. Payload: fake model menangkap request, ada `cache_control` di 2 posisi §5, ≤ 4 breakpoint, tidak ada di pesan yang tersimpan di memo.
6. `prompt_hash` dan kunci memo identik dengan cache on/off. Fixture audit `pilot3a4` tetap 9/9.
7. Parsing usage dari respons Anthropic rekaman (dengan creation dan read) → token dan biaya cocok, tanpa double count.
8. Reconcile crash memakai tarif terburuk.

Lalu `verify.sh` penuh, 0 sandbox skip, log di `verification/`.

## 8. Pilot D5 (butuh persetujuan Atha terpisah, tidak otomatis)

- Sama persis dengan `pilot3a4`: issue, model, cap $0,75, anggaran attempt $0,45, satu run serial. Bedanya hanya `prompt_cache.enabled: true`.
- Kriteria ditulis **sebelum** run:
  - `cache_read > 0` mulai langkah ke-2;
  - biaya aktual untuk langkah eksplorasi yang setara jauh di bawah $0,31 `pilot3a4`;
  - tidak ada `budget_violation`;
  - audit hash 9/9-gaya cocok;
  - laporan perilaku (jumlah langkah eksplorasi) dibandingkan dengan `pilot3a4` untuk memastikan perilaku memang tidak berubah.
- Sukses penuh (`PASSED`) bukan syarat D5. Pertanyaannya: apakah dua putaran perbaikan muat dalam satu attempt. Kalau tidak, baru lanjut ke D4.

## 9. Hasil verifikasi (Claude, 2026-10-22)

### 9a. Harga resmi

Sumber: halaman harga resmi Anthropic, `https://platform.claude.com/docs/en/about-claude/pricing` (dibuka 2026-10-22), tabel "Model pricing" dan
"Prompt caching". USD per juta token.

| Model | input | cache write 5m | cache write 1h | cache read | output |
|---|---|---|---|---|---|
| Claude Opus 5.5 | 4 | 5 | 8 | 0,20 (×0,05) | 20 |
| **Claude Sonnet 5.5** (model coder) | 2 | **2,50** | 4 | **0,10** (×0,05) | 10 |
| Claude Haiku 5.5, prompt ≤ 100.000 token | 0,10 | 0,125 | 0,20 | 0,01 | 0,50 |
| Claude Haiku 5.5, prompt > 100.000 token | 0,50 | 0,625 | 1 | 0,05 | 2,50 |

- Opus 5.5: cocok dengan bagian 0 dan dengan `config.yaml`.
- **Sonnet 5.5: `config.yaml` salah di `cache_read` (0,20; resminya 0,10).** Halaman resmi: cache read Opus 5.5 dan Sonnet 5.5 = 0,05× input
  ($0,20 dan $0,10). Saat ini tidak berdampak (belum ada cache read di run mana pun), tetapi begitu caching menyala, ledger akan mencatat read dua
  kali lipat dari tagihan. Arah kesalahannya konservatif (biaya tercatat lebih tinggi), tetap harus dibetulkan di D5.
- Haiku 5.5: klaim tarif konteks panjang **benar**: ambang 100.000 token, harga ×5 di semua kategori. "A request's prompt length counts all of its
  input tokens, including cache reads and cache writes." `config.yaml` sudah mencatat bahwa tier ini tidak dimodelkan.
- Pengali umum: write 5m ×1,25, write 1h ×2, read ×0,1 (×0,05 untuk Opus 5.5 dan Sonnet 5.5, ×0,025 untuk Fable 5.1/Mythos 5.1).
- Model yang dipakai pilot adalah **Sonnet 5.5**, bukan Opus; tabel bagian 0 perlu baris Sonnet (di atas).

### 9b. Bagaimana usage dilaporkan (hitung ganda)

- API mentah: `input_tokens` = sisa yang **tidak** di-cache; `cache_creation_input_tokens` dan `cache_read_input_tokens` terpisah; total prompt =
  ketiganya dijumlah. `usage.cache_creation` merinci per TTL (`ephemeral_5m_input_tokens`, `ephemeral_1h_input_tokens`).
- `langchain_anthropic` 1.7.6 (yang terpasang di VM, `anthropic` 1.13.0), `_create_usage_metadata`: `usage_metadata.input_tokens` =
  `input_tokens + cache_read + cache_creation` (**termasuk** keduanya). `input_token_details` berisi `cache_read`, `cache_creation`, dan bila API
  memberi rincian TTL, `ephemeral_5m_input_tokens` / `ephemeral_1h_input_tokens` **dengan `cache_creation` di-set 0** supaya tidak terhitung dua kali.
- **Akibat untuk kode sekarang:** `models/registry.usage_from_message` hanya mengambil `cache_read`, dan `cost_usd` menghitung
  `fresh = input_tokens − cache_read`. Token yang ditulis ke cache tertagih sebagai input biasa (kurang 25% untuk write 5m). Tes 7 harus memakai
  kedua bentuk detail (generik `cache_creation`, dan rincian TTL dengan generik 0).

### 9c. Hal lain dari dokumentasi caching

- Maksimal 4 breakpoint; minimum prefix yang bisa di-cache 512 token untuk Opus 5.5/Sonnet 5.5/Haiku 5.5 (prompt sistem + skema alat coder sudah
  ±3.000 token). Di bawah minimum: tidak error, `cache_creation_input_tokens` 0.
- TTL dihitung dari **awal** request yang menulis/membaca; read menyegarkan timer tanpa biaya. Jeda antar panggilan coder (termasuk validasi
  otomatis ±38 detik) jauh di bawah 5 menit, sesuai bagian 1.
- Lookback 20 blok: satu giliran yang menambah lebih dari 20 posisi bisa membuat entri sebelumnya tidak terbaca (rangkaian tool_use dan tool_result
  masing-masing dihitung satu posisi). Di `pilot3a4` giliran terbesar 6 tool call; aman, tetapi dicatat.
- `langchain_anthropic` mendukung `cache_control` pada blok konten (termasuk memindahkannya ke `tool_result`) dan parameter `cache_control`
  tingkat atas (penempatan otomatis). Bagian 5 memakai penanda eksplisit; mana yang dipakai diputuskan saat implementasi, dengan tes 5.

## 10. Keputusan yang diminta

1. **K1:** `config.yaml` dibetulkan: Sonnet 5.5 `cache_read` 0,20 → **0,10**; ditambah `cache_write_5m` untuk Opus 5.5 (5,00), Sonnet 5.5 (2,50),
   Haiku 5.5 (0,125), dengan tanggal pengecekan 2026-10-22. Perubahan `cache_read` Sonnet masuk PR D5 (kode uang, ikut tes dan mutan).
2. **K2:** tarif konteks panjang Haiku 5.5: tetap tidak dimodelkan, tetapi **ConfigError** bila caching menyala untuk role ber-model Haiku 5.5
   yang estimasi/batas masukannya bisa melewati 100.000 (sekarang tidak ada role seperti itu); atau caching untuk Haiku tetap off di D5. Usul:
   off untuk Haiku di D5 (pilot memakai Sonnet).
3. **K3:** bagian 4 "field tidak dilaporkan → `null`": untuk provider yang tidak punya konsep cache write (DeepSeek), `cache_creation` = `null`;
   untuk Anthropic dengan caching mati, API melaporkan 0, dicatat 0.

## 11. Keputusan (Atha/GPT, 2026-10-22)

1. **K1:** disetujui, masuk PR implementasi. `fresh = input_tokens − cache_read − cache_write` (LangChain `input_tokens` sudah termasuk keduanya).
   Kedua kesalahan belum pernah berdampak (selama caching mati, read dan write selalu 0), tetapi harus beres sebelum caching dinyalakan.
2. **K2:** caching Haiku 5.5 mati di D5, **ditambah** cek config yang berlaku selalu (tidak bergantung pada caching): role ber-model Haiku 5.5
   dengan batas masukan per panggilan di atas 100.000 → `ConfigError` (tarif ×5 berlaku juga untuk input biasa). Satu tes, satu mutan.
3. **K3:** disetujui (`null` bila provider tidak mengenal cache write, `0` bila Anthropic melaporkan 0). **Tambahan untuk tes 7:** D5 hanya meminta
   TTL 5 menit; `ephemeral_1h_input_tokens > 0` berarti ada yang salah di request. Token itu dihargai dengan tarif write 1 jam (kasus terburuk) dan
   dicatat sebagai event peringatan, tidak dihargai tarif 5 menit diam-diam.
