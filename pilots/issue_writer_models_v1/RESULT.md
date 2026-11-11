# Hasil: replay n = 3 dengan gerbang amandemen 4 (2026-11-11)

Sesuai `PLAN.md`: 6 job di `~/wt-exp/jobs-exp` (Argus `45ebe87`), semua giliran WRITTEN, tidak ada error harness, tidak ada
giliran > $0,10. Total tagihan ≈ $0,11 (Haiku ≈ $0,03, 1017 ≈ $0,08), sedikit di atas perkiraan PLAN ($0,06-0,10) karena
giliran issue 1017 kini 2-3× lebih mahal. Log `run_*`, issue `issue_*.txt`, balasan `reply_*_w2.txt`.

Clash nyata pada p4 w2 (7 tempat): timeline judul kolom (177/183/184), isi baris 216, baris sum 243; share judul kolom
132, 157, 224; share "sel terakhir = share" 107-109.

| job | model | w2 dtk | submit (ditolak) | touches → baris tes | clash nyata /7 | A: tanya/tandai data API | w2 $ |
|---|---|---|---|---|---|---|---|
| a401 | Haiku | 31,5 | 3 (2) | `stages`, `share` → 176 | 1 (share sel terakhir) | ya (pertanyaan) | 0,0082 |
| a402 | Haiku | 21,9 | 2 (1) | tanpa issue (balasan saja) | — (di balasan: share 132/133/157/158/225, timeline 216-218, sum 150) | **ya, menolak menulis issue sebelum dijawab** | 0,0060 |
| a403 | Haiku | 39,6 | 4 (3) | `['stage', 'kind', 'status', 'cost', 'share']` → 3 | 4 (share 132/157/224, timeline 184) | ya (pertanyaan) | 0,0107 |
| b401 | 1017 | 101,1 | 3 (2) | 8 touches → 470 | 5 | tidak | 0,0155 |
| b402 | 1017 | 222,1 | 4 (3) | 4 touches → 44 | 6 | tidak ("not read at all") | 0,0310 |
| b403 | 1017 | 132,0 | 4 (3) | 3 touches → 43 | 5 (+ most-expensive 118) | tidak (dibuat opsional) | 0,0270 |

Pembanding v0 (n = 1, tanpa gerbang): Haiku 20,6 dtk, 2 clash, A ya; 1017 52,3 dtk, 6 clash, A tidak.

**Penilaian Claude.**
- **A (kesalahan termahal p4): Haiku 3/3, 1017 0/3.** Konsisten dengan v0. 1017 tetap menulis seolah API sudah mengirim
  `started_at`/`ended_at`.
- **B: 1017 5-6/7, Haiku 1 dan 4 (plus satu giliran yang benar menahan issue).** Gerbang membantu Haiku sekali (a403: 4
  vs 2 di v0), tidak di a401.
- **Masalah gerbang yang terlihat.** (1) touches umum (`share`, `stages`) menghasilkan 176-698 baris di 44 file; daftar
  dipotong 40, jadi hampir tidak berguna, dan model lalu mempersempit touches sampai daftarnya kecil (a403 memakai
  teks daftar judul persis, justru menemukan 3 judul kolom; b402 698 → 44). (2) 1017 menyebut touches yang belum ada
  (`duration`, `started_at`) dan kehilangan satu submit. (3) giliran issue 1017 jadi 2-4× lebih lambat (101-222 dtk vs
  52 dtk v0) dan ±2× lebih mahal; Haiku naik 20 → 22-40 dtk.
- **Kecepatan dan biaya:** Haiku ±31 dtk dan ±$0,008 per giliran issue; 1017 ±152 dtk dan ±$0,025.

**Kesimpulan.** Masih tidak ada model yang lulus A dan B penuh. Haiku punya penilaian yang benar di 3/3 dan 5× lebih
cepat dan 3× lebih murah, tapi pencarian bentroknya masih tidak stabil; 1017 teliti soal bentrok tapi gagal A di semua
percobaan, dan kini lambat. Usul (keputusan Atha): (a) Haiku jadi default `issue_writer` sekarang (bentrok yang
terlewat masih tertangkap Claude sebelum Start dan oleh tes lama di job code; data API yang salah tidak), dan
(b) perbaiki gerbang: daftar > 40 baris ditolak sebagai "terlalu umum" dengan jumlah baris per file, minta touches yang
lebih sempit (a403 menunjukkan itu yang berhasil).
