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

## Run 2: `argus retry` (tahap `a2`, setelah PR #187/#188): berhasil

2026-10-24, job yang sama, tanpa drafter baru dan tanpa review draf ulang. Preflight di chat: cap `min($0,75, $0,969)` =
$0,75, layar batas menyebut `a1 ended: context_limit after 5 steps, no file changed`, max input 60.000.

| Tahap | Hasil | Biaya | Waktu (UTC) |
|---|---|---|---|
| Retry | Atha ("y", setelah preflight) | – | 11:05:10 |
| Agen `a2` | `DONE`, 1 attempt, 6 panggilan | $0,0039 | 11:05:10 → 11:05:58 |
| **Job** | **REVIEW_READY** | **$0,0349** dari cap $1,00 | |

- **Agen menulis sebelum konteks penuh.** Attempt 1 `a2` membaca 3 berkas (`acceptance/intake.py`, tes baru,
  `acceptance/workspace.py`) dan satu `list_files`, lalu `edit_file` di langkah 3, dua `run_validation`, `Finish` di
  langkah 5. Di `a1` setiap attempt membaca 8–9 berkas tanpa menulis.
- **Peringatan 70% tidak muncul**: input terbesar est. 19.671, di bawah 42.000 (70% dari 60.000) dan juga di bawah
  batas lama 40.000. Jadi `a2` berhasil **bukan karena batasnya naik**. Bedanya ada di prompt: carry (`a1` berhenti
  `context_limit` tanpa menulis) dan petunjuk "read only what the change needs, then write it: ... acceptance/intake.py".
  Satu run tidak cukup untuk memisahkan efek petunjuk dari variasi model.
- **Carry** tercatat (`carried_feedback` di events, `carry` di `job.json`). Isinya tanpa daftar berkas yang dibaca,
  karena `a1` berjalan sebelum #188 (sesuai spek untuk run lama).
- **Patch** (`live/a2_changes.patch`, sha256 `cd136666…`, sama dengan yang dicetak `status`): fungsi baru
  `approved_tests(record)` dan `expected = {**tree, **approved_tests(record)}`. Diterapkan tanpa perubahan ke branch dari
  `main` di `~/Argus-agent` (bukan di checkout live, saran Atha): `apply --check` bersih, lalu `apply`.
- **Repro dengan git asli** (sebelum `verify.sh`, permintaan Atha): 7 kasus. Record intake → `[]`; record task persis
  seperti disetujui → `[]`; berkas lain diubah, berkas tambahan, tes yang disetujui diedit, tes `changed` kembali ke
  isi `before`, dan record intake pada workspace task → semuanya dilaporkan. Di kode `main` (sebelum patch), kasus
  "persis seperti disetujui" gagal: bug terbukti dan ditutup patch ini.
- **Temuan review diff (kecil):** untuk record task, perbandingan bit executable di `check_against_repo` mengabaikan
  berkas tes yang disetujui (`got = [p for p in got if p in tree]`). Issue meminta "executable bits are compared as
  now". Ini bukan celah: `intake.check` (dijalankan `intake_repo.py --check` dan setup) tetap membandingkan bit
  executable seluruh workspace dengan `record["executable"]`, jadi tes yang disetujui lalu dibuat executable tetap
  ketahuan. Tapi baris itu tidak diminta dan tidak dites. Dibiarkan seperti dari agen (patch diterapkan tanpa
  perubahan); bisa dihapus di PR terpisah bila Atha mau.

### Supervisi (seluruh pilot)

Keputusan Atha untuk run: go live (`code`), "y" (`approve`), "y" (`retry`) = **3**, plus review preflight, spek #187, dan
merge. Waktu mesin seluruh tahap ±3,5 menit; biaya $0,0349.

## Cek key (kriteria 4, dijalankan Atha)

```bash
grep -rlF -f ~/.config/argus/deepseek_key ~/pilot3a_live/jobs/j20261024_031449_052d | wc -l
```

Harus `0`. Hasil: **belum dicek manual** (Atha, 2026-10-24: skip dulu; dijalankan nanti dari PC). Sampai saat itu
kriteria 4 bertumpu pada tes router (key tidak tertulis di berkas job mana pun, key diketik maupun `--key-file`).
