# Pilot 3a v2: preflight (ditulis sebelum run)

Status 2026-10-22: **persiapan; belum ada run live.** Task yang sama dengan `pilot3a` (`fix_run_inspectors`: satu pembaca run bersama
`evals/runlog.py` dan dua inspector yang dipindah ke atasnya), disetujui ulang sebagai `fix_run_inspectors_v2` hanya karena profil
anggarannya berubah. Yang diuji: apakah agen, dengan D1 + D2 + D3, memperbaiki cacat begitu melihat error-nya di attempt yang sama.
**D4 (batas ListFiles) dan D5 (prompt caching) sengaja tidak ikut**, supaya hasilnya bisa dikaitkan ke D1–D3 (review GPT, 2026-10-22).

## 1. Apa yang berubah dari `pilot3a`, dan apa yang tidak

| | `pilot3a` / `pilot3a2` | v2 |
|---|---|---|
| Kontrak | `fix_run_inspectors`, profil `large` | `fix_run_inspectors_v2`, profil `large_usd`; scope, validasi, alat, issue, tes baru, patch referensi, `max_usd` 0,75 dan 3 iterasi **sama** (draft v2 = draft lama dengan satu baris berbeda) |
| Anggaran attempt | 45.000 token dihargai seolah output ($0,45) | **$0,45** (D1); batas masukan 40.000 per panggilan; keluaran 8.192; pengaman 400.000 token |
| Umpan balik antar attempt | tanpa baris error | dengan baris error (D2) |
| Setelah langkah yang menulis | tidak ada | validasi otomatis, paling banyak 4 per attempt (D3) |
| Config | `config.yaml` + `max_usd` 0,75 | `config.yaml` + tiga selisih: `budget.max_usd` 0,75, `budget.max_tokens` 1.200.000 (D1 K3), `code_task.auto_validate` true (D3 K5) |
| Model | Sonnet 5.5 ($2/M masukan, $10/M keluaran) | sama |

## 2. Ekspektasi (sebelum run)

- **Hampir pasti satu attempt.** Attempt kedua diterima hanya bila attempt pertama menghabiskan ≤ $0,30 (admission: terpakai + $0,45 ≤ $0,75;
  D1 K2). Simulasi D3 untuk tiga putaran perbaikan: ±$0,37 (`CONTEXT_DESIGN.md` bagian 7). Bila attempt pertama gagal di atas $0,30, run berhenti
  `FAILED_ACCEPTANCE` dengan alasan admission; itu hasil, bukan alasan menaikkan cap.
- **Biaya paling banyak $0,75** (cap run), nyatanya diperkirakan $0,25–0,45 untuk attempt pertama.
- **Waktu:** tiap validasi otomatis ±40 detik (inspectors 35 s + regression 5 s, diukur), paling banyak 4 per attempt; acceptance ±40 detik.
  Code task tidak punya batas waktu dinding (dicatat di `DESIGN_AUTO_VALIDATION.md`).
- **Batas masukan 40.000** tidak diperkirakan mengikat (puncak simulasi empat putaran dengan D3: 34.497; pesan validasi otomatis nyata
  1.855 karakter, lebih kecil dari asumsi simulasi 2.502). Bila mengikat, attempt berakhir `context_limit`; itu dicatat sebagai hasil.
- Cacat yang diketahui di patch agen `pilot3a` (`CONTEXT_DESIGN.md` bagian 7): `NameError` impor, lalu dua tes wajib lain (`events skipped: 1`
  dan `result["tools"]` = `None`). Jadi perbaikan butuh lebih dari satu putaran; empat validasi otomatis = tulisan pertama + tiga putaran.

## 3. Kriteria (ditetapkan sebelum run, tidak diubah sesudahnya)

1. **Berhasil:** `DONE` (acceptance harness lulus, klaim jujur), dalam cap.
2. **Berhasil sebagian (D3 bekerja, tugas belum selesai):** status bukan `DONE`, tetapi di attempt 0 agen menerima pesan validasi otomatis yang
   memuat error, **dan** sesudahnya memperbaiki setidaknya satu cacat yang disebut pesan itu (jumlah tes wajib yang gagal di validasi otomatis
   berikutnya turun, atau error pertama berganti ke error berikutnya).
3. **Gagal:** selain itu (mis. agen tidak menulis, tidak bereaksi pada pesan, atau berhenti sebelum validasi otomatis pertama).

Semua status akhir (`FAILED_ACCEPTANCE`, `FAILED_BUDGET`, `BLOCKED`, `reservation_exhausted`, `context_limit`) dicatat dan **berhenti**: tidak ada
run ulang, kenaikan cap, atau profil lain tanpa persetujuan baru. `--resume` hanya untuk run yang mati.

**Dicatat apa pun hasilnya:** jumlah putaran perbaikan (tulisan → validasi otomatis), USD dan token masukan per panggilan, puncak masukan, apakah
agen tetap memanggil `RunValidation` setelah validasi otomatis (dan berapa kali), durasi sandbox per `origin` (`auto` / `tool` / `acceptance`),
jalur langkah, dan apakah patch akhir sama dengan patch referensi atau butuh intervensi.

## 4. Gerbang (`v2/go_live.sh`, semua harus lolos; diuji di `v2/gl_test.sh`)

1. Kontrak: nama `fix_run_inspectors_v2`, sha256 kontrak = yang dicatat setelah approval, profil `large_usd`, `max_usd` 0,75, 3 iterasi, tiga berkas writable.
2. Config: sha256 berkas yang direview, dan selisih dari `config.yaml` **persis** tiga kunci di atas.
3. Batas efektif dihitung dengan fungsi run sendiri: `large_usd`, $0,45, masukan 40.000, keluaran 8.192, model Sonnet 5.5, cap $0,75, token run
   1.200.000, 3 iterasi, 12 langkah, validasi otomatis 4; buku besar kosong menerima satu attempt.
4. Tanpa `ARGUS_LIVE=1` runner menolak dan tidak membuat direktori run; id run yang sudah ada ditolak; id run `pilot3a[3-9]`.
5. Kunci API diketik Atha sendiri di prompt skrip (tidak tampil, tidak di chat, commit, atau argumen); kosong berarti tidak ada yang dimulai.

## 5. Urutan (tidak ada langkah sebelum persetujuan di kolom kanan)

| # | Langkah | Persetujuan |
|---|---|---|
| 1 | Cek draft v2 tanpa `--approve` (sandbox, biaya nol): baseline merah tepat pada tes wajib, patch referensi lulus, regresi lulus | |
| 2 | `approve_draft.py --draft pilots/m6_pilot3/3a/v2/draft.json --task fix_run_inspectors_v2 --issue-file pilots/m6_pilot3/3a/issue.txt --max-usd 0.75 --max-iterations 3 --reference-patch pilots/m6_pilot3/3a/reference.patch --approve` pada checkout live yang bersih | **Atha, eksplisit** |
| 3 | sha256 kontrak dicatat di `go_live.sh`; PR bukti (record intake, kontrak, laporan cek); tes gerbang `gl_test.sh`; merge | Atha |
| 4 | Checkout live ke `main`, `go_live.sh --check-only` | |
| 5 | Run live **satu kali**: `bash pilots/m6_pilot3/3a/v2/go_live.sh pilot3a3` | **Atha, "go live"** |
| 6 | Laporan menurut bagian 3; `build_review.py` bila `DONE` | |
