# Pilot router v0 #1 (`argus list`): preflight (ditulis sebelum run)

Status 2026-10-23: **persiapan; belum ada run.** Router v0: `docs/reviews/SPEC_ROUTER_V0.md`, PR #163. Task dipilih
Claude atas permintaan Atha ("lu yang pilihin"); issue ditulis Claude.

## 1. Tujuan

Pilot pertama lewat **satu perintah per keputusan**: `argus code`, `argus approve`, lalu patch diterapkan. Yang diukur:
- **jumlah keputusan Atha**: W2b-2 butuh ±17 (dengan dua kegagalan drafter dan tiga PR perbaikan di tengahnya); target
  router ±4 (mulai, approve, merge patch, ditambah kunci);
- biaya total job terhadap cap job $1,00;
- apakah hasilnya `agent-completed` tanpa patch referensi.

## 2. Task

`pilots/router_v0/p1/issue.txt`: perintah baru **`argus list`** (satu baris per job: id, state, terpakai dari cap;
`unreadable` untuk `job.json` rusak; `no jobs` bila kosong; read-only, tanpa kunci). Cocok dengan aturan W2a karena
ini perilaku baru dan tidak ada tes lama yang harus diubah. Tantangan yang disengaja:
- `router/job.py` berukuran 23 KB (±5.900 token). Dengan profil `default` (output 4.096), drafter **harus** menambah
  `edit_file` (cek tulis ulang, PR #157);
- tes lama router butuh `git`, yang tidak ada di sandbox. Tes baru harus membuat job dengan menulis `job.json` sendiri,
  bukan lewat intake (petunjuk sandbox, PR #158).

## 3. Cara jalan (Atha, di VM, checkout live di `main` setelah PR #163)

```bash
cd ~/pilot3a_live && git pull && ~/Argus-agent/.venv-verify/bin/python scripts/argus.py code --repo ~/pilot3a_live --commit HEAD --issue-file pilots/router_v0/p1/issue.txt --exclude verification --exclude pilots
```
Layar drafter menampilkan batas, lalu `[y/N]`, lalu kunci. Setelah drafter selesai, `status` mencetak sha draf dan
perintah approve. Claude meringkas draf untuk Atha. Bila Atha setuju:
```bash
~/Argus-agent/.venv-verify/bin/python scripts/argus.py approve <job> --sha <12 karakter>
```
Layar approve menampilkan sha, writable, validasi, dan cap, lalu `[y/N]`, lalu kunci. Agen jalan, lalu paket review
dibuat. Claude menerapkan patch ke branch, `verify.sh`, dan PR.

## 4. Ekspektasi (sebelum run)

- **Drafter:** ±$0,10–0,30 (W2b-2: $0,09–0,19 per run), 2–4 submit. Yang mungkin: profil `default` dengan `edit_file`.
- **Agen:** satu fungsi baru di `router/job.py` dan satu subperintah di `scripts/argus.py`. ±$0,05–0,20, 1–2 attempt.
- **Job:** ±$0,15–0,50 dari cap $1,00.

## 5. Kriteria (ditetapkan sebelum run, tidak diubah sesudahnya)

1. **Drafter:** `DRAFTED` dalam ≤ 5 submit. Bila `NO_DRAFT`, `redraft` hanya dengan persetujuan baru, dan dicatat.
2. **Approve** adalah keputusan Atha (boleh menolak; itu hasil yang sah).
3. **Berhasil** bila agen `DONE`, paket valid, patch diterapkan ke `main` tanpa perubahan, `verify.sh` lulus, dan biaya
   job ≤ $1,00. Selain itu: gagal, dicatat, berhenti.
4. **Dicatat:** keputusan Atha dan waktunya (dari log `job.json`), biaya per tahap, submit dan alasannya, profil dan
   tool pilihan drafter, menit Atha (opsional), serta kendala router itu sendiri (bug, pesan yang membingungkan).
