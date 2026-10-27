# Pilot SWE v0 batch 3: instance yang butuh Python 3.9 (preflight, ditulis sebelum run)

Status 2026-10-27: **persiapan; belum ada run.** Pilot pertama di environment dari image Python resmi (`sympy_py39`,
`docs/reviews/SPEC_ENV_FROM_PYTHON_IMAGE.md`, #201/#202). Selain environment, aturannya sama dengan `../batch1/PREFLIGHT.md`: satu
"go live" untuk semua tahap `argus code`, `approve` dan `retry` per "y", cap $1,00 per job, cap batch $3,00 (dihitung Claude dari
ledger sebelum setiap tahap live), ringkasan draf format tetap (tanpa hasil patch resmi, bagian 3a), kriteria `resolved` menurut
`swe_grade.py`, dan batas klaim (harness, bukan model; penilaian ala SWE-bench di Python 3.9.25, penilai milik Argus; instance publik).

## 1. Environment

`sympy_py39`: `python:3.9-slim` dipin digest, `pytest==8.4.2`, `mpmath==1.3.0`, requirements ber-hash. Di `~/pilot3a_live`: image
`sha256:2f684b89c437…`, rootfs `176cffbb…` (sama dengan build di `~/Argus-agent`), **cek environment PASS** (catatan
`.sandbox_image_sympy_py39.check.json` untuk id itu; router dan penilai menolak tanpa catatan itu). Id image dipin per job saat
`code`; image tidak dibangun ulang selama batch.

## 2. Instance

Lima kandidat yang di batch 1–2 ditolak karena Python 3.12, dicek ulang di `sympy_py39` (`feasibility.log`): patch resmi
`resolved`, patch kosong tidak.

| Instance | Versi | Modul | Issue (singkat) | Patch resmi | `F2P` / `P2P` | Difficulty |
|---|---|---|---|---|---|---|
| `sympy__sympy-21847` | 1.9 | `polys/monomials.py` | `itermonomials` salah dengan `min_degrees` | 4 baris | 1 / 9 | <15 menit |
| `sympy__sympy-21612` | 1.9 | `printing/str.py` | pecahan LaTeX kehilangan kurung | 2 baris | 1 / 98 | 15 menit–1 jam |
| `sympy__sympy-21379` | 1.9 | `core/mod.py` | `PolynomialError` tak terduga dari `subs()` | 12 baris | 1 / 91 | 15 menit–1 jam |
| `sympy__sympy-24661` | 1.12 | `parsing/sympy_parser.py` | `evaluate=False` diabaikan untuk relasional di `parse_expr` | 23 baris | 1 / 27 | 15 menit–1 jam |

**Tidak dipakai:** `sympy__sympy-22080`. Dengan patch resmi pun `PASS_TO_PASS` `test_sqrt` menjadi `missing`, karena nama itu
didefinisikan di dua berkas yang disentuh `test_patch` (`test_pycode.py` dan `test_lambdify.py`); penilai tidak menebak (K2
SPEC_SWE_PILOT), jadi instance ini tidak bisa dinilai adil. Bukan batas environment.

Issue: `<instance>/issue.txt` = `problem_statement` apa adanya.

## 3. Cara jalan

Setelah "go live", untuk setiap instance berurutan (`~/pilot3a_live`, `main`):

```bash
~/Argus-agent/.venv-verify/bin/python scripts/argus.py code --repo ~/swe/sympy --commit <base_commit> \
    --issue-file ~/swe/inst/<instance>/problem_statement.txt --environment sympy_py39 \
    --key-file ~/.config/argus/deepseek_key --yes
```

Agen memakai profil yang dipilih drafter; untuk `large_usd`, DeepSeek mendapat `max_input_tokens` 60.000 dan `max_output_tokens`
32.000 (#188, #200). Selama batch, `verify.sh` tidak dijalankan (venv yang sama).

## 3a. Tanpa bocoran jawaban (review Atha 2026-10-27)

Di batch 1–2, tes drafter dijalankan di atas patch resmi **sebelum** approve dan hasilnya ditampilkan di ringkasan; di batch 2 itu
memicu redraft. Itu menyaring draf dengan jawaban, yang tidak tersedia di repo nyata, jadi hasilnya mengukur "Argus + bocoran
jawaban". Batch 3 tidak memakainya:
- **approve hanya dari isi draf**: node wajib merah karena assertion, writable wajar, tes menguji perilaku dari issue;
- tes drafter di atas patch resmi **tidak dijalankan sebelum approve** (supaya penilaian Claude pun tidak terpengaruh), **tidak
  memicu redraft**, dan baru dijalankan **setelah grading**; hasilnya dicatat di `RESULT.md` (berapa draf yang lolos review ternyata
  salah paham, dan apakah itu yang membuat `resolved: false`);
- redraft tetap boleh atas "y" bila isi draf sendiri bermasalah (bukan karena patch resmi).

## 4. Ekspektasi (sebelum run)

Per instance ±$0,02–0,30. `21379` (12 baris) dan `24661` (23 baris) paling mungkin butuh lebih dari satu attempt atau `retry`.

## 5. Kriteria (ditetapkan sebelum run, tidak diubah sesudahnya)

Per drafter `DRAFTED` ≤ 5 submit, validasi di environment `sympy_py39`, node wajib merah karena assertion pada perilaku dari issue,
writable tidak lebih luas dari paket modul issue; dinilai dari isi draf saja (bagian 3a). Per instance berhasil bila `resolved: true`. Hasil batch
dilaporkan apa adanya per instance, termasuk redraft dan retry. Tidak ada patch yang diterapkan ke sympy.
