# Pilot W2b-3 (`success_rate_all`): hasil

2026-10-23, job `j20261023_104529_ca7d`, DeepSeek V4.1 Flash thinking, `--no-reference`. Kriteria:
`PREFLIGHT.md` (ditulis sebelum run). Artefak: `live/`.

## Hasil: gagal (kriteria 3), karena tes draf yang rusak lolos baseline

| Tahap | Hasil | Biaya | Waktu |
|---|---|---|---|
| Drafter | `DRAFTED`, 2 submit (submit 1: "changed_tests has duplicate paths", karena model mengirim file yang sama dua kali, salah satunya kosong) | $0,0143 | 10:46 → 10:48 |
| Approve | Atha, dengan rekomendasi Claude | – | 10:52 |
| Agen | `FAILED_ACCEPTANCE` (stagnant, 2 attempt) | $0,0212 | 10:52 → 10:57 |
| **Job** | **AGENT_FAILED** | **$0,0355** dari cap $1,00 | 12 menit |

Keputusan Atha: 2 perintah live (`code`, `approve`).

## Yang berjalan benar

- **W2a-ext bekerja seperti yang dirancang.** Drafter memakai `changed_tests` untuk `tests/test_pilot_report.py`: helper
  `expected()` mendapat key baru (peringatan K3 "module-level code" muncul, dan relevan), 4 tes hanya ditambah assert, tidak
  ada tes yang hilang, tidak ada `removed`/`modified`, dan 6 tes lama yang ekspektasinya berubah merah di baseline. Layar
  approve menyebut "changes 1 existing test file(s), 1 warning(s)". Kriteria 1 terpenuhi.
- **Patch agen benar** (`live/agent_pilot_report.diff`): `"success_rate_all": round(len(done) / total, 4) if total else
  None`, tepat setelah `success_rate`. Validasi `report` (tes lama yang diubah) dan `regression` **lulus**.
- **Harness menolak dengan benar:** kriteria yang tidak bisa dipenuhi tidak menghasilkan paket.

## Kenapa gagal

Dua dari lima tes baru drafter (`tests/test_pilot_report_all.py`) memakai `runs["f5c"]` dan `runs["f6a"]`. Run
tersebut hanya dibuat oleh fixture di `test_pilot_report.py`, bukan oleh `build()`. Akibatnya kedua tes gagal karena
**`KeyError: 'f6a'`, bukan karena assertion**, dan akan tetap gagal apa pun patch-nya. Task ini `unproven`, dan di sini
kriterianya memang mustahil dipenuhi.

Kenapa lolos baseline: W2a hanya membedakan FAIL dari ERROR. Pengecualian apa pun di dalam tubuh tes (KeyError,
TypeError) dilaporkan pytest sebagai FAILED, sehingga dianggap "merah karena assertion". Ini celah W2a yang sudah ada
sejak awal dan baru terlihat sekarang.

**Kesalahan Claude:** `DRAFT_REVIEW.md` sebenarnya sudah menampilkan `KeyError: 'f6a'` di bagian "Why they fail now".
Ringkasan Claude untuk Atha tidak menyebutnya dan malah merekomendasikan approve. Manusia diminta membaca alasan merah
itu, dan pembaca yang ditugasi (Claude) melewatkannya.

## Usulan (belum dikerjakan; butuh keputusan)

1. **Merah harus benar-benar karena assertion** (harness, W2a): untuk tiap node wajib yang FAIL di baseline, baca baris
   `E   ...` pertama di bagian tracebacknya (`--tb=short`). Hanya `assert ...`, `AssertionError`, atau `Failed: DID NOT
   RAISE` yang diterima. Pengecualian lain menolak draf sambil menyebut nama node dan jenis errornya, dan drafter
   mendapat petunjuk perbaikan. Ini akan menolak draf pilot ini di submit 2.
2. **Ringkasan approve dari Claude** selalu mengutip baris "Why they fail now" apa adanya.
3. Coba ulang W2b-3 (job baru atau `redraft`) setelah perbaikan 1.

## Run 2 (setelah PR #179, red by assertion): diblok setup

Job `j20261023_125659_6528`, issue yang sama.

- **Drafter:** `DRAFTED`, 2 submit, $0,0156. Submit 1 kembali ditolak "duplicate paths", karena model lagi-lagi
  mengirim entri kosong untuk file yang sama. Pengecekan merah yang baru bekerja: ke-10 tes wajib gagal karena
  `AssertionError` dari file tesnya sendiri. Diff tes lama bersih, dengan 3 `modified` beserta alasannya. Diapprove Atha.
- **Agen:** `BLOCKED` di setup, $0. Scope draf berisi glob protected `"tests"`, yaitu nama folder, padahal glob hanya
  mencocokkan file. Setup menolaknya ("protected glob 'tests' matches no input file"), tapi cek draf tidak menjalankan
  pengecekan yang sama, jadi draf itu lolos cek dan approve. Job: $0,0156.
- **Perbaikan** (PR berikutnya): semua cek kontrak yang dijalankan setup sebelum agen (scope terhadap file, profil
  budget, environment sandbox) dijadikan satu fungsi, `ct.setup_problems`. Fungsi itu dipanggil setup dan juga `check()`
  W2a terhadap baseline task. Glob folder ditolak dengan petunjuk "use 'tests/**'", tidak diubah diam-diam. Prompt
  drafter juga mendapat contoh glob yang benar.
- Run berikutnya: job baru setelah merge, menunggu "y" dari Atha.
