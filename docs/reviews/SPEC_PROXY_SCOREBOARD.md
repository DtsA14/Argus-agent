# Spek: proxy viewer meneruskan `GET /api/scoreboard`

Status: **keputusan Atha 2026-11-12** ("kalo udah beres langsung go live lagi"; jalur ketat didelegasikan). Temuan: Stage 18 (`pilots/staging_stage18/steps.md`), langkah 5: `/api/scoreboard` lewat 8710 memberi 404 karena proxy
hanya meneruskan empat jalur tetap (`router/stage_viewer.py:76`). Perubahan di sisi Argus, jalur ketat (permukaan yang bisa dibaca dari HP; staging). Tanpa model, tanpa uang.

## 1. Perubahan
Satu jalur API tetap ditambahkan ke daftar yang diteruskan proxy ke ledger Stage 18: **`/api/scoreboard`**, sama persis dengan `/api/summary`: `GET` dan `HEAD`, tanpa parameter, tanpa subpath, tanpa cache (`no-store`), diteruskan
sebagai permintaan sendiri ke `/scoreboard` di soket ledger, header klien tidak diteruskan, metode lain 405. Isinya hanya jumlah job per jenis dan hasil beserta biaya (bukan teks job, judul, atau data per job).
Regex `API`: `^/api/(summary|scoreboard|jobs|jobs/(<id>)(/draft)?)$`. Semua bentuk lain tetap 404 dan tidak pernah diteruskan.

## 2. Tes (gagal di kode lama)
1. `/api/scoreboard` mencapai ledger sebagai `GET /scoreboard`, `200`, `cache-control: no-store`, `application/json`; `HEAD` 200; `POST` 405 dan tidak diteruskan.
2. Setiap bentuk lain 404 dan tidak pernah diteruskan: `/api/scoreboard/`, `/api/scoreboard/x`, `/api/scoreboard?x=1`, `/api/scoreboards`, `/api/Scoreboard`, `/api/scoreboard%00`, `/api//scoreboard`, `/api/scoreboard.json`, `/api/jobs/scoreboard`, `/api/scoreboard/summary`.
3. Tes lama (`summary`, `jobs`, `draft`, dan daftar 404) tetap lulus tanpa diubah, kecuali penyimpanan upstream palsu yang kini menjawab `/scoreboard`.
Mutan: regex tanpa `scoreboard`; `scoreboard` dengan akhiran opsional (`/?`, `s?`); `scoreboard` diizinkan dengan query; upstream path salah; `no-store` dibuang; `HEAD`/`POST` diizinkan beda dari `summary`.

## 3. Setelah digabung
Proxy yang berjalan (unit `systemd --user`) harus dimulai ulang agar memuat regex baru; itu "go live" tersendiri (Atha mengizinkan langsung sesudah PR selesai, 2026-11-12). Lalu rilis viewer S3 dan S4.
