# Prompt untuk uji lepas tangan (dua PRD pilot yang tersisa)

Tempel isi bagian "PROMPT" ke sesi Claude yang baru di VM Argus (`~/Argus-agent`). Ditulis 2026-11-16 sesudah VF O1, `argus apply`,
antrean dan penulis PRD ter-merge. Butirnya di `PENDING.md`: "Uji lepas tangan" (Inti 2). Bagian "Contoh keinginan" di bawah hanya
contoh bentuk; keinginan yang dipakai harus tulisan Atha sendiri.

---

## PROMPT

Kita menjalankan **uji lepas tangan** Argus. Tujuannya satu angka: berapa kali gue butuh Claude supaya satu keinginan sampai
`APPLIED`. Jadi di sesi ini peranmu dibalik: kamu **tangan dan pencatat, bukan pembaca dan penilai**.

### 1. Baca dulu

`AGENTS.md`, lalu di `PENDING.md` bagian "Arah" dan butir "Uji lepas tangan", lalu `pilots/prd_writer_v0/RESULT.md` (bentuk hasil
pilot pertama). Jangan membaca kode repo target.

### 2. Aturan peran (ini inti ujinya)

Yang BOLEH kamu lakukan tanpa dihitung:
- mengetik perintah `argus` persis yang gue sebut, atau perintah berikutnya yang dicetak `status`, sesudah gue bilang jalankan;
- menampilkan keluaran apa adanya: `status`, PRD, issue, draf, `changes.patch`, tanpa ringkasan, tanpa komentar, tanpa penekanan;
- menjawab "perintah apa untuk langkah X" bila jawabannya ada di `--help` atau di `status`;
- mencatat waktu tiap gerbang (kapan Argus menunggu gue, kapan gue memutuskan).

Yang DIHITUNG sebagai satu campur tangan Claude (catat: jam, langkah, apa yang gue minta, kenapa gue butuh):
- kamu membaca PRD, issue, draf atau patch dan memberi penilaian, ringkasan atau saran;
- kamu memperbaiki apa pun: issue, tes, kode, konfigurasi, environment, repo target;
- kamu menyarankan approve, reject, retry, redraft atau reply, atau menulis isi `reply`;
- kamu menjelaskan arti sebuah kegagalan lebih dari mengutip pesannya.

Bila gue meminta salah satu dari itu, **lakukan**, tapi bilang dulu satu kalimat "ini dihitung satu campur tangan" dan catat. Jangan
menawarkannya. Bila kamu melihat sesuatu yang salah dan gue tidak bertanya, **diam dan catat** di catatan tertutup (bagian 4);
pengecualiannya hanya tiga: uang akan melewati batas yang gue setujui, perintah akan menyentuh key, staging atau layanan, atau patch
akan di-apply ke repo yang salah. Untuk tiga itu berhenti dan bilang.

### 3. Jalannya

1. Gue menulis keinginan dengan kata-kata gue sendiri (kasar tidak apa-apa), cukup besar untuk beberapa issue berurutan. Simpan
   persis sebagai `message.txt` di folder pilot; jangan dirapikan.
2. `argus prd new` di repo yang gue sebut (penulis PRD: Haiku, paling banyak 5 issue, giliran $0,30, job $1,50). Bila penulis
   bertanya, gue yang menjawab; kamu meneruskan jawaban gue persis.
3. `argus prd check`, lalu gue membaca PRD dan issue sendiri dan memutuskan `prd approve --sha`.
4. `argus queue go` (gue menyebut jumlah uangnya), lalu `queue step` berulang. Di tiap draf gue membaca dan memutuskan
   `approve --sha`; di tiap patch gue membaca dan memutuskan `apply --read-sha`. Aturan "jangan apply job `DONE` tanpa dibaca"
   dipenuhi oleh gue, bukan oleh kamu.
5. Antrean berhenti di kegagalan pertama. Itu hasil, bukan gangguan: catat di mana dan kenapa, tanyakan gue mau apa, jangan
   memperbaiki sendiri.
6. Tanpa push, tanpa deploy, tanpa staging di uji ini. Antrean berakhir di `APPLIED`.

Dua PRD, satu per satu. Yang kedua baru dimulai sesudah `RESULT.md` yang pertama ditulis.

### 4. Sesudah tiap PRD selesai atau berhenti

Baru sekarang kamu boleh membaca. Tulis `pilots/handsoff_v0/prd<n>/RESULT.md` (bentuk seperti pilot sebelumnya, n = 1, dipisah dari
angka papan skor):
- tabel langkah: job atau antrean, hasil, biaya dari ledger;
- **campur tangan Claude: jumlah per issue dan daftar lengkapnya**; issue dengan nol campur tangan disebut satu per satu;
- menit gue per gerbang (menunggu dan memutuskan), dan apakah gue membaca patch sampai habis (gue yang bilang, jangan ditebak);
- apakah aturan urutan antar-issue (`creates` sebelum `touches`) benar-benar jalan;
- **pembanding, ditandai terpisah:** bacaanmu sendiri atas tiap draf dan patch sesudah semuanya `APPLIED`: apa yang akan kamu tolak
  atau perbaiki, dan apakah gue menangkapnya. Ini mengukur apa yang lolos tanpa Claude;
- catatan tertutupmu dari bagian 2;
- "yang tidak ditunjukkan".

Lalu perbarui butir "Uji lepas tangan" di `PENDING.md` dengan angka dari `RESULT.md` itu (angka tanpa berkas sumber tidak ditulis),
dan buka PR dokumen dan data.

### 5. Batas

- Uang: hanya di dalam batas yang gue sebut di `queue go`. Key dari `--key-file`; jangan pernah ditampilkan.
- Jangan mengubah kode Argus di sesi ini. Bug Argus yang ketemu dicatat sebagai temuan, bukan diperbaiki.
- Jangan menulis keinginan, issue atau jawaban untuk gue. Bila gue minta contoh keinginan, itu satu campur tangan.

---

## Contoh keinginan (bentuk saja; ganti dengan kata-kata dan kebutuhan Atha sendiri)

Yang membuat sebuah keinginan cocok untuk uji ini: satu tujuan yang butuh dua sampai empat perubahan berurutan (yang kedua memakai
hasil yang pertama), hanya backend atau hanya satu repo, hasilnya bisa dicek dengan tes, dan ditulis seperti orang bicara, tanpa nama
fungsi atau berkas.

Contoh bentuk untuk `athena` (backend saja, sandbox belum punya node):

> Gue pengen bisa lihat rekap jurnal per minggu. Tiap minggu ada berapa posisi yang ditutup, berapa yang untung dan rugi, dan total
> hasilnya. Terus gue pengen bisa ambil rekap itu lewat API buat rentang tanggal tertentu, dan ada versi CSV-nya buat gue buka di
> spreadsheet. Minggu dihitung Senin sampai Jumat waktu Jakarta.

Contoh bentuk untuk `argus-ledger`:

> Di ledger gue pengen tahu job mana yang paling boros. Tambahin hitungan biaya per job dibanding batasnya, tandain yang kepake lebih
> dari 80% dari batas, terus bikin satu endpoint yang ngasih daftar job itu diurutkan dari yang paling boros, bisa difilter per
> minggu.

Keduanya sengaja tidak menyebut angka contoh atau nama endpoint: itu pekerjaan penulis PRD, dan mutunya bagian dari yang diukur.
