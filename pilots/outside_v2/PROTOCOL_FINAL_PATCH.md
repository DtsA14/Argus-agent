# Protokol batch 3: approve atas patch AKHIR, dengan cek buta (urutan Fable 2026-11-13, butir 2)

Status: draf 2026-11-13, menunggu persetujuan Atha; belum dipakai. Alat: `final_patch_tool.py` (di folder ini; bukan bagian harness).

## Masalah (bukti)

Di batch 1 dan 2 pembacaan Claude "sebelum approve" hanya atas **rencana draf**. Dua kali rencana yang masuk akal menghasilkan patch akhir yang salah: more-itertools#1344 (batch 1, kunci panjang modulo 7) dan boltons#393/Q02
(batch 2, traversal ditulis ulang, nilai buta C). Pembacaan atas patch akhir juga luput sekali (boltons#343, regresi metode publik). Angka "menit manusia per A" juga tidak pernah terukur dengan jujur.

## Aturan

0. **Arti approve (Atha 2026-11-13):** approve = patch akhir di-apply **apa adanya**, tanpa satu baris pun diubah manusia; yang masih butuh perapian (nilai B: mode, letak tes, pembungkus exception) adalah reject, dengan `reason` diawali `cuma perapian:` agar bisa dihitung terpisah. Berlaku sama untuk verdict Claude dan jawaban Atha.
1. **Draf:** seperti sekarang, setiap draf yang diterima harness di-approve (aturan batch 1 dan 2). Claude tidak lagi menulis "on-target" atas rencana sebagai verdict; itu catatan, bukan keputusan.
2. **Verdict Claude jatuh pada patch akhir** (stage agen terakhir, paket review yang valid): Claude membaca issue, `changes.patch` seluruhnya, `tests.md`, dan baris R1/R1b (`stage status`) lalu menulis per job satu baris di `verdicts_claude.json`:
   `{"verdict": "approve"|"reject", "reason": "<satu baris>", "read": "final patch", "human_minutes": 0}`; job tanpa paket review yang valid (`REVIEW_INVALID`) ditulis `{"verdict": "no final patch"}`. Sebelum menulis, Claude memeriksa: tes yang ditambah ikut diubah?, tanda tangan publik berubah?, perubahan di luar berkas yang
   disebut issue?, perilaku lain di berkas yang sama? Verdict ditulis **sebelum** nilai buta, hasil tes pemelihara, dan hasil judge (judge mati default) dilihat.
3. **Dicatat apa adanya:** "0 menit manusia, disetujui model". Waktu Atha tidak dihitung ke job; pembacaan Atha atas sampel dihitung terpisah (butir 5) sebagai cek, bukan sebagai biaya per job.
4. **Segel:** `final_patch_tool.py seal <folder batch>` memeriksa satu verdict per job (`no final patch` wajib dan hanya untuk job `REVIEW_INVALID`) lalu mencatat sha256 `verdicts_claude.json` di `SEALED.json`; kedua berkas di-commit **sebelum** langkah berikutnya (`pick` menolak bila belum di-commit atau berbeda dari HEAD). Verdict yang berubah sesudah segel membuat `pick` dan `compare` menolak.
5. **Sampel buta untuk Atha:** sesudah segel di-commit, Atha menulis satu nonce (kata atau angka bebas, tidak diberitahukan sebelumnya) dan menjalankan `pick <folder batch> <nonce>`. `pick` mengambil `ceil(n/3)` job (n = job dengan patch akhir yang valid; 8 → 3) secara acak. Benihnya sha256 dari daftar `label:sha256(changes.patch)`, sha256 verdict yang disegel, dan nonce: penulis verdict tidak bisa tahu sampelnya sebelum menulis (nonce belum ada), dan verdict tidak bisa digiling karena sudah terkunci sebelum nonce. Nonce dan benih dicatat di `packet_key.json`; `pick` kedua dengan nonce lain ditolak (nonce yang sama menghasilkan sampel yang sama). Job `no final patch` tidak ikut sampel. Paket `packet/Rxx.md` (paket lama dihapus dulu) berisi issue, patch akhir dan
   `tests.md` dengan kode acak; tanpa verdict Claude, tanpa judge, tanpa nilai, tanpa nama job. Atha menjawab `approve` atau `reject` per paket di `atha_verdicts.json` tanpa melihat verdict Claude.
6. **Hitung:** `compare` mencetak berapa yang dibaca dan berapa yang dibalik (verdict Claude ≠ Atha). Dilaporkan bersama kedua angka biasa (apa adanya; artefak mode dibuang) dan nilai buta A/B/C akhir.

## Batas yang diketahui

- Ini kalibrasi pembacaan Claude terhadap pembacaan Atha, bukan penilai ketiga yang independen. Nilai buta A/B/C (dua model, dengan Atha menilai 3 sampai 4 sebagai jangkar) tetap yang menentukan vonis.
- Benih bisa dihitung ulang siapa pun sesudah nonce diketahui; yang dijaga adalah urutan: verdict disegel dan di-commit (cap waktu git), baru nonce ditulis. Nonce harus dipilih Atha sendiri, bukan oleh sesi yang menulis verdict.
- Penolakan `pick` kedua bersandar pada `packet_key.json` di folder batch; menghapus berkas itu membukanya lagi. Commit `packet_key.json` segera sesudah `pick`.
- Sampel 3 dari 8: nol pembalikan hanya membuktikan "berfungsi" (batas atas kasar 3/n); satu pembalikan sudah informatif.
- Patch tanpa paket valid (`REVIEW_INVALID`) tidak punya patch akhir untuk dibaca: dicatat `no final patch`, bukan verdict, dan tidak ikut sampel; `compare` melaporkan jumlahnya terpisah.

## Dicoba

Dry run kedua 2026-11-13 (job palsu, 8 job, satu `REVIEW_INVALID`, di repo git sementara): `seal` menolak verdict `approve` untuk job invalid; `pick` menolak sebelum commit, dengan nonce kosong, dengan nonce kedua, dan sesudah verdict diubah; dua nonce berbeda memberi sampel berbeda, nonce yang sama memberi sampel yang sama; job invalid tidak pernah terpilih; `compare` melaporkan 3 dari 7 dibaca, 1 tanpa patch akhir.

Dry run 2026-11-13 pada delapan patch batch 2 (verdict palsu): `pick` menolak sebelum disegel dan setelah berkas diubah; sesudah segel memilih 3 dari 8; `compare` menghitung pembalikan.
