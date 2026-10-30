# Hasil pilot viewer v0 #1 (2026-10-30)

Dua "go live" Atha: rencana (`PLAN.md`) lalu lanjutan sesudah #263. Semua dari `~/pilot3a_live`, output per langkah di
folder ini.

| # | hasil | log |
|---|---|---|
| 0 | `viewer live: nothing`, tanpa listener 8710, container ledger `1af21f1a2fc5` | `step0_status.log` |
| 1 | `viewer-deploy` exit 0: rilis `j20261030_164214_d603-e794a53775be`, image `9ac2fb4376d2`, `sw.js` = `db58777a…` | `step1_deploy.log` |
| 2 | unit proxy dipasang, `active (running)` | `step2_proxy_unit.log` |
| 3 | listener 8710 hanya `127.0.0.1:8710` | `step3_ss.log` |
| 4 | **FAIL**: `/api/summary` lewat proxy 502, cek lain pass. Berhenti di sini | `step4_smoke.log` |
| 5 | (kesalahan Claude: curl ikut dijalankan dalam perintah yang sama dengan langkah 4; hanya membaca) `/api/jobs` 502, fetch service worker untuk aset → 404, `/sw.js` → 200 | `step5_curl.log` |

**Penyebab langkah 4:** di unit `systemd --user`, `PrivateTmp=yes` menjalankan service di user namespace sendiri
(`uid_map` `1001 1001 1`); di sana `connect()` ke socket ledger gagal `EACCES`. Dibuktikan dengan `systemd-run --user`
(PrivateTmp yes → gagal, no → berhasil). Smoke kandidat saat deploy lolos karena berjalan di proses `argus`, bukan di
unit. Perbaikan #263 (a5ff7a9): `PrivateTmp` dihapus, tes opsi unit. Akibat sampingan: monitor 17:00 UTC gagal sekali
(smoke viewer); notifikasi butuh 3× berturut-turut, jadi tidak terkirim.

Lanjutan ("merge" + "go live"):

| # | hasil | log |
|---|---|---|
| 2b | `daemon-reload` + `restart`: `active (running)`, `uid_map` `0 0 4294967295` (namespace biasa) | `step2b_restart.log` |
| 3 | listener 8710 hanya `127.0.0.1:8710` | `step3b_ss.log` |
| 4 | `viewer-smoke` exit 0, semua pass; `/api/summary` = angka snapshot (57 job, $4.2766) | `step4b_smoke.log` |
| 5 | `/api/jobs` 200 JSON, `no-store` + CSP; fetch service worker untuk aset → 404, `/sw.js` → 200 | `step5b_curl.log` |
| 6 | `stage monitor` exit 0, `ok: true`, smoke ledger dan viewer pass | `step6_monitor.log` |
| 7 | viewer live = rilis langkah 1; ledger live `…-1f31e34c1ff2.up1`, container `1af21f1a2fc5` sama dengan langkah 0 | `step7_status.log` |

Pelajaran: satu langkah rencana = satu perintah (jangan digabung); smoke kandidat tidak menguji lingkungan unit systemd.
Berikutnya: Termius di HP Atha, lalu issue 002 dan 003.
