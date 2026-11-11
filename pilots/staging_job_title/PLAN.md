# Staging: judul job di snapshot (SPEC_STAGING_REAL_DATA amandemen 9)

**"Go live" Atha 2026-11-11 ("Ok go live aja bro")**, sesudah PR amandemen 9 merge. Claude menjalankan langkah
berurutan, satu langkah = satu perintah (atau satu cek), mencatat output di `steps.md`, dan berhenti di langkah pertama
yang tidak sesuai harapan. Tanpa model. Container ledger, proxy 8710 dan service 8711 tidak di-restart.

| # | perintah / cek | harapan |
|---|---|---|
| 0 | `git -C ~/pilot3a_live log -1`, `status --short`; `systemctl --user is-active argus-stage-monitor.timer`; baris terakhir `~/argus-staging/monitor.jsonl` | HEAD `1ecdb43` (sebelum amandemen 9), bersih; timer active; monitor terakhir lolos |
| 1 | `git -C ~/pilot3a_live pull --ff-only` | fast-forward ke merge amandemen 9 atau sesudahnya |
| 2 | `systemctl --user start argus-stage-monitor.service` (refresh + smoke, yang biasa dijalankan timer) | selesai; baris baru di `monitor.jsonl` lolos semua cek |
| 3 | snapshot aktif: hitung `job.json` dengan `title`, dan `excluded` di manifest | 138 job (112 code + 26 riset) atau lebih dengan `title`, 3+ job `issue` tanpa; `excluded` kosong |
| 4 | `GET /jobs` ledger lewat proxy 8710 (yang dipakai viewer) | 200, jumlah job sama dengan snapshot (ledger mengabaikan `title`, T2) |

Sesudahnya: issue ledger (tampilkan `title` di API) ditulis dari HP lewat 8711.

Rollback: `git -C ~/pilot3a_live checkout 1ecdb43` lalu `systemctl --user start argus-stage-monitor.service` (snapshot
tanpa judul); butuh "go live" sendiri. 8711 ikut berjalan di checkout yang sama tetapi kodenya tidak berubah oleh
amandemen ini (hanya `router/stage_data.py`), jadi tidak di-restart.
