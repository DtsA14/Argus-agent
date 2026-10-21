# M6 pilot 4, run 1 (`pilot4a`): hasil live (2026-10-21)

Status: **`DONE`** (`all criteria passed`). Run 1 dari rencana 3 run; run 2 dan 3 menunggu review ini. Klasifikasi pilot (`agent-completed` /
`human-assisted`) adalah keputusan reviewer. Bukti: folder ini.

## Fakta

| Hal | Nilai |
|---|---|
| Run | `pilot4a`, checkout bersih `3c76fff` (`provenance.argus.dirty: false`), kontrak `1c3a063a3ab2`, profil `large`, config pilot (cap $0,75) |
| Biaya | **$0,028892** (`usd_complete: true`), 3 panggilan terkirim, 0 ditolak, 0 tak diketahui; 1 attempt |
| Jalannya (`failure_trace.py`, `audit_run.py`: 3 hash prompt cocok, 0 mismatch) | s0 `ReadFile(models/pricing.py)` (2.732 token masuk); s1 `EditFile` + `RunValidation(target)` + `RunValidation(regression)` (3.267); s2 `Finish` (5.697). Agen **tidak membaca berkas tes**, tidak mencari, tidak menjelajah |
| Perubahan | hanya `models/pricing.py` (dan `SUMMARY.json` dari harness); tes dan `config.yaml` tidak berubah (`agent_changes.diff`) |
| Paket review (`build_review.py`) | **valid**, 12 dari 12 cek ok; validasi ulang `target` dan `regression` lulus pada tree bersih dari commit dasar + patch |
| Model dipanggil | `anthropic:claude-sonnet-5-5`; reservasi terbesar yang terpakai ±5,7k dari 45k |
| Waktu supervisi | belum dicatat (unknown) |

## Patch agen vs referensi

Agen menulis ulang bagian akhir `is_peak` sebagai loop eksplisit:

```
hour = now.hour
for start, end in window.get("utc_hours") or []:
    if start < end:   if start <= hour < end: return True
    elif start > end: if hour >= start or hour < end: return True
return False
```

- **Setara pada seluruh perilaku yang ditetapkan:** uji pembeda (`differential_test.txt`) menjalankan fungsi agen dan fungsi referensi pada **633.024 kasus**
  (semua pasangan `start`/`end` 0..24, dua daftar jendela, `weekdays_only` hidup/mati, 7 hari x 24 jam, 3 zona waktu): **0 perbedaan**.
  `start == end` kosong, akhir eksklusif, `weekdays_only` pada tanggal UTC dari `now`, konversi zona, `None`/`{}`: sama.
- **Satu perbedaan di luar yang ditetapkan:** `window.get("utc_hours") or []` membuat jendela tanpa kunci `utc_hours` (mis. `{"weekdays_only": true}`) mengembalikan
  `False`, sedangkan kode asli dan referensi melempar `KeyError`. Tidak diuji dan tidak diatur issue. Di kode penentu harga, jendela yang salah tulis
  menjadi "bukan puncak" secara diam-diam alih-alih error (gagal terbuka); ini perlu keputusan reviewer apakah diterima atau dicatat sebagai catatan.
- Bentuk lebih panjang dari referensi (loop 9 baris vs satu ekspresi); komentar docstring tidak diperbarui. Kosmetik.

## Yang masih berjalan / belum

- `verify.sh` penuh atas "main + patch agen" sedang dijalankan (hasil menyusul sebagai bukti terpisah).
- Patch dibaca manusia karena menyentuh kode harga: bagian di atas adalah hasil bacaan saya, belum review reviewer.

## Satu sampel

Ini run 1 dari 3. `DONE` di attempt pertama dengan $0,029 adalah satu sampel, bukan tingkat keberhasilan (model tidak deterministik; 3a gagal pada task yang jauh lebih besar).
Rencana: run 2 (`pilot4b`) dan 3 (`pilot4c`) hanya setelah review ini, dengan "go live" sendiri-sendiri. Tidak ada perubahan cap, profil, atau harness di antara run.
