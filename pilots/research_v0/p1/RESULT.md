# Pilot research v0 #1: issue 013 (argus-ledger), dua lengan

2026-10-29, 11:57–12:05 UTC (18:57–19:05 WIB, off-peak; semua panggilan `peak: false`). "Go live" Atha. Harness `main`
8223574 (PR #242, SPEC_RESEARCH_STAGE). Model DeepSeek V4.1 Flash (thinking). Environment `ledger_py312`
(starlette 1.8.0, fastapi 0.143.0).

Issue 013: dengan `allowed_hosts=["www.dashboard.example"]`, `Host: dashboard.example` dijawab 307 ke www, padahal
README menjanjikan 400. Issue hanya menulis gejala; nama parameter Starlette tidak disebut.

| | A: `--research` | B: tanpa riset |
|---|---|---|
| job | `j20261029_115742_bffd` | `j20261029_120123_9cf3` |
| r1 riset | RESEARCHED, 10 panggilan, 3 halaman, 1 submit lolos gate, $0,0056 | — |
| d1 drafter | DRAFTED, $0,0111 | DRAFTED, $0,0051 |
| a1 agen | DONE, 1 attempt, 4 langkah, $0,0012 | DONE, 1 attempt, 9 langkah, $0,0034 |
| total | **$0,0179** | **$0,0085** |
| fix | `www_redirect=False` | `www_redirect=False` (identik) |
| hasil | APPLIED (argus-ledger `804e13a`, tes 120 → 124) | REJECTED (lengan pembanding, fix sama) |
| keputusan Claude | research-ok, approve, applied (3) | approve, reject (2) |

## Handoff (A)

`handoff.json` dan `HANDOFF.md` di folder ini. Verdict SUPPORTED, `starlette==1.8.0`, 5 kutipan dari
`starlette.dev/middleware/`, `starlette.dev/release-notes/` dan `fastapi.tiangolo.com/tutorial/middleware/`, semuanya lolos
gate di submit pertama. Isinya benar: dicek Claude terhadap source `TrustedHostMiddleware` yang terpasang (default
`www_redirect=True`, redirect hanya bila `"www." + host` ada di daftar). Ketidakpastian ditulis jujur: halaman middleware
adalah dokumentasi "latest", bukan khusus 1.8.0, dan teks `Invalid host header` tidak ada di dokumentasi.

## Temuan

1. **Riset tidak mengubah hasil untuk bug ini.** Drafter B, tanpa riset, sudah menulis `www_redirect=False` di
   rencananya dari ingatan model; agen B sampai ke fix yang sama. Sama seperti pilot K7: untuk API yang umum, model
   sudah tahu. A dua kali lebih mahal ($0,018 vs $0,0085), tetapi keduanya sangat murah.
2. **Yang A tambahkan adalah bukti, bukan jawaban:** kutipan yang dicek harness dan ketidakpastian versi. Untuk review
   manusia ini nilai tambah (B mengklaim "documented" tanpa bukti), tetapi tidak terukur dari status DONE.
3. **Gate bekerja di jalur nyata:** 3 halaman diambil, 5 kutipan lolos G1–G3 tanpa penolakan; agen A memakai 4 langkah
   (B 9), mungkin karena issue A sudah membawa perubahan yang direkomendasikan.
4. Kecil: `fetched` di `HANDOFF.md` ditulis sebagai epoch mentah (`1793275071.118654`); lebih mudah dibaca sebagai UTC.

## Langkah berikutnya (usul, belum diputuskan)

Uji Alur A butuh bug yang jawabannya **tidak** ada di ingatan model: perilaku yang baru berubah di rilis terbaru
(misalnya starlette 1.x yang sudah melewati batas pengetahuan model), atau dependency yang jarang. Tanpa itu, `--research`
tetap opsional dan bernilai sebagai bukti untuk reviewer.
