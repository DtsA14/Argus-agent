# Review W2a: merah harus benar-benar karena assertion

Spek: `docs/reviews/SPEC_W2A_RED_BY_ASSERTION.md` (bagian 6, keputusan review). Pemicunya pilot W2b-3
(`pilots/m6_w2b/w2b3/RESULT.md`). Ditulis Claude, 2026-10-23.

## Cara kerja

- `acceptance/validation.py` `red_check` menjalankan, di sandbox, `python3 -I -B -c RED_CHECK <nonce> <node wajib>`.
  `RED_CHECK` memanggil `pytest.main` dengan plugin kecil. Di `pytest_runtest_makereport`, plugin itu mencatat per
  node: outcome, tipe exception asli, apakah tipe itu `AssertionError`/turunannya atau `pytest.fail.Exception`, dan path
  frame terakhir **di dalam `/workspace`** (frame pytest, stdlib, dan site-packages dilewati). Hasilnya JSON di satu
  baris setelah nonce. Tidak ada teks traceback yang di-parse.
- `acceptance/draft.py` `red_by_assertion`: setiap node wajib di file tes baru atau file yang diubah harus `failed`,
  harus assertion, dan frame terakhirnya harus file tes itu sendiri atau helper yang protected dan tidak writable di
  direktori file tes itu. Run yang tidak terbaca atau node tanpa catatan membuat draf ditolak. Pengecekan ini dijalankan
  `baseline_problems` hanya bila semua cek lain di validasi itu sudah lolos.
- Pesan penolakan untuk tipe yang bukan assertion memberi petunjuk (`assert "key" in report` sebelum `report["key"]`,
  `assert hasattr(...)`, dan membuat sendiri data yang dipakai tes). Prompt drafter juga menyebut aturan ini.
- Router dan drafter meneruskan `red` (injeksi dari tes, seperti `validate` dan `collect`).

## Tes

- Sandbox, ditolak: `KeyError` di tubuh tes (dengan petunjuk), `AttributeError`, dan `assert` di kode produksi
  (`src/guard.py`).
- Sandbox, diterima: `AssertionError("msg")`, `pytest.fail`, `pytest.raises` tanpa raise, helper assert di `tests/`,
  metode kelas, dan parametrize.
- Unit: run yang tidak terbaca, catatan yang hilang, outcome bukan `failed`, tipe lain, frame di produksi, frame di luar
  repositori, dan helper yang writable.
- Drafter (fake): penolakan `KeyError` beserta petunjuknya sampai ke model, lalu submit berikutnya lolos.

## Bukti

- Tes terdampak di VM: 310 lulus.
- Mutan 10/10 mati (`verification/red_mutants.log`): plugin (tipe apa saja, frame pertama, `pytest.fail` dibuang),
  verdict (tipe, frame, outcome, run tidak terbaca, helper writable), cek yang tidak pernah jalan, dan petunjuk.
- 5 tes baru (19 kasus) dijalankan pada kode `main` lama dengan image sandbox: semuanya gagal, tidak ada yang lulus atau di-skip
  (`verification/red_mutants.log`, bagian "old code").
- `verify.sh` penuh di 67e6c46: PASS, 1536 lulus, 0 tes sandbox di-skip (`verification/red_verify.log`).

## Batas

- Hasilnya dibaca dari proses yang sama dengan kode yang dites. Pemalsuan yang disengaja dibatasi oleh sandbox, bukan
  dideteksi (batas yang sama dengan validasi pada umumnya).
- Satu run sandbox tambahan per validasi yang punya node merah (berisi node wajib saja).
