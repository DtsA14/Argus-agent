# Pilot UI kontrol #2: chatbox penulis issue di 127.0.0.1:8711 (SPEC_ISSUE_WRITER PR 1-3)

**"Go live" Atha 2026-11-09 ("Merge dan go live", sesudah #400 dan #401).** Claude menjalankan langkah berurutan,
satu langkah = satu perintah (atau satu cek), mencatat output di folder ini, dan berhenti di langkah pertama yang tidak
sesuai harapan. Tidak ada model yang dipanggil oleh Claude dalam rencana ini; port 8000, argus-ledger dan proxy 8710
tidak disentuh. `~/pilot3a_live` (`main`).

| # | perintah / cek | harapan |
|---|---|---|
| 0 | `systemctl --user is-active argus-control`; `git -C ~/pilot3a_live log -1`; `ss -ltn` | `active`; HEAD sebelum #398; 8711 hanya `127.0.0.1` |
| 1 | `git -C ~/pilot3a_live pull --ff-only` | fast-forward ke `68d42c1` (berisi #398, #399, #400, #401) |
| 2 | `systemctl --user restart argus-control`; `is-active`; `ss -ltn` | `active`; 8711 hanya di `127.0.0.1:8711` |
| 3 | `curl` (Host `localhost:8711`): `GET /`, `GET /issues`, `GET /issues/new` | 200 dengan header CSP/`X-Frame-Options`/`Referrer-Policy: same-origin`; `/` menautkan `/issues`; `/issues/new` menulis `ARGUS_CONTROL_KEY_FILE is not set` (belum dipasang) |
| 4 | `curl` `POST /issues/new` tanpa Origin; dengan Origin tanpa token | 403; 403 (atau 400 bila form ditolak lebih dulu); tidak ada job baru di `jobs/`; baris penolakan di `audit.jsonl` |

Sesudah langkah 4 (bukan Claude): Atha memasang path key di drop-in unit (`systemctl --user edit argus-control`,
`Environment=ARGUS_CONTROL_KEY_FILE=...`, lalu `systemctl --user restart argus-control`); Claude hanya mengecek bahwa
`/issues/new` kini menampilkan form (tanpa membaca atau menampilkan path-nya). Lalu pemakaian pertama dari Safari oleh
Atha: satu issue nyata, satu-dua balasan (~$0,02), dan bila issue-nya baik Start job (drafter ~$0,05); Claude memeriksa
job issue, job code, audit, dan mencatat hasilnya.

Rollback: `git -C ~/pilot3a_live checkout <HEAD langkah 0>` lalu restart `argus-control` (Reject/Abandon fase 2 tetap
ada di versi itu); butuh "go live" sendiri.
