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