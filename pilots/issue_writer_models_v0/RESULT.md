# Hasil: model penulis issue lewat OpenRouter (2026-11-10)

Replay dua giliran p4 (repo argus-viewer `f68bc4c`, pesan Atha persis), satu kali per model, dari `~/wt-exp` (main
`7c5734c`, config lokal: role `issue_writer` per model, tanpa param thinking DeepSeek), jobs di `~/wt-exp/jobs-exp`.
Log `run_*.log`, issue `issue_*.txt`. n = 1 per model: sinyal kasar, bukan ukuran pasti.

| model | w1 (tanya) | w2 (issue) | submit ditolak | clash | A: tandai data API belum pasti | tagihan nyata w1+w2 |
|---|---|---|---|---|---|---|
| deepseek-flash langsung (p4, pembanding) | 7,9 dtk / 4 | 49,7 dtk / 14 | 0 | 5 | tidak ("the api now carries") | $0,0091 |
| V4.1 Flash 1017 (DeepInfra) | 7,2 dtk / 5 | 52,3 dtk / 12 | 1 (paragraf Tests) | 6 | tidak (waktu dibuat opsional, "-" bila tak ada) | $0,0065 (ledger batas atas $0,0132) |
| GPT-6 Luna (OpenAI) | 15,2 dtk / 6 | **89,1 dtk** / 11 (37 langkah) | 0 | 6 | tidak | $0,0082 |
| Haiku 5.5 (Anthropic) | 7,7 dtk / 4 | **20,6 dtk** / 5 | 0 | 2 | **ya**: di balasan ("field ini tidak ditemukan di kode frontend, API harus mengirimkannya") dan sebagai pertanyaan | $0,0065 |

Gerbang #413 bekerja di ketiganya: tidak ada klaim "keep passing unchanged", daftar "A human loosens these existing
tests first" ditulis harness. Haiku tidak kena batas input 40.000 (gateway). Upstream sesuai pin (DeepInfra, OpenAI,
Anthropic).

**Penilaian Claude.**
- A (data lintas repo): hanya **Haiku** yang menandainya, dan bertanya ke human. Ini kegagalan termahal p4.
- B (bentrok): 1017 dan Luna menemukan 6 (semua tempat daftar kolom dan isi baris), Haiku 2 (sel baris timeline 216 dan
  sel terakhir share 109; terlewat daftar judul kolom share 132/157/224 dan baris sum). Haiku membaca jauh lebih sedikit
  (8 langkah vs 19/37).
- Kecepatan: Haiku tercepat (giliran issue 2,4× lebih cepat dari flash), Luna terlambat.
- Biaya: setara (±$0,006-0,009 per dua giliran); 1017 DeepInfra sekarang ~30% lebih murah dari flash langsung.

**Kesimpulan.** Tidak ada model yang lulus A dan B penuh. Haiku punya penilaian terbaik (A) dan paling cepat tapi
pencarian bentroknya dangkal; 1017 dan Luna teliti mencari bentrok tapi menegaskan hal yang tidak dicek. Usul berikut
(belum dikerjakan, keputusan Atha): (1) Haiku sebagai penulis issue **dengan** pencarian bentrok yang dipaksa harness
(daftar tes yang memuat selector/teks yang disentuh, sebelum SubmitIssue), atau (2) 1017 tetap, plus instruksi/gerbang
"sebut asumsi data dari repo lain". Ulangi replay (n ≥ 3) sebelum mengganti default.
