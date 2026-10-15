# Acceptance criteria untuk task umum (draf untuk review)

Status: **draf**, 2026-10-15. Dokumen ini hanya kontrak dan rencana: tidak ada kode, config, atau run live yang
berubah. Setelah direview, implementasinya dipecah ke PR kecil, masing-masing dengan tes yang gagal kalau jaminannya
dilanggar (AGENTS.md). Pertanyaan yang dijawab: kapan Argus boleh menyatakan sebuah task **selesai** kalau tidak ada
ground truth yang bisa dihitung ulang seperti di demo CSV?

## 1. Yang sudah ada, dan yang tidak ikut ke task umum

Di demo CSV, `DONE` hanya keluar dari evaluator, bukan dari klaim agen:
- kontrak task ditulis harness (`nodes/contract.py`: `SALES_REPORT`), plan divalidasi harness (`nodes/plan.py`);
- semua cek programatik (`run_checks`) harus lulus; skornya dihitung dari cek, bukan dari judge;
- judge rubric hanya berjalan kalau semua cek lulus, fail closed, dan tidak pernah bisa meloloskan laporan yang
  ditolak kode;
- budget ditegakkan sebelum setiap panggilan; ledger, memo, dan crash-resume menjaga supaya tidak ada pembelian ulang.

Yang **tidak** ikut ke task umum:
- **Ground truth.** `dataset.truth()` menghitung ulang jawaban dari data. Task umum (memperbaiki bug, menulis dokumen)
  tidak punya jawaban tunggal yang bisa dihitung.
- **Format tetap.** `run_checks` tahu persis bagian dan baris `laporan.md`. Task umum punya artefak yang berbeda-beda.
- **Kontrak tetap di kode.** `graph.py` mengimpor `SALES_REPORT` langsung; belum ada cara memberi kontrak per task.

## 2. Prinsip

1. **Kriteria ditetapkan sebelum eksekusi.** Kontrak acceptance dibuat dan divalidasi sebelum worker pertama berjalan,
   lalu dibekukan (disimpan dengan hash di run dir). Model boleh *mengusulkan* kriteria tambahan, tapi tidak boleh
   menghapus atau melonggarkan kriteria yang diberikan. Perubahan di tengah run berarti kontrak versi baru, yang
   butuh persetujuan, dan hasil versi lama tetap tercatat.
2. **`DONE` diputuskan harness dari bukti.** Klaim agen ("tes lulus", "bug sudah diperbaiki") tidak pernah menjadi
   bukti. Harness sendiri yang memeriksa file di disk dan menjalankan validasi.
3. **Tidak bisa diverifikasi berarti tidak lulus.** Validasi yang tidak bisa dijalankan (sandbox mati, perintah
   timeout, tes di-skip) membuat kriteria itu gagal atau `BLOCKED`, tidak pernah lulus. Ini aturan yang sama dengan
   "tes yang di-skip tidak dihitung lulus" di AGENTS.md.
4. **Cek deterministik dulu, judge hanya untuk yang subjektif.** Judge tetap fail closed, berjalan setelah semua cek
   kode lulus, dan tidak bisa membatalkan cek kode yang gagal (sama seperti 3c).
5. **Setiap putusan membawa bukti.** Per kriteria: lulus/gagal, jenis cek, dan bukti yang bisa diperiksa ulang (hash
   artefak, perintah dan exit code, potongan output yang dibatasi, atau kutipan judge yang memang ada di artefak).

## 3. Syarat lulus: lima lapis

Task dinyatakan `DONE` hanya kalau **semua kriteria wajib** di kelima lapis lulus.

### A. Kontrak task terpenuhi
- Semua output wajib di kontrak ada; tidak ada output di luar kontrak (sama dengan `required_outputs` /
  `allowed_outputs` sekarang).
- Lingkup dihormati: perubahan file hanya di path yang diizinkan kontrak. Harness membandingkan isi workspace sebelum
  dan sesudah run (daftar file dan hash), bukan membaca laporan agen.

### B. Artefak benar-benar ada
- Setiap artefak yang disebut kontrak ada di disk, file biasa (bukan symlink), tidak kosong kecuali kontrak
  mengizinkan, dan lolos cek jenisnya (misalnya JSON bisa di-parse, Markdown punya bagian wajib, Python bisa
  dikompilasi).
- Hash artefak dicatat di event log saat dinilai. Kalau artefak berubah setelah dinilai, putusan itu tidak berlaku.

### C. Validasi yang relevan lulus
- Perintah validasi (tes, build, lint, atau skrip cek) **ditulis di kontrak**, bukan dipilih agen di akhir run.
- Harness yang menjalankannya, di sandbox Docker (tanpa network, sama seperti `run_python`), dengan batas waktu.
- Lulus berarti exit code 0, **dan** jumlah tes yang dijalankan sesuai harapan kontrak (misalnya minimal N tes, 0
  skip untuk tes yang wajib). Exit 0 dengan 0 tes yang berjalan adalah gagal.
- File validasi dilindungi: tes, config tes, dan skrip validasi yang disebut kontrak tidak boleh diubah agen, kecuali
  kontrak secara eksplisit mengizinkan (misalnya task "tambahkan tes"). Mengubahnya tanpa izin langsung gagal.

### D. Tidak ada klaim penyelesaian palsu
- Ringkasan akhir agen dipecah menjadi klaim terstruktur (bukan teks bebas), misalnya
  `{"claim": "tests_pass", "evidence": "validation:unit"}` atau `{"claim": "file_changed", "path": "src/x.py"}`.
- Setiap klaim dicocokkan dengan bukti harness. Klaim yang tidak punya bukti, atau bertentangan dengan bukti, membuat
  task gagal. Ini padanan `grounded` di demo CSV, tapi dicek kode, bukan judge.
- Pola curang yang dicek langsung: tes dihapus atau di-skip, assertion dilonggarkan di file yang dilindungi, perintah
  validasi diganti, atau output validasi ditulis tangan ke workspace.

### E. Batas biaya dan waktu dipatuhi
- Budget USD dan token tetap ditegakkan seperti sekarang (`LLMCaller`, reservasi per node, ledger). Task yang selesai
  di atas budget tidak mungkin terjadi, karena permintaan ditolak sebelum dikirim.
- Waktu: `max_seconds` sekarang masih soft limit (dicek antar iterasi, diterima sebagai batasan di PENDING). Untuk
  task umum, validasi bisa lama, jadi perintah validasi diberi timeout keras di sandbox. Apakah `max_seconds` juga
  dijadikan batas keras adalah pertanyaan terbuka (bagian 8).

## 4. Status akhir

| Status | Kapan |
|---|---|
| `DONE` | semua kriteria wajib lulus, dengan bukti |
| `FAILED_ACCEPTANCE` (baru) | masih ada kriteria wajib yang gagal setelah `max_iterations` atau stagnan; laporan menyebut kriteria dan buktinya |
| `BLOCKED` (baru) | sebuah kriteria tidak bisa diverifikasi (sandbox tidak tersedia, perintah validasi tidak bisa dijalankan) atau butuh persetujuan; tidak pernah dianggap lulus |
| `FAILED_BUDGET`, `FAILED_PLAN`, `FAILED_LLM`, `FAILED_STAGNANT` | tetap seperti sekarang |

Untuk demo CSV tidak ada yang berubah: kontrak `SALES_REPORT` menjadi salah satu kontrak, dan cek yang ada menjadi
kriterianya.

## 5. Bentuk kontrak (sketsa, bukan final)

Contoh untuk vertical slice di bagian 7:

```yaml
contract: fix_bug
version: 1
inputs:
  workspace: fixtures/repos/calc        # disalin ke run dir; agen hanya bekerja di salinan
  issue: "divide() returns 0 instead of raising on division by zero"
scope:
  writable: ["src/**"]                  # semua path lain read-only bagi agen
  protected: ["tests/**", "pyproject.toml"]
artifacts:
  - {path: "SUMMARY.json", type: json, schema: claims_v1}
validation:
  - {id: unit, run: "python -m unittest discover -s tests", timeout_s: 120, min_tests: 5, max_skipped: 0}
  - {id: target, run: "python -m unittest tests.test_divide.DivideTest.test_zero", timeout_s: 60, min_tests: 1}
judge: []                               # tidak ada kriteria subjektif di slice ini
limits: {max_usd: 0.50, max_iterations: 3}
```

Image sandbox yang di-pin sekarang (`python:3.13-slim`) tidak punya pytest, dan sandbox tidak punya network untuk
`pip install`. Karena itu slice pertama memakai `unittest` bawaan Python. Image dengan test runner lain berarti image
baru yang di-pin dan direview terpisah.

Kontrak divalidasi harness seperti plan sekarang: path relatif tanpa `..`, perintah validasi hanya dari daftar yang
diizinkan, `protected` dan `writable` tidak tumpang tindih, dan semua angka positif dan terbatas.

## 6. Jaminan yang harus punya tes (dicek dengan mutasi)

1. Agen menyatakan selesai tapi validasi gagal → bukan `DONE`.
2. Validasi exit 0 tapi 0 tes berjalan, atau ada tes wajib yang di-skip → bukan `DONE`.
3. Sandbox tidak tersedia → `BLOCKED`, tidak pernah `DONE`, tidak ada fallback tanpa sandbox.
4. File di `protected` diubah atau dihapus → gagal, walaupun tes lulus.
5. File di luar `writable` diubah → gagal.
6. Klaim di `SUMMARY.json` tanpa bukti, atau bertentangan dengan bukti → gagal.
7. Artefak berubah setelah dinilai → putusan lama tidak berlaku.
8. Kontrak berubah di tengah run tanpa persetujuan → run berhenti; hasil versi lama tetap tercatat.
9. Perintah validasi timeout → kriteria gagal, waktu tercatat.
10. Crash di tengah validasi → setelah resume, validasi dijalankan ulang dengan aman (tidak berbayar, idempoten);
    putusan yang sudah di-commit tidak dihitung ulang.

## 7. Vertical slice yang diusulkan: perbaiki bug kecil di repo fixture

- Repo kecil di `fixtures/repos/` (beberapa fungsi, sekitar 5 tes, satu bug yang membuat satu tes gagal), di-commit
  ke repo ini. Tidak ada network, tidak ada GitHub, tidak ada PR sungguhan.
- Agen membaca dan menulis hanya di salinan workspace (path jail yang ada), dan validasi berjalan di sandbox Docker.
- Tahap 1, **tanpa biaya**: model palsu (scripted) memainkan beberapa skenario: perbaikan benar, perbaikan yang
  menghapus tes, perbaikan yang mengubah file di luar scope, klaim palsu, dan validasi yang timeout. Setiap skenario
  harus berakhir dengan status yang benar di bagian 4.
- Tahap 2, **butuh persetujuan terpisah**: satu run live dengan batas biaya kecil, setelah tahap 1 di-review.
- Di luar lingkup slice ini: membuat PR sungguhan, merge, deploy, dan network di sandbox.

Ini sejalan dengan M6 di `docs/FUTURE_ARCHITECTURE.md` (branch `docs-future-architecture`, belum di-merge): kriteria
eksplisit, kerja hanya di workspace yang diizinkan, tes di sandbox, putusan per kriteria dengan bukti, dan tidak ada
merge otomatis.

## 8. Pertanyaan untuk review

1. Status baru `FAILED_ACCEPTANCE` dan `BLOCKED`, atau cukup memakai `FAILED_STAGNANT` dengan alasan? (Usul: status
   baru, supaya "tidak bisa diverifikasi" tidak tercampur dengan "sudah dicoba dan gagal".)
2. `max_seconds` dijadikan batas keras untuk task umum, atau cukup timeout keras per perintah validasi? (Usul: timeout
   per perintah dulu; `max_seconds` keras dibahas terpisah karena menyentuh crash-resume.)
3. Klaim terstruktur di `SUMMARY.json`: wajib untuk semua task umum, atau hanya kalau kontrak memintanya? (Usul:
   wajib, karena tanpa itu lapis D tidak bisa dicek kode.)
4. Siapa yang boleh menulis kontrak: hanya manusia, atau model boleh mengusulkan lalu disetujui? (Usul: slice pertama
   hanya kontrak tertulis tangan; usulan model dibahas setelah slice berjalan.)
5. Angka ambang (misalnya `min_tests`) ditulis per kontrak, bukan global. Angka global baru ditetapkan setelah ada
   pengukuran, tidak dikarang sekarang.
