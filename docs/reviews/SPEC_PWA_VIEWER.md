# Spek: aplikasi kedua di staging, viewer argus-ledger (React PWA) yang ditulis agen

Status: **disetujui Atha 2026-10-30** (keputusan §7, tambahan §8; PR 1 dirinci di §9). Jalur ketat untuk harness (§2 V, §3 E, §4 S);
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

**V3. Daftar tes** (`collect_nodes`): hanya dipakai `changed_tests`, yang ditolak untuk vitest di v0 (§9); jadi **tidak dibuat** di PR 1. Tes baru yang tidak terkumpul tetap tertangkap: baseline menyebut node wajib yang tidak berjalan ("was not collected").

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

## 7. Keputusan Atha (2026-10-30)

1. **Proxy selalu hidup** (`systemd --user`), dengan syarat **bind eksplisit hanya ke `127.0.0.1`** dan tidak bisa
   diakses dari jaringan publik.
2. **Port 8710.**
3. **Repo `argus-viewer` lokal saja.**
4. **Dua PR terpisah:** PR 1 runner Vitest dan environment, PR 2 staging dan proxy. Keduanya jalur ketat, **tidak
   di-merge sebelum approval Atha**. Staging/proxy tidak disentuh sebelum PR 1 selesai direview.
5. Docs React/Vite untuk agen **belum** dibuka sampai ada kebutuhan nyata.

## 8. Tambahan pengamanan Atha (dijamin dan dites; mutants)

**A1. API proxy: hanya GET, allowlist eksplisit.** Tepat tiga bentuk path: `/api/summary`, `/api/jobs`,
`/api/jobs/<id>` dengan `<id>` sesuai pola job Argus; tanpa query string; selain itu 404, selain GET/HEAD 405 (PR 2).

**A2. Header forwarding dari client tidak dipercaya.** `X-Forwarded-*`, `Forwarded`, `X-Real-IP` dan sejenisnya
diabaikan, tidak pernah diteruskan. Proxy membuat request baru ke socket ledger dengan header miliknya sendiri
(`Host` tetap yang diterima ledger); tidak ada header client yang ikut. Keputusan akses hanya dari alamat listen
(`127.0.0.1`) dan `Host` (S2) (PR 2).

**A3. PWA tidak menyimpan data API/job di browser.** Tiga lapis:
- Respons `/api/*` membawa `Cache-Control: no-store` (cache HTTP browser tidak menyimpan) (PR 2).
- `sw.js` ditulis Claude di kerangka, dilindungi scope, hanya meng-cache daftar app shell tetap; staging menolak
  rilis yang `sw.js`-nya berbeda dari versi yang direview (sha tercatat) (PR 2).
- Build dipindai: kemunculan `localStorage`, `sessionStorage`, `indexedDB`, `caches.` atau `CacheStorage` di luar
  `sw.js` → rilis ditolak. (Cek awal: bundle React 19 tidak memuat satu pun.) Batasnya ditulis: pemindaian teks
  tidak menangkap akses yang disamarkan (`window["local" + "Storage"]`); lapis ini menangkap pemakaian biasa, bukan
  niat jahat, dan kode aplikasi tetap direview di jalur cepat (PR 2).

**A4. Validasi artifact build** (S1, PR 2): setiap entri `dist` diperiksa tanpa mengikuti link: symlink, hardlink
(`st_nlink > 1`), device/fifo/socket → ditolak; nama path hanya `[A-Za-z0-9._-]` per segmen, tanpa `..`, tanpa
segmen diawali titik, kedalaman ≤ 4; ekstensi dalam allowlist dan isi cocok tipe (HTML/JS/CSS/JSON/manifest UTF-8
valid; PNG/ICO dengan magic bytes); ukuran per berkas ≤ 2 MB dan total ≤ 5 MB; jumlah berkas ≤ 200.

**A5. Termius lewat SSH port forwarding, 8710 tidak terekspos.**
- Proxy bind `127.0.0.1` secara eksplisit (bukan `0.0.0.0`, bukan `localhost` yang bisa resolve ke `::`);
  smoke memeriksa lewat `ss -ltnH` bahwa satu-satunya listener di port 8710 adalah `127.0.0.1:8710` (PR 2).
- Tidak ada perubahan firewall/iptables/security list OCI; port tidak pernah dibuka ke publik.
- Panduan Termius untuk Atha (di pilot): *Port Forwarding → Local*, host = VM lewat SSH, **bind address di HP
  `127.0.0.1`** (bukan `0.0.0.0`, supaya perangkat lain di Wi-Fi yang sama tidak bisa memakai forward-nya), port
  lokal 8710 → tujuan `127.0.0.1:8710`.

## 9. PR 1 secara rinci (runner Vitest dan environment)

Cek mekanisme (Claude, scratchpad): vitest dijalankan **secara programatik** oleh skrip milik harness
(`node --input-type=module -e SCRIPT nonce file...`, memanggil `startVitest` dari `/node_modules/vitest` dengan
reporter perekam milik harness), setara plugin pytest red check: hasilnya JSON di belakang nonce, bukan teks yang
di-parse. Perekam memberi per tes: status, tipe error (`AssertionError` vs `TestingLibraryElementError`), berkas
`/workspace` teratas di stack, pesan; per modul: error impor. Nama dengan spasi dan `describe` (` > `) terbaca. Mode
`collect` (`createVitest().collect`) memberi daftar tes tanpa menjalankannya.

**Temuan:** filter berkas vitest mencocokkan **substring** (`src/App` menjalankan `src/App.test.jsx`). Jadi hasil
dipercaya hanya bila himpunan modul yang berjalan **sama persis** dengan berkas yang diminta; selain itu gagal
tertutup.

Isi PR 1:
- Hasil PR 1 (Claude): image `pwa_node22` distroless (node + library + `/node_modules`, tanpa shell/npm/git), rootfs sama di dua build (id image tidak, seperti environment Python); `check_env_image.py pwa_node22` 6/6 PASS.
- `acceptance/validation.py`: bentuk kontrak `{"executable": "vitest", "args": ["run", FILE, ...]}` (V1, tanpa `-t`
  di v0); satu skrip harness untuk validasi dan red check; `judge_result`, `collect_nodes`, `red_check` memilih
  runner dari `kind()`; record red check berbentuk sama dengan pytest (`outcome`, `type`, `assertion`, `path`,
  `message`, `message_names`, `repo_paths`), jadi gate draf yang ada dipakai apa adanya.
- `acceptance/contract.py`: node id vitest `FILE::NAMA` (boleh spasi, tanpa baris baru, ≤ 300 karakter); `no_skip`
  tetap hanya pytest.
- `acceptance/draft.py`: tes baru `*.test.js|jsx|ts|tsx` untuk environment ber-runner vitest, `test_*.py` untuk
  pytest; `changed_tests` **ditolak** untuk vitest di v0 (perbandingan AST hanya Python; tes lama tidak bisa diubah,
  hanya ditambah tes baru), dicatat sebagai batas.
- `codetask/drafter.py`, `codetask/agent.py`: teks runner dan bentuk perintah dari `runner` environment; potongan
  error vitest untuk agen.
- Environment `pwa_node22` (§3), `scripts/build_env_node.sh`, cek di `scripts/check_env_image.py`, `config.yaml`
  (`runner: vitest`; environment tanpa `runner` = pytest seperti sekarang).
- E1 (dependency repo ⊆ lock environment) **pindah ke PR 2** (build rilis): di PR 1 paket yang tidak ada di image membuat berkas tes gagal dimuat, dan itu sudah gagal tertutup dengan pesan yang menyebut impornya. Fixture `vitest_demo` dites cocok dengan lock.
- Tes: unit (parser, judge, kontrak, draf) + integrasi di sandbox nyata dengan repo contoh (lulus, gagal karena
  assertion, gagal bukan assertion, impor gagal, filter substring, skip). Docker tidak tersedia = tes tidak lulus.

## 10. PR 2 secara rinci (staging dan proxy)

Isi (Claude, 2026-10-30), `router/stage_viewer.py`, tes `tests/test_stage_viewer.py`, fixture `fixtures/repos/viewer_demo`:
- Perintah: `argus stage viewer-deploy <job> [--yes]`, `viewer-rollback [--yes]`, `viewer-status`, `viewer-smoke`,
  `argus stage proxy` (unit `deploy/systemd/argus-stage-proxy.service`, **belum dipasang**: dipasang di pilot sesudah
  "go live"). Monitor 15 menit ikut menjalankan smoke viewer bila ada rilis viewer yang live.
- Area sendiri `~/argus-staging/apps/viewer/` (`releases/`, `current`, `state.json`, `releases.jsonl`): perintah viewer
  tidak pernah menulis state/rilis argus-ledger atau menyalakan/mematikan container, dan sebaliknya (dites, §6.7).
- Job viewer = job `APPLIED` apa adanya dengan environment `pwa_node22`. E1 dan cek workspace (tanpa `node_modules`,
  tanpa `package.json`/`.npmrc` bersarang) **sebelum** build; build di container tanpa jaringan, root dan workspace
  read-only, `/out` satu-satunya mount writable, uid host, batas memori/pids/cpu.

Keputusan Claude dalam batas spek (untuk dicek Atha):
1. **sha `sw.js` yang direview = konstanta `SW_SHA256` di kode**. Awalnya `None` (semua rilis ditolak); dipin ke
   `public/sw.js` kerangka `argus-viewer` 505e23b (`db58777a…`, network-first, tidak pernah `/api/`) lewat PR pin (jalur
   ketat). `fixtures/repos/viewer_demo/public/sw.js` = salinan persisnya.
2. **Gerbang deploy/rollback:** rilis kandidat di-smoke lewat proxy yang sama (kode yang sama) di port ephemeral
   `127.0.0.1` **sebelum** `current` di-swap; smoke live di 8710 (termasuk `ss -ltnH`) lewat `viewer-smoke` dan monitor,
   tidak menggerbang deploy (proxy belum dipasang sebelum pilot).
3. **Berkas yang tidak ada:** `index.html` hanya untuk rute aplikasi (segmen terakhir tanpa titik, atau berakhir `/`);
   berkas ber-ekstensi yang tidak ada → 404 (lebih ketat dari S2: aset hilang tidak dijawab HTML).
4. Jawaban ledger diteruskan hanya bila status 200/404, `Content-Type` JSON, JSON valid dan ≤ 1 MB; selain itu 502.
   Ledger tidak live → 503. Path statis membawa `Cache-Control: no-cache` (bukan `no-store`): pembaruan rilis langsung
   terlihat, data API tetap `no-store`.
5. `localhost:8710`/`127.0.0.1:8710` persis satu header `Host`; dua header `Host` → 421. Request yang tidak bisa
   di-parse `http.server` (400/414) juga membawa header keamanan.
