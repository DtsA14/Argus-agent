# Pilot SWE v0 batch 3: hasil

2026-10-27, empat instance sympy SWE-bench Verified di environment **`sympy_py39`** (Python 3.9.25 dari image resmi, pytest 8.4.2,
image `sha256:2f684b89c437…` dipin per job, cek environment PASS), DeepSeek V4.1 Flash thinking, `--no-reference`. Kriteria:
`PREFLIGHT.md` (ditulis sebelum run, diperbarui sebelum run atas review Atha: bagian 3a).

**Tanpa bocoran jawaban:** approve hanya dari isi draf; tes drafter di atas patch maintainer baru dijalankan setelah grading. Batch
ini tidak dicampur dengan batch 1 (oracle-informed), batch 2 (oracle-assisted), dan `sympy__sympy-23534` (oracle-informed).

## Hasil: 3/4 `resolved`

| Instance | Drafter | Agen | `swe_grade.py` | Biaya job |
|---|---|---|---|---|
| `21847` polys | `d1` DRAFTED, 2 submit, $0,0166 | `a1`: attempt 1 `context_limit` tanpa menulis, attempt 2 `finished` (3 langkah), $0,0093 | **resolved** (1/1, 9/9) | $0,0259 |
| `21612` printing | `d1` **NO_DRAFT `output_truncated`** (reasoning 16.384 dari 16.384), $0,0241; redraft `d2` (atas "y", sekali) DRAFTED, 3 submit, $0,0401 | `a1`: attempt 1 `context_limit` tanpa menulis, attempt 2 `finished` (9 langkah), $0,0239 | **resolved** (1/1, 98/98) | $0,0881 |
| `21379` core/mod | `d1` DRAFTED, 2 submit, $0,0310 | `a1` dan `retry` `a2` gagal (4 attempt: `max_steps` 12 langkah, `context_limit`, `context_limit`, `max_steps`), **tidak satu pun menulis berkas**, $0,0191 + $0,0137 | – (tidak ada paket review) | $0,0638 |
| `24661` parsing | `d1` DRAFTED, 2 submit, $0,0218 | `a1` `DONE`, 1 attempt, $0,0130 | **resolved** (1/1, 27/27) | $0,0349 |
| **Batch** | | | **3/4** | **$0,2127** (ledger) |

Dua instance (`21612`, `24661`) sebelumnya tidak bisa dinilai di Python 3.12 (`distutils`, parser); di `sympy_py39` dinilai dan
`resolved`.

**Klaim:** harness Argus menyelesaikan 3 dari 4 task SWE-bench sympy tanpa bocoran jawaban, dinilai ala SWE-bench (Python 3.9.25,
penilai milik Argus). Bukan tingkat sukses model dan tidak dibandingkan dengan leaderboard: instance publik 2021–2023.

## Tes drafter di atas patch maintainer (dibuka setelah grading)

Keempat draf yang di-approve **hijau** di atas patch maintainer (`21847` 6/6, `21612` 3/3, `24661` 8/8, `21379` 1/1). Tidak ada draf
yang lolos review tapi salah paham issue. Kegagalan `21379` **bukan** karena tesnya salah, tapi karena agen tidak pernah menulis.

Catatan isi tes (dari review sebelum approve, tidak berubah): `21379` hanya menguji "tidak error" (MWE issue, termasuk
`clear_cache()`), tidak menguji nilai hasil; `21612` menyusun sendiri ekspresi yang dihasilkan konverter LaTeX karena antlr4 tidak
ada di image (asumsi yang tidak bisa dibuktikan di environment ini; tetap hijau di atas patch maintainer).

## Patch agen vs maintainer

- `21847`: identik (`max` → `sum` di dua tempat).
- `24661`: struktur hampir sama (`relational_operators` dan `visit_Compare` di transformer `evaluate=False`); kontaminasi mungkin.
- `21612`: **berbeda**: maintainer menambah `Pow` ke satu `isinstance`; agen menambah fungsi yang mendeteksi pembagian di tingkat
  kurung terluar pada string yang dicetak. Lebih kasar, tapi lulus semua 98 `PASS_TO_PASS`.

## Yang dipelajari

1. **Feedback #188 terbukti di run live tanpa bocoran:** `21847` dan `21612` sama-sama gagal di attempt 1 (`context_limit` tanpa
   menulis) dan selesai di attempt 2 setelah petunjuk "baca hanya yang perlu, lalu tulis".
2. **Mode gagal ketiga, tanpa petunjuk:** `21379` berhenti di **`max_steps`** dua kali tanpa menulis (hampir semua langkah
   `search_files`), dan retry dengan carry `context_limit` tidak cukup. Feedback untuk `max_steps` tanpa menulis belum ada.
3. **Drafter juga kena "thinking menghabiskan output"** (`21612` `d1`): batas output drafter 16.384 tidak ikut perbaikan #200.
   Batas input drafter sendiri 200.000 (bukan 60.000 seperti agen): input tagihan 65.769 pada langkah itu, perkiraan 78.137.
4. **Teks kebijakan drafter usang:** `profile_info` yang ditunjukkan ke drafter masih menyebut `large_usd` `max_input_tokens`
   40.000, padahal DeepSeek mendapat 60.000 sejak #188 (dan output 32.000 sejak #200).

Perbaikan 2–4 dikerjakan **setelah** batch ini (keempat instance berjalan di versi harness yang sama, review Atha).

## Supervisi

Keputusan Atha untuk run: "go live" (keempat tahap `code`), "y" approve ×4, "redraft" `21612` (sekali), "y retry" `21379` = **7**.
Waktu dari ringkasan dikirim sampai "y" (`review_times.txt`): `21847` 5 menit 26 detik; `21379` dan `24661` disetujui bersama ±6–7
menit setelah ringkasan masing-masing; `21612` (d2): waktu kirim ringkasan tidak tercatat. Lebih lama dari batch 1 (median 45 detik),
karena ringkasan tanpa hasil patch resmi menuntut Atha menilai isi tes sendiri (mis. syarat `clear_cache()` di `21379`).

## Koreksi diagnosis (2026-10-29, sesudah batch 5)

`21379` (`j20261027_151552_7cdd`): `EditFile` menolak `sympy/polys/polytools.py` dan `sympy/core/expr.py` ("file larger than 100000
bytes", 6 kali). "Tidak pernah menulis" sebagian disebabkan batas itu, bukan hanya oleh agen. Angka hasil tidak berubah. Perbaikan:
`EditFile` sampai 2 MB (PR sesudah batch 5).
