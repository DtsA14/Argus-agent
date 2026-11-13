# Spek: contoh issue dijalankan lagi di pohon yang sudah dipatch (`repro` R1b), judge mati default

Status: **draf Claude 2026-11-13, belum disetujui.** Asal: jawaban Fable atas laporan batch 2 (P2, P5, A): "matikan judge default; gantinya R1 dijalankan lagi pada pohon yang sudah
dipatch: `raised` di dasar lalu `ran clean` setelah patch itu sinyal murah dan deterministik. Tampilkan sebagai sinyal, jangan jadi gerbang." Jalur ketat: menjalankan kode di
sandbox. Tanpa model, tanpa uang. Berlaku AGENTS.md: tes gagal di kode lama → kode → review → mutants → `verify_at` → "merge" Atha.

## 1. Masalah (bukti)

Judge makan 77% biaya batch 1 dan 2, NOT_JUDGED 7 dari 18 job (semua `output_truncated`: GLM-5.3 menghabiskan 32.000 token output untuk reasoning, ~$0,15 per job), dan PASS-nya
jatuh pada dua patch yang salah (boltons#480 dan boltons#393). Manusia butuh satu sinyal murah di layar yang sama dengan patch. R1 (#468-#470) sudah menjalankan contoh issue di
commit dasar dan menampilkannya; yang belum ada: hasil contoh yang sama sesudah patch, di sebelahnya.

## 2. Usul

**P1. Judge mati default.** Judge sudah hanya jalan lewat `argus judge` (tidak ada pemanggilan otomatis di `approve`/`resume`); tidak ada perubahan kode. Yang berubah: aturan
kerja (PENDING dan memori) dan satu hal di `status`: di `REVIEW_READY` tanpa tahap judge, `status` tidak menyebut judge sama sekali (sudah begitu; tes mengunci ini). Judge dan
`scripts/calibrate_judge.py` tetap ada sebagai alat manual.

**P2. R1 sesudah patch (tanpa model, tanpa penolakan).** Di `_agent`, sesudah `review.build` mengatakan paket **valid**, jalankan `acceptance.repro.run` pada
`run_dir/workspace` (pohon akhir agen; paket valid berarti sama dengan dasar + `changes.patch`) dengan issue yang sama, konfigurasi sandbox yang sama dan batas yang sama dengan R1
(maks 3 blok, 4.000 byte, 20 s, keluaran 2.000 byte). Hasil disimpan di `repro_patched_<sid>.json` di folder job, terikat ke `sha256(sha256 changes.patch + "\n" + issue)`.
Paket tidak valid → tidak dijalankan, tanpa berkas.

**P3. Tampilan.** Satu baris di `status` dan layar review (di bawah `review package`): `issue example after the patch: ran clean, last output "0o644" (at base: raised ValueError)`.
Pasangan per blok: dasar (dari `repro.json`) lalu sesudah patch. Kalimat tetap: "A clean run does not prove the bug is fixed: the example runs agent-written code; read the
output against the issue". Baris dihitung ulang dari berkas dan **dicek terhadap patch yang ada di disk** (kunci tidak cocok → "not run (the patch changed since it was run)");
tidak ada yang dibaca dari laporan agen.

**P4. Display only.** Tidak menolak, tidak mengubah status job, patch, review package, ledger, anggaran. Galat apa pun (sandbox mati, berkas rusak, `repro.run` melempar) →
"not run", job lanjut ke `REVIEW_READY` seperti biasa. Tidak ada kode keluar atau status yang bergantung padanya.

## 3. Di luar cakupan

Membandingkan keluaran dengan nilai yang diharapkan issue (R2, parser doctest: PR lain), menjalankan tes proyek, jadi gerbang, menggantikan penilaian manusia. Sinyal ini dapat
dipalsukan oleh kode agen (kode produksi bisa mencetak apa saja); itu alasan ia hanya tampilan, bukan gerbang.

## 4. Tes (gagal di kode lama)

1. agen DONE dengan paket valid dan issue memuat satu blok python → `repro_patched_a1.json` ada, `run` dipanggil dengan `workdir` = salinan `run_dir/workspace` (bukan dasar, bukan
   `/workspace` asli); status `REVIEW_READY`.
2. paket tidak valid (`REVIEW_INVALID`) → `run` tidak dipanggil, tidak ada berkas.
3. `repro.run` melempar atau mengembalikan `None` → status tetap `REVIEW_READY`, ledger dan `job.json` sama dengan kasus tanpa fitur kecuali satu event `repro_patched`.
4. `status` menampilkan pasangan "after the patch ... (at base: ...)" dengan dasar `raised` dan sesudah patch `ok`; dasar `None` (not run) tetap tampil sebagai "at base: not run".
5. `changes.patch` diubah di disk sesudahnya → baris menjadi "not run (the patch changed since it was run)"; issue diubah → sama.
6. hasil tidak mengubah apa pun: `job.json` (kecuali event), `result.json`, `changes.patch`, anggaran identik antara hasil `ok`, `raised`, `timeout` dan tanpa fitur.
7. keluaran dipotong 2.000 byte dan karakter kontrol diganti (fungsi `_cut` yang sama; berkas yang diedit dibersihkan lagi saat dibaca).
8. judge: `approve`/`resume` tidak pernah memanggil `jd.run_judge` (tes pada jalur `_agent` dengan model palsu yang gagal bila judge disentuh).
Mutants: `run` dipanggil pada dasar bukan pohon akhir; dijalankan pada paket tidak valid; galat naik ke job; kunci tanpa sha patch; baris dibaca dari laporan bukan dari berkas;
status job bergantung hasil; judge dipanggil dari `_agent`.

## 5. Ukuran sesudah merge

Di batch 3: untuk tiap job, pasangan (dasar, sesudah patch) dan nilai buta. Hitung: berapa `raised → ran clean` pada patch yang A atau B, berapa `ran clean → ran clean` (tak
informatif), dan apakah ada `raised → ran clean` pada patch yang dinilai C (sinyal bohong). Dari angka itu baru diputuskan R2.
