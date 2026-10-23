# Pilot W2b-3 (`success_rate_all`): preflight (ditulis sebelum run)

Status 2026-10-23: **persiapan; belum ada run.** Ini pilot pertama W2a-ext (`changed_tests`, PR #176), sesuai spek
`docs/reviews/SPEC_W2A_EXT_CHANGED_TESTS.md` bagian 8. Issue ditulis Claude.

## 1. Tujuan

Task yang **mengubah perilaku yang sudah dikunci tes lama**. `tests/test_pilot_report.py` membandingkan seluruh laporan
secara persis, jadi menambah satu key pasti membuat tes itu gagal. Sebelum W2a-ext, task seperti ini tidak bisa
diekspresikan. Yang diukur:
- apakah drafter memakai `changed_tests` dengan benar: tes lama diperbarui lewat `changed_tests`, tidak ada tes yang
  hilang, tidak ada fungsi tes yang diubah diam-diam, dan tidak ada skip;
- apakah peringatan K3 membantu atau malah mengganggu;
- jumlah keputusan Atha dan biaya job.

## 2. Task

`pilots/m6_w2b/w2b3/issue.txt`: tambah `success_rate_all = done / runs_total` di samping `success_rate` (butir PENDING
sejak review 3b). Yang kemungkinan akan dilakukan drafter:
- mengubah `tests/test_pilot_report.py` lewat `changed_tests`. Fungsi `expected(...)` di file itu adalah helper tingkat
  modul, jadi perubahannya hanya memicu peringatan K3. Tes yang membandingkan laporan menjadi merah karena laporan
  belum punya key baru;
- kemungkinan juga menambah satu file tes baru, karena `new_tests` wajib berisi minimal satu file.

Risiko yang sudah diketahui: `test_pilot_report.py` membangun run sintetis lewat `tests/test_run_inspectors.py`. Belum
pasti apakah itu bisa jalan di sandbox. Kalau tidak bisa, drafter seharusnya menyadarinya dari baseline.

## 3. Cara jalan (Atha, di VM, checkout live di `main` setelah PR #176)

Drafter dan coder memakai DeepSeek thinking (bawaan `config.yaml`).
```bash
cd ~/pilot3a_live && git pull && ~/Argus-agent/.venv-verify/bin/python scripts/argus.py code --repo ~/pilot3a_live --commit HEAD --issue-file pilots/m6_w2b/w2b3/issue.txt --exclude verification --exclude pilots
```
Setelah drafter selesai, Claude membaca `DRAFT_REVIEW.md`: diff tes yang diubah, `removed`/`modified`, dan peringatan
K3. Ringkasannya diberikan ke Atha. Bila Atha setuju:
```bash
~/Argus-agent/.venv-verify/bin/python scripts/argus.py approve <job> --sha <12 karakter>
```
Layar approve sekarang juga menyebut "changes N existing test file(s), M warning(s)".

## 4. Ekspektasi (sebelum run)

- **Drafter:** ±$0,03–0,15, 1–4 submit. Penolakan yang mungkin: node lama hilang, fungsi tes non-wajib yang berubah
  tanpa `modified`, atau tes lama yang dijadikan wajib padahal masih hijau.
- **Agen:** satu baris di `pilot_report.py`. ±$0,01–0,05, 1 attempt.
- **Job:** ±$0,05–0,25 dari cap $1,00.

## 5. Kriteria (ditetapkan sebelum run, tidak diubah sesudahnya)

1. **Drafter:** `DRAFTED` dalam ≤ 5 submit, dan draf memuat `changed_tests` untuk `tests/test_pilot_report.py`. Draf yang
   lolos tanpa mengubah tes lama, misalnya dengan membuang tes itu dari validasi, dicatat sebagai **gagal mengekspresikan
   task** dan tidak di-approve.
2. **Approve** adalah keputusan Atha setelah membaca diff (boleh menolak; itu hasil yang sah).
3. **Berhasil** bila agen `DONE`, paket valid (PR.md menandai `tests/test_pilot_report.py` sebagai "changed test,
   approved with the task"), patch plus tes yang diubah diterapkan ke `main` tanpa perubahan, `verify.sh` lulus, dan
   biaya job ≤ $1,00. Selain itu: gagal, dicatat, berhenti.
4. **Dicatat:** keputusan Atha (dari log `job.json`), biaya dan waktu per tahap, submit beserta alasan penolakannya, isi
   `removed`/`modified`, peringatan K3 dan apakah ada gunanya, menit Atha (opsional), serta kendala W2a-ext atau router.
