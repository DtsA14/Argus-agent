# Protokol batch 3: approve atas patch AKHIR, dengan cek buta (urutan Fable 2026-11-13, butir 2)

Status: draf 2026-11-13, menunggu persetujuan Atha; belum dipakai. Alat: `final_patch_tool.py` (di folder ini; bukan bagian harness).

## Masalah (bukti)

Di batch 1 dan 2 pembacaan Claude "sebelum approve" hanya atas **rencana draf**. Dua kali rencana yang masuk akal menghasilkan patch akhir yang salah: more-itertools#1344 (batch 1, kunci panjang modulo 7) dan boltons#393/Q02
(batch 2, traversal ditulis ulang, nilai buta C). Pembacaan atas patch akhir juga luput sekali (boltons#343, regresi metode publik). Angka "menit manusia per A" juga tidak pernah terukur dengan jujur.

## Aturan

1. **Draf:** seperti sekarang, setiap draf yang diterima harness di-approve (aturan batch 1 dan 2). Claude tidak lagi menulis "on-target" atas rencana sebagai verdict; itu catatan, bukan keputusan.
2. **Verdict Claude jatuh pada patch akhir** (stage agen terakhir, paket review yang valid): Claude membaca issue, `changes.patch` seluruhnya, `tests.md`, dan baris R1/R1b (`stage status`) lalu menulis per job satu baris di `verdicts_claude.json`:
   `{"verdict": "approve"|"reject", "reason": "<satu baris>", "read": "final patch", "human_minutes": 0}`. Sebelum menulis, Claude memeriksa: tes yang ditambah ikut diubah?, tanda tangan publik berubah?, perubahan di luar berkas yang
   disebut issue?, perilaku lain di berkas yang sama? Verdict ditulis **sebelum** nilai buta, hasil tes pemelihara, dan hasil judge (judge mati default) dilihat.
3. **Dicatat apa adanya:** "0 menit manusia, disetujui model". Waktu Atha tidak dihitung ke job; pembacaan Atha atas sampel dihitung terpisah (butir 5) sebagai cek, bukan sebagai biaya per job.
4. **Segel:** `final_patch_tool.py seal <folder batch>` mencatat sha256 `verdicts_claude.json` di `SEALED.json`; berkas itu di-commit **sebelum** langkah berikutnya. Verdict yang berubah sesudah segel membuat `pick` dan `compare` menolak.
5. **Sampel buta untuk Atha:** `pick` mengambil `ceil(n/3)` job (n=8 → 3) secara acak. Benihnya sha256 dari daftar `label:sha256(changes.patch)` semua patch akhir, bukan dari verdict apa pun, jadi tidak bisa digiling lewat verdict. Paket `packet/Rxx.md` berisi issue, patch akhir dan
   `tests.md` dengan kode acak; tanpa verdict Claude, tanpa judge, tanpa nilai, tanpa nama job. Atha menjawab `approve` atau `reject` per paket di `atha_verdicts.json` tanpa melihat verdict Claude.
6. **Hitung:** `compare` mencetak berapa yang dibaca dan berapa yang dibalik (verdict Claude ≠ Atha). Dilaporkan bersama kedua angka biasa (apa adanya; artefak mode dibuang) dan nilai buta A/B/C akhir.

## Batas yang diketahui

- Atha tahu kodenya bukan dari model yang lain: ini kalibrasi Claude terhadap Atha, bukan penilai independen. Nilai buta A/B/C (dua model) tetap yang menentukan vonis.
- Benih bisa dihitung siapa pun yang punya patch; urutan dijaga oleh segel yang di-commit dulu (cap waktu git), bukan oleh kerahasiaan benih.
- Sampel 3 dari 8: nol pembalikan hanya membuktikan "berfungsi" (batas atas kasar 3/n); satu pembalikan sudah informatif.
- Patch tanpa paket valid (`REVIEW_INVALID`) tidak punya patch akhir untuk dibaca: dicatat `no final patch`, bukan verdict, dan tidak ikut sampel.

## Dicoba

Dry run 2026-11-13 pada delapan patch batch 2 (verdict palsu): `pick` menolak sebelum disegel dan setelah berkas diubah; sesudah segel memilih 3 dari 8; `compare` menghitung pembalikan.
