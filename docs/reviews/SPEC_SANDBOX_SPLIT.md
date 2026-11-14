# Spec SANDBOX-SPLIT: grup sandbox serial dipecah jadi dua grup serial

Status: **draf spec untuk dibaca Atha; belum ada kode.** Strict lane. Ditulis Claude, 2026-11-14.
Dasar: laporan Fable (item 5), review desain Opus (2026-11-13), dan pengukuran dasar `verification/verify-20261113T201900Z-aarch64.log` (commit 7175b91) dengan pencatat `docker events` dan tekanan CPU/memori.

## 0. Masalah (terukur)

Waktu dinding satu `verify_at` (sekitar 19 menit pytest) sama dengan waktu grup sandbox serial: **1.146,8 detik (744 tes)** lawan non-sandbox **1.045,2 detik (3.396 tes)** yang jalan paralel di tiga worker lain. Menambah worker tidak menolong selama grup itu serial.
Per modul (log #508, tes >= 1 detik): `test_draft` 538 detik, `test_eval_sandbox` 131, `test_codetask_crash` 76, `test_stage` 55, `test_env_node` 44, sisanya masing-masing < 33.

## 1. Usulan

Dua grup serial: **`sandbox_a` hanya berisi tes yang didefinisikan di `tests/test_draft.py`** (sekitar 545 detik); **semua tes sandbox lain masuk `sandbox_b`** (sekitar 580 detik). Perkiraan waktu dinding 10 sampai 11 menit, sebelum biaya rebutan sumber daya. Pembagian "draft + eval lawan sisanya" (670 lawan 450 detik) tidak dipakai.

Karena hanya `test_draft.py` yang dipisah, semua modul yang berbagi keadaan global ada di grup yang sama secara otomatis (review Opus 2026-11-14): `remove_labeled` pada run id `rc` (`codetask/run.py:485`, `test_codetask_crash.py`, `test_auto_validation.py`), `docker rmi` di `test_env_node.py:226`, label staging (`router/stage.py:396`). `test_draft.py` sendiri tidak menyentuh apa pun di seluruh mesin (tidak ada `remove_labeled`, `docker ps/rm/rmi`, nama tetap, atau resume; `dr.check` tidak menambah label `argus.run`). Aturan pasangan modul dari draf pertama dibuang: tidak diperlukan.

Aturan (dikunci tes di `tests/test_xdist_groups.py`):
1. **Grup ditentukan per tes (node), bukan per modul**, dengan urutan: tes yang didefinisikan di `test_draft.py` masuk `sandbox_a`; tes sandbox lain (teksnya sendiri, atau fixture dari berkas yang memuat teks itu) masuk `sandbox_b`. Jadi `test_red_caught.py` (mengimpor `scfg` dari `test_draft`) dan `test_append_tests_sandbox.py` (memakai `root` dan `tdr` dari `test_draft`) masuk `sandbox_b`. Daftar `{node: grup}` dihitung dari koleksi sungguhan dan dipin.
2. **Ketergantungan pada xdist dicatat dan dipin**: dua grup mulai bersamaan di dua worker hanya karena `--loadscope-reorder` aktif (bawaan xdist 3.8, `loadscope.py:375-398`: unit terbesar lebih dulu, satu per worker). Satu tes memastikan opsi `--no-loadscope-reorder` tidak ada di `verify.sh`, dan `verify.sh` mencetak versi xdist.
3. **`VERIFY_SANDBOX_GROUPS`** (bawaan 2 setelah spec ini lolos; `1` mengembalikan satu grup `sandbox`): dibaca di `conftest.py`, hanya `1` atau `2` diterima (selain itu gagal keras), dicetak di header `verify.sh` dan di ringkasan akhir; `precheck.sh` mewarisi nilai yang sama. Aturan rollback: setelah merge, satu kegagalan `verify_at` karena batas waktu atau exit 137 yang tidak masuk daftar-izin (butir 3 di bagian 3) berarti kembali ke `1`.
4. **Ringkasan per grup** (`group_totals`) membedakan grup lewat akhiran node id (`@sandbox_a`, `@sandbox_b`, dicocokkan dengan `endswith` pada nama grup yang dikenal, karena ada parameter id yang memuat `@`), dan mencetak **waktu dinding per grup** (paling awal `start` sampai paling akhir `stop` dari laporan tes).
5. Tempat yang mengasumsikan satu grup diperbarui: `tests/grouplist_plugin.py:9`, `tests/test_xdist_groups.py:130`, `tests/test_verify_hardening.py:155-171`, komentar `conftest.py`, `docs/Reconciliation.md` (aturan "tes sandbox tidak jalan bersamaan" menjadi "dalam satu grup"; baris 280 sampai 281 yang menyebut `test_acceptance_sandbox` meminta tanpa kontainer di seluruh mesin sudah usang sejak `sandbox_scope` dan ikut dikoreksi), `PENDING.md`.
6. Batas kontainer tidak diubah (1 CPU, 512 MB, `XDIST_WORKERS=4`), tidak ada plugin rerun. Aturan lama "tes dengan batas waktu ketat tinggal di grup ringan" **dibuang**: semuanya jatuh di `sandbox_b` yang justru lebih berat, jadi aturan itu bertentangan dengan pembagian. Gantinya: margin terukur (bagian 3, butir 5).

## 2. Apa yang dikoreksi dari catatan lama

`docs/Reconciliation.md` menulis "CPU berebut membuat exit 137". Penyebab itu **tidak pernah dibuktikan**. Dasar `verification/verify-20261113T201900Z-aarch64.log` (commit 7175b91, PASS, 18 modul sandbox termasuk `test_append_tests_sandbox.py`) sudah punya 28 kematian 137 dan satu event `oom` (20:36:20 UTC), sebagian disengaja: dari image, 20 ada di tiga pin staging (`test_stage` menghentikan rilis), 8 di image python bawaan (`test_sandbox.py:146` batas memori, dan pembunuhan di `:168,196,272,281`); dua yang lain (20:20:32 dan 20:22:18) kemungkinan dari `test_acceptance_sandbox.py:124` dan `test_codetask_crash.py:181`, itu inferensi. Kriteria "nol 137" tidak dipakai.

## 3. Bukti yang diminta sebelum merge

1. **Audit statis** (membaca) sudah dikerjakan Opus untuk modul-modul sandbox (lihat 3.1); hasilnya dicatat di sini, dan setiap temuan baru menghentikan pekerjaan.
2. **Pengamat yang lebih baik** (skrip di luar repositori, atau `scripts/` bila dipakai berulang): `docker events` dengan nama kontainer, label, event `start`, `die` (exitCode) dan `oom`; tekanan CPU/memori tiap 5 detik; **cap waktu per tes** dari hook `conftest.py` (`start`/`stop` tiap tes ke berkas di luar repositori) agar tiap event dapat dikaitkan ke tes. Kondisi awal dicatat (satu kontainer layanan staging hidup sebelum run mulai).
3. **Daftar-izin**: setiap kematian 137 harus jatuh di dalam jendela waktu sebuah tes yang membunuh kontainer dengan sengaja (daftar eksplisit di spec ini, diisi dari pemetaan run dasar yang diulang dengan pengamat baru), dan setiap `oom` di dalam `test_memory_limit_kills_the_code` saja. Kematian 137 di luar daftar-izin menghentikan pekerjaan. Hitungan per image **tidak** dipakai (id image berubah tiap run).
4. **Tiga `verify_at` penuh berturut-turut, semuanya bersih**, tanpa job live dan tanpa `verify_at` kedua: semuanya `RESULT: PASS` dengan 0 tes sandbox dilewati; butir 3 terpenuhi; waktu dinding per grup tercatat. Satu kegagalan menghentikan, bukan diulang sampai hijau.
5. **Margin waktu**: tes berbatas waktu ketat tidak boleh lebih buruk dari dasar sebesar X (dasar: `test_cleanup_is_bounded…` 5,23 detik terhadap `< 9`; sekitar 5 detik bawaan: timeout 2 + cleanup 3). X ditetapkan dari tiga run (selisih terbesar antar run dasar) sebelum angkanya dipakai; sebelum itu hanya dicatat.
6. **Mutan**: grup `test_draft` bocor ke `sandbox_b` atau sebaliknya harus membuat tes pin gagal; `test_red_caught` dan `test_append_tests_sandbox` di grup salah harus gagal; modul tak dikenal gagal; nilai `VERIFY_SANDBOX_GROUPS` tak sah gagal keras; `1` mengembalikan satu grup; `--no-loadscope-reorder` ditolak.

### 3.1 Hasil audit statis (Opus, 2026-11-14, membaca kode)

- `test_stage_viewer.py`: docker sungguhan hanya lewat `vite_build` (`router/stage_viewer.py:202`, nama acak); `Staging` hanya dengan `run` palsu (`:267`); proxy memakai `port=0` (`:297`). Tidak memakai `TEST_PREFIX`/`TEST_LABEL` dengan docker sungguhan.
- `test_env_from_base.py:192` memang membangun image (dua `docker import`, cache `~/.cache/argus-pip`, `build_env_from_base.sh:14`); `test_env_node` memakai `argus-npm`: keduanya **tidak berbagi cache** (alasan di draf pertama salah). Keduanya melabeli ulang `argus-sandbox-<env>:...`, aman karena pemakai memakai id yang dipin. Karena keduanya sama-sama di `sandbox_b`, tidak perlu aturan khusus.
- `test_review`, `test_swe_pilot`, `test_eval_sandbox`, `test_pytest_sandbox`: tidak ada nama tetap atau perintah docker global. `sandbox_scope.py` dan `test_sandbox.py:171,317` dibatasi lewat token atau nama uuid.
- Nama kontainer berisi uuid (`tools/sandbox.py:292`), tidak ada port tetap. Variabel Python global tidak bocor antar grup (tiap worker xdist adalah proses sendiri).
- Di luar lingkup tetapi dicatat: `remove_labeled` dengan label kosong akan menghapus semua kontainer sandbox di mesin (`tools/sandbox.py:235-241`), perlu penjaga di PR terpisah.

## 4. Sengaja tidak dikerjakan

- Memecah satu modul lintas grup, lebih dari dua grup, menambah worker, melonggarkan batas atau timeout.
- #7 (mengurangi run kontainer di `test_draft.py`): hematnya kecil (sekitar 1 menit CPU) dan menyentuh tes jaminan. Dikerjakan hanya kalau setelah ini `test_draft` ternyata grup terpanjang, dengan mutan per jaminan, dalam PR terpisah.
- Menjadikan `precheck.sh` bukti. Catatan: pra-cek yang memilih `test_draft.py` memakan 8 menit 51 detik, bukan 40 detik.

## 5. Batas yang diketahui

Penyebab exit 137 lama belum diketahui. Perilaku dua grup di bawah beban tidak diketahui sebelum langkah 4. Waktu dinding sebenarnya bisa kurang dari 10 menit bila sumber daya berebut.
