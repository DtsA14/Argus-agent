# Pilot: drafter dengan validasi `old_tests_*` (SPEC_VITEST_FULL_REGRESSION amandemen 1, PENDING 3a-1)

**"Go live" Atha 2026-11-11 ("Ok langsung go live kalo plannya udah ok bro")**, sesudah PR ini merge. Claude menjalankan
langkah berurutan, satu langkah = satu perintah (atau satu cek), mencatat output di `steps.md`, dan berhenti di langkah
pertama yang tidak sesuai harapan. Tidak ada service yang di-restart: drafter berjalan sebagai CLI per job dari
`~/pilot3a_live`. Port 8000, ledger, proxy 8710 tidak disentuh; 8711 tidak memakai kode drafter.

`A = .venv-verify/bin/python scripts/argus.py` (di `~/pilot3a_live`). Job = `j20261111_073447_cc5a` (viewer, judul di
kartu beranda; d1 NO_DRAFT 5 submit habis karena formulir, $0,044; issue `j20261111_043029_53f7`).

| # | perintah / cek | harapan |
|---|---|---|
| 0 | `git -C ~/pilot3a_live log -1`, `status --short`; tidak ada job `DRAFTING`/`AGENT_RUNNING`; `$A status j20261111_073447_cc5a` | HEAD `ba5aa99` (#427) atau sesudahnya tanpa PR ini; bersih; job `DRAFT_FAILED`, spent $0,0441 dari cap $1,00 |
| 1 | `git -C ~/pilot3a_live pull --ff-only` | fast-forward ke merge PR ini |
| 2 | `$A redraft j20261111_073447_cc5a --key-file ~/.config/argus/deepseek_key --yes` (Atha "Ok redraft bro") | selesai; d2 `DRAFTED` atau `NO_DRAFT` dengan alasannya; biaya dalam cap |
| 3 | kontrak d2: validasi drafter + `old_tests_*` dari harness; jumlah submit | semua berkas tes lama tersebut sekali; dibanding d1 (5 submit habis) |

Bila d2 `DRAFTED`: Claude membaca draf (merah hanya `AssertionError`, tes sesuai contoh issue, tidak ada tes lama yang
diubah walaupun issue memuat daftar clash palsu), approve, applied, rilis viewer 042 (jalur cepat). Bila `NO_DRAFT`:
berhenti dan lapor; 3a-2 (perbaikan formulir) berikutnya.

Rollback: `git -C ~/pilot3a_live checkout <HEAD langkah 0>`; butuh "go live" sendiri.
