# Spec router: key dari file di VM (tanpa PC)

Status: **spec, belum dikoding.** 2026-10-24. Ditulis Claude atas permintaan Atha ("key deepseek simpen di vm aja";
risikonya diterima: "saldo gw selalu dikit"). **Keputusan yang diminta: bagian 5.**

## 1. Masalah

Sejak 2026-10-24 Claude Code juga berjalan di VM (tmux `argus`, Remote Control), jadi Atha bisa bekerja dari HP tanpa
PC. Ada dua hal di router yang menghalangi run live dari sana:
- `live()` menolak jalan tanpa terminal ("the key is typed, never passed"). Perintah yang dijalankan sesi Claude tidak
  punya terminal interaktif;
- konfirmasi `[y/N]` dan key dibaca dari keyboard, sedangkan dari HP tidak ada keyboard terminal. Key juga **tidak
  boleh** diketik di chat, karena akan tersimpan di riwayat percakapan.

## 2. Usulan

- **`--key-file PATH`** di `argus code`, `approve`, `redraft`, dan `resume`. Isi file itu dipakai sebagai key untuk
  provider yang dibutuhkan stage tersebut, menggantikan prompt key. File ditolak (dengan pesan, tanpa menampilkan
  isinya), kecuali bila:
  - berupa file biasa (bukan symlink), dimiliki user yang menjalankan, dengan mode tanpa izin grup atau orang lain
    (`0600` atau `0400`);
  - berada di luar repositori dan di luar direktori `jobs/`;
  - isinya, setelah satu newline di akhir dibuang, lolos cek bentuk yang sama dengan key yang diketik (tidak kosong, tanpa
    spasi, prefiks provider).
- Key **hanya** dimasukkan ke environment selama stage berjalan, lalu dihapus (sama seperti sekarang). Key tidak pernah
  ditulis ke `job.json`, log event, atau output. Yang dicatat di `job.json` hanya bahwa key berasal dari file, beserta
  path-nya.
- **`--yes`** hanya boleh dipakai bersama `--key-file`. Layar batas (cap, sisa, writable, validasi, dan seterusnya)
  **tetap dicetak** sebelum stage mulai, tapi `[y/N]` tidak ditanyakan. Persetujuan manusia pindah ke chat: sesi Claude
  hanya menjalankan perintah live dengan `--yes` setelah Atha menulis "go live" atau "y" untuk perintah itu, sesuai aturan
  yang sudah ada (perintah live butuh persetujuan per run). Tanpa terminal dan tanpa `--yes`, run tetap ditolak seperti
  sekarang.
- Tanpa `--key-file`, perilaku router **tidak berubah sama sekali**.

## 3. Di luar kode (setup VM, dikerjakan Atha)

- Key khusus VM dengan saldo kecil, terpisah dari key yang lain. Atha menulisnya sendiri lewat ssh, tanpa chat dan tanpa
  argumen command line:
  ```bash
  mkdir -p ~/.config/argus && chmod 700 ~/.config/argus && read -rs K && printf '%s' "$K" > ~/.config/argus/deepseek_key && chmod 600 ~/.config/argus/deepseek_key && unset K
  ```
- Setting Claude Code di VM mendapat `permissions.deny` untuk `Read(~/.config/argus/**)` dan perintah Bash yang
  menyebut path itu. Ini lapisan tambahan, **bukan jaminan**: pola Bash bisa diakali, dan sesi Claude memang menjalankan
  router yang membaca file itu.

## 4. Tes (gagal di kode lama; mutan)

1. Dengan `--key-file` yang benar, stage jalan tanpa terminal dan env berisi key selama stage. Setelahnya env bersih, dan
   isi key tidak ada di `job.json`, `events.jsonl`, maupun output.
2. Ditolak: symlink, file milik user lain atau dengan mode `0644`, file di dalam repo atau `jobs/`, isi kosong, isi
   dengan spasi, prefiks salah. Isi file tidak pernah muncul di pesan penolakan.
3. `--yes` tanpa `--key-file` ditolak. Tanpa terminal dan tanpa `--yes`, run tetap ditolak seperti sekarang.
4. Dengan `--yes`, layar batas tetap dicetak dan dicatat di log job.
5. Tanpa `--key-file`, semua tes router lama lulus tanpa perubahan.

## 5. Keputusan

| | Pertanyaan | Usul |
|---|---|---|
| K1 | Sumber key | `--key-file` eksplisit per perintah, bukan dibaca otomatis dari config |
| K2 | Syarat file | file biasa, milik user, mode `0600`/`0400`, di luar repo dan `jobs/`, cek bentuk sama |
| K3 | Konfirmasi tanpa terminal | `--yes` hanya bersama `--key-file`; persetujuan per run lewat chat ("go live"/"y"); layar batas tetap dicetak |
| K4 | Pagar tambahan | key khusus VM bersaldo kecil, dan deny rule di setting Claude VM (bukan jaminan) |
