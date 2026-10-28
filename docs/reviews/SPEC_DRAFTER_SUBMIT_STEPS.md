# Spec: langkah baca drafter habis di `max_steps`, submit tidak (dari run ulang SWE `21379`, percobaan 2)

Status: **disetujui** (Atha 2026-10-28: pilihan "A"). Kode di PR yang sama; tes yang gagal di kode lama, mutan, `verify.sh` penuh.

## 1. Masalah

Job `j20261027_185915_f13b`: tiga run drafter (`d1` 16 langkah, `d2` 16, `d3` 24 sesudah #210) membaca sampai tool baca dimatikan di
3 langkah terakhir, lalu berhenti `NO_DRAFT max_steps` dengan **satu** masalah tersisa dan jatah submit belum habis (3, 2, dan 2 dari
5). Menambah `max_steps` (#210) hanya memperpanjang bacaan; catatan "steps left" di tengah run tidak mengubahnya.

## 2. Usulan

Sesudah `max_steps`, loop drafter memberi **langkah submit** sampai `max_submits` habis (paling banyak `max_submits` langkah):
- hanya `SubmitDraft` dan `ReviseDraft` ditawarkan; di langkah pertama ada catatan `SUBMIT_STEPS_NOTE` (berapa submit tersisa);
- balasan tanpa submit (tool lain, teks saja, panggilan tidak valid) **mengakhiri** run (`max_steps`);
- jumlah langkah yang dilaporkan = langkah yang benar-benar dijalankan;
- pertanyaan scope (#208) tidak lagi dibatasi "bukan di langkah terakhir": selalu ada langkah submit untuk menjawabnya, selama ada
  submit tersisa (cek `n < max_submits` yang sudah ada).

Batas uang tidak berubah: setiap panggilan di dalam reservasi attempt ($0,70) dan cap tahap ($0,75). Kunci memo langkah tetap
`(step, messages, tools)`, jadi resume di langkah submit memutar ulang yang sudah dibeli.

## 3. Tes

Penolakan di langkah baca terakhir masih bisa diperbaiki (DRAFTED); langkah submit berhenti saat submit habis (jumlah langkah benar);
balasan tanpa submit, juga teks saja, mengakhiri run; crash di langkah submit → resume di sana; pertanyaan scope di langkah baca
terakhir dijawab di langkah submit. Dua tes lama disesuaikan (satu langkah submit sesudah `max_steps`; pertanyaan di langkah terakhir).
