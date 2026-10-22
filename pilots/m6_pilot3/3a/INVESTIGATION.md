# M6 pilot 3a: investigasi penyebab kegagalan dan reproduksi (2026-10-22)

Tanpa biaya: semuanya dari rekaman run `pilot3a` (buku besar, memo, verdict) dan dari replay lewat harness yang sama dengan balasan model yang direkam. Bukti: `evidence/investigation/`.
Skrip: `investigate.py` (token per panggilan dan per hasil alat), `investigate_attempt1.py` (apa yang dilihat agen), `replay_3a.py` (replay).

## 1. Ringkasan

- **Kegagalan 3a bisa direproduksi sampai tingkat hash di sisi harness.** Replay dengan balasan model yang direkam menghasilkan 9 panggilan yang sama (iterasi, langkah, status, hash prompt, token), `reservation_exhausted` di kedua attempt,
  digest workspace sama (`41b051c07334de8d`), kriteria gagal yang sama, dan biaya yang sama ($0,200014). Jadi hasilnya ditentukan oleh (balasan model, anggaran); tidak ada keacakan dari provider atau harness di sisi penghitungan.
- **Yang tidak bisa direproduksi tanpa membayar:** pilihan model itu sendiri (memanggil `ListFiles` di langkah 0, membaca modul data, mencari alih-alih memperbaiki). Itu hanya bisa diuji dengan run live baru.
- **Penyebab utama attempt 0 adalah bentuk trajektori, bukan satu kesalahan:** konteks tumbuh kuadratik (setiap langkah mengirim ulang semua hasil alat sebelumnya) dan dalam tiga langkah sudah terpakai 95% reservasi, sebelum validasi pertama.
- **Koreksi atas klaim saya sebelumnya:** agen melihat `NameError` **sekali**, bukan dua kali (lihat 4). Penjelasan "satu bacaan ekstra (modul data) yang mengubah hasil" di `RESULT.md` juga tidak lengkap (lihat 3).

## 2. Ke mana token pergi (attempt 0, reservasi 45.000)

| Langkah | Token masuk (taksiran sebelum kirim) | Keluaran | Terpakai sebelum langkah | Tersisa |
|---|---|---|---|---|
| s0 | 3.097 | 139 | 0 | 45.000 |
| s1 | 12.657 | 172 | 3.236 | 41.764 |
| s2 | 23.840 | 3.046 | 16.065 | 28.935 |
| s3 (ditolak) | **27.252** | – | **42.951** | **2.049** |

Isi konteks (token tiap hasil alat; `token_ledger_and_tool_results.txt`):
- s0 meminta `ListFiles` + `audit_run.py` + `failure_trace.py`: `ListFiles` menambah **4.141 token** (13 KB, ±390 berkas), `audit_run.py` 1.439, `failure_trace.py` 494.
- s1 membaca tes utama (2.701), **modul data tes (4.817)**, `harness/events.py` (609).
- s2 menulis `evals/runlog.py` dan empat penyuntingan: 3.046 token keluaran yang ikut terkirim ulang.
- Validasi (s3) dan `Finish` (s4) belum terjadi, jadi `NameError` tidak pernah terlihat oleh agen di attempt 0.

## 3. Berapa yang dibutuhkan trajektori itu, dan apa yang akan diubah oleh tiap hipotesis (hitungan dari buku besar)

Trajektori rekaman butuh langkah s3 (validasi) dan s4 (`Finish`), masing-masing dengan masukan ≥ 27,3 ribu token. Total sampai selesai ≈ **98–99 ribu token**, sekitar 2,2 kali reservasi 45.000.

| Seandainya | Kebutuhan perkiraan |
|---|---|
| tidak memanggil `ListFiles` (4.141 token terkirim ulang di 4 langkah) | ≈ 82 ribu |
| tidak membaca modul data (4.817 token terkirim ulang di 3 langkah) | ≈ 84 ribu |
| keduanya | ≈ 68 ribu, **masih di atas 45.000** |

Jadi menghilangkan modul data (asumsi yang salah di desain saya) atau `ListFiles` saja tidak akan membuat attempt 0 selesai; yang dibutuhkan adalah bentuk yang jauh lebih pendek (simulasi `c_with_tests` memakai lima langkah dengan satu penulisan terbatch, 38 ribu).
Simulasi token 3a terlalu optimistis karena **tidak memodelkan langkah-langkah yang benar-benar diambil agen** (daftar berkas di awal, pembacaan terpisah, penulisan besar sendiri); pelajaran: simulasi harus dijalankan juga dengan bentuk langkah yang diamati di run nyata.

## 4. Attempt 1: apa yang dilihat agen, dan mengapa tidak memperbaiki

Reservasi attempt 1 mulai dari nol (konteks baru, tidak membawa riwayat attempt 0), 45.000 token. Agen memakai 40.692 untuk empat langkah, lalu langkah ke-5 ditolak (tersisa 4.308 untuk masukan 18.971).

- **Umpan balik di prompt attempt 1** memuat kriteria yang gagal dan nama tes wajib yang gagal, plus hasil cek harness (tes dijalankan, berkas yang berubah). **Tidak memuat traceback**: di prompt attempt 1 yang utuh (5.314 karakter; hash prompt yang dibangun ulang sama dengan buku besar, jadi ini persis yang diterima agen) tidak ada `NameError` maupun `Traceback`. Nama `read_result` ada di sana hanya karena issue sendiri menyebut fungsi itu. Alasan kegagalan ada di verdict, tetapi tidak dikirim ke agen.
- **Hasil `RunValidation(inspectors)` di s0 attempt 1** (dibaca agen) memuat `output_tail` 1.496 karakter dengan `NameError: name 'read_result' is not defined` (`audit_run.py` baris 24), muncul dua kali di ekor itu. Jadi agen **melihat error itu sekali**, di langkah yang sama saat ia membaca ulang `audit_run.py`.
- Langkah berikutnya: `SearchFiles(codetask, "def offered")` dan `SearchFiles(tests, "blocked_before")` (menjelajahi perilaku run yang `BLOCKED`, bukan impor), lalu membaca `codetask/tools.py` (17,7 KB, **5.649 token**) dan tes utama lagi (2.701), lalu `SearchFiles` dengan `path` berupa berkas (ditolak). Yang diperlukan hanya satu penyuntingan impor.
- Tidak ada informasi tentang sisa reservasi di prompt (`codetask/agent.py` tidak menyebut token atau anggaran); agen tidak tahu bahwa ia menghabiskan jatah.

## 5. Faktor, diurutkan menurut pengaruh yang terukur

1. **Bentuk trajektori dan konteks kuadratik** (utama; ≈ 98 ribu dibutuhkan vs 45 ribu tersedia di attempt 0).
2. **`ListFiles` 4.141 token** yang terkirim ulang tiap langkah (perilaku model; harness tidak membatasinya). Di Pilot 4 dan 5 agen tidak memanggil `ListFiles`; di 3a yang menyebut tiga berkas, satu di antaranya baru, ia memanggilnya.
3. **Modul data 4.817 token** (asumsi desain saya salah: agen membacanya).
4. **Penulisan besar** 3.046 token.
5. **Attempt 1:** penjelajahan yang tidak relevan (5.649 + 2.701 token bacaan) dan tidak menerapkan perbaikan satu baris walau `NameError` terlihat. Ini kegagalan perilaku model; umpan balik tanpa traceback memperburuknya.

## 6. Hipotesis perbaikan (belum diuji; urut dari termurah)

| # | Hipotesis | Jenis | Catatan |
|---|---|---|---|
| H1 | Task lebih kecil (3a-lite; atau `audit_run.py` saja) | desain task | bukti: task satu fungsi 3 dari 3 `DONE` di attempt pertama |
| H2 | Issue menyebut jalur persis semua berkas dan menyatakan tidak perlu daftar berkas | prompt/issue | murah; di Pilot 4/5 agen langsung membaca berkas yang disebut |
| H3 | Umpan balik memuat potongan traceback kegagalan pertama dan menyuruh memperbaikinya dulu | harness (`codetask/agent.py`) | belum ada bukti selain 3a; ubah hanya setelah pola terulang |
| H4 | `ListFiles` dibatasi (per direktori atau jumlah) | harness (`codetask/tools.py`) | 4,1 ribu token per langkah adalah biaya tetap untuk repo sebesar ini |
| H5 | Memberi tahu agen sisa reservasinya | harness | belum diuji; bisa membuat agen berhenti menjelajah, atau malah terburu-buru |

Semua perubahan harness mengikuti aturan inti (tes yang gagal di kode lama, mutan, `verify.sh`).

## 7. Apakah akan terulang di run live? (terjawab oleh replikasi `pilot3a2`, 2026-10-22)

- Sisi harness: identik (replay).
- Sisi model: **ya**, dengan satu run live ulang (kontrak, config, dan batas sama; `live/pilot3a2/RESULT.md`): langkah 0 identik, langkah 1 identik dalam isi (token dan alat sama), kegagalan yang sama (`reservation_exhausted` di kedua attempt, tidak sampai `Finish`), biaya $0,1937,
  dan kesalahan impor `read_result` yang sama di `audit_run.py`. Model menyimpang mulai langkah ketiga (menulis vs mencari), tetapi anggaran sudah habis lebih dulu. Catatan: hash prompt langkah ke-1 dan seterusnya berbeda antar run karena id pemanggilan alat dari provider acak, jadi perbandingan memakai token dan alat, bukan hash.

## 8. Koreksi laju token dan tindak lanjut (2026-10-22)

`CONTEXT_DESIGN.md` (simulasi kebijakan konteks dari buku besar dan memo kedua run, `simulate_context.py`) memfit laju token per jenis isi ke buku besar. Hasilnya mengoreksi taksiran di bagian 2 dan 3 dokumen ini, yang memakai laju kasar
0,3186 token/karakter: `ListFiles` ±7.070 token (bukan 4.141) dan modul data ±7.050 (bukan 4.817). Jumlah per langkah di buku besar tidak berubah (itu angka provider); yang berubah hanya pembagian per jenis isi, yang di sana lemah teridentifikasi
(6 parameter untuk 9 transisi; kesimpulan tahan uji ±15%). Kesimpulan bagian 1 dan 5 tetap: bentuk trajektori yang mengikat, bukan satu bacaan.

Verifikasi independen: `simulate_context.py` dijalankan ulang di VM pada `runs/pilot3a` dan `runs/pilot3a2` (arsip run asli) dan keluarannya identik dengan `evidence/context_sim/simulation_output.txt` (85 baris).
Usulan perubahan harness (D1–D5) ada di `CONTEXT_DESIGN.md`; spesifikasi D2 di `docs/reviews/DESIGN_FEEDBACK_TRACEBACK.md`.
