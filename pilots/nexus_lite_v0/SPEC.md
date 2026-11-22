# NEXUS-lite: spek pilot (revisi 2, 2026-11-22; draf Claude untuk review Atha)

Status: **draf untuk review Atha. Belum ada repo, belum ada uang keluar, belum ada yang dikirim ke Argus.** Revisi 2 menjawab tinjauan Opus (GO WITH CHANGES, 25 temuan; 5 yang utama:
tanda tangan metode yang pasti, normalisasi URL dengan tabel, aturan tag/status/snapshot/Markdown yang lengkap, urutan issue dan antarmuka penyimpanan yang ditulis di issue, perancah
dengan konfigurasi tes terpisah). Spek dan tes tersembunyi ditulis Claude, jadi tes hanya menguji kasus yang Claude pikirkan (uji asap, bukan bukti kebenaran).

## 1. Tujuan
Aplikasi riset pribadi satu perangkat: **tangkap lalu temukan kembali.** Masukkan URL, teks, atau catatan; beri tag; simpan permanen di perangkat; cari cepat; cadangkan dan pulihkan;
ekspor project ke Markdown. Dipakai dari HP sebagai PWA di Vercel (Atha menghubungkan repo; Argus tidak menyentuh Vercel). Pilot ini juga mencari **celah kemampuan frontend** Argus.

## 2. Batasan
- Satu pengguna, satu perangkat, **tanpa backend, tanpa AI, tanpa akun**; data di IndexedDB. Tidak ada klaim/bukti/insight (irisan kedua), dashboard, sinkron, ekstensi, integrasi luar.
- Stack: JavaScript (bukan TypeScript), React 19, Vite 6, Tailwind 4, shadcn/ui (`components.json` `"tsx": false`), vitest 3, vite-plugin-pwa. Environment `nexus_node22`.
- **Paket yang boleh dipakai agen** hanyalah yang ada di `environments/nexus_node22/package.json`. Tidak ada `idb`, `uuid`, atau `react-router`; paket baru = environment baru, tidak dipasang di tengah job.
- Claude menyiapkan perancah (CLI shadcn butuh jaringan): repo, `package.json` dan lockfile **disalin dari `nexus_node22`** (Vercel dan sandbox memakai versi yang sama), `vite.config.js` untuk aplikasi dan
  **`vitest.config.js` terpisah** (jsdom, alias `@`, `vitest.setup.js` dengan stub `ResizeObserver`, `hasPointerCapture`, `scrollIntoView`, `matchMedia` yang tidak dimiliki jsdom), `.argus/protected`
  yang tidak cocok dengan jalur tes agen (`src/**/*.test.js`), komponen shadcn awal, manifest PWA. Perancah satu commit sebelum PRD pertama; issue hanya berisi kode.

## 3. Kontrak (yang dipanggil tes tersembunyi)
Tes tersembunyi hanya memakai jalur, nama, dan perilaku di bagian 3 dan 4. Struktur di dalamnya bebas. Semua kasus tepi yang dipakai tes tercantum sebagai contoh di spek ini.

**Umum.** `normalizeUrl` dan `normalizeTags` sinkron. `createNexus`, `memoryStorage`, dan `indexedDbStorage` mengembalikan nilai secara sinkron (basis data IndexedDB dibuka malas pada pemanggilan
pertama); semua metode `createNexus` mengembalikan Promise. `now` bawaan `() => new Date().toISOString()`; `idGen` bawaan `crypto.randomUUID`. Global `indexedDB` dibaca saat basis data dibuka, bukan saat modul dimuat.
Semua galat adalah `NexusError` (`src/core/errors.js`) dengan properti `code`, dan `existingId` untuk `DUPLICATE_URL`. Kode: `INVALID_INPUT`, `INVALID_URL`, `DUPLICATE_URL`, `NOT_FOUND`, `INVALID_STATUS`,
`INVALID_TAG`, `PROJECT_REQUIRED`, `INVALID_SNAPSHOT`.

| Jalur | Ekspor | Perilaku |
|---|---|---|
| `src/core/errors.js` | `NexusError` | lihat di atas |
| `src/core/url.js` | `normalizeUrl(input)` | bagian 4.2 |
| `src/core/tags.js` | `normalizeTags(list)` | bagian 4.3 |
| `src/core/memoryStorage.js` | `memoryStorage()` | penyimpanan memori |
| `src/storage/indexedDbStorage.js` | `indexedDbStorage({ name })` | penyimpanan IndexedDB; `createNexus` baru dengan nama sama melihat data lama |
| `src/core/nexus.js` | `createNexus({ storage, now, idGen })` | metode di bawah |

**Metode `createNexus`:**
- `addItem({ kind, title, body = '', url, summary = null, tags = [], project = null })` → item lengkap. Bidang lain (termasuk `status`, `id`) → `INVALID_INPUT`. Item baru berstatus `inbox`.
- `getItem(id)` → item, atau `NOT_FOUND`. `deleteItem(id)` → `undefined`, atau `NOT_FOUND`.
- `updateItem(id, patch)` → item baru. Patch boleh berisi `title`, `body`, `url`, `summary`, `tags`, `project`, `status`; bidang lain, termasuk `id`, `createdAt`, `updatedAt`, `kind` → `INVALID_INPUT`.
- `listItems()` → array semua item, urut `createdAt` naik lalu `id` naik (perbandingan string biasa).
- `search({ q, tag, project, status, limit = 50, offset = 0 })` → `{ items, total }`; `total` dihitung sebelum `limit` dan `offset`.
- `stats()`, `exportMarkdown(project)`, `exportSnapshot()`, `importSnapshot(x)`.

## 4. Aturan
### 4.1 Item
`id`, `kind` (`url` | `text` | `note`), `title`, `body`, `url`, `summary`, `tags` (array), `status` (`inbox` | `filed` | `archived`), `project` (string atau `null`), `createdAt`, `updatedAt`.
Urutan pemeriksaan di `addItem`/`updateItem` (galat pertama yang menang): `kind` (tidak dikenal: `INVALID_INPUT`) → `title` (setelah `trim()` tidak boleh kosong atau mengandung baris baru: `INVALID_INPUT`) →
`url` (`text`/`note` dengan `url`: `INVALID_INPUT`; `url` tanpa `url` atau tidak valid: `INVALID_URL`) → `tags` → duplikat URL. `project` di-`trim()`; `''` menjadi `null`. Duplikat memeriksa semua item **kecuali item itu sendiri**.
Tag disimpan sebagai relasi (koleksi `items`, `tags`, `itemTags`), bukan teks atau JSON di dalam item.

### 4.2 Normalisasi URL
`input` bukan string → `null`. `trim()`, lalu `new URL(...)`; gagal parse, atau protokol bukan `http:`/`https:` → `null`. Kosongkan `hash`. Dari string `search` mentah, pisahkan pada `&`; buang pasangan yang
**kuncinya** (sebelum `=`) diawali `utm_` (huruf kecil persis); pasangan lain dipertahankan **byte demi byte dan urutannya**; bila tak ada yang tersisa, `?` dibuang. Bila `pathname` bukan `/`, buang **satu** `/` di ujung.
Userinfo dipertahankan. Hasil: `url.href`. Contoh (dihitung dengan `new URL` di Node 22; tes hanya memakai kasus dari tabel ini):

| Masukan | Hasil |
|---|---|
| `https://a.com` | `https://a.com/` |
| `HTTPS://A.com:443/x/?b=2&utm_source=y&a=1#f` | `https://a.com/x?b=2&a=1` |
| `http://a.com:80/` | `http://a.com/` |
| `https://a.com/a/` | `https://a.com/a` |
| `https://a.com/a//` | `https://a.com/a/` |
| `https://a.com/?utm_source=x` | `https://a.com/` |
| `https://a.com/p?utm_source=x&UTM_medium=y` | `https://a.com/p?UTM_medium=y` |
| `https://a.com/p?a=1&utm_x=2` | `https://a.com/p?a=1` |
| `https://a.com/p?q=a%20b&x` | `https://a.com/p?q=a%20b&x` |
| `https://a.com/p#top` | `https://a.com/p` |
| `  https://a.com/p  ` | `https://a.com/p` |
| `https://a.com/p/?` | `https://a.com/p` |
| `https://user:pw@a.com/x` | `https://user:pw@a.com/x` |
| `https://b.com/p?id=1` dan `https://b.com/p?id=2` | berbeda (bukan duplikat) |
| `ftp://x`, `not a url`, `''`, `javascript:alert(1)` | `null` |

### 4.3 Tag
`normalizeTags(list)`: bukan array → `INVALID_TAG`; `[]` boleh. Tiap elemen: bukan string → `INVALID_TAG`; `trim()` lalu `toLowerCase()` (spasi di dalam dipertahankan); kosong → `INVALID_TAG`;
`.length` lebih dari 30 → `INVALID_TAG`. Hapus duplikat dengan mempertahankan urutan kemunculan pertama; **lebih dari 10 setelah duplikat dibuang** → `INVALID_TAG`. Hanya ASCII yang diuji.
Filter `tag` di `search` melewati `trim()` dan `toLowerCase()` yang sama.

### 4.4 Status (lewat `updateItem`)
Boleh: `inbox→filed` (hanya bila `project` bukan `null` setelah patch digabung), `filed→archived`, `archived→filed`, `filed→inbox`, sama→sama. Tidak boleh: `inbox→archived`, `archived→inbox` (`INVALID_STATUS`).
Nilai status tidak dikenal: `INVALID_STATUS`. Mengosongkan `project` pada item `filed`/`archived`: `PROJECT_REQUIRED`. `status` dan `project` boleh diubah dalam satu patch. `updateItem` memperbarui `updatedAt`.

### 4.5 Cari
Huruf kecil dengan `toLowerCase()`; substring pada `title`, `body`, `summary` (URL dan tag tidak dicari). `q` kosong setelah `trim()` = tanpa kata kunci. Filter yang `undefined` tidak dipakai; `project: null` cocok dengan item tanpa project.
Urutan: item yang kata kuncinya ada di `title` dulu, lalu `updatedAt` turun (perbandingan string; `now()` harus berformat `toISOString`), lalu `id` naik (perbandingan kode unit `<`, bukan `localeCompare`). Tanpa kata kunci tahap judul dilewati.

### 4.6 Statistik
`stats()` → `{ total, byStatus: { inbox, filed, archived }, byProject: { nama: jumlah }, unprocessed }`. `byStatus` selalu memuat ketiga kunci (boleh 0). `byProject` melewati project `null` dan menghitung semua status.
`unprocessed` = jumlah `inbox`.

### 4.7 Snapshot (cadangan)
`exportSnapshot()` → objek biasa `{ version: 1, exportedAt: now(), items }`, `items` urut `createdAt` lalu `id`. `importSnapshot(x)` menerima objek atau string JSON (gagal parse: `INVALID_SNAPSHOT`). Diperiksa dulu di tempat sementara:
`version` tepat 1; tiap item lolos aturan 4.1 dan 4.4 dan `url`-nya sudah sama dengan `normalizeUrl(url)`; `id` unik; URL unik. Lolos → mengganti seluruh isi sekaligus, mempertahankan `id`/`createdAt`/`updatedAt`
tanpa memanggil `now` atau `idGen`. Gagal → `INVALID_SNAPSHOT` dan isi lama tidak berubah. Ekspor setelah impor sama persis dengan yang diimpor, kecuali `exportedAt`.
Di `indexedDbStorage`, penggantian isi harus **satu transaksi `readwrite` atas semua koleksi**, dan kegagalan di dalamnya memanggil `abort()`.

### 4.8 Ekspor Markdown
`exportMarkdown(project)`: `project` kosong atau bukan string → `PROJECT_REQUIRED`. Cocok persis dengan `project` item; semua status; urut `createdAt` naik lalu `id`. Blok digabung dengan `\n\n`; berkas diakhiri tepat satu `\n`.
Baris `URL` hanya untuk `kind` `url`; `Tag` hanya bila ada tag; `Ringkasan` hanya bila `summary` string tidak kosong setelah `trim()`; isi `body` hanya bila tidak kosong setelah `trim()`, dicetak apa adanya.
Keluaran acuan, untuk `now()` = `2026-01-10T00:00:00.000Z` dan dua item (satu `url` berstatus `filed` dengan tag `ai`, `bisnis` dan ringkasan, satu `note` berstatus `inbox` dengan isi), sebagai string JS:

```
"# Project: AI Business\n\nDiekspor: 2026-01-10T00:00:00.000Z\n\n## Peluang agen AI\n- Jenis: url\n- URL: https://example.com/ai\n- Tag: ai, bisnis\n- Status: filed\n- Dibuat: 2026-01-02T00:00:00.000Z\n\nRingkasan: Ringkas.\n\n## Catatan rapat\n- Jenis: note\n- Status: inbox\n- Dibuat: 2026-01-03T00:00:00.000Z\n\nIsi catatan.\n"
```
Project tanpa item: `"# Project: X\n\nDiekspor: <now>\n"`.

### 4.9 Kecepatan dan penyimpanan
`search` pada 500 item dengan `memoryStorage` selesai di bawah 1 detik di lingkungan uji. Persistensi dibuktikan terhadap `fake-indexeddb` (simulasi API di Node), bukan Safari asli.

## 5. Issue inti (urutan; yang bisa diskor)
Tiap issue berbunyi "implementasikan HANYA ini, jangan buat yang lain" dan contohnya menyentuh perilaku yang baru di issue itu (supaya draf tidak lolos di basis dan gerbang draf tidak berakhir `NO_DRAFT`).
1. Modul murni: `errors.js`, `normalizeUrl` (tabel 4.2), `normalizeTags` (4.3).
2. Antarmuka penyimpanan dan `memoryStorage` (koleksi `items`, `tags`, `itemTags`, dan `replaceAll` atomik, ditulis di issue); `createNexus` dengan `addItem`, `getItem`, `listItems`, pemeriksaan 4.1 dan duplikat URL.
3. `updateItem`, `deleteItem`, dan matriks status 4.4.
4. `search` dan filter (4.5); jangkar issue pada tes urutan dan filter, uji kecepatan hanya tambahan.
5. `stats` (4.6).
6. Snapshot (4.7) dengan `memoryStorage`.
7. `exportMarkdown` (4.8).
8. `indexedDbStorage` (4.7 transaksi tunggal, 4.9) dengan `fake-indexeddb`; tes lingkungan `node` memakai `import 'fake-indexeddb/auto'`.

## 6. Tahap UI/PWA (2–4 issue; tidak diskor, dinilai "dipakai atau tidak" dan daftar celah)
Perancah, manifest PWA, service worker, dan gaya dasar oleh Claude (tidak bisa punya tes gagal di basis). Agen mengerjakan, tiap kali dengan tes komponen (`@testing-library/react` + jsdom) yang gagal di basis: (a) tangkap dan daftar item; (b) detail, ubah, cari, filter; (c) cadangkan,
pulihkan, statistik. Atha memeriksa tampilan lewat URL pratinjau Vercel di HP.
**Celah yang diketahui sebelum mulai:** tidak ada tes browser (jsdom saja); service worker dan mode offline tidak teruji; "mobile-friendly" tidak punya penguji mekanis.
**Perangkat iOS (pemahaman Claude, belum diverifikasi di perangkat):** aplikasi yang dipasang ke layar utama memakai penyimpanan terpisah dari Safari (data di tab Safari tidak muncul di aplikasi terpasang); batas tujuh hari
untuk penyimpanan situs berlaku untuk situs di peramban, bukan aplikasi layar utama; menghapus ikon menghapus data; sistem tetap bisa membersihkan bila ruang habis; `navigator.storage.persist()` mungkin tidak memberi `true` di iOS; unduhan `<a download>` di mode
mandiri tidak selalu andal (cadangan: Web Share dengan berkas, atau tampilkan JSON untuk disalin). Aturan pakai: **pasang ke layar utama lebih dulu dan pakai hanya aplikasi terpasang**; tombol cadangan diuji di perangkat pada minggu pertama; hasil `persist()` ditampilkan di layar statistik.

## 7. Tes tersembunyi (di luar repo, `~/nexus_eval/`, tidak diberikan ke Argus sebelum evaluasi)
Dari angka yang dihitung tangan, hanya memakai kasus yang tercantum di spek ini: (1) skenario AI Business Opportunities (1 project, 10 sumber, 5 catatan; hasil cari per kata kunci dan tag, jumlah per status);
(2) tabel URL 4.2; (3) tag: 11 unik, 11 dengan duplikat yang jadi 10, 31 karakter, kosong, huruf besar; (4) matriks status; (5) urutan hasil cari dan tie-break; (6) snapshot: ekspor, impor ke penyimpanan kosong, ekspor ulang sama;
rusak ditolak dan isi lama tetap (pada `memoryStorage`, ditambah satu bolak-balik di IndexedDB); (7) Markdown dibandingkan dengan string acuan di 4.8; (8) persistensi IndexedDB (buat ulang `createNexus`); (9) kecepatan 500 item.
Cara menjalankan saat evaluasi: salin `~/nexus_eval/*.test.js` ke `<klon>/eval_hidden/` lalu `vitest run eval_hidden` di image `nexus_node22`, dengan `// @vitest-environment node` dan `import 'fake-indexeddb/auto'`.
Tes ditulis dan dijalankan lebih dulu terhadap implementasi acuan kecil buatan Claude (memeriksa tesnya sendiri), lalu implementasi acuan dihapus.

## 8. Ukuran
1. Tes tersembunyi lulus (%). 2. Issue yang harus diulang. 3. Keputusan di tengah (PENDING, "Angka bisa ditinggal"; dibedakan antara yang butuh manusia dan yang bisa dijawab dengan membaca repo).
4. Biaya total. 5. Atha masih memakainya setelah 3 hari (dan tiga pertanyaan: berapa banyak yang dikelola, apakah menemukan kembali lebih mudah, apakah membantu keputusan).

## 9. Langkah sebelum mulai
Atha me-review spek ini → Claude menulis tes tersembunyi dan implementasi acuan → Atha menyetujui pembuatan repo privat di GitHub (`nexus-lite`) → Claude membuat perancah, mendaftarkan repo di `config.yaml`
(`issue_writer.repos`, environment `nexus_node22`) lewat satu PR → PRD per issue lewat jalur biasa (uang tiap antrean ditanyakan dulu).

## 10. Default Claude yang belum diputuskan Atha
Nama repo `nexus-lite`; JavaScript; format Markdown di 4.8; batas 10 tag dan 30 karakter; `limit` bawaan 50; label `project` tidak mengharuskan status `filed` saat item dibuat; cadangan lewat Web Share/salin bila unduhan tidak andal.
