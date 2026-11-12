# Probe PRD-lite "papan skor di HP": hasil (2026-11-12)

PRD disetujui Atha ("gass"), empat irisan, tiga gerbang manusia (PRD, "go live" Stage 18, "go live" restart proxy + rilis viewer; draf di-approve Claude dengan izin tetap). Fitur live di HP: halaman `/scoreboard`,
tautan "Papan skor" di halaman utama, `GET /api/scoreboard`.

| Irisan | Repo | Hasil | Biaya model |
|---|---|---|---|
| S1 `GET /scoreboard` | argus-ledger `1aeb82d` | draf lolos pertama, agen 1 percobaan, di-apply apa adanya | $0,0375 |
| S2 Stage 18 | staging | langkah 0-4 lolos, langkah 5 meleset (proxy), lanjut sesudah perbaikan | – |
| S3 halaman `/scoreboard` | argus-viewer `1ed4374` | draf lolos pertama, agen 2 percobaan (1 `context_limit`), di-apply apa adanya | $0,0741 |
| S4 tautan | argus-viewer `11ce204` | draf lolos pertama, agen 1 percobaan, di-apply apa adanya | $0,0529 |
| Perbaikan proxy | Argus `router/stage_viewer.py` | PR #460, jalur ketat penuh (spek, tes, review, 7/8 mutan + 1 ekuivalen, verify_at 3702), **bukan job Argus** | $0 (tanpa model) |

Total model $0,1645 untuk tiga job Argus. Data nyata cocok dengan kontrak: 156 job = `/api/summary`, total biaya sama persis sampai nano-dollar.

## Temuan
1. **Kontrak yang dibekukan membuat irisan nyambung tanpa selisih.** Tiga job berurutan dari satu kontrak di PRD: nol salah nama field, nol konflik tes lama, tiga draf lolos pada percobaan pertama.
2. **Dua ketergantungan tersembunyi, keduanya di sisi Argus (jalur ketat, tidak bisa dikerjakan Argus sendiri):** snapshot staging tidak memuat nama repo dan `as_is` (ditemukan saat menulis PRD, memaksa versi per jenis job), dan proxy viewer hanya meneruskan
   empat jalur API tetap (ditemukan saat staging, langkah 5 Stage 18). Tahap PRD yang hanya membaca kode aplikasi tidak menemukannya.
3. **Urutan "S2 sebelum S3" ternyata "S2 sebelum rilis S3":** kode S3 tidak butuh ledger yang sudah live, hanya kontraknya.
4. **Pagar yang sudah dibangun bekerja di dunia nyata:** gerbang konflik tes lama dan peringatan `leaks` tidak terpicu (tidak ada konflik); batas `RunValidation`/FIX-A tidak disentuh.

## Penilaian tiga sambungan (dari saran Fable)
| Sambungan | Dari probe |
|---|---|
| `argus apply` (sekarang manual) | **Paling terasa**: tiga apply dengan tangan (baca patch, `git apply`, commit, `argus applied`); semuanya mekanis. Prioritas tertinggi |
| Tahap PRD (penulis issue mode PRD) | Berguna tetapi **perlu daftar periksa jalur Argus** (snapshot, proxy), bukan hanya kode aplikasi; menulis issue dari kontrak sebagian bisa diotomasi |
| Antrean berurutan | Rendah: dengan tiga irisan, mengurutkan secara manual murah; irisan yang bergantung pada rilis (S3 pada S2) justru butuh gerbang manusia di antara |

Batas probe: n = 1, fitur kecil, aplikasi dan staging yang sudah ada, Claude menulis issue dan menjadi perekat, dan tiga draf yang lolos itu ditulis untuk aplikasi yang tesnya sudah dikenal agen.
Daftar perekat lengkap: `GLUE_LOG.md`.
