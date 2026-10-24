# Router pilot #3 (`intake_repo --check` task record): preflight (ditulis sebelum run)

Status 2026-10-24: **persiapan; belum ada run.** Pilot pertama yang dijalankan dari VM tanpa terminal (`--key-file`,
`--yes`, PR #183) dan pertama dengan log waktu keputusan (PR #185). Issue ditulis Claude.

## 1. Tujuan

- **Alur dari VM:** `argus code` dan `argus approve` dijalankan sesi Claude dengan `--key-file ~/.config/argus/deepseek_key
  --yes`, setelah Atha menulis "go live" (atau "y") di chat untuk perintah itu. Isi file key tidak pernah dibaca atau
  ditampilkan oleh Claude.
- **Ukuran supervisi:** jumlah keputusan Atha dan waktunya, dari log `job.json` (`limits_shown`, `confirmed_by_flag`,
  `key_from_file`, `approved`) ditambah keputusan di chat (go live, approve, merge). Target spek router v0: dari ±17
  menjadi sekitar 4.
- **Task berguna:** butir PENDING sejak pilot 1 (`intake_repo.py --check <task> --repo` memberi mismatch palsu).

## 2. Task

`pilots/router_v0/p3/issue.txt`. Untuk record task (`"kind": "task"`), `check_against_repo` harus membandingkan workspace
dengan tree commit **ditambah** tes yang disetujui (`added`, dan `changed[...].after`), sambil tetap melaporkan perbedaan
lain. Record intake biasa tidak berubah.

Bug sudah direproduksi di `main` `5d49cf4` dengan skrip kecil (repo git sementara, intake, workspace task = snapshot +
`tests/test_x.py`, record `kind: task` dengan `added` yang benar): record intake → `[]`, record task yang persis seperti
disetujui → `["the snapshot is not the commit's tree minus the exclusions"]`. (`fixtures/repos/` tidak ada di checkout,
jadi tidak bisa lewat `intake_repo.py --check` langsung.) Yang kemungkinan dilakukan drafter:
- tes baru di `tests/` yang membuat repo git kecil (seperti fixture `repo`/`root` di `tests/test_intake.py`), intake,
  lalu workspace task buatan tangan (salin snapshot + satu file tes, record `kind: task` dengan `added`); merah di
  baseline karena laporan mismatch palsu;
- tes negatif (file lain berubah, tes yang disetujui berubah isinya) yang **hijau di baseline**, jadi masuk regresi, bukan
  node wajib merah;
- writable: `acceptance/intake.py`.

Risiko yang sudah diketahui:
- drafter memakai `dr.approve` sungguhan untuk membuat record task: berat, tapi sah bila jalan di sandbox;
- tes yang hanya merah karena error (bukan assertion) ditolak oleh cek "red by assertion" (#179), seperti seharusnya;
- `acceptance/intake.py` dipakai setup dan `dr.approve`: patch yang salah bisa melemahkan cek intake. Karena itu kriteria
  3 menuntut tes negatif dan review diff sebelum patch diterapkan.

## 3. Cara jalan (sesi Claude di VM; Atha hanya menulis "go live" / "y" per perintah)

Checkout live `~/pilot3a_live` di `main` (`5d49cf4` atau lebih baru, sudah berisi #183 dan #185). Issue diambil dari
branch preflight ini, jadi `main` tidak perlu diubah dulu. DeepSeek thinking (bawaan `config.yaml`), cap job $1,00.

```bash
cd ~/pilot3a_live && git pull -q --ff-only && git -C ~/Argus-agent show origin/router-p3-preflight:pilots/router_v0/p3/issue.txt > /tmp/claude-1001/-home-ubuntu-Argus-agent/d51fc756-57c7-4728-bce1-3728a84a578f/scratchpad/p3_issue.txt
~/Argus-agent/.venv-verify/bin/python scripts/argus.py code --repo ~/pilot3a_live --commit HEAD --issue-file /tmp/claude-1001/-home-ubuntu-Argus-agent/d51fc756-57c7-4728-bce1-3728a84a578f/scratchpad/p3_issue.txt --exclude verification --exclude pilots --key-file ~/.config/argus/deepseek_key --yes
```

Setelah drafter selesai, Claude membaca `DRAFT_REVIEW.md` dan mengirim ringkasan ke Atha, dengan baris "Why they fail
now" dikutip apa adanya. Bila Atha setuju ("y" untuk approve):

```bash
~/Argus-agent/.venv-verify/bin/python scripts/argus.py approve <job> --sha <12 karakter> --key-file ~/.config/argus/deepseek_key --yes
```

Selama tahap berjalan, `verify.sh` tidak dijalankan (venv yang sama).

## 4. Ekspektasi (sebelum run)

- **Drafter:** ±$0,02–0,15, 1–4 submit.
- **Agen:** ±10–25 baris di `check_against_repo`. ±$0,01–0,08, 1–2 attempt.
- **Job:** ±$0,05–0,25 dari cap $1,00.
- **Log `job.json`:** per tahap `limits_shown`, `confirmed_by_flag`, `key_from_file`, tanpa `confirmed`/`key_typed`.

## 5. Kriteria (ditetapkan sebelum run, tidak diubah sesudahnya)

1. **Drafter:** `DRAFTED` dalam ≤ 5 submit, dengan minimal satu node wajib yang merah karena assertion pada record task
   yang benar, dan minimal satu tes yang memastikan perbedaan lain pada record task **tetap** dilaporkan. Draf tanpa tes
   negatif seperti itu tidak di-approve (patch yang selalu mengembalikan `[]` untuk task akan lolos).
2. **Approve** adalah keputusan Atha setelah membaca ringkasan (boleh menolak; itu hasil yang sah).
3. **Berhasil** bila agen `DONE`, paket valid, patch diterapkan ke branch dari `main` tanpa perubahan (sha256
   `changes.patch` sama dengan yang dicetak `status`; `apply --check` lalu `apply`), `verify.sh` lulus, review diff
   tidak menemukan pelemahan cek intake biasa, dan biaya job ≤ $1,00. Selain itu: gagal, dicatat, berhenti.
4. **Alur VM:** kedua perintah live jalan tanpa terminal. Key tidak muncul di berkas job: dijamin tes router, dan Atha
   bisa cek sendiri (Claude tidak membuka file key, juga tidak lewat `grep`):
   `! grep -rlF -f ~/.config/argus/deepseek_key ~/pilot3a_live/jobs/<job> | wc -l` → harus `0`.
5. **Dicatat:** keputusan Atha dan waktunya (log `job.json` dan chat), biaya dan waktu per tahap, submit beserta alasan
   penolakannya, apakah `status` yang baru (`why:`, `next:`, perintah apply) cukup tanpa membuka file, menit Atha
   (opsional), dan kendala router.
