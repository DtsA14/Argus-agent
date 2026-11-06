# Spek: retry 429 dengan jeda panjang (dan 429 gateway tidak ditagih)

Status: **disetujui Atha 2026-11-06 ("Setuju gas bro"): K1-K3 ya.** Jalur ketat (`harness/llm.py`: retry, ledger, reservasi). Satu PR. Lanjutan
`PENDING.md` (tahap 2, item 429 Baidu) dan `SPEC_JUDGE.md` bagian 6.

## 1. Masalah

`argus judge` (GLM-5.3 lewat OpenRouter, pin Baidu fp8) kehilangan banyak stage karena 429 dari upstream
("z-ai/glm-5.3 is temporarily rate-limited upstream"):

- Replay putaran 2 percobaan 2: 7 dari 11 stage NOT_JUDGED, semuanya 3x 429.
- Uji cacat tanam: 3 dari 10 stage NOT_JUDGED; `81ed` kena 429 di ketiga stage (9 panggilan).
- Dengan jeda 150 s **antar job** (skrip Claude), replay j2 dan shadow batch 3: 0 dari 11 stage gagal.

Dua penyebab di `LLMCaller.call`:

1. **Jeda terlalu pendek.** `llm.attempts: 3`, `llm.base_delay: 1.0`: jeda 0,5-1,5 s lalu 1-3 s (OpenRouter tidak
   mengirim `Retry-After`). Ketiga percobaan jatuh di gelombang rate limit yang sama.
2. **Setiap 429 ditagih worst-case** (`failed_attempt_charge: worst_case`, `delivery: received`): satu 429 judge
   ±$0,033, jadi tiga 429 menghabiskan cap stage $0,10 tanpa satu token pun dibeli. Ledger replay putaran 2 mencatat
   $0,78 untuk biaya riil ±$0,09. Model `:free` lewat gateway sudah dikecualikan (429 = 0), model berbayar belum.

## 2. Usul

**R1. Jeda khusus 429.** Bila error transient berstatus HTTP 429, jedanya
`llm.rate_limit_delay_s * 2 ** (attempt - 1) * (0.5 + random())`, dibatasi `llm.rate_limit_max_delay_s`. Default 30 dan
120: ±15-45 s, ±30-90 s, ±60-120 s. `Retry-After` tetap menang bila ada, juga dibatasi `rate_limit_max_delay_s`. Error
transient lain (408/409/425/5xx, timeout) tetap memakai `base_delay` seperti sekarang.

**R2. Percobaan untuk 429.** `llm.rate_limit_attempts` (default 4) berlaku bila error percobaan terakhir adalah 429;
error lain tetap `llm.attempts` (3). Batas keseluruhan per panggilan = maksimum keduanya; tidak ada loop tanpa batas.
Total tunggu terburuk per panggilan ±4 menit.

**R3. 429 dari gateway tidak ditagih** (K1). Panggilan lewat provider `kind: gateway` (OpenRouter) yang dijawab HTTP 429
dicatat `charged: none`, `usd_nano` 0, `tokens` 0, dengan `delivery: received` dan `http_status: 429` seperti sekarang;
reservasi tidak dikurangi. Ini memperluas aturan yang sudah ada untuk model `:free` ke model berbayar. Alasan: 429
berarti ditolak sebelum diproses, dan OpenRouter tidak menagih request yang gagal. Provider langsung (Anthropic,
DeepSeek, DeepInfra) **tidak berubah** (tetap worst-case), karena belum ada bukti tagihannya.

**R4. Tidak berubah:** `llm_call_started` sebelum setiap percobaan dan `llm_call` sesudahnya; reservasi dicek sebelum
setiap percobaan; memo, checkpoint `sync`, dan crash-resume tidak tersentuh (jeda hanya `self.sleep` yang sudah
disuntikkan); error non-transient tidak di-retry.

**Tidak dikerjakan:** circuit breaker antar job, antrean global, jeda antar job di harness, fallback provider (dicabut
#322), mengubah `failed_attempt_charge` untuk provider langsung.

## 3. Jaminan dan tes (`tests/test_rate_limit_retry.py`, tanpa sandbox, `sleep` palsu)

- **G1.** 429 tanpa `Retry-After`: jeda percobaan n berada di [0,5; 1,5] x 30 x 2^(n-1), dibatasi 120.
- **G2.** 429 dengan `Retry-After: 500`: jeda = 120 (dibatasi); `Retry-After: 7`: jeda 7.
- **G3.** 500/timeout: jeda tetap dari `base_delay` (tidak ikut 30 s).
- **G4.** 429 terus-menerus: tepat `rate_limit_attempts` percobaan lalu `LLMCallFailed`; 500 terus-menerus: tepat
  `attempts`.
- **G5.** 429 lewat gateway berbayar: `charged: none`, `usd_nano` 0, reservasi utuh, sehingga 4 percobaan muat di cap
  yang hanya cukup untuk satu worst-case.
- **G6.** 429 dari provider langsung: tetap worst-case (perilaku lama).
- **G7.** Urutan ledger per percobaan tetap `llm_call_started` lalu `llm_call`, juga untuk 429 yang tidak ditagih.
- **G8.** Config tidak valid (`rate_limit_delay_s` negatif, `rate_limit_attempts` < 1, `max` < `delay`): `ConfigError`
  sebelum apa pun dikirim.

Mutants (`verification/rate_limit_mutants.py`): jeda 429 memakai `base_delay`; batas 120 dibuang; `Retry-After` tidak
dibatasi; `rate_limit_attempts` diabaikan; 429 gateway tetap worst-case; 429 provider langsung jadi 0; 500 ikut jeda 30.

## 4. Keputusan untuk Atha

- **K1.** 429 dari OpenRouter (model berbayar) dicatat $0 (R3)? Usul: ya. Tanpa ini, R1-R2 tetap jalan, tetapi tiga 429
  masih menghabiskan cap judge $0,10 sebelum percobaan keempat, jadi R2 tidak berguna untuk judge.
- **K2.** Default 30 s / 120 s / 4 percobaan? Usul: ya. Judge menunggu paling lama ±4 menit; job `argus code` (DeepSeek
  langsung) jarang 429 dan ikut aturan yang sama.
- **K3.** Sesudah merge: ulang stage judge `81ed` (cacat tanam terakhir) sebagai bukti hidup (±$0,02, "go live")? Usul: ya.

## 5. Implementasi dan code review (medium, 10 finding)

Diperbaiki:
- **Penghitung terpisah.** 429 dan error transient lain dihitung sendiri-sendiri (`seen`), dan backoff 429 mulai dari
  jumlah 429 saja: 500, 500 lalu 429 menunggu ±30 s, bukan 120 s; 429, 429 lalu 500 masih punya dua retry 500. Batas
  loop = `attempts + rate_limit_attempts - 1`.
- **Model `:free` tetap cepat** (penyempitan R1-R2): rantai model gratis pindah ke model berikutnya lebih cepat daripada
  menunggu, jadi 429 di model `:free` tetap memakai `base_delay` dan `attempts` (tetap tidak ditagih seperti sebelumnya).
- **Error rate limit tanpa status** (nama kelas `RateLimit...`) ikut jeda panjang.
- **`Retry-After` negatif, NaN atau tak hingga** diabaikan (jeda dihitung sendiri); `inf`/NaN di config, `attempts` < 1
  dan `base_delay` negatif ditolak `ConfigError`.

Dibiarkan: 429 gateway berbayar $0 (K1, disetujui Atha); 429 provider langsung tetap worst-case sehingga empat
percobaan bisa menghabiskan reservasi (reservasi tetap dicek sebelum setiap percobaan; ReservationExhausted, bukan
pengiriman tanpa reservasi); duplikasi override di helper tes.
