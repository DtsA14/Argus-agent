# Spek: `argus approve` menolak draf dengan penanda konflik tes lama

Status: **keputusan Atha 2026-10-31: K1-K3 ya**; merge didelegasikan ke Claude. Jalur ketat (approve = keputusan manusia + uang
agen). Satu PR kecil. Lanjutan SPEC_VITEST_FULL_REGRESSION (#273) dan shadow batch 2 (`PENDING.md`).

## 1. Masalah

Sejak #273 drafter vitest menulis `EXISTING TEST CONFLICT: <file>::<test>` di awal `unverifiable` bila issue mengubah
perilaku yang dicek tes lama (yang tidak bisa diubah lewat draf). Harness tidak membacanya: `argus approve` tetap menjalankan
agen. Bukti shadow batch 2:

- `j20261031_083121_1808`: drafter menandai dua konflik yang benar; approve buta; agen membuat setiap sel tabel total
  `<th scope="row">` agar tes lama yang dilindungi tetap hijau (semantik tabel salah). Blok Claude, $0.0382 terbuang.
- `j20261031_093043_3f45`: konflik yang benar; skrip shadow Claude berhenti sebelum approve ($0.0245, hanya draf). Gerbang ini
  hanya ada di skrip itu (`~/argus-viewer-issues/SHADOW.md`), bukan di harness.

Penanda itu sendiri bekerja (2 dari 2 benar). Yang kurang: tidak ada yang bertindak atasnya.

## 2. Usul

**C1. Tempat: approve, bukan cek draf.** `router/job.py` `approve()` menolak, sesudah cek sha dan sebelum apa pun yang
lain (web, cap, BLOCKED, konfirmasi, stage agen), bila satu entri `unverifiable` draf yang disetujui berisi teks
`EXISTING TEST CONFLICT` (substring, peka huruf besar). Pesan: `job <id>: the draft flags a conflict with an existing test
(<entri, dipotong 300>); change that test by a commit of yours, then abandon this job and start a new one; nothing was
approved`. State job tidak berubah (tetap AWAITING_APPROVAL / DRAFT_FAILED), tidak ada stage, tidak ada panggilan model,
tidak ada entri log keputusan.
Cek draf (`acceptance/draft.py`) **tidak** menolaknya: penolakan di sana menjadi umpan balik drafter, dan drafter akan belajar
menghapus penanda agar lolos.

**C2. Layar.** `argus status` menampilkan setiap entri berpenanda sebagai baris sendiri `conflict: <entri>` (sebelum baris
draf), agar manusia melihatnya tanpa membuka `DRAFT_REVIEW.md`. Layar konfirmasi approve tidak pernah muncul untuk draf
seperti itu (C1 menolak lebih dulu); pesan penolakan menyebut entri pertama.

**C3. Semua environment.** Prompt yang menulis penanda hanya prompt vitest, tetapi gerbang membaca draf apa pun (Python juga):
teks itu tidak muncul tanpa sengaja, dan fail closed lebih murah daripada pengecualian.

**C4. Tanpa jalan pintas (K1).** Tidak ada `--conflict-ok`. Konflik yang benar diselesaikan dengan commit manusia pada tes
lama, lalu job baru (redraft memakai commit yang sama, jadi tidak menolong). Penanda yang salah: abandon + job baru juga
(drafter berikutnya bisa tidak menandai). Data batch 2: 2 dari 2 penanda benar.

**Tidak dikerjakan:** cek mekanis apakah konfliknya nyata (menjalankan tes lama terhadap sesuatu); override; gerbang di
cek draf.

## 3. Jaminan dan tes (`tests/test_conflict_gate.py`, tanpa sandbox)

- **G1.** Draf berpenanda: `approve` dengan sha yang benar menolak; job tetap AWAITING_APPROVAL; tidak ada stage `a1`, tidak
  ada `llm_call_started` dari agen, model coder tidak dipanggil.
- **G2.** Penanda di entri mana pun (bukan hanya yang pertama, bukan hanya di awal entri) menolak.
- **G3.** Penolakan datang sebelum cek cap: job dengan sisa cap terlalu kecil tetap AWAITING_APPROVAL (tidak dipindah ke
  BLOCKED) bila drafnya berpenanda; dan sebelum konfirmasi (tidak ada prompt `[y/N]`).
- **G4.** Draf DRAFT_FAILED yang draf terakhirnya diterima dan berpenanda juga ditolak.
- **G5.** `status` menampilkan `conflict: ...` untuk tiap entri berpenanda (dan pesan penolakan menyebut entri pertama);
  tidak ada baris itu tanpa penanda.
- **G6.** Tanpa penanda approve berjalan seperti sebelumnya (tes approve yang ada tetap hijau).
- **G7.** Draf Python berpenanda juga ditolak (C3).

Mutants (`verification/conflict_gate_mutants.py`): gerbang dihapus; hanya entri pertama dibaca; gerbang sesudah cek cap; tidak
dicek untuk DRAFT_FAILED; baris `conflict:` tidak ditampilkan. Lalu review medium, verify.sh, "merge".

**Code review (medium, 2026-10-31), semua diperbaiki:** penanda dibaca tanpa peka huruf besar dan dengan pemisah apa pun
(`acceptance/draft.py` `CONFLICT_RE`, fail closed); `dr.approve` juga menolak (jalur kedua `scripts/approve_draft.py
--approve`); `argus retry` menolak job yang draf disetujuinya berpenanda (disetujui sebelum gerbang); pesan menyebut juga
environment (tes lama yang butuh network); entri diambil langsung, bukan dari potongan baris status; tes urutan terhadap cek
web, ledger/run dan log keputusan tidak berubah; mutan dihitung killed hanya bila tes gerbang FAILED tanpa error.
`argus resume` tidak dicek: ia melanjutkan stage yang sudah berjalan dari keputusan yang sudah dibuat.

## 4. Sesudah merge

Skrip shadow Claude memakai `argus approve` apa adanya (gerbangnya sendiri dihapus, agar yang diukur adalah harness).

## 5. Keputusan untuk Atha

- **K1.** Tanpa `--conflict-ok` (C4). Usul: ya; ditambah hanya bila ada penanda salah yang terbukti.
- **K2.** Berlaku untuk semua environment (C3). Usul: ya.
- **K3.** Gerbang di approve, bukan di cek draf (C1). Usul: ya.
