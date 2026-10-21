# M6 pilot 4, run 2 (`pilot4b`): hasil live (2026-10-21)

Status: **`DONE`** (`all criteria passed`), 1 attempt. Run 2 dari rencana 3; run 3 menunggu review ini. Klasifikasi pilot untuk run ini adalah keputusan
reviewer. Bukti: folder ini.

## Fakta

| Hal | Nilai |
|---|---|
| Run | `pilot4b`, checkout bersih `d83c2d9` (`provenance.argus.dirty: false`), kontrak `1c3a063a3ab2`, profil `large`, config pilot (cap $0,75), dijalankan lewat `~/go_live.sh pilot4b` (kunci diketik Atha) |
| Biaya | **$0,028872** (`usd_complete: true`), 3 panggilan terkirim, 0 ditolak, 0 tak diketahui; 1 attempt |
| Jalannya (`failure_trace.py`, `audit_run.py`: 3 hash prompt cocok, 0 mismatch) | s0 `ReadFile(models/pricing.py)` (2.732 token masuk); s1 `EditFile` + `RunValidation(target)` + `RunValidation(regression)` (3.267); s2 `Finish` (5.697). Tidak membaca tes, tidak menjelajah |
| Paket review (`build_review.py`) | **valid**, 12 dari 12 cek ok |
| Waktu supervisi | belum dicatat (unknown) |

## Perbandingan dengan run 1 (`pilot4a`)

| | run 1 | run 2 |
|---|---|---|
| status / attempt / panggilan | `DONE` / 1 / 3 | `DONE` / 1 / 3 |
| biaya | $0,028892 | $0,028872 |
| token masuk per langkah | 2.732 / 3.267 / 5.697 | 2.732 / 3.267 / 5.697 |
| alat per langkah | Read, Edit+2 Validasi, Finish | Read, Edit+2 Validasi, Finish |
| `models/pricing.py` hasil | sha256 `d64b967c398c…` | sha256 `d64b967c398c…` (**byte-identik**) |
| `changes.patch` | sha256 `bf89d5b5ba81…` | sha256 `bf89d5b5ba81…` (**identik**) |
| `SUMMARY.json` | "...keeps the UTC conversion and weekdays_only check." | "...keeps the weekday check on the UTC date of now." (hanya kalimat ringkasan berbeda) |
| penyimpangan `utc_hours` (jendela tanpa kunci → `False`) | ya | ya, sama (kode identik) |

## Bacaan

- Patch run 2 **identik** dengan run 1 sampai tingkat byte; maka uji pembeda 633.024 kasus, `verify.sh` (1196 lulus, 0 skip, PR #108/#109), dan kesimpulan tentang `utc_hours`
  untuk run 1 berlaku apa adanya (kode yang sama, sudah ada di `main` lewat PR #109). Tidak ada verifikasi baru yang diperlukan untuk patch ini.
- Penyimpangan `utc_hours` **tidak kebetulan** pada run 1: model memilih bentuk yang sama lagi. Itu bukti bahwa celah spesifikasi mendorong isian yang konsisten, bukan acak.
- **Dua sampel yang hampir identik bukan dua bukti independen.** Pada task kecil dengan satu jalur jelas, model ini (parameter bawaan penyedia; config tidak mengatur
  `temperature`) tampak menghasilkan hasil yang sama sampai byte. Itu menjawab pertanyaan konsistensi untuk task ini, bukan keberhasilan umum: pada 3a yang jauh lebih besar
  hasilnya gagal. Run 3 menambah satu sampel yang sama jenisnya.
- Biaya per run hampir sama ($0,0289), jauh di bawah batas ($0,75) dan di bawah perkiraan ($0,15).

## Penutupan (keputusan reviewer, 2026-10-21)

- Validasi `pilot4b` **ditutup**. Patch run 2 diperiksa dan **sesuai patch run 1** (`models/pricing.py` dan `changes.patch` byte-identik; sha256 di atas), yang sudah ada di `main` lewat PR #109.
- `verify.sh` pada `main` (`d83c2d9`, berisi patch) selesai bersih: **1196 lulus, 0 skip sandbox, PASS** (`verification/verify-m6-pilot4-main-d83c2d9-20261021T163656Z-aarch64.log`).
- **`pilot4c` tidak dijalankan** dengan kontrak yang sama: dua run menghasilkan patch identik dengan biaya hampir sama, jadi run ketiga memberi sedikit informasi baru. Hasil Pilot 4: **2 dari 2 `DONE`**
  (satu attempt, ±$0,029 masing-masing, patch byte-identik); ini indikasi konsistensi pada task kecil, bukan tingkat keberhasilan umum.
- Langkah berikutnya: task `utc_hours` gagal-tertutup (aturan lebih ketat; acceptance, tes pembeda, dan patch referensi dibekukan sebelum coder dijalankan).
