# Pilot SWE v0 (`sympy__sympy-23534`): hasil

2026-10-24, job `j20261024_140954_dfb0`, DeepSeek V4.1 Flash thinking, `--no-reference`, environment `sympy` (image
`sha256:de306e046ab6…`, rootfs `5b2123cd…`, dipin di `job.json`), dari VM dengan `--key-file`/`--yes`. Kriteria:
`PREFLIGHT.md` (ditulis sebelum run). Artefak: `live/`, penilaian: `grade.json`.

> **Oracle-informed** (review Atha 2026-10-27): tes drafter dijalankan di atas patch resmi sebelum approve dan hasilnya (4/4)
> ditampilkan di ringkasan.

## Hasil: berhasil (kriteria 3), `resolved: true`

| Tahap | Hasil | Biaya | Waktu (UTC) |
|---|---|---|---|
| Intake | `~/swe/sympy` di `832c24fec104`, 1.968 berkas | – | 14:09:54 |
| Drafter | `DRAFTED`, 1 submit, 10 panggilan | $0,0149 | 14:09:55 → 14:11:16 |
| Approve | Atha ("y", setelah ringkasan Claude) | – | 14:14:29 |
| Agen | `DONE`, 1 attempt, 3 langkah, 4 panggilan | $0,0054 | 14:14:41 → 14:15:18 |
| Penilai | `swe_grade.py`: **`resolved: true`**, `FAIL_TO_PASS` 1/1, `PASS_TO_PASS` 11/11 | – | 14:16 |
| **Job** | **REVIEW_READY**, dinilai resolved | **$0,0202** dari cap $1,00 | ±6 menit |

**Klaim (batas dari preflight):** harness Argus menyelesaikan satu task SWE-bench dari ujung ke ujung di repositori
asing: intake, environment sandbox sendiri, drafter, approve manusia, agen, paket review, dan penilaian ala SWE-bench
dengan tes resmi yang tidak terlihat oleh drafter maupun agen. **Bukan** klaim bahwa model memperbaiki bug yang belum
pernah ia lihat, dan tidak dibandingkan dengan leaderboard (Python 3.12, penilai milik Argus).

## Yang terjadi

- **Drafter** (1 submit): writable hanya `sympy/core/symbol.py`; tes baru di berkas **baru**
  `sympy/core/tests/test_symbols_cls.py` (tidak lewat `changed_tests`, jadi tidak menyentuh berkas yang diubah
  `test_patch`). Empat tes perilaku (`isinstance(..., UndefinedFunction)`, nama, bentuk tuple/list): kasus issue
  `symbols(('q:2','u:2'), cls=Function)`, tuple nama, `cls=Dummy` dengan tuple range, dan input list. Keempatnya merah
  karena assertion di baseline. Regresi: `test_symbol.py` + `test_var.py` (`test_symbols`, `test_var`, `test_var_cls`).
  Rencananya menyebut penyebabnya dengan tepat (`cls` keyword-only, tidak diteruskan pada rekursi cabang non-string).
- **Sebelum approve** (tanpa biaya model): tes drafter dijalankan di sandbox `sympy` di atas `base_commit` + patch resmi
  → 4/4 lulus. Jadi tesnya menguji perilaku, bukan cara memperbaiki tertentu. Penilai mencatat hal yang sama
  (`drafter_tests_on_reference: pass`).
- **Agen**: satu baris, `symbols(name, cls=cls, **args)`, **identik** dengan patch resmi maintainer. 3 langkah, $0,0054.
- **Penilai** (setelah #195): sha `changes.patch` `7a44a85f…` = yang dicetak `status` = `provenance.json`. Tree
  `base_commit`, lalu `changes.patch`, lalu `test_symbol.py` dikembalikan ke base dan `test_patch` resmi diterapkan; 13
  tes jalan di image yang dipin.

## Catatan

- **Kontaminasi.** Patch agen identik dengan patch maintainer. Itu konsisten dengan dua penjelasan yang tidak bisa
  dipisahkan dari satu run: perbaikannya memang satu baris yang jelas dari issue, atau model pernah melihat perbaikan
  ini (issue publik 2022, instance SWE-bench Verified). Karena itu hasil ini tidak dipakai sebagai ukuran kemampuan
  model.
- **Layar batas drafter tidak menyebut environment.** Atha meminta environment diperiksa di layar `argus code` sebelum
  run. Layar tahap drafter hanya menyebut model, cap, dan overrides; environment dan id image baru tampil di `status`
  dan layar approve. Pin-nya benar (`job.json`: `sympy`, `sha256:de306e046ab6…`), tapi pemeriksaan sebelum run tidak
  bisa dilakukan dari layar itu. Usul: satu baris `environment sympy, image …` di layar tahap drafter.
- **`.sandbox_image_sympy` harus ada di checkout yang menjalankan `argus`** (`~/pilot3a_live`). Awalnya hanya ada di
  `~/Argus-agent`, dan job akan ditolak sebelum intake (gagal tertutup, K4). Disalin sebelum run.
- Patch tidak diterapkan ke sympy dan tidak di-push ke mana pun (kriteria 5).

## Supervisi

Keputusan Atha untuk run: "merge, go live" (`code`) dan "y" (`approve`) = **2**, plus review spek #192, kode #193,
penilai #195, dan preflight #194. Waktu mesin ±3 menit; jeda review draf (ringkasan Claude, cek tes drafter di atas
patch resmi, lalu Atha) ±3 menit. Menit Atha: belum ditanyakan.
