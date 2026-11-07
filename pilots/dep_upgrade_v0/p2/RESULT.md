# Pilot dependency upgrade v0 #2: hasil (2026-11-07)

"go live" Atha 2026-11-07 ("go live kalo udah lulus verify"), sesudah verify.sh #302 PASS (`182f142`, 3077 passed, sandbox
skip 0). Dijalankan dari `~/pilot3a_live` di `fd4c633`, 15:44–15:46 UTC. Tanpa model, biaya model $0.

**Hasil: semua langkah 0–8 sesuai harapan, tidak ada penyimpangan.** Staging sekarang Stage 13 (argus-ledger `4e947a0`) di
atas starlette 1.10.0 + fastapi 0.162.0.

| # | langkah | hasil |
|---|---|---|
| 0 | status | live `.up1`, runtime `ledger_staging_up1`, monitor pass |
| 1 | check `ledger_py312_up2` | PASS, 137 tes (`-W error::DeprecationWarning`), image `3e48cd98c8de` |
| 2 | deploy `ledger_staging_up2` | live `.up2`, smoke pass; image `6d8fc5cc3639`; rollback → `.up1` |
| 3 | gzip | `/jobs.csv` 200 tanpa `Content-Encoding`; `/jobs` 200 `gzip` (sama seperti up1, Stage 13) |
| 4 | monitor | `ok: true` (viewer juga) |
| 5 | rollback | live `.up1`, smoke pass, image `4edca09d1842` (image up1 yang tercatat) |
| 6 | deploy up2 lagi | rilis `.up2` dipakai ulang (`src` dari langkah 2), check langkah 1 masih berlaku; smoke pass |
| 7 | gzip + monitor | sama dengan 3 dan 4 |
| 8 | status | live `.up2`, runtime `ledger_staging_up2`; rollback → `.up1` |

Setiap container: tepat satu `argus-staging-ledger-*`, `NetworkMode=none`, `ReadonlyRootfs=true`, `CapDrop=[ALL]`, user
`1001:1001`, `no-new-privileges`, `/data` = `~/argus-staging/data/pub` read-only, image seperti tertulis.

Bagian A: #302 (dengan tambahan dari `/code-review medium`: tes container nyata check/deploy/rollback di image up2 dan tes
pasangan up2 di sisi `check()`, 3 mutan mati). Bagian C: 22 pin ada di PyPI dan tidak ditarik; fastapi 0.162.1 dan 0.162.2
terbit 2026-11-07 (belum 14 hari), jadi 0.162.0 tetap.

Keputusan Atha: 2 ("merge" #302 tersirat dalam "go live kalo udah lulus verify"; "Gass" untuk mulai build). Log:
`step*_*.log`.
