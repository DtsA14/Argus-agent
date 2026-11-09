# Pilot viewer v0 #15: rilis issue 032 + 033 (baris job jadi kartu, tahap jadi garis waktu)

**"Go live" dari izin sesi Atha (jalur cepat, termasuk go live; approve dan applied didelegasikan ke Claude, 2026-11-08;
"Lanjut dua sisa", 2026-11-09).** Claude menjalankan langkah berurutan dari `~/pilot3a_live` (`main`), **satu langkah = satu
perintah**, mencatat output di folder ini, dan berhenti di langkah pertama yang tidak sesuai harapan, tanpa menambah atau
mengulang langkah. Hanya staging; tanpa model; container argus-ledger dan port 8000 tidak disentuh; proxy tidak di-restart.

`A = ~/Argus-agent/.venv-verify/bin/python scripts/argus.py`. Di atas rilis 031 `c4f0352`, argus-viewer:
- `e12bbea` tangan: tes 027 tidak lagi mengunci 9 selector sel `.jobs`/`.stages` (izin Atha 2026-11-09, "Longgarkan");
- `745128c` job 032 `j20261109_021656_55e9` (APPLIED; draf pertama, agen 1 percobaan);
- `e64e0f0` tangan: tes 032 tidak lagi mewajibkan `.stages td` di aturan bersama (klausa salah tulis di issue 032 oleh
  Claude; draf 033 pertama `j20261109_023042_52a3` konflik karenanya dan ditolak);
- `4955dc2` job 033 `j20261109_023512_7b70` redraft d2 (APPLIED; d1 ditolak: fixture nano tidak konsisten, tes
  mengharapkan sum `$0.0800` yang memaksa perhitungan sum berubah; redraft dengan catatan).

Rilis = `j20261109_023512_7b70-4955dc297319` (berisi 032 dan 033). Build lokal: class ada di CSS; vitest 246/246.

| # | perintah | harapan |
|---|---|---|
| 0 | `$A stage viewer-status` | viewer live `j20261108_185802_6db8-c4f0352f2280` |
| 1 | `$A stage viewer-deploy j20261109_023512_7b70 --yes` | exit 0; live rilis 033; rollback berikutnya = rilis 031 |
| 2 | `$A stage viewer-smoke` | exit 0, semua pass |
| 3 | `$A stage monitor` | exit 0, `ok: true`, viewer rilis 033 |
| 4 | `$A stage viewer-status` | viewer live rilis 033, rollback → rilis 031 |

Sesudahnya di HP: daftar job berupa kartu (id + label status, biaya + "decisions N"); di halaman job, tahap tampil sebagai
garis waktu bertitik (titik tahap termahal kuning), baris `sum` di bawahnya.
Rollback: `$A stage viewer-rollback` (ke rilis 031), butuh "go live" sendiri.
