# SPEC VF O1: kenari dan nonce di validasi pytest

Status: **draf 2026-11-15, menunggu persetujuan Atha** (jalur ketat: grader). Lanjutan `SPEC_VF_CANARY.md` (probe A10, O2 sudah
ter-merge #477) dan sketsa Fable di `AUDIT2_2026-11-11.md` bagian 1. Urutan inti diterima Atha 2026-11-15: ini pekerjaan pertama.

## 1. Masalah

Validasi pytest dinilai dari teks yang dicetak proses yang juga menjalankan kode agen (`acceptance/validation.py`: `argv`,
`parse_pytest`, `judge_result`). Kode itu bisa mencetak laporan yang konsisten lalu keluar dengan kode 0 sebelum tes mana pun
jalan; validasi menjawab `pass` (terbukti 2026-11-12, `fixtures/forgers/pytest_pipe_forger`, `tests/test_vf_forger.py` xfail
strict). O2 (#477) hanya menangkap forger yang polanya terlihat per baris, dan menangkapnya di gerbang deteksi, bukan di validasi.

## 2. Yang dijanjikan, dan yang tidak

**Dijanjikan:** validasi pytest `pass` hanya bila (a) proses mencetak catatan harness di belakang nonce yang dibuat untuk run itu,
tepat satu kali; (b) tiga tes kenari milik harness, dijalankan di proses yang sama sesudah tes kontrak, berakhir persis seperti
seharusnya (satu lulus, satu gagal karena `assert`, satu gagal karena `RuntimeError`); (c) catatan itu sepakat dengan teks pytest
untuk setiap node dan untuk kode keluar. Dengan itu dua kelas forger menjadi `fail`:

| Kelas | Contoh | Tertangkap oleh |
|---|---|---|
| cetak laporan lalu keluar | `pytest_pipe_forger` (fixture yang ada) | (a): tidak ada catatan |
| lumpuhkan semua tes di proses | `Function.runtest = lambda self: None` (fixture baru `pytest_noop_forger`) | (b): kenari yang harus gagal ikut lulus |

**Tidak dijanjikan (ditulis di docstring dan di sini):** kode di proses yang sama bisa membaca `sys.argv`, modul `__main__` dan
berkas kenari, lalu meniru catatan lengkap dengan nonce. Forger yang menarget kenari tetap lolos. Hook di `conftest.py` workspace
yang hanya berlaku untuk tes di bawah direktorinya (pytest membatasi hook conftest menurut letak) tidak menyentuh kenari, jadi
pemalsuan lewat conftest tidak tertangkap di sini; pagarnya tetap berkas terlindungi dan gerbang deteksi. Aturan **"jangan apply
job `DONE` tanpa dibaca" tidak dicabut oleh PR ini**; O1 menaikkan biaya pemalsuan, bukan membuktikan ketiadaannya. Pencabutan
aturan itu keputusan Atha tersendiri, sesudah ada data.

## 3. Rancangan

Probe 2026-11-15 (`pilots/vf_o1_probe/green.py`, pytest 9.1.1, di luar sandbox, kode sendiri): forger pipa menghasilkan teks
"1 passed", kode keluar 0 dan **tanpa catatan**; forger no-op menghasilkan catatan dengan ketiga kenari `passed`. Keduanya menjadi
`fail` menurut aturan di bawah. Belum dijalankan di sandbox dan belum pada pytest 8.4.2 (`sympy_py39`); itu bagian tes PR ini.

1. **Perintah.** Validasi pytest tidak lagi `python3 -I -B -m pytest ...`, melainkan `python3 -I -B -c GREEN <nonce> <target...>`,
   skrip milik harness seperti `RED_CHECK` (tidak pernah dari kontrak, tidak dari workspace). Nonce: `ARGUS-GREEN-<32 hex>:`,
   baru untuk setiap run. Bukti (`evidence.argv`) menampilkan skrip dengan nama dan sha, seperti perekam vitest.
2. **Sesi 1, tes kontrak.** `pytest.main([*PYTEST_FIXED, *target], plugins=[Rekam()])`: opsi dan teks keluaran **sama persis
   dengan hari ini**, sehingga `parse_pytest`, `output_tail`, `failed_nodes`, `skip_violations` dan apa yang dibaca agen tidak
   berubah. `Rekam` mencatat hasil per node dari `pytest_runtest_logreport`.
3. **Sesi 2, kenari.** Sesudah sesi 1, di proses yang sama: skrip menulis `test_argus_canary_<16 hex>.py` ke direktori baru di
   `/tmp` (tmpfs; workspace tetap read-only), menjalankannya dengan `pytest.main` kedua, keluarannya dibuang, hasilnya direkam.
   Nama acak dibuat di dalam kontainer, bukan di argv.
4. **Catatan.** Satu baris `<nonce>{"rc": ..., "outcomes": {...}, "canary": {...}, "canary_rc": ...}` di akhir stdout, lalu
   `sys.exit(rc)` dengan kode keluar sesi 1 (kode keluar validasi tetap berarti sama seperti hari ini).
5. **Penilaian** (`judge_result`, cabang pytest). Semua aturan lama tetap. Ditambah, masing-masing menjadi alasan `fail`:
   - tidak ada baris catatan di belakang nonce run ini, atau lebih dari satu, atau bentuknya salah: `no harness record`;
   - kenari tidak persis `{pass: passed, fail: failed, error: failed}` atau `canary_rc != 1`: `harness canary: ...`;
   - `rc` di catatan berbeda dari kode keluar kontainer;
   - himpunan node atau hasil per node di catatan berbeda dari yang dibaca `parse_pytest` dari teks.
   Baris catatan dibuang dari teks sebelum `parse_pytest` dan dari `output_tail`. Bukti mendapat `record: true|false` dan
   `canary: "ok"` atau isinya.
6. **Gagal tertutup.** Keluaran terpotong, batas waktu, proses mati sebelum catatan: `fail` seperti hari ini (alasan lama tetap
   muncul lebih dulu). Tidak ada jalur yang menerima validasi pytest tanpa catatan.

## 4. Di luar PR ini

- **unittest dan vitest.** Vitest sudah dinilai dari catatan di belakang nonce tetapi tanpa kenari; unittest masih dari teks.
  Keduanya tidak disentuh (K1).
- **Himpunan node dibekukan saat approve** (butir ketiga sketsa Fable): menyentuh kontrak dan approve; `must_pass`, `min_tests`
  dan cek konsistensi tetap menjadi pagar untuk node yang dibuang (K3).
- **Kenari gagal menjadi terminal** (tanpa retry, seperti GATE): menyentuh mesin keadaan run; di PR ini `fail` biasa, agen boleh
  mencoba lagi (K4).
- `red_check`, `collect_nodes` dan `stage check`: dibaca dari proses yang sama, batasnya sudah tertulis; tidak diubah.

## 5. Tes (ditulis dulu, merah di kode lama)

Tanpa sandbox, pada keluaran yang direkam: catatan hilang; dua catatan; nonce salah; kenari `fail` tercatat `passed`; kenari
hilang; `canary_rc` 0; `rc` berbeda dari kode keluar; catatan menyebut node `passed` yang teksnya `FAILED` dan sebaliknya; node
di catatan yang tidak ada di teks; baris catatan tidak bocor ke `output_tail`; proyek hijau dan merah yang jujur memberi vonis,
alasan dan bukti lama yang sama (selain kunci baru).
Dengan sandbox (modul memuat `SANDBOX NOT AVAILABLE`): `tests/test_vf_forger.py` tanpa xfail, forger pipa `fail`; fixture baru
`pytest_noop_forger` `fail` dengan alasan kenari; proyek jujur `pass`; berjalan di `argus`, `ledger_py312_up2` dan `sympy_py39`
(pytest 8.4.2); `scripts/check_env_image.py` tetap lolos. Mutan: tiap aturan di butir 5 dibuang satu per satu, nonce dibuat tetap,
kenari dijalankan sebelum sesi 1 di proses lain, catatan diterima walau ganda.
Sebelum `verify_at`: `bash scripts/precheck.sh`, lalu `tests/test_pytest_validation.py`, `test_pytest_sandbox.py`,
`test_acceptance_sandbox.py`, `test_swe_pilot.py` dan berkas yang mengunci `argv` pytest.

## 6. Risiko yang diketahui

- Dua `pytest.main` dalam satu proses tidak dianjurkan pytest untuk modul yang sama; di sini sesi kedua hanya memuat berkas
  kenari yang baru. Bila ternyata rapuh di sandbox atau di pytest 8: mundur ke satu sesi dengan kenari sebagai target terakhir
  (teks berubah, kenari harus dikurangkan dari ringkasan; lebih banyak yang tersentuh).
- Plugin pytest di image yang mengubah hasil secara global (misalnya rerun) bisa membuat kenari meleset pada proyek jujur:
  `check_env_image.py` menjalankan validasi jujur per environment, jadi itu ketahuan saat image didaftarkan, bukan di job.
- Waktu: satu sesi pytest kecil tambahan per validasi; diukur dan ditulis di PR.
- Versi tool `RunValidation` (kunci memo): pertanyaan untuk peninjau, apakah dinaikkan (FIX-A sengaja tidak).

## 7. Keputusan yang diminta dari Atha

| | Pertanyaan | Saran |
|---|---|---|
| K1 | Hanya pytest di PR ini; vitest dan unittest menyusul bila perlu | ya |
| K2 | Dua sesi dalam satu proses (teks tes kontrak tidak berubah), bukan kenari di dalam sesi yang sama | ya |
| K3 | Himpunan node dibekukan saat approve: PR tersendiri sesudah ini | ya, tunda |
| K4 | Kenari meleset = `fail` biasa dulu, belum terminal | ya |
| K5 | Aturan "jangan apply `DONE` tanpa dibaca" tetap berlaku sesudah PR ini | ya |
