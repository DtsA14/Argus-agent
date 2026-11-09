# Hasil pilot UI kontrol #1: fase 2 live (2026-11-09)

Semua langkah sesuai PLAN, tanpa penyimpangan:

| # | hasil |
|---|---|
| 0 | `argus-control` tidak aktif; tidak ada listener 8711 |
| 1 | symlink unit, `daemon-reload`, `enable --now`: exit 0 |
| 2 | `active`; listener hanya `127.0.0.1:8711` |
| 3 | `GET /` 200 dengan CSP, `X-Frame-Options: DENY`, `no-store`; halaman job 039 (APPLIED) tanpa form |
| 4 | Host asing 421; POST tanpa Origin 403; dengan Origin tanpa token 403; `job.json` sha256 sama; dua baris penolakan di `audit.jsonl` (`origin`, `token`) |
| 5 | cadangan `authorized_keys.bak-20261109`; `diff`: satu baris (`iphone-viewer`) mendapat `permitopen="127.0.0.1:8711"`; mode 600 tetap |
| 6 | live viewer `j20261109_070807_8b33-9fd637600440` (rilis 039, tautan Decide); rollback → rilis 038 |
| 7 | smoke 12/12 |
| 8 | monitor `ok: true` (08:01:47Z), viewer rilis 039 |
| 9 | live rilis 039, rollback → rilis 038 |

Catatan: komentar di akhir baris kunci `iphone-viewer` masih berbunyi "forward to 127.0.0.1:8710 only" (label saja, tidak
diubah di rencana ini). Berikutnya: Atha menambah forward 8711 di Termius dan memakai Reject/Abandon dari HP; fase 3
(approve) dikoding sesudah fase 2 dipakai.

## Pemakaian pertama dari HP (2026-11-09)

- 09:22Z: Reject pertama Atha dari Safari ditolak di F3.2 (Origin). Sebab: `Referrer-Policy: no-referrer` membuat
  browser mengirim `Origin: null` pada POST form halaman sendiri; tes mengirim Origin buatan, jadi tidak menangkapnya. Job
  tidak berubah. Perbaikan #395 (`same-origin`, Origin yang ditolak dicatat di audit; mutants 38/38, verify PASS 3247),
  `argus-control` di-restart sesudah pull.
- 09:54:35Z: kiriman dari halaman lama, ditolak dengan `origin: "null"` tercatat (diagnosis terbukti).
- 09:55Z: Reject `j20261028_051613_1861` (REVIEW_READY sejak 2026-10-28, tidak diterapkan) dari HP berhasil: state
  REJECTED, log `reason` "Lama tidak diterapkan", `via: "ui"`, `sha: 0b0aacce9835`; audit `attempt` lalu hasil `exit 0`.
- Pelajaran: PLAN deploy service web memuat satu aksi sungguhan dari browser HP sebelum dinyatakan selesai.
