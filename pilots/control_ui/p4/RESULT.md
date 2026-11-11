# Hasil pilot UI kontrol #4 (2026-11-10): catatan repo antar giliran (#408)

Deploy: langkah 0-4 PLAN sesuai harapan (`step0.txt`..`step4.txt`): tidak ada giliran berjalan, live `4b17a39`,
`argus-control` active, 8711 hanya `127.0.0.1`, POST tanpa token 403 dan tercatat di audit.

Pemakaian dari Safari (Atha), job baru j20261110_165623_7672 (argus-viewer, deepseek-flash):

| giliran | pesan Atha | hasil | detik | panggilan | langkah | USD |
|---|---|---|---|---|---|---|
| w1 | "Di halaman job, bagian stage apa aja yang ditampilkan sekarang? ... belum usah bikin issue." | tanpa issue, catatan repo ditulis (±1500 karakter, baris-baris `App.jsx`) | **7,9** | 4 | 5 | 0,0012 |
| w2 | "Oke, tambahin durasi tiap stage ... dari started_at sampai ended_at." | issue + 5 clash + 2 pertanyaan | 49,7 | 14 | 23 | 0,0079 |

Pembanding p3: w2 (tanpa issue) 27,3 detik / 9 panggilan; w3 (issue) 59,8 detik / 10 panggilan.

**Ukuran.** Giliran tanpa issue yang pertanyaannya terarah: **7,9 detik, target ≤ 10 detik tercapai**. Giliran issue
dengan catatan: 49,7 detik (−17% dari 59,8) tapi **14 panggilan (lebih banyak)**: catatan memang dipakai (tidak ada
ListFiles awal penuh), tapi giliran issue wajib mencari bentrok di tes lama (bagian 4), dan itulah sebagian besar
langkahnya (8 ReadFile/SearchFiles pada file tes, `App.jsx` dibaca 3 kali di bagian berbeda). Catatan tidak memuat isi tes,
jadi pencarian bentrok tetap dari nol.

**Issue w2.** 5 clash nyata (tes yang mengunci daftar kolom tabel stage), disebut jelas di balasan; issue tetap menulis
"... existing tests keep passing unchanged." di baris 18 sambil mencatat 5 clash — pola
p3 w3 berulang (gerbang di PENDING). Belum di-Start.

**Kesimpulan.** Giliran tanya-jawab sudah cepat; giliran issue ±50 detik karena pencarian bentrok yang memang diwajibkan.
Mempercepatnya lagi berarti mengurangi pencarian bentrok (risiko issue yang merusak tes lama, sumber utama draf ditolak
2026-11-08/09). Usul: berhenti mengoptimasi kecepatan giliran issue; lanjut gerbang "keep passing unchanged" + clash.
