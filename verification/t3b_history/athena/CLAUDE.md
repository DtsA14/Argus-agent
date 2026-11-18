# ATHENA — orientasi cepat

ATHENA adalah scanner momentum-trading buat saham IDX (Bursa Efek Indonesia),
dipakai lewat PWA React (FastAPI backend + frontend React/Vite) yang bisa diakses
dari HP. Dibangun buat trader yang tadinya feeling-based — tujuannya ngasih
disiplin lewat skor, confidence, dan
risk sizing yang konsisten, bukan gantiin keputusan trader dengan "sinyal beli/jual"
otomatis. Framing di seluruh sistem selalu "kandidat untuk review", bukan instruksi
eksekusi.

Kalau kamu sesi baru (manusia atau AI) yang baru buka proyek ini, baca file ini
duluan sebelum nyentuh kode.

## Peta modul

- `data_collection/fetcher.py` — fetch OHLCV dari yfinance (+ IHSG), data quality
  flag, cache lokal.
- `ta_engine/indicators.py` — indikator teknikal (RSI, MACD, MA, ATR, VWAP approx,
  volume profile).
- `market_regime/regime.py` — klasifikasi regime (trend/volatility) — dipakai
  dua kali dengan fungsi yang sama: sekali buat IHSG (market-wide), sekali per saham.
- `scoring/scoring_engine.py` — skor 0-100 dari 5 faktor berbobot (trend, breakout
  quality, relative strength, volume, sector strength), liquidity sebagai GATE
  (bukan faktor tertimbang). `market_regime` SENGAJA dibuang dari skor total
  (identik buat semua saham di hari yang sama, jadi nggak bantu ranking) — lihat
  PENDING #22 soal parameter yang masih nyisa tapi nggak kepake.
- `confidence/confidence_engine.py` — skor confidence, independen total dari skor
  (nggak menerima input skor sama sekali).
- `risk_management/risk_manager.py` — position sizing, stop/TP (tick-aware, IDX
  price floor Rp50), exposure check, daily loss limit. Modul yang paling langsung
  nyentuh uang beneran.
- `explainability/explainability_engine.py` — agregasi murni (data engineering),
  gabungin scoring + confidence + risk jadi satu penjelasan, dipanggil SEKALI di
  akhir pipeline.
- `decision_intelligence/decision_engine.py` — satu-satunya tempat skor + confidence
  digabung jadi kategori final (termasuk downgrade rule kalau confidence rendah).
- `journal/` — trade journal (executed & skipped records) + starred/bookmarked
  ticker.
- `portfolio/` — portfolio intelligence (cost-basis snapshot, exposure) + post-trade
  review (klasifikasi exit, termasuk bedain stop kena gap vs stop kena sesuai rencana).
- `dashboard/` — `dashboard_logic.py`, logic layer murni (testable, nggak
  bergantung ke framework UI apapun) yang dipakai `api/` (FastAPI backend buat
  PWA React). Dulu juga dipakai `app.py` (Streamlit) — itu sudah dihapus setelah
  PWA React punya paritas fitur penuh, `dashboard_logic.py` sendiri tetap jadi
  layer bersama yang aktif dipakai.
- `api/` — FastAPI backend (routes_scan/journal/holdings/starred/config), tipis,
  murni wiring HTTP ke `dashboard_logic.py` dkk.
- `frontend/` — PWA React/Vite, satu-satunya UI yang aktif dipakai sekarang.
- `setups/` — deteksi setup tambahan (compression/Wyckoff-style, breakout entry
  zone, ALKA warning untuk possibly_suspended/extreme_runup, support/resistance
  helper).
- `sector_data/` — `idx_sectors.py` (proxy list 11 sektor IDX-IC + ticker→sektor
  map), `holdings_sync.py` (import holding dari KYW).
- `scripts/` — manual e2e/smoke check scripts, plus `validate_*.py` dan
  `measure_*.py` — harness statistik walk-forward buat nguji ide sinyal baru
  (lihat VALIDATION.md).

## Prinsip desain inti

- **6 modul inti dianggap "beku" (frozen)**: `scoring/`, `confidence/`,
  `decision_intelligence/`, `risk_management/`, `market_regime/`, `explainability/`
  (plus `data_collection/fetcher.py` juga diperlakukan sensitif). Perubahan logic
  di modul-modul ini butuh persetujuan eksplisit — kalau suatu task ternyata butuh
  mengubah logic engine, STOP dan laporkan, jangan diam-diam dikerjakan. UI/dashboard
  boleh dikerjakan lebih bebas selama nggak nyentuh logic modul beku.
- **Disiplin validasi statistik buat ide sinyal baru**: setiap ide "faktor/sinyal
  baru" wajib diukur walk-forward (no-lookahead), edge dibandingkan ke ambang
  **2×SE**, dan yang dipercaya adalah statistik **date-clustered** (per-tanggal),
  BUKAN pooled. Alasannya: saham-saham IDX bergerak bareng (market-wide factor) —
  di hari IHSG jatuh/naik, ribuan event sebenarnya cuma segelintir hari yang saling
  "menyalin", jadi SE pooled menganggap event-event itu independen padahal bukan,
  dan hasilnya overstate confidence (beberapa "REAL EDGE" versi pooled hilang total
  jadi noise begitu dihitung ulang per-tanggal). Cek VALIDATION.md dulu sebelum
  mengajukan ide yang mirip dengan yang sudah pernah diuji dan ditolak.
- **No-lookahead / walk-forward**: semua pengukuran prediktif pakai data yang
  tersedia SEBELUM titik waktu yang diprediksi, nggak pernah "mengintip" masa depan
  buat nentuin sinyal hari ini.
- **"Explain, don't hide"** buat tampilan Risk & Sizing: Risk Management sengaja
  independen dari skor (nggak tau kategori Strong Buy/Avoid), jadi tetap ngasih
  ukuran posisi yang "meyakinkan" walau skornya jelek. Yang diperbaiki bukan
  logic-nya (itu desain yang benar), tapi TAMPILANNYA — dashboard & `display_text()`
  wajib kasih peringatan eksplisit kalau kategori Avoid/Neutral: angka sizing itu
  "seandainya kamu entry", bukan rekomendasi beneran. Prinsip yang sama berlaku di
  tempat lain: kalau ada limitation/asumsi/gap yang belum ditutup, catat eksplisit
  (di notes/docstring/warning), jangan didiamkan.

## Cara jalanin

```bash
pip install -r requirements.txt
python -m pytest tests/ -v                              # full test suite
python -m uvicorn api.main:app --host 0.0.0.0 --port 8000   # backend
npm --prefix frontend run dev -- --host                 # frontend, buka dari HP via IP LAN/Tailscale
```

⚠️ Backend dev server jalan **tanpa `--reload`** — tiap ubah kode backend,
restart manual (bukan cuma refresh browser). Endpoint baru yang balikin
404/405 padahal kode & tes udah bener = curiga proses lama, bukan bug (lihat
CHANGELOG "Gotcha: Method Not Allowed pas verifikasi live"). `--host
0.0.0.0` wajib kalau mau diakses dari HP/LAN/Tailscale, bukan cuma localhost.

## Pointer

- Histori lengkap pembangunan (per-Tahap, bug fixes, feature build): **CHANGELOG.md**
- Hasil studi validasi statistik — apa yang sudah diuji dan diterima/ditolak:
  **VALIDATION.md**
- Backlog aktif / task yang masih terbuka: **PENDING.md**
