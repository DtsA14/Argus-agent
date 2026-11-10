# Pilot UI kontrol #3: chat yang terasa cepat di 127.0.0.1:8711 (SPEC_ISSUE_WRITER amandemen 1, #404)

**Menunggu "go live" Atha.** Claude menjalankan langkah berurutan, satu langkah = satu perintah (atau satu cek), mencatat
output di folder ini, dan berhenti di langkah pertama yang tidak sesuai harapan. Claude tidak memanggil model; port 8000,
argus-ledger dan proxy 8710 tidak disentuh. `~/pilot3a_live` (`main`). Drop-in key tidak dibaca.

| # | perintah / cek | harapan |
|---|---|---|
| 0 | `systemctl --user is-active argus-control`; `git -C ~/pilot3a_live log -1`; `ss -ltn` | `active`; HEAD `cd70a2d` (#403); 8711 hanya `127.0.0.1` |
| 1 | `git -C ~/pilot3a_live pull --ff-only` | fast-forward ke merge #404 (`1b394ce`) atau sesudahnya (hanya berkas PLAN ini) |
| 2 | `systemctl --user restart argus-control`; `is-active`; `ss -ltn` | `active`; 8711 hanya di `127.0.0.1:8711` |
| 3 | `curl` (Host `localhost:8711`): `GET /issues`, `GET /issues/j20261109_162802_3ff8`, `GET /style.css` | 200 dengan CSP; halaman job memuat `class="bubble"` dan form reply dengan `name="turn"`; CSS memuat `.bubble` |
| 4 | `curl` `POST /issues/j20261109_162802_3ff8/reply` dengan Origin tanpa token | 403 atau 400; tidak ada giliran baru; baris penolakan di `audit.jsonl` |

Sesudah langkah 4 (Atha, dari Safari): balas job j20261109_162802_3ff8 dengan pertanyaan umum (giliran tanpa issue,
~$0,01), lalu satu keinginan konkret (giliran dengan issue, ~$0,02). Claude mencatat di `RESULT.md`: detik per giliran
(`run_start` → `run_end`), jumlah panggilan model, biaya, dan apakah langkah tampil saat menunggu. Target giliran tanpa
issue ≤ 10 detik.

Rollback: `git -C ~/pilot3a_live checkout cd70a2d` lalu restart `argus-control`; butuh "go live" sendiri.
