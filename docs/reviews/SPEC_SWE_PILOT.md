# Spec: repositori luar lewat router, dinilai ala SWE-bench (`sympy__sympy-23534`)

Status: **spec, belum dikoding.** 2026-10-24. Fase 3 dari rencana pilot SWE-bench Verified (diskusi 2026-10-24); fase
1–2 (pilih instance, kelayakan environment) sudah dikerjakan tanpa biaya model. Syarat dari review Atha dimasukkan di
bagian 2–3. **Keputusan yang diminta: bagian 7.**

## 1. Tujuan dan batas klaim

Pilot pertama di repositori selain Argus, dengan target sukses dari luar: `FAIL_TO_PASS` dan `PASS_TO_PASS` resmi
instance SWE-bench Verified `sympy__sympy-23534` (sympy 1.11, satu baris di `sympy/core/symbol.py`). Alurnya tetap alur
Argus: intake di `base_commit`, drafter menulis tes sendiri dari issue, Atha approve, agen, paket review. **Sesudah**
itu baru penilai menerapkan tes resmi.

Klaim yang boleh ditulis dari hasilnya (review Atha):
- "**harness Argus menyelesaikan task SWE-bench dari ujung ke ujung**", bukan "model X memperbaiki bug yang belum pernah
  ia lihat": instance Verified publik sejak 2024 dan kemungkinan ada di data latih model (kontaminasi);
- "**penilaian ala SWE-bench**": Python 3.12 (environment resmi sympy 1.11 memakai 3.9) dan penilai milik Argus, bukan
  harness resmi. Tidak dibandingkan dengan angka leaderboard.

Kelayakan yang sudah diperiksa (fase 2): di sandbox Argus dengan image `sympy` (offline, tanpa shell dan git;
`mpmath==1.3.0`, `pytest==9.1.1`), `base_commit` + `test_patch` → `test_symbols` FAIL karena AssertionError, 12 lainnya
lulus; ditambah patch resmi → 13/13. Tree `base_commit`: 1.968 berkas, 35,7 MB, tanpa symlink, submodule, atau
`__pycache__`.

## 2. Perubahan harness

### 2.1 Environment per job (`argus code --environment NAME`)

Sekarang `drafter.environment: argus` ada di config, jadi setiap draf memakai environment Argus.
- `argus code --environment NAME`: bawaan `argus` (perilaku sekarang tidak berubah). Nama itu harus ada di
  `sandbox.environments` dan imagenya harus ditemukan. Bila tidak, job ditolak sebelum intake.
- `job.json` mencatat `inputs.environment` **dan id image yang dipakai** (`sha256:…`) saat job dibuat.
- **Image dikunci per job:** setiap tahap live (`code`, `redraft`, `approve`, `retry`, `resume`) membandingkan id image
  environment itu sekarang dengan yang tercatat. Bila berbeda (image dibangun ulang di tengah job), tahap **ditolak
  tanpa mengubah apa pun dan tanpa memanggil model**, dengan pesan yang menyebut kedua id. Aturannya sama dengan versi
  tool di memo key (`tool_version`): hasil sandbox dari image lain tidak dipakai ulang diam-diam.
- Drafter tahap job memakai environment itu (`drafter.environment` lewat `stage_config`), jadi setiap validasi yang ia
  tulis membawa `"environment": NAME`. Itu sudah tercatat di kontrak per validasi (`environment` di setiap entri
  `validation`).
- **Layar approve** menulis environment di setiap baris validasi (`validation target (env sympy): python -m pytest …`)
  dan id image pendek (12 karakter). `status` juga menampilkannya.
- **`setup_problems`** (dipakai cek draf dan setup, perbaikan #180) sudah menolak environment yang tidak dikonfigurasi.
  Pilot ini menambah tes untuk environment non-`argus`: draf dan setup sama-sama menolak nama yang tidak ada, dan
  menerima `sympy`.

### 2.2 Image per environment (`scripts/build_env_sandbox_image.sh NAME VENV`)

`build_argus_sandbox_image.sh` diumumkan: nama environment dan venv menjadi argumen. Image ditulis ke
`.sandbox_image_<NAME>` dan `.sandbox_image_<NAME>.json` (git-ignored; metadata berisi rootfs, python, `pip freeze` sha).
Cara rakitnya sama: python host + site-packages venv, offline, tanpa shell, git, atau Docker; waktu dan pemilik berkas
tetap. `build_argus_sandbox_image.sh` tetap ada sebagai pembungkus (`argus`, `.venv-verify`, `requirements.txt`).
`config.yaml` mendapat `sandbox.environments.sympy: {image: null}` (image dari berkasnya atau `ARGUS_SANDBOX_IMAGE_SYMPY`).

### 2.3 Penilai `scripts/swe_grade.py` (di luar sandbox, tanpa model)

```
python scripts/swe_grade.py --instance ~/swe/inst/sympy__sympy-23534 --repo ~/swe/sympy \
    --review <dir paket review> --sha <sha256 changes.patch> --environment sympy --out <grade.json>
```

Aturannya sama dengan penilai resmi (review Atha):
1. **Patch yang dinilai persis patch paket review:** sha256 `changes.patch` harus sama dengan `--sha` **dan** dengan
   `provenance.json` `patch.sha256`. Bila tidak sama, penilai berhenti tanpa menjalankan apa pun.
2. Tree `base_commit` ditulis dari repo (`intake.write_tree`, tanpa `.git`) ke direktori sementara, lalu
   `changes.patch` diterapkan (`git apply` di luar sandbox).
3. **Setiap berkas yang disentuh `test_patch` dikembalikan ke isinya di `base_commit`** (atau dihapus bila belum ada di
   sana), baru `test_patch` diterapkan. Jadi bila agen atau drafter mengubah berkas tes yang sama, `test_patch` tetap
   menang dan tidak bentrok.
4. Tes dijalankan di sandbox dengan environment yang sama (`run_validation`, `python -m pytest <berkas tes test_patch>`).
   Nama tes SWE-bench untuk sympy berupa nama fungsi (`test_symbols`), dan dipetakan ke node `berkas::nama` dari berkas
   yang disentuh `test_patch`. Nama yang tidak ditemukan atau ambigu dilaporkan, tidak ditebak.
5. **Hasil per node:** `FAIL_TO_PASS` dan `PASS_TO_PASS` masing-masing `{node: pass|fail|missing}`, dan
   `resolved = semua FAIL_TO_PASS pass dan semua PASS_TO_PASS pass` (definisi SWE-bench). Ditulis ke `--out`, bersama
   sha patch, id image, `base_commit`, dan sha `test_patch`.
6. **Tes drafter terhadap patch resmi** (informasi, bukan bagian dari `resolved`): tes yang di-approve dijalankan di atas
   `base_commit` + patch resmi. Hijau berarti tes drafter dan tes resmi menangkap perilaku yang sama.

### 2.4 Tes resmi tidak terlihat (syarat sah, review Atha)

Tidak ada kode baru di sini. Yang ditambah adalah **tes** yang membuktikan jaminan yang sudah ada:
- intake mengambil tree commit saja: snapshot dari repo yang **punya commit lebih baru** (berisi berkas "jawaban")
  tidak memuat `.git`, berkas dari commit yang lebih baru, maupun berkas di luar repo;
- sandbox hanya me-mount workspace: validasi di sandbox yang mencari (lewat `os.walk('/')`) penanda unik yang diletakkan
  di direktori host ala `~/swe` (dataset, `test_patch`, clone dengan `.git`) **tidak menemukannya**, dan tidak ada
  direktori `.git` di mana pun dalam container;
- `~/swe` berada di luar `~/pilot3a_live` dan job root, jadi juga di luar akar file tool drafter dan agen (path jail).

## 3. Yang tidak berubah

Jalur uang, router, drafter, approve, agen, dan paket review. Job tanpa `--environment` berperilaku seperti sekarang.
Penilai tidak memanggil model.

## 4. Tes (gagal di kode lama; mutan)

1. `--environment`: tercatat beserta id image; nama tidak dikenal atau image tidak ditemukan → ditolak sebelum intake;
   drafter tahap job memakai environment itu; tanpa opsi → `argus`.
2. Image berubah di tengah job → `approve`/`retry`/`resume`/`redraft` ditolak tanpa mengubah `job.json` dan tanpa
   panggilan model.
3. Layar approve dan `status` menyebut environment per validasi dan id image.
4. `setup_problems` untuk environment non-`argus`, di cek draf dan setup.
5. Script build: dua kali build dari venv yang sama → rootfs sama; image tanpa shell dan git (seperti tes image
   `argus`).
6. Penilai: sha patch yang salah → berhenti; berkas tes yang diubah agen → dikembalikan lalu `test_patch` menang; hasil
   per node; `resolved` false bila satu `PASS_TO_PASS` gagal; nama tes yang tidak ada → `missing`. Dengan repo sintetis
   kecil dan validasi palsu, ditambah satu tes sandbox nyata.
7. Tes bagian 2.4 (snapshot tanpa commit baru dan `.git`; penanda host tidak terlihat di sandbox). Tes sandbox yang
   di-skip tidak dihitung lulus.

Mutan untuk setiap butir di atas, lalu `verify.sh` penuh di latar belakang. Bukti di `verification/`.

## 5. Pilot (sesudah PR kode)

Preflight terpisah (`pilots/swe_v0/sympy__sympy-23534/`): issue = `problem_statement` apa adanya, kriteria ditulis
sebelum run, cap job $1,00. **Berhasil bila `resolved` menurut `swe_grade.py`**; `DONE` dari Argus saja tidak cukup.
Dicatat juga: apakah tes drafter hijau di atas patch resmi, biaya, keputusan, serta kalimat klaim dari bagian 1.

## 6. Data di luar repo

`~/swe/` (dataset parquet, `inst/<id>/` berisi `patch.diff`, `test_patch.diff`, `FAIL_TO_PASS.txt`, `PASS_TO_PASS.txt`,
`base_commit.txt`, `problem_statement.txt`, dan clone sympy). Tidak di-commit ke repo Argus. Skrip pemilih instance
disimpan bersama bukti pilot.

## 7. Keputusan

| | Pertanyaan | Usul |
|---|---|---|
| K1 | Image berubah di tengah job | Tahap ditolak tanpa perubahan (bukan `BLOCKED`), supaya manusia bisa mengembalikan image atau `abandon` |
| K2 | Pemetaan nama tes sympy | `berkas::nama` dari berkas yang disentuh `test_patch`; tidak ditemukan atau ambigu = `missing`, tanpa tebakan |
| K3 | Tes drafter vs patch resmi | Ikut dilaporkan penilai sebagai informasi, tidak memengaruhi `resolved` |
| K4 | Environment `sympy` di `config.yaml` | Ya, sebagai entri `{image: null}`; imagenya dari berkas lokal yang di-gitignore |
