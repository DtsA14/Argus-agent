# p6 hasil (2026-11-11)

Aksi Atha dari Safari: balasan "Coba lagi bro" ke `j20261111_054721_cebd` (argus-ledger `b712363`).

- Giliran w2 (Haiku 5.5): WRITTEN, 35,8 dtk, 10 langkah, 2 submit (yang pertama ditolak: balasan 2.893 > 1.200 karakter),
  $0,0148. Bandingkan w1 sebelum perbaikan: WRITE_FAILED, 4 submit habis karena touches berganti.
- `touches` = `["title"]`, 0 baris tes lama: tidak ada tes ledger yang memuat `title`, jadi tidak ada daftar dan tidak ada
  clash. Benar menurut Claude: fixture tes ledger tidak punya `title`, jadi tes lama yang membandingkan kunci item persis
  tetap lolos; viewer (`readJob`) membuang kunci yang tidak dikenalnya, jadi urutan deploy ledger → viewer aman.
- Issue: `title` di GET /jobs dan GET /jobs/{id} bila string, kunci tidak ada bila tidak ada/bukan string, posisi sesudah
  `created_at`, CSV/`/ui`/`/summary` tetap; contoh dan tes lengkap. Satu pertanyaan: `""` dikirim atau dibuang (snapshot
  Argus tidak pernah menerbitkan judul kosong, jadi tidak berpengaruh).

Deploy p6 selesai menurut aturan (satu aksi sungguhan dari HP). Gerbang `clash_check` dengan daftar belum teruji pada
issue yang diterima: menunggu issue viewer (bagian 3).
