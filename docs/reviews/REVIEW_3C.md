# Permintaan review: fase 3c (judge rubric, fail closed)

Branch `m3-3c` dari `main` `bd0a5fa`. Kontrak: `docs/MILESTONE3_PLAN.md` bagian 3.6.
Bukti: `verification/verify-20261014T194201Z-aarch64.log` (commit `8ce6ba2`, working tree bersih, **568 lulus, 0 tes
sandbox di-skip**, VM OCI ARM). Semua tes memakai model palsu. Tidak ada uang yang dipakai; kalibrasi live baru di 3d.

Koreksi: pesan commit `8ce6ba2` menyebut "42 test cases". Angka yang benar **34 kasus tes baru** (suite naik dari 534
ke 568).

## File utama
- `nodes/judge.py`: prompt judge, tool `SubmitVerdict`, `validate_verdict`, `make_judge`.
- `nodes/contract.py`: kriteria rubric di kontrak task (`SALES_REPORT["rubric"]`): `grounded`,
  `consistent_with_trend`, `actionable`, `not_restating`, `no_instructions`.
- `nodes/evaluator.py`: judge dijalankan setelah cek programatik dan menggantikan stub `recs_rubric`.
- `graph.py`: `impl.evaluator: fake | llm`.
- `config.yaml`:
  - role `evaluator` = `deepseek:deepseek-flash` (sebelumnya placeholder OpenAI), output 4096 token, karena thinking
    DeepSeek ikut dihitung sebagai output;
  - `judge.attempts: 2`, `llm_token_estimates.evaluator: 14000`, `llm_node_roles.evaluator`.

## Jalur fail-closed (syarat GPT sebelum uang kalibrasi dipakai)

| Jalur | Hasil | Tes |
|---|---|---|
| Verdict malformed: `criteria` bukan list, entri bukan objek, kriteria asing, ganda, atau hilang, `pass` bukan boolean, `reason` kosong, `evidence` kosong atau lebih dari 3, kutipan terlalu pendek | Error dikirim balik; setelah `attempts` kali, rubric gagal (`rubric_valid`) | 13 kasus |
| **Kutipan palsu:** tidak ada di teks laporan, termasuk kutipan dari tabel fakta | Tidak valid | 2 kasus + mutasi |
| Tidak memanggil tool, memanggil tool lain, atau dua verdict dalam satu balasan | Tidak valid, dihitung sebagai percobaan | 3 kasus |
| Balasan terpotong | Gagal, tidak dibaca, tidak diulang | 1 kasus |
| Kegagalan API: 400, atau 500 terus-menerus setelah retry wrapper | Gagal (`llm_failed`), tidak diulang di level judge | 2 kasus |
| Budget node habis | Ditolak sebelum dikirim, rubric gagal | 1 kasus |
| **Injeksi:** laporan berisi `</report>` (juga variasi spasi dan huruf besar) dan perintah | Laporan tidak bisa menutup bloknya sendiri. Prompt menyatakan isi blok adalah data, dan instruksi di dalamnya membuat `no_instructions` gagal | 2 kasus |
| Judge tidak pernah memberi verdict yang bisa dipakai, di graph penuh | Run tidak pernah `DONE` | 1 kasus |

Kutipan dicocokkan setelah normalisasi spasi. Kutipan yang terverifikasi hanya membuktikan teksnya ada di laporan,
bukan bahwa keputusan judge benar; itu diukur oleh kalibrasi 3d.

## Integrasi evaluator
- **Judge hanya dijalankan kalau semua cek programatik lulus.** Laporan yang angkanya salah tidak dibayar ke judge
  (tes: model tidak dipanggil, event `rubric_skipped`), dan rubric tidak pernah bisa meloloskan laporan yang ditolak
  kode.
- Kriteria yang gagal menjadi failure `report:rubric_<id>`, dengan alasan dan kutipan judge sebagai feedback ke
  orchestrator.
- `score` hanya menghitung cek programatik. Rubric dilaporkan terpisah (`eval_verdict.rubric`) dan harus lulus juga.
- Biaya judge dilaporkan ke budget (`tokens_used`, `usd_used`), dan role `evaluator` hanya ditagih kalau
  `impl.evaluator: llm`. Angka M1/M2 tidak berubah (dites).
- Crash-resume: setiap balasan judge di-commit ke memo sebelum dipakai. Kuncinya memuat laporan, fakta, kriteria, dan
  model; laporan yang berubah dinilai ulang (dites).

## Mutasi: 21 dijalankan, 21 tertangkap
- **Validasi verdict:** kutipan tidak dicek terhadap laporan, tanpa normalisasi spasi, kriteria hilang diterima,
  kriteria ganda diterima, kriteria asing diterima, `pass` berupa string diterima, `reason` kosong diterima.
- **Judge:** balasan terpotong dibaca, laporan bisa menutup bloknya sendiri, aturan "data tidak tepercaya" dibuang
  dari prompt, memo tidak dibaca, kegagalan API diulang, budget habis diulang, kriteria gagal tetap dianggap lulus.
- **Evaluator:** judge dibayar walau kode sudah menolak laporan, stub dibiarkan di samping judge, verdict tak terpakai
  diabaikan, `score` ikut menghitung rubric, biaya judge tidak dilaporkan.
- **Graph dan biaya:** judge tidak pernah dibangun, judge tidak ditagih.

Skema tool yang dikirim ke provider memakai nama field `pass` (dicek lewat `convert_to_openai_tool`).

## Batasan
- **Belum ada run live dengan DeepSeek.** Jalur tool call DeepSeek sudah lulus di `smoke_models.py`, tapi skema
  `SubmitVerdict` yang lebih besar dengan mode thinking belum pernah dikirim. Run pertama adalah kalibrasi 3d.
- `judge.attempts: 2` dan estimasi 14.000 token adalah titik awal, dikoreksi dari ledger kalibrasi.
- Ketahanan judge terhadap injeksi yang sebenarnya hanya bisa diukur dengan model sungguhan (kategori injeksi di
  set kalibrasi). Tes di sini membuktikan struktur pertahanannya, bukan perilaku model.

## Langkah berikutnya (3d)
Fixture kalibrasi (±35 laporan, bagian 3.4) dan runner kalibrasi dengan batas $1.00, dijalankan dengan model palsu
dulu. Run live hanya setelah GPT menyetujui fixture dan aturan penilaian. Ambang tidak diubah setelah melihat hasil.
