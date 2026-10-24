# Router pilot #3 (`intake_repo --check` task record): hasil

2026-10-24, job `j20261024_031449_052d`, DeepSeek V4.1 Flash thinking, `--no-reference`, dari VM dengan `--key-file` dan
`--yes`. Kriteria: `PREFLIGHT.md` (ditulis sebelum run). Artefak: `live/`.

## Hasil: gagal (kriteria 3), agen kehabisan konteks sebelum menulis apa pun

| Tahap | Hasil | Biaya | Waktu (UTC) |
|---|---|---|---|
| Drafter | `DRAFTED`, 2 submit, 15 panggilan | $0,0218 | 03:14:49 → 03:16:35 |
| Approve | Atha ("y", setelah ringkasan Claude) | – | 03:55:11 |
| Agen | `FAILED_ACCEPTANCE` (stagnant, 2 attempt), 11 panggilan | $0,0092 | 03:55:21 → 03:56:03 |
| **Job** | **AGENT_FAILED** | **$0,0310** dari cap $1,00 | 41 menit (38 menit di antaranya review draf) |

Kriteria 1 (drafter), 2 (approve), dan 4 (alur VM) terpenuhi. Kriteria 3 gagal. Sesuai preflight: dicatat, berhenti.
Langkah yang diminta Atha setelah apply (skrip repro dengan git asli sebelum `verify.sh`) **tidak dijalankan**: tidak
ada patch.

## Yang berjalan benar

- **Alur VM (kriteria 4).** `argus code` dan `argus approve` jalan dari sesi Claude tanpa terminal. Layar batas tetap
  dicetak. Key tidak pernah dibaca atau ditampilkan oleh Claude; cek isi key di berkas job diserahkan ke Atha (lihat
  bawah).
- **Log keputusan (#185).** Per tahap tercatat `limits_shown`, `confirmed_by_flag`, `key_from_file`, tanpa `confirmed`
  atau `key_typed`, sesuai ekspektasi. `approved` tercatat 10 detik setelah layar approve, yaitu waktu `dr.check`.
- **`status` yang baru cukup tanpa membuka berkas:** `why: stagnant: ...`, `agent result: FAILED_ACCEPTANCE, 2
  attempt(s), failing: artifact:SUMMARY.json, claims, validation:target`, dan `next: argus abandon ...`. Penyebab
  sebenarnya (konteks habis) tetap perlu `result.json` dan `events.jsonl`; lihat usul 2.
- **Draf (kriteria 1).** 5 node wajib merah karena assertion, 6 tes negatif hijau di baseline (`modify`, `add`,
  `remove`, isi tes yang berbeda dari hash, record `kind` kosong/`intake`), writable hanya `acceptance/intake.py`.
  `FakeGit` (sandbox tanpa git) cocok dengan parser `tree_entries`/`write_tree`. Di dua attempt agen, 11 tes jalan, 5
  gagal, 6 lulus: baseline yang sama.
- **Harness menolak dengan benar:** panggilan yang melebihi `max_input_tokens` ditolak sebelum dikirim
  (`llm_call` `refused`, `input_limit`), tanpa biaya.

## Kenapa gagal

Agen (profil `large_usd`: `max_input_tokens` 40.000) **tidak mengubah satu berkas pun** di kedua attempt (diff kosong).
Setiap attempt hanya membaca, lalu panggilan berikutnya ditolak karena konteks penuh (`attempt_end: context_limit`):

- attempt 1 (6 langkah): `acceptance/intake.py`, tes baru, `acceptance/workspace.py`, `tests/test_intake.py`,
  `acceptance/changed.py`, `scripts/intake_repo.py`, `fixtures/intake/argus_p7.json`, `codetask/run.py`,
  `scripts/approve_draft.py`, plus satu `run_validation`. Ditolak pada est. 41.034 > 40.000;
- attempt 2 (5 langkah): hal yang sama, plus `acceptance/draft.py` (27 KB) dan `codetask/run.py`. Ditolak pada est.
  44.771.

Perbaikannya kira-kira 10 baris di satu fungsi yang sudah dibaca agen di langkah pertama. Berkas yang dibaca sesudahnya
(`codetask/run.py`, `approve_draft.py`, `draft.py`) tidak diperlukan. Ini kegagalan **perilaku model** (membaca terlalu
lebar), yang dibatasi oleh **perkiraan token**: perkiraan heuristik untuk DeepSeek sekitar 1,4× token sebenarnya (est.
39.306 vs 27.658 di panggilan terakhir yang dikirim), jadi batas efektifnya sekitar 28.000 token sebenarnya.

Pola yang sama juga ada di W2b-3 run 1 (attempt terakhir berakhir `context_limit`), tapi di sana tesnya memang mustahil
dipenuhi, jadi tidak kelihatan sebagai penyebab.

## Supervisi

- Keputusan Atha: **2 di chat untuk run** (go live `code`, "y" `approve`), ditambah preflight (review PR #186). Belum ada
  apply dan merge karena gagal. Log `job.json` mencatat 2 `confirmed_by_flag`.
- Waktu: tahap mesin ±2,5 menit. 38 menit antara draf siap dan approve: ringkasan Claude, lalu Atha membaca.
- Menit Atha: belum ditanyakan.

## Usul (belum dikerjakan, keputusan Atha)

1. **Ulang agen dalam job yang sama** (celah 6 router). Drafnya bagus dan sudah di-approve, tapi router hanya
   menawarkan `abandon`. Mengulang sekarang berarti job baru, drafter baru ($0,02), dan review ulang draf (38 menit di
   pilot ini). Pilot ini bukti pertama bahwa celah itu mahal **dalam waktu manusia**, bukan uang.
2. **Alasan agen berhenti di `status`:** `attempt end: context_limit` (dari `result.json`), supaya penyebabnya terlihat
   tanpa membuka `events.jsonl`.
3. **Konteks agen:** naikkan `max_input_tokens` profil `large_usd` (mis. 64.000; harga DeepSeek kecil), dan/atau
   petunjuk di prompt coder untuk membaca hanya berkas yang perlu diubah dan tesnya sebelum menulis. Opsi pertama lebih
   kecil dan bisa diukur.

## Cek key (kriteria 4, dijalankan Atha)

```bash
grep -rlF -f ~/.config/argus/deepseek_key ~/pilot3a_live/jobs/j20261024_031449_052d | wc -l
```

Harus `0`. Hasil: _belum diisi_.
