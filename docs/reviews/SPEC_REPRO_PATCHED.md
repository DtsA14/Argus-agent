# Spek: contoh issue dijalankan lagi di pohon yang sudah dipatch (`repro` R1b), judge mati default

Status: **v2 2026-11-13, disetujui Fable untuk mulai menulis tes dengan empat perubahan (sudah masuk di bawah: label `changed`/`unchanged`, status disimpan dulu, tiga keadaan "not run", kalimat netral).** Asal: jawaban Fable atas laporan batch 2 (P2, P5, A): "matikan judge default; gantinya R1 dijalankan lagi pada pohon yang sudah
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

**P2. R1 sesudah patch (tanpa model, tanpa penolakan).** Dijalankan **sesudah** `job.move(REVIEW_READY)` tersimpan (bukan di dalam `_agent` sebelum pindah status): run bisa sampai
3 x 20 s, dan proses yang mati di tengahnya tidak boleh menahan job. Hanya bila paket **valid**, jalankan `acceptance.repro.run` pada pohon yang dibangun dengan `review.apply_patch`
(base commit + `changes.patch` lewat `git apply`, dibangun di folder sementara: persis yang akan diterapkan manusia, tanpa berkas cache agen), dengan issue yang sama, konfigurasi
sandbox yang sama dan batas yang sama dengan R1 (maks 3 blok, 4.000 byte, 20 s, keluaran 2.000 byte). Hasil disimpan **per stage** di `repro_patched_<sid>.json` di folder job,
terikat ke `sha256(sha256 changes.patch + "\n" + issue)`. Mati di tengah run: `resume` tidak mengulang agen (job sudah `REVIEW_READY`) dan tidak ada berkas setengah jadi (tulis
atomik); `status` menyebut "not run". Paket tidak valid: tidak dijalankan; berkas kecil `repro_patched_<sid>.json` dengan `skipped: "review package invalid"` ditulis agar layar bisa
membedakannya dari galat.

**P3. Tampilan, dua arah.** Per blok, bandingkan hasil di dasar (dari `repro.json`) dengan hasil sesudah patch secara mekanis dari tiga hal: status (`ok`/`raised`/`timeout`), tipe
exception (token pertama baris stderr terakhir, mis. `ValueError`), dan baris keluaran terakhir. Label per blok: `changed` (salah satunya beda) atau `unchanged` (sama semua); tanpa
label bila salah satu sisi tidak jalan. Tidak ada arah yang dianggap baik: `raised -> ok` dan `ok -> raised` sama-sama `changed` (di #1257 dasarnya `ran clean "1"` dan perbaikan yang
benar `raised ValueError`). `unchanged` adalah sinyal yang paling berguna (patch tidak mengubah apa pun untuk contoh issue, seperti tiga instance batch 1 yang sudah beres di dasar).
Satu baris di `status` dan layar review, di bawah `review package`: `issue example, base -> patched: raised ValueError -> ran clean "0o644" [changed]`.
Tiga keadaan "tidak ada hasil" dibedakan di layar: `not run (review package invalid)`, `not run (error)`, dan tidak ada baris sama sekali untuk job lama tanpa berkas
(`status` tidak berubah untuk job yang dibuat sebelum fitur ini). Kalimat tetap, netral: "the example runs agent-written code; compare both outputs against the issue".
Baris dihitung ulang dari berkas milik **stage yang paketnya sedang direview** dan **dicek terhadap patch yang ada di disk** (kunci tidak cocok -> `not run (the patch changed since
it was run)`); tidak ada yang dibaca dari laporan agen. Batas yang dicatat: keluaran yang tidak deterministik (alamat memori, waktu) terbaca `changed`.

**P4. Display only.** Tidak menolak, tidak mengubah status job, patch, review package, ledger, anggaran. Galat apa pun (sandbox mati, berkas rusak, `repro.run` melempar) →
"not run", job lanjut ke `REVIEW_READY` seperti biasa. Tidak ada kode keluar atau status yang bergantung padanya.

## 3. Di luar cakupan

Membandingkan keluaran dengan nilai yang diharapkan issue (R2, parser doctest: PR lain), menjalankan tes proyek, jadi gerbang, menggantikan penilaian manusia. Sinyal ini dapat
dipalsukan oleh kode agen (kode produksi bisa mencetak apa saja); itu alasan ia hanya tampilan, bukan gerbang.

## 4. Tes (gagal di kode lama)

1. agen DONE dengan paket valid dan issue memuat satu blok python → `repro_patched_a1.json` ada, `run` dipanggil pada pohon hasil `review.apply_patch` (bukan dasar, bukan
   `run_dir/workspace`, tanpa berkas cache); status `REVIEW_READY` sudah tersimpan **sebelum** `run` dipanggil (urutan dicek).
2. paket tidak valid (`REVIEW_INVALID`) → `run` tidak dipanggil; berkas hanya memuat `skipped`, dan `status` menampilkan `not run (review package invalid)`.
3. `repro.run` melempar atau mengembalikan `None` → status tetap `REVIEW_READY`, ledger dan `job.json` sama dengan kasus tanpa fitur kecuali satu event `repro_patched`.
4. `status` menampilkan pasangan "after the patch ... (at base: ...)" dengan dasar `raised` dan sesudah patch `ok`; dasar `None` (not run) tetap tampil sebagai "at base: not run".
5. `changes.patch` diubah di disk sesudahnya → baris menjadi "not run (the patch changed since it was run)"; issue diubah → sama.
6. hasil tidak mengubah apa pun: `job.json` (kecuali event), `result.json`, `changes.patch`, anggaran identik antara hasil `ok`, `raised`, `timeout` dan tanpa fitur.
7. keluaran dipotong 2.000 byte dan karakter kontrol diganti (fungsi `_cut` yang sama; berkas yang diedit dibersihkan lagi saat dibaca).
8. proses mati di tengah R1b (sesudah `REVIEW_READY`) → `resume` tidak menjalankan agen lagi, job tetap `REVIEW_READY`, `status` menampilkan `not run`, tidak ada berkas setengah jadi.
9. label: dasar `ok "1"` dan sesudah patch `raised ValueError` → `changed`; sama persis → `unchanged`; salah satu `None` → tanpa label; tipe exception beda → `changed`.
10. tiga keadaan layar: paket tidak valid, galat (`run` melempar) dan job lama tanpa berkas menghasilkan tiga teks berbeda (yang ketiga: tidak ada baris).
11. dua stage (a1 lalu retry a2 dengan patch lain): `status` menampilkan berkas milik stage yang paketnya sedang direview, bukan stage lain.
12. judge: `approve`/`resume` tidak pernah memanggil `jd.run_judge` (tes pada jalur `_agent` dengan model palsu yang gagal bila judge disentuh).
Mutants: `run` dipanggil sebelum `REVIEW_READY` tersimpan; label hanya satu arah (`raised -> ok`); `unchanged` dan `changed` tertukar; `status` menampilkan berkas stage lain; `run` dipanggil pada dasar bukan pohon akhir; dijalankan pada paket tidak valid; galat naik ke job; kunci tanpa sha patch; baris dibaca dari laporan bukan dari berkas;
status job bergantung hasil; judge dipanggil dari `_agent`.

## 5. Ukuran

Per job: pasangan (dasar, sesudah patch), label, dan nilai buta. Hitung: `unchanged` pada patch A/B (patch yang menurut penilai benar tapi contoh issue tidak berubah:
contohnya tidak mengukur apa pun), `changed` pada patch A/B (sinyal cocok), `changed` pada patch C (sinyal bohong: patch salah tapi contoh berubah), `unchanged` pada patch C (sinyal
benar). Dari angka itu baru R2 diputuskan.

## 6. Sebelum batch 3: R1b offline pada 18 patch yang ada (usul Fable, di luar PR ini)

Skrip kecil di `pilots/outside_v1/` (bukan bagian harness; tanpa model, tanpa uang) menjalankan `repro.run` pada dasar dan pada pohon hasil `review.apply_patch` untuk 18 patch batch 1
dan 2 yang sudah punya nilai buta, dan menulis tabel (job, dasar, sesudah patch, label, nilai buta). Dikerjakan **setelah** kode R1b ter-merge, supaya memakai fungsi yang sama.
Hasilnya menentukan apakah sinyal layak dan memajukan keputusan R2 tanpa menunggu delapan job lagi.
