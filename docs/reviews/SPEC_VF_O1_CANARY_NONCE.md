# SPEC VF O1: catatan nonce dan kenari di validasi pytest

Status: **revisi 1, 2026-11-15, menunggu persetujuan Atha** (jalur ketat: grader). Lanjutan `SPEC_VF_CANARY.md` (probe A10, O2 sudah
ter-merge #477) dan sketsa Fable di `AUDIT2_2026-11-11.md` bagian 1. Urutan inti diterima Atha 2026-11-15: ini pekerjaan pertama.
Revisi 1 menerapkan tinjauan Opus (GO WITH CHANGES, 2026-11-15): klaim dipersempit, catatan berbentuk hash, tabel pemetaan, daftar
berkas, kasus tepi.

## 1. Masalah

Validasi pytest dinilai dari teks yang dicetak proses yang juga menjalankan kode agen (`acceptance/validation.py`: `argv`,
`parse_pytest`, `judge_result`). Kode itu bisa mencetak laporan yang konsisten lalu keluar dengan kode 0 sebelum tes mana pun
jalan; validasi menjawab `pass` (terbukti 2026-11-12, `fixtures/forgers/pytest_pipe_forger`, `tests/test_vf_forger.py` xfail
strict). O2 (#477) hanya menangkap forger yang polanya terlihat per baris, dan menangkapnya di gerbang deteksi, bukan di validasi.

## 2. Yang dijanjikan, dan yang tidak

**Dijanjikan.** Validasi pytest `pass` hanya bila (a) proses mencetak tepat satu catatan harness di belakang nonce yang dibuat
untuk run itu; (b) tiga tes kenari milik harness, dijalankan di proses yang sama sesudah tes kontrak, berakhir persis seperti
seharusnya (satu lulus, satu gagal karena `assert`, satu gagal karena `RuntimeError`); (c) hitungan dan hash di catatan sama dengan
yang `parse_pytest` baca dari teks, dan `rc` di catatan sama dengan kode keluar kontainer. Akibatnya dua kelas pemalsuan **yang tidak
bersyarat** menjadi `fail`:

| Kelas | Contoh | Tertangkap oleh |
|---|---|---|
| cetak laporan lalu keluar | `pytest_pipe_forger` (fixture yang ada) | (a): tidak ada catatan |
| lumpuhkan semua tes di proses, tanpa syarat | `Function.runtest = lambda self: None` (fixture baru `pytest_noop_forger`) | (b): kenari yang harus gagal ikut lulus |

**Tidak dijanjikan** (terbukti oleh peninjau pada pytest 9.1.1; fixture xfail-strict, lihat bagian 5):

- **F1, pemalsu berdasarkan jalur:** `Function.runtest` dilumpuhkan hanya untuk berkas di bawah akar repositori; kenari ada di `/tmp`
  dan berjalan jujur. Hasil: teks "1 passed", kode keluar 0, catatan benar, kenari benar, **`pass`**.
- **F2, pemalsu berdasarkan sesi:** semua tes dilumpuhkan, lalu dipulihkan di `pytest_sessionfinish` supaya sesi kenari jujur.
  **`pass`**.
- Kode di proses yang sama bisa membaca `sys.argv`, `__main__` dan berkas kenari, lalu meniru catatan lengkap dengan nonce.
- Hook `conftest.py` workspace tidak menyentuh kenari (pytest membatasi hook conftest menurut letak): pemalsuan lewat conftest tidak
  tertangkap di sini; pagarnya berkas terlindungi dan gerbang deteksi.

Jadi O1 menutup pemalsuan yang tidak sadar akan kenari; pemalsu yang membedakan kenari dari tes kontrak (F1, F2 dan yang sejenis)
tetap lolos. Aturan **"jangan apply job `DONE` tanpa dibaca" tidak dicabut oleh PR ini**; O1 menaikkan biaya pemalsuan, bukan
membuktikan ketiadaannya. Pencabutan aturan itu keputusan Atha tersendiri, sesudah ada data.

## 3. Rancangan

Probe 2026-11-15 (`pilots/vf_o1_probe/`, pytest 9.1.1, di luar sandbox, kode sendiri dan kode peninjau, tanpa model): forger pipa
menghasilkan teks "1 passed", kode keluar 0 dan **tanpa catatan**; forger no-op menghasilkan catatan dengan kenari `passed`. Keduanya
menjadi `fail` menurut aturan di bawah. Peninjau menjalankan tujuh skenario dua-sesi pada proyek jujur (`filterwarnings=error`,
conftest yang memasang `simplefilter("error")`, `pytest.exit`, `KeyboardInterrupt`, `sys.stdout` yang diganti, thread daemon,
xdist): satu catatan dan kenari benar di semuanya, tanpa false positive. **Belum dijalankan** di sandbox, pada pytest 8.4.2
(`sympy_py39`), atau dengan `-I` memakai `-c` di Python 3.9; itu bagian tes PR ini.

1. **Perintah.** Validasi pytest tidak lagi `python3 -I -B -m pytest ...`, melainkan `python3 -I -B -c GREEN <nonce> <target...>`,
   skrip milik harness seperti `RED_CHECK` (tidak pernah dari kontrak atau workspace). Nonce: `ARGUS-GREEN-<32 hex>:`, baru untuk
   setiap run. Karena `-c` mengubah `sys.argv`, skrip memasang `sys.argv` ke bentuk `["pytest", *opsi, *target]` sebelum sesi 1
   (kode jujur yang memeriksa `sys.argv[0]` berperilaku seperti sebelumnya) dan membaca nonce dari argumennya sendiri sebelum itu.
   Bukti (`evidence.argv`) menampilkan skrip dengan nama dan sha, seperti perekam vitest.
2. **Sesi 1, tes kontrak.** `pytest.main([*PYTEST_FIXED, *target], plugins=[Rekam()])`: opsi dan teks keluaran **sama dengan hari
   ini**, sehingga `parse_pytest`, `output_tail`, `failed_nodes`, `skip_violations` dan apa yang dibaca agen tidak berubah. `Rekam`
   mencatat hasil per node dari `pytest_runtest_logreport` dan memetakannya ke kata `parse_pytest` (butir 5).
3. **Sesi 2, kenari.** Sesudah sesi 1, di proses yang sama: skrip menulis `test_argus_canary_<16 hex>.py` ke direktori baru di
   `/tmp` (tmpfs; workspace tetap read-only; `with open`), menjalankannya dengan `pytest.main` kedua dengan keluaran dibuang. Nama acak
   dibuat di dalam kontainer, bukan di argv. Bila menulis gagal (`OSError`, tmpfs penuh), catatan membawa `canary_error` dan
   alasannya `harness canary: could not write`, bukan "no harness record".
4. **Catatan, berbentuk ringkas.** Satu baris `<nonce>{"rc": ..., "counts": {...}, "sha": ..., "canary": {...}, "canary_rc": ...}`
   di akhir stdout, lalu `sys.exit(rc)` dengan kode keluar sesi 1. `counts`: jumlah node per status. `sha`: sha256 dari daftar
   `(node, status)` terurut. Catatan **tidak** memuat node satu per satu: batas keluaran per aliran 65.536 byte
   (`tools/sandbox.py:50`) sudah hampir terpakai oleh baris `-v` pada sekitar 400 tes, dan catatan per node akan menggandakannya
   (perkiraan peninjau; ukur di PR). Ukuran catatan tetap, beberapa ratus byte.
5. **Penilaian** (`judge_result`, cabang pytest). Semua aturan lama tetap. `judge_result` menghitung `counts` dan `sha` dari
   `parse_pytest(teks)` dan membandingkannya dengan catatan. Pemetaan dari `Rekam` ke kata `parse_pytest` (diperoleh dari
   peninjau, pytest 9.1.1): `call` lulus → `ok`; `call` gagal → `FAIL`; kegagalan di `setup` atau `teardown` → `ERROR` (status
   terburuk per node, urutan `ERROR` > `FAIL` > lain, seperti `parse_pytest`); `skipped` tanpa `wasxfail` → `skipped`; `skipped`
   dengan `wasxfail` → `expected failure`; `passed` dengan `wasxfail` → `unexpected success`. Node tak terpilih (`-k`) tidak ada di
   kedua sisi. Alasan `fail` yang baru:
   - tidak ada baris catatan di belakang nonce run ini, lebih dari satu, atau bentuknya salah: `no harness record`;
   - kenari tidak persis `{pass: passed, fail: failed, error: failed}` atau `canary_rc != 1`: `harness canary: ...`;
   - `rc` di catatan berbeda dari kode keluar kontainer;
   - `counts` atau `sha` berbeda dari yang dibaca dari teks: `harness record disagrees with the report`.
   Baris catatan dibuang dari teks **sebelum** `parse_pytest` dan sebelum teks sampai ke pembaca mana pun (butir 7). Bukti
   mendapat `record: true|false` dan `canary: "ok"` atau isinya.
6. **Gagal tertutup.** Keluaran terpotong, batas waktu (sesi 2 ikut batas `timeout_s` kontrak), proses mati sebelum catatan:
   `fail` seperti hari ini, alasan lama lebih dulu. Tidak ada jalur yang menerima validasi pytest tanpa catatan. Galat kolektif
   (tidak ada `logreport`) sudah `fail` lewat aturan konsistensi lama.
7. **Pembaca teks pytest yang ikut berubah** (peninjau; semuanya aman hanya bila catatan dibuang lebih dulu, atau diganti ke
   `argv` baru): `acceptance/validation.py` (`judge_result`, `argv`), `scripts/check_env_image.py:85` dan
   `tests/test_pytest_sandbox.py:61` (memanggil `va.argv(s)` lalu `parse_pytest` pada teks mentah: keduanya harus memakai satu
   fungsi harness yang menjalankan dan membuang catatan), `tests/test_pytest_validation.py` (argv dan keluaran yang direkam),
   `codetask/agent.py` (kutipan `--tb=short`), `codetask/tools.py:481`, `acceptance/draft.py:414`, `codetask/drafter.py`.
   **`router/stage.py:59` (`CHECK_ARGV`, `stage check`) tidak diubah**: ia punya argv sendiri dan batas yang sudah tertulis
   (`stage check` bisa dipalsukan oleh conftest di commit).

## 4. Di luar PR ini

- **unittest dan vitest.** Vitest sudah dinilai dari catatan di belakang nonce tetapi tanpa kenari; unittest dari teks. Tidak
  disentuh (K1).
- **Himpunan node dibekukan saat approve** (butir ketiga sketsa Fable): menyentuh kontrak dan approve; `must_pass`, `min_tests`
  dan cek konsistensi tetap menjadi pagar untuk node yang dibuang (K3).
- **Kenari meleset menjadi terminal** (tanpa retry, seperti GATE): menyentuh mesin keadaan run; di PR ini `fail` biasa (K4).
- **Versi tool `RunValidation` (kunci memo) tidak dinaikkan**, seperti FIX-A: versi baru membeli ulang balasan model; hasil yang
  diputar ulang hanya umpan balik ke agen, vonisnya dari node acceptance yang menjalankan `judge_result` lagi (peninjau).
- `red_check`, `collect_nodes` dan `stage check`: dibaca dari proses yang sama, batasnya sudah tertulis; tidak diubah.

## 5. Tes (ditulis dulu, merah di kode lama)

Tanpa sandbox, pada keluaran yang direkam: catatan hilang; dua catatan; nonce salah; kenari `fail` tercatat `passed`; kenari
hilang; `canary_rc` 0; `rc` berbeda dari kode keluar; `counts` atau `sha` berbeda dari teks (satu node `passed` di catatan,
`FAILED` di teks, dan sebaliknya); `canary_error` (tmpfs penuh); baris catatan tidak bocor ke `output_tail` dan tidak dibaca
`parse_pytest`; ukuran catatan tetap untuk 1 dan 5.000 node; proyek hijau dan merah yang jujur memberi vonis, alasan dan bukti lama
yang sama (selain kunci baru). **Tabel pemetaan**: satu tes per baris, termasuk setup error, teardown error sesudah `call` lulus
dan gagal, xfail, xpass (strict dan bukan), skip (penanda dan di dalam `call`), id parametrize dengan spasi, subtest, `-k`.
Dengan sandbox (modul memuat `SANDBOX NOT AVAILABLE`): `tests/test_vf_forger.py` tanpa xfail, forger pipa `fail`; fixture baru
`pytest_noop_forger` `fail` dengan alasan kenari; proyek jujur `pass`; berjalan di `argus`, `ledger_py312_up2` dan `sympy_py39`
(pytest 8.4.2, dan `-I` dengan `-c` di Python 3.9); `scripts/check_env_image.py` lolos, ditambah satu cek di dalamnya bahwa
kenari lulus validasi pada tiap environment (menutup celah yang peninjau temukan di klaim lama). **Fixture xfail-strict F1 dan F2**
(`pilots/vf_o1_probe/path_forger_f1`, `session_forger_f2`): menyatakan jaminan yang **tidak** dipenuhi; XPASS strict memaksa spek
ini diperbarui bila suatu hari tertutup. Mutan: tiap alasan di butir 5 dibuang satu per satu, nonce dibuat tetap, kenari dijalankan
sebelum sesi 1 di proses lain, catatan diterima walau ganda, hash tidak dibandingkan, catatan tidak dibuang dari teks.
Sebelum `verify_at`: `bash scripts/precheck.sh`, lalu `tests/test_pytest_validation.py`, `test_pytest_sandbox.py`,
`test_acceptance_sandbox.py`, `test_swe_pilot.py` dan berkas yang mengunci `argv` pytest.

## 6. Risiko yang diketahui

- Dua `pytest.main` dalam satu proses tidak dianjurkan pytest untuk modul yang sama; di sini sesi kedua hanya memuat berkas
  kenari baru. Tujuh skenario peninjau tidak menemukan false positive di 9.1.1; 8.4.2 belum dicoba. Bila rapuh: mundur ke satu
  sesi dengan kenari sebagai target terakhir (teks berubah; lebih banyak yang tersentuh).
- Thread yang menulis di tengah baris catatan membuat run `fail` (gagal tertutup), bukan pass.
- Plugin pytest di image yang mengubah hasil secara global (misalnya rerun) bisa membuat kenari meleset pada proyek jujur;
  image hari ini tidak memasang plugin pytest. Cek kenari di `check_env_image.py` (butir 5 bagian 5) menangkapnya saat image
  didaftarkan, bukan di job.
- Waktu: satu sesi pytest kecil tambahan per validasi; diukur dan ditulis di PR.
- **Nilai terbatas, dinyatakan terus terang:** karena F1 dan F2, O1 hanya menangkap pemalsuan yang tidak sadar akan kenari.
  Nilainya: pemalsuan cetak-lalu-keluar dan pelumpuhan tanpa syarat berhenti jadi pass; pemalsu yang harus membedakan kenari dari
  tes kontrak meninggalkan kode yang lebih terlihat bagi pembaca patch.

## 7. Keputusan yang diminta dari Atha

| | Pertanyaan | Saran |
|---|---|---|
| K1 | Hanya pytest di PR ini; vitest dan unittest menyusul | ya |
| K2 | Dua sesi dalam satu proses (teks tes kontrak tidak berubah), bukan kenari di dalam sesi yang sama | ya, dengan klaim bagian 2 yang sempit |
| K3 | Himpunan node dibekukan saat approve: PR tersendiri sesudah ini | ya, tunda |
| K4 | Kenari meleset = `fail` biasa dulu, belum terminal | ya |
| K5 | Aturan "jangan apply `DONE` tanpa dibaca" tetap berlaku sesudah PR ini | ya |
