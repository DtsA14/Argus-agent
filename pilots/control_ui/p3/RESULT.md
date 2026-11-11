# Hasil pilot UI kontrol #3 (2026-11-10): chat yang terasa cepat (#404)

Deploy: langkah 0-4 PLAN sesuai harapan (`step0.txt`..`step4.txt`): live `e012262`, `argus-control` active, 8711 hanya
`127.0.0.1`, halaman job berbentuk chat (`bubble`, form dengan `turn`), POST tanpa token 403 dan tercatat di audit.

Pemakaian dari Safari (Atha), job j20261109_162802_3ff8 (argus-viewer, deepseek-flash):

| giliran | pesan Atha | hasil | detik | panggilan model | langkah | USD |
|---|---|---|---|---|---|---|
| w1 (2026-11-09, sebelum #403/#404) | "Apa yang fitur yang perlu ditambahkan ke argus viewer?" | WRITE_FAILED (batas lama) | 23,9 | 8 | – | 0,0056 |
| w2 | "Fitur apa yang paling berguna ... Kasih 3 ide aja, belum usah bikin issue." | WRITTEN, **tanpa issue** (3 ide berdasar kode), Start tidak tampil | 27,3 | 9 | 11 | 0,0029 |
| w3 | "Bikin issue nomor 3: kartu Waiting for you bisa diketuk ..." | WRITTEN, issue `9d157b57d475` + 7 clash | 59,8 | 10 | 14 | 0,0078 |

Atha: "Ok working bro. Stream baca filenya juga jalan" (langkah tampil selama menunggu: A2 bekerja).

**Ukuran.** Target giliran tanpa issue ≤ 10 detik **tidak tercapai** (27 detik): untuk pertanyaan tentang isi repo model
tetap membaca (README, `App.jsx` dua kali, 5 pencarian); jawabannya memang berdasar kode. Waktu per panggilan 0,8-4,9
detik; yang mahal adalah jumlah langkah, bukan menyalakan CLI. Giliran tanpa issue untuk pertanyaan yang tidak butuh repo
belum dicoba.

**Issue w3.** Gaya Argus lengkap (aturan dengan contoh, teks/kelas persis, tes keamanan markup). Tapi 7 clash di
`src/jobs-waiting-card.test.jsx` (href kartu `/jobs/<id>/draft` → `/waiting`), sementara issue tetap menulis "The existing
tests keep passing unchanged" dan paragraf Tests meminta perubahan di file tes kartu: tidak konsisten. Belum di-Start;
perlu keputusan (melonggarkan 7 tes oleh manusia lebih dulu, atau issue tanpa mengubah href kartu, mis. tautan "see all"
terpisah).

**Berikutnya (usul).** (1) Giliran membawa ringkasan repo / hasil baca giliran sebelumnya, supaya w3 tidak membaca ulang
apa yang w2 sudah baca (w2 dan w3 sama-sama membaca `App.jsx` dan file tes kartu); (2) gerbang SubmitIssue: issue yang
punya `clashes` tidak boleh berisi "keep passing unchanged" tanpa menyebut tes yang dilonggarkan.
