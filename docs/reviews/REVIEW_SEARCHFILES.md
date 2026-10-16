# Review: implementasi `SearchFiles`

Desain: `docs/reviews/DESIGN_SEARCHFILES.md` (PR #49), disetujui dengan empat syarat. Implementasi ada di
`codetask/tools.py`, tesnya di `tests/test_searchfiles.py`. **Belum diaktifkan secara default:** `search_files` tidak
ada di `tools.coder` di config, jadi prompt agen untuk task yang ada (hash `ee7af58d…`) tidak berubah. Mengaktifkannya
adalah keputusan terpisah, untuk task repo besar. Tidak ada run live.

## Empat syarat dan cara memenuhinya

| Syarat | Implementasi | Tes |
|---|---|---|
| **Keamanan path** | `path` lewat `PathJail.parts` (tolak `..`, path absolut termasuk `/`, NUL); setiap komponen di-`lstat`, symlink ditolak, bukan-direktori ditolak; walk `followlinks=False` dan direktori symlink dibuang dari daftar; hanya file biasa yang dibaca; isi dibaca lewat `jail.read_text` (O_NOFOLLOW per komponen) | traversal (6 bentuk), symlink file dan direktori ke luar workspace, FIFO tidak membuat hang, `/` ditolak |
| **Batas kerja** | paling banyak `SEARCH_MAX_FILES` = 500 file dan `SEARCH_MAX_BYTES` = 2 MB dibaca per panggilan; file > `SEARCH_MAX_FILE` (256 KB) tidak dibaca dan dilaporkan | batas file, batas byte, file besar |
| **Hasil yang bisa ditindaklanjuti** | `path:baris: teks`, urut path lalu baris, paling banyak 20 baris dipotong 200 karakter; setiap batas yang tercapai disebut eksplisit sebagai "results incomplete" | banyak hasil, baris panjang, Unicode (dipotong per karakter), tanpa hasil |
| **Tes adversarial dan mutasi** | lihat di bawah | 20 tes |

Lainnya: pencarian literal dan case-sensitive (bukan regex), teks 1–200 karakter dalam satu baris, izin lewat allowlist
`search_files`, hasil deterministik (aman diulang setelah crash), dan versi tool masuk ke key memo.

Satu perbaikan saat tes: `path="/"` awalnya diperlakukan sebagai "tanpa path" (`strip("/")`), sehingga yang dicari
tetap workspace, bukan root sistem. Tidak ada yang bocor, tapi path absolut sekarang ditolak eksplisit supaya agen
tidak salah mengira ia sudah mencari di `/`.

## Mutation check

16 mutan, **14 tertangkap**. Dua yang lolos ekuivalen satu per satu: `os.walk(followlinks=True)` saja, atau membuang
filter direktori symlink saja. Masing-masing lapis sudah cukup sendirian untuk mencegah walk masuk ke direktori
symlink. Mutan yang menghapus **kedua** lapis sekaligus tertangkap. Bahkan dalam kondisi itu, isi file di luar
workspace tetap tidak terbaca, karena lapis ketiga (`jail.read_text`) menolak path yang melewati symlink.

## Simulasi ulang dengan tool asli dan pencarian yang tidak sempurna

Jalurnya sama seperti PR #48/#49 (estimasi ±10%). Skenario:
- `read_all`: tanpa pencarian;
- `perfect`: kata yang benar langsung dicari;
- `wrong_term`: kata yang tidak ada hasilnya, lalu kata yang benar;
- `too_common`: kata yang ada di mana-mana (terpotong 20 baris), lalu kata yang benar;
- `wrong_lead`: kata yang masuk akal tapi mengarah ke file yang tidak relevan, file itu dibaca, lalu kata yang benar.

| Ukuran | File | read_all | perfect | wrong_term | too_common | wrong_lead |
|---|---|---|---|---|---|---|
| ~1 KB | 10 | 20.040 | 13.618 | 15.437 | 16.575 | 19.062 |
| ~1 KB | 40 | **habis** | 14.287 | 16.241 | 17.333 | 19.999 |
| ~1 KB | 80 | **habis** | 15.180 | 17.310 | 18.402 | 21.246 |
| ~3 KB | 10 | **habis** | 17.444 | 19.263 | 20.382 | 26.074 |
| ~3 KB | 40 | **habis** | 18.113 | 20.066 | 21.185 | 27.011 |
| ~3 KB | 80 | **habis** | 19.006 | 21.136 | 22.256 | **28.260** |

**Yang terlihat:**
- Semua skenario pencarian selesai, di semua ukuran repo yang diukur. Tanpa pencarian, budget habis mulai 20 file 1 KB
  atau 10 file 3 KB.
- Setiap langkah yang salah ada harganya, karena semua yang masuk percakapan dikirim ulang: pencarian tanpa hasil
  +1.800–2.100, kata yang terlalu umum +2.900–3.200, satu file yang salah dibaca +5.400–9.300 token.
- **Kelonggarannya cepat habis:** dengan file 3 KB, satu jalur salah saja sudah membawa attempt ke 26–28 ribu dari 30
  ribu. Dua jalur salah kemungkinan besar habis. Jadi pencarian memperpanjang jangkauan, tapi tidak menghilangkan
  batas pengiriman ulang (sesuai catatan GPT).

## Langkah berikutnya (untuk diputuskan)

Kalau hasil ini cukup, rancang satu task repo besar dengan model palsu dulu, di mana `search_files` diaktifkan lewat
kontrak atau config untuk task itu saja. Setelah itu baru live, di mana agen sungguhan harus menemukan kata kuncinya
sendiri.
