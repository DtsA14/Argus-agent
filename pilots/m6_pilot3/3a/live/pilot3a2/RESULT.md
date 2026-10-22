# M6 pilot 3a, replikasi (`pilot3a2`): hasil live (2026-10-22)

Status: **`FAILED_ACCEPTANCE`** (`stagnant: the same criteria failed 2 attempts in a row`), dicatat sebagai hasil. Satu run, tidak ada pengulangan, tidak ada perubahan: kontrak `fix_run_inspectors` (`0826ee93de65`), profil `large`, cap pilot $0,75,
checkout bersih `9b3f929` (`dirty: false`), lewat `pilots/m6_pilot3/3a/go_live.sh` (semua gerbang lolos, kunci diketik Atha). Bukti: folder ini.

## Fakta

| Hal | `pilot3a` (run 1) | `pilot3a2` (replikasi) |
|---|---|---|
| status | `FAILED_ACCEPTANCE` | `FAILED_ACCEPTANCE` |
| attempt / panggilan terkirim / ditolak | 2 / 7 / 2 | 2 / 6 / 2 |
| akhir tiap attempt | `reservation_exhausted`, `reservation_exhausted` | `reservation_exhausted`, `reservation_exhausted` |
| biaya | $0,200014 | **$0,193676** |
| tes `inspectors` lulus di akhir | 9 dari 16 (3 dari 5 wajib) | **8 dari 16** (2 dari 5 wajib: kontrak reader) |
| `SUMMARY.json` / `Finish` | tidak pernah | tidak pernah |
| `RunValidation` dipanggil oleh agen | sekali (attempt 1) | **tidak pernah** |
| berkas yang berubah | `runlog.py`, `audit_run.py`, `failure_trace.py` | hanya `runlog.py` dan `audit_run.py` |
| waktu supervisi | unknown | belum dicatat |

## Langkah demi langkah (`comparison_step_by_step.txt`, `failure_trace.txt`)

- **Langkah 0 attempt 0 identik** dengan run 1 (hash prompt sama): `ListFiles` + `audit_run.py` + `failure_trace.py`, 3.097 token masuk.
- **Langkah 1 identik dalam isi:** membaca tes utama, **modul data**, dan `harness/events.py` (12.657 token masuk pada kedua run, keluaran 172). Hash prompt berbeda karena id pemanggilan alat dari provider acak; jumlah token dan alatnya sama.
- **Langkah 2 berbeda:** run 1 menulis `runlog.py` dan empat penyuntingan (keluaran 3.046); replikasi memanggil `SearchFiles("runlog")` (keluaran 170, tanpa menulis apa pun). Masukan keduanya 23.840. Langkah 3 ditolak di keduanya: run 1 tersisa 2.049 token, replikasi 4.925, masing-masing untuk
  masukan ≥ 24.103.
- **Attempt 1 replikasi mengulang awalnya**: `ListFiles` + dua skrip (3.957 token), lalu tiga bacaan yang sama (13.517), lalu `WriteFile(evals/runlog.py)` + satu `EditFile(audit_run.py)` (keluaran 2.222); langkah 3 ditolak (tersisa 293 token untuk masukan 27.060).
  Attempt 1 tidak memperpendek jalurnya walau tahu bahwa workspace masih kosong dari attempt 0 (umpan balik: "files changed from the original: none").
- **`NameError: name 'read_result' is not defined` muncul lagi di `audit_run.py`**, kesalahan yang persis sama dengan run 1 (menulis `read_result(run_dir)` tanpa menambah impor). Di replikasi agen tidak pernah menjalankan validasi, jadi tidak sempat melihatnya.

## Bacaan

1. **Kegagalan stabil di sisi model juga, bukan hanya di sisi harness** (replay sudah membuktikan sisi harness): empat dari empat attempt di dua run berakhir `reservation_exhausted`, tidak satu pun mencapai `Finish`, dan dua run memilih awal yang sama (`ListFiles` dan bacaan yang sama).
   Model menyimpang mulai langkah ketiga, tetapi hasilnya sama karena anggarannya sudah habis lebih dulu.
2. **Kesalahan impor di `audit_run.py` adalah pola yang berulang**, bukan kebetulan: kedua run menaruh `read_result(...)` tanpa mengimpornya.
3. **Biaya sebelum aksi pertama yang berarti** (`ListFiles` 4.141 + bacaan skrip 1.933 + tes/data/events 8.127 token, semuanya terkirim ulang tiap langkah) sudah sekitar separuh reservasi di langkah ke-3. Hipotesis H1 (task lebih kecil) dan H2 (issue menyebut jalur
   persis dan tidak perlu daftar berkas) di `INVESTIGATION.md` makin kuat; H3 (umpan balik dengan traceback) tidak bisa dinilai dari replikasi ini karena agen tidak pernah menjalankan validasi.
4. **Tidak ada alasan menjalankan 3a ketiga kali** dengan konfigurasi ini; yang berubah harus task, issue, atau harness (keputusan reviewer).
