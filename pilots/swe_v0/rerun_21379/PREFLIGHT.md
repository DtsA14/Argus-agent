# Pilot SWE v0: `sympy__sympy-21379` diulang setelah #206 (preflight, ditulis sebelum run)

Status 2026-10-27: **siap; belum ada run.** #206 sudah di-merge (`docs/reviews/SPEC_LOCATE_FROM_TRACEBACK.md`); menunggu "go live".
Asal: penelusuran kegagalan `21379` di batch 3 (job `j20261027_151552_7cdd`: 4 attempt di 2 tahap, tidak satu pun menulis;
`../batch3/RESULT.md`). Aturan lain sama dengan `../batch3/PREFLIGHT.md` (tanpa bocoran jawaban, bagian 3a di sana).

**Dilaporkan terpisah, tidak dihitung ke angka batch mana pun:** instance ini dipilih ulang *karena* gagal, dan perbaikan #206 dipilih
setelah tahu sebab gagalnya. Hasilnya menjawab "apakah #206 menutup sebab kegagalan ini", bukan tingkat sukses.

## 1. Yang sama dan yang berbeda dari run batch 3

| | Batch 3 (`7cdd`) | Run ini |
|---|---|---|
| Instance, `base_commit`, issue | `624217179aaf…`, `problem_statement` apa adanya | sama |
| Environment | `sympy_py39`, image `sha256:2f684b89c437…` | sama (image yang sama, cek environment diulang: PASS; bagian 2) |
| Harness | `main` sebelum #204 | `main` `fd20cde` (sesudah #206) |
| Model | DeepSeek V4.1 Flash thinking | sama |
| Draf | `d1` (approve dari isi draf) | **job baru, draf baru dari awal**; drafter tidak melihat run lama |

Perubahan harness yang relevan sejak `7cdd`: #204 (petunjuk setelah `max_steps` tanpa menulis, output drafter 32.000, profil
efektif untuk drafter) dan #206 (frame pemanggil di potongan error, baseline merah draf di attempt 1 setiap tahap, `SearchFiles` per
berkas, "No matches" yang jujur). Efek keduanya **tidak bisa dipisahkan** di satu run.

## 2. Sebelum run (Claude, tanpa biaya model)

1. #206 di-merge (`fd20cde`); `~/pilot3a_live` di `main` itu (fast-forward, 2026-10-27). **Selesai.**
2. Image: `~/pilot3a_live` memakai id dari berkasnya sendiri, `.sandbox_image_sympy_py39` = `sha256:2f684b89c437…` (image yang sama
   dengan batch 3, rootfs `176cffbb…`). `verify.sh` di `~/Argus-agent` membangun ulang tag `argus-sandbox-sympy_py39:py3.9` (dua kali
   hari ini: `c40992b4…`, lalu `4596a398…`), tapi image `2f684b89…` tetap ada (tanpa tag) dan tidak dipakai ulang tag-nya.
   Cek environment dijalankan ulang di `~/pilot3a_live` untuk id itu: **PASS** (2026-10-27T17:53:47Z; isolation, red check,
   collection, tanpa shell/git/pip, Python 3.9.25, pytest 8.4.2). **Selesai.**
3. Selama run: tidak ada `verify.sh` dan tidak ada `docker image prune` (image yang dipin tidak bertag, jadi prune akan
   menghapusnya).

## 3. Cara jalan

Setelah "go live" (`~/pilot3a_live`):

```bash
I=~/swe/inst/sympy__sympy-21379
~/Argus-agent/.venv-verify/bin/python scripts/argus.py code --repo ~/swe/sympy --commit $(cat $I/base_commit.txt) \
    --issue-file $I/problem_statement.txt --environment sympy_py39 --key-file ~/.config/argus/deepseek_key --yes
```

Lalu ringkasan draf dengan format tetap (kutipan "Why they fail now" apa adanya; dengan #206 kutipan itu memuat frame pemanggil),
approve atas "y". `retry` paling banyak sekali, atas "y". Tes drafter di atas patch maintainer baru dijalankan **setelah grading**.

## 4. Yang diamati (dicatat apa pun hasilnya)

1. **Apakah attempt 1 melihat `mod.py`:** `job.json` `approval.baseline` dan prompt attempt 1 (`audit_run.py`) memuat
   `sympy/core/mod.py:169`. Ini bergantung pada tes drafter yang baru: bila tesnya tidak lewat `Mod.eval` (atau menelan exception
   tanpa traceback), frame itu tidak ada, dan itu dicatat sebagai temuan tersendiri.
2. **Apakah agen menulis, dan di mana:** berkas pertama yang diubah dan pada langkah ke berapa; berapa `SearchFiles` per berkas dan
   berapa penolakan yang tersisa.
3. Cara setiap attempt berhenti (`finished`, `context_limit`, `max_steps`, `output_truncated`) dan apakah `RunValidation` dipakai.
4. `swe_grade.py`: `resolved`, `FAIL_TO_PASS` 1/1, `PASS_TO_PASS` 91/91.

## 5. Ekspektasi (sebelum run)

Biaya job ±$0,03–0,10 (batch 3: $0,0638 tanpa hasil), cap job $1,00. Perkiraan Claude, bukan janji: dengan `mod.py:169` di prompt
attempt 1, agen kemungkinan besar menulis di `Mod.eval`, tapi perbaikan maintainer (`try/except PolynomialError` di sekitar `gcd`)
tetap harus ditemukan model sendiri.

**Tafsir yang ditetapkan sebelum run:**
- `resolved` dan agen menulis di `mod.py` → sebab utama kegagalan lama adalah informasi yang tidak sampai ke agen (harness).
- Gagal walaupun `mod.py:169` ada di prompt attempt 1 → sebab utama ada di model (atau di tool baca berkas besar, K4 #206); bukan
  bukti kuat dari satu run, tapi alasan untuk membandingkan dengan model lain sebelum menambah fitur harness.
- Gagal dan `mod.py:169` tidak ada di prompt → yang diuji bukan #206; dicatat, tidak ditafsirkan.

## 6. Kriteria (ditetapkan sebelum run, tidak diubah sesudahnya)

Drafter `DRAFTED` ≤ 5 submit, node wajib merah karena assertion pada perilaku dari issue, writable tidak lebih luas dari paket modul
issue; dinilai dari isi draf saja. Berhasil bila `resolved: true`. Dilaporkan apa adanya, termasuk redraft dan retry. Tidak ada patch
yang diterapkan ke sympy.
