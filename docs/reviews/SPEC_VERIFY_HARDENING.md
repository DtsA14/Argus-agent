# Spec VERIFY-HARDENING: mistakes of the sandbox group are caught in under a minute, and a failed `verify_at` costs less

Status: **dikerjakan atas "go" Atha 2026-11-13 untuk satu batch penuh ("berhenti kalau ada yang ragu"); merge menunggu kata "merge" dari Atha (strict lane).** Ditulis Claude.
Dasar: laporan diagnosis dan optimasi dari subagen Fable (2026-11-13) atas tiga `verify_at` yang gagal pada kerja APPEND-TESTS, dan pengukuran di log
`verification/verify-20261113T154903Z-aarch64.log`, `...T161049Z...`, `...T163214Z...`.

## 0. Masalah (terukur)

- Tiga `verify_at` (masing-masing 19 sampai 20 menit) gagal karena tes sandbox yang **lepas dari grup serial** (`conftest.py` memutuskan grup dari **teks sumber modul**, jadi modul yang memakai
  fixture `scfg` dari modul lain tidak terdeteksi) dan karena daftar eksplisit `SANDBOX_MODULES` yang belum diperbarui.
- `tests/test_red_caught.py` punya cacat yang sama sejak 2026-11-05 (mengimpor `scfg`, delapan tes memakai kontainer sungguhan, tidak punya teksnya, tidak berkelompok).
- Tiga pemeriksaan melihat **seluruh mesin**, bukan run-nya sendiri: `test_acceptance_sandbox.py` (`docker ps` berlabel `argus.sandbox=1` harus kosong), `test_sandbox.py` (menjalankan `docker rm -f` pada
  semua kontainer berlabel itu, dan memeriksa `ids[0]` dari daftar mesin). Job live atau `verify_at` kedua di mesin yang sama memengaruhinya, dan yang kedua bahkan bisa membunuh kontainer orang lain.
- Log hanya mencatat 25 durasi terpanjang, jadi ke mana 18,7 menit pytest habis hanya bisa diperkirakan (grup sandbox serial: 735 tes, 17 modul; yang terlihat di 25 teratas saja 505 sampai 512 detik).
- Sebuah run yang gagal di 7% tetap berjalan sampai habis, dan menghentikan `verify_at` dengan sinyal membiarkan worker pytest yatim sementara worktree-nya sudah dihapus.

## 1. Yang dibangun (urut dari yang murah dengan hasil bagus)

1. **`scripts/precheck.sh` (sekitar 45 detik).** Memilih tes dari berkas yang berubah terhadap sebuah basis (`scripts/precheck_select.py`: modul tes yang tersentuh, tes yang namanya memuat nama modul sumber yang tersentuh, dan
   himpunan tetap: `test_acceptance_sandbox.py`, `test_xdist_groups.py`, `test_verification_names.py`, `test_verify_at.py`, `test_verify_provenance.py`), memasang pin image seperti `verify.sh`, dan menjalankannya dengan
   `-n 4 --dist loadgroup`. Bukan bukti (tidak menulis log di `verification/`), tidak menggantikan `verify_at`, tidak dijalankan berbarengan dengannya. `PRECHECK_PRINT=1` hanya mencetak apa yang akan dijalankan.
2. **Durasi yang terukur.** `verify.sh` mencatat semua durasi sekurang-kurangnya 1 detik (`--durations=0 --durations-min=1.0`, bukan 25 teratas) dan `conftest.py` mencetak **total per grup** (sandbox dan lainnya: detik dan
   jumlah tes) di ringkasan akhir.
3. **Gagal cepat yang opt-in dan penghentian yang bersih.** `VERIFY_MAXFAIL=<n>` membuat `verify.sh` memakai `--maxfail=<n>` dan mencatat di log bahwa run itu boleh berhenti lebih awal (bawaannya tidak berubah: tanpa
   variabel itu perilaku persis seperti sekarang). `verify_at.sh` yang menerima INT atau TERM mematikan seluruh pohon proses `verify.sh` (pytest, worker, anak-anaknya) **sebelum** worktree dihapus.
4. **Pengelompokan lewat fixture.** `conftest.py` memasukkan sebuah tes ke grup sandbox bila modulnya memuat teks **atau** ada fixture dalam closure-nya yang didefinisikan di berkas yang memuat teks itu. Daftar
   `SANDBOX_MODULES` di `test_xdist_groups.py` kini dihitung dari koleksi sungguhan (subproses `--collect-only`), bukan dari heuristik teks yang sama dengan yang dijaganya; `test_red_caught.py` masuk daftar.
5. **Pemeriksaan kontainer dibatasi ke run-nya sendiri.** Tiga pemeriksaan di atas memakai label unik per tes (`argus.test=<token>`, lewat `labels` yang sudah didukung `tools/sandbox.py`) dan helper
   `tests/sandbox_scope.py`; ada tes yang membuktikan bahwa kontainer berlabel lain **diabaikan** dan tidak dihapus.

## 2. Sengaja tidak dikerjakan (diputuskan "berhenti kalau ragu")

- **Memecah grup sandbox menjadi dua** (hemat sekitar 6 sampai 8 menit): `docs/Reconciliation.md` mencatat exit 137 karena CPU berebut; dua kontainer berCPU 1 ditambah dua worker pada empat CPU butuh tiga run penuh yang bersih
  sebagai bukti, dan pengukuran di bagian 1.2 belum ada. Dikerjakan sesudah angka itu ada.
- **Memangkas run kontainer di `test_draft.py`** (1 sampai 3 menit): menyentuh tes jaminan untuk hemat kecil.
- **Cache venv dan tambahan worker**: tidak berguna (hemat kurang dari semenit, dan membuang jaminan venv segar; worker tambahan tidak menolong selama grup sandbox serial).
- **Penjaga otomatis untuk pemakaian `docker` langsung tanpa fixture** (autouse yang gagal bila item tak berkelompok memanggil `docker_args`): ide Fable, belum dibangun; pengelompokan lewat fixture menutup kasus yang terjadi.

## 3. Verifikasi

Tes di `tests/test_verify_hardening.py`, `tests/test_xdist_groups.py`, `tests/test_verify_at.py`, `tests/test_sandbox.py` dan `tests/test_acceptance_sandbox.py`; mutan di `verification/verify_hardening_mutants.py`;
satu `verify_at` penuh di commit akhir; satu review independen. Perubahan pada `test_sandbox.py` dan `test_acceptance_sandbox.py` mengubah **cara** sebuah jaminan diperiksa (dibatasi ke run-nya), bukan jaminannya.

## 4. Batas yang diketahui

- Pemilihan tes di pra-cek memakai kecocokan nama (`codetask/drafter.py` memilih `test_drafter*.py`); sebuah perubahan yang tesnya bernama lain tidak terpilih. `verify_at` tetap yang menentukan.
- Pengelompokan lewat fixture tidak melihat tes yang memanggil `docker` langsung tanpa fixture bersama.
- Dua cabang yang masing-masing menambah modul sandbox akan berselisih di satu baris `SANDBOX_MODULES`.
