# Spek: berkas yang dilindungi per repo, dipaksa harness

Status: **keputusan Atha 2026-10-31, diimplementasikan di #270** (bagian 5; celah hapus/rename dan symlink ditambahkan sebagai P8 dan jaminan 8). Jalur ketat (scope, cek draf, paket review). Satu PR. Menggantikan
`~/argus-viewer-issues/check_protected.py` (skrip di luar repo yang dijalankan Claude) dengan aturan di harness. Prasyarat
shadow mode dan approve dari UI kontrol (`PENDING.md`).

## 1. Masalah

Scope sebuah task (writable/protected) ditulis **drafter** per draf. Repo tidak punya cara menyatakan "berkas ini tidak pernah
diubah agen, apa pun drafnya". Yang ada sekarang:

- **vitest:** `VITEST_LOADED` (`acceptance/contract.py`): config vite/vitest, `package.json`, `.npmrc` di root tidak boleh
  writable. Daftar tetap di kode, hanya root, hanya untuk vitest.
- **`argus-viewer`:** `PROTECTED` di repo + `check_protected.py` (mode `draft`, `patch`, `commit`) yang dijalankan Claude saat
  approve dan sebelum `argus applied`. Bergantung pada ingatan Claude; tidak ada di job, tidak dites di Argus.
- Contoh yang lolos tanpa skrip itu: draf dengan writable `src/**` membiarkan agen **membuat** `src/x/package.json` atau mengubah
  `public/sw.js`; draf dengan writable `*` membiarkan agen membuat `postcss.config.js` (dieksekusi saat build) atau `.env`.
  Pin `SW_SHA256` dan cek workspace vitest menangkap sebagian, tidak semuanya.

## 2. Usul

**P1. Sumber daftar.** Berkas `.argus/protected` di repo target: satu glob per baris (aturan glob kontrak: `**` melintasi
direktori, `*` dan `?` di satu komponen), baris kosong dan `#` diabaikan. Dibaca **dari commit job** (`git show
<commit>:.argus/protected`), tidak pernah dari working tree, saat `argus code` membuat job. `.argus/protected` sendiri selalu
dilindungi.

**P2. Dibekukan per job.** `job.json` mencatat `protected_repo: {"sha256": <hash berkas>, "globs": [...]}` (atau
`null` bila berkas tidak ada) di samping `environment_image`. Tahap sesudahnya memakai catatan ini, tidak membaca ulang. Approve
menyalinnya ke record task (`fixtures/intake/<task>.json`), yang dibaca setup run, tools, dan paket review. Berkas yang
tidak bisa dibaca sebagai daftar (bukan UTF-8, glob tidak sah, > 200 baris) → job **tidak dibuat**, pesan menyebut barisnya.

**P3. Cek draf.** Draf ditolak bila sebuah berkas di commit yang cocok dengan daftar juga cocok dengan writable kontrak (pesan
menyebut berkas dan glob). Sama dengan `check_protected.py draft` sesudah dilonggarkan: berkas yang tidak writable aman walau
tidak disebut di protected kontrak. Tes baru drafter (`new_tests`) boleh cocok dengan daftar (mis. `**/*.test.*`) karena
berkas baru dan disetujui manusia. **`changed_tests` pada berkas yang cocok dengan daftar ditolak** (K3): "dilindungi" berarti
tidak diubah lewat draf apa pun; bila perlu diubah, Atha mengubahnya lewat commit sendiri.

**P4. Tulis agen.** `_writable` di `codetask/tools.py` menolak path yang cocok dengan daftar repo, sebelum cek writable kontrak,
dengan pesan sendiri ("protected by the repository (.argus/protected)"). Ini juga menutup **berkas baru** yang cocok (glob
writable yang lebar tidak lagi cukup).

**P5. Paket review.** `changes_in_scope` (`codetask/review.py`) menolak setiap perubahan agen pada path yang cocok dengan daftar
repo → paket `REVIEW_INVALID`. Tes yang disetujui ada di pristine, jadi tidak terhitung sebagai perubahan agen.

**P6. Tanpa daftar.** Repo tanpa `.argus/protected` (argus-ledger, sympy, repo Argus) tidak berubah perilakunya, **kecuali**
environment yang di `config.yaml` bertanda `protected_required: true` (sekarang hanya `pwa_node22`): di sana job **tidak dibuat**
tanpa daftar (commit yang tidak sengaja menghapus `.argus/protected` tidak boleh mematikan proteksi diam-diam; viewer
dipublikasikan ke staging). `VITEST_LOADED` tetap berlaku untuk vitest apa pun daftarnya.

**P8. Hapus, rename, symlink.** Tidak ada perubahan pada berkas di daftar lewat jalan lain selain tulis/edit:
- Agen tidak punya tool hapus, rename, atau symlink; validasi berjalan dengan workspace read-only. Dijadikan jaminan: setiap tool
  yang mengubah workspace (sekarang `WriteFile`, `EditFile`) melewati satu pemeriksaan (`_writable`), dan daftar tool yang
  mengubah workspace dites, sehingga tool hapus/rename di masa depan wajib melewati pemeriksaan yang sama (tes gagal bila
  ada tool baru yang menulis tanpa `_writable`).
- Symlink: path jail (`tools/fs.py`) tidak pernah mengikuti symlink di level mana pun, dan pencocokan memakai path yang dinamai
  agen tanpa resolve. Symlink yang ada di commit (mis. `src/link.js → ../public/sw.js` di folder writable): `WriteFile` dan
  `EditFile` ke `src/link.js` **ditolak** (jail tidak pernah mengganti atau membuka link), target dan link tidak tersentuh.
- Penghapusan atau rename yang muncul di workspace (dari jalan apa pun) tetap ditolak di paket review (P5 memakai diff
  state, yang mencatat berkas hilang sebagai perubahan).

**P7. Layar dan status.** Layar `code`, `approve`, `retry` dan `argus status` menyebut `protected by the repository: N globs
(sha256 …)` atau `none`. Drafter mendapat daftarnya di prompt (supaya tidak menulis draf yang pasti ditolak).

## 3. Yang dijamin (dites; mutants)

1. Daftar dibaca dari commit job, bukan working tree: berkas working tree yang berbeda tidak berpengaruh.
2. Daftar dibekukan saat job dibuat: commit baru di repo atau perubahan berkas sesudahnya tidak mengubah tahap yang berjalan.
3. Draf dengan writable yang mencakup berkas di daftar ditolak; draf yang tidak menyentuhnya lolos walau protected kontrak tidak
   menyebutnya.
4. Agen tidak bisa menulis, mengedit, atau **membuat** path yang cocok dengan daftar, apa pun writable kontraknya.
5. Paket review dengan perubahan agen pada path di daftar tidak `valid`.
6. Daftar rusak → job tidak dibuat; tidak ada daftar → perilaku lama (tes perilaku lama tetap lulus tanpa diubah).
7. `.argus/protected` selalu dilindungi, juga bila tidak disebut di dalamnya.
8. Berkas di daftar tidak bisa dihapus, di-rename, atau ditulis lewat symlink: setiap tool yang mengubah workspace melewati
   `_writable` (tes daftar tool), symlink tidak pernah diikuti (tes sandbox dengan symlink di commit), dan berkas yang hilang
   dari workspace membuat paket review tidak valid.
9. Environment dengan `protected_required` tanpa `.argus/protected` di commit → job tidak dibuat.
10. `changed_tests` pada berkas di daftar → draf ditolak.

Tes P4 dan P8 memakai `Toolbox` dan path jail yang sebenarnya pada direktori nyata (tools berjalan di proses harness, bukan
di container, jadi tidak butuh Docker), plus job router ujung ke ujung dengan model palsu: agen mencoba membuat berkas di
daftar, dan tool yang "lupa" daftar tertangkap di paket review. `tests/test_protected_files.py`, satu tes per jaminan.

## 4. Sesudah merge (jalur cepat)

Sampai merge, `check_protected.py` manual tetap pengaman sementara di setiap job `argus-viewer`.


- `argus-viewer`: `PROTECTED` → `.argus/protected` (commit Claude), isi sama.
- `check_protected.py` tidak dipakai lagi di langkah approve/apply; disimpan sebagai riwayat. Satu job viewer berikutnya dicek
  dengan daftar dari harness (layar menyebutnya).

## 4b. Review #270 (code review medium + security review)

Security review: tanpa temuan >= 8/10. Code review medium, 9 temuan; diperbaiki:
- **Daftar bisa hilang diam-diam di antara job dan record task:** `job.json` kini menyimpan daftar lengkap (`sha256`, `globs`);
  setiap tahap agen (approve, retry, resume) menolak (`BLOCKED`) bila record task berbeda dari daftar job, atau bila
  environment mewajibkan daftar dan job berasal dari sebelum daftar ada.
- **BOM** di awal berkas (editor Windows) tidak lagi menjadi bagian glob pertama; karakter tak terlihat ditolak.
- **Nama direktori tanpa `/**`** (mis. `public`) ditolak dengan petunjuk, bukan diam-diam tidak melindungi apa pun.
- **Entri daftar tanpa wildcard yang tidak ada di intake** (berkas yang belum ada, atau `.argus/protected` yang di-exclude)
  juga tidak boleh writable di cek draf.
- Satu pembacaan daftar per job (router meneruskannya ke intake); glob dikompilasi sekali (`lru_cache`); review tanpa guard mati.

Tidak diubah: tes baru yang cocok dengan daftar (P3) hanya bisa berupa berkas tes (`test_*.py`, `*.test.js|jsx|ts|tsx`),
jadi tidak bisa menanam `postcss.config.js` atau sejenisnya.

## 5. Keputusan Atha (2026-10-31)

- **K1:** `.argus/protected`.
- **K2:** perilaku lama untuk repo tanpa daftar, **kecuali `pwa_node22`**: daftar wajib (P6).
- **K3:** `changed_tests` pada berkas di daftar **ditolak** (bisa dilonggarkan nanti bila terbukti perlu).
- **K4:** **tanpa mengejar tenggat up2**; perubahan keamanan jalur ketat tidak dipercepat. Satu PR jalur ketat pada satu
  waktu: bila belum selesai saat up2 dimulai, Atha memilih yang didahulukan.
- Tambahan Atha: hapus/rename dan symlink (P8, jaminan 8).
