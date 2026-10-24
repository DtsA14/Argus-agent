# Pilot SWE v0 batch 1: lima instance sympy (preflight, ditulis sebelum run)

Status 2026-10-24: **persiapan; belum ada run.** Lanjutan `sympy__sympy-23534` (`resolved`, $0,0202). Spek, penilai, dan batas klaim
sama dengan `../sympy__sympy-23534/PREFLIGHT.md`. Persetujuan: **satu "go live" untuk kelima tahap `argus code`** (Atha 2026-10-24,
Reconciliation 2026-10-24 keputusan 1); `approve` tetap satu "y" per draf, `retry` satu "y" per job.

## 1. Tujuan dan batas klaim

Angka pertama untuk alur Argus di repo luar: berapa dari lima yang `resolved`, biaya per task yang `resolved`, apakah tes drafter
menangkap perilaku yang sama dengan tes resmi, dan jumlah keputusan Atha per task.

- "**harness Argus pada lima task SWE-bench**", **bukan** kemampuan model: instance SWE-bench Verified publik (2021–2023) dan
  kemungkinan ada di data latih. Lima task bukan tingkat sukses umum.
- "**penilaian ala SWE-bench, Python 3.12**", penilai milik Argus, **tidak** dibandingkan dengan leaderboard.

## 2. Instance (dipilih sebelum run, tidak diganti sesudahnya)

Dari 43 instance sympy kecil (satu berkas, ≤ 12 baris, 1–3 `FAIL_TO_PASS`; `pick_instances.py`), 13 kandidat versi 1.9–1.12 dicek
dengan penilai di sandbox `sympy` (`feasibility.log`): patch resmi `resolved`, patch kosong tidak, setiap nama tes ditemukan.
**10 layak; 3 ditolak** (`21847`, `21612`, `21379`, sympy 1.9: `import distutils`, yang tidak ada di Python 3.12; penilai menolak,
bukan mencatat gagal). Lima dari yang layak, satu per modul:

| Instance | Modul | Issue (singkat) | Patch resmi | `F2P` / `P2P` | SWE-bench difficulty |
|---|---|---|---|---|---|
| `sympy__sympy-22714` | `geometry/point.py` | `Point2D` gagal di dalam `evaluate(False)` | 2 baris | 1 / 11 | <15 menit |
| `sympy__sympy-23950` | `sets/contains.py` | `Contains.as_set()` mengembalikan `Contains` | 2 baris | 1 / 4 | 15 menit–1 jam |
| `sympy__sympy-24213` | `physics/units/unitsystem.py` | dimensi setara tidak dikenali pada penjumlahan | 2 baris | 1 / 31 | 15 menit–1 jam |
| `sympy__sympy-22914` | `printing/pycode.py` | `pycode` tidak mendukung `Min`/`Max` | 2 baris | 1 / 17 | 15 menit–1 jam |
| `sympy__sympy-24539` | `polys/rings.py` | `PolyElement.as_expr()` mengabaikan symbol yang diberikan | 9 baris | 1 / 62 | <15 menit |

- Issue: `<instance>/issue.txt` = `problem_statement` **apa adanya** (sama dengan `~/swe/inst/<instance>/problem_statement.txt`).
  Issue `22914` memuat usulan kodenya sendiri (`_print_Min`/`_print_Max`); itu bagian dari issue asli dan dibiarkan.
- Tes resmi dan patch maintainer ada di `~/swe/inst/`, di luar repo, job root, dan path jail; drafter dan agen tidak melihatnya.

## 3. Cara jalan (sesi Claude di VM)

Environment `sympy`, image `sha256:de306e046ab6347cbd56ffb62dd75fcf71c51999c5a5fbf60117e36bd11fe412` (dihitung dengan
`environment_pin` dari `~/pilot3a_live`, sebelum run), dipin per job. DeepSeek thinking (bawaan). Per job: cap $1,00, drafter
$0,75, agen `min(profil, sisa job)`.

Setelah "go live", untuk setiap instance berurutan (`~/pilot3a_live`, `main`):

```bash
~/Argus-agent/.venv-verify/bin/python scripts/argus.py code --repo ~/swe/sympy --commit <base_commit> \
    --issue-file ~/swe/inst/<instance>/problem_statement.txt --environment sympy \
    --key-file ~/.config/argus/deepseek_key --yes
```

Lalu ringkasan per draf (baris "Why they fail now" dikutip apa adanya; tes drafter dijalankan di atas patch resmi di sandbox
sebelum approve, tanpa biaya model), `approve` per "y", `retry` per "y" bila perlu, dan `swe_grade.py` untuk setiap
`REVIEW_READY`.

**Cap batch $3,00, diperiksa Claude, bukan harness:** sebelum setiap tahap live, jumlah biaya kelima job (ledger) ditambah cap tahap
itu harus ≤ $3,00. Bila tidak, tahap itu tidak dimulai dan dicatat.

## 4. Ekspektasi (sebelum run)

Per instance ±$0,02–0,30 (23534: $0,0202). Batch ±$0,10–1,50. Drafter mungkin membaca lebih banyak di `polys` dan `physics.units`.
Lebih dari satu instance mungkin gagal, karena sebagian berlabel 15 menit–1 jam.

## 5. Kriteria (ditetapkan sebelum run, tidak diubah sesudahnya)

1. **Per drafter:** `DRAFTED` dalam ≤ 5 submit, validasi di environment `sympy`, node wajib merah karena assertion pada perilaku
   dari issue, writable tidak lebih luas dari paket modul issue (mis. `sympy/geometry/**` untuk `22714`). Draf yang tidak
   memenuhi ini tidak di-approve (dicatat sebagai `draft_rejected`).
2. **Approve** per draf adalah keputusan Atha.
3. **Per instance berhasil** bila: agen `DONE`, paket review valid, dan **`swe_grade.py` `resolved: true`** untuk patch dengan sha
   yang dicetak `status`. Penilai yang menolak = "belum dinilai", bukan gagal.
4. **Hasil batch** dilaporkan apa adanya: `resolved` / tidak / draf ditolak / belum dinilai, per instance, dengan biaya. Tidak ada
   ambang lulus untuk batch; yang dicatat adalah angkanya.
5. **Dicatat per instance:** biaya dan waktu per tahap, submit dan penolakannya, apakah tes drafter hijau di atas patch resmi,
   apakah patch agen sama dengan patch maintainer, keputusan Atha (mana yang ditutup oleh "go live" batch).
6. Tidak ada patch yang diterapkan ke sympy atau di-push ke mana pun.
