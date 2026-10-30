# Pilot viewer v0 #1: rilis viewer pertama, proxy 127.0.0.1:8710, lalu HP lewat Termius

Spek: `docs/reviews/SPEC_PWA_VIEWER.md` (§4 S, §8 A1–A5, §10), pin `SW_SHA256` (#261, 4cff16b). **Satu "go live" Atha
untuk seluruh rencana ini** (U4). Claude menjalankan langkah berurutan dari `~/pilot3a_live` (`main`), mencatat output
tiap langkah di folder ini, dan berhenti di langkah pertama yang tidak sesuai harapan, tanpa menambah atau mengulang
langkah. Hanya staging; tanpa model; build tanpa jaringan; athena-api (port 8000) dan container argus-ledger tidak
disentuh.

`A = ~/Argus-agent/.venv-verify/bin/python scripts/argus.py`; job 001 viewer = `j20261030_164214_d603` (APPLIED,
commit `e794a53775be` di `~/argus-viewer`). Rilis = `j20261030_164214_d603-e794a53775be`.

Setelah setiap langkah: container staging argus-ledger yang live tetap sama (id `docker ps` sama dengan sebelum langkah 1),
port 8000 tetap menjawab, dan tidak ada listener 8710 selain `127.0.0.1:8710`.

| # | perintah | harapan |
|---|---|---|
| 0 | `$A stage viewer-status`; `ss -ltnH`; `docker ps` | `viewer live: nothing`; tidak ada listener 8710; satu container `argus-staging-ledger-…up1` (id dicatat) |
| 1 | `$A stage viewer-deploy j20261030_164214_d603 --yes` | exit 0; build di `pwa_node22` (image `9ac2fb4376d2`) tanpa jaringan; cek artifact bersih; smoke kandidat (port ephemeral) pass; `current` → rilis di atas; `sw.js` rilis sha256 = `db58777a…` |
| 2 | `ln -s ~/pilot3a_live/deploy/systemd/argus-stage-proxy.service ~/.config/systemd/user/`, `systemctl --user daemon-reload`, `systemctl --user enable --now argus-stage-proxy.service` | unit `active (running)` |
| 3 | `ss -ltnH` | satu-satunya listener port 8710 = `127.0.0.1:8710` |
| 4 | `$A stage viewer-smoke` | exit 0; semua cek pass (index, aset = hash rekaman, `/api/summary` = angka snapshot, Host lain 421, POST 405, `/../x` dan `/api/x` 404, listener) |
| 5 | `curl -s -D- http://127.0.0.1:8710/api/jobs` (Host `127.0.0.1:8710`); `curl -s -o /dev/null -w '%{http_code}' -H 'Service-Worker: script' http://127.0.0.1:8710/assets/<js rilis>`; sama untuk `/sw.js` | `/api/jobs` 200 JSON dengan `Cache-Control: no-store` dan CSP; aset dengan header `Service-Worker` → 404, `/sw.js` → 200 |
| 6 | `$A stage monitor` | exit 0; `ok: true`, smoke ledger dan smoke viewer pass; rilis viewer dan ledger tidak berubah |
| 7 | `$A stage viewer-status`; `$A stage status` | viewer live = rilis langkah 1; ledger live tetap `…-1f31e34c1ff2.up1`, container id sama dengan langkah 0 |

Sesudah langkah 7 (bukan langkah Claude, di HP Atha, satu per satu dengan Claude di chat): Termius *Port Forwarding →
Local*, host = VM lewat SSH, bind address HP `127.0.0.1`, port lokal 8710 → tujuan `127.0.0.1:8710`; buka
`http://localhost:8710` di Safari, lalu *Add to Home Screen*. Tidak ada perubahan firewall/iptables/security list OCI.

Sesudahnya: `RESULT.md`, PENDING.md, issue 002 (detail job) dan 003 (tampilan HP) di jalur cepat.
