# Pilot UI kontrol #5: penulis issue Haiku dengan pencarian bentrok oleh harness (SPEC_ISSUE_WRITER amandemen 3-5)

**"Go live" Atha 2026-11-11 ("Ok langsung merge kalo beres. Dan langsung go live kalo plan udah ok")**, sesudah PR
amandemen 5 merge. Rencana ini menggantikan versi pertama p5 (hanya #413): yang di-deploy kini #413 (daftar clash ditulis
harness), #417 (amandemen 4: `touches` + `clash_check`) dan amandemen 5 (touches terlalu umum ditolak, Haiku 5.5 lewat
OpenRouter sebagai penulis, `ARGUS_CONTROL_WRITER_KEY_FILE`).

Claude menjalankan langkah berurutan, satu langkah = satu perintah (atau satu cek), mencatat output di `steps.md`, dan
berhenti di langkah pertama yang tidak sesuai harapan. Claude tidak memanggil model; port 8000, argus-ledger dan proxy
8710 tidak disentuh. `~/pilot3a_live` (`main`). Drop-in key tidak dibaca: Atha menulis `writer-key.conf` sendiri
(2026-11-11); Claude hanya menghitung baris yang menyebut nama variabelnya, tanpa menampilkan nilainya.

| # | perintah / cek | harapan |
|---|---|---|
| 0 | `systemctl --user is-active argus-control`; `git -C ~/pilot3a_live log -1`, `status --short`; tidak ada job `issue` berstate `WRITING` | `active`; HEAD sebelum #413; worktree bersih; tidak ada giliran berjalan (versi alat SubmitIssue 3 → 5, model berganti) |
| 1 | `systemctl --user show argus-control -p Environment \| grep -c 'ARGUS_CONTROL_WRITER_KEY_FILE=/'` | `1` (drop-in sudah dimuat systemd) |
| 2 | `git -C ~/pilot3a_live pull --ff-only` | fast-forward ke merge amandemen 5 atau sesudahnya |
| 3 | `systemctl --user restart argus-control`; `is-active`; `ss -ltn` | `active`; 8711 hanya di `127.0.0.1:8711` |
| 4 | `curl` (Host `localhost:8711`): `GET /issues`, `GET /issues/new` | 200 dengan CSP; `/issues/new` menampilkan form (key penulis terlihat oleh service) |
| 5 | `curl` `POST /issues/new` dengan Origin tanpa token | 403 atau 400; tidak ada job baru; baris penolakan di `audit.jsonl` |

**Selesai hanya sesudah satu aksi sungguhan Atha dari Safari** (aturan deploy service web): satu pesan ke penulis issue di
8711. Harapan: giliran berjalan di `openrouter:anthropic/claude-haiku-5.5` (job log `limits_shown`), selesai WRITTEN.
Bila pesannya meminta perubahan, issue memuat `touches` di `result.json` dan, bila bentrok, paragraf "A human loosens these
existing tests first ..." dari harness. Claude mencatatnya di `RESULT.md`.

Rollback: `git -C ~/pilot3a_live checkout <HEAD langkah 0>` lalu restart `argus-control`; butuh "go live" sendiri.
`writer-key.conf` tidak mengganggu versi lama (variabelnya tidak dibaca di sana).
