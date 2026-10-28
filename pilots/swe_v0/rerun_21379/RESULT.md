# Pilot SWE v0: `sympy__sympy-21379` diulang setelah #206 (hasil)

2026-10-27/28, `sympy_py39` (image `sha256:2f684b89c437…`, sama dengan batch 3), DeepSeek V4.1 Flash thinking, `--no-reference`.
Kriteria dan tafsiran: `PREFLIGHT.md` (ditulis sebelum run). Artefak: `live/`, penilaian: `grade.json`.

**Dilaporkan terpisah, tidak dihitung ke angka batch mana pun:** instance ini dipilih ulang karena gagal di batch 3, dan perbaikan
harness #206, #208, #210, #211 dibuat di tengah pilot setelah tahu sebab gagalnya. Tanpa `redraft --note`.

## Hasil: `resolved` (`FAIL_TO_PASS` 1/1, `PASS_TO_PASS` 91/91)

| Tahap | Harness (`main`) | Hasil | Biaya |
|---|---|---|---|
| Percobaan 1, job `j20261027_175610_34ba`, `d1` | `03d078b` (#206) | DRAFTED, **ditolak** (pilihan B): tes menelan traceback, writable tanpa pemanggil di jalur error | $0,0515 |
| Percobaan 2, job `j20261027_185915_f13b`, `d1` | `b9f773c` (#208) | NO_DRAFT `max_steps` 16, 3 submit; sisa 1 masalah ("1 tests skipped", tanpa nama node) | $0,0421 |
| `d2` (redraft, "y") | sama | NO_DRAFT `max_steps` 16, 2 submit; masalah yang sama; **rencana memuat `sympy/core/mod.py`** setelah melihat traceback | $0,0333 |
| `d3` (redraft, "y" sebelumnya) | `1b12739` (#210: node skipped disebut, 24 langkah) | NO_DRAFT `max_steps` 24, 2 submit; pesan sekarang menyebut `test_subs.py::test_mul2`, langkah habis | $0,0465 |
| `d4` (redraft, "skip+y") | `58f5db4` (#211: langkah submit sesudah `max_steps`) | **DRAFTED**, 3 submit, langkah 23 dari 24 (langkah submit tidak terpakai); di-approve | $0,0720 |
| `a1` agen | sama | FAILED (2× `context_limit`, tidak menulis) | $0,0313 |
| `a2` retry ("y") | sama | **DONE**, 3 attempt (`max_steps` 12 sudah menulis, `context_limit`, `finished`) | $0,0521 |
| **Percobaan 2** | | **REVIEW_READY, resolved** | **$0,2773** |
| **Seluruh run ulang** | | | **$0,3288** |

## Patch agen

Hanya `sympy/core/mod.py` (berkas lain di paket: tes baru draf yang di-approve):

```python
        try:
            G = gcd(p, q)
        except PolynomialError:
            # e.g. a Piecewise in p or q cannot be handled by the polys
            G = S.One
```

**Dua cek Atha setelah approve** (gerbang regresi draf 16 tes jauh lebih sempit dari writable `sympy/core/*.py`, dan "tidak error"
bisa diakali):
1. Berkas yang disentuh: **hanya `mod.py`** (tidak `polytools.py`, tidak `basic.py`).
2. Penangkapan **sempit**, hanya di sekitar `gcd`. Maintainer membungkus juga blok `gcd_terms` sesudahnya; agen hanya pemanggilan
   `gcd`. Keduanya lulus 91 `PASS_TO_PASS`.

Tes draf `d4` di atas patch maintainer (dibuka setelah grading): **pass**. Kontaminasi mungkin (instance publik 2021; bentuk perbaikan
mirip maintainer), sama dengan batas klaim batch 1–3.

## Tafsiran (yang ditetapkan di preflight)

- **Informasi sampai ke agen:** `approval.baseline` memuat `mod.py:169`; di **semua** attempt `a1` dan `a2` agen membaca `mod.py` di
  langkah pertama (attempt 3 `a2`: langkah kedua). Di batch 3 agen tidak pernah membukanya.
- `a1` tetap gagal **walaupun** `mod.py:169` ada di prompt: agen lalu membaca `basic.py` (69 KB), `piecewise.py` (51 KB), `power.py`
  (74 KB) utuh sampai `context_limit`. Menurut preflight: sebab di model, atau di `ReadFile` yang selalu membaca berkas utuh (K4 #206,
  ditunda). Satu run tidak memisahkan keduanya.
- `a2` (carry `context_limit`: "baca hanya yang perlu, lalu tulis") menulis di `mod.py` sejak attempt 1 langkah 7 dan selesai di
  attempt 3.
- Perbaikan drafter (#206/#208/#210/#211) masing-masing terlihat bekerja di run berikutnya: traceback disimpan (`d1`+), `mod.py`
  masuk rencana tanpa bocoran (`d2`), node skipped disebut (`d3`). Langkah submit #211 dan pertanyaan scope #208 belum pernah
  terpakai di run live (`d4` lolos sebelum `max_steps`; `mod.py` sudah tercakup glob).

## Yang dipelajari

1. **Drafter membaca sampai dipaksa berhenti** (16, 16, 24, 23 langkah). Menambah `max_steps` hanya memperpanjang bacaan.
2. **Writable glob lebar + regresi sempit** (catatan Atha): `sympy/core/*.py` dengan 16 tes regresi. Agen kali ini memilih tempat yang
   sempit, tapi tidak ada gerbang yang memaksanya. Kandidat spek: writable glob atau writable jauh lebih lebar dari regresinya perlu
   alasan/regresi yang mencakup modulnya (mis. `test_arit.py`, `test_polytools.py` untuk `mod.py`/`polytools.py`).
3. **Baca berkas besar utuh** masih penyebab `context_limit` di agen (`a1`): bukti untuk `ReadFile` per rentang (K4 #206).

## Supervisi

Keputusan Atha untuk run: "go live" ×2, "B" (reject percobaan 1), "y" (`d2`), "y" sekali di muka (`d3`), "skip+y" (`d4`), "y"
(approve), "y" (retry) = **8**, plus keputusan harness: K1–K4 #206, K1–K4 #208, #210 ("gas"), A (#211), auto-merge, skip review #211.
