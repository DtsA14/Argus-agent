# Pilot UI kontrol #4: catatan repo antar giliran di 127.0.0.1:8711 (SPEC_ISSUE_WRITER amandemen 2, #408)

**Menunggu "go live" Atha.** Claude menjalankan langkah berurutan, satu langkah = satu perintah (atau satu cek), mencatat
output di folder ini, dan berhenti di langkah pertama yang tidak sesuai harapan. Claude tidak memanggil model; port 8000,
argus-ledger dan proxy 8710 tidak disentuh. `~/pilot3a_live` (`main`). Drop-in key tidak dibaca.

| # | perintah / cek | harapan |
|---|---|---|
| 0 | `systemctl --user is-active argus-control`; `git -C ~/pilot3a_live log -1`; tidak ada job `issue` berstate `WRITING` di `jobs/` | `active`; HEAD `e012262` (#405) atau sesudahnya tanpa #408; tidak ada giliran berjalan (versi alat dan SYSTEM berubah: giliran yang terpotong deploy akan membeli ulang langkahnya) |
| 1 | `git -C ~/pilot3a_live pull --ff-only` | fast-forward ke merge #408 (`bd2feba`) atau sesudahnya (hanya berkas PLAN ini) |
| 2 | `systemctl --user restart argus-control`; `is-active`; `ss -ltn` | `active`; 8711 hanya di `127.0.0.1:8711` |
| 3 | `curl` (Host `localhost:8711`): `GET /issues`, `GET /issues/new` | 200 dengan CSP; `/issues/new` menampilkan form |
| 4 | `curl` `POST /issues/new` dengan Origin tanpa token | 403 atau 400; tidak ada job baru; baris penolakan di `audit.jsonl` |

Sesudah langkah 4 (Atha, dari Safari): satu job issue baru dengan pertanyaan tentang repo (giliran 1), lalu satu balasan
yang meminta perubahan (giliran 2), ~$0,02. Claude mencatat di `RESULT.md`: detik dan panggilan model per giliran,
apakah giliran 2 memakai catatan (`repo_notes` ada, langkah baca berkurang), dibanding p3 w3 (10 panggilan, 60 detik).

Rollback: `git -C ~/pilot3a_live checkout e012262` lalu restart `argus-control`; butuh "go live" sendiri.
