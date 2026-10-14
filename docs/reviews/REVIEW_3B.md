# Permintaan review: fase 3b (penulis rekomendasi + angka berdasar)

Branch `m3-3b` dari `main` `b01eda3`. Kontrak: `docs/MILESTONE3_PLAN.md` bagian 3.6, yang disetujui GPT setelah dua
koreksi: angka di `action` ikut divalidasi, dan format angka kanonis plus aturan pembagi nol.
Bukti: `verification/verify-20261014T185029Z-aarch64.log` (commit `9dc370f`, working tree bersih, **524 lulus, 0 tes
sandbox di-skip**, VM OCI ARM). Semua tes memakai model palsu; belum ada run live (smoke di 3e).

## File utama
- `nodes/facts.py`:
  - tabel fakta dibuat harness (`build_facts`);
  - aturan angka (`check_numbers`);
  - validasi `SubmitRecommendations` (`validate_recommendations`);
  - render baris rekomendasi.
- `nodes/synthesize.py`:
  - penulis template (`impl: fake`) dan penulis model (`impl: llm`, role `writer`), lewat jalur render yang sama;
  - provenance di `laporan.provenance.json`.
- `nodes/evaluator.py`: cek baru `recs_grounded`.
- `harness/budget.py`: `llm_node_roles`, supaya penulis hanya dihitung biayanya kalau synthesize memakai LLM.
- `config.yaml`: role `writer` (Sonnet 5.5), `impl.synthesize`, `synthesize.attempts`,
  `llm_token_estimates.synthesize: 8000`.

## Klaim
1. **Model tidak pernah menentukan angka di Top 3 dan Tren.** Keduanya disalin harness dari hasil worker yang lolos
   validator. Model hanya mengisi rekomendasi.
2. **Setiap digit yang dirender diperiksa,** di `text` maupun `action`, termasuk digit yang menempel ke huruf
   (`Rp4200000`, `top3`):
   - Bulan `YYYY-MM` harus bulan dari fakta tren yang dirujuk.
   - Rupiah harus digit polos dan sama persis dengan fakta yang dirujuk.
   - Persen harus pakai `%`, 0 atau 1 desimal, dan sama dengan fakta persen yang dirujuk setelah dibulatkan half-up.
   - Selain itu (`12,5`, `4.200.000`, `72.40%`, `4200000.5`, angka yang tidak dirujuk) ditolak, dan pesan errornya
     menyebut format yang benar.
3. **Fakta turunan dihitung dengan `Decimal`.** Kalau penyebutnya nol, fakta itu tidak dimasukkan, jadi rujukan ke
   fakta itu gagal sebagai fakta tidak ada.
4. **Penulis:**
   - Output yang tidak valid dikembalikan ke model dengan error persisnya, maksimal `attempts` kali. Setelah itu
     laporan ditulis tanpa rekomendasi dan event `synthesize_failed` mencatat alasannya.
   - Balasan terpotong tidak dipakai dan tidak diulang.
   - Kalau output worker hilang, model tidak dipanggil.
   - Setiap balasan di-commit ke memo sebelum dipakai, jadi resume tidak membelinya lagi (dites, termasuk balasan
     terpotong yang di-replay).
5. **`recs_grounded`:**
   - Rekomendasi di laporan harus persis sama dengan provenance.
   - Setiap angka dicek ulang terhadap fakta yang **dihitung dari data**, bukan dari hasil worker. Rekomendasi yang
     konsisten dengan angka worker yang salah lolos validasi penulis, tapi gagal di evaluator (ada tesnya).
   - Provenance yang hilang atau rusak berarti gagal.
6. **Angka biaya M1/M2 tidak berubah.** Role penulis hanya dihitung kalau `impl.synthesize: llm` (dites).

## Bug lama yang ditemukan dan diperbaiki (dari 2c)
Memo menyimpan balasan model dengan key terurut (`sort_keys`). Kunci memo langkah berikutnya dihitung dari teks pesan
**tanpa** mengurutkan key. Akibatnya, setelah balasan di-replay, langkah sesudahnya tidak ditemukan di memo dan
**dibeli ulang**. Ini terjadi kalau argumen tool punya lebih dari satu key, misalnya `SubmitResult` dengan `value` dan
`notes`, atau nilai `data_check` yang berupa dict. Ini melanggar jaminan crash-resume di AGENTS.md.

Perbaikan: `_text` di `harness/llm.py` sekarang memakai `sort_keys`. Tes regresi ada di worker
(`test_replay_after_a_reply_with_multi_key_args_still_hits_the_memo`) dan di penulis. Keduanya gagal kalau
`sort_keys` dibuang.

## Perubahan tes lama (bukan pelonggaran)
- `test_fail_then_pass_uses_feedback`: di iterasi 1 rekomendasi template dibangun dari angka worker yang sengaja
  salah, jadi `recs_grounded` ikut gagal dengan `task: "report"`. Daftar output yang direvisi sekarang `["report",
  "top3", "trend"]`, dan masih dicek sama persis.
- Kasus 3a yang mengubah baris rekomendasi sekarang juga mengharapkan `recs_grounded`, karena barisnya tidak lagi sama
  dengan provenance. Himpunan cek yang gagal tetap dicek persis.
- `test_evaluator_*` di `test_audit_gaps.py` sekarang menulis provenance seperti synthesize.

## Tes dan mutasi
- 30 kasus tes baru di `tests/test_synthesize_llm.py`, plus kasus `recs_grounded` di `tests/test_evaluator_checks.py`.
- Mutasi: **24 dijalankan, 24 tertangkap**, ditambah regresi `sort_keys`. Yang dimutasi:
  - Aturan angka: `action` tidak divalidasi, angka menempel huruf dilewati, koma diterima, rupiah desimal diterima,
    dua desimal diterima, bulan tidak dicek terhadap rujukan, bulan tidak valid diterima, pembulatan selalu 1
    desimal.
  - Fakta: pembagi nol diberi nilai, float menggantikan `Decimal`, semua fakta dianggap dirujuk.
  - Validasi: duplikat diterima, jumlah rekomendasi tidak dibatasi.
  - Penulis: balasan terpotong dipakai, model dipanggil tanpa output worker, memo tidak dibaca, error tidak
    dikembalikan ke model, output tidak divalidasi.
  - `recs_grounded`: angka diabaikan, baris yang diedit diabaikan, lolos tanpa provenance.
  - Biaya dan role: penulis ditagih saat palsu atau tidak pernah ditagih, synthesize memakai role orchestrator.

## Batasan
- Belum ada run live. Estimasi `synthesize: 8000` token adalah titik awal dan dikoreksi dari ledger di smoke 3e.
- `recs_grounded` membuktikan angka berdasar, bukan bahwa rekomendasinya bagus. Itu tugas judge (3c).
- Aturan "tidak ada digit selain fakta" sengaja ketat. Model harus menulis "three", bukan "top 3". Kalau ini terlalu
  sering memicu percobaan ulang di run live, akan terlihat di event `recs_invalid`.
