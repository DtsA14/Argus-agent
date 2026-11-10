# Pilot UI kontrol #5: issue yang bentrok memuat daftar tes yang dilonggarkan (SPEC_ISSUE_WRITER amandemen 3, #413)

**Menunggu "go live" Atha.** Claude menjalankan langkah berurutan, satu langkah = satu perintah (atau satu cek), mencatat
output di folder ini, dan berhenti di langkah pertama yang tidak sesuai harapan. Claude tidak memanggil model; port 8000,
argus-ledger dan proxy 8710 tidak disentuh. `~/pilot3a_live` (`main`). Drop-in key tidak dibaca.

| # | perintah / cek | harapan |
|---|---|---|
| 0 | `systemctl --user is-active argus-control`; `git -C ~/pilot3a_live log -1`; tidak ada job `issue` berstate `WRITING` | `active`; HEAD tanpa #413; tidak ada giliran berjalan (versi alat SubmitIssue berubah) |
| 1 | `git -C ~/pilot3a_live pull --ff-only` | fast-forward ke merge #413 (`af62124`) atau sesudahnya (hanya berkas pilot) |
| 2 | `systemctl --user restart argus-control`; `is-active`; `ss -ltn` | `active`; 8711 hanya di `127.0.0.1:8711` |
| 3 | `curl` (Host `localhost:8711`): `GET /issues`, `GET /issues/new` | 200 dengan CSP; `/issues/new` menampilkan form |
| 4 | `curl` `POST /issues/new` dengan Origin tanpa token | 403 atau 400; tidak ada job baru; baris penolakan di `audit.jsonl` |

Sesudahnya: issue berikutnya dari HP yang bentrok dengan tes lama harus memuat paragraf "A human loosens these existing
tests first ..." sebelum baris Environment, tanpa klaim "keep passing unchanged". Claude mencatatnya di `RESULT.md`.

Rollback: `git -C ~/pilot3a_live checkout <HEAD langkah 0>` lalu restart `argus-control`; butuh "go live" sendiri.
