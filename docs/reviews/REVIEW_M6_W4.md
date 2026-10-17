# M6 W4: intake dan provenance

Status: **implementasi untuk review.** 2026-10-17. Rencana: `docs/reviews/M6_PLAN.md` W4. Tanpa run live.

## 1. Yang dibangun

| Bagian | Isi |
|---|---|
| **Intake** | `scripts/intake_repo.py --repo R --commit C --name N [--exclude P ...]` (`acceptance/intake.py`). Commit C dari repo R menjadi `fixtures/repos/N`. Catatannya ada di `fixtures/intake/N.json`, **di luar workspace**, jadi agen tidak bisa melihat atau mengubahnya. Isi catatan: repo, commit penuh, tree, pengecualian, jumlah file, hash snapshot, dan file executable. Intake tidak pernah menimpa. |
| **Isi = tree commit persis** | Setiap blob ditulis dari `git cat-file`, bukan `git archive`. `git archive` menerapkan `.gitattributes` (`export-ignore`, `export-subst`), jadi isinya bisa berbeda dari commit. Ini **penyimpangan kecil dari rencana** ("git archive"), dengan alasan itu. Tesnya memakai repo dengan `export-ignore`, `export-subst`, dan CRLF: semua byte sama dengan commit. |
| **Fail closed saat intake** | Ditolak: nama yang bukan nama huruf kecil; pengecualian yang bukan path relatif polos, atau yang tidak cocok dengan apa pun (salah ketik tidak boleh diam-diam mengecualikan apa-apa); symlink atau submodule yang tidak dikecualikan; commit yang tidak ada. Penolakan tidak meninggalkan apa pun. Git berjalan tanpa konfigurasi pengguna atau sistem dan tanpa hook. |
| **Kredensial** | URL `origin` dicatat tanpa user atau password (`https://user:token@…` menjadi `https://…`). Path lokal mesin tidak dicatat. |
| **Cek saat setup** | Kalau workspace kontrak punya catatan intake, setup membandingkan snapshot dengan catatan itu **sebelum panggilan model pertama**: hash isi, jumlah file, dan bit executable. Kalau ada file yang berubah, bertambah, atau terhapus, hasilnya `BLOCKED invalid_contract` ("input repository changed since intake"). Fixture tulisan tangan yang sudah ada tidak punya catatan, jadi berjalan seperti sebelumnya. |
| **Provenance di `result.json`** | Isinya `input` (workspace, hash snapshot salinan, dan catatan intake: name, repo, commit, tree, exclude; atau `null`) dan `argus` (commit Argus yang menjalankan agen, dan apakah file terlacaknya berubah). Keduanya ditetapkan di setup dan disimpan di checkpoint, jadi resume tidak mengubahnya. |

`inputs.workspace` tetap wajib di bawah `fixtures/repos/`: intake yang mengisinya.

## 2. Bukti

- **Intake nyata:** repo Argus di `866ac4b`, dengan `verification` dikecualikan, ke direktori sementara. Hasilnya 384 file dan 2,7 MB dalam 0,3 detik. Empat skrip executable terdeteksi, dan cek terhadap catatan maupun terhadap tree commit yang dibangun ulang dari repo sama-sama bersih.
- **Tes** (`tests/test_intake.py`, `tests/test_codetask.py`):
  - perubahan setelah intake terdeteksi: ubah, tambah, hapus, file di direktori baru, bit executable;
  - `__pycache__` bukan bagian snapshot;
  - commit yang lebih baru di repo tidak dianggap sama dengan intake;
  - symlink ditolak kecuali dikecualikan;
  - penolakan tidak meninggalkan apa pun;
  - intake tidak menimpa;
  - URL tanpa kredensial;
  - setup memblok input yang berubah sebelum panggilan model;
  - `result.json` memuat provenance, dengan atau tanpa intake.
- **Mutan: 12/12 tertangkap.**
  - Cek snapshot: hash tidak dibandingkan, bit executable tidak dibandingkan, cek terhadap repo selalu bersih.
  - Isi intake: pengecualian diabaikan, pengecualian yang tidak cocok diterima, symlink/submodule diterima, mode tidak disimpan.
  - Keamanan intake: intake menimpa, kredensial tersimpan di URL.
  - Setup dan hasil: setup tidak memeriksa intake, provenance tidak ada di `result.json`, commit intake tidak tercatat.
  - Log: `verification/mutants-w4-*.log`.

## 3. Batas

- `argus.dirty` hanya melihat file yang terlacak. File untracked di checkout Argus tidak dihitung.
- Bit executable hanya diperiksa di POSIX. Di Windows tidak ada artinya, dan tesnya dijalankan di VM.
- Repo besar memuat semua blob dalam satu panggilan `git cat-file --batch` ke memori. Untuk repo Argus itu 2,7 MB. Kalau suatu repo jauh lebih besar, ini perlu dibuat streaming.
