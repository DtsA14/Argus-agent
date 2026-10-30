# Spek: aplikasi kedua di staging, viewer argus-ledger (React PWA) yang ditulis agen

Status: **draf** (Claude, 2026-10-30), menunggu keputusan Atha (§7). Jalur ketat untuk harness (§2 V, §3 E, §4 S);
jalur cepat untuk aplikasinya (§5). Menutup gap: M6 "JS belum bisa divalidasi" (bulking-app terhalang di sini), M9
"satu aplikasi", agen di repo baru, dan untuk pertama kalinya hasil agen bisa **dipakai** Atha di HP, bukan hanya
dibaca angka smoke-nya. Tahap 3b (Playwright/Chromium) **tidak** termasuk.

## 1. Cek awal (Claude, 2026-10-30, scratchpad, repo tidak disentuh)

- Image `node:22-bookworm-slim` dipin digest (`node@sha256:4b150b48…`, Node 22.23.4). React 19.1.0, vite 6.3.5,
  @vitejs/plugin-react 4.4.1, vitest 3.1.4, jsdom 26.1.0, @testing-library/react 16.3.0 dan dom 10.4.0, semua jauh
  lebih tua dari 2 minggu. `package-lock.json`: 201 paket, semuanya dengan hash `integrity`; `npm ci --ignore-scripts`
  memeriksanya saat build image (satu-satunya langkah dengan jaringan).
- `node_modules` (72 MB, image 440 MB) di **`/node_modules`**, read-only, induk dari `/workspace`: resolusi Node dan
  vite naik ke sana, jadi workspace tetap read-only dan tanpa symlink.
- Dengan aturan sandbox sekarang (`--network none`, root read-only, `cap-drop ALL`, `no-new-privileges`, uid 1001,
  workspace `:ro`, `/tmp` tmpfs): `vitest run` 1,6 s (2 lulus, 1 gagal karena assertion, sesuai tes);
  `vite build` 1,2 s; `vitest list --json` memberi daftar tes; tidak ada berkas tertulis di workspace.
- **Temuan:** secara default vite menulis `node_modules/.vite-temp` saat memuat config → gagal di read-only. Dengan
  `--configLoader runner` dan cache/output di `/tmp` lolos. Opsi ini dipilih harness, bukan repo.
- `--reporter=json` memberi per tes: berkas, nama lengkap, status, pesan gagal. `NO_COLOR=1`: tanpa kode ANSI.
- `vite build` dua kali: hash seluruh `dist` **identik**.

## 2. V: validasi vitest di harness

**V1. Bentuk perintah baru** di `acceptance/validation.py`, di samping unittest dan pytest:
`vitest run FILE [FILE ...] [-t NAME]` (bentuk kontrak, executable `vitest`; FILE path relatif berakhiran `.test.js|.test.jsx|.test.ts|
.test.tsx`, tanpa `..`). Dijalankan sebagai
`node /node_modules/vitest/vitest.mjs run --configLoader runner --reporter=json --no-cache --root /workspace FILE ...`
dengan `NO_COLOR=1`, `HOME=/tmp`. Opsi selalu milik harness; kontrak tidak bisa menambah plugin, reporter, atau config.

**V2. Penilaian dari JSON reporter.** Node id = `FILE::NAMA_LENGKAP` (nama lengkap vitest, describe dipisah ` > `).
Karena dibaca dari JSON, **node id vitest boleh berisi spasi** (pytest tetap tidak). Hasil dipercaya hanya bila
jumlah per status sama dengan `numPassedTests/numFailedTests/numPendingTests/numTotalTests`, setiap berkas yang diminta
ada di hasil, dan JSON berada di akhir output; selain itu **gagal tertutup**. `skipped`/`todo` dihitung seperti skip
pytest (`no_skip`). Batasnya sama dengan pytest dan ditulis di docstring: kode yang dites berjalan di proses yang sama
dan bisa memalsukan output; ditahan oleh sandbox dan berkas tes yang dilindungi scope.

**V3. Daftar tes** (`collect_nodes`): `vitest list --json --configLoader runner FILE ...` → node id seperti V2.

**V4. Merah karena assertion** (W2a, drafter): tes baru wajib gagal karena `AssertionError` (dari `expect`/`assert`)
dan baris gagal teratas berada di berkas tes itu. Error lain (mis. `TestingLibraryElementError` dari `getByText`,
`TypeError`, import gagal) **bukan** merah yang sah, sama seperti pytest. Dicek dari `failureMessages` dan stack.

**V5. Agen dan drafter tahu runner-nya dari environment**, bukan dari teks tetap: environment punya
`runner: pytest|vitest`. Prompt, petunjuk, dan potongan error untuk agen (`codetask/agent.py`: untuk vitest, pesan
gagal + lokasi pertama di `/workspace`, maks. panjang yang sama) mengikuti runner. Fungsi pytest tidak berubah.

## 3. E: environment `pwa_node22`

`environments/pwa_node22/`: `base` (digest Node), `package.json` + `package-lock.json` (pengganti `requirements.txt`),
README. Dibangun `scripts/build_env_node.sh pwa_node22` (dua tahap: `npm ci --ignore-scripts` dengan jaringan, lalu
`node_modules` disalin read-only ke `/node_modules` di image dari base yang sama; tanpa cache npm). Dicek
`scripts/check_env_image.py pwa_node22`: versi Node, `/node_modules` read-only dan berisi tepat versi di lock, vitest
dan vite jalan tanpa jaringan dengan tes contoh bawaan harness. `config.yaml`: `runner: vitest`, image id dipin seperti environment lain. **Tidak** di
`web.environments`.

**E1. Dependency repo harus cocok dengan environment.** `package.json` repo (dependencies + devDependencies) harus
**subset persis** (nama dan versi) dari lock environment; selain itu intake dan validasi ditolak dengan pesan yang
menyebut paketnya. Agen tidak bisa memasang paket (tanpa jaringan); paket baru = environment baru (`*_up1`, alur U).

## 4. S: staging aplikasi statis

**S1. Rilis = build dari commit applied**, di container `pwa_node22` tanpa jaringan: workspace = `git archive`
commit (dicek terhadap tree, seperti sekarang), `:ro`; output `vite build --configLoader runner --outDir /out` ke
direktori build harness di luar tempat publikasi. Sesudah build: hanya berkas biasa (tanpa symlink), ekstensi dalam
allowlist (`.html .js .css .webmanifest .json .svg .png .ico .txt`), ukuran total ≤ 5 MB, pemindaian pola key,
`index.html` ada. Lolos → direktori dibuat read-only lalu dipublikasikan dengan swap symlink atomik
(`~/argus-staging/apps/viewer/current`), seperti snapshot data. Image dan hash `dist` tercatat per rilis.
`rollback` = swap ke rilis sebelumnya. Gagal di langkah mana pun → rilis live tidak berubah.

**S2. Proxy lokal** (harness, stdlib Python, **bukan** kode agen): mendengar **hanya di `127.0.0.1:<port>`**.
- `GET /api/summary`, `/api/jobs`, `/api/jobs/<id>` → diteruskan ke socket argus-ledger yang live, dengan cek
  `S_ISSOCK` dan SO_PEERCRED yang sudah ada; selain path itu 404. Hanya JSON.
- `GET` path lain → berkas dari `current` (path dinormalisasi, tanpa `..`, tanpa mengikuti symlink; tidak ada →
  `index.html` untuk rute SPA).
- Selain `GET`/`HEAD` → 405. `Host` harus `localhost:<port>` atau `127.0.0.1:<port>`, selain itu 421 (cegah DNS
  rebinding dari situs lain di browser HP).
- Header: `Content-Security-Policy: default-src 'self'; connect-src 'self'; img-src 'self' data:; object-src
  'none'; base-uri 'none'; frame-ancestors 'none'`, `X-Content-Type-Options: nosniff`, `Referrer-Policy: no-referrer`.
- Tidak ada penulisan apa pun; tidak ada port lain; tidak pernah port 8000.

**S3. Smoke viewer:** `/` 200 berisi `index.html` rilis; aset yang dirujuk `index.html` ada dan hash-nya sama dengan
yang tercatat; `/api/summary` = angka harness dari snapshot (D3 SPEC_STAGING_REAL_DATA); `Host: evil.example` → 421;
`POST /` → 405; `/../x` dan `/api/x` → 404. Monitor 15 menit (yang sudah ada) ikut menjalankan smoke ini tanpa
mengubah rilis.

**S4. Akses dari HP:** port forwarding Termius (lokal HP → `127.0.0.1:<port>` VM lewat SSH). Service worker PWA
sah di `localhost`, jadi tanpa DNS/TLS. Belum diuji (butuh HP Atha); diuji di pilot.

## 5. Aplikasi: `argus-viewer` (jalur cepat)

- Repo lokal baru `~/argus-viewer`, seperti `argus-ledger`. **Kerangka awal ditulis Claude** (package.json yang cocok
  E1, `vite.config.js`, `index.html`, manifest, service worker yang hanya meng-cache app shell, `App.jsx` kosong, satu
  tes): drafter butuh tes yang bisa merah karena assertion, dan impor modul yang belum ada bukan merah yang sah (V4).
  `vite.config.js`, manifest, dan `sw.js` dilindungi scope.
- Issue berikutnya ditulis Claude (format issue argus-ledger), "go live" per job dari Atha, Claude approve dan commit:
  001 daftar job + biaya + total dari `/api/jobs` dan `/api/summary`; 002 detail job (tahap, keputusan); 003 tampilan
  HP (layout sempit, pull to refresh). Viewer **hanya membaca**.
- **Data tidak di-cache service worker**: hanya app shell; data selalu diambil baru (yang tampil = snapshot terkini).

## 6. Yang dijamin (dites; mutants)

1. Perintah vitest hanya bentuk V1; opsi kontrak lain ditolak; hasil yang tidak cocok dengan hitungan → gagal.
2. Merah tes baru hanya karena `AssertionError` di berkas tes (V4).
3. Validasi vitest: tanpa jaringan, workspace read-only, `/node_modules` read-only (dicek seperti sandbox sekarang).
4. Dependency repo di luar lock environment → ditolak (E1).
5. Build rilis tanpa jaringan; berkas di luar allowlist, symlink, ukuran berlebih, atau pola key → rilis ditolak dan
   yang live tetap.
6. Proxy: hanya `127.0.0.1`, hanya GET/HEAD, Host dicek, path di luar `current` dan `/api` yang diizinkan tidak
   pernah terbaca, socket hanya ke container rilis (peer pid).
7. `rollback` viewer tidak menyentuh argus-ledger dan sebaliknya.

## 7. Keputusan untuk Atha

1. **Proxy selalu hidup** (`systemd --user`, restart otomatis) atau **hanya saat dipakai** (`argus stage serve`,
   mati sendiri sesudah N menit)? Saran Claude: selalu hidup; eksposurnya sama (hanya `127.0.0.1`, dan siapa pun yang
   punya shell di VM sudah bisa membaca semuanya).
2. **Port**: saran `8710` (bukan 8000).
3. **Nama repo** `argus-viewer`, lokal saja seperti `argus-ledger`?
4. **Urutan PR (jalur ketat):** PR 1 = V + E (runner vitest dan environment); PR 2 = S (rilis statis, proxy, smoke);
   lalu kerangka repo dan issue 001 (jalur cepat). Pilot staging: satu `PLAN.md`, satu "go live".
5. Dokumentasi React/vite untuk `ReadDocs` agen (`web.hosts`): **belum** (saran Claude), dibuka bila agen terbukti
   kekurangan.
