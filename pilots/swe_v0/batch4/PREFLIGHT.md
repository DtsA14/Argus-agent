# Pilot SWE v0 batch 4: lima instance sympy yang tidak dipilih di batch 1 (preflight, ditulis sebelum run)

Status 2026-10-28: **persiapan; belum ada run.** Menunggu "go live". Aturan dasar sama dengan `../batch3/PREFLIGHT.md` (tanpa bocoran
jawaban: approve hanya dari isi draf; tes draf di atas patch maintainer baru dijalankan setelah grading). Yang baru ada di bagian 3.

## 1. Instance

Kelimanya layak di environment `sympy` (Python 3.12) dan **tidak dipilih** di batch 1 (satu per modul, urutan daftar), jadi batch ini
tidak bergantung pada pilihan tangan. Cek kelayakan 2026-10-24 (`../batch1/feasibility.log`): patch resmi `resolved`, patch kosong tidak.

| Instance | Berkas patch resmi | Baris | `F2P` / `P2P` | Issue (baris pertama) |
|---|---|---|---|---|
| `sympy__sympy-24562` | `sympy/core/numbers.py` | 8 | 1 / 105 | Rational calc value error |
| `sympy__sympy-24066` | `sympy/physics/units/unitsystem.py` | 7 | 1 / 30 | `SI._collect_factor_and_dimension()` cannot properly detect that exponent is dimensionless |
| `sympy__sympy-23824` | `sympy/physics/hep/gamma_matrices.py` | 3 | 1 / 2 | `kahane_simplify()` incorrectly reverses order of leading uncontracted gamma matrices |
| `sympy__sympy-22456` | `sympy/codegen/ast.py` | 12 | 1 / 29 | Argument invariance of `codegen.ast` `String` |
| `sympy__sympy-23262` | `sympy/utilities/lambdify.py` | 4 | 1 / 61 | Python code printer not respecting tuple with one element |

Issue: `~/swe/inst/<instance>/problem_statement.txt` apa adanya.

## 2. Environment dan harness

- Environment `sympy` (Python 3.12), image `sha256:de306e046ab6…` dari `~/pilot3a_live/.sandbox_image_sympy`, dipin per job saat `code`.
- Harness: `main` `235c3ab` (sesudah #206, #208, #210, #211), di `~/pilot3a_live`. Sha dicatat di `RESULT.md`.
- Selama batch: tidak ada `verify.sh` dan tidak ada `docker image prune` (image yang dipin bisa kehilangan tag-nya).

## 3. Aturan baru batch ini (Atha 2026-10-28: "Ok gass")

1. **Harness tidak diubah selama batch.** Kegagalan dicatat apa adanya; spek baru dibuat **setelah** batch, dari pola kegagalannya.
   Kalau ada bug harness yang membuat hasil tidak sah (bukan sekadar gagal), batch dihentikan dan dilaporkan.
2. **Izin di muka per instance:** paling banyak **satu redraft** (bila run drafter berakhir tanpa draf, atau isi draf sendiri bermasalah)
   dan **satu retry** agen. Tanpa `redraft --note`. Approve tetap per draf, atas "y" Atha.
3. Satu "go live" untuk semua tahap `code`, redraft, dan retry di atas.
4. Cap $1,00 per job, cap batch $3,00 (dihitung Claude dari ledger sebelum setiap tahap live).

## 4. Ringkasan draf untuk approve (format tetap)

Kutipan "Why they fail now" apa adanya, writable, validasi (jumlah tes regresi), peringatan scope (glob, jalur panggilan di luar
writable), dan satu kalimat penilaian. Tanpa hasil patch maintainer.

## 5. Sesudah setiap job (catatan Atha pada 21379)

Untuk setiap patch agen: **berkas mana yang disentuh** (dibandingkan writable dan rencana draf), dan apakah perubahannya **sempit**
(mis. exception ditangkap di titik yang tepat) atau menelan error di level yang lebih atas. Dicatat di `RESULT.md`.

## 6. Ekspektasi (sebelum run)

Per instance ±$0,03–0,10 (batch 1: $0,016–0,039 per instance; run ulang 21379: $0,28 dengan 4 drafter). `23824` (3 baris, 2 `P2P`)
paling ringan; `22456` (12 baris) dan `24562` (`numbers.py` besar, 105 `P2P`) paling mungkin butuh retry.

## 7. Kriteria (ditetapkan sebelum run, tidak diubah sesudahnya)

Drafter `DRAFTED` ≤ 5 submit, validasi di `sympy`, node wajib merah karena assertion pada perilaku dari issue, writable tidak lebih luas
dari paket modul issue; dinilai dari isi draf saja. Per instance berhasil bila `resolved: true` menurut `swe_grade.py`. Hasil dilaporkan
apa adanya per instance (termasuk redraft dan retry), sebagai angka **tanpa bocoran**; dibandingkan dengan batch 3 (3/4), bukan
dicampur dengan batch 1–2. Batas klaim: harness, bukan model; penilaian ala SWE-bench (Python 3.12, penilai milik Argus); instance
publik 2021–2023. Tidak ada patch yang diterapkan ke sympy.
