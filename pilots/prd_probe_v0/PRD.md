# PRD-lite (draft for Atha's approval): Papan skor di HP

Status: **draft, belum disetujui** (2026-11-12). Probe pertama alur "PRD → irisan → staging" tanpa kode baru di Argus: Claude menulis PRD dan irisannya, Argus mengerjakan tiap irisan sebagai job biasa,
Atha menjadi gerbang (approve PRD, approve tiap draf, "go live" staging). Tujuan probe: mengukur **perekat manual** di antara irisan (lihat `GLUE_LOG.md`), bukan fiturnya.

## 1. Masalah
Hasil kerja Argus (berapa job di-apply, ditolak, ditinggalkan, berapa biaya per perubahan) baru bisa dilihat lewat skrip di VM (`scripts/scoreboard.py`). Atha ingin melihatnya di HP, tanpa terminal.

## 2. Tujuan dan bukan-tujuan
- **Tujuan:** satu halaman `/scoreboard` di viewer yang menampilkan, per jenis job (code, research, issue): jumlah job menurut hasil (di-apply, ditolak, ditinggalkan, gagal, terbuka), total biaya, dan satu baris "biaya per perubahan di-apply".
- **Bukan tujuan (v1):** per repo (snapshot staging belum memuat nama repo; butuh perubahan di sisi Argus, jalur ketat), perbandingan antar minggu, ekspor, grafik, filter, autentikasi baru.

## 3. Pengguna dan cara pakai
Satu pengguna (Atha), HP, lewat viewer yang sudah ada (port 8710). Halaman dibuka dari tautan di halaman utama.

## 4. Kontrak data (ledger → viewer), dibekukan di PRD
`GET /scoreboard` di argus-ledger, JSON, tanpa parameter:
```json
{
  "jobs": 153,
  "kinds": {
    "code":     {"jobs": 119, "outcomes": {"applied": 62, "rejected": 18, "abandoned": 13, "failed": 6, "open": 20},
                 "cost_nano": 7098973624, "cost_usd": "7.0990"},
    "research": {"jobs": 26,  "outcomes": {"applied": 0, "rejected": 0, "abandoned": 0, "failed": 2, "open": 24},
                 "cost_nano": 738600000, "cost_usd": "0.7386"},
    "issue":    {"jobs": 5,   "outcomes": {"applied": 0, "rejected": 0, "abandoned": 0, "failed": 0, "open": 5},
                 "cost_nano": 0, "cost_usd": "0.0000"}
  },
  "cost_per_applied": {"nano": 116132400, "usd": "0.1161"}
}
```
Aturan: jenis dari `kind` di `job.json` (jenis lain atau tanpa `kind` dihitung di `"other"`); hasil dari `state`: `APPLIED`→applied, `REJECTED`→rejected, `ABANDONED`→abandoned,
`DRAFT_FAILED`/`AGENT_FAILED`/`BLOCKED`/`REVIEW_INVALID`/`RESEARCH_FAILED`/`RESEARCH_INCONCLUSIVE`→failed, lainnya→open; biaya dari ledger run (yang sudah dipakai `cost_nano` job);
`cost_per_applied` = (biaya semua job `code` dan `issue`) / jumlah `code` yang applied, `null` bila nol. Semua jumlah bilangan bulat, biaya dalam nano-dollar, teks empat desimal.

## 5. Irisan (urutan tetap; tiap irisan satu issue dan satu job Argus, kecuali S2)
| Irisan | Repo | Isi | Syarat selesai | Bergantung pada |
|---|---|---|---|---|
| S1 | argus-ledger | `GET /scoreboard` sesuai kontrak, tes, bagian README | tes lulus; `curl` pada data uji memberi bentuk persis kontrak | – |
| S2 | staging | Stage 18: rilis ledger dengan endpoint baru (Claude, "go live" per PLAN.md) | `/api/scoreboard` di 8710 memberi 200 dengan bentuk kontrak untuk 150+ job nyata | S1 |
| S3 | argus-viewer | halaman `/scoreboard`: tabel per jenis, baris biaya per perubahan, status memuat dan galat | tes lulus; rilis viewer; halaman terbuka di HP | S2 (data), kontrak |
| S4 | argus-viewer | tautan "Papan skor" di halaman utama | tes lulus; rilis viewer | S3 |

## 6. Gerbang manusia (tiga)
1. Atha menyetujui PRD ini (sekali).
2. Atha atau Claude menyetujui tiap draf (aturan jalur cepat; izin tetap untuk job viewer kecil).
3. "Go live" Atha untuk S2 (staging ledger).

## 7. Risiko dan pertanyaan terbuka
- Kontrak harus dikutip persis ke issue S1 dan S3; selisih satu nama field adalah perekat yang akan terlihat.
- Tes lama yang mengunci bentuk JSON `GET /jobs` tidak terpengaruh (endpoint baru), tetapi tes `README` atau daftar rute ledger bisa bocor: peringatan `leaks` (#437) berlaku untuk Python.
- Nama repo per job tidak ada di snapshot (`router/stage_data.py` tidak mempublikasikan `inputs`, dan entri `APPLIED` tidak memuat `as_is`): versi per repo adalah irisan Argus jalur ketat, di luar probe.

## 8. Ukuran keberhasilan probe
Bukan fiturnya, tetapi: berapa irisan lolos pada percobaan pertama, biaya total, dan **daftar perekat** (tindakan manusia atau Claude di antara irisan) di `GLUE_LOG.md`, dengan penilaian bisa diotomasi atau tidak (seperti `chain_probe_v0`).
