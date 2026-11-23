# Prioritas perbaikan dari pilot NEXUS-lite

Dibuat 2026-11-23 dari temuan pilot NEXUS-lite (16 issue, empat tahap; laporan: https://claude.ai/artifact/VLV3GLLrUSwcNGASRn42PD). Berkas ini **terpisah dari `PENDING.md`**: PENDING menyimpan semua butir, berkas ini hanya urutan kerjanya. Butir lama tetap di PENDING dengan rincian; di sini hanya ringkasan, alasan urutan, ruang lingkup, dan status.

**Ukuran urutan:** seberapa sering membuat pekerjaan berhenti dan butuh Claude (penghalang "bisa ditinggal"), dibagi besar kerjanya. Datanya satu pilot, 16 issue, jadi angkanya kecil; pemakaian nyata tiga hari (mulai 2026-11-23) bisa mengubah urutan.

**Cara kerja:** berurutan menurut tabel; yang tidak saling bergantung boleh dikerjakan bersamaan. Jalur ketat (spek, tinjauan Opus read-only, mutan sekali, precheck, satu `verify_at`) untuk kode yang bisa merugikan; jalur ringan untuk tampilan, alat uji, dan dokumen. Perubahan config (batas, model) butuh kata Atha.

| # | Butir | Bukti dari pilot | Kerja | Jalur | Perlu kata Atha | Status |
|---|---|---|---|---|---|---|
| 1 | Blocker pembaca hanya dengan bukti | 3 dari 16 issue berhenti palsu (Markdown, `parseTags`, jenis Link); tiap kali sekitar $0,10 dan 10–15 menit, Claude harus membuktikan keberatan salah | sedang | ketat | tidak (prompt dan aturan, bukan config) | [x] selesai 2026-11-23 (#697): rev 1 (cek kutipan, ubah prompt) NO-GO dari tinjauan Opus; dibangun O3 (konteks: file yang dimodifikasi dan diimpor patch, kondisi sebelum patch). Uji ulang pembaca asli: patch issue 3 4/4 `ok`; patch Markdown 3/3 `ok` setelah batas file dimodifikasi dinaikkan ke 20 KB (sebelumnya terpotong di 8 KB dan Hy4 memberi blocker 2/2). Mutan 76/78 (2 setara) |
| 2 | Kegagalan penyedia tampil dengan kode dan sebabnya; biaya $0 hanya untuk penolakan pasti (402, 401) | 402 tampil "the model provider failed"; Claude salah diagnosis "saldo habis" | kecil | ketat (menyentuh pencatatan biaya) | tidak | [x] selesai 2026-11-23 (#695 tampilan status HTTP; #698 biaya 401/402 = $0, putusan Atha "429 ya"; 17/17 mutan) |
| 3 | Pembaca terpotong pada diff besar | 1 kali (6 berkas), memblokir apply; akan terulang karena UI memberi diff besar | kecil sampai sedang | ketat | **ya** bila yang diubah batas keluaran (config) | [x] selesai 2026-11-23 (#696, atas kata Atha "No.3 naikan batas"): `--max-output` 64000 -> 100000; belum teruji pada diff besar berikutnya (DeepSeek bisa tetap terpotong) |
| 4 | Jalan pendek setelah agen gagal atau diinterupsi (`redraft` untuk agen diinterupsi; berhenti setelah `report_conflict`) | 2 kejadian, sekitar 12–14 menit dan $0,07–0,22 | kecil | ketat | tidak | [ ] |
| 5 | Kecepatan drafter (85–89% waktu = model berpikir) | tahap 4: 4 jam 9 menit prompt-ke-apply, 99 menit mesin; tidak membuat berhenti | sedang, perlu diukur dulu | ketat bila config | **ya** (reasoning effort atau model = config) | [ ] sedang diukur 2026-11-23: effort medium vs bawaan pada issue 3 dan 4 tahap 4 (atas kata Atha); hasil dan keputusan config menyusul |
| 6 | Gerbang umum "tes harus bisa lulus" (green probe) | tes mustahil 2 kali, pola berbeda; pola 1 ditutup (#684), kerugian pola 2 dibatasi A' (#689) | besar | ketat | tidak | [ ] |
| 7 | Aturan mekanis profil anggaran | salah 2 dari 5 draf awal; tahap 4 benar 5 dari 5 | kecil | ketat | tidak | [ ] |
| 8 | Konsistensi antar issue di PRD (gerbang mesin) | 2 kontradiksi, keduanya tertangkap daftar periksa Claude, bukan mesin | besar | ketat | tidak | [ ] |
| 9 | Batas `prd_writer.message_max` 4.000 karakter | prompt berbahasa biasa ±2.000 karakter: tidak lagi masalah | kecil | config | **ya** | ditunda |

## Rencana pengerjaan

- **Gelombang A (bersamaan):** nomor 2 (kecil, berdiri sendiri) dan spek nomor 1 (tinjauan Opus read-only) tidak saling bergantung.
- **Gelombang B:** bangun nomor 1 setelah tinjauan; nomor 3 (pecah diff per berkas tidak butuh config; menaikkan batas butuh kata Atha).
- **Gelombang C:** nomor 4, lalu ukur nomor 5 (tanpa mengubah config) dan tanyakan Atha.
- **Menunggu data pakai:** 6 sampai 9.

Tiap butir selesai: centang, tulis nomor PR dan hasil verifikasinya di kolom Status, dan perbarui butir terkait di `PENDING.md`.
