# Pilot W2b-1: preflight (ditulis sebelum run)

Status 2026-10-22: **persiapan; belum ada run.** Spec: `docs/reviews/SPEC_W2B_DRAFTER.md` bagian 7 (K7). Kode:
`docs/reviews/REVIEW_M6_W2B.md` (PR #148). Pilot ini **hanya menyusun draf**: tidak ada approve dan tidak ada agen yang jalan.

## 1. Tujuan

Pertanyaannya: **apakah drafter, dari issue saja, menghasilkan draf yang lolos cek W2a, dan seberapa dekat drafnya dengan
draf manusia?** Task-nya sengaja yang jawabannya sudah ada, yaitu pilot 3b (`scripts/pilot_report.py`). Draf manusia
`pilots/m6_pilot3/3b/draft.json` (17 node wajib) menjadi pembanding.

## 2. Artefak dan cek (tanpa biaya)

| | |
|---|---|
| Basis | intake `argus_p6` = `main` `f37aaba` (423 berkas; exclude `verification`, `pilots`). Intake yang sama dengan 3b |
| Cek bocoran | `tests/test_pilot_report.py`, `scripts/pilot_report.py`, dan `pilots/` **tidak ada** di snapshot (gate 1, dan T2 di tes gerbang). Satu-satunya jejak: satu baris di `PENDING.md` snapshot yang menyebut nama skrip dan bahwa spesifikasinya menunggu keputusan. Isinya tidak memuat tes atau jawaban, dan namanya juga ada di issue |
| Issue | `w2b1/issue.txt` = `3b/issue.txt` byte demi byte (akhir baris dinormalisasi), 1.713 karakter |
| Config | `w2b1/config_w2b1.yaml` = `config.yaml` + tiga selisih: `budget.max_tokens` 1.200.000, `drafter.attempt_tokens` 400.000 (hanya batas atas; USD yang mengikat), dan `llm.prompt_cache.enabled` true |
| Batas efektif (gate 3) | Sonnet 5.5; satu attempt **$0,45**, cap run **$0,50** (`--max-usd 0.50` = `budget.max_usd`); input ≤ 40.000 per panggilan; output 8.192; 16 langkah; **3 submit**; tool read-only; validasi di environment `argus`; caching menyala |
| Gerbang | `w2b1/go_live.sh`: intake tidak berubah dan bebas bocoran, sha issue dan config, selisih config persis tiga kunci, batas efektif, tanpa `ARGUS_LIVE` ditolak tanpa membuat direktori, run id `w2b1d[1-9]` baru, dan bentuk kunci. Waktu terminal (gerbang lolos, kunci diketik, run selesai) dicatat ke `~/argus-supervision.log`, di luar repo |
| Tes gerbang | `w2b1/gl_test_output.txt`: kondisi benar lolos (T0, T15); **14 kondisi rusak ditolak** (intake berubah, jawaban 3b dimasukkan ke intake, issue diubah, config diubah, selisih keempat, caching di `config.yaml`, `attempt_usd` 0,60, drafter boleh menulis, 4 submit, tree kotor, run id sudah ada, run id salah atau injeksi, dan kunci kosong, salah bentuk, atau ter-paste dua kali); tidak ada direktori run yang dibuat dan tidak ada `key_entered` tercatat |

## 3. Ekspektasi (sebelum run)

Yang kemungkinan dibaca drafter: `evals/runlog.py` (1,4 KB), `evals/score.py` (9,8 KB), dan satu atau dua tes yang sudah
ada sebagai contoh gaya (`tests/test_run_inspectors.py`, 8,6 KB). Tes yang ditulis untuk issue ini kemungkinan
5–10 KB, atau 2.000–3.500 token output per `SubmitDraft`. Perkiraannya **6–10 panggilan, $0,10–0,30**, dengan 1–2 submit.

Kemungkinan gagal, semuanya hasil yang dicatat, bukan alasan menaikkan apa pun:
- `context_limit` bila drafter membaca terlalu banyak sebelum submit (input > 40.000 per panggilan);
- submit ditolak karena tes yang ERROR di baseline (misalnya import `scripts.pilot_report` di level modul, yang gagal
  karena skripnya belum ada, padahal kegagalannya harus karena assertion). Ini jebakan paling mungkin untuk task
  "berkas baru". Draf manusia menghindarinya dengan menjalankan skrip sebagai subprocess.

## 4. Kriteria (ditetapkan sebelum run, tidak diubah sesudahnya)

1. **Berhasil:** status `DRAFTED` dalam ≤ 3 submit, `source_unchanged` true, dan biaya ≤ $0,45 dengan `usd_complete`
   true. Dengan begitu, setiap node wajib tes baru drafter sudah terbukti merah karena assertion di sandbox, dan semua
   validasi lain hijau.
2. **Gagal:** selain itu (`NO_DRAFT` karena alasan apa pun, atau `BLOCKED`). Status apa pun dicatat lalu **berhenti**:
   tidak ada run ulang, kenaikan cap, atau perubahan config tanpa persetujuan baru. `--resume` hanya untuk run yang mati.
3. **Dicatat** (bukan kriteria lulus):
   - panggilan, langkah, submit (dan alasan setiap penolakan), biaya, cache read/write dan penghematan, puncak input;
   - scope: apakah writable = `scripts/pilot_report.py` saja seperti draf manusia, peringatan scope, dan isi protected;
   - validasi: adakah validasi regresi, dan apa isinya dibanding draf manusia (empat berkas tes 3a); profil budget
     yang dipilih;
   - **cakupan dibanding draf manusia**: untuk setiap perilaku yang diuji draf manusia, apakah tes drafter mengujinya
     (dinilai Claude dari isi tes, ditulis di `RESULT.md` dengan kutipan nama tes):
     tujuh jenis run; menit supervisi; menit yang hilang = null dan 0 = data; tidak ada run `DONE`; tidak ada biaya
     yang diketahui; hanya run tanpa hasil; tanpa argumen ditolak; argumen bukan direktori run ditolak; berkas supervisi
     tidak valid (8 bentuk); berkas supervisi tidak ada. Juga perilaku yang diuji drafter tetapi tidak oleh manusia;
   - `unverifiable` dari drafter;
   - **supervisi** (ukuran ringan): titik keputusan Atha untuk pilot ini, waktu terminal dari `~/argus-supervision.log`,
     dan menit Atha (opsional, satu angka; "skip" dicatat `unknown`).
4. **Bukan bagian pilot ini:** approve draf drafter dan menjalankan agen di atasnya. Bila draf lolos dan Atha mau, itu
   langkah terpisah dengan persetujuan sendiri (`approve_draft.py --no-reference` dengan nama task baru, lalu preflight
   agen). Itu juga yang akan memberi ukuran pertama untuk W2b-2.

## 5. Urutan

| # | Langkah | Persetujuan |
|---|---|---|
| 1 | Merge PR ini (issue, config, gerbang, tes gerbang, preflight) | Atha |
| 2 | Live checkout ke `main`: `cd ~/pilot3a_live && git checkout main && git pull`; lalu `bash pilots/m6_w2b/w2b1/go_live.sh --check-only` | |
| 3 | Run live **satu kali**: `bash ~/pilot3a_live/pilots/m6_w2b/w2b1/go_live.sh w2b1d1` (kunci di-paste sekali) | **Atha, "go live"** |
| 4 | Laporan menurut bagian 4 di `w2b1/live/w2b1d1/RESULT.md`, dengan `DRAFT_REVIEW.md` dan `draft.json` dari run | |

## 6. Run kedua `w2b1d2` (pilihan A, Atha 2026-10-22; ditulis sebelum run)

`w2b1d1` gagal (`live/w2b1d1/RESULT.md`): `SubmitDraft` terpotong di output 8.192, dan 6.108 di antaranya thinking.
Satu-satunya perubahan untuk run kedua: `roles.drafter.max_output_tokens` 8.192 → **16.384** di `config.yaml`.
`config_w2b1.yaml` dibuat ulang dari situ dengan tiga selisih yang sama, sha baru ada di gerbang, dan gate 3 mengharapkan
16.384. **Uang tidak naik:** satu attempt tetap $0,45 dan cap run $0,50. Setiap panggilan tetap ditolak sebelum dikirim
bila kasus terburuknya (input dengan tarif tulis, ditambah output yang tersisa) tidak muat.

- **Ekspektasi:** langkah baca kira-kira sama (±$0,05), lalu submit pertama dengan output 8.000–14.000 token
  (thinking ±6.000, tes 4.000–8.000), ±$0,07–0,15. Bila submit pertama ditolak dan diperbaiki, totalnya ±$0,25–0,40.
  Submit ketiga mungkin tidak muat lagi; bila begitu, hasilnya `reservation_exhausted` dan dicatat apa adanya.
- **Kriteria:** sama dengan bagian 4, tanpa perubahan.
- **Langkah:** merge PR ini; checkout live ke `main`; `go_live.sh --check-only`; lalu
  `bash ~/pilot3a_live/pilots/m6_w2b/w2b1/go_live.sh w2b1d2` setelah **"go live"** dari Atha. Run id `w2b1d1` sudah ada
  dan ditolak gerbang.

## 7. Run ketiga `w2b1d3` (Atha 2026-10-22: "1+2+revisedraft"; ditulis sebelum run)

`w2b1d2` gagal (`live/w2b1d2/RESULT.md`). Submit 1 nyaris lolos, tetapi satu tes gagal tanpa diwajibkan. Kiriman
ulangnya butuh input sekitar 45.000, sehingga ditolak oleh batas 40.000. Perubahan untuk run ketiga:

1. **Penolakan menyebut tes yang gagal atau error di luar `must_pass`.** Bukti validasi pytest kini memuat
   `failed_nodes`, dan pesan cek baseline mencantumkannya.
2. **`ReviseDraft`:** mengubah hanya field yang diberikan dari draf yang terakhir dikirim. Setiap field yang diberikan
   menggantikan field itu seluruhnya. Hasilnya dicek seperti `SubmitDraft` dan ikut dihitung ke `max_submits` (3).
   Perbaikan kecil, seperti satu node `must_pass`, tidak lagi menuntut kirim ulang tes 10 KB.
3. **Uang dan konteks (naik, disetujui Atha):**
   - `drafter.attempt_usd` 0,45 → **0,70**;
   - `drafter.max_input_tokens` 40.000 → **64.000**;
   - config pilot `budget.max_usd` 0,50 → **0,75**, dan `--max-usd 0.75`.

   Config pilot kini berbeda dari `config.yaml` di **empat** kunci. Gate 2 dan gate 3 serta tes gerbangnya sudah
   diperbarui.

- **Ekspektasi:** langkah baca dan submit 1 seperti `w2b1d2` (±$0,22). Bila submit 1 ditolak, ReviseDraft murah
  (input ±45.000, sebagian besar cache read; output thinking ditambah argumen kecil), ±$0,05–0,15. Total
  **$0,25–0,45**; batas keras $0,70 per attempt dan $0,75 per run.
- **Kriteria:** sama dengan bagian 4, tanpa perubahan.
- **Langkah:** merge PR; checkout live ke `main`; `go_live.sh --check-only`; lalu
  `bash ~/pilot3a_live/pilots/m6_w2b/w2b1/go_live.sh w2b1d3` setelah **"go live"**.
