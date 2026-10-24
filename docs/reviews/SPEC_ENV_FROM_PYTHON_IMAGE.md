# Spec: environment sandbox dari image Python resmi (versi Python per environment)

Status: **spec, belum dikoding.** 2026-10-24. Langkah 3 rencana SWE (diskusi 2026-10-24). **Keputusan yang diminta: bagian 7.**

## 1. Masalah

Setiap image environment sekarang dirakit dari **python host** (3.12) ditambah site-packages sebuah venv (`build_env_sandbox_image.sh`).
Akibatnya, task yang butuh Python lain tidak bisa dinilai dengan adil:
- 3 instance sympy 1.9 (`21847`, `21612`, `21379`) dan `22080` (sympy 1.10, `sympy/codegen/tests/test_rewriting.py`):
  `import distutils`, yang dihapus di Python 3.12;
- `24661`: dengan patch maintainer pun 2 `PASS_TO_PASS` gagal (parser 3.12);
- hampir semua task "1–4 jam" di SWE-bench Verified dan repo lain (django, astropy, scikit-learn) memakai Python 3.6–3.11; SWE-rebench
  juga beragam.

Penilai menolak semua kasus itu dengan benar (bukan mencatat gagal), tapi tasknya tidak bisa dipakai.

## 2. Usulan

### 2.1 Definisi environment di repo

`environments/<name>/` (di-commit):
- `base`: satu baris, image Python resmi **dipin digest**, mis. `python@sha256:2d97f6910b16…` (`python:3.9-slim`, Python 3.9.25,
  arm64; diambil 2026-10-24);
- `requirements.txt`: dependensi yang dipin **dengan hash** (`pip install --require-hashes`), termasuk pytest versi yang mendukung
  Python itu (pytest 9 tidak mendukung 3.9, jadi `pytest==8.4.*` dipin persis);
- `README` satu paragraf: untuk task apa environment ini (mis. sympy 1.9–1.10 SWE-bench).

Environment pertama: **`sympy_py39`** (Python 3.9, `mpmath==1.3.0`, pytest 8.4.x dan dependensinya).

### 2.2 Build (`scripts/build_env_from_base.sh NAME`)

1. **Builder** (satu-satunya langkah dengan jaringan): `docker run --rm` dari `base` dengan direktori keluaran ter-mount, menjalankan
   `pip install --no-deps --require-hashes --target /out/site -r requirements.txt`, lalu menyalin ke `/out/root` hanya yang
   dibutuhkan: interpreter (`/usr/bin/python3` dan `python3.X`), `libpython`, stdlib (tanpa `test/`, `ensurepip`, `idlelib`, `tkinter`),
   `lib-dynload`, dan pustaka bersama yang dibutuhkan interpreter dan modul `.so` (dari `ldd` di dalam builder).
2. **Rakit di host**, persis seperti `build_env_sandbox_image.sh` sekarang: waktu dan pemilik berkas tetap, `tar --sort=name`,
   `docker import` dengan `PATH=/usr/bin` dan `WORKDIR /workspace`. Hasilnya: **tanpa shell, tanpa pip, tanpa git, tanpa Docker**.
3. Keluaran: `.sandbox_image_<NAME>` (id) dan `.sandbox_image_<NAME>.json` (digest base, sha `requirements.txt`, versi Python, versi
   pytest, rootfs), di-gitignore seperti sekarang. `config.yaml` mendapat `sandbox.environments.sympy_py39: {image: null}`.

Jaminan yang sama dengan image `argus`/`sympy`: isolasi run tidak berubah (tanpa jaringan, read-only, non-root, tanpa capability);
environment tanpa image ditolak (gagal tertutup, K4 SPEC_SWE_PILOT); id image dipin per job (K1). Rootfs harus sama untuk base digest
dan requirements yang sama (yang dibandingkan rootfs, bukan id).

### 2.3 Cek environment (`scripts/check_env_image.sh NAME`)

Sebelum environment dipakai job mana pun, satu skrip menjalankan di image itu, lewat jalur sandbox Argus yang sama dengan validasi:
- tes isolasi (`fixtures/repos/pytest_demo`: tanpa jaringan, workspace read-only, berjalan sebagai nobody);
- **klasifikasi per node yang sama dengan environment `argus`** untuk `pytest_demo` (ok, FAIL, skipped, expected failure,
  unexpected success, ERROR setup/teardown), karena parser Argus dibangun di atas output pytest 9;
- **cek red-by-assertion** (`RED_CHECK`, #179) dan koleksi (`collect_nodes`) di pytest versi environment itu;
- tidak ada `/bin/sh`, `pip`, `git` di image; versi Python dan pytest sesuai `.json`.

Lognya disimpan di `verification/env_<NAME>.log`. Environment yang cek-nya gagal tidak dipakai.

## 3. Instance yang terbuka

Pilot sesudahnya (preflight terpisah): sympy 1.9–1.10 di `sympy_py39`, mulai dari yang ditolak di Python 3.12 (`21847`, `21612`,
`21379`, `22080`) dan yang lebih berat; `24661` dicoba ulang. Kelayakan per instance tetap diperiksa dengan penilai (patch resmi
`resolved`, patch kosong tidak) sebelum preflight.

## 4. Yang tidak berubah

Router, environment per job, penilai, jalur uang, image `argus` dan `sympy` (tetap dari python host). Script lama tidak berubah.

## 5. Risiko

- **Rantai pasokan saat build:** `pip` mengunduh dari PyPI di builder. Ditekan dengan `--require-hashes` (paket yang tidak cocok
  hash-nya ditolak) dan base image dipin digest. Run tetap tanpa jaringan.
- **Pustaka sistem yang terlewat** oleh `ldd` (dimuat lewat `dlopen`): cek environment (2.3) akan gagal mengimpor modul itu; daftar
  tambahan per environment bila perlu.
- **Perbedaan output pytest 8 vs 9** yang tidak tertangkap `pytest_demo`: cek 2.3 hanya mencakup bentuk yang ada di fixture itu.
  Tes yang jalan di pilot SWE (`resolved` patch resmi, patch kosong tidak) menjadi lapis kedua.

## 6. Tes (gagal di kode lama; mutan)

1. Argumen build: nama environment tidak valid ditolak; `base` tanpa digest ditolak; `requirements.txt` tanpa hash ditolak (sebelum
   docker dipanggil).
2. Definisi `environments/sympy_py39/`: `base` berdigest, setiap baris requirements punya `--hash=sha256:`, pytest dipin persis.
3. Image hasil build (tes sandbox, butuh image itu; skip dihitung gagal di verify, jadi **verify.sh membangunnya** seperti image
   `argus`, dengan cache pip di luar repo): tanpa `/bin/sh` dan `git`; Python 3.9; klasifikasi `pytest_demo` sama dengan `argus`;
   red check dan koleksi bekerja; isolasi.
4. Dua build berurutan → rootfs sama.

Mutan untuk butir 1–2 dan untuk penyalinan file (mis. shell ikut tersalin), lalu `verify.sh`.

## 7. Keputusan

| | Pertanyaan | Usul |
|---|---|---|
| K1 | Environment pertama | `sympy_py39` (Python 3.9 resmi, pytest 8.4.x); versi lain menyusul per kebutuhan pilot |
| K2 | Jaringan saat build | Hanya di builder, dengan `--require-hashes` dan base berdigest; run tetap offline |
| K3 | `verify.sh` membangun `sympy_py39` | Ya (supaya tes sandbox-nya tidak skip), dengan cache pip di luar repo; menambah ±1–2 menit |
| K4 | Cek environment wajib | Ya, log `verification/env_<NAME>.log` sebelum environment dipakai pilot |
