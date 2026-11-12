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
