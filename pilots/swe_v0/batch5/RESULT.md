# Pilot SWE v0 batch 5: hasil

2026-10-29, lima instance sympy 1.6–1.8 SWE-bench Verified di environment **`sympy_py39`** (Python 3.9.25, image
`sha256:146db0c5d665…` dipin per job), DeepSeek V4.1 Flash thinking, tanpa referensi. Harness `main` `aee6aef` (`verify.sh` PASS,
1953 passed, sandbox skipped 0), **tidak diubah selama batch**; run dari `b479428` (selisihnya hanya `pilots/swe_v0/batch5/`).
Kriteria: `PREFLIGHT.md` (ditulis sebelum run).

## Hasil: 2/5 `resolved` (1/4 tanpa campur tangan reviewer, 1/1 *human-steered*)

| Instance | Drafter | Agen | `swe_grade.py` | Biaya job |
|---|---|---|---|---|
| `20801` core/numbers | `d1` DRAFTED, 4 submit, $0,0124 | `a1` FAILED_ACCEPTANCE (30 langkah `max_steps` tanpa menulis; 2× finished tapi validasi target merah), $0,1350; `retry` `a2` FAILED_ACCEPTANCE (`max_steps` tanpa menulis, `context_limit`, `max_steps` tanpa menulis), $0,1854 | – (tidak ada paket review) | $0,3328 |
| `20428` polys | `d1` DRAFTED, 2 submit (1 pertanyaan scope), $0,0277 | `a1` DONE, 2 attempt, $0,0385 | **unresolved** (F2P 0/1, P2P 154/154) | $0,0662 |
| `19954` combinatorics | `d1` DRAFTED, 1 submit, $0,0208 | `a1` **FAILED_BUDGET** (`reservation_exhausted` sesudah 29 langkah; 1.210.037 token dilaporkan vs perkiraan 1.200.000), $0,1860; `retry` `a2` FAILED_ACCEPTANCE (finished, `context_limit`, `max_steps`; semuanya menulis), $0,1905 | – | $0,3973 |
| `19346` printing/repr | `d1` DRAFTED, 4 submit, $0,0140 | `a1` DONE, 1 attempt (2 langkah), $0,0032 | **resolved** (1/1, 40/40) | $0,0172 |
| `18189` solvers | `d1` DRAFTED, 1 submit, $0,0146, **ditahan**; `d2` redraft **dengan catatan reviewer** (`human-steered`), 2 submit, $0,0323 | `a1` DONE, 1 attempt (14 langkah), $0,0141 | **resolved** (1/1, 41/41) | $0,0610 |
| **Batch** | | | **2/5** | **$0,8746** (ledger) |

**Klaim:** harness Argus menyelesaikan 2 dari 5 task SWE-bench sympy 1.6–1.8 tanpa bocoran jawaban; salah satunya (`18189`) sesudah
reviewer menahan draf pertama dan memberi catatan, jadi tanpa campur tangan 1/4. Penilaian ala SWE-bench (Python 3.9, penilai milik
Argus). Bukan tingkat sukses model; instance publik 2019–2021. **Lebih rendah** dari batch 3 (3/4, juga `sympy_py39`) dan batch 4 (3/5).

## Kenapa gagal

- **`20428`: kontrak benar tapi tidak cukup (drafter).** Issue menyebut `clear_denoms()`, dan draf menguji `clear_denoms()`: rep
  di-strip, `terms_gcd` tidak `IndexError`. Agen memperbaikinya dengan sempit (strip sesudah perkalian dan konversi di
  `dup_clear_denoms`/`dmp_clear_denoms`, `densetools.py` saja). Tes resmi menuntut Poly yang **dibangun** dari ekspresi itu sudah
  `== Poly(0, x, domain='EX')`; fix maintainer ada di `polys/domains/expressiondomain.py`, yang tidak ada di writable. Tes draf lulus
  juga di atas fix maintainer (`drafter_tests_on_reference: pass`), jadi tesnya tidak salah, hanya lebih sempit dari masalahnya.
  Kandidat (sesudah batch): drafter memeriksa titik di mana nilai salah **pertama kali** muncul (konstruksi), bukan hanya tempat
  gejalanya dilaporkan.
- **`20801` dan `19954`: agen.** Keduanya gagal dua stage (a1 + retry), dengan pola yang sama seperti `24562` di batch 4 dan 010b di
  argus-ledger: attempt habis karena `max_steps` 30 tanpa menulis, atau `context_limit`. Di `20801` (`numbers.py` besar) agen membaca
  40 + 55 kali (`read_file`) dan mencari 28 + 44 kali. #227 (outline untuk berkas besar, petunjuk sesudah `context_limit`) **tidak
  mencegah** pola ini di sini; efeknya per berkas belum diukur dari run ini.
- **`19954` a1 FAILED_BUDGET:** penjaga anggaran bekerja benar (run dihentikan saat token yang dilaporkan melebihi perkiraan heuristik
  0,8%); bukan bug yang membuat hasil tidak sah. Catatan untuk H3 spek margin (`estimate_miss` per run).

## Patch agen (berkas yang disentuh, sempit atau tidak)

- `20428`: hanya `sympy/polys/densetools.py` (writable 5 berkas). Sempit; tidak menelan error. Tidak menyentuh konstruksi Poly.
- `19346`: hanya `sympy/printing/repr.py` (= writable). 2 langkah.
- `18189`: hanya `sympy/solvers/diophantine.py` (= writable).

## Review draf (supervisi)

- Ringkasan kelima draf dikirim dalam satu pesan (`review_times.txt`). Atha: "Y 1-4", nomor 5 **ditahan**: tes ke-2 `d1` mengunci
  keluaran `permute=True` yang memuat pasangan **bukan solusi** (`x² + y² + 3x − 5` di (4, 1) = 24, di (−1, 1) = −6). Alasannya berdiri
  dari isi draf (cek matematika), bukan dari patch maintainer.
- Pilihan A (Atha): `redraft --note` dengan catatan yang diusulkan Claude, dipakai apa adanya (`note_18189.txt`). Ini **di luar** aturan
  batch 3.2 ("tanpa `--note`") atas izin eksplisit Atha; job ditandai `human_steered` dan dilaporkan terpisah. `d2` memisahkan
  perilaku dari issue (urutan `syms` hanya membalik tuple, pasangan tidak dikunci) dari nilai expected (dibuktikan di dalam tes).
  "Y 5".
- Gate "tes menelan traceback": 1 dari 12 submit yang ditolak (`19346` submit 1, `NameError` dari `eval` tanpa rantai; permintaan
  wajar). **Tidak ada** salah tolak jenis draf 008 di batch ini.

## Tes drafter di atas patch maintainer (dibuka setelah grading)

`20428`, `19346`, `18189`: hijau (`drafter_tests_on_reference: pass` di `grade.json`).

## Penutupan job

`20801`, `19954`: `abandon` (retry sudah dipakai). `20428`, `19346`, `18189`: `reject "batch 5: graded, not applied"` (#233); tidak ada
patch yang diterapkan ke sympy.

## Koreksi diagnosis (2026-10-29, sesudah batch 5)

Bagian "Kenapa gagal" untuk `20801` dan `19954` **salah sasaran**: penyebabnya batas harness, bukan pola baca agen. `EditFile` membaca
dengan batas `MAX_READ` 100.000 byte dan menolak `numbers.py` (117 KB) dan `perm_groups.py` (182 KB).
- `20801`: agen menemukan fix (cek `Boolean` sebelum `if not self` di `Float.__eq__`), `EditFile` ditolak, sisa langkah habis mencari
  jalan lain; `Finish` "No change made ... `EditFile` refuses that file because it is larger than the 100000-byte tool limit".
- `19954`: sesudah penolakan agen memakai `WriteFile` dan menimpa seluruh berkas (5.262 → 401 → 103 baris); peringatan harness
  menyarankan `EditFile`, yang menolak berkas itu. Token dan context habis di situ (termasuk FAILED_BUDGET a1).
Sejak 2026-10-24: 9 job SWE kena penolakan ini (batch 3 `21379`, batch 4 dan dev set `24562`, batch 5). Angka 2/5 tidak berubah.
Perbaikan: `EditFile` sampai 2 MB (PR sesudah batch 5); `20801`, `19954`, `24562` diulang sebagai dev set (bukan klaim).

## Koreksi: `19954` a1 harness-affected (2026-10-29, `SPEC_ESTIMATE_REASONING.md`)

`FAILED_BUDGET` di `a1` (1.210.037 dari 1.200.000 token) bukan sekadar "penjaga bekerja benar". Penyebabnya bug harness:
counter heuristik tidak menghitung `reasoning_content` yang dikirim balik ke DeepSeek, sehingga input tagihan sampai 1,10×
perkiraan di a1 dan 1,91× di a2, meski margin sudah 2,5. `19954` dicatat **harness-affected** (counter dan `EditFile`),
terpisah dari kegagalan model; angka 2/5 tidak berubah. Tidak dijalankan ulang di batch 5. Dev set 2 (`../dev2/`) memakai
harness sesudah `EditFile` tetapi sebelum fix counter, dan merupakan data tersendiri, bukan klaim.
