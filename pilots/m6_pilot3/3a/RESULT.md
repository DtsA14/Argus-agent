# M6 pilot 3a: hasil live run (2026-10-21)

Status: **`FAILED_ACCEPTANCE`** (`stagnant: the same criteria failed 2 attempts in a row`), dicatat sebagai hasil. Tidak ada run ulang,
tidak ada kenaikan cap. Klasifikasi pilot (`failed` / `human-assisted`) adalah keputusan reviewer. Bukti: `evidence/live/`.

## Fakta

| Hal | Nilai |
|---|---|
| Run | `pilot3a`, checkout bersih `c54d8da` (`provenance.argus.dirty: false`), kontrak `0826ee93de65`, profil `large`, config pilot (cap $0,75) |
| Biaya | **$0,200014** (`usd_complete: true`), 7 panggilan terkirim + 2 ditolak harness sebelum dikirim |
| Attempt | 2; **keduanya `reservation_exhausted`** (permintaan berikutnya tidak muat di reservasi 45.000 token) |
| Awal run | dua percobaan mulai mati di `node_start agent` dengan 0 panggilan model ($0): `ANTHROPIC_API_KEY` tidak terbaca oleh prosesnya (`MissingApiKey`, direproduksi tanpa memanggil provider). Run dilanjutkan dengan `--resume` pada run id yang sama, sesuai aturan; bukan hasil pilot |
| Hasil kerja agen | `evals/runlog.py` ditulis, `audit_run.py` dan `failure_trace.py` disunting (`evidence/live/agent_changes.diff`). Validasi `inspectors`: **9 dari 16 tes lulus**; 3 dari 5 tes wajib lulus (reader, dan skrip yang tidak melaporkan `result.json`) |
| Penyebab kegagalan tes | satu kesalahan: `audit_run.py` memanggil `read_result(run_dir)` tetapi impor-nya hanya `read_events, read_memo, skipped_line` (`NameError`). Itu menggagalkan dua tes wajib dan lima penjaga yang menjalankan `audit_run.py` |
| `SUMMARY.json` | tidak pernah ditulis (agen tidak sampai `Finish`), jadi tidak ada klaim penyelesaian |

## Jalannya (dari `failure_trace.py` dan `audit_run.py`; semua hash prompt cocok)

| Attempt | Langkah | Masukan (token) | Catatan |
|---|---|---|---|
| 0 | s0 | 3.097 | `ListFiles`, baca `audit_run.py`, `failure_trace.py` |
| 0 | s1 | 12.657 | baca `test_run_inspectors.py`, **`test_run_inspectors_data.py`**, `harness/events.py` |
| 0 | s2 | 23.840 | tulis `runlog.py`, 4 suntingan (keluaran 3.046) |
| 0 | s3 | 27.252 | **ditolak**: sisa reservasi 2.049 token; belum pernah menjalankan validasi |
| 1 | s0 | 3.983 | baca ulang tiga berkas, jalankan `inspectors` (melihat `NameError`) |
| 1 | s1–s3 | 8.424 → 18.743 | menjelajah (`SearchFiles codetask/tests`, baca `codetask/tools.py` dan tes) alih-alih memperbaiki impor |
| 1 | s4 | 18.971 | **ditolak** |

## Temuan

1. **Asumsi desain yang salah:** modul data emas (15 KB) saya pisahkan supaya agen "tidak perlu membacanya"; agen membacanya tetap
   (±8k token terkirim ulang di tiap langkah berikutnya). Simulasi menganggap agen hanya membaca tes utama; satu bacaan ekstra itu
   yang mengubah jalur bersih ±38k menjadi 43k pada attempt 0 dan membuat langkah validasi tidak muat.
2. **Kesalahan agen kecil dan mudah:** impor yang kurang. Setelah melihat keluaran validasi di attempt 1 agen tidak memperbaikinya,
   dan menghabiskan sisa reservasi untuk menjelajah.
3. **Reservasi per attempt membatasi lebih keras daripada cap uang:** terpakai $0,20 dari $0,75. Cap $0,75 dan profil `large`
   memberi 2 attempt; yang habis adalah token tiap attempt, bukan uang.
4. Simulasi token (`TOKEN_SIMULATION.md`) memperkirakan "jalur bersih muat di 45k, satu siklus perbaikan tidak"; hasil nyata
   sesuai arah itu (tidak muat), dengan penyebab tambahan di atas.
5. Alat yang dibangun di pilot ini bekerja: `failure_trace.py` dan `audit_run.py` (versi lama) membaca run live tanpa masalah.

## Keputusan yang diperlukan (tidak diambil otomatis)

Tidak ada run ulang dan tidak ada kenaikan cap atau profil tanpa persetujuan baru. Opsi untuk dipertimbangkan reviewer: (a) catat
sebagai `failed` dan lanjut; (b) task yang lebih kecil dengan bacaan wajib lebih sedikit (mis. modul data lebih kecil atau dipecah per
skrip); (c) apakah `Finish` yang gagal karena reservasi sebaiknya membawa umpan balik yang lebih berguna ke attempt berikutnya
(attempt 1 memulai dari workspace yang sudah diedit, tetapi menghabiskan 4 dari 5 langkahnya untuk membaca ulang dan menjelajah).
Waktu supervisi: belum dicatat (perlu angka dari Atha).
