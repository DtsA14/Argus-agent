# Pilot e1_effort v0: claim checker e1 dengan `reasoning.effort: low` (2026-11-06)

Butir PENDING tahap 1 (eksperimen e1 `reasoning.effort: low`), jalur cepat (Atha "#1 dan #2 jalur cepat"). Laporan sama,
e1 diulang: salinan job di `~/e1_jobs` (`build_jobs.py`: state CHECKING, stage e1 dan `check.json` dibuang, lalu
`argus resume`). Lengan **def** = config sekarang (`or_deepseek_checker`, DeepSeek V4.1 Flash lewat OpenRouter/DeepInfra,
tanpa param reasoning); lengan **low** = config salinan yang sama dengan `params: {extra_body: {reasoning: {effort: low}}}`.

Dua laporan dengan nilai Claude (`docs/Reconciliation.md` bagian 4d):
- **A** `j20261105_121107_718e` (Agentic AI, job 3): e1 asli 8 SUPPORTED / 9 PARTIAL; Claude mencocokkan alasan PARTIAL
  dengan sumber (nama di laporan yang tidak ada di kutipan mana pun): **e1 asli benar**, jadi verdict asli = rujukan.
- **B** `j20261105_125836_ebbd` (ekonomi): e1 asli 11 SUPPORTED / 2 PARTIAL; Claude: semua angka ada di kutipan, PARTIAL
  = salah rujuk.

## Hasil

| laporan | lengan | sama dengan rujukan | reasoning tokens | waktu | biaya |
|---|---|---|---|---|---|
| A (17 item) | asli | 17/17 | 26.230 | 167 s | - |
| A | def ulang | **12/17** (5 PARTIAL → SUPPORTED: S, P2, P7, P11, P12) | 27.296 (+10 submit ke-2) | 188 s | $0,0145 |
| A | **low** | **17/17** | 12.493 | 83 s | $0,0071 |
| B (13 item) | asli | 13/13 | 7.514 | 63 s | - |
| B | def ulang | 13/13 | 6.172 | 39 s | $0,0042 |
| B | **low** | 13/13 | 3.700 | 27 s | $0,0033 |

Total biaya pilot $0,0291.

## Bacaan (n = 1 per lengan per laporan)

- `effort: low` dihormati sebagian: reasoning turun ±50% (A) dan ±40% (B), bukan ke angka kecil. Biaya dan waktu turun
  hampir separuh.
- Ketepatan tidak turun: low sama dengan rujukan di kedua laporan (30/30). Lengan def yang diulang justru lebih longgar di
  A (5 item yang Claude nilai PARTIAL dengan benar jadi SUPPORTED): variasi antar-run e1 default sendiri besar, sama
  dengan catatan PENDING "e1 lebih longgar saat berbeda".
- Usul Claude (keputusan Atha): pakai `reasoning: {effort: low}` di `or_deepseek_checker` (jalur cepat, satu baris
  config). Satu run per lengan belum cukup untuk menyebut low **lebih** tepat; yang cukup didukung: tidak lebih buruk,
  separuh harga dan waktu.
