# Dev set 2 (sesudah perbaikan `EditFile`, #236): hasil apa adanya

2026-10-29. Tiga instance yang gagal karena `EditFile` menolak berkas > 100.000 byte (`20801`, `19954` dari batch 5; `24562` dari
batch 4 dan dev set 1), dijalankan ulang di harness `476b734` (`verify.sh` PASS:
`verification/verify-20261029T021836Z-aarch64.log`, 1957 passed, sandbox skipped 0). **Bukan klaim:** instance ini sudah pernah
dilihat, dan harness diubah karena kegagalannya. Angka resolve rate tetap dari batch dengan instance baru dan harness beku.
DeepSeek V4.1 Flash thinking, tanpa referensi, cap $1,00 per job.

| Instance | Environment | Drafter | Agen | `swe_grade.py` | Biaya job |
|---|---|---|---|---|---|
| `20801` `S(0.0) == S.false` | `sympy_py39` | `d1` DRAFTED, 4 submit, $0,0177 | `a1` DONE, 1 attempt, 3 langkah, $0,0011 | **resolved** (1/1, 96/96) | $0,0188 |
| `19954` `sylow_subgroup()` | `sympy_py39` | `d1` DRAFTED, 3 submit, $0,0270 | `a1` DONE, 1 attempt, 7 langkah, $0,0028 | **resolved** (1/1, 56/56) | $0,0298 |
| `24562` `Rational('0.5', '100')` | `sympy` | `d1` DRAFTED, 2 submit, $0,0098 | `a1` DONE, 1 attempt, 4 langkah, $0,0031 | **resolved** (1/1, 105/105) | $0,0129 |
| **Total** | | | | **3/3** | **$0,0615** (ledger) |

Sebelumnya: `20801` dan `19954` masing-masing dua stage agen gagal ($0,3328 dan $0,3973), `24562` tiga stage gagal di batch 4 dan
dev set 1. Sekarang satu attempt masing-masing, 3–7 langkah. Ini konsisten dengan diagnosis koreksi batch 5: batasnya ada di tool,
bukan di agen.

## Review draf (supervisi)

Ringkasan ketiga draf dalam satu pesan; Atha: "Y semua". Satu catatan yang diangkat sebelum approve: issue `20801` menutup dengan
pertanyaan "I assume we would want `S(0.0) == S.false` to return True as well?", sedangkan draf mengunci **False** (selaras dengan
`S(0) == S.false` dan `S.false == S(0.0)`). Nilai expected `19954` (sistem blok minimal D18 = `[6, 9]`, Sylow-2 order 4 untuk D18
dan D50) dan `24562` dicek secara matematis dari isi draf. Tidak ada redraft, tidak ada retry.

## Patch agen vs maintainer (dibuka sesudah grading)

- `20801`: sama dengan upstream (cek `Boolean` dipindah ke atas `if not self: return not other` di `Float.__eq__`); arah False
  dari draf sama dengan keputusan maintainer.
- `19954`: setara: indeks yang dibuang dikumpulkan lalu `del` dari belakang di ketiga list (`num_blocks`, `blocks`, `rep_blocks`);
  upstream memakai mask dan list comprehension.
- `24562`: setara dengan cara lain: `p`/`q` dikonversi ke `Rational` dulu lalu `p = pn*qd`, `q = pd*qn`; upstream mengumpulkan
  penyebut di `Q`.
- Tes drafter di atas patch maintainer: hijau untuk ketiganya.

## Penutupan job

Ketiganya `reject "dev set 2: graded, not applied"` (#233); tidak ada patch yang diterapkan ke sympy.
