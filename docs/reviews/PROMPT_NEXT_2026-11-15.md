# Prompt untuk sesi berikutnya (sesudah arah 2026-11-15 dan vonis fase 2)

Tempel isi bagian "PROMPT" di bawah ke sesi Claude yang baru. Ditulis 2026-11-15 sesudah #546 (arah) dan PR vonis fase 2.

---

## PROMPT

Kamu melanjutkan Argus. Atha menulis bahasa Indonesia santai; jawab dalam bahasa Indonesia yang singkat, mulai dari jawabannya, jujur
soal apa yang sudah terbukti dan apa yang belum. Dia sering membaca dari HP.

### 1. Baca dulu (urut, jangan dilewati)

1. `AGENTS.md` (jaminan, jalur ketat, jalur penasihat, aturan chat).
2. `PENDING.md` seluruhnya (bagian "Arah" dan "Keputusan Atha yang ditunggu" paling penting).
3. `docs/Reconciliation.md` bagian 0, 6 dan 7.

### 2. Arah (sudah diputuskan Atha 2026-11-15, jangan dibuka ulang)

"Spesialis di sifatnya, generalis di permukaannya." Kekuatan: "agen yang bisa ditinggal: kerjanya terbukti, biayanya terkunci."
Inti = kerja terbukti, biaya terkunci, tanpa Claude di tengah. Permukaan = chat di `127.0.0.1:8711`; kemampuan ditambah satu per
satu, hanya bila bisa diberi gerbang atau kartu konfirmasi. Fase 2 (repo luar) sudah ditutup: "benar menurut tes, belum rapi menurut
rubrik"; garis A/B/C tidak dipakai lagi, ukurannya kini persen issue yang sampai staging tanpa campur tangan Claude. Atha bekerja
kurang lebih 8 jam per hari, tergantung limit Claude.

Atha sendiri bilang keputusannya sering berubah di tengah jalan. Bila dia mengusulkan arah atau kemampuan baru di tengah sesi, jangan
langsung dikerjakan: catat di `PENDING.md`, katakan di mana tempatnya terhadap arah di atas, dan tanyakan apakah ini mengganti
pekerjaan yang sedang berjalan.

### 3. Yang harus diputuskan Atha lebih dulu (tanyakan, satu per satu, dengan saranmu)

1. **Urutan inti.** Usul yang tercatat: VF O1 kenari dan nonce → `argus apply` → antrean PRD; di permukaan: assistant atas Argus
   sendiri. Antrean PRD, operator rantai dan pekerjaan riset baru tidak dimulai sampai ini diputuskan.
2. **Aturan main arah.** Satu angka di repo, titik cek tetap untuk mengubah arah, jatah eksplorasi (dihitung ulang dengan 8 jam per
   hari), log permintaan yang chat belum bisa.
3. **"Daya saing" untuk siapa:** portofolio/karier atau produk dengan pengguna lain.

Catat setiap jawaban di `PENDING.md` dan `docs/Reconciliation.md` bagian 7 dengan tanggal, dengan kata-kata Atha.

### 4. Pekerjaan pertama sesudah urutan diputuskan

Bila Atha menerima urutan yang diusulkan, mulai dari **VF O1 kenari dan nonce** (`docs/reviews/SPEC_VF_CANARY.md`;
`tests/test_vf_forger.py` masih xfail strict; fixture di `fixtures/forgers/`). Ini jalur ketat: spek dibaca dan disetujui Atha, tes
dulu, review, mutan, `bash scripts/precheck.sh`, satu `verify_at`, lalu "merge" dari Atha. Jangan memulai PR jalur ketat kedua
sebelum yang pertama selesai. Sampai kenari dan nonce ada: jangan apply job `DONE` tanpa dibaca.

Sejajar dan kecil, bila Atha mau: angka "persen issue sampai staging tanpa campur tangan Claude" di `scripts/scoreboard.py` (cek dulu
apa yang sudah dicatat `job.json` tentang siapa yang approve dan apply; jangan mengarang angka, angka di dokumen status disalin dari
berkas di `verification/`).

### 5. Batas

- Uang, key, staging, restart layanan dan "go live" selalu atas kata Atha, per tindakan.
- Tabel milestone dan ADR di `docs/Reconciliation.md` belum direkonsiliasi terhadap kode sesudah #444; jangan mengutipnya sebagai
  keadaan kode sekarang tanpa mengecek.
- Dokumen di `docs/reviews/` adalah riwayat; jangan diubah, tambahkan berkas baru.
