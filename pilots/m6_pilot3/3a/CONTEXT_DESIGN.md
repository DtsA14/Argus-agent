# M6 pilot 3a: konteks, anggaran attempt, dan apa yang sebaiknya diubah (2026-10-22)

Status: **desain dan angka; belum ada kode harness yang diubah.** Semuanya tanpa biaya: dihitung dari buku besar dan memo dua run
live (`pilot3a`, `pilot3a2`), tanpa model dan tanpa sandbox. Skrip: `simulate_context.py`. Keluaran: `evidence/context_sim/`
(`simulation_output.txt`, `simulation.json`). Data masukan: arsip `runs/pilot3a` dan `runs/pilot3a2` dari VM OCI (tidak di repo).

## 1. Ringkasan

- **Replikasi `pilot3a2` gagal dengan cara yang sama.** Dua langkah pertama identik dengan `pilot3a` (ListFiles, lalu tiga bacaan
  termasuk modul data, dengan token yang sama persis), dan di keempat attempt dari dua run reservasi habis. **Tidak ada attempt
  yang sempat menulis lalu memvalidasi tulisannya**: dua attempt menulis lalu ditolak tepat sebelum validasi, satu memvalidasi
  (`pilot3a` attempt 1) tetapi tidak pernah menulis, satu tidak melakukan keduanya. Kegagalan ini stabil, jadi perbaikannya bisa
  diuji tanpa banyak replikasi.
- **Agen sebenarnya hampir selesai.** Kedua patch yang ditulis (pilot3a attempt 0, pilot3a2 attempt 1) gagal karena bug yang sama:
  `scripts/audit_run.py` memanggil `read_result` tanpa mengimpornya (`failure_trace.py` di patch yang sama mengimpor dengan benar).
  Satu baris impor. Yang membunuh attempt adalah anggaran, sebelum agen sempat melihat traceback-nya.
- **Yang mengikat adalah reservasi token kumulatif, bukan uang.** Profil `large` menyimpan 45.000 token, yaitu $0,45 bila setiap
  token dihargai sebagai output ($10/M). Padahal hampir semua token adalah input ($2/M): attempt 0 `pilot3a` memakai 42.951 token
  tetapi hanya membayar **$0,1128**. Proyeksi baseline sampai `Finish` butuh 158.700 token (3,5×) tetapi hanya **$0,35**, di bawah
  $0,45.
- **Tidak ada kebijakan konteks yang membuat attempt ini muat di 45.000 token.** Yang terbaik (batas ListFiles + validasi otomatis)
  masih butuh 77.961 token (1,73×). Dengan admission USD per panggilan ($0,45 per attempt), **semua kebijakan termasuk baseline
  selesai**.
- **Elisi hasil alat lama tidak sepadan sekarang.** Hematnya kecil, agen perlu panggilan baca ulang (satu panggilan ≈ seluruh
  konteks), dan prefix cache rusak sehingga biaya dengan cache justru naik.

## 2. Metode

1. **Kalibrasi.** Selisih token masuk antar langkah = balasan sebelumnya (`output_tokens` di buku besar, eksak) + hasil alat
   (karakter × laju per jenis) + biaya per panggilan. Laju di-fit ke 9 transisi berbeda dari kedua run:

   | Jenis isi | Token/karakter |
   |---|---|
   | ListFiles (daftar jalur) | 0,540 |
   | kode (`ReadFile` .py) | 0,371 |
   | modul data tes | 0,463 |
   | keluaran validasi | 0,502 |
   | hasil kecil (tulis, cari) | 0,243 |
   | per panggilan alat | 50,5 token |

   Galat terbesar 32 token. Karena 6 parameter untuk 9 transisi, fit ini hampir pasti tepat secara konstruksi, jadi bagian 3 juga
   memuat uji sensitivitas laju ±15%. Laju lama di `TOKEN_SIMULATION.md` (0,3186/karakter + 407) terlalu rendah untuk daftar
   berkas dan keluaran tes; itu salah satu alasan simulasi 3a terlalu optimistis. **Koreksi untuk `INVESTIGATION.md` bagian 2–3:**
   ListFiles di sana ditaksir 4.141 token dan modul data 4.817 dengan laju lama; dengan laju yang di-fit ke buku besar keduanya
   ±7.070 dan ±7.050 token, hampir sama besar dan masing-masing lebih mahal dari yang tercatat.
2. **Baseline mereproduksi buku besar persis** untuk 17 panggilan (ok dan ditolak) di kedua run; skrip berhenti bila tidak. Residu
   tiap langkah terbawa ke semua kebijakan, jadi yang ditaksir hanya bagian yang dihapus.
3. **Cek silang:** rekaman attempt 0 + satu validasi + `Finish` = 99.311 token; `INVESTIGATION.md` bagian 3 menaksir 98–99 ribu.
4. **Proyeksi sampai selesai** (attempt yang menulis): validasi gagal dengan keluaran nyatanya (2.502 karakter; `pilot3a` attempt 1
   menjalankan validasi itu pada workspace attempt 0), `EditFile` impor, validasi lulus (1.744 karakter, ekor keluaran regresi yang
   lulus), `Finish`. Kebijakan yang menghapus isi berkas dari konteks menambah satu `ReadFile` `audit_run.py` sebelum penyuntingan.
5. **Asumsi yang harus dibaca bersama hasilnya:**
   - **Trajektori dipaksa:** model dianggap mengambil langkah yang sama walau konteksnya berubah. Konteks yang lebih kecil bisa
     mengubah pilihannya.
   - Keluaran langkah proyeksi: validasi 150, baca 120, sunting 200, `Finish` 250 token (langkah kecil yang terekam: 114–216).
   - Cache: baca 0,1×, tulis 1,25× harga input. **Belum diverifikasi** terhadap daftar harga; tabel harga di repo tidak punya tarif
     cache.
   - Admission meniru harness: ditolak bila masukan + 64 token keluaran tidak muat; `max_tokens` = min(8.192, sisa − masukan).

## 3. Hasil: attempt yang menulis, diproyeksikan sampai `Finish`

`pilot3a` attempt 0 (satu berkas baru + 4 penyuntingan di s2). Kolom "45k" adalah hasil di reservasi sekarang; "USD $0,45" adalah
admission USD per panggilan tanpa reservasi token.

| Kebijakan | Panggilan | Token dibutuhkan | × 45k | USD | USD dgn cache | 3 panggilan pertama | 45k | USD $0,45 |
|---|---|---|---|---|---|---|---|---|
| baseline | 7 | 158.700 | 3,53 | 0,3503 | 0,1412 | 42.951 | ditolak di panggilan 3 | selesai |
| batas ListFiles 2.000 karakter | 7 | 123.067 | 2,73 | 0,2790 | 0,1204 | 31.073 | ditolak di 3 | selesai |
| elisi aman | 8 | 125.469 | 2,79 | 0,2848 | 0,1677 | 35.957 | ditolak di 3 | selesai |
| batas ListFiles + elisi aman | 8 | 119.530 | 2,66 | 0,2729 | 0,1529 | 30.018 | ditolak di 3 | selesai |
| + batas ReadFile 8.000 karakter | 8 | 98.670 | 2,19 | 0,2312 | 0,1327 | 26.541 | ditolak di 4 | selesai |
| elisi umur > 2 langkah (agresif) | 8 | 91.014 | 2,02 | 0,2158 | 0,1633 | 42.951 | ditolak di 3 | selesai |
| validasi otomatis | 5 | 101.716 | 2,26 | 0,2339 | 0,1261 | 42.951 | ditolak di 3 | selesai |
| **batas ListFiles + validasi otomatis** | 5 | **77.961** | 1,73 | 0,1864 | 0,1077 | 31.073 | ditolak di 3 | selesai |

`pilot3a2` attempt 1 (satu berkas + satu penyuntingan) memberi gambaran yang sama: baseline 159.688 token ($0,3456), kebijakan
terbaik 79.333 ($0,1825), semua ditolak di 45k dan semua selesai di admission USD.

Sensitivitas (laju ×0,85 / ×1,15): baseline 157.997 / 159.404; batas ListFiles + validasi otomatis 81.013 / 74.909. Tidak ada
kombinasi yang mendekati 45.000 di kedua ujung, jadi kesimpulannya tidak bergantung pada fit.

Attempt yang menjelajah (`pilot3a` attempt 1, `pilot3a2` attempt 0) tidak bisa diproyeksikan karena tidak menulis. Di 45k,
langkah yang ditolak di `pilot3a2` attempt 0 baru diterima dengan batas ListFiles + elisi aman (sisa 599 token).

Yang dibaca dari tabel:

- **Tiga panggilan pertama sudah memakan 42.951 token**, sebelum ada hasil alat yang basi. Elisi tidak menyentuh bagian ini; hanya
  batas pada sumbernya (ListFiles, ReadFile) yang menyentuhnya.
- **Jumlah panggilan sama pentingnya dengan ukuran konteks**: satu panggilan di tahap ini ≈ 20–30 ribu token. Validasi otomatis
  menghapus dua panggilan (−56.984 token); elisi aman menambah satu panggilan baca ulang dan hampir menghapus manfaatnya sendiri.
- **Elisi merusak cache**: dengan cache, elisi aman lebih mahal dari baseline ($0,1677 vs $0,1412), karena mengganti pesan lama
  membatalkan prefix setelahnya dan menulis ulang cache dengan harga 1,25×.

## 4. Perubahan yang diusulkan (urut prioritas)

Semua mengikuti aturan inti: tes yang gagal di kode lama, mutan, `verify.sh`.

### D1. Reservasi attempt dalam USD, dengan batas konteks per panggilan (harness/llm.py, codetask/run.py, config)

- Attempt dibatasi oleh USD-nya (profil `large` tetap $0,45). Sebelum tiap panggilan harness sudah tahu masukan persis (penghitung
  provider) dan `max_tokens`, jadi kasus terburuk = masukan × harga input + `max_tokens` × harga output. **Batas keras tetap
  terjaga**; yang hilang hanya penetapan harga input sebagai output.
- Reservasi token kumulatif per attempt diganti dengan **batas masukan per panggilan** (`max_input_tokens`, misalnya 32.000; puncak
  baseline di sini 30.057) dan `max_steps` yang sudah ada. Itu batas yang berarti untuk kualitas konteks, bukan proksi biaya.
- `budget.max_tokens` 200.000 di tingkat run juga berupa jumlah kumulatif. Baseline sudah 158.700 untuk satu attempt, jadi ini perlu
  diputuskan bersamaan: dijadikan USD, atau dinaikkan dengan alasan tertulis.
- Tes: attempt yang jumlah tokennya > 45.000 tetapi biayanya < $0,45 diterima di setiap panggilan; panggilan yang kasus terburuk
  USD-nya melebihi sisa ditolak; masukan di atas `max_input_tokens` ditolak dengan alasan tersendiri. Mutan: harga input dan output
  tertukar, suku masukan dihapus, `min_output` meleset satu.
- **Verifikasi gratis:** `replay_3a.py` dengan admission baru. Panggilan `it0 s3` (27.252 token, tercatat di buku besar sebagai
  ditolak) harus diterima. Karena balasannya tidak pernah direkam, responder replay gagal di sana dan harness mengakhiri attempt
  dengan `llm_failed` (pengecualian dibungkus `LLMCallFailed`), dengan `requests_the_live_run_never_made` ≥ 1 (tiap percobaan ulang ikut terhitung), bukan dengan
  `reservation_exhausted`. Itu bukti bahwa batasnya bergeser ke tempat yang benar.

### D2. Umpan balik antar attempt memuat traceback (codetask/agent.py, `feedback_from`)

- Traceback-nya sudah ada di `verdict_0.json` (`evidence.output_tail` dari `validation:inspectors`, `NameError` di
  `audit_run.py` baris 24). `feedback_from` hanya mengambil `reason` (dipotong 300 karakter) dan jumlah tes, jadi traceback-nya
  dibuang.
- Usul: untuk tiap validasi yang gagal, tambahkan blok error pertama dari `output_tail` (dibatasi, misalnya 800 karakter).
- Tes: umpan balik dari `verdict_0` `pilot3a` memuat `NameError: name 'read_result' is not defined` dan `audit_run.py`. Mutan yang
  membuang blok itu harus gagal.
- Catatan: di `pilot3a` attempt 1 agen melihat traceback ini lewat `RunValidation` dan tetap menjelajah. Jadi D2 perlu, tetapi tidak
  menjamin perbaikan; ruang USD dari D1 yang memberi agen kesempatan untuk mencoba.

### D3. Validasi otomatis setelah langkah yang menulis (codetask/agent.py)

- Setelah langkah yang memuat `WriteFile`/`EditFile` yang berhasil, harness menjalankan validasi kontrak dan melampirkan hasilnya
  (dibatasi, error pertama dulu) sebagai pesan harness sesudah `ToolMessage`. Agen tidak perlu menghabiskan panggilan untuk meminta
  validasi, dan traceback langsung sampai di attempt yang sama.
- Dampak di attempt 0 `pilot3a`: 7 → 5 panggilan, 158.700 → 101.716 token, $0,35 → $0,23.
- Crash-resume: hasil validasi otomatis di-commit ke memo dengan kunci sendiri (misalnya `auto_validation`, iterasi, langkah) supaya
  replay tidak menjalankannya ulang. Versinya masuk ke `tool_versions`.
- Yang perlu diukur dulu: waktu sandbox per validasi. Bila mahal, jalankan hanya validasi yang relevan dengan berkas yang berubah.

### D4. ListFiles dibatasi (codetask/tools.py)

- Pohon direktori sampai kedalaman tertentu dengan jumlah berkas per direktori, ±2.000 karakter, dan petunjuk untuk
  `ListFiles(path=...)`. Ubah versi alat (kunci memo memuat versi alat).
- Dampak: 3 panggilan pertama 42.951 → 31.073; total 158.700 → 123.067. Lebih ramah cache daripada elisi karena isinya kecil
  sejak awal, tidak diganti belakangan.
- Pelengkap murah dari H2 (`INVESTIGATION.md`): issue menyebut jalur semua berkas yang relevan.

### D5. Prompt caching (harness/llm.py, models/registry.py, tabel harga)

- Semua panggilan di kedua run tercatat `cache_read: 0`, dan tidak ada `cache_control` di kode. Dengan asumsi tarif di atas, baseline
  $0,35 → $0,14 per attempt yang selesai.
- Perlu: titik cache di pesan terakhir tiap panggilan, tarif `cache_write` di tabel harga (`cost_usd` baru mengenal `cache_read`),
  dan admission yang tetap menganggap tidak ada cache hit (kasus terburuk), sehingga biaya nyata ≤ yang dicadangkan.
- Verifikasi tarif cache terhadap daftar harga sebelum angka di atas dikutip, lalu satu smoke run live yang murah.

### Ditunda

- **Batas ReadFile + rentang baris:** hemat besar di atas kertas (−20.860 token di atas batas ListFiles + elisi), tetapi agen harus
  membaca per halaman; asumsi trajektori-dipaksa paling lemah di sini.
- **Elisi konteks:** lihat bagian 3. Bila nanti dibutuhkan, lakukan di titik pemadatan (hanya bila konteks melewati ambang), sebagai
  fungsi deterministik dari riwayat yang sudah di-commit, dengan versi kebijakan masuk ke `llm_step_key`.

## 5. Dampak ke memo, replay, dan run lama

- `llm_step_key` dan `prompt_hash` dibangun dari isi pesan. D2, D3, dan D4 mengubah pesan, jadi memo run lama tidak cocok lagi
  dengan kode baru. Agar `replay_3a.py` tetap mereproduksi `pilot3a`, perilaku lama perlu bisa dipilih lewat config (versi kebijakan
  konteks), dan replay memakai versi lama.
- D1 tidak mengubah pesan, hanya admission, jadi replay `pilot3a` dengan admission baru tetap berjalan sampai `it0 s3` (lihat D1).

## 6. Urutan kerja yang disarankan

1. **D2 dan D1** (kecil, berbasis tes). Verifikasi lewat replay: `it0 s3` diterima.
2. **D3 dan D4.** Simulasi ulang dengan skrip ini (kebijakan `list_cap+auto_validate`), lalu satu run live dengan kontrak yang sama.
   Dengan admission USD, attempt pertama baseline butuh ±$0,35; cap run $0,75 memberi ruang satu attempt penuh plus sisa kecil.
   Keputusan cap tetap di preflight.
3. **D5** setelah tarif cache diverifikasi.
4. Run live dilaporkan seperti replikasi: jalur langkah, token dan USD per langkah, apakah traceback terlihat, apakah impor
   diperbaiki.
