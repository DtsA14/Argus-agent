# M6 W1: sandbox untuk repo Argus (lingkungan bernama dan validasi pytest)

Status: **implementasi untuk review.** 2026-10-17. Rencana: `docs/reviews/M6_PLAN.md` W1. Tanpa run live dan tanpa
biaya model.

## 1. Yang dibangun

| Bagian | Isi |
|---|---|
| **Lingkungan bernama** | `sandbox.environments.argus.image` di `config.yaml`. Sebuah validasi di kontrak boleh menyebut `"environment": "argus"`; tanpa itu, image default yang dipakai, persis seperti sebelumnya. Image lingkungan hanya bisa diganti lewat variabelnya sendiri (`ARGUS_SANDBOX_IMAGE_ARGUS` atau `.sandbox_image_argus`), **tidak pernah** oleh `ARGUS_SANDBOX_IMAGE` (`tools/sandbox.py` `settings`, `environment_image`). |
| **Gagal tertutup** | Nama yang tidak dikenal: `status` tidak tersedia, dan tidak ada container yang dijalankan. Di code task, setup memeriksa nama dan image setiap lingkungan **sebelum panggilan model pertama**: nama tidak dikenal menjadi `BLOCKED invalid_contract`, image tidak ada menjadi `BLOCKED sandbox_unavailable` (`codetask/run.py` `setup`). |
| **Image Argus offline** | `scripts/build_argus_sandbox_image.sh [VENV]`: python dan stdlib mesin ini ditambah site-packages dari venv yang dipasang dari `requirements.txt`, lewat `docker import`, tanpa registry dan tanpa unduhan. Waktu file, pemilik, dan urutan dipatok. Hasilnya `.sandbox_image_argus` (image id) dan `.sandbox_image_argus.json` (rootfs, versi python, sha requirements, sha `pip freeze`, commit, waktu build). `verify.sh` membangunnya dari venv barunya sendiri. |
| **Validasi pytest** | `python -m pytest TARGET... [-k NAME]`. Kontrak hanya boleh menyebut target (path relatif atau node id) dan `-k`. Semua opsi lain dipasang harness: tanpa cache, `addopts` dari ini dikosongkan, baris per tes klasik, `--rootdir /workspace` (`acceptance/validation.py` `PYTEST_FIXED`). `-p`, `-o`, `-c`, `--rootdir`, path absolut, dan `..` ditolak. |
| **Hasil per node** | `parse_pytest`: status per node id, dipetakan ke istilah yang sudah dipakai harness (`ok`, `FAIL`, `ERROR`, `skipped`, `expected failure`, `unexpected success`). Tes yang lulus lalu gagal di teardown mendapat status terburuk. `must_pass` untuk pytest wajib berupa node id (`path.py::nama`). Node yang tidak terkoleksi berstatus "did not run" dan gagal. |
| **Hasil yang tidak bisa dipercaya gagal** | Run pytest hanya dipercaya kalau baris per tes **persis** menjelaskan ringkasannya: jumlah per status sama, dan satu node per tes yang terkoleksi dan terpilih. Kalau tidak, gagal dengan "pytest output inconsistent". Output terpotong, tanpa ringkasan, exit code bukan 0, error koleksi (exit 2), target tidak ada (exit 4), dan semua tes ter-deselect (exit 5) juga gagal. |
| **Memo** | Versi tool RunValidation memuat image setiap lingkungan yang dipakai kontrak. Kontrak tanpa lingkungan memakai key yang sama seperti sebelumnya. |

Di luar scope W1: profil budget (W5), intake (W4), paket review (W3), draf kontrak (W2).

## 2. Bukti

- **Reproduksi image:** dua build dengan skrip resmi menghasilkan rootfs yang sama
  (`sha256:52fc08cc…` di VM, python 3.12.3). Image id berbeda per build karena `docker import` mencatat waktu
  pembuatan. Run mematok image id; rootfs yang membuktikan isinya sama.
- **Determinisme per node, bukan hanya total:** `tests/test_pytest_sandbox.py` menjalankan repo demo dua kali di
  sandbox. Peta status ke-13 node identik di kedua run dan sama dengan yang diharapkan.
- **Isolasi di dalam lingkungan argus:** tes di repo demo lulus hanya kalau tidak ada jaringan, workspace read-only,
  dan proses berjalan sebagai nobody.
- **Image default tidak pernah dipakai diam-diam:** validasi yang sama tanpa lingkungan gagal dengan
  `No module named pytest`.
- **Tes Argus sendiri** (`test_parse_subtests.py` dan `test_pytest_validation.py`) lulus di lingkungan argus dengan
  node wajib. Itu termasuk id parametrize yang memakai spasi, kutip, dan `...`.
- **Output asli:** parser diuji pada output pytest asli dari sandbox (`tests/data/pytest_*.txt`) untuk semua status,
  error koleksi, file dan node yang tidak ada, deselect, dan id dengan spasi. Ada juga empat output yang dimanipulasi:
  baris dihapus, baris dipalsukan, ringkasan dihapus, ringkasan diubah. Keempatnya gagal walaupun exit 0.
- **Mutan: 18/18 tertangkap.** Yang diuji, per kelompok:
  - lingkungan tidak diteruskan, override default menimpa image lingkungan, nama tidak dikenal jatuh ke image
    default, status mengabaikan error lingkungan;
  - setup tidak memeriksa nama, setup tidak memeriksa image;
  - konsistensi tidak diwajibkan, jumlah baris tidak dibandingkan, baris berikutnya menimpa status yang lebih buruk,
    output terpotong dipercaya, ringkasan hilang dipercaya;
  - skip dihitung ok, xpass dihitung ok;
  - opsi pytest apa pun diizinkan, target tidak dicek, `must_pass` pytest tidak dicek sebagai node id, nama
    lingkungan tidak dicek;
  - versi memo mengabaikan lingkungan.
- **Kontrak lama:** tidak ada yang berubah. Semua tes code task, acceptance, sandbox, eval, dan crash-resume yang ada
  tetap lulus. `verify.sh`: lihat PR.

## 3. Batas yang diketahui (dicatat, tidak disembunyikan)

Run tes Argus penuh di lingkungan argus (eksperimen sebelum W1, commit `5f1c2c5`):
**794 lulus, 4 gagal, 55 dilewati.**

- **4 tes `tests/test_verify_provenance.py` gagal** karena butuh `git` dan `bash`, yang tidak ada di image.
  **Keputusan: image tidak ditambah git dan bash.** Tes itu menguji alat verifikasi di host (`scripts/provenance.sh`),
  bukan kode yang akan diubah task. Tes itu tetap dijalankan `verify.sh` di host, dan tidak boleh menjadi kriteria
  task di lingkungan argus. Kalau suatu task benar-benar membutuhkannya, itu keputusan terpisah dengan kebutuhan yang
  jelas.
- **55 tes dilewati** karena butuh Docker (sandbox di dalam sandbox). Tes itu juga hanya berjalan di `verify.sh` di
  host, dan tidak bisa menjadi kriteria task.
- **Id parametrize dengan spasi** didukung untuk hasil. `must_pass` tetap harus tanpa spasi.
- **Pemalsuan dari dalam proses:** seperti unittest, hasil dibaca dari output runner yang berjalan di proses yang sama
  dengan kode yang diuji. Kode yang sengaja memalsukan output pytest tidak terdeteksi di sini. Itu dibatasi oleh
  sandbox, file tes yang protected, dan cek konsistensi.
- **Image hanya untuk arsitektur dan python mesin pembangunnya** (VM: aarch64, 3.12.3). Mesin lain membangun image-nya
  sendiri, dengan rootfs yang berbeda.
