# Review: task umum slice 1, bagian A (inti deterministik)

Kontrak: `docs/reviews/ACCEPTANCE_GENERAL.md` (disetujui, PR #20). Bagian ini membangun semua yang memutuskan
**apakah sebuah task selesai**, tanpa agen dan tanpa model. Bagian B (PR berikutnya) menambahkan loop agen, status
run `FAILED_ACCEPTANCE` dan `BLOCKED`, budget per task, dan crash-resume, dengan model palsu.

## Yang dibangun

| Bagian | File | Isi |
|---|---|---|
| Repo fixture | `fixtures/repos/calc/` | 5 fungsi, 7 tes `unittest`. `divide(a, 0)` mengembalikan 0, jadi tepat 1 tes gagal |
| Kontrak | `fixtures/contracts/fix_divide.json`, `acceptance/contract.py` | validasi penuh, dibekukan (JSON kanonis + sha256) |
| Workspace | `acceptance/workspace.py` | salinan repo, snapshot (path → sha256), diff, cek scope |
| Validasi | `acceptance/validation.py`, `tools/sandbox.py` (`run_command`) | perintah terstruktur, allowlist, sandbox read-only, tanpa shell |
| Klaim | `acceptance/claims.py` | schema `claims_v1` untuk `SUMMARY.json`, setiap klaim dicek terhadap bukti |
| Putusan | `acceptance/verdict.py` | kriteria lapis A–D dengan bukti; hasil `pass`, `fail`, atau `blocked` |

`tools/sandbox.py`: `run_python` tidak berubah perilakunya. Bagian yang menjalankan kontainer dipisah ke `_run`, lalu
`run_command(argv)` ditambahkan. Fungsi ini hanya menerima list argv (string ditolak) dan me-mount workspace
**read-only** tanpa `/data`. Batas, timeout (kontainer dimatikan), dan pembersihan sama dengan `run_python`.

## Keputusan review PR #20 yang diterapkan

- **Perintah terstruktur, tanpa shell.** Kontrak berisi `executable` + `args`. Slice 1 hanya mengizinkan
  `python -m unittest discover` dengan opsi `-s`, `-t`, `-p`, dan `-k`. Nilai opsi harus nama relatif biasa: tanpa
  `..`, tanpa path absolut, tanpa karakter shell. Harness menjalankan `python3 -I -m unittest discover ... -v` sebagai
  list argv di kontainer.
- **Timeout membunuh proses.** Timeout dari kontrak menjadi timeout sandbox. Saat lewat batas, kontainer di-kill dan
  dihapus, dan tes memeriksa bahwa tidak ada kontainer tersisa.
- **`SUMMARY.json` wajib.** Schema ketat: hanya `claims` dan `summary`, hanya tiga jenis klaim (`tests_pass`,
  `issue_fixed`, `file_changed`), dan tidak ada kunci tambahan. Teks `summary` tidak pernah menjadi bukti.
- **Kontrak ditulis manusia.** Agen tidak punya jalur untuk mengubahnya. Kontrak divalidasi lalu dibekukan dengan
  hash.
- **Ambang per kontrak.** `min_tests ≥ 1` (0 tes yang berjalan tidak pernah lulus), `max_skipped ≥ 0`, dan
  `timeout_s` dalam (0, 600].

## Jaminan dan tesnya

| Jaminan (ACCEPTANCE_GENERAL bagian 6) | Tes |
|---|---|
| 1. Agen mengklaim selesai tapi validasi gagal → bukan pass | `test_the_fixture_bug_is_real_unit_and_target_fail` (Docker), `test_a_true_claim_does_not_rescue_a_failed_check` |
| 2. Exit 0 dengan 0 tes, atau tes di-skip → bukan pass | `BAD_RUNS`, `test_a_command_that_runs_no_tests_fails` dan `test_skipping_the_failing_test_fails` (Docker) |
| 3. Sandbox tidak tersedia → `blocked`, tidak pernah pass | `test_no_sandbox_means_blocked_never_a_pass`, `test_blocked_wins_over_fail_and_is_never_a_pass` |
| 4. File protected diubah atau dihapus → gagal walaupun tes lulus | `SCOPE_BREAKS`, `test_making_the_test_pass_by_editing_it_fails` (Docker: tes yang diedit memang lulus, dan justru karena itu task gagal) |
| 5. File di luar `writable` diubah → gagal | `SCOPE_BREAKS["write outside scope"]` |
| 6. Klaim tanpa bukti atau bertentangan dengan bukti → gagal | `FALSE_CLAIMS`, skema di `test_a_summary_outside_the_schema_is_rejected` |
| 7. Artefak berubah setelah dinilai → putusan tidak berlaku | `test_a_workspace_that_changes_during_evaluation_invalidates_the_verdict`; validasi tidak bisa menulis ke workspace (`test_validation_cannot_write_to_the_workspace`, Docker) |
| 9. Validasi timeout → gagal, proses dimatikan | `test_a_validation_that_hangs_is_killed_at_its_timeout` (Docker) |
| Tanpa shell | `test_validation_runs_without_a_shell` (Docker: `$(touch ...)` sampai sebagai argumen literal), `BAD_CONTRACTS` |

Jaminan 8 (kontrak berubah di tengah run) dan 10 (crash di tengah validasi) ada di level run, jadi masuk bagian B.

## Batasan yang dinyatakan

- **Hasil validasi dibaca dari output test runner.** Kode yang diuji berjalan di proses yang sama dengan
  `unittest`, jadi kode yang sengaja memalsukan output `unittest` dari dalam proses tidak terdeteksi di sini.
  Dampaknya tertahan sandbox, dan file tes yang dilindungi membuat tesnya sendiri tetap jujur. Opsi untuk menutup
  celah ini nanti: runner harness yang terpisah dari kode yang diuji.
- **Output dibatasi** sampai 64 KiB per stream (bagian awal yang disimpan). Kalau ringkasan `unittest` terpotong,
  kriteria gagal ("no unittest summary"); tidak pernah dianggap lulus.
- **Layer E** (budget dan waktu) ditegakkan di level run (bagian B). Di sini hanya timeout per perintah.
- **Image sandbox** `python:3.13-slim` tidak punya pytest, jadi slice 1 hanya mendukung `unittest`.

## Mutation check (VM, `tests/test_acceptance.py` + `tests/test_acceptance_sandbox.py`)

Total **33 mutan** dijalankan: 31 di run pertama dan 2 tambahan.
- **1 ekuivalen, tidak dihitung**: `os.walk(followlinks=True)`. Kode sudah membuang direktori symlink dari
  `dirnames`, dan mencatatnya sebagai bukan file biasa, sebelum `os.walk` sempat masuk. Jadi flag itu hanya lapis
  kedua, dan perilakunya tidak berubah.
- **32 mutan efektif, semuanya tertangkap**: 30 dari run pertama, ditambah 2 mutan tambahan yang benar-benar menghapus
  perlindungan symlink:
  - cabang `is_symlink()` dihapus (direktori symlink tidak lagi dicatat dan tidak lagi dibuang dari `dirnames`);
  - cabang yang sama dihapus **dan** `followlinks=True` (walk benar-benar masuk ke direktori di luar workspace).

  Keduanya tertangkap oleh `test_a_symlink_in_the_workspace_fails_and_is_not_followed`.

Tes symlink itu menguji perilaku, bukan teks kode. Tes membuat direktori sungguhan di luar workspace berisi sebuah
file, lalu memasang symlink ke direktori itu dari dalam `src/`. Setelah itu tes memeriksa tiga hal: snapshot mencatat
symlink sebagai bukan file biasa, tidak ada satu pun file dari luar workspace yang masuk ke snapshot, dan kriteria
`scope:regular_files` gagal. Path traversal di bagian ini dijaga oleh validasi kontrak (glob dan nilai opsi tanpa `..`
atau path absolut, diuji di `BAD_CONTRACTS`) dan oleh mount read-only saat validasi. Tool tulis milik agen datang di
bagian B lewat `PathJail`, yang sudah punya tes traversal dan race sendiri (`tests/test_fs.py`).

Daftar mutan mencakup: setiap syarat lulus validasi (min_tests, skip, must_pass, exit code, outcome, ringkasan, timeout,
`-v`, timeout kontrak), `blocked` menjadi pass, allowlist (executable, prefix, nilai), workspace read-only, argv
string, scope (protected, writable, file khusus), cache bytecode, setiap cek klaim, prioritas `blocked`, perubahan
saat evaluasi, dan validasi kontrak (min_tests 0, judge, tumpang tindih scope).
