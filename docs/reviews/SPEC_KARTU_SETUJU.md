# SPEC kartu persetujuan dalam bahasa biasa (T3 diubah bentuknya): yang Atha setujui adalah contoh angka, bukan patch

Status: **rev 0, 2026-11-17; menunggu tinjauan Opus (read-only) dan kata Atha.** Lahir dari dua hal: (1) Atha melihat kartu T2 di HP dan masih pusing membacanya ("kalo itu gw masih pusing bacanya"), (2) usul sesi lain: "Kamu tidak paham kode, tapi kamu paham domainnya. Yang kamu setujui seharusnya contoh, bukan patch." Mengganti isi T3 di `PENDING.md` (uji kartu cacat-ditanam tetap, tetapi diuji pada kartu ini) dan menentukan bentuk kartu yang nanti dipakai T4. Bahan: `docs/reviews/SPEC_CHAT_CARDS.md` (T2, `router/cards.py`), `docs/reviews/SPEC_EXAMPLE_GATE.md` (data contoh), `router/apply.py` (`--read-sha`), `pilots/example_gate_rp1_v0/RESULT.md` (empat angka salah Rp1).

## 1. Masalah dan ukuran
Kartu T2 menampilkan semuanya (kode contoh, `actual`, teks issue 1600 karakter): benar tetapi tidak bisa dinilai Atha dari HP. Atha tidak membaca kode; ia paham domain (harga, lot, batas rugi). Yang bisa ia nilai: "dengan masukan ini, keluarannya segini: benar atau salah?". Ukuran: (1) Atha membaca satu kartu dalam kira-kira dua menit tanpa melihat kode; (2) dalam uji T3, dari kartu yang memuat angka salah yang ditanam ia menolak sedikitnya 4 dari 5 (angka salah Rp1 adalah contoh nyatanya); (3) kartu baik yang ia tolak salah dicatat.

## 2. Tiga blok kartu (urutan tetap, hanya baca)
**A. "Ini yang akan dibuat dan biayanya."** Ringkasan PRD dalam bahasa Indonesia biasa (kalimat `reply` penulis, ditandai "ditulis model"), jumlah issue, biaya: yang sudah keluar dan yang diusulkan untuk antrean (mesin).
**B. "Ini contohnya."** Tiap contoh sebagai tabel kecil **masukan → keluaran dalam angka nyata**, bukan kode. Isinya diturunkan **secara mekanis dari kode contoh itu sendiri** (bagian 3), jadi angka di kartu persis angka yang dijalankan mesin; kalimat `says` penulis hanya tambahan bertanda "ditulis model". Di bawah tiap contoh satu baris bukti mesin: `mesin menjalankan ini di kode: cocok` / `TIDAK cocok (kode memberi ...)` / `belum dijalankan`. Contoh `after` (perilaku baru) dipisah dari yang lama dengan judul "Yang berubah" dan "Yang tidak boleh berubah". Bila issue tidak punya contoh `after`, kartu menulis tegas "Tidak ada contoh untuk perilaku yang baru".
**C. "Pasang?"** hanya terbuka bila bukti lengkap, semuanya dari mesin: (a) contoh di dasar lulus, (b) audit sesudah agent: tiap contoh cocok pada kode akhir, (c) tes drafter lulus, (d) paket review valid, (e) **tahap pembaca patch tercatat** (bagian 4). Bila ada yang belum: kartu menulis apa yang kurang, dan tidak ada tombol (T4). Tidak pernah ada kata "aman".

## 3. Contoh sebagai angka (penurunan mekanis, tanpa model)
Dari `setup` dan `run` (AST, tanpa menjalankan apa pun): nama fungsi yang dipanggil, argumen literal (angka, teks, bool, daftar sederhana), proyeksi atribut (`.passed`, `["stop"]`), dan `expect`. Tampilan: judul = nama fungsi, baris "masukan" = `nama argumen: nilai`, baris "keluaran" = nilai yang diharapkan, angka dengan titik ribuan dan koma desimal (1.000.000; 0,03), `True`/`False` ditulis "ya"/"tidak" dengan nilai aslinya di dalam tanda kurung. Argumen **posisi** ditulis `argumen 1`, `argumen 2`; supaya kartu terbaca, **gerbang penulis menolak contoh yang memanggil kode repo dengan angka literal sebagai argumen posisi** ("tulis argumennya dengan nama"), keputusan D2. Contoh yang tidak bisa diturunkan (ekspresi rumit: lambda berlapis, perulangan) tampil sebagai "contoh ini tidak bisa ditampilkan sebagai angka" dan **dihitung sebagai cacat kartu** (blok C tidak terbuka). Yang tidak bisa diturunkan tidak pernah diganti parafrase model.
Satuan dan arti kolom ("kerugian hari ini, Rp") adalah pengetahuan domain; nama argumen kode (`current_daily_realized_loss_idr`) ditampilkan apa adanya di samping, dan bila penulis menyertakan label bahasa biasa untuk argumen (bidang `labels` baru di contoh, opsional, bertanda model) label itu tampil **di samping** nama kode, tidak menggantikannya.

## 4. Siapa membaca patch (jujur)
Contoh membuktikan perilaku, bukan bahwa kodenya bersih. Patch tetap harus dibaca, dan Atha tidak membacanya. Usul (D3, saran sesi lain): **Claude membaca patch, dicatat terang-terangan sebagai tahap**, bukan sebagai manusia. Konkretnya: sebelum blok C terbuka, satu catatan terstruktur dibuat oleh sesi Claude lewat perintah (`argus patch-read <job> --sha <sha patch> --verdict ok|concerns --note "..."`) yang disimpan di job (`patch_read.json`, terikat sha patch), dengan pembaca `claude`, waktu dan catatannya; `argus apply --read-sha` mengakui `--reader claude` dan mencatat `reader` pada entri log yang sudah ada (bukan jenis `what` baru). Kartu menampilkan "Patch dibaca oleh: Claude, <waktu>, hasil: ok/ada catatan" dan catatan itu, dengan label **bukan dibaca manusia**. Pilihan lain (model peninjau di dalam Argus) ditunda sampai diuji dengan cacat ditanam; peninjau murah sudah terbukti meloloskan dua patch salah.

## 5. Yang tidak ditangkap (batas jujur)
- Contoh hanya mencakup yang terpikir penulis; angka di prosa issue tidak diperiksa. Kartu menyebut jumlah contoh `after` dan peringatan bila nol (sudah ada di T2).
- Bila pembaca patch (Claude) keliru atau kode contoh memalsukan `pass`, kartu tidak tahu; patch yang bersih secara perilaku tetapi berbahaya (membaca kunci, menulis berkas) hanya ditangkap oleh pagar yang ada (sandbox, protected files, pembaca patch) dan oleh pembaca.
- Kartu tidak menilai apakah contoh mewakili aturan bisnis; itu tugas Atha (domain).

## 6. Uji T3 pada kartu ini
Lima kartu dengan angka salah yang ditanam di antara kartu baik (fixture buatan di direktori job terpisah, tidak tercampur data nyata; kunci jawaban disimpan Claude dan tidak tampak di kartu). Cacat: (1) contoh yang kodenya sendiri gagal (mesin menandai), (2) angka masukan→keluaran yang salah secara domain tetapi cocok dengan kode (mesin lulus, domain tidak), (3) perilaku baru tanpa contoh `after`, (4) biaya jauh di atas wajar, (5) issue yang menyimpang dari permintaan (mengubah batas yang diminta tetap). Lulus bila Atha menolak sedikitnya 4 dari 5 dengan jawaban teks ke Claude ("tolak 2 karena ..."), dan kartu baik yang ia tolak dicatat. Gagal = kartu dirancang ulang; T4 tetap ditahan.

## 7. Tes dan mutan (ditulis sebelum kode)
Penurunan angka: tiap bentuk contoh yang didukung (argumen bernama, proyeksi atribut, kunci dict, daftar, bool, angka besar dan kecil, negatif, teks) menghasilkan tabel yang persis; yang tidak didukung menghasilkan "tidak bisa ditampilkan" dan menutup blok C; angka di kartu sama dengan `eval` literal dari AST (properti: mutasi satu angka di kode mengubah satu angka di kartu); argumen posisi ditolak penulis; blok C tidak terbuka tanpa bukti (a)-(e) satu per satu; `patch-read` terikat sha dan basi bila patch berubah; `apply` mencatat `reader` tanpa jenis log baru; kartu tidak pernah menampilkan parafrase model sebagai angka; fixture T3 tidak tampil di daftar kartu nyata. Mutan: angka diformat salah (titik/koma tertukar), argumen posisi diterima, `ya/tidak` terbalik, blok C terbuka tanpa audit, bukti basi diterima, `reader` dibuang, label model menggantikan nama kode.

## 8. Keputusan untuk Atha
| | Pertanyaan | Usul Claude |
|---|---|---|
| D1 | Yang Atha setujui | Contoh angka dan biaya (blok A-C), bukan patch |
| D2 | Contoh dengan angka sebagai argumen posisi | Ditolak penulis: "tulis argumennya dengan nama", supaya kartu terbaca |
| D3 | Pembaca patch | Claude, tercatat sebagai tahap (bukan manusia); model peninjau di dalam Argus ditunda sampai diuji dengan cacat ditanam |
| D4 | Isi uji T3 | Lima angka salah dalam bahasa domain (bagian 6), jawaban teks ke Claude |
| D5 | Label bahasa biasa untuk argumen (`labels`) | Ya, opsional, bertanda model, di samping nama kode |

## 9. Tidak dikerjakan di sini
Tombol (T4), model peninjau, mengubah pagar yang ada (sandbox, protected files), menilai aturan bisnis, mengganti kartu T2 yang sudah ada (kartu ini adalah halaman baru di atasnya; T2 tetap sebagai tampilan teknis).
