# Pilot SWE v0 batch 1: hasil

2026-10-24, lima instance sympy SWE-bench Verified, DeepSeek V4.1 Flash thinking, `--no-reference`, environment `sympy` (image
`sha256:de306e046ab6…`, dipin per job), dari VM dengan `--key-file`/`--yes`. Kriteria: `PREFLIGHT.md` (ditulis sebelum run).
Per instance: `<instance>/grade.json` (penilaian) dan `<instance>/live/` (job, draf, paket review, tes drafter di atas patch resmi).

## Hasil: 5/5 `resolved` (4 instance + 1 dengan petunjuk perbaikan di issue)

| Instance | Drafter | Agen | `swe_grade.py` | Biaya job | Patch agen vs maintainer |
|---|---|---|---|---|---|
| `22714` geometry | 1 submit, $0,0153 | 1 attempt, 3 langkah, $0,0077 | **resolved** (1/1, 11/11) | $0,0230 | **berbeda, setara**: `a.is_extended_real is False` vs `im(a).is_zero is False` |
| `23950` sets | 2 submit, $0,0298 | 1 attempt, 4 langkah, $0,0074 | **resolved** (1/1, 4/4) | $0,0372 | sama (`return self.args[1]`), plus docstring |
| `24213` physics.units | 4 submit, $0,0360 | 1 attempt, $0,0027 | **resolved** (1/1, 31/31) | $0,0388 | identik (`equivalent_dims`) |
| `24539` polys | 2 submit, $0,0172 | 1 attempt, 7 langkah, $0,0059 | **resolved** (1/1, 62/62) | $0,0231 | hampir identik (beda huruf besar di pesan error) |
| **4 instance** | | | **4/4** | **$0,1221** | 1 berbeda, 3 sama |
| `22914` printing ⚠ | 4 submit, $0,0086 | 1 attempt, 9 langkah, $0,0071 | **resolved** (1/1, 17/17) | $0,0157 | **berbeda**: agen memakai usulan kode issue (`_print_Min`/`_print_Max`), maintainer mendaftarkan `'Min': 'min'` di tabel fungsi |
| **Batch** | | | **5/5** | **$0,1378** (ledger) | |

`22914` dilaporkan terpisah (review Atha): issue-nya sendiri memuat usulan kode perbaikan, jadi hasilnya tidak sebanding dengan
empat lainnya.

**Klaim (batas dari preflight):** harness Argus menyelesaikan lima task SWE-bench sympy dari ujung ke ujung, dinilai ala SWE-bench
(Python 3.12, penilai milik Argus) dengan tes resmi yang tidak terlihat oleh drafter maupun agen. **Bukan** tingkat sukses model
dan tidak dibandingkan dengan leaderboard: instance publik 2021–2023, dan tiga dari lima patch agen sama dengan patch maintainer
(kontaminasi mungkin). Dua patch yang berbeda (`22714`, `22914`) menunjukkan bahwa setidaknya di sana agen tidak sekadar mengulang
patch maintainer, tapi lima task tetap bukan tingkat sukses umum.

## Aturan pemilihan (review Atha)

Dari 13 kandidat (versi 1.9–1.12, dari 43 instance sympy kecil), **10 layak** dan **3 ditolak** (`21847`, `21612`, `21379`, sympy
1.9: `import distutils` tidak ada di Python 3.12). Dari yang 10, dipilih **satu per modul**, urutan daftar kandidat: geometry, sets,
physics.units, printing, polys. **Lima yang layak tetapi tidak dipilih:** `24562` (core/numbers), `24066` (physics.units, modul sudah
diwakili `24213`), `23824` (physics.hep), `22456` (codegen), `23262` (utilities/lambdify). Kelimanya bisa dijalankan sebagai
batch 2 dengan preflight yang sama, sehingga angka di atas tidak bergantung pada pilihan tangan.

## Tes drafter

- Lima draf, semua tes **di berkas baru**; satu draf (`23950`) juga mengubah tes lama lewat `changed_tests`
  (`test_contains.py::test_as_set`, yang dulu mengunci `NotImplementedError`; berkas itu juga disentuh `test_patch`, dan penilai
  mengembalikannya ke base lebih dulu).
- **Tes drafter di atas patch resmi maintainer: hijau di kelima instance** (dijalankan di sandbox sebelum approve, dan dicatat ulang
  oleh penilai, `drafter_tests_on_reference: pass`). Jadi tes drafter menguji perilaku yang sama dengan tes resmi, tidak mengunci
  cara memperbaiki yang berbeda dari maintainer.
- Draf dengan tes negatif yang hijau di baseline: `24213` (dimensi yang memang tidak cocok tetap `ValueError`), `24539` (simbol
  bawaan dan jumlah simbol yang salah).
- Submit yang ditolak harness: 8 dari 13 (`23950` 1, `24213` 3, `22914` 3, `24539` 1; `22714` lolos di submit pertama). Alasannya ada
  di `events.jsonl` masing-masing run drafter.
- `22914`: di `base_commit`, `pycode(Min)` sudah menghasilkan ekspresi `if/else` (bukan "Not supported" seperti di issue). Drafter
  menulis tes terhadap perilaku yang ia amati di kode, bukan terhadap teks issue.

## Supervisi

- **Keputusan Atha untuk run: 6**. Satu "go live" untuk kelima tahap `code` (mencakup job `9b1c`, `0c81`, `e451`, `872b`, `6482`),
  dan lima "y" untuk approve, satu per draf. Tidak ada retry.
- **Waktu dari ringkasan draf dikirim sampai "y" diterima** (`review_times.txt`): 45, 38, 39, 107, dan 58 detik. Median 45 detik.
  Ini batas bawah waktu baca Atha (mencakup membuka chat). Ringkasan memakai format tetap: kutipan "Why they fail now", writable,
  satu kalimat penilaian, dan hasil tes drafter di atas patch resmi.
- Waktu mesin: tahap `code` 17:42–17:53 (berurutan), agen berjalan paralel dengan drafter berikutnya; seluruh batch dari job
  pertama sampai `REVIEW_READY` terakhir ±15 menit.
- **Cap batch $3,00** diperiksa Claude dari ledger (`spent_nano`, kasus terburuk untuk panggilan terputus) sebelum setiap tahap
  live (`spent.py`, `run_code.log`): tidak pernah mendekat; maksimum $0,1248 + $0,75 sebelum approve terakhir.

## Catatan

- **Skrip cek tes drafter (sisi Claude) sempat salah**: direktori sementara 0700 tidak terbaca oleh sandbox (`nobody`), dan hasilnya
  "no pytest summary". Ditemukan di draf pertama, diperbaiki (`chmod 755`), dijalankan ulang sebelum ringkasan dikirim.
  `swe_grade.py` tidak terkena (yang di-mount subdirektori biasa).
- Satu "y" Atha datang saat dua draf menunggu; ditafsirkan untuk draf yang ringkasannya dikirim lebih dulu (`22914`), lalu ringkasan
  `24539` dikirim dan disetujui terpisah.
- Tidak ada patch yang diterapkan ke sympy atau di-push ke mana pun.
