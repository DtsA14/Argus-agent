# Pilot SWE v0 batch 5: lima instance sympy 1.6–1.8 yang belum pernah dipakai (preflight, ditulis sebelum run)

Status 2026-10-28: **persiapan; belum ada run.** Menunggu "go live". Tujuan: melihat efek #225 (alasan merah per tes, gate per node)
dan #227 (outline `ReadFile`, petunjuk `context_limit`) di instance baru. Aturan dasar sama dengan `../batch4/PREFLIGHT.md` (tanpa
bocoran jawaban: approve hanya dari isi draf; tes draf di atas patch maintainer baru dijalankan setelah grading).

## 1. Instance

Kolam sympy 1.9–1.12 yang kecil (satu berkas, ≤ 12 baris, 1–3 `FAIL_TO_PASS`, satu berkas tes; `../batch1/pick_instances.py`)
**sudah habis** di batch 1–4 dan dev set. Kolam baru: 15 instance kecil sympy 1.5–1.8 (`extract.py` ke `~/swe/inst/`), semuanya
dicek di environment **`sympy_py39`** (`feasibility.log`, 2026-10-28): **15/15 layak**, patch resmi `resolved`, patch kosong tidak.

Aturan pilih (hanya metadata, ditetapkan sebelum melihat patch): urut `created_at` terbaru dulu, **satu per modul teratas**
(`core`, `polys`, ...), lima pertama. Yang dilewati karena modulnya sudah terpilih: `20590`, `19637` (core), `19040` (polys),
`18763` (printing), `18698` (polys), `18211` (core).

| Instance | Versi | Berkas patch resmi | Baris | `F2P` / `P2P` | Difficulty | Issue (baris pertama) |
|---|---|---|---|---|---|---|
| `sympy__sympy-20801` | 1.8 | `sympy/core/numbers.py` | 4 | 1 / 96 | 15 menit–1 jam | `S(0.0) == S.false` returns True |
| `sympy__sympy-20428` | 1.8 | `sympy/polys/domains/expressiondomain.py` | 2 | 1 / 154 | 15 menit–1 jam | Result from `clear_denoms()` prints like zero poly but behaves wierdly |
| `sympy__sympy-19954` | 1.7 | `sympy/combinatorics/perm_groups.py` | 9 | 1 / 56 | <15 menit | `sylow_subgroup()` IndexError |
| `sympy__sympy-19346` | 1.7 | `sympy/printing/repr.py` | 10 | 1 / 40 | 15 menit–1 jam | `srepr` not printing dict and set properly |
| `sympy__sympy-18189` | 1.6 | `sympy/solvers/diophantine.py` | 2 | 1 / 41 | <15 menit | diophantine: incomplete results depending on syms order with permute=True |

Issue: `<instance>/issue.txt` = `problem_statement` **apa adanya** (509–3.710 karakter, di bawah batas 8.000). Tes resmi dan patch
maintainer ada di `~/swe/inst/`, di luar repo, job root, dan path jail.

## 2. Environment dan harness

- Environment `sympy_py39` (Python 3.9.25, pytest 8.4.2), image `sha256:146db0c5d665…` dari `~/pilot3a_live/.sandbox_image_sympy_py39`,
  dipin per job saat `code`. `check_env_image.py sympy_py39` PASS 2026-10-28 (dibutuhkan sejak #221; batch 3 jalan sebelum cek ini ada).
- Harness: `main` `aee6aef` (sesudah #225, #227, #229, #231, #233), `verify.sh` PASS di commit itu
  (`verification/verify-20261028T183756Z-aarch64.log`: 1953 passed, sandbox skipped 0). Sha run dicatat di `RESULT.md`.
- ReadDocs (`--web`) **tidak** diberikan: tidak ada host sympy di allowlist, dan ini bukan pilot ReadDocs.
- Selama batch: tidak ada `verify.sh` dan tidak ada `docker image prune`.

## 3. Aturan batch (sama dengan batch 4)

1. **Harness tidak diubah selama batch.** Kegagalan dicatat apa adanya; spek baru **setelah** batch. Bug yang membuat hasil tidak
   sah: batch dihentikan dan dilaporkan.
2. **Izin di muka per instance:** paling banyak **satu redraft** dan **satu retry** agen, tanpa `redraft --note`. Approve tetap per
   draf, atas "y" Atha.
3. Satu "go live" untuk semua tahap `code`, redraft, dan retry di atas.
4. Cap $1,00 per job, cap batch $3,00 (dihitung Claude dari ledger sebelum setiap tahap live, `spent.py`).
5. Sesudah setiap job ditutup: `argus applied` tidak dipakai (tidak ada patch yang diterapkan ke sympy); paket review yang tidak
   dipakai ditutup dengan `argus reject <job> "batch 5: graded, not applied"` sesudah grading.

## 4. Ringkasan draf untuk approve (format tetap)

Kutipan "Why they fail now" apa adanya, writable, validasi (jumlah tes regresi), peringatan scope, dan satu kalimat penilaian.
Tanpa hasil patch maintainer. Yang baru dicatat per draf: jumlah submit yang ditolak gate "tes menelan traceback" dan alasannya
(data untuk keputusan gate `sys.monitoring`, PENDING).

## 5. Ekspektasi (sebelum run)

Per instance ±$0,03–0,15. `20428` (`P2P` 154, issue panjang) dan `19346` (10 baris) paling mungkin butuh retry; `18189` dan `20801`
paling ringan. Pembanding: batch 3 (3/4, juga `sympy_py39`) dan batch 4 (3/5).

## 6. Kriteria (ditetapkan sebelum run, tidak diubah sesudahnya)

Drafter `DRAFTED` ≤ 5 submit, node wajib merah karena assertion pada perilaku dari issue, writable tidak lebih luas dari paket modul
issue; dinilai dari isi draf saja. Per instance berhasil bila `resolved: true` menurut `swe_grade.py` (environment `sympy_py39`).
Hasil dilaporkan apa adanya per instance (termasuk redraft dan retry), sebagai angka **tanpa bocoran**. Batas klaim: harness, bukan
model; penilaian ala SWE-bench (Python 3.9, penilai milik Argus); instance publik 2019–2021, kemungkinan besar ada di data latih.
