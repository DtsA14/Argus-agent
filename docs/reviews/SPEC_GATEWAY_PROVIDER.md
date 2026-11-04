# Spek: provider gateway (OpenRouter dulu, Vercel AI Gateway sesudahnya)

Status: **disetujui Atha 2026-11-04** ("Ikut saran lu bro": semua usul §10). Dasar: permintaan Atha 2026-11-04 ("butuh multi provider kalo multi agent gw
jalan, biar ga ribet masukin banyak API, dan lumayan suka ada gratisannya"), perbandingan Claude di chat hari yang sama
(OmniRoute ditolak; OpenRouter dan Vercel AI Gateway dipilih sebagai satu adapter).

Jalur ketat: provider model baru, uang (harga, cost yang dilaporkan gateway, model gratis), key baru, data keluar ke
pihak baru. AGENTS.md berlaku penuh: spek → tes yang gagal di kode lama → kode → mutants → `/code-review medium` +
`/security-review` → `verify.sh` di commit final → "merge" Atha. Run live pertama butuh "go live".

## 1. Kenapa, dan batasnya

Agen multi-role butuh model dari beberapa provider (mis. judge `nodes/judge.py` wajib beda provider dari penulis;
eval riset ingin membandingkan model). Sekarang setiap provider = satu key, satu kelas LangChain, satu baris harga.
Gateway memberi **satu key untuk banyak model**, dan OpenRouter punya **model gratis** (`:free`).

Yang dipertahankan, tanpa pengecualian: setiap panggilan lewat `LLMCaller`; reservasi (token dan USD) sebelum kirim;
model tanpa harga ditolak selama `max_usd` finite; ledger `llm_call_started` / `llm_call`; biaya yang tidak diketahui
`null`, bukan `0`; retry SDK mati (`max_retries=0`).

Yang **tidak** masuk: routing otomatis antar model atau provider (`auto`, `models: [...]` fallback, sort by price),
BYOK lewat gateway, streaming, embeddings, OmniRoute.

## 2. Bentuk di config

```yaml
providers:
  openrouter:
    kind: gateway
    vendor: openrouter                 # menentukan bentuk parameter pin (§3) dan pembacaan cost (§4)
    api_key_env: OPENROUTER_API_KEY
    base_url: https://openrouter.ai/api/v1
  vercel:                              # PR sesudahnya (§9), bentuknya sama
    kind: gateway
    vendor: vercel
    api_key_env: AI_GATEWAY_API_KEY
    base_url: https://ai-gateway.vercel.sh/v1

gateway_models:                        # hanya model di sini yang boleh dipakai lewat gateway
  "openrouter:deepseek/deepseek-chat":  {upstream: [deepseek], free: false}
  "openrouter:<id>:free":               {upstream: [<slug>], free: true}

prices:                                # wajib, seperti provider lain; model gratis ditulis 0 eksplisit
  "openrouter:deepseek/deepseek-chat":  {input: ..., output: ..., cache_read: ..., checked: "2026-11-..", source: "<url>"}
  "openrouter:<id>:free":               {input: 0, output: 0}

gateway:
  free_roles: []                       # role yang boleh memakai model free: true (default: tidak ada)
  free_repos: []                       # repo yang boleh dibaca model gratis (§5.1); default: tidak ada
  cost_drift_warn: 0.10                # selisih cost gateway vs hitungan kita yang dicatat sebagai price_drift
```

- Model ref: `openrouter:<id gateway>`; `ModelRef.parse` memisah di `:` pertama, jadi `:free` tetap bagian id model.
- Model yang tidak ada di `gateway_models` ditolak sebelum dikirim (`ConfigError`), juga lewat `--model role=...`.
- Kelas: `ChatOpenAI` dengan `base_url` vendor (kelas yang sama dengan `openai_compatible` yang sudah ada), parameter
  pin lewat `extra_body`.

## 3. Pin provider: tidak ada fallback diam-diam

Reservasi dihitung dari harga satu model di satu provider; gateway yang diam-diam pindah ke model atau provider lain
membuat harga itu salah. Karena itu setiap request membawa pin, dan request tanpa pin tidak bisa dibuat:

- **OpenRouter:** `extra_body.provider = {order: upstream, only: upstream, allow_fallbacks: false,
  require_parameters: true, data_collection: <§5>}`; tidak ada `models` (fallback model) dan tidak ada `sort`.
- **Vercel:** `providerOptions.gateway.only = upstream` per request (gratis; allowlist tingkat tim tidak dipakai), tanpa
  `models` fallback, tanpa BYOK (BYOK Vercel jatuh ke kredensial sistem saat gagal, §1).
- Nama provider yang melayani (bila respons memuatnya) dicatat di ledger (`upstream_served`); bila tercatat dan **tidak**
  ada di `upstream`, event `pin_violated` ditulis dan stage berhenti (`LLMCallFailed` yang tidak di-retry). Uangnya tetap
  dicatat (§4).
- Bentuk persis parameter Vercel lewat endpoint OpenAI-compatible diverifikasi di PR Vercel (§9); kalau pin tidak bisa
  dipasang lewat endpoint itu, vendor itu tidak diaktifkan.

## 4. Uang

- **Sebelum kirim:** sama persis dengan provider lain. Harga dari `prices`, worst case (input + output cap) harus muat di
  reservasi. Token dihitung dengan **heuristik** (tidak ada counting API untuk gateway), termasuk untuk model Anthropic
  lewat gateway; aturan AGENTS.md berlaku: tidak disebut cap finansial absolut.
- **Sesudah kirim:** OpenRouter mengembalikan `usage.cost` (kredit = USD) di setiap respons. Yang di-charge:
  **`max(hitungan kita dari token × harga config, cost gateway)`**; keduanya dicatat (`usd_nano` = yang di-charge,
  `usd_reported_nano`, `usd_computed_nano`). Alasan: kalau gateway lebih mahal (harga berubah, peak DeepSeek, cache
  tidak tercatat), ledger mengikuti tagihan nyata; kalau gateway lebih murah, kita tetap konservatif. Selisih >
  `cost_drift_warn` → event `price_drift` (tidak menghentikan stage; ditampilkan di `status` dan audit supaya harga
  config diperbarui).
- Cost gateway tidak ada atau rusak → hitungan kita saja (seperti sekarang), `usd_reported_nano: null`.
- Fee beli kredit OpenRouter (~5,5% menurut satu sumber, belum dicek di halaman harga resmi) **tidak** masuk ledger per
  panggilan; dicatat di `docs/` sebagai biaya saldo. Rekonsiliasi bulanan pakai dashboard gateway
  (seperti rekonsiliasi ledger vs console DeepSeek Oktober).
- **Model gratis:** harga `0` eksplisit = biaya diketahui nol (beda dengan `null`). Tetap lewat reservasi (token),
  tetap tercatat di ledger dengan `free: true`. Kalau gateway melaporkan cost > 0 untuk model gratis → `price_drift` dan
  di-charge (aturan max di atas).
- Saldo gateway habis (HTTP 402) = error provider pasti, tidak di-retry, stage BLOCKED.

## 5. Data dan model gratis

- Model gratis di OpenRouter sering dilayani provider yang menyimpan atau melatih pakai prompt. Karena itu:
  - `free: true` hanya boleh di role yang ada di `gateway.free_roles` (default kosong; Atha yang mengisi), dicek sebelum
    kirim; role lain → ditolak dengan pesan yang menyebut alasannya.
  - Model berbayar dikirim dengan `data_collection: "deny"`; model gratis dengan `"allow"` (kalau tidak, umumnya tidak
    ada provider yang mau melayani) dan layar konfirmasi "go live" menyebut "prompt ke model gratis bisa disimpan atau
    dipakai training oleh provider-nya".
  - Model gratis untuk riset publik dan eksperimen eval; role yang membaca repo diatur §5.1.
- Rate limit model gratis OpenRouter: 20 request/menit; 50/hari (kredit dibeli < $10) atau 1000/hari (≥ $10). HTTP 429
  di-retry sesuai `retry` + `Retry-After` yang ada; kalau tetap 429 → `LLMCallFailed` → stage BLOCKED. **Tidak pernah**
  pindah otomatis ke model berbayar.

### 5.1 Model gratis dan repo (Atha 2026-11-04)

Model gratis yang membaca repo mengirim isi repo ke provider yang boleh menyimpan atau melatih: rahasia yang terselip
(`.env`, key di fixture atau di git history, path dan user VM), kode yang belum publik, dan data di repo (mis. ledger di
`argus-ledger`). Yang sudah terkirim tidak bisa ditarik. Karena itu:

- **Default:** role yang membaca repo (coder, drafter, researcher r1, dan role baru yang diberi tool file) **tidak**
  memakai model gratis.
- **Dibuka per repo:** repo boleh dibaca model gratis hanya bila (a) ada di `gateway.free_repos` (Atha yang mengisi),
  dan (b) ada catatan scan rahasia yang **lolos untuk commit persis** yang akan dibaca (working tree dan seluruh git
  history), pola `scripts/check_env_image.py` (catatan per image). Commit lain, atau working tree yang kotor → ditolak
  sebelum stage mulai, dengan pesan yang menyebut cara menjalankan scan.
- Scan: `scripts/check_secrets.py` (PR 1) menjalankan pemindai rahasia (alat dipilih di PR 1, mis. `gitleaks` dengan
  versi dipin; kalau tidak ada, pola regex sendiri untuk key yang dikenal + file `.env*`) dan menulis catatan
  `{repo, commit, tool, version, findings: 0}`. Temuan > 0 → tidak ada catatan lolos; temuan diperbaiki di repo, bukan
  di-allowlist diam-diam (allowlist eksplisit per temuan boleh, ikut di-commit dan di-review).
- Usul awal: hanya `Argus-agent` (repo publik) yang dikandidatkan, setelah scan pertama lolos. `argus-ledger` (lokal,
  berisi data ledger) dan repo kerjaan atau klien tidak.

## 6. Key

- Satu key per gateway (`OPENROUTER_API_KEY`, nanti `AI_GATEWAY_API_KEY`), diambil lewat `--key-file` atau terminal
  seperti provider lain (`router/job.py` `_needs_key` sudah membaca `api_key_env` per provider). Tidak pernah masuk
  prompt, log, ledger, memo, atau `job.json` (tes yang sama dengan PR A riset).
- Saran operasional (bukan kode): buat key OpenRouter dengan **credit limit** di dashboard-nya, sebagai batas kedua di
  luar Argus.

## 7. Model DeepSeek thinking lewat gateway

DeepSeek dalam mode thinking + tool wajib menerima `reasoning_content` balasan sebelumnya (`ArgusChatDeepSeek`).
Gateway memakai bentuk lain (`reasoning` / `reasoning_details` di OpenRouter). v0: model lewat gateway dipakai **tanpa
thinking** sampai smoke §9 membuktikan loop tool dengan thinking jalan; DeepSeek langsung tetap jalur utama.

## 8. Tes (masing-masing harus gagal bila jaminannya dirusak; mutants)

Server HTTP palsu (lokal) meniru endpoint chat completions vendor:

1. Pin: setiap request membawa `provider.only/order = upstream`, `allow_fallbacks: false`, tanpa `models`/`sort`;
   model di luar `gateway_models` ditolak sebelum kirim (server tidak menerima apa pun).
2. Uang: cost gateway > hitungan → yang di-charge cost gateway; < hitungan → hitungan; tidak ada → hitungan dan
   `usd_reported_nano: null`; selisih > ambang → `price_drift`; model tanpa harga + cap finite → ditolak; 402 → tidak
   di-retry, BLOCKED; crash di antara started dan akhir → worst case (aturan yang sudah ada, untuk provider ini).
3. Gratis: role di luar `free_roles` ditolak sebelum kirim; role yang membaca repo dengan model gratis ditolak bila
   repo tidak di `free_repos`, tidak ada catatan scan untuk commit itu, catatannya untuk commit lain, atau working tree
   kotor; scan dengan temuan tidak menghasilkan catatan lolos; 429 berulang → BLOCKED, tidak ada request ke model lain;
   model gratis tercatat `free: true`, `usd_nano: 0`; cost > 0 dari gateway untuk model gratis → di-charge.
4. Pin dilanggar: respons menyebut provider di luar `upstream` → `pin_violated`, stage berhenti, uang tercatat.
5. Key: tidak muncul di ledger, log, memo, `job.json`; tanpa key → refused sebelum konfirmasi selesai, tidak ada request.
6. `max_retries=0` juga untuk kind `gateway`.

## 9. Urutan PR

1. **PR 1 (jalur ketat):** kind `gateway` vendor `openrouter`, `gateway_models`, pin, cost max, free_roles, tes §8.
   Belum ada role yang memakainya di config default.
   Implementasi (2026-11-04): PR 1 menolak model gratis di **setiap** role yang membaca repo (lebih ketat dari §5.1);
   `free_repos` + `scripts/check_secrets.py` menyusul di PR 1b, hanya bila dibutuhkan (role eksperimen `research_free`
   tidak membaca repo). Tool yang dihitung "membaca repo": list_files, search_files, read_file, write_file,
   run_validation, read_docs.
1c. **PR 2 (jalur ketat, 2026-11-04), syarat smoke:**
   - `research_job.profiles` (role per stage: planner, worker, synthesis, checker), dipilih per job dengan
     `argus research --profile NAME` dan dicatat di `job.json` (resume memakai role yang sama). Profil: `deepseek`
     (default, seperti sebelumnya), `free` (p1/s1 `nvidia/nemotron-3-ultra-550b-a55b:free`, worker
     `nvidia/nemotron-3.5-super-vl:free` (Inkling diganti 2026-11-04: versi gratisnya hanya untuk aplikasi yang terdaftar di OpenRouter, HTTP 403 di smoke), e1 `google/gemma-4-31b-it:free`), `deepinfra` (DeepSeek V4.1 Flash lewat
     OpenRouter).
   - `gateway.free_roles` = `free_planner`, `free_worker`, `free_checker` (pengganti satu role `research_free`, karena
     tiap stage memakai model lain), tanpa tool sendiri.
   - DeepSeek **tidak** melayani DeepSeek V4.1 Flash di OpenRouter (cek endpoints 2026-11-04); pembandingnya dipin ke
     DeepInfra fp8 ($0,14/$0,42 per 1M, tanpa peak).
   - Key: worker tetap butuh key DeepSeek untuk web, jadi satu stage bisa butuh dua key. `--key-file` bisa diulang
     sebagai `--key-file PROVIDER=PATH` (bentuk satu PATH tetap untuk satu key); file harus pas dengan provider yang
     butuh key (kurang atau lebih → ditolak); key OpenRouter dicek berawalan `sk-or-v1-` (`providers.*.key_prefix`).
   - Preflight sebelum konfirmasi: tiap model stage berharga dan boleh untuk role-nya (aturan model gratis).
1d. **Fallback model gratis (Atha 2026-11-04, sesudah smoke: Gemma 4 31B gratis kena HTTP 429 dari Google):**
   `roles.<role>.fallback_models`, hanya untuk role bermodel gratis dan hanya berisi model gratis di `gateway_models`
   (masing-masing dengan pin sendiri); tidak pernah model berbayar, dan model berbayar tidak punya fallback. Pindah hanya
   bila model sebelumnya kena 429 (sesudah retry LLMCaller) sebelum balasan pertama loop stage itu (step 0); model yang
   dipakai di-commit ke memo sebelum panggilan pertamanya, jadi resume melanjutkan di model itu. Event `model_fallback`
   di ledger. Ini bukan routing otomatis OpenRouter: rantainya ditulis di config dan diperiksa preflight.
2. **Smoke live (butuh "go live", ≤ $0,10):** satu panggilan + satu loop tool kecil ke 2–3 model terpilih (§10 no. 4),
   membandingkan cost gateway dengan hitungan kita dan memeriksa pin. Hasilnya menentukan harga di config.
3. **Eksperimen:** satu stage riset (worker atau s1) memakai model gateway, dibandingkan dengan DeepSeek langsung di
   eval riset v0.
4. **PR Vercel:** vendor `vercel` setelah bentuk pin per request diverifikasi.

## 10. Pertanyaan untuk Atha

1. **Vendor pertama OpenRouter** (gratisan, katalog terluas, cost ada di respons), Vercel sesudahnya — setuju?
2. **Charge = max(hitungan kita, cost gateway)** — setuju? (Alternatif: percaya cost gateway saja; lebih tepat, tapi
   kalau gateway salah lapor ke bawah, reservasi kita ikut longgar.)
3. **Model gratis** hanya di role yang Atha daftarkan di `gateway.free_roles`, default kosong; role yang membaca repo
   hanya untuk repo di `free_repos` dengan scan rahasia lolos (§5.1, disetujui Atha 2026-11-04). Role mana yang mau
   langsung didaftarkan (mis. role baru `research_free` untuk eksperimen)?
4. **Model awal** untuk smoke: usul (a) DeepSeek lewat OpenRouter dipin ke DeepSeek (pembanding harga), (b) satu model
   murah dari provider lain (mis. Gemini Flash) untuk judge/eksperimen, (c) satu model `:free`. Id persisnya dipilih dan
   harganya dicek dari halaman model saat PR 1.
5. **Top-up $10 di OpenRouter** supaya batas model gratis 1000/hari (bukan 50) dan pasang credit limit di key-nya —
   ini tindakan Atha di dashboard OpenRouter.

**Jawaban Atha 2026-11-04 ("Ikut saran lu bro"):** 1 OpenRouter dulu, Vercel sesudahnya; 2 charge = max(hitungan kita,
cost gateway); 3 `free_roles: [research_free]` (role baru untuk eksperimen riset, tanpa tool file), `free_repos` kosong
sampai scan Argus-agent lolos (kandidat: Argus-agent saja); 4 smoke: DeepSeek lewat OpenRouter dipin ke DeepSeek, satu
model murah provider lain (Gemini Flash), satu model `:free`; 5 top-up $10 + credit limit di key OpenRouter (tindakan
Atha di dashboard, sebelum smoke).
