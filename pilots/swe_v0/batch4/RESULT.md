# Pilot SWE v0 batch 4: hasil

2026-10-28, lima instance sympy SWE-bench Verified di environment **`sympy`** (Python 3.12, image `sha256:de306e046ab6…` dipin per
job), DeepSeek V4.1 Flash thinking, `--no-reference`. Harness `main` `e640143` (kode sama dengan `235c3ab`; selisihnya hanya
`PENDING.md` dan `PREFLIGHT.md`), **tidak diubah selama batch**. Kriteria: `PREFLIGHT.md` (ditulis sebelum run).

**Tanpa bocoran jawaban:** approve hanya dari isi draf; tes drafter di atas patch maintainer baru dijalankan setelah grading (lihat
catatan di 22456 tentang alasan reviewer).

## Hasil: 3/5 `resolved` (3/4 tanpa yang harness-blocked)

| Instance | Drafter | Agen | `swe_grade.py` | Biaya job |
|---|---|---|---|---|
| `24562` core/numbers | `d1` DRAFTED, 2 submit, $0,0749 | `a1` dan `retry` `a2` gagal (4 attempt, semuanya `max_steps` 12 langkah), **tidak satu pun menulis berkas**, $0,0252 + $0,0196 | – (tidak ada paket review) | $0,1197 |
| `24066` physics/units | `d1` DRAFTED, 1 submit, $0,0526 | `a1` `DONE`, 1 attempt (3 langkah), $0,0026 | **resolved** (1/1, 30/30) | $0,0552 |
| `23824` physics/hep | **BLOCKED** sebelum panggilan model: issue 2.103 karakter, batas harness 2.000 | – | **harness-blocked** | $0,0000 |
| `22456` codegen | `d1` DRAFTED, 3 submit, $0,0716, **ditahan** reviewer; redraft polos `d2` DRAFTED, 1 submit, $0,0647 | `a1` gagal (`context_limit` sesudah menulis, lalu `context_limit` tanpa menulis), $0,0277; `retry` `a2` `DONE` (6 langkah), $0,0222 | **resolved** (1/1, 29/29) | $0,1861 |
| `23262` utilities/lambdify | `d1` DRAFTED, 3 submit, $0,0574 | `a1` `DONE`, 1 attempt (5 langkah), $0,0075 | **resolved** (1/1, 61/61) | $0,0649 |
| **Batch** | | | **3/5** (3/4) | **$0,4260** (ledger) |

Kolom *harness-blocked* dipisah dari unresolved biasa (Atha): `23824` tidak pernah sampai ke model, jadi tidak mengukur drafter
maupun agen. Angka resmi batch tetap 3/5; 3/4 dilaporkan berdampingan, bukan sebagai pengganti.

**Klaim:** harness Argus menyelesaikan 3 dari 5 task SWE-bench sympy tanpa bocoran jawaban (3 dari 4 yang bisa dijalankan), dinilai
ala SWE-bench (Python 3.12, penilai milik Argus). Bukan tingkat sukses model; tidak dibandingkan dengan leaderboard: instance publik
2021–2023. Dibandingkan dengan batch 3 (3/4): setara, dengan batch yang lebih besar dan aturan tanpa perbaikan di tengah.

## Tes drafter di atas patch maintainer (dibuka setelah grading)

| Instance | Tes draf yang di-approve di atas patch maintainer |
|---|---|
| `24066` | hijau (3/3) |
| `23262` | **1 dari 6 gagal** (tes yang mana tidak tercatat di `grade.json`, hanya jumlahnya) |
| `22456` (`d2`) | **1 dari 4 gagal** (sama: hanya jumlahnya) |

Dua dari tiga draf yang di-approve memuat satu tes yang lebih ketat dari, atau berbeda tafsir dengan, fix maintainer. Keduanya tetap
`resolved` (tes resmi lulus), jadi tidak menyebabkan kegagalan. Di `22456` kandidat yang paling mungkin adalah
`test_String_args_hold_the_text` (`String('foobar').args == ('foobar',)`), yang sudah ditandai di ringkasan approve sebagai
"mendikte bentuk implementasi". Ini belum diverifikasi: `swe_grade.py` tidak mencatat nama tes yang gagal di atas patch maintainer.
Itu celah pencatatan, kandidat spek.

## Patch agen (berkas yang disentuh, sempit atau tidak)

- `24066`: hanya `sympy/physics/units/unitsystem.py` (= writable, = rencana draf). Sempit: di cabang `Function` dari
  `_collect_factor_and_dimension`, dimensi argumen yang `is_dimensionless` dipetakan ke `Dimension(1)`. Tidak ada exception yang
  ditelan.
- `23262`: hanya `sympy/utilities/lambdify.py` (= writable). Sempit: di `_recursive_to_string`, tuple satu elemen diberi koma di
  belakang. Tidak menyentuh printer.
- `22456`: hanya `sympy/codegen/ast.py` (= writable). `not_in_args = ['text']` dihapus dan `is_Atom = True` dipertahankan, ditambah
  tiga override di `String`: `free_symbols` (selalu `set()`), `match`, dan `matches` (keduanya direduksi ke uji kesamaan). Override
  `match`/`matches` **lebih luas dari issue**: dipakai untuk menahan mesin pattern-matching `Basic` yang tidak tahan argumen `str`.
  Tidak menelan error, tapi mengubah perilaku pencocokan pola untuk semua `String`. Lulus 29/29 `PASS_TO_PASS`.

## Review draf (supervisi)

- Approve d1 `24562`, `24066`, `23262` dan "ok" untuk `23824` BLOCKED dalam satu balasan, ±7 menit setelah kelima ringkasan dikirim
  bersama (pertama kali dikirim sebagai satu pesan, atas permintaan Atha).
- `22456` `d1` **ditahan**: `test_cnodes.py::test_sizeof` diubah (`atoms()` → `atoms(String)`), dan `test_cnodes` tidak punya tes
  wajib, jadi tes lama dilonggarkan sekaligus tidak dijaga. Alasan itu berdiri dari isi draf saja. **Catatan kejujuran:** balasan
  reviewer juga menyebut dugaan tentang fix upstream ("setahuku fix upstream memang begitu"). Dugaan itu **tidak** diteruskan ke
  drafter: redraft dijalankan polos, tanpa `--note` (pilihan a dari tiga opsi; `--note` akan menandai job *human-steered*).
- `22456` `d2`: tidak mengubah tes lama, regresi `test_ast.py` penuh (31 wajib), tapi `test_cnodes.py` tidak ada di validasi sama
  sekali. Di-approve.
- Waktu: `review_times.txt`.

**Keputusan Atha untuk run:** "go live" (semua tahap), "y" ×3 + "ok" (satu balasan), tahan `22456` d1, "a" (redraft polos), "y"
`22456` d2 = **5 balasan**. Redraft `22456`, retry `24562`, dan retry `22456` tercakup izin di muka (preflight 3.2), tanpa balasan
tambahan. Batch 3 butuh 7 keputusan untuk 4 instance.

## Yang dipelajari (bahan spek sesudah batch; harness tidak diubah selama batch)

1. **`max_steps` tanpa menulis** (`24562`, sama dengan `21379` di batch 3): empat attempt × 12 langkah, nol berkas. Retry dengan carry
   yang ada tidak membantu. Sekarang 2 dari 9 instance tanpa bocoran gagal dengan pola ini, jadi kandidat spek nomor satu.
2. **Batas issue 2.000 karakter** (`23824`): instance ditolak sebelum model dipanggil. Batas ini perlu dinaikkan, atau issue yang
   panjang perlu cara lain (spek).
3. **`context_limit` sesudah menulis** (`22456` `a1` attempt 1), lalu attempt 2 juga `context_limit` tanpa menulis. Retry selesai.
4. **Drafter bisa melonggarkan tes lama yang tidak ia jadikan wajib** (`22456` `d1`). Harness memeriksa bahwa tes lama tidak hilang
   atau di-skip, tapi tidak mewajibkan tes lama yang **diubah** masuk ke `must_pass`. Kandidat spek: tes lama yang diubah otomatis
   wajib.
5. **`swe_grade.py` tidak mencatat nama tes drafter yang gagal di atas patch maintainer**, hanya jumlahnya.
6. **Blok "Why they fail now" bisa tidak memuat semua tes merah** (`22456` `d2`: 4 gagal, 3 tampil). Reviewer melihat lebih sedikit
   dari yang diwajibkan.

## Bukti

Per instance: `issue.txt`, `grade.json` (bila dinilai), `live/` (job, draf, `DRAFT_REVIEW_*`, `result_*`, patch dan PR bila ada, log
setiap tahap, ringkasan draf yang dikirim). Skrip dan log batch: `run_code.*`, `run_approve.*`, `run_redraft.*`, `spent.py`,
`draft_summary.py`. Grading dijalankan dua kali untuk `24066` dan `23262`: yang pertama ditolak `swe_grade.py` karena path patch
relatif (kesalahan perintah Claude, tidak ada hasil yang dibaca), yang kedua dengan path absolut.
