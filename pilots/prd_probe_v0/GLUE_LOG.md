# Glue log (probe PRD-lite: papan skor), diisi saat probe berjalan

Satu baris per tindakan manusia atau Claude di antara irisan, dengan menit (bila Atha) dan penilaian **bisa diotomasi?** (ya / sebagian / tidak). Kosong sampai probe dimulai.

| Irisan | Perekat | Siapa | Bisa diotomasi? |
|---|---|---|---|
| S1 | Menulis issue ledger dari kontrak PRD (menyalin bentuk JSON, aturan hasil, pembulatan, contoh berangka) ke teks issue | Claude | sebagian: bentuk kontrak bisa ditempel dari PRD otomatis; contoh berangka dan edge case butuh penilaian |
| S1 | Membaca draf (alasan merah, tes lama, peringatan bocor) lalu approve | Claude | sebagian (gerbang harness sudah ada; penilaian "tes sehat" masih manusia) |
| S1 | Membaca patch, `git apply`, commit di repo target, `argus applied` | Claude | **ya**: ini `argus apply` yang belum ada (sambungan 3) |
| S1→S2 | Menulis `PLAN.md` Stage 18 dari pola Stage 17 | Claude | ya (templat sama dengan Stage 17; hanya id job, commit, dan cek data yang berganti) |
| S1→S3 | Temuan: S3 (viewer) tidak perlu menunggu S2 untuk **kodenya** (kontrak sudah beku); ketergantungannya hanya pada rilis dan verifikasi di HP, jadi S3 dikerjakan dulu dan rilisnya ditahan | Claude | sebagian: urutan "S2 sebelum S3" di PRD sebenarnya "S2 sebelum rilis S3" |
