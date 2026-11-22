# NEXUS-lite: spek pilot (draf Claude, 2026-11-22)

Status: **draf untuk review Atha. Belum ada repo, belum ada uang keluar, belum ada yang dikirim ke Argus.** Ditulis oleh Claude; tes tersembunyi
juga akan ditulis Claude, jadi mereka hanya menguji kasus yang Claude pikirkan (uji asap, bukan bukti kebenaran).

## 1. Tujuan
Aplikasi riset pribadi satu perangkat: **tangkap lalu temukan kembali.** Masukkan URL, teks, atau catatan; beri tag; simpan permanen di perangkat; cari cepat;
cadangkan dan pulihkan; ekspor project ke Markdown. Dipakai dari HP sebagai PWA (Vercel; Atha yang menghubungkan repo, Argus tidak menyentuh Vercel).

Alasan pilot: Argus membangun repo dari nol, bertahap, dengan kontrak perilaku eksplisit; sekaligus mencari **celah kemampuan frontend** Argus.

## 2. Batasan
- Satu pengguna, satu perangkat, **tanpa backend, tanpa AI, tanpa akun**. Data di IndexedDB.
- **Tidak ada:** klaim/bukti/insight (irisan kedua), dashboard, sinkron antar perangkat, ekstensi browser, integrasi luar.
- Stack: JavaScript (bukan TypeScript), React 19, Vite 6, Tailwind 4, shadcn/ui, vitest 3, vite-plugin-pwa. Environment `nexus_node22` (React 19, fake-indexeddb
  untuk uji penyimpanan). Argus tidak boleh menambah paket di tengah job; paket baru = environment baru.
- shadcn ditambahkan oleh Claude sebagai perancah (CLI-nya butuh jaringan); agen memakainya.

## 3. Kontrak modul (yang dipanggil tes tersembunyi)
Tes tersembunyi hanya memakai modul dan fungsi di bawah. Struktur di dalamnya bebas, selama jalur dan nama ekspor ini ada.

| Jalur | Ekspor | Kontrak |
|---|---|---|
| `src/core/errors.js` | `NexusError` | `Error` dengan properti `code` (string) dan opsional `existingId` |
| `src/core/url.js` | `normalizeUrl(input)` | string → string URL ternormalisasi, atau `null` bila bukan `http`/`https` yang valid |
| `src/core/tags.js` | `normalizeTags(list)` | array string → array unik, huruf kecil, dirapikan; melempar `NexusError` (`INVALID_TAG`) bila lebih dari 10, ada yang kosong, atau lebih dari 30 karakter |
| `src/core/memoryStorage.js` | `memoryStorage()` | penyimpanan di memori untuk tes |
| `src/storage/indexedDbStorage.js` | `indexedDbStorage({ name })` | penyimpanan IndexedDB (tes memakai `fake-indexeddb`); membuka lagi nama yang sama mengembalikan data |
| `src/core/nexus.js` | `createNexus({ storage, now, idGen })` | API asinkron di bawah; `now()` mengembalikan string ISO, `idGen()` mengembalikan id (keduanya opsional, untuk tes) |

Metode `createNexus`: `addItem`, `getItem(id)`, `updateItem(id, patch)`, `deleteItem(id)`, `listItems(opts)`, `search(opts)`, `stats()`,
`exportMarkdown(project)`, `exportSnapshot()`, `importSnapshot(json)`.

Kode galat (`NexusError.code`): `INVALID_INPUT`, `INVALID_URL`, `DUPLICATE_URL` (dengan `existingId`), `NOT_FOUND`, `INVALID_STATUS`, `INVALID_TAG`,
`PROJECT_REQUIRED`, `INVALID_SNAPSHOT`.

## 4. Data dan aturan
**Item:** `id`, `kind` (`url` | `text` | `note`), `title` (wajib, tidak kosong), `body` (teks, boleh kosong), `url` (hanya untuk `url`, disimpan ternormalisasi),
`summary` (ringkasan manual, opsional), `tags` (array), `status` (`inbox` → `filed` → `archived`), `project` (teks bebas atau `null`), `createdAt`, `updatedAt`.
Tag disimpan sebagai relasi (item dan tag terpisah, hubungan banyak-ke-banyak), bukan teks atau JSON di dalam item; ini syarat desain yang diperiksa Claude dengan
membaca, bukan oleh tes.

1. **Tambah:** item baru berstatus `inbox`. `kind` `url` wajib punya `url` valid; `text` dan `note` tidak boleh punya `url`.
2. **Normalisasi URL (konservatif):** host huruf kecil, buang `#fragment`, buang parameter `utm_*`, buang `/` di ujung path (bukan path akar). **Parameter query lain
   tidak disentuh dan urutannya dipertahankan.** Dua URL sama setelah normalisasi dianggap duplikat: `addItem` ditolak dengan `DUPLICATE_URL` dan `existingId`.
3. **Tag:** `normalizeTags`; maksimal 10 per item, 30 karakter per tag.
4. **Status:** `inbox` → `filed` hanya bila `project` terisi (`PROJECT_REQUIRED` bila tidak). `filed` ↔ `archived` boleh dua arah. `archived` → `inbox` tidak boleh
   (`INVALID_STATUS`).
5. **Ubah/hapus:** `updateItem` hanya mengubah bidang yang dikirim, memperbarui `updatedAt`, tidak mengubah `id` atau `createdAt`. Mengubah `url` menjalankan aturan 2 lagi.
   Id yang tidak ada: `NOT_FOUND`.
6. **Cari:** substring, huruf besar/kecil diabaikan, pada `title`, `body`, dan `summary`. Tanpa kata kunci: semua. Filter `tag` (item harus punya tag itu), `project`, `status`.
   Urutan: item yang kata kuncinya ada di `title` dulu, lalu `updatedAt` terbaru, lalu `id`. Hasil `{ items, total }`; `limit` (default 50) dan `offset` (default 0).
7. **Statistik:** `{ total, byStatus: {inbox, filed, archived}, byProject: {nama: jumlah}, unprocessed }` (`unprocessed` = jumlah `inbox`).
8. **Snapshot (cadangan):** `exportSnapshot()` mengembalikan JSON `{ version: 1, exportedAt, items }`. `importSnapshot(json)` memeriksa dulu di tempat sementara (versi,
   bidang, id unik, tanpa URL ganda); lolos → mengganti seluruh isi sekaligus; gagal → `INVALID_SNAPSHOT` dan isi lama tidak berubah.
9. **Ekspor Markdown project:** format tetap (tes membandingkan dengan berkas acuan). Item `status` apa pun dengan `project` itu, urut `createdAt` naik lalu `id`:
   ```
   # Project: {project}

   Diekspor: {now()}

   ## {title}
   - Jenis: {kind}
   - URL: {url}              (baris ini hanya untuk kind url)
   - Tag: {tag1, tag2}       (baris ini hanya bila ada tag)
   - Status: {status}
   - Dibuat: {createdAt}

   Ringkasan: {summary}      (hanya bila ada)

   {body}                    (hanya bila tidak kosong)
   ```
   Antar item satu baris kosong; berkas diakhiri satu baris baru. Project tanpa item: judul dan `Diekspor` saja.
10. **Kecepatan:** `search` pada 500 item dengan penyimpanan memori selesai di bawah 1 detik di lingkungan uji.
11. **Persistensi:** dengan `indexedDbStorage`, item yang ditambah masih ada setelah `createNexus` dibuat ulang dengan nama yang sama.

## 5. Issue inti (urutan; yang bisa diskor)
1. Perancah proyek (Claude: repo, `package.json`, vite, vitest, `.argus/protected`, README) lalu `errors.js`, `memoryStorage`, `createNexus` dengan `addItem`/`getItem`/`listItems`.
2. `normalizeUrl` dan deteksi duplikat (aturan 1–2).
3. `updateItem`, `deleteItem`, `normalizeTags`, aturan status (aturan 3–5).
4. `search` dan filter (aturan 6) beserta uji kecepatan.
5. `stats` (aturan 7).
6. Snapshot (aturan 8).
7. Ekspor Markdown (aturan 9).
8. `indexedDbStorage` (aturan 11).

## 6. Tahap UI/PWA (2–4 issue; tidak diskor, dinilai "dipakai atau tidak" dan daftar celah)
Perancah shadcn, manifest PWA, dan tata letak dasar oleh Claude. Agen mengerjakan: (a) tangkap dan daftar item; (b) detail, ubah, cari, filter; (c) cadangkan dan pulihkan,
statistik. Verifikasi tampilan: Atha lewat URL pratinjau Vercel di HP. **Celah yang diketahui sebelum mulai:** tidak ada tes browser (jsdom saja), service worker dan mode
offline tidak teruji, "mobile-friendly" tidak punya penguji mekanis. Perilaku nyata IndexedDB di Safari iOS perlu dicek di perangkat (yang Claude ketahui: penyimpanan
situs yang tidak dipasang ke layar utama bisa dibersihkan sistem; perlu dikonfirmasi, mitigasi: ekspor snapshot berkala dan `navigator.storage.persist()`).

## 7. Tes tersembunyi (di luar repo, `~/nexus_eval/`, tidak diberikan ke Argus sebelum evaluasi)
Dari angka yang dihitung tangan: (1) skenario AI Business Opportunities (1 project, 10 sumber, 5 catatan; hasil pencarian per kata kunci dan tag, jumlah per status);
(2) tujuh URL menyamar (huruf besar host, `/` di ujung, `utm_*`, fragment) yang harus dianggap sama, dan tiga yang berbeda (query lain, path beda); (3) tag: 11 tag,
tag 31 karakter, tag kosong, duplikat setelah dirapikan; (4) aturan status; (5) urutan hasil cari; (6) snapshot: ekspor, impor ke penyimpanan kosong, hasil sama persis;
snapshot rusak ditolak dan isi lama tetap; (7) ekspor Markdown dibandingkan dengan berkas acuan; (8) persistensi IndexedDB (buat ulang `createNexus`); (9) kecepatan 500 item.
Tes ditulis dan dijalankan lebih dulu terhadap implementasi acuan kecil buatan Claude (untuk memeriksa tesnya sendiri), lalu implementasi acuan dihapus.

## 8. Ukuran
1. Tes tersembunyi lulus (%). 2. Issue yang harus diulang. 3. Keputusan di tengah (PENDING, "Angka bisa ditinggal"; dibedakan antara yang butuh manusia dan yang bisa dijawab dengan membaca repo).
4. Biaya total. 5. Atha masih memakainya setelah 3 hari (dan jawaban tiga pertanyaan: berapa banyak yang dikelola, apakah menemukan kembali lebih mudah, apakah membantu keputusan).

## 9. Langkah sebelum mulai
Atha me-review spek ini → Claude menulis tes tersembunyi dan implementasi acuan → Atha menyetujui pembuatan repo privat di GitHub (`nexus-lite`) → Claude membuat perancah, mendaftarkan repo di
`config.yaml` (`issue_writer.repos`, environment `nexus_node22`) lewat satu PR → PRD per issue lewat jalur biasa (uang tiap antrean ditanyakan dulu).

## 10. Yang belum diputuskan (default Claude, bisa diubah Atha)
Nama repo `nexus-lite`; JavaScript, bukan TypeScript; format Markdown di aturan 9; batas 10 tag dan 30 karakter; `limit` default 50.
