# Spek: FIX-C, ledger tahan mati listrik (D2) dan key tidak masuk log atau teks error (D7)

Status: **dikerjakan Claude 2026-11-12** (Atha: "b dulu", FIX-C dulu sebelum RC; item 4 fase 3 di `FABLE_PLAN_2026-11-11.md`). Jalur ketat, menyentuh jalur uang
(`harness/events.py` dan `harness/errors.py`): berlaku AGENTS.md, **merge tetap dari Atha**. Tanpa model, tanpa uang.

## D2. Ledger di disk sebelum `emit` kembali

`EventLog.emit` menulis tanpa `flush`/`fsync`, berbeda dengan memo. Proses yang mati tidak masalah (OS menulis buffer), tetapi mati listrik tepat sesudah request dikirim
menghilangkan `llm_call_started`, dan `reconcile_ledger` tidak lagi menagih panggilan itu (jaminan "setiap percobaan sampai ke ledger"). **Perbaikan:** `flush()` lalu
`os.fsync()` di dalam `emit`, di bawah kunci yang sama; galat fsync tidak ditelan (emit gagal keras, seperti galat tulis).

Bagian kedua dari temuan D2 ("baris non-final yang tak bisa di-decode adalah galat") **tidak dikerjakan**, dengan alasan: `EventLog` sengaja menambah newline pada baris
terakhir yang terpotong saat proses mati di tengah tulis, sehingga potongan itu menjadi baris non-final yang sah (rekam yang terpotong adalah rekam yang tidak pernah
terkirim, karena `llm_call_started` ditulis sebelum kirim). Menjadikannya galat membuat setiap job yang pernah crash tak bisa dibaca. Kerusakan lain pada rekam lengkap
butuh kerusakan disk; bila `llm_call` akhir yang rusak, `llm_call_started` tetap ada dan panggilan ditagih sebesar kasus terburuk (konservatif). `runner.py` sudah melaporkan
jumlah baris yang tak bisa di-decode. Dibuka lagi bila jumlah itu pernah tidak nol pada job nyata.

## D7. Nilai key tidak keluar lewat log atau teks error

Teks error penyedia masuk ledger (`llm_call`, `llm_count_failed`, event retry) dan pesan `LLMCallFailed` apa adanya; penyedia yang menggemakan request-nya bisa membawa
header `Authorization`. **Perbaikan:** `harness/redact.py`: setiap key yang diberikan ke klien (`models/registry._api_key`) didaftarkan (`register`); `EventLog.emit` mengganti
setiap nilai terdaftar di seluruh rekam (nilai bersarang ikut; juga di `echo`), dan `LLMCallFailed` menyembunyikannya di pesannya. Nilai kurang dari 8 karakter tidak
didaftarkan (placeholder seperti `unused` akan menghapus kata biasa). Penanda `[redacted]`. Serangan A9 (`FABLE_INJECTION_ATTACKS.md`) jadi tes.

**Batas yang diketahui (tidak ditutup):** (1) pengecualian asli yang dirantai (`raise ... from exc`) tetap membawa teks penyedia; yang tidak tersaring hanya muncul bila ada
yang mencetak traceback penuh ke terminal, bukan di ledger atau pesan job. (2) Key yang tidak melewati `_api_key` (misalnya klien dibangun di luar registry) tidak terdaftar.
(3) Key yang dipotong atau diubah penyedia (di-hash, dibengkokkan) tidak dikenali. (4) Teks yang ditulis ke `job.json` oleh kode di luar `EventLog` dan `LLMCallFailed`
tidak disaring; jalur utamanya (alasan berhenti dari `LLMCallFailed`) sudah tersaring.

## Tes (gagal di kode lama), `tests/test_fix_c.py`

fsync dipanggil satu kali per rekam dan rekam sudah terbaca saat fsync jalan; galat fsync keluar; scrub (semua kemunculan, terpanjang dulu, bukan-string utuh, nilai
pendek tidak didaftarkan); rekam bersarang dan `echo`; pesan `LLMCallFailed`; `_api_key` mendaftarkan; A9: galat permanen dan galat sementara yang gagal sesudah retry tidak
membawa key ke `events.jsonl` maupun ke pengecualian, sementara sisa teks error tetap ada. Mutants: `verification/fix_c_mutants.py`.

## Efek samping yang ketemu di `verify_at` (dan perbaikannya)

Dengan fsync, `verify_at` pertama (`verification/verify-20261112T135411Z-aarch64.log`) gagal di dua tes `test_crash_after_commit_is_answered_from_memo[worker-0/3]`
(11 dari 12 `result_committed`). Penyebab: di `harness/guard.py` sebuah node menulis memo (`memo.put`) lalu event `result_committed`; simulasi crash worker A (`os._exit`)
bisa jatuh saat worker B sudah di memo tetapi event-nya masih antre menunggu kunci log. Sebelum fsync jendela itu mikrodetik; sekarang tiap emit makan sekitar 1,4 ms
(diukur, 500 emit). Memo tetap benar (resume membaca memo, tidak ada kerja diulang, tidak ada uang hilang), hanya event itu yang hilang di tes yang menghitungnya.
**Perbaikan:** simulasi crash menunggu `CRASH_GRACE_S = 0.2` detik sebelum `os._exit`. Hanya jalur simulasi (`maybe_crash`); crash sungguhan tidak berubah.
Diukur dengan `CRASH_REPEATS=30` (verify memakai 5): tanpa jeda 15 gagal dari 251, dengan jeda 0,2 s 251 lulus.

## FIX-C2 (2026-11-13): kebocoran yang ditemukan Fable pada `e892d5a`

Jalur ketat (menyentuh key): berlaku AGENTS.md, **merge dari Atha**. Tanpa model, tanpa uang. Tes: `tests/test_fix_c_leaks.py`; mutants: `verification/fix_c2_mutants.py`.

1. **`runner.py` `result.json`** (jalur `main.py`) ditulis tanpa `scrub_value`. Sekarang disaring, seperti `codetask/run.py`.
2. **`verdict_N.json`** (`codetask/run.py`) ditulis tanpa `scrub_value`. Sekarang disaring. (Isinya keluaran validasi di sandbox, tempat key tidak pernah masuk; disaring karena murah dan satu pola dengan `result.json`.)
3. **Filter terminal hanya dipasang di `scripts/argus.py`.** Sekarang `redact.install()` ada di blok `__main__` setiap entry script yang bisa memegang key: `main.py` dan `scripts/{approve_draft,calibrate_judge,check_deepseek_thinking,draft_task,measure_context,run_code_task,run_eval,smoke_live,smoke_models}.py`. Satu tes (AST) menelusuri `main.py` dan `scripts/*.py`: yang punya `__main__` dan mengimpor `models`, `runner`, `codetask` atau `router` harus memanggil `install()`, kecuali empat skrip tampilan (`pin_status`, `scoreboard`, `swe_grade`, `build_review`) yang tidak membangun klien sehingga tidak ada key terdaftar di prosesnya. Skrip baru yang lupa memasangnya membuat tes gagal.
4. **Base64 `user:key` (HTTP Basic).** `register` kini juga mendaftarkan bagian base64 dari `<apa pun>key<apa pun>` yang tidak bergantung pada sekitarnya, untuk tiga keselarasan key di dalam grup 3 byte (hanya grup yang seluruhnya ada di dalam key). Bagian yang kurang dari 8 karakter dibuang. Diuji untuk key 8 sampai 51 karakter, user 0 sampai 11 karakter, dengan dan tanpa ekor.

**Batas yang ditemukan reviewer dan tidak ditutup di sini (jangan klaim "tidak ada key di berkas job mana pun"):** (a) penulis lain yang menyimpan teks model atau penyedia tanpa `scrub_value`: `codetask/drafter.py` (`_write`: draft.json, check_report.json, DRAFT_REVIEW.md, issue.txt, result.json), `router/research.py` (REPORT.md, findings.json, report.json), berkas judge di `router/job.py`; risikonya rendah karena key tidak masuk prompt atau sandbox dan teks error sudah bersih di sumbernya, tetapi sebuah penyedia yang menggemakan key ke dalam teks yang kemudian dimasukkan ke draf atau laporan akan lolos; (b) `verdict_N.json` memakai `default=str` sesudah `scrub_value`, jadi objek bukan-JSON (Path, pengecualian) di dalamnya diubah ke teks setelah penyaringan; (c) filter terminal hanya menyaring tulisan teks ke `sys.stdout`/`sys.stderr`: `sys.stdout.buffer`, `sys.__stdout__`, keluaran proses anak pada fd turunan dan galat tingkat C tidak lewat filter (tidak ada dari 10 skrip yang memakai `.buffer`); (d) base64 urlsafe (alfabet `-_`) dari `user:key` tidak didaftarkan (HTTP Basic memakai base64 standar); 1 sampai 2 byte key di grup parsial awal dan akhir sebuah token tetap terlihat (paling banyak 16 bit key), itu sifat bawaan; (e) `register()` melempar `UnicodeEncodeError` untuk key dengan surrogate tunggal (sudah begitu sebelumnya).

**Tidak ditutup, dicatat:** `checkpoints.sqlite` (isi graf agen: balasan model dan hasil tool; key tidak masuk sandbox dan teks error sudah bersih di sumbernya), data staging (`router/stage*.py`: snapshot yang dihasilkan dari job yang sudah tersaring), `acceptance/repro.py` (keluaran kode sandbox), dan teks yang dipotong penyedia atau diubah bentuknya (batas 3 di bagian D7).
