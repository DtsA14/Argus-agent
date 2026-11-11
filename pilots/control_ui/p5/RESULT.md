# p5 hasil (2026-11-11)

Aksi sungguhan Atha dari Safari: issue baru di 8711, repo argus-viewer (`49b11ec`), pesan "Di kartu job di beranda,
tampilin judul job di atas id-nya, biar gampang dibedain" (job `j20261111_043029_53f7`).

- Model: `openrouter:anthropic/claude-haiku-5.5` (job log `limits_shown`); key lewat `ARGUS_CONTROL_WRITER_KEY_FILE`.
- Giliran w1: WRITTEN, 23,1 dtk, 10 langkah, 1 submit (diterima), $0,0117. Job AWAITING_HUMAN.
- Hasil: **balasan tanpa issue** dengan dua pertanyaan: data job di beranda tidak punya field judul (hanya id, state,
  created_at, stages, decisions, cost_nano, cost_usd, running), jadi "judul" dari mana? (state, atau field API yang belum
  terlihat?), dan halaman mana. Ini perilaku yang diharapkan dari replay #418 (A: menandai data yang tidak dikirim API)
  pada pesan nyata yang butuh data lintas repo (judul job ada di antrean PENDING: butuh allowlist + ledger).
- Gerbang amandemen 4/5 belum teruji di sini (tidak ada issue, `touches` kosong): menunggu giliran yang menulis issue.

Deploy p5 selesai menurut aturan (satu aksi sungguhan dari HP).
