# Rencana MVP M6 (repo-to-PR): keputusan, scope, urutan, dan kriteria go/no-go

Status: **rencana untuk review; tanpa perubahan kode.** 2026-10-17, direvisi setelah review pertama PR #74
(dua P1: cap biaya dan cara membuat patch; dua P2: status hasil pilot dan baseline merah). Basis main `af32d70`. Dasar:
`docs/reviews/M6_GAP_ANALYSIS.md` (PR #73) dan keputusan review atas empat pertanyaannya.

**Tujuan MVP:** Argus menerima satu task nyata di satu repo, mengerjakannya, memvalidasinya di sandbox yang bisa
direproduksi, lalu menghasilkan paket review. Manusia membaca paket itu dan membuka PR. Ukurannya bukan jumlah ADR
yang selesai, tetapi:
- task selesai dengan benar;
- biayanya masuk akal;
- supervisi manusia sedikit.

## 1. Keputusan yang sudah diambil (review PR #73)

| # | Keputusan | Batasannya |
|---|---|---|
| 1 | Hambatan 1–4 menjadi scope MVP: sandbox per proyek, diff dan draf PR, provenance, profil budget | Profil 45k / 8.192 hanya untuk task berat, bukan default global. Sandbox dibuat secukupnya untuk repo pertama, bukan platform universal |
| 2 | Model membuat draf rencana bertipe dan kriteria acceptance; manusia menyetujui sebelum eksekusi | Kriteria harus bisa diuji secara deterministik. Kriteria yang belum bisa diverifikasi tidak boleh diam-diam dianggap terpenuhi. Belum ada planner penuh atau replanning dinamis |
| 3 | PR dibuka manusia | Argus menghasilkan diff, ringkasan, hasil tes, klaim yang didukung bukti, dan metadata commit. PR otomatis adalah tahap berikutnya |
| 4 | Repo pertama: Argus sendiri (bersyarat) | Satu task kecil, terisolasi, acceptance jelas, **tidak mengubah komponen keselamatan inti**. Jika dependensi atau validasinya tidak bisa direproduksi, jangan dipaksakan: Athena menjadi alternatif setelah kompatibilitasnya diverifikasi |

Di luar scope MVP: multi-agent (M4), registry penuh (ADR-001), memory layers (ADR-003), artifact store penuh (ADR-005),
idempotensi di sisi provider, pembukaan PR oleh harness.

## 2. Workstream

Setiap workstream adalah satu PR, kecuali disebutkan lain. Proses mengikuti jenjang risiko yang sudah disepakati: yang
menyentuh acceptance, sandbox, budget, atau crash-resume memakai desain singkat, tes, mutan untuk invariant kritis,
dan `verify.sh`.

### W0. Menutup gap bukti kecil (bisa paralel dengan W1)
- Tes deterministik di loop code task untuk:
  - tool call rusak (`invalid_tool_calls`): dijawab dan tidak dijalankan;
  - balasan terpotong (`is_truncated`): tool call-nya tidak dijalankan dan attempt berakhir `output_truncated`.
- **Timeout panggilan model di code task:** verifikasi perilakunya. Timeout tergolong *transient*
  (`harness/llm.py`), dicatat sebagai mungkin sudah diproses dan dihitung worst case. Lalu tulis tes deterministik
  bahwa run berakhir `BLOCKED provider_failed` setelah retry habis, tanpa salah hitung biaya.
- Perubahannya hanya tes, kecuali tes menemukan cacat.

### W1. Sandbox untuk satu repo: Argus (vertical slice)
- **Image proyek tanpa jaringan:**
  - dibangun dari venv VM yang sudah terverifikasi (`requirements.txt` dipatok), dengan cara yang sama seperti
    `scripts/build_local_sandbox_image.sh` (`docker import`, tanpa registry dan tanpa unduhan);
  - dipatok ke content id-nya;
  - flag isolasi tetap sama (`--network none`, read-only, non-root, tanpa capability, batas sumber daya).
- **Pemilihan image** lewat lingkungan bernama di config (misalnya `sandbox.environments.argus`) yang dirujuk kontrak.
  Nama yang tidak dikenal berarti BLOCKED (fail-closed). Kontrak yang ada sekarang tetap memakai image default.
- **Perintah pytest terstruktur:**
  - `python -m pytest` dengan allowlist opsi (path tes, `-k`, `-p no:cacheprovider`, `-q`), tanpa shell;
  - parser hasil per tes;
  - `must_pass` berbentuk node id pytest (`tests/test_x.py::test_y`).
  - Kontrak tetap divalidasi statis. Pelajaran pilot 3: jangan menolak hal yang hanya bisa diketahui saat run.
- **Batas yang diketahui:** sekitar 11 file tes Argus butuh Docker dan tidak bisa berjalan di dalam sandbox. Validasi
  task Argus memakai file tes yang tidak butuh Docker. Itu dicatat di kontrak, bukan disembunyikan.
- **Bukti reproduksi:** tes target dijalankan dua kali di sandbox dengan hasil sama, dan baseline merah/hijau
  ditunjukkan sebelum pilot.

### W2. Draf rencana dan kriteria, disetujui manusia
- Langkah terpisah sebelum eksekusi, misalnya `scripts/draft_task.py`, dengan masukan issue, repo, dan commit.
- Model (role `coder`, budget sendiri, tercatat di ledger) membaca repo dan mengusulkan:
  1. rencana bertipe: file yang akan disentuh, langkah, dan risiko;
  2. draf kontrak: scope, validasi, `must_pass`, profil budget;
  3. bila perlu, draf tes baru.
- **Pemeriksaan deterministik atas draf:**
  - kontrak lolos `validate`, dan file tes baru masuk scope `protected` (agen tidak bisa mengubahnya);
  - **baseline merah yang benar**, di sandbox pada commit dasar:
    - setiap tes baru **terkoleksi** (node id-nya ada di laporan pytest) dan berstatus **failed** karena assertion.
      Status *error* (import error, gagal koleksi, fixture atau setup rusak) dan *not collected* **tidak** dihitung
      sebagai baseline merah, dan draf ditolak;
    - tes regresi yang sudah ada di kontrak **lulus** di commit dasar pada sandbox yang sama. Ini bukti bahwa
      environment-nya sehat, sehingga kegagalan tes baru bukan karena environment;
    - pesan assertion setiap tes baru dicatat di laporan draf. Saat menyetujui, manusia memeriksa bahwa kegagalannya
      memang perilaku yang ingin diperbaiki. Bagian ini penilaian manusia, bukan cek otomatis, dan ditulis begitu;
  - **baseline hijau:** sebelum pilot, patch referensi (ditulis manusia, di luar workspace agen) membuat semua tes
    baru dan tes regresi lulus di sandbox. Ini bukti bahwa kriterianya bisa dipenuhi. Setelah run, acceptance tetap
    mewajibkan tes yang sama lulus (`must_pass`);
  - kriteria yang tidak bisa diuji ditandai eksplisit sebagai "tidak terverifikasi otomatis". Kriteria itu tidak
    boleh dihitung lulus.
- **Persetujuan manusia** berupa membekukan kontrak yang sudah disetujui. Hanya kontrak beku yang bisa dijalankan.
  Draf tidak pernah menjadi kontrak secara otomatis.

### W3. Paket review (tanpa LLM)
Setelah DONE, harness membuat `review/` di run dir secara deterministik:
- `changes.patch`: patch format Git (lihat "Cara membuat patch" di bawah);
- `tests.md`: validasi segar per kriteria, dari verdict;
- `claims.md`: klaim dan buktinya;
- `provenance.json`: repo, commit dasar, commit agen, sha kontrak, model, dan biaya dari ledger;
- `PR.md`: draf deskripsi PR dari ringkasan agen dan bukti.

**Cara membuat patch.** Snapshot hasil `git archive` tidak punya `.git`, jadi patch tidak diambil dari workspace
langsung:
1. Snapshot murni dari intake (W4, tidak pernah ditulisi agen) disalin ke direktori sementara, lalu dibuat repo Git
   baru di sana dengan satu commit.
2. Isi salinan itu **dicerminkan** (mirror) ke workspace akhir, bukan sekadar ditimpa: semua file yang dilacak di
   salinan dihapus dulu, lalu seluruh isi workspace akhir disalin masuk. Dengan begitu file baru, file yang berubah,
   dan **file yang dihapus agen** semuanya terwakili. Kemudian `git add -A` dan
   `git diff --cached --binary --full-index` menghasilkan `changes.patch`.
3. Git dijalankan tanpa konfigurasi pengguna atau sistem (`GIT_CONFIG_GLOBAL=/dev/null`, `GIT_CONFIG_NOSYSTEM=1`) dan
   tanpa hook. Git hanya membandingkan file; tidak ada kode repo yang dijalankan.

**Verifikasi deterministik patch** (bagian dari pembuatan paket; kalau gagal, paket ditandai tidak valid dan run tidak
dilaporkan siap PR):
- `git worktree add` pada commit dasar yang tercatat, dari repo asli, lalu `git apply --check` dan `git apply`;
- file yang berubah setelah apply sama persis dengan file berubah di verdict, dan semuanya di dalam scope `writable`
  kontrak. Tidak ada file `protected` atau path yang dikecualikan saat intake;
- **keadaan akhir identik secara menyeluruh:** daftar semua file (path, mode eksekusi, hash isi) di worktree yang sudah
  di-patch sama persis dengan workspace agen, di luar `.git` dan path yang dikecualikan saat intake. Ini mencakup file
  yang tidak berubah, jadi file yang seharusnya terhapus tetapi tertinggal, atau file yang hilang, ikut tertangkap;
- validasi kontrak dijalankan ulang di sandbox pada worktree yang sudah di-patch, dan hasilnya sama dengan verdict.

**Tes deterministik pembuatan dan verifikasi patch** (dengan repo Git sementara, tanpa model dan tanpa biaya). Setiap
kasus memeriksa bahwa patch diterapkan di worktree bersih menghasilkan keadaan yang identik:
- file baru, file berubah, dan **file yang dihapus**, termasuk direktori yang menjadi kosong;
- file binary: tool agen (`WriteFile`, `EditFile`) hanya menulis teks, jadi perubahan binary dari agen tidak mungkin.
  Tesnya membuktikan dua hal: binary yang tidak disentuh tetap identik byte demi byte, dan perubahan binary yang
  disuntikkan langsung ke workspace terbawa utuh oleh `--binary` (atau ditolak kalau di luar scope);
- perubahan di luar scope `writable`, di file `protected`, atau di path yang dikecualikan saat intake: patch ditolak
  dan paket ditandai tidak valid;
- mutan: mirror yang tidak menghapus file, dan perbandingan yang hanya mengecek file berubah. Keduanya harus
  menggagalkan tes.

Manusia memeriksa paket itu, menerapkan patch yang sama ke branch dari commit dasar, lalu membuka PR.

### W4. Intake dan provenance
- Snapshot yang bisa diulang dari repo dan commit tertentu ke `fixtures/repos/<nama>`. Ini mengikuti pola manual di
  pilot (`git archive`, dengan pengecualian yang dinyatakan, misalnya `verification/`). Snapshot dicatat dengan commit
  dasarnya. Intake memverifikasi bahwa snapshot identik dengan `git archive <commit dasar>` dikurangi pengecualian
  yang dinyatakan; tanpa itu, patch tidak bisa dijamin berlaku di commit dasar.
- `result.json` mencatat commit dasar repo target dan commit agen. Sekarang keduanya belum dicatat.
- Aturan `inputs.workspace` di bawah `fixtures/repos/` tetap berlaku. Intake yang mengisi folder itu.

### W5. Profil budget per task
- Profil di config, misalnya `default` (30.000 / 4.096) dan `large` (45.000 / 8.192), dipilih kontrak dengan field
  opsional yang divalidasi. Nama tidak dikenal berarti invalid.
- **Profil tidak pernah mengubah cap biaya.** Cap run tetap `min(budget.max_usd di config, limits.max_usd di
  kontrak)` (`codetask/run.py`). Default config tetap **$0.50**. Memilih profil `large` tidak menaikkan angka itu.
- **Akibatnya di $0.50.** Hitungannya dari `admission`, dengan reservasi per attempt = `attempt_tokens` × harga output
  Sonnet 5.5 ($10/M):
  - `large` = $0.45 per attempt. Attempt pertama masuk. Attempt kedua hanya masuk kalau attempt pertama menghabiskan
    ≤ $0.05, jadi praktis **satu attempt**;
  - `default` = $0.30 per attempt. Attempt kedua masuk kalau yang pertama ≤ $0.20.
- **Cap di atas $0.50 hanya untuk run yang disetujui di preflight.** Angka di config dan kontrak dinyatakan di
  preflight, berlaku untuk run itu saja, dan tidak diulang otomatis.
- **Usulan untuk pilot M6:** `large` dengan cap **$1.00**, karena itu kondisi eksperimen budget (45k: 9/9). Di $1.00,
  attempt kedua masuk kalau yang pertama ≤ $0.55, dan attempt ketiga kalau dua yang pertama ≤ $0.10 total. Kalau cap
  $1.00 tidak disetujui, pilot berjalan di $0.50 dengan praktis satu attempt, dan itu dicatat sebagai kondisinya.
- Kontrak yang cap-nya tidak memuat satu reservasi attempt profilnya ditolak saat validasi (fail-closed), bukan
  dijalankan lalu berhenti.
- **Tes:**
  - memilih profil tidak mengubah `max_usd` efektif;
  - angka attempt di atas dicek dengan `admission` asli, seperti `tests/test_budget_experiment.py`.
- Kontrak tanpa profil berjalan persis seperti sekarang.

**Urutan:** W0 dan W1 paralel. W4 dan W5 kecil dan bisa menyusul W1. W2 setelah W1, karena draf tes perlu sandbox untuk
membuktikan baseline merah. W3 setelah W4, karena provenance. Lalu pilot. Vertical slice boleh diuji lebih awal
(misalnya W1 + W3 + W4 dengan kontrak tulisan manusia) sebelum W2 selesai.

## 3. Pilot M6 pertama (setelah workstream yang diperlukan)

**Pemilihan task (diputuskan di preflight, bukan sekarang):**
- di repo Argus;
- kecil dan terisolasi;
- acceptance bisa diuji dengan tes yang tidak butuh Docker;
- **tidak menyentuh komponen keselamatan inti** (budget, acceptance, crash-resume, sandbox).

Contoh jenis yang cocok: perbaikan atau fitur kecil di skrip analisis, laporan, atau utilitas di luar jalur produksi.
Fix fail-closed `evals/runner.py` **tidak** cocok untuk pilot pertama, karena menyentuh kontrol biaya.

**Yang dicatat per pilot:**
- tingkat sukses, biaya per sukses, kegagalan jujur;
- waktu supervisi manusia (menit untuk menyetujui draf, meninjau paket, dan membuka PR);
- status hasil (agent-completed, human-assisted, atau failed) dan diff perubahan manual kalau ada.

## 4. Kriteria go/no-go

**Go ke pilot jika semua ini terpenuhi:**
1. W0 di-merge; tes output rusak, terpotong, dan timeout lulus.
2. Image Argus bisa dibangun ulang tanpa jaringan dari venv yang dipatok. Tes target task berjalan di sandbox dua kali
   dengan hasil identik. Baseline merah/hijau terbukti.
3. Draf kontrak dan tes untuk task pilot disetujui manusia:
   - kontraknya lolos `validate`;
   - tes barunya terkoleksi dan gagal karena assertion di commit dasar (bukan error);
   - tes regresi lulus di commit dasar, dan patch referensi membuat semuanya lulus;
   - tidak ada kriteria tak terverifikasi yang dihitung lulus.
4. Dry run dengan model palsu menghasilkan paket review lengkap (patch, tes, klaim, provenance, draf PR); patch-nya
   lolos verifikasi W3 di worktree bersih pada commit dasar; dan paket itu ditinjau.
5. `verify.sh` lulus di head yang akan dipakai. Cap biaya (termasuk apakah cap di atas $0.50 disetujui untuk run
   itu), profil budget, dan aturan henti dikunci di preflight.

**Hasil pilot dicatat dengan salah satu dari tiga status:**

| Status | Syarat |
|---|---|
| **agent-completed** | DONE dalam cap; patch lolos verifikasi W3 dan diterapkan **tanpa perubahan**; validasi independen dan `verify.sh` lulus di branch itu; paket review lengkap |
| **human-assisted** | Sama, tetapi manusia mengubah isi file di patch sebelum PR. Perubahan itu disimpan sebagai diff terpisah, dengan alasan dan menitnya. Ini keberhasilan dengan intervensi, **bukan** keberhasilan mandiri Argus |
| **failed** | Selain itu: tidak DONE, patch tidak lolos verifikasi, atau validasi gagal setelah patch diterapkan |

Mengedit teks deskripsi PR (`PR.md`) bukan perubahan kode. Itu dihitung sebagai waktu supervisi.

**MVP M6 dianggap tercapai jika** satu pilot di repo nyata dimulai dari draf yang disetujui dan berakhir
**agent-completed**. Hasil human-assisted dilaporkan sebagai data (apa yang harus diubah manusia, dan kenapa), tetapi
tidak memenuhi kriteria ini. Satu sukses adalah bukti kelayakan, bukan tingkat sukses umum.

**No-go atau berhenti:**
- sandbox tidak bisa direproduksi atau tesnya flaky;
- kriteria tidak bisa dibuat deterministik;
- ada anomali biaya atau klaim palsu;
- task pilot ternyata menyentuh komponen keselamatan inti.

Dalam kasus itu, kembali ke review, tanpa memaksakan run. Jika repo Argus tidak bisa divalidasi dengan andal, Athena
dievaluasi sebagai alternatif.

## 5. Risiko yang sudah terlihat

- **Self-hosting dengan kode harness:** agen mengubah salinan, bukan checkout yang menjalankan run. Pola ini sudah
  dipakai di pilot (snapshot terpisah, scope tulis sempit). Tetap dipertahankan.
- **Tes Argus yang butuh Docker** tidak bisa menjadi kriteria task. Pemilihan task harus memperhitungkannya.
- **VM 1 vCPU / 2 GB:** image proyek lebih besar dan pytest lebih lambat. Waktu `verify.sh` diukur sebelum dan
  sesudah W1.
- **Draf oleh model bisa mengarahkan kriteria ke yang mudah:** karena itu persetujuan manusia dan pemeriksaan
  baseline merah wajib, dan kriteria tak terverifikasi tidak pernah dihitung lulus.
