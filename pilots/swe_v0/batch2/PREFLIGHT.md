# Pilot SWE v0 batch 2: instance sympy yang lebih berat (preflight, ditulis sebelum run)

Status 2026-10-24: **persiapan; belum ada run.** Batch 1 (`../batch1/`) 5/5 `resolved`, tapi sengaja dipilih yang kecil (satu
berkas, ≤ 12 baris). Batch 2 mengambil instance sympy ≥ 1.10 di SWE-bench Verified yang paling berat menurut patch maintainer:
bukan "<15 menit" **dan** (lebih dari satu berkas, > 15 baris, atau > 2 `FAIL_TO_PASS`). Ada tepat tiga:

| Instance | Patch maintainer | `F2P` | Kelayakan di sandbox `sympy` (Python 3.12) |
|---|---|---|---|
| `sympy__sympy-22080` | 2 berkas, 12 baris | 3 | **tidak layak**: `sympy/codegen/tests/test_rewriting.py` mengimpor `distutils` (tidak ada di 3.12); penilai menolak |
| `sympy__sympy-24443` | 1 berkas, 53 baris (`combinatorics/homomorphisms.py`) | 1 | **layak**: patch resmi `resolved`, patch kosong tidak |
| `sympy__sympy-24661` | 1 berkas, 23 baris | 1 | **tidak layak**: dengan patch resmi pun 2 `PASS_TO_PASS` gagal (`test_sympy_parser`, `test_factorial_fail`; parser di 3.12) |

Jadi batch 2 = **satu instance**, `sympy__sympy-24443`: `_check_homomorphism` gagal pada `PermutationGroup` karena `_image()` tidak
menangani generator terbalik; issue menyarankan menyederhanakan fungsinya (patch maintainer 53 baris). Dua yang tidak layak
menunjukkan batas environment Python 3.12 (spek berikutnya: environment dari image Python resmi).

Selain itu sama dengan `../batch1/PREFLIGHT.md`: issue apa adanya (`sympy__sympy-24443/issue.txt`), environment `sympy` (image
`sha256:de306e046ab6…`, dipin), cap job $1,00, drafter $0,75, satu "go live" untuk tahap `code`, "y" untuk approve dan retry,
ringkasan draf format tetap, kriteria per instance `resolved` menurut `swe_grade.py`, batas klaim (harness, bukan model;
penilaian ala SWE-bench, Python 3.12; kemungkinan kontaminasi).

Yang paling ingin dilihat di sini: apakah tugas yang lebih besar membuat agen butuh lebih dari satu attempt, `retry`, atau ≥ 2
putaran perbaikan dalam satu attempt (pertanyaan B D5).

```bash
~/Argus-agent/.venv-verify/bin/python scripts/argus.py code --repo ~/swe/sympy \
    --commit 809c53c077485ca48a206cee78340389cb83b7f1 --issue-file ~/swe/inst/sympy__sympy-24443/problem_statement.txt \
    --environment sympy --key-file ~/.config/argus/deepseek_key --yes
```
