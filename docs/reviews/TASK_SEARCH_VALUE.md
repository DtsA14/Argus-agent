# Task untuk mengukur nilai tambah `search_files`: desain (untuk review sebelum fixture)

Status: desain disetujui untuk lanjut ke fixture (review PR #55, dengan catatan yang sudah dimasukkan di bawah),
2026-10-16. Belum ada fixture, kontrak, atau run.

Latar: di live #7 (`shop_coupon_leak`) agen menyelesaikan task tanpa memakai `SearchFiles`. Nama folder dan nama tes
target sudah menunjuk ke modul yang relevan. Jadi pertanyaan "apakah pencarian membantu" masih terbuka. Yang terungkap
adalah kelemahan benchmark itu, bukan kelemahan agen.

Tujuannya **mengukur nilai tambah** pencarian, bukan memaksa tool dipakai. Task harus tetap bisa diselesaikan tanpa
pencarian, hanya lebih mahal.

## 1. Repo `fixtures/repos/ledger/` (sekitar 40 modul, 2–3 KB per modul)

Layanan tagihan kecil. **Nama path sengaja netral** dan tidak menunjuk ke bug: `core/`, `common/`, `jobs/`,
`plugins/`, `adapters/`, `util/`, dengan nama modul seperti `pipeline.py`, `options.py`, `stages.py`, `nightly.py`,
`live.py`.

**Bug (informasi tersebar di tiga tempat):**
- **Kontrak fungsi:** `common/options.py` punya `merge_options(base, override)` dengan docstring "values in override win".
  Fungsinya benar.
- **Konfigurasi:** `config/schedules.json` berisi default per jadwal. Jadwal `eu` punya `grace_days: 14` sebagai
  override dari default `30`.
- **Perilaku pemanggil:** `jobs/nightly.py` memanggil `merge_options(schedule_override, defaults)`, dengan argumen
  tertukar. Akibatnya default menimpa override, dan akun jadwal `eu` dihitung dengan grace 30 hari. `jobs/live.py`
  (dipakai dashboard) memanggilnya dengan benar.

Baris yang salah terlihat wajar kalau dibaca sendiri: kedua argumen adalah dict, dan tidak ada parameter yang tidak
dipakai. Bug baru terlihat setelah kontrak `merge_options` dihubungkan dengan pemanggilnya.

**Decoy yang sama-sama masuk akal:**
- dua kalkulator denda (`plugins/fee_a.py` dan `plugins/fee_b.py`, salah satunya tidak dipakai);
- modul pembulatan;
- adapter ekspor CSV.

Kata `late_fee` dan `grace_days` muncul di banyak modul, sehingga pencarian kata umum menghasilkan banyak baris yang
terpotong.

**Issue (gejala saja, tanpa nama file):** "In the nightly export, accounts on the EU schedule are charged a late fee
two weeks too late (the dashboard shows the right due date). Fix it. Do not change the tests."

**Peluang nyata bagi pencarian (didokumentasikan di sini, tidak diberitahukan ke agen):** `SearchFiles("grace_days")`
atau `SearchFiles("merge_options(")` mempersempit pencarian ke beberapa file. Tanpa pencarian, nama path tidak membantu
dan agen harus membaca banyak modul. Itu mungkin dilakukan, tapi lebih mahal.

## 2. Validasi (sama ketatnya dengan task lain)

- **Tes regresi** (dilindungi, lulus sekarang): jadwal default, dashboard (`live`), pembulatan, ekspor CSV, dan
  **perilaku umum `merge_options`**: key yang hanya ada di base tetap ada, key yang hanya ada di override ditambahkan,
  override menang kalau bentrok, dan kedua input tidak dimutasi.
- **Tes target** tidak hanya membandingkan tiga angka yang sudah diketahui. Untuk **setiap** jadwal di
  `config/schedules.json`, ekspor nightly harus sama dengan jalur `live`. Selain itu, beberapa nilai literal diuji.
- Tes target (dilindungi, gagal sekarang) mencakup jadwal `eu`, jadwal default, dan jadwal ketiga yang juga punya
  override.
- **Perbaikan referensi:** urutan argumen di `jobs/nightly.py`.
- **Naskah keliru (tambalan dangkal):** hardcode `grace_days = 14` untuk `eu` di nightly. Ini harus gagal di tes target
  untuk jadwal ketiga yang juga punya override. Kalau tidak gagal, desain tesnya yang salah.
- **Mutan validasi** yang meloloskan tambalan dangkal → benchmark `BROKEN`.
- **Varian yang diukur sebelum dipakai:** bug, referensi, tambalan dangkal, dan alternatif sah (misalnya memakai
  keyword argument).
- **Guard kebocoran label:** issue tidak boleh menyebut nama file, fungsi, maupun kata yang hanya ada di jalur bug.

## 3. Tiga kondisi sebagai varian kontrak (tanpa perubahan harness)

Repo dan tesnya sama. Yang berbeda hanya kontraknya. Semua varian disimpan di manifest eksperimen terpisah
(`evals/search_v1/manifest.json`, lewat `--manifest`), bukan di benchmark utama v1, sampai hasilnya konsisten.

| Kondisi | Kontrak | Pertanyaan |
|---|---|---|
| A. search tersedia, bebas | `"tools": ["search_files"]`, issue apa adanya | Apakah agen memakai pencarian secara alami? |
| B. search tersedia + instruksi netral | sama, ditambah satu kalimat di issue: "The repository is large; you can search file contents with SearchFiles." | Apakah pencarian membantu kalau dipakai? |
| C. search nonaktif | tanpa `tools` | Apakah hasilnya menurun tanpa pencarian? Semua tool lain tetap ada |

**Semantik C, dipastikan:** kontrak tanpa `tools` hanya **tidak menambah** `search_files`. Allowlist efektifnya adalah
allowlist config `coder`, yaitu `list_files, read_file, write_file, run_validation` ditambah `Finish`. Jadi C hanya
kehilangan pencarian, bukan kemampuan melihat daftar file, membaca, menulis, atau menjalankan validasi. Ini sudah
perilaku harness sekarang (kontrak tanpa `tools` berjalan identik dengan sebelum PR #52), dan dibuktikan per run:
`tools_effective` dan `result.json` untuk C harus persis empat tool itu, sedangkan untuk A dan B ditambah
`search_files`. Pengecekan ini dijalankan di mode `reference` untuk ketiga varian sebelum live.

**Cara membaca perbandingan:** A vs B adalah efek **instruksi** untuk memakai pencarian, bukan efek pencarian semata.
A vs C adalah efek **ketersediaan** pencarian, termasuk keputusan agen untuk memakainya atau tidak.

**Catatan:** B mengubah teks issue, jadi hash kontraknya berbeda. Perbedaan itu dicatat sebagai variabel eksperimen.
Ini cara termurah dan tidak menyentuh prompt sistem maupun harness. Alternatifnya, varian prompt per kontrak, adalah
perubahan harness, dan aku sarankan tidak dikerjakan dulu.

**Kriteria penerimaan sebelum fixture dipakai (masing-masing ditegakkan oleh tes):**
1. **Kesetaraan tugas:** kontrak A, B, dan C identik kecuali `tools` (C tanpa field itu) dan satu kalimat instruksi B.
   Repo, tes, scope, validasi, dan batas sama persis.
2. **Anti-bocor:** issue A, B, dan C tidak menyebut nama file, nama fungsi, maupun kata yang hanya ada di jalur bug.
   Selisih issue B dan A harus **persis** kalimat instruksi yang ditetapkan. Kalimat itu hanya menyebut nama tool dan
   tidak memuat petunjuk solusi apa pun, sehingga tidak ada informasi tentang bug yang tersedia di B tapi tidak di A.
3. **Simulasi realistis:** model palsu membaca beberapa file per langkah (3, seperti live #7) dengan strategi yang
   masuk akal, misalnya `config/` dan `jobs/` dulu, atau menelusuri dari tes target. Pola satu file per langkah
   tidak dipakai sebagai satu-satunya pembanding.

## 4. Urutan kerja

1. Fixture + kontrak + tes, lalu ukur varian kode (bug, referensi, dangkal, alternatif). Mode `reference` dan `wrong`,
   plus mutan. Biaya nol.
2. Ukur dengan model palsu, seperti `measure_context shop`. Pertama, tanpa pencarian dengan pola baca yang realistis
   (**3 file per langkah**, pilihan file dari nama path, sesuai live #7). Kedua, dengan pencarian efektif. Syaratnya:
   kondisi tanpa pencarian harus **mungkin** selesai dalam 30.000 token kalau pilihannya beruntung, tapi lebih mahal.
   Kalau tidak mungkin sama sekali, task ini mengukur kapasitas, bukan nilai pencarian, dan desainnya diubah.
3. PR, review, lalu verify.
4. Rencana live terpisah untuk disetujui: misalnya 3 kondisi × 3 ulangan = 9 run. Estimasi kasar $0.05–0.12 per run,
   jadi sekitar $0.45–1.10 total, dengan cap per run $0.50 dan cap total yang disetujui. Tiga ulangan masih kecil, jadi
   hasilnya dilaporkan sebagai rentang per kondisi (sukses, token, jumlah tool call, file dibaca, lokasi perbaikan),
   bukan klaim signifikansi. Ini eksperimen eksploratif. Per run dicatat: token, file yang dibaca, pemakaian
   pencarian, hasil tes, dan apakah patch benar di akar masalah.

## 5. Batas yang dinyatakan

- Satu task. Kesimpulannya terbatas pada jenis bug ini, yaitu kontrak + konfigurasi + pemanggil.
- Agen sungguhan tetap bisa membaca `config/` lebih dulu dan menebak. Itu jalur diagnosis yang sah dan akan dilaporkan.
EOF
git add docs/reviews/TASK_SEARCH_VALUE.md && git commit -q -F - <<'EOF'
Design draft: a task to measure the value of search_files (neutral paths, spread information, three contract variants)

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
EOF
git push -q -u origin task-search-design 2>&1|tail -1; gh pr create --base main --head task-search-design --title "Design: task to measure the value of search_files (draft for review)" --body "Design only, no fixture, code or run. See \`docs/reviews/TASK_SEARCH_VALUE.md\`. Follows live #7, where the agent finished \`shop_coupon_leak\` without using SearchFiles. Open questions for review: the bug (caller swaps \`merge_options\` arguments; contract + config + caller), the three conditions as contract variants in a separate experiment manifest (no harness change), and a 3 × 3 live plan to be approved separately.

🤖 Generated with [Claude Code](https://claude.com/claude-code)"
## 6. Hasil fixture pertama (`fixtures/repos/ledger`, branch `fixture-search-value`, biaya nol)

**Penyimpangan dari desain:** bug dipindah dari `jobs/nightly.py` ke `core/ledger.py` (`prepare_lines` memanggil
`merge_options(plan, base)`). Alasannya, tes target harus mengimpor titik masuknya. Kalau bug ada di titik masuk,
file tes sudah menunjuk langsung ke sana.

**Varian kode (tes regresi 8, tes target 5):**

| Varian | Hasil |
|---|---|
| bug | 5 tes target gagal |
| referensi `merge_options(base, plan)` | lulus |
| alternatif sah dengan keyword argument | lulus |
| tambalan dangkal `eu` | 4 tes target gagal (tes `eu` sendiri lulus) |
| jalur halaman akun ikut dibuat salah | 4 tes target gagal |

**Mode eval:**
- `reference` A/B/C: DONE. Tool efektif dari `result.json` dan `tools_effective`: A/B lima tool, C empat tool.
- Di C, panggilan `SearchFiles` dijawab "Denied" dan tercatat sebagai `tool_denied`.
- `wrong`: tertangkap hanya pada `issue_fixed`.

**Mutan, semua tertangkap:**
- Validasi yang selalu lulus → ketiga varian `BROKEN`.
- Petunjuk di B, nama fungsi di issue, `tools` di C, dan batas C yang berbeda → tes guard gagal.

**Simulasi model palsu (3 tool per langkah, sandbox asli):**

| Strategi | Kontrak | Hasil | Token |
|---|---|---|---|
| tanpa search, ikuti impor dari tes target | C | DONE | **15.982** |
| tanpa search, baca direktori yang terdengar relevan | C | `reservation_exhausted` ×2 | 28.226 / 29.215 |
| search "efektif" | A | DONE | 19.889 |
| search kata umum dulu | A | DONE | 29.761 (nyaris batas) |

**Temuan yang mengubah desain.** Jalur termurah ternyata **tanpa** search: dari tes target ikuti impor `cycle.py` →
`ledger.py` → `options.py`. Nama path yang netral tidak menghalanginya, karena impor eksplisit menunjuk ke file
berikutnya. Naskah "search efektif" juga tidak realistis: ia mencari `merge_options(`, padahal nama itu baru terlihat
setelah `ledger.py` dibaca.

Jadi dalam bentuk sekarang, search tidak punya keunggulan nyata atas agen yang mengikuti impor. A vs C kemungkinan
hanya mengukur strategi baca agen, bukan nilai search. Fixture ini **belum** dipakai untuk live. Keputusan desain
berikutnya menunggu review.

## 7. Revisi desain (untuk review; fixture belum diubah)

### 7.1 Registry langkah yang masuk akal secara produk

Run overnight menjadi pipeline yang langkahnya diatur lewat konfigurasi. Ini pola yang umum:
- `src/config/pipeline.json` berisi `"overnight": ["load_open", "resolve_terms", "assess_fees", "to_rows"]`;
- setiap langkah mendaftarkan diri dengan dekorator `@step("resolve_terms")`;
- `core/pipeline.py` mengimpor semua modul di `src/steps/` (auto-discovery) lalu menjalankan langkah sesuai urutan
  config.

Polanya sama dengan rute Flask, perintah Click, atau operator di pipeline data. Alasan produknya: urutan langkah per
lingkungan bisa diubah tanpa mengubah kode.

**Bug:** tetap `merge_options(plan, base)`, sekarang di langkah `resolve_terms` di `src/steps/prepare.py`.
`src/steps/` berisi 8 modul langkah bernama netral (`apply`, `batch`, `compat`, `finalize`, `prepare`, …),
masing-masing sekitar 2 KB (8, bukan 10: lihat 7.5). Satu modul `compat` berisi `resolve_terms_v1` yang tidak terdaftar di config, sebagai decoy.

**Tidak ada lagi jalur dua lompatan impor:** tes → `jobs/cycle.py` → `core/pipeline.py`. Dari sana jejaknya berupa
**nama string** di config, bukan impor.
- **Jalur wajar tanpa search:** baca `pipeline.py` dan config (keduanya terlihat dari impor), lalu baca modul di
  `src/steps/` sampai menemukan `@step("resolve_terms")`.
- **Jalur dengan search:** cari string `resolve_terms`, yang sudah terlihat di config, lalu baca satu modul.

### 7.2 Kondisi setara

Definisi A/B/C tetap seperti bagian 3:
- A: search tersedia;
- B: search tersedia + satu kalimat netral;
- C: tanpa search, semua tool lain ada.

Bug, kriteria penerimaan, budget, batas attempt, repo, dan tes sama persis, dan ditegakkan oleh tes kesetaraan yang
sudah ada. Yang berbeda hanya akses tool (dan karena itu daftar tool di prompt sistem, yang tidak terhindarkan) serta
kalimat B. Naskah model palsu hanya mencari string yang sudah terlihat di konteksnya.

### 7.3 Temuan dari prediksi: search punya biaya tetap yang besar

Prediksinya memakai kalibrasi dan diambil dari panggilan nyata live #7: biaya tetap 1.790 token, `ListFiles` 640 token,
dan output sekitar 250 token per panggilan. Satu panggilan `SearchFiles` adalah **satu panggilan model tambahan**,
yang mengirim ulang seluruh percakapan (4–6 ribu token di titik itu). Membaca satu modul 2 KB hanya menambah sekitar
640 token per panggilan berikutnya.

Disapu untuk 4–12 modul langkah berukuran 1–3 KB, dengan budget 30.000:
- kalau baseline membaca **semua modul sekaligus**, search lebih murah hanya di sedikit kombinasi, dan selisihnya
  paling banyak sekitar 10%. Itu sebesar galat kalibrasi;
- kalau baseline membaca **3 per langkah** (pola live #7), search jelas lebih murah, tapi di hampir semua kombinasi
  itu baseline-nya sudah melewati 30.000.

Artinya, dengan budget 30.000, "search menang" hampir selalu bertepatan dengan "baseline kehabisan budget". Persis itu
yang tidak boleh kita sebut nilai search.

Prediksi untuk desain 7.1 (10 modul × 2 KB, ±10%):

| Strategi | Prediksi token |
|---|---|
| search string yang terlihat | ~27.000 |
| search kata umum dulu, satu file salah | ~46.600 |
| tanpa search, semua modul langkah sekaligus | ~33.000 |
| tanpa search, 3 per langkah, bug di batch 2 | ~34.900 |
| tanpa search, 3 per langkah, bug terakhir | ~60.500 |

### 7.4 Pilihan

1. **Budget eksperimen yang sama dan cukup untuk semua kondisi (usulku).**
   - Run eksperimen ini memakai config eksperimen lewat `--config`, tanpa perubahan harness: `attempt_tokens` 60.000
     untuk A, B, dan C sekaligus.
   - Konsekuensinya: reservasi satu attempt menjadi 60.000 × tarif tertinggi. Dengan harga output Sonnet di config ($10 per
     juta), itu $0.60 per attempt, padahal sekarang $0.30. Cap kontrak sekarang $0.50, jadi satu attempt pun tidak
     akan diterima. Cap per run harus dinaikkan ke sekitar $1. Itu perlu persetujuan biaya tersendiri.
   - Dengan begitu tidak ada kondisi yang gagal karena budget, dan nilai search terlihat sebagai token, file yang
     dibaca, dan langkah pada anggaran yang sama.
   - Status dengan 30.000 tetap dilaporkan dari simulasi, sebagai informasi terpisah.
2. **Tetap 30.000.** Selisih token yang diharapkan sebesar galat kalibrasi, dan kegagalan baseline akan bercampur
   dengan efek budget. Hasilnya sulit ditafsirkan.
3. **Tunda eksperimen search.** Catat temuannya: dengan pengiriman ulang kumulatif, satu panggilan tool tambahan
   seharga membaca beberapa file kecil. Jadi search hanya jelas bernilai di repo yang memang tidak bisa dibaca
   dengan budget ini. Pengungkit yang lebih besar mungkin biaya per panggilan, tapi itu perubahan harness dan di luar
   scope sekarang.

Keputusan diminta sebelum fixture diubah.

### 7.5 Keputusan review: budget eksperimen 60.000 untuk A/B/C, prediksi sebelum fixture

Dua pertanyaan dipisah:
- **Efisiensi** (apakah search mengurangi token dan file yang dibaca) diukur dengan `attempt_tokens` 60.000 yang sama
  untuk A, B, dan C.
- **Kemampuan dalam batas operasional** (apakah selesai dengan 30.000) dilaporkan terpisah dari simulasi 30.000.

**Semua angka di bawah adalah estimasi, bukan hasil terukur.** Kalibrasinya `407 + 0,3186 × karakter` (galat ≤ 10%),
dengan biaya tetap dan biaya `ListFiles` dari live #7 dan output sekitar 250 token per panggilan. Harga dari config:
Sonnet 5.5 input $2 per juta, output $10 per juta. Jika attempt pertama kehabisan reservasi, diasumsikan attempt kedua
mengikuti rencana yang sama lalu berhenti stagnan, seperti di simulasi sebelumnya. Skrip prediksinya: `scripts/predict_search_value.py`.

**Ukuran `src/steps/` diubah dari 10 ke 8 modul × 2 KB.** Dengan 10 modul, strategi terburuk C (3 per langkah, bug di
batch terakhir) diprediksi butuh sekitar 60.500 token, jadi gagal juga di 60.000. Itu melanggar syarat bahwa semua
kondisi punya kesempatan setara di 60.000. Dengan 8 modul, strategi terburuk diprediksi 46.600, dengan sisa sekitar
13.000.

**Strategi yang dimodelkan:**
- search string yang terlihat: `ListFiles` → baca tes, `cycle.py`, `pipeline.py`, config → `SearchFiles("resolve_terms")`
  → baca `prepare.py` dan `options.py` → tulis + validasi → `Finish`;
- search kata umum dulu: seperti di atas, didahului `SearchFiles("late fee")` dan dua file yang salah;
- tanpa search: modul langkah dibaca sekaligus, atau 3 per langkah dengan bug di batch 2 atau di batch terakhir.

| Metrik (estimasi) | A: search tersedia | B: search + kalimat netral | C: tanpa search |
|---|---|---|---|
| Strategi yang diasumsikan | search string yang terlihat; kalau agen tidak mencari (seperti live #7), sama dengan C | search string yang terlihat (search kata umum dulu sebagai kasus buruk) | sekaligus / 3 per langkah, bug di batch 2 / bug di batch terakhir |
| Total token (60k) | 27.100 (tidak mencari: 30.400–46.600) | 27.100 (kasus buruk 46.600) | 30.400 / 34.900 / 46.600 |
| Biaya aktual (60k) | $0.066 (tidak mencari: $0.071–0.107) | $0.066 (kasus buruk $0.109) | $0.071 / $0.082 / $0.107 |
| Panggilan model | 6 | 6 (kasus buruk 8) | 5 / 6 / 7 |
| File dibaca | 6 | 6 (kasus buruk 8) | 13 / 11 / 13 |
| Status pada 30k | DONE dengan sisa sekitar 3.000; tidak mencari → gagal | DONE; kasus buruk gagal | gagal di ketiganya (2 × `reservation_exhausted`, biaya $0.093–0.119) |
| Status pada 60k | DONE | DONE | DONE di ketiganya |
| Token per task sukses (diagnostik) | sama dengan total token | sama dengan total token | sama dengan total token |

**Reservation guard bukan biaya.** Admission mencadangkan `attempt_tokens` × tarif tertinggi (output $10 per juta)
per attempt:
- untuk 30.000, cadangannya $0.30;
- untuk 60.000, cadangannya $0.60, padahal biaya aktual yang diprediksi hanya $0.07–0.11 per run.

Karena cap kontrak sekarang $0.50, attempt 60.000 akan ditolak sebelum panggilan pertama (`FAILED_BUDGET`). Untuk
**simulasi** (biaya nol), salinan kontrak sementara yang ditulis skrip memakai cap yang sama tinggi untuk A, B, dan C,
sehingga guard tidak menentukan hasil. Fixture dan kontrak di repo tidak berubah. Cap untuk live tetap keputusan
terpisah dan belum disetujui.

**Yang diprediksi dan aturan berhenti:**
- Penghematan search terhadap C bergantung pada cara agen membaca tanpa search:
  - sekitar 11% kalau semua modul langkah dibaca sekaligus. Itu sebesar galat estimasi;
  - sekitar 22% kalau 3 per langkah dengan bug di batch 2;
  - sekitar 42% kalau bug di batch terakhir.
- Prediksi B sama dengan A yang mencari. A bisa saja tidak mencari, dan justru itu yang ingin dilihat.
- Sesuai review: kalau pada 60.000 search hanya menghemat dalam galat estimasi (≤ 10%), eksperimen dihentikan dan
  dicatat bahwa nilai tambahnya belum terbukti.

**Metrik.** Tiga metrik milestone berikutnya adalah tingkat sukses task, biaya per task sukses, dan tingkat kegagalan
yang jujur. Token per task sukses hanya metrik diagnostik untuk eksperimen ini.

**Urutan:** review prediksi ini → ubah fixture → simulasi 30.000 dan 60.000 → evaluasi apakah layak menjadi fixture.
Belum ada PR, kenaikan cap, atau live run.
