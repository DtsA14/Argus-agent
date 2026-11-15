# SPEC `argus apply`: menerapkan paket review ke repo target dengan satu perintah

Status: **draf 2026-11-15, menunggu tinjauan dan persetujuan Atha** (jalur ketat: mengubah repo target di host dan mencatat keputusan
manusia di `job.json`). Langkah kedua urutan inti (Atha 2026-11-15) sesudah VF O1. Bahan: `pilots/prd_probe_v0/RESULT.md` dan
`GLUE_LOG.md` (tiga apply dengan tangan; semuanya mekanis), `router/job.py` (`applied`), `docs/reviews/SPEC_VF_O1_CANARY_NONCE.md`.

## 1. Masalah

Sesudah `REVIEW_READY`, "sampai staging" selalu butuh seseorang untuk: membaca patch, `git apply`, membuat commit di repo target, lalu
`argus applied <job> --commit <sha>`. Itu sambungan yang paling terasa dari probe PRD, dan satu-satunya langkah dari issue ke staging
yang harus dilakukan Claude dengan tangan tanpa keputusan apa pun di dalamnya. Yang **bukan** mekanis (membaca isi patch) harus tetap
ada: VF O1 hanya menaikkan biaya pemalsuan verdict, aturan "jangan apply job `DONE` tanpa dibaca" tetap berlaku.

## 2. Perintah

`argus apply <job> --read-sha <sha256 patch, minimal 12 karakter> [--onto-descendant] [--note TEKS]`

`--read-sha` sama bentuknya dengan `--sha` di `approve`: nilai yang `status` cetak untuk patch yang sedang menunggu. Isinya pernyataan
"patch dengan sha ini sudah dibaca", dan harus sama dengan sha256 `changes.patch` **sekarang di disk**. Patch yang berubah sejak dibaca
ditolak. Tanpa `--read-sha`, tidak ada apply.

## 3. Yang dilakukan, berurutan (berhenti dan tidak mengubah apa pun di langkah pertama yang meleset)

1. Job harus `REVIEW_READY` dengan paket yang valid (sama dengan `applied` sekarang). Selain itu `Refused`.
2. sha256 `changes.patch` sama dengan `--read-sha`.
3. Repo target (`inputs.repo`): working tree bersih (`git status --porcelain` kosong, termasuk berkas tak terlacak), berada di cabang
   bernama (bukan detached HEAD), dan `HEAD` sama dengan commit dasar job. `--onto-descendant` mengizinkan `HEAD` yang turunan dari commit
   dasar (alasan dan commit dasar dicatat); `git apply --check` tetap harus lulus. HEAD yang bukan turunan ditolak.
4. Patch ditolak bila menyentuh `.git/`, `.gitmodules` atau `.gitattributes`, membuat atau mengubah symlink (mode 120000) atau submodule
   (160000), atau memuat jalur absolut atau `..`. Daftar berkas yang diubah patch dicocokkan dengan daftar di paket review.
5. `git apply --index` (tanpa `--3way`, tanpa `--reject`): semua atau tidak sama sekali.
6. Commit memakai identitas git yang sudah dikonfigurasi di repo target (`user.name` dan `user.email`); tanpa identitas, ditolak,
   tidak ada identitas karangan. Pesan: judul dari `PR.md` paket (sudah dipotong di batas kata), badan satu paragraf, dan trailer
   `Argus-Job: <id job>` dan `Argus-Patch-Sha256: <sha>`. **Hook repo tidak dijalankan**: `git -c core.hooksPath=/dev/null commit
   --no-verify` (hook adalah kode repo target yang berjalan di host; patch tidak boleh menjadi jalan ke sana).
7. Bila langkah 6 gagal sesudah langkah 5, indeks dan tree dikembalikan (`git apply -R --index` dari patch yang sama) dan galatnya
   dicetak; tree harus bersih lagi (diperiksa dan dicatat).
8. `applied(job, commit=<commit baru>)` dipanggil dengan catatan `via=apply` dan `--note`; `as_is` harus `True` (patch-id commit sama
   dengan patch). Bila tidak, commit dibiarkan, perintah gagal dengan pesan jelas, dan job tetap `REVIEW_READY` (tidak dicatat).
9. Mencetak commit, cabang, dan perintah berikutnya (`stage deploy` bila ada rencana). **Tidak ada push, merge, deploy, atau staging**,
   dan tidak ada panggilan model: uang tidak disentuh.

## 4. Di luar spek ini

Push dan membuat PR; `stage deploy` otomatis; membaca patch atas nama manusia (tidak ada mode "baca otomatis"); tombol di chat (kartu
apply, prepare lalu confirm, sesudah CLI ini ada dan teruji); antrean berurutan (langkah berikutnya di urutan inti).

## 5. Tes (ditulis dulu, merah di kode lama)

Repo git sementara dengan job `REVIEW_READY` buatan: jalan sukses (satu commit, trailer, `as_is` True, status `APPLIED`, entri log dengan
`by` dan `via`); `--read-sha` salah, pendek, atau hilang; patch diubah sesudah dibaca; tree kotor (berkas terlacak dan tak terlacak);
detached HEAD; HEAD bukan commit dasar (tanpa dan dengan `--onto-descendant`; non-turunan); patch menyentuh `.git/` atau `.gitmodules`,
membuat symlink, memuat `..`; `git apply` gagal (tidak ada perubahan); tanpa identitas git; hook `pre-commit` dan `commit-msg` yang
menulis berkas **tidak** berjalan; commit gagal sesudah apply (tree dikembalikan); job bukan `REVIEW_READY`; apply kedua ditolak;
konkurensi (dua `apply` bersamaan: kunci job). Mutan: tiap penjaga di langkah 2 sampai 8 dibuang satu per satu; `--no-verify` dan
`hooksPath` dibuang; `as_is` tidak diperiksa; pemulihan di langkah 7 dibuang.

## 6. Risiko yang diketahui

- Perintah ini mengubah repo target di host dengan isi yang ditulis agen. Pagarnya: patch sudah melewati gerbang dan paket review,
  `--read-sha` memaksa seseorang melihatnya, dan langkah 4 menutup jalur yang menyentuh metadata git. Isi patch (kode) tetap kode agen:
  baru berjalan saat ada yang menjalankan tes atau deploy, yang punya gerbangnya sendiri.
- `--read-sha` tidak membuktikan patch dibaca; ia membuktikan seseorang menyalin sha yang `status` cetak. Itu sama dengan
  `approve --sha` hari ini. Jangan mengutipnya sebagai bukti pembacaan.
- Membuat commit di cabang yang sedang aktif (seperti alur manual) berarti `main` bisa langsung bertambah. Repo latihan dipakai begitu;
  untuk repo lain pakai cabang kerja sebelum menjalankan perintah (K3).

## 7. Keputusan yang diminta dari Atha

| | Pertanyaan | Saran |
|---|---|---|
| K1 | `--read-sha` wajib (bukan opsional) | ya |
| K2 | `HEAD` harus sama dengan commit dasar; turunan hanya dengan `--onto-descendant` | ya |
| K3 | Commit di cabang aktif repo target (bukan cabang baru per job) | ya untuk repo latihan; cabang baru per job diputuskan saat ada repo lain |
| K4 | Tanpa push, merge, atau deploy di v0 | ya |
| K5 | Hook repo target tidak dijalankan | ya |
| K6 | Kartu apply di chat menyusul sesudah CLI ini live, bukan di PR ini | ya |
