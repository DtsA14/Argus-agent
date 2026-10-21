# M6 pilot 5, run 1 (`pilot5a`): hasil live (2026-10-21)

Status: **`DONE`** (`all criteria passed`), 1 attempt. Satu live run, tidak ada run lain. Klasifikasi pilot (`agent-completed` / `human-assisted`) adalah keputusan reviewer.
Bukti: folder ini.

## Fakta

| Hal | Nilai |
|---|---|
| Run | `pilot5a`, checkout bersih `1bb9b12` (`provenance.argus.dirty: false`), kontrak `a05548186f86`, profil `large` (45.000 token, keluaran maks 8.192), config pilot (cap $0,75), lewat `pilots/m6_pilot5/go_live.sh` (semua gerbang lolos, kunci diketik Atha) |
| Biaya | **$0,042622** (`usd_complete: true`), 3 panggilan terkirim, 0 ditolak, 0 tak diketahui; 1 attempt |
| Jalannya (`failure_trace.py`, `audit_run.py`: 3 hash prompt cocok, 0 mismatch) | s0 `ReadFile(models/pricing.py)` (3.150 token masuk); s1 satu `EditFile` besar (keluaran 1.133 token) + `RunValidation(target)` + `RunValidation(regression)` (3.738); s2 `Finish` (7.338). **Tidak membaca berkas tes**, tidak mencari, tidak menjelajah |
| Pemakaian reservasi | ±15,6k token terpakai dari 45k (simulasi memperkirakan ±23k untuk jalur `minimal`, ±17k untuk `search_first`); tidak ada `reservation_exhausted` |
| Perubahan | hanya `models/pricing.py` (dan `SUMMARY.json` dari harness); tes dan `config.yaml` tidak berubah (`agent_changes.diff`) |
| Paket review (`build_review.py`) | **valid**, 12 dari 12 cek ok |
| Waktu supervisi | belum dicatat (unknown) |

## Patch agen vs referensi

Agen menaruh seluruh validasi langsung di `is_peak` (tanpa fungsi `_checked` terpisah), menambah `_is_int` (bilangan bulat tetapi bukan bool), dan docstring yang menyatakan kewajiban zona waktu. Urutan pemeriksaan sama dengan referensi
(jendela falsy lebih dulu, lalu seluruh jendela, lalu `now`).

- **Setara pada seluruh perilaku yang ditetapkan:** uji pembeda (`differential_test.txt`) membandingkan fungsi agen dengan fungsi referensi: **403.200 kasus jendela valid, 0 perbedaan**; **1.301 input tidak valid atau aneh**
  (semua tipe nilai, semua kombinasi `weekdays_only`, `now` naive dan berzona, semua pasangan `start`/`end` −3..27, jendela non-dict dan falsy): **0 perbedaan** (jenis hasil: nilai, `WindowError`, atau galat lain).
  Item buruk di belakang item yang cocok ditolak oleh keduanya; jendela falsy dengan `now` naive menghasilkan `False` pada keduanya.
- **Satu perbedaan di luar yang ditetapkan:** subclass `int` selain `bool` (mis. `IntEnum`) diterima oleh agen (`isinstance(v, int) and not isinstance(v, bool)`) dan ditolak oleh referensi (`type(v) is int`). Issue menyebut "bilangan bulat
  (bool dan float ditolak)"; subclass `int` tidak disebut dan tidak diuji. Dampak praktis nol (jendela berasal dari YAML: `int` biasa); dicatat sebagai pengamatan.
- Pesan galat menyebut masalah dan nilai yang salah, seperti diminta.

## Yang belum

- `verify.sh` penuh atas "main (`1bb9b12`) + patch agen" (working tree bersih): **1210 lulus, 0 skip sandbox**, `RESULT: PASS` (`verification/verify-m6-pilot5a-agent-patch-20261021T181631Z-aarch64.log`). Patch belum diterapkan ke `main`; itu PR terpisah setelah keputusan reviewer.
- Patch dibaca manusia karena menyentuh kode harga: bagian di atas adalah hasil bacaan saya dan uji pembeda, belum review reviewer.

## Satu sampel

Ini satu run pada task dengan spesifikasi lebih ketat dari Pilot 4. `DONE` di attempt pertama dengan $0,043 adalah satu sampel, bukan tingkat keberhasilan; model tidak deterministik (Pilot 4: dua run, patch byte-identik; 3a: gagal pada task yang jauh lebih besar).
Skenario "baca semua pemakai `is_peak`" tidak terjadi di run ini dan tetap risiko terbuka. Tidak ada run lain tanpa keputusan reviewer dan "go live" sendiri.
