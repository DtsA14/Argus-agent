# argus-ledger issue 014 (keputusan manusia per job): job Argus → staging

2026-10-30. Issue ditulis Claude (`~/argus-ledger-issues/014-human-decisions.txt`). Jalur cepat: "go live" Atha untuk
job, Claude approve dan apply; deploy lewat `PLAN.md` dengan "go live" kedua. Model DeepSeek V4.1 Flash (thinking), jam
peak (2×).

## Job `j20261030_060939_8433` (06:09–06:13 UTC)

| tahap | hasil | biaya |
|---|---|---|
| d1 drafter | DRAFTED, 1 submit, 17 panggilan; 8 tes baru merah karena assertion; mengubah `tests/test_api.py` hanya dengan `"decisions"` di dict yang dibandingkan persis | $0,0557 |
| a1 agen | DONE di attempt pertama, 24 langkah | $0,0242 |
| **total** | `applied` apa adanya: argus-ledger **`1f31e34`** (tidak ditulis ulang) | **$0,0800** |

Review Claude: semantik keputusan sesuai issue (state ke DRAFTING, `note`, `what` angka, `<script>` bukan keputusan;
nilai disalin, null → sel kosong, HTML di-escape); seluruh suite **133 passed** di stack up1 dengan
`-W error::DeprecationWarning`; di snapshot data asli 55 job, 217 keputusan (013: 6).

Catatan issue: "existing tests keep passing unchanged" bertentangan dengan menambah key ke `/jobs` (tes lama
membandingkan dict persis); drafter benar mengubah tes lama secukupnya. Issue berikutnya: sebut bahwa tes yang
membandingkan bentuk JSON persis boleh ditambah key baru.

## Deploy (06:21 UTC), `PLAN.md` 6/6 sesuai harapan

`stage check` 133 lolos → deploy `j20261030_060939_8433-1f31e34c1ff2.up1` (smoke angka asli: 55 job, 4.256.800.452
nano) → `/jobs` lewat socket (peer = pid container): setiap job punya `decisions` → monitor `ok` → status. Isolasi
`docker inspect` dan `/data` = `pub` read-only seperti sebelumnya; satu container; port 8000 tidak disentuh. Rollback →
013 `.up1`.

## Ukuran

Merged without rewrite: ya. Biaya per fitur: $0,0800. Keputusan Atha: 2 ("go live" job, "go live" deploy); keputusan
Claude: approve draf, apply. Waktu: job 4 menit, deploy < 1 menit.
