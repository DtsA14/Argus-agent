# Pilot UI kontrol #1: service fase 2 (127.0.0.1:8711), akses HP, viewer rilis 039 (tautan Decide)

**"Go live" Atha 2026-11-09 ("Ok merge dan go live kalo udah beres", sesudah #392 merge).** Claude menjalankan langkah
berurutan dari `~/pilot3a_live` (`main` = `2704e9f`), satu langkah = satu perintah (atau satu cek), mencatat output di
folder ini, dan berhenti di langkah pertama yang tidak sesuai harapan, tanpa menambah atau mengulang langkah. Tidak ada job
sungguhan yang di-reject atau di-abandon dalam rencana ini. Port 8000, container argus-ledger dan proxy 8710 tidak
disentuh. `A = ~/Argus-agent/.venv-verify/bin/python scripts/argus.py`; `J` = `j20261109_070807_8b33` (job 039, APPLIED).

| # | perintah / cek | harapan |
|---|---|---|
| 0 | `systemctl --user is-active argus-control`; `ss -ltn` | tidak aktif; tidak ada listener 8711 |
| 1 | `ln -s ~/pilot3a_live/deploy/systemd/argus-control.service ~/.config/systemd/user/`; `systemctl --user daemon-reload`; `systemctl --user enable --now argus-control` | exit 0 |
| 2 | `systemctl --user is-active argus-control`; `ss -ltn` | `active`; 8711 hanya di `127.0.0.1:8711` |
| 3 | `curl` `GET /` dan `GET /jobs/$J` (Host `localhost:8711`) | 200, header CSP/`X-Frame-Options`/`no-store` ada; halaman `J` tanpa form (APPLIED) |
| 4 | `curl` `GET /` dengan Host `evil.example:8711`; `POST /jobs/$J/abandon` tanpa Origin; dengan Origin tapi tanpa token | 421; 403; 403 (atau 400 bila form ditolak lebih dulu); `job.json` `J` tidak berubah (sha256 sama); `audit.jsonl` berisi baris penolakan |
| 5 | cadangkan `~/.ssh/authorized_keys` ke `~/.ssh/authorized_keys.bak-20261109`; di baris `iphone-viewer` saja, `permitopen="127.0.0.1:8710"` → `permitopen="127.0.0.1:8710",permitopen="127.0.0.1:8711"` | `diff` cadangan vs baru: tepat satu baris berubah, hanya penambahan itu; mode file tetap |
| 6 | `$A stage viewer-deploy $J --yes` | exit 0; live rilis 039 (`9fd6376`); rollback = rilis 038 |
| 7 | `$A stage viewer-smoke` | exit 0, semua pass |
| 8 | `$A stage monitor` | exit 0, `ok: true`, viewer rilis 039 |
| 9 | `$A stage viewer-status` | live rilis 039, rollback → rilis 038 |

Sesudahnya: Atha menambah forward 8711 di Termius (bind 127.0.0.1 di HP), membuka `http://localhost:8711`.
Rollback: `systemctl --user disable --now argus-control`, kembalikan `authorized_keys` dari cadangan, `$A stage
viewer-rollback`; masing-masing butuh "go live" sendiri.
