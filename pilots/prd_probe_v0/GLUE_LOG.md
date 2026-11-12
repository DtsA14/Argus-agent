# Glue log (probe PRD-lite: papan skor), diisi saat probe berjalan

Satu baris per tindakan manusia atau Claude di antara irisan, dengan menit (bila Atha) dan penilaian **bisa diotomasi?** (ya / sebagian / tidak). Kosong sampai probe dimulai.

| Irisan | Perekat | Siapa | Bisa diotomasi? |
|---|---|---|---|
| S1 | Menulis issue ledger dari kontrak PRD (menyalin bentuk JSON, aturan hasil, pembulatan, contoh berangka) ke teks issue | Claude | sebagian: bentuk kontrak bisa ditempel dari PRD otomatis; contoh berangka dan edge case butuh penilaian |
| S1 | Membaca draf (alasan merah, tes lama, peringatan bocor) lalu approve | Claude | sebagian (gerbang harness sudah ada; penilaian "tes sehat" masih manusia) |
| S1 | Membaca patch, `git apply`, commit di repo target, `argus applied` | Claude | **ya**: ini `argus apply` yang belum ada (sambungan 3) |
| S1→S2 | Menulis `PLAN.md` Stage 18 dari pola Stage 17 | Claude | ya (templat sama dengan Stage 17; hanya id job, commit, dan cek data yang berganti) |
| S1→S3 | Temuan: S3 (viewer) tidak perlu menunggu S2 untuk **kodenya** (kontrak sudah beku); ketergantungannya hanya pada rilis dan verifikasi di HP, jadi S3 dikerjakan dulu dan rilisnya ditahan | Claude | sebagian: urutan "S2 sebelum S3" di PRD sebenarnya "S2 sebelum rilis S3" |
| S3 | Menulis issue viewer dari kontrak yang sama (menempel contoh JSON, memilih teks kolom dan kalimat tetap, meniru pola `/waiting`) | Claude | sebagian: bentuk data dan pola halaman bisa diturunkan dari kontrak; teks tampilan dan pilihan "meniru halaman mana" butuh penilaian |
| S3 | Agen kehabisan konteks pada percobaan 1 (20 langkah) dan selesai pada percobaan 2 | harness | ya (sudah otomatis; hanya biaya +$0,02) |
| S3 | Membaca draf, patch, apply, commit, `applied` | Claude | ya untuk apply (sambungan 3); sebagian untuk membaca |
| S4 | Memutuskan tempat tautan (akhir halaman, bukan di bawah ringkasan) supaya tidak berbenturan dengan tes urutan lama | Claude | tidak: pilihan desain berdasarkan pengetahuan tentang tes lama (peringatan `leaks` tidak ada untuk JS) |
| S4 | Rilis viewer S3 + S4 | Claude | ya (`stage viewer-deploy` satu perintah) tetapi **menunggu S2** (data) dan "go live" Atha untuk staging |

Hasil sementara (2026-11-12): S1, S3, S4 lolos pada draf pertama dan percobaan agen pertama atau kedua; tidak ada konflik tes lama di ketiganya; biaya model total $0,1645 (S1 $0,0375, S3 $0,0741, S4 $0,0529).
Perekat yang tersisa sebelum fitur terlihat di HP: S2 (Stage 18) dan rilis viewer, keduanya menunggu "go live".
| S2 | **Ketergantungan tersembunyi 2:** proxy viewer (Argus, `router/stage_viewer.py:76`) hanya meneruskan empat jalur API tetap; `/api/scoreboard` mengembalikan 404 walau ledger Stage 18 sehat. Ditemukan saat cek data nyata (langkah 5 Stage 18); PRD tidak menyebutnya | Claude | **tidak** untuk menemukannya sebelum jalan (tahap PRD tidak melihat daftar jalur proxy); ya untuk perbaikannya (satu regex, tapi jalur ketat dan perlu restart proxy) |
| S2 | Menjalankan Stage 18 dan mencatat langkah | Claude | ya (templat sama dengan Stage 17) |

Hasil probe sejauh ini: dua ketergantungan tersembunyi di sisi **Argus** (snapshot tidak memuat nama repo dan `as_is`, ditemukan saat menulis PRD; proxy tidak meneruskan jalur baru, ditemukan saat staging). Keduanya jalur ketat dan tidak bisa dikerjakan Argus sendiri.
Pelajaran untuk tahap PRD: sebelum membekukan kontrak, periksa **jalur data yang melewati Argus** (snapshot yang diterbitkan, daftar jalur proxy), bukan hanya kode aplikasi.
