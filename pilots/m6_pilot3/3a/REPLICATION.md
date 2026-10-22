# M6 pilot 3a: replikasi (run live ulang, kontrak yang sama)

Status 2026-10-22: **jalur siap; belum dijalankan.** Tujuan: menjawab satu pertanyaan dari `INVESTIGATION.md`: apakah kegagalan `pilot3a` stabil di sisi model? Sisi harness sudah terbukti identik (replay). Tidak ada yang diubah:
kontrak `fix_run_inspectors` (sha256 `0826ee93de65…`), profil `large`, cap pilot $0,75 (`config_pilot3a.yaml`), tes, dan snapshot task tetap. Run id `pilot3a2`.

- **Skrip:** `pilots/m6_pilot3/3a/go_live.sh` (di repo, nilai yang diharapkan tertulis di dalamnya): `--check-only` menjalankan semua gerbang tanpa meminta kunci dan tanpa membuat run; `go_live.sh pilot3a2` menjalankan gerbang, meminta kunci (tidak tampil), menjalankan satu run, lalu menghapus kunci dari shell.
- **Gerbang:** checkout bersih; kontrak, hash, profil, batas, dan scope tulis sesuai; `config_pilot3a.yaml` sha256 `46e9d99f…` dan berbeda dari `config.yaml` hanya pada `budget.max_usd`; batas efektif (`large`, 45.000 token, $0,45 per attempt, cap $0,75, 3 attempt); tanpa `ARGUS_LIVE=1` runner menolak tanpa membuat run; id berbentuk `pilot3a<angka>` dan belum ada.
- **Diuji** di worktree buangan (`evidence/go_live_tests.txt`): lolos pada keadaan benar (dua kali) dan menolak hash kontrak salah, profil salah, cap config $1,00, `config.yaml` diubah di tempat lain, tree kotor, id sudah ada, id salah bentuk (termasuk injeksi dan id run lama `pilot3a`), kunci kosong, dan tanpa argumen.
- **Aturan:** satu run. `reservation_exhausted` atau `FAILED_ACCEPTANCE` adalah hasil, bukan alasan mengulang atau menaikkan cap. Hasil dilaporkan sebagai replikasi dan dibandingkan dengan `pilot3a` (jalur langkah, token per langkah, `ListFiles` ya atau tidak, modul data dibaca atau tidak, perbaikan impor ya atau tidak).
- **Yang akan dicatat:** status, biaya, attempt, langkah per attempt dan token per langkah, berkas yang dibaca, apakah ada `ListFiles`, apakah `NameError` diperbaiki, waktu supervisi (ditanyakan ke Atha setelah run).
