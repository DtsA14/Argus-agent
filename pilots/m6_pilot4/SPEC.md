# M6 pilot 4 (usulan): `is_peak` dengan jendela yang melewati tengah malam

Status 2026-10-21: **spesifikasi untuk review. Belum ada draf, tes, patch referensi, simulasi final, atau coder.** Dasar: hasil Pilot 3a
(`failed`, `pilots/m6_pilot3/3a/RESULT.md`) dan arahan reviewer: task lebih kecil, bacaan wajib minimal, satu variabel diubah (ukuran task),
beberapa run per kondisi. Basis: `main`.

## 1. Kandidat yang dipertimbangkan (dari `PENDING.md`)

| Kandidat | File | Ukuran file yang harus dibaca | Catatan |
|---|---|---|---|
| **A. `is_peak` jendela melewati tengah malam** (usulan) | `models/pricing.py` | **1,3 KB** (±0,8k token) | Satu fungsi, perilaku tunggal, tes deterministik dengan `datetime`. Menyentuh uang, tetapi laten dan dibatasi (lihat 4) |
| B. Judul `PR.md` dipotong di tengah kata | `codetask/review.py` | **30 KB** (±10k token) jika dibaca utuh | Kosmetik; pilihan perilaku ambigu (elipsis? batas kata?); `ReadFile` tidak punya rentang baris, jadi bisa mahal. Cadangan |
| C. `intake_repo.py --check <task> --repo` mismatch palsu | `acceptance/intake.py` (9 KB) | ±3k token | Fondasi acceptance, lebih rumit; tidak cocok setelah arahan "jangan pakai coder untuk fondasi coder" |

Usulan: **A**, karena paling kecil, perilakunya paling jelas, dan tidak menyentuh jalur coder maupun acceptance. B sebagai cadangan.

## 2. Reproduksi (dijalankan, tanpa model)

`models/pricing.py::is_peak` hanya mengenali `start <= hour < end`. Jendela yang melewati tengah malam tidak pernah cocok:

```
window = {"utc_hours": [[22, 4]]}
23:00 UTC -> False    01:00 UTC -> False    03:00 UTC -> False   (seharusnya True, True, True)
04:00 UTC -> False    12:00 UTC -> False                         (benar: akhir eksklusif; di luar jendela)
jendela di config.yaml ([1,4], [6,10], weekdays_only)  -> 03:00 Rabu True, Sabtu False   (benar, tidak berubah)
```

Pemakai: `multiplier()` dan `cost_usd()` (`models/pricing.py`), `harness/llm.py`, `scripts/calibrate_judge.py`. **Laten**: jendela di `config.yaml`
tidak melewati tengah malam, jadi tidak ada perilaku produksi yang berubah dengan patch ini.

## 3. Perilaku yang ditetapkan (semua keputusan eksplisit; butuh persetujuan reviewer)

1. Jendela `[start, end]` dengan `start < end`: seperti sekarang (`start <= jam < end`).
2. Jendela dengan `start > end` (melewati tengah malam, mis. `[22, 4]`): cocok bila `jam >= start` **atau** `jam < end`. Akhir tetap eksklusif.
3. `start == end`: **tidak pernah cocok** (jendela kosong, seperti sekarang). Bukan "sehari penuh".
4. `weekdays_only`: dinilai pada **tanggal UTC dari `now`**, seperti sekarang, juga untuk jendela yang melewati tengah malam (Sabtu 01:00 UTC
   tidak dihitung puncak walau jendela Jumat 22:00 dimulai di hari kerja). Sederhana dan tidak mengubah aturan yang ada; dicatat sebagai batasan.
5. Beberapa jendela dalam satu daftar (`[[22, 4], [6, 10]]`): cocok bila salah satu cocok. `now` non-UTC dikonversi ke UTC. `window` kosong/`None`: `False`.
6. Nilai `end` 24 tetap bekerja (`[20, 24]` = 20:00 sampai tengah malam), seperti sekarang.

## 4. Batas perubahan

- **Writable:** `models/pricing.py` saja. **Protected:** semuanya yang lain, termasuk `config.yaml`, `harness/**`, `scripts/**`, `tests/**`.
- Mengubah jendela di `config.yaml` atau cara biaya dihitung: di luar scope. Hanya `is_peak` yang berubah, jadi `multiplier`/`cost_usd` mengikuti.
- Karena menyentuh uang: patch referensi manusia, mutan (termasuk off-by-one di akhir eksklusif dan `or` jadi `and`), `verify.sh` penuh,
  review patch agen oleh manusia sebelum dianggap selesai. Tidak ada perubahan perilaku produksi (jendela config tidak melewati tengah malam).

## 5. Acceptance (rancangan)

Berkas tes baru kecil `tests/test_peak_window.py` (target ±3 KB, tanpa modul data). Tes wajib (merah di baseline karena assertion):
jendela `[22, 4]`: 23:00, 01:00, 03:59 di dalam; 04:00, 12:00, 21:59 di luar; dua jendela `[[22, 4], [6, 10]]`; `weekdays_only` pada tanggal
UTC dari `now` (Jumat 23:00 benar, Sabtu 23:00 salah); `multiplier()` dan `cost_usd()` memakai `peak_multiplier` di dalam jendela yang melewati
tengah malam. Penjaga (lulus di baseline): jendela biasa `[1, 4]`, `[6, 10]`, akhir eksklusif, `start == end`, `None`, akhir pekan, `now` non-UTC.
Regresi: tes yang sudah ada yang memakai puncak (`test_llm_wrapper.py`, `test_calibration.py`, `test_judge.py`) tidak berubah.

## 6. Ukuran dan skenario token (perkiraan, simulasi sebenarnya menyusul)

Pelajaran 3a: simulasi harus memasukkan skenario "agen membaca semua berkas tes yang ada".

| Skenario | Bacaan | Perkiraan token bacaan |
|---|---|---|
| minimal | `pricing.py` + tes baru | ±2,2k |
| wajar | + `tests/test_models.py` | ±4,9k |
| terburuk wajar (mengejar semua pemakai) | + `harness/llm.py` (19 KB), `tests/test_llm_wrapper.py`, `test_calibration.py`, `test_judge.py`, `calibrate_judge.py` | ±35k |

Skenario terburuk tidak muat di reservasi `default` 30k (dan hampir tidak di 45k). Mitigasi: issue menyebut fungsi dan file persisnya dan
bahwa tidak ada pemakai yang perlu dibaca; tetap dihitung sebagai risiko. Profil usulan: `default` ($0,30; cap $0,50), karena dua skenario
pertama muat jauh di bawah 30k. Kalau simulasi skenario terburuk dipakai sebagai syarat, task ini bisa gagal syarat, dan B (judul `PR.md`) juga
(30 KB utuh): itu perlu keputusan reviewer.

## 7. Rencana run

Beberapa run pada kontrak yang sama (usulan 3, masing-masing `--run-id` baru, kunci diketik Atha, "go live" eksplisit per run), dilaporkan sebagai
"x dari 3 `DONE`" dengan biaya per run, bukan sebagai satu kesimpulan. Model tidak deterministik; satu run adalah satu sampel. Perkiraan biaya
total di bawah $0,30. Tidak ada kenaikan cap atau perubahan harness di antara run.

## 8. Keputusan untuk reviewer

1. Setuju kandidat A (atau pilih B/C)?
2. Perilaku 3.3 (`start == end` kosong) dan 3.4 (weekday pada tanggal UTC `now`) sudah seperti yang diinginkan?
3. Apakah skenario terburuk yang tidak muat harus menggugurkan task, atau cukup dicatat sebagai risiko dengan issue yang menunjuk file persis?
4. Jumlah run per kondisi (3) dan profil `default`.
