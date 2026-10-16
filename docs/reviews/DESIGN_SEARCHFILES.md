# `SearchFiles`: desain kecil dan simulasi (belum diimplementasi di harness)

Status: **draf untuk review**, 2026-10-16. Arah dari review PR #48: tool pencarian read-only sebagai eksperimen
arsitektur pertama. Tidak ada perubahan harness. Prototipe tool ini hanya ada di `scripts/measure_context.py`, untuk
mengukur penghematan sebelum ada keputusan implementasi.

## Desain

```
SearchFiles(text: str, path: str = "")
```

| Aturan | Nilai |
|---|---|
| Sifat | **read-only**. Tidak ada shell dan tidak ada proses: pencarian dilakukan di Python, di dalam path jail workspace |
| Pencocokan | **teks literal, case-sensitive**, bukan regex (tidak ada risiko backtracking dan tidak perlu escaping) |
| `text` | 1–200 karakter, satu baris; selain itu ditolak |
| `path` | opsional, direktori relatif di dalam workspace; `..` dan path absolut ditolak lewat path jail |
| File yang dicari | hanya file biasa dari snapshot workspace; symlink dan file khusus dilewati |
| Hasil | `path:baris: isi baris`, diurutkan per path lalu baris; **paling banyak 20 baris**, isi baris dipotong 200 karakter |
| Kelebihan | ditambah satu baris "… N more matches not shown; narrow the text or the path" |
| Tanpa hasil | "No matches." |
| Allowlist | izin baru `search_files` di `tools.coder`, ditegakkan harness seperti tool lain |
| Crash-resume | hasilnya ditentukan oleh isi workspace dan argumen, jadi aman diulang. Versi tool masuk ke key memo seperti tool lain |

Ukuran output-nya dibatasi sekitar 20 × 220 karakter (kira-kira 1.800 token). Ini mencegah satu pencarian yang terlalu
umum menghabiskan konteks.

## Simulasi (jalur harness yang sama seperti PR #48)

Yang dipakai asli: loop agen, `LLMCaller` (reservasi, penolakan), tool asli, ditambah prototipe `SearchFiles`. Token
dihitung dengan model kalibrasi PR #48 (≈ 407 + 0,3186 × karakter, galat ≤ 9,4%), jadi semua angka adalah
**estimasi**. Skenarionya: repo dengan N modul sintetis; simbol yang perlu diperbaiki didefinisikan di satu file dan
dipakai di satu file lain.

- **Tanpa pencarian:** `ListFiles` → membaca semua file sekaligus (pola terbaik di PR #48) → tulis → validasi → selesai.
- **Dengan pencarian:** `ListFiles` → `SearchFiles` simbolnya → membaca **2 file yang ditemukan** → tulis → validasi →
  selesai.

| Ukuran file | File | Tanpa pencarian | Dengan pencarian |
|---|---|---|---|
| ~1 KB | 5 | 14.465, selesai | 13.211, selesai |
| ~1 KB | 10 | 19.737, selesai | 13.322, selesai |
| ~1 KB | 20 | habis (`reservation_exhausted`) | 13.545, selesai |
| ~1 KB | 40 | habis | 13.991, selesai |
| ~1 KB | 80 | habis | 14.882, selesai |
| ~3 KB | 5 | 26.057, selesai | 19.069, selesai |
| ~3 KB | 10 | habis | 19.181, selesai |
| ~3 KB | 20 | habis | 19.404, selesai |
| ~3 KB | 40 | habis | 19.849, selesai |
| ~3 KB | 80 | habis | 20.742, selesai |

Di setiap skenario, pencarian menemukan kedua file yang diperlukan, dengan 2 baris hasil. Untuk kata yang sangat umum
(`result`, 40 file ~3 KB), output terpotong di 20 baris ditambah baris "more matches", dan total attempt tetap 20.614
token.

**Yang terlihat:** dengan pencarian, total token per attempt **hampir datar terhadap ukuran repo**. Yang bertambah
hanya daftar file dari `ListFiles`, sekitar 13–15 ribu token untuk file 1 KB dan 19–21 ribu untuk file 3 KB. Tanpa
pencarian, batas 30.000 habis di sekitar 20 file 1 KB atau 10 file 3 KB.

## Batasan: penghematannya diukur, bukan dijamin

1. **Model palsu tahu persis kata yang harus dicari.** Ini skenario terbaik. Di task diagnosis (`money_precision`,
   `cache_key`), issue-nya hanya berisi gejala. Agen sungguhan harus menebak kata kunci, mungkin mencari beberapa kali,
   dan mungkin tetap membaca file yang tidak relevan. Setiap pencarian dan setiap file tambahan ikut dikirim ulang di
   langkah berikutnya.
2. **Biaya pengiriman ulang tetap ada.** Pencarian mengurangi berapa banyak yang dibaca, tapi semua yang sudah masuk
   percakapan tetap ditagih lagi di setiap langkah (catatan GPT benar). Di simulasi ini percakapannya pendek (6 langkah),
   jadi efek itu kecil.
3. **`ListFiles` masih membesar mengikuti repo.** Untuk repo dengan ribuan file, daftar itu sendiri jadi masalah. Itu di
   luar skala yang diukur di sini.
4. Hasil tetap estimasi ±10%, dan output model disederhanakan.

## Yang perlu diputuskan

- Desain di atas cukup, atau ada batas yang perlu diubah (20 baris, 200 karakter, literal tanpa regex).
- Kalau lanjut: implementasi di harness sebagai PR terpisah, dengan tes (path jail, batas output, file khusus,
  allowlist, crash-resume) dan mutation check. Setelah itu, task repo besar dengan model palsu dulu, lalu baru live.
  Di task itu, agen sungguhan yang harus menemukan kata kuncinya sendiri, dan di situlah penghematannya benar-benar
  diuji.
