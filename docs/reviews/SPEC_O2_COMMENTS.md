# Spek: O2 tidak menangkap teks yang tidak bisa jalan (komentar dan docstring Python)

Status: 2026-11-13, dari bacaan Fable atas `e892d5a` ("pola O2 masih terlalu lebar"). Jalur ketat: gerbang deteksi (`scope:no_test_detection`) bisa menghentikan job, jadi melonggarkannya
adalah perubahan strict. Berlaku AGENTS.md: tes gagal di kode lama, mutants, review, satu `verify_at`, "merge" Atha. Tanpa model, tanpa uang.

## Ukuran dulu

Gerbang dijalankan pada berkas non-tes dari repo yang kita tangani, di `~/argus-viewer` (5 berkas), `~/argus-ledger` (7), boltons (34) dan more-itertools (4): **0 kecocokan**. Jadi
false positive-nya belum pernah terlihat; ini pencegahan, bukan perbaikan atas kejadian.

## Yang diubah

Pada berkas **Python**, pola **forger** (`FORGERS`: `os._exit`, `os.exec*`, `os.abort`, `os.write(1|2,`, `S_ISFIFO`, `/proc/self`, self-kill, dan teman-temannya) hanya melihat **kode**:
komentar (juga di ujung baris) dan docstring atau pernyataan string berdiri sendiri dikosongkan dengan spasi (panjang dan nomor baris tetap) sebelum dicocokkan. `"""Never call os._exit(0)."""`
dan `x = 1  # see /proc/self/status` tidak lagi menghentikan job. Dikerjakan dengan `ast` (pernyataan `Expr` berisi konstanta str) dan `tokenize` (token `COMMENT`), tidak dengan memotong di `#`:
- `x = "#"; os._exit(0)` tetap kena (tanda `#` di dalam string tidak menyembunyikan apa pun); kode sebelum komentar tetap dipindai;
- f-string (`f"{os._exit(0)}"`) dan string yang diberikan ke `exec(...)` bukan pernyataan berdiri sendiri, tetap dipindai;
- kolom `ast` dalam byte diubah ke karakter (baris non-ASCII).

**Kembali ke pemindaian lama (lebih lebar)** bila garisnya tidak pasti: berkas tidak bisa di-parse, ada `\r` yang bukan bagian `\r\n` (Python menghitungnya sebagai akhir baris, `split("\n")` tidak, sehingga
nomor baris bisa bergeser), awal span `ast` tidak jatuh di awal string, atau galat apa pun.

## Tidak diubah (dan kenapa)

- **JavaScript** (`process.exit(`, `process.abort(`, `process.kill(`, `fs.writeSync(1|2,`): tanpa parser di sini, `//` muncul di string, regex dan URL; dan tidak ada false positive yang terlihat.
- **`process.kill(`**: mempersempit ke `process.kill(process.pid` akan meloloskan `const p = process.pid; process.kill(p)`; melemahkan deteksi demi false positive yang belum pernah terjadi.
- **`process.exit(`**: forger bisa mencetak laporan palsu dengan `console.log` lalu keluar.
- **Pola deteksi uji** (`PYTEST_CURRENT_TEST`, `sys.modules`+`pytest`, ...): tetap memindai seluruh teks, termasuk komentar.

**Batas yang diterima:** kode yang dijalankan dari docstring (`exec(f.__doc__)`) tidak terlihat lagi oleh pola forger; patch seperti itu harus mengutip docstring itu ke `exec`, dan `exec` sendiri bukan pola.

**Batas yang sudah ada sebelum O2 (tidak diubah di sini):** `_hits` melewati seluruh baris yang diawali `#` atau `//`, jadi `# c\ros._exit(0)` (komentar yang diakhiri `\r` tunggal lalu kode, pada baris yang diawali `#`) tidak kena. Itu pagar per baris, di luar cakupan O2.

**Biaya (ditemukan 2026-11-13 setelah #488):** `tokenize` dan pengosongan kuadratik terhadap panjang satu baris (literal data 320 KB di satu baris: 28 detik; `tokenize` saja pada 80 KB satu baris: lebih dari 3 GB memori). Baris terpanjang > `MAX_VIEW_LINE` (20.000 karakter) tidak dipersempit: pemindaian lama yang linear. Arahnya aman (lebih banyak hit, bukan lebih sedikit). Data yang sama dipecah per baris tetap dipersempit.

**Pengukuran dan tinjauan:** pola gerbang O2 diukur di empat repo nyata (`argus-viewer`, `argus-ledger` dan dua lainnya): nol kecocokan, jadi kekhawatiran false positive belum pernah terjadi. Mutants 11/11 terbunuh. Reviewer sudut penyerang (sekitar 75 input: pernyataan sesudah string, senyawa satu baris, non-ASCII, CRLF, BOM, f-string Python 3.12) tidak menemukan false negative.

## Tes (gagal di kode lama)

`tests/test_o2_comments.py`: teks yang tidak bisa jalan tidak kena (docstring modul, fungsi, kelas; komentar di ujung baris; pernyataan string berdiri sendiri); kode tetap kena (kode sebelum komentar, `#` di
dalam string, f-string, `exec("...")`, kode setelah docstring, baris non-ASCII); nomor baris tidak bergeser; berkas yang tidak ter-parse dan `\r` tunggal tetap pemindaian lama; JavaScript dan pola deteksi tidak dipersempit;
satu tes ujung ke ujung lewat `check`. Mutants: `verification/o2_comments_mutants.py`.
