# p5 langkah (2026-11-11, Claude, "go live" Atha)

| # | hasil |
|---|---|
| 0 | `argus-control` active; `~/pilot3a_live` HEAD `b54efa8` (#411, sebelum #413), worktree bersih; 140 job, tidak ada yang `WRITING` |
| 1 | `ARGUS_CONTROL_WRITER_KEY_FILE=/` dihitung 1 di Environment unit (nilai tidak ditampilkan) |
| 2 | `pull --ff-only` → `1ecdb43` (merge #414, sesudah #419 `b2e7e8d`) |
| 3 | restart; `active`; `LISTEN 127.0.0.1:8711` saja |
| 4 | `GET /issues` 200 + CSP; `GET /issues/new` 200 + CSP, satu `<form>`, tanpa pesan "is not set for the service" |
| 5 | `POST /issues/new` dengan Origin tanpa token → 403; job 140 → 140; audit `refused: token, "no token of this page"` |

Semua sesuai harapan. Belum selesai: satu aksi sungguhan Atha dari Safari (pesan ke penulis issue), lalu `RESULT.md`.
Rollback: `git -C ~/pilot3a_live checkout b54efa8` + restart `argus-control` (butuh "go live").
