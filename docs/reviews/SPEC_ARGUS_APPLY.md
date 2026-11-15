# SPEC `argus apply`: menerapkan paket review ke repo target dengan satu perintah

Status: **revisi 2, 2026-11-15, menunggu persetujuan Atha** (jalur ketat: mengubah repo target di host dan mencatat keputusan manusia di
`job.json`). Langkah kedua urutan inti (Atha 2026-11-15) sesudah VF O1 (ter-merge #550). Revisi 1 menerapkan tinjauan Fable (GO WITH CHANGES; semua
temuan di bawah diuji di repo sementara, git 2.43.0; Revisi 2 menerapkan tinjauan Opus atas revisi 0 (buta, NO-GO karena temuan 1; semua dibuktikan dengan menjalankan) dan bagian B atas revisi 1: konfigurasi global/sistem dipasang ulang terisolasi, `.gitignore` dan `.github/` tidak ikut ditolak, masuk ulang diperiksa sebelum penjaga HEAD, kunci di `jobs/`, patch-id langkah 6 lewat pembantu PR 1, sha256 patch dicatat di `job.json`. Bahan:
`pilots/prd_probe_v0/RESULT.md` dan `GLUE_LOG.md` (tiga apply dengan tangan, semuanya mekanis), `router/job.py` (`applied`, `Job.lock`),
`codetask/review.py` (pembuat paket), `acceptance/intake.py` (`git`).

## 1. Masalah

Sesudah `REVIEW_READY`, "sampai staging" selalu butuh seseorang untuk: membaca patch, `git apply`, membuat commit di repo target, lalu
`argus applied <job> --commit <sha>`. Itu sambungan yang paling terasa dari probe PRD, dan satu-satunya langkah dari issue ke staging yang dilakukan
Claude dengan tangan tanpa keputusan apa pun di dalamnya. Yang **bukan** mekanis (membaca isi patch) tetap ada: VF O1 hanya menaikkan biaya
pemalsuan verdict, aturan "jangan apply job `DONE` tanpa dibaca" tetap berlaku.

## 2. Dua PR, berurutan (satu PR ketat pada satu waktu)

- **PR 1, memperbaiki `applied()` (temuan 1 dan 4):** perbandingan `as_is` memakai `git show` yang tidak sama dengan cara patch dibuat
  (`--binary --full-index --no-renames`, `codetask/review.py:148`), jadi patch biner, pindah berkas, atau `diff.noprefix`/`diff.renames=false`/`diff.context`
  lokal membuat `as_is` salah (terbukti) dan `show` menjalankan textconv. Perbaikan: `git show --no-color --no-ext-diff --no-textconv --binary --full-index
  --no-renames` dengan `-c diff.noprefix=false -c diff.renames=false -c diff.context=3` dan semua `GIT_*` dibuang dari lingkungan. Dan memecah
  `applied()` menjadi pencatat dalam (`_record_applied`, tanpa kunci) yang dipanggil `applied()` (yang memegang kunci) dan nanti `apply`. Perilaku `applied` yang
  terlihat tidak berubah selain `as_is` yang kini benar. Tes: patch biner, pindah berkas, `diff.noprefix`, textconv. Juga: sha256 `changes.patch` dicatat di `job.json` saat job menjadi `REVIEW_READY` (`provenance.json` ada di sebelah patch, jadi mengubah keduanya lolos bila hanya keduanya yang dibandingkan). Mutan.
- **PR 2, `argus apply`:** bagian 3 sampai 8.

## 3. Perintah

`argus apply <job> --read-sha <sha256 patch, minimal 12 karakter> [--note TEKS]`

`--read-sha` sama bentuknya dengan `approve --sha` (awalan 12+ karakter dari yang `status` cetak: sha256 penuh `changes.patch` di disk sekarang) dan harus
sama dengan sha256 berkas itu sekarang. Isinya pernyataan "patch dengan sha ini sudah dibaca"; **bukan bukti pembacaan**, sama dengan `approve --sha` hari ini.
Tanpa `--read-sha`, tidak ada apply. Tidak ada `--onto-descendant` di v0 (K2): validasi paket dijalankan pada pohon dasar, bukan pada turunannya.

## 4. Langkah, berurutan (berhenti dan tidak mengubah apa pun di langkah pertama yang meleset)

1. **Job:** `REVIEW_READY` dengan paket yang valid. `provenance.json` `patch.sha256` sama dengan sha256 berkas sekarang, sama dengan yang dicatat PR 1 di `job.json`, dan sama dengan `--read-sha`; glob
   `job.data["protected_repo"]` dicek ulang terhadap berkas di patch (paket sudah menolak `.git`, glob terlindungi, di luar lingkup dan non-reguler,
   `codetask/review.py:316-328`, tetapi `job.json` tidak mengikat patch di disk; ini yang mengikatnya).
2. **Lingkungan git bersih:** semua `GIT_*` dan `EMAIL` dibuang, `GIT_CONFIG_NOSYSTEM=1` dan `GIT_CONFIG_GLOBAL=/dev/null` dipasang pada **setiap** panggilan (konfigurasi global dibaca satu kali saja, untuk identitas, di langkah 7); semua opsi di bawah berlaku untuk **setiap** panggilan git, termasuk `apply --index` (hook `post-index-change`) dan `apply -R`; `-c user.useConfigOnly=true`, `-c core.fsmonitor=false`, `-c commit.gpgsign=false`, `-c gc.auto=0`, `-m` (tanpa editor), `-c
   core.hooksPath=/dev/null`, `--no-verify`, `--no-textconv`, `--no-ext-diff`; `git rev-parse --show-toplevel` sama dengan `inputs.repo` yang di-resolve. Repo
   target adalah **kode tepercaya**: biner `git`, isi `.git/` (termasuk `info/attributes`) dan konfigurasi lokal tidak dapat dikendalikan perintah ini.
3. **Konfigurasi lokal diperiksa:** `git config --local --list` hanya boleh berisi kunci dari daftar putih (`core.repositoryformatversion`, `core.filemode`,
   `core.bare`, `core.logallrefupdates`, `core.ignorecase`, `user.*`, `remote.*`, `branch.*`); selain itu, termasuk `filter.*`, `include.*`, `core.fsmonitor`,
   `diff.*` (driver), `core.hooksPath` dan `config.worktree`, ditolak dengan nama kuncinya. Alasan (terbukti): filter clean/smudge dan fsmonitor berjalan di `status`,
   `apply` dan `commit` walau hook dimatikan, dan filter tidak bisa dimatikan secara generik. Kedua repo latihan lolos.
4. **Repo:** path ada; bukan checkout Argus sendiri; working tree bersih (`git status --porcelain` kosong, termasuk tak terlacak, kecuali yang di-ignore);
   cabang bernama (bukan detached); cabang tidak dipinjam worktree lain; `HEAD` sama dengan `job.data["intake"]["commit"]` (selalu 40 heksa; `inputs.commit`
   adalah yang diketik pengguna dan bisa 12 karakter). **Kunci per repo** (`flock` di `jobs/.repo-<hash path repo>.lock`, tidak pernah di dalam repo target): dua job pada satu repo
   berlomba pada pemeriksaan bersih dan HEAD. `Job.lock` per job (`flock` tak-memblokir, `job.py:161`) dipegang di seluruh operasi.
5. **Patch di indeks sementara** (tidak menyentuh indeks repo): `GIT_INDEX_FILE` sementara, `read-tree HEAD`, `git apply --cached`, lalu
   `git diff-index --cached --raw -z --no-renames HEAD` untuk **jalur dan mode**. Ditolak: jalur yang salah satu komponennya, di kedalaman mana pun, tepat `.git`, `.gitattributes` atau `.gitmodules` (`sub/.gitattributes`; **bukan** `.gitignore` atau `.github/`, yang sah dan pernah diubah di kedua repo latihan), mode 120000 atau 160000 (symlink dan submodule, termasuk symlink yang ada lalu diubah), patch kosong, dan daftar jalur yang
   tidak sama dengan `provenance.json` `patch.files`. (`apply --numstat` hanya menampilkan tujuan pindah dan tanpa mode, `--summary` melewatkan symlink yang diubah, dan
   `--check` meloloskan submodule 160000 dan diff non-git, jadi tidak dipakai untuk keputusan.)
6. **Terapkan ke pohon kerja dan indeks:** `git apply --index` (tanpa `--3way` dan `--reject`). Lalu **sebelum commit**: patch-id dari `git diff --cached --binary --full-index --no-renames --no-textconv` lewat pembantu yang sama dengan PR 1 (`-c diff.noprefix=false -c diff.renames=false -c diff.context=3`, bukan `git diff` polos) sama dengan patch-id `changes.patch`; bila tidak, batalkan dan tolak.
7. **Commit:** identitas dibaca **sekali** dengan konfigurasi normal pengguna (`git config user.name` dan `user.email`, termasuk global; `argus-viewer` hanya punya
   identitas global) dan diteruskan lewat `-c user.name=... -c user.email=...`; tanpa identitas, ditolak, tidak ada karangan. Pesan: judul dari `PR.md`
   paket (bila tidak ada, `job <id>`), badan satu paragraf, trailer `Argus-Job: <id>` dan `Argus-Patch-Sha256: <sha>`.
8. **Pemulihan:** bila langkah 7 gagal sesudah langkah 6: `git apply -R --index` dari patch yang sama, dengan cadangan `git reset --hard HEAD` **hanya** karena pohon
   dipastikan bersih di langkah 4; hasilnya diperiksa dan dicetak (tree bersih lagi, atau pesan jelas bila tidak).
9. **Pencatatan:** `_record_applied` (PR 1) dengan `method="apply"` (bukan `via`, yang dicadangkan untuk `("ui",)`, `job.py:1365`), `head_before`, `branch`, `base`,
   `read_sha` dan `--note`; `as_is` harus `True` (patch-id commit sama). Bila tidak, commit dibiarkan, perintah gagal dengan pesan jelas, job tetap `REVIEW_READY`.
10. **Mati di tengah:** langkah 6 mencatat entri log `apply_started` (HEAD sebelum) sebelum mengubah apa pun. Masuk ulang pada job `REVIEW_READY` (diperiksa **sebelum** langkah 4, yang menolak HEAD yang bukan `intake.commit`): bila `HEAD`
    adalah anak dari `head_before`, trailer `Argus-Job` dan `Argus-Patch-Sha256` cocok, dan patch-id sama, perintah hanya mencatat (tanpa commit kedua). Mati di
    antara langkah 6 dan 7 meninggalkan perubahan di pohon: perintah berikutnya menolak dengan petunjuk `git apply -R --index`.
11. Mencetak commit, cabang, peringatan yang ada (hasil judge, repro, `leaks`: **saran**, dicetak, tidak menolak; jalur penasihat `AGENTS.md`) dan perintah berikutnya.
    **Tidak ada push, merge, deploy, staging, atau panggilan model**: uang tidak disentuh.

Teks `status` yang kini mencetak langkah manual ke cabang `argus/<job>` diperbarui ke perintah ini (K3).

## 5. Di luar spek ini

Push dan PR; `stage deploy` otomatis; mode "baca otomatis"; tombol di chat (kartu apply, prepare lalu confirm, sesudah CLI ini live dan teruji); antrean
berurutan (langkah berikutnya di urutan inti); `--onto-descendant` (K2); repo yang konfigurasi lokalnya di luar daftar putih.

## 6. Tes (ditulis dulu, merah di kode lama)

Repo git sementara dengan job `REVIEW_READY` buatan (paket dari pembuat paket asli). **Sukses:** satu commit, trailer, `as_is` True, status `APPLIED`, entri log
dengan `by`, `method` dan `head_before`; juga untuk patch biner, pindah berkas, mode berkas, hapus, dan patch tanpa newline akhir. **Ditolak, tidak ada perubahan:**
`--read-sha` salah, pendek atau hilang; patch diubah sesudah dibaca; `provenance.patch.sha256` tidak cocok; tree kotor (terlacak dan tak terlacak); detached HEAD;
HEAD bukan `intake.commit`; cabang dipinjam worktree lain; patch menyentuh `.git/`, `sub/.gitattributes`, `.gitmodules`, membuat atau mengubah symlink, submodule,
atau memuat `..`; patch kosong; daftar jalur beda dari `provenance`; `git apply` gagal; tanpa identitas; repo hilang; repo = checkout Argus; konfigurasi lokal
berisi `filter.*`, `core.fsmonitor`, `include.path`; job bukan `REVIEW_READY`; apply kedua. **Kode repo tidak berjalan:** hook `pre-commit` dan `commit-msg`, filter
clean/smudge, `core.fsmonitor`, `commit.gpgsign` dengan `gpg.program` tiruan: tidak ada yang menulis berkasnya. **Lingkungan:** `GIT_DIR`, `GIT_CONFIG_COUNT`,
`GIT_AUTHOR_NAME` di lingkungan pemanggil tidak berpengaruh. **Kunci dan crash:** dua job pada satu repo; dua `apply` bersamaan pada satu job; mati sesudah commit
sebelum pencatatan (masuk ulang hanya mencatat); mati antara langkah 6 dan 7; commit gagal (pohon dikembalikan). **`status`** mencetak perintah baru.
Mutan: tiap penjaga langkah 1 sampai 10 dibuang satu per satu; `-c core.fsmonitor=false`, `commit.gpgsign=false`, `--no-verify`, `hooksPath`, daftar putih
konfigurasi, pembuangan `GIT_*`, kunci per repo, pembandingan patch-id sebelum commit, pemulihan, dan pemeriksaan `as_is` dibuang.

## 7. Risiko yang diketahui

- Perintah ini mengubah repo target di host dengan isi yang ditulis agen. Pagarnya: patch sudah melewati gerbang dan paket review, `--read-sha` memaksa
  seseorang melihat sha-nya (bukan membuktikan membaca), langkah 5 menutup jalur ke metadata git dan mode berbahaya, langkah 2 dan 3 menutup kode repo yang berjalan
  saat git bekerja. Isi patch tetap kode agen yang baru berjalan saat ada yang menjalankan tes atau deploy, yang punya gerbangnya sendiri.
- Repo target dan `.git/`-nya dianggap tepercaya; biner `git` juga. Repo di luar daftar putih konfigurasi ditolak, bukan dibersihkan.
- Commit di cabang aktif berarti `main` langsung bertambah di repo latihan, seperti alur manual (K3).

## 8. Keputusan yang diminta dari Atha

| | Pertanyaan | Saran |
|---|---|---|
| K1 | `--read-sha` wajib | ya |
| K2 | `HEAD` harus sama dengan `intake.commit`; tanpa `--onto-descendant` di v0 | ya (berubah dari revisi 0 atas saran peninjau) |
| K3 | Commit di cabang aktif repo target; teks `status` diperbarui | ya untuk repo latihan |
| K4 | Tanpa push, merge, atau deploy | ya |
| K5 | Hook, filter, fsmonitor dan gpg tidak berjalan; konfigurasi lokal di luar daftar putih ditolak | ya |
| K6 | Kartu apply di chat menyusul sesudah CLI ini live | ya |
| K7 | Dua PR: PR 1 memperbaiki `applied()`, PR 2 `argus apply` | ya |
