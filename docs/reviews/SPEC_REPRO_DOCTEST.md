# Spek: R1 membaca blok `>>>` (sesi interaktif) lewat parser `doctest`

Status: draf 2026-11-13. Asal: urutan kerja Fable 2026-11-13 ("R1 membaca blok `>>>` lewat parser `doctest`"). Jalur ketat: menjalankan kode di sandbox. Tanpa model, tanpa uang.
Berlaku AGENTS.md: tes gagal di kode lama → kode → review → mutants → `verify_at` → "merge" Atha.

## 1. Masalah (bukti)

R1 (`acceptance/repro.py`) melewati setiap blok python yang berisi baris `>>>` ("an interactive session (>>>), not a script"). Di batch 2, empat dari delapan job tanpa sinyal:
more-itertools#1284 (tiga blok `bucket`, ditulis sebagai sesi `>>>`) dan boltons#322 (`human_list`, satu blok), padahal isinya contoh yang bisa dijalankan (`R1b offline`, PR #491: 5 dari 8 job punya
sinyal, 4 dari 4 patch B terbaca `changed`, satu-satunya C `unchanged`). Penulis issue untuk pustaka kecil sering menulis contoh sebagai sesi `>>>`.

## 2. Usul

Sebuah blok python yang punya baris `>>>` dibaca dengan `doctest.DocTestParser().get_examples`. Tiap contoh dijalankan berurutan di **satu** namespace (`globals()` program), dengan
`exec(compile(<sumber contoh>, "<doctest>", "single"), globals())`: mode `single` mencetak `repr` sebuah ekspresi seperti sesi interaktif, jadi `>>> s['c']` menampilkan nilainya di keluaran
(itu yang dibandingkan R1b: status, tipe exception, baris keluaran terakhir). Sumber dimasukkan lewat `repr()`, tidak pernah disambung sebagai teks program.

- Keluaran yang diharapkan (baris di bawah `>>>`, termasuk komentar di ujungnya) **tidak dijalankan dan tidak dibandingkan**; membandingkan adalah R2.
- Contoh dengan `# doctest: +SKIP` dilewati. Opsi `doctest` lain diabaikan.
- Exception menghentikan blok (status `raised`), seperti skrip biasa; tidak ada toleransi "Traceback yang diharapkan".
- Blok doctest yang tidak punya contoh yang bisa dijalankan: `skipped`, alasan "no runnable doctest example". Parser menolak blok (`ValueError`, mis. `...x` tanpa spasi): `skipped`, alasan "doctest examples do not parse".
- Batas lama tetap: paling banyak 3 blok, sumber blok ≤ 4.000 byte (diukur pada teks blok), 20 s, keluaran 2.000 byte. Baris `$ ` tetap membuat blok dilewati. Baris `...` sendirian tetap membuat blok
  **non-doctest** dilewati; di blok doctest itu penanda lanjutan atau keluaran.
- Blok tanpa baris `>>>` berjalan persis seperti sekarang (program yang sama, byte demi byte).

## 3. Di luar cakupan

Membandingkan keluaran dengan yang diharapkan (R2, hanya bila ada perbandingan mekanis "harap X, dapat Y"), fence berbahasa `pycon`/`python-console`, sesi `>>>` tanpa fence, opsi doctest selain SKIP,
menjalankan lanjut setelah exception. Kode contoh dijalankan dengan kepercayaan yang sama seperti skrip biasa (sandbox tanpa jaringan, batas yang sama); doctest tidak menambah izin.

## 4. Tes (gagal di kode lama): `tests/test_repro_doctest.py`

Program yang dibuat dijalankan sungguhan di tes (`python -I` di folder sementara), bukan hanya dibaca.
1. ekspresi mencetak repr-nya; `print` tercetak; keluaran yang diharapkan tidak muncul; 2. state terbawa antar contoh; 3. contoh banyak baris (`...`); 4. exception menghentikan blok dan exit code 1;
5. `+SKIP` dilewati; 6. semua contoh `+SKIP` → skipped; 7. blok tidak ter-parse → skipped; 8. sumber dengan kutip, backslash, unicode dan `'''` berjalan benar (tidak disambung sebagai teks);
9. blok non-doctest tidak berubah (program identik; `...` sendirian dan `$ ` tetap dilewati); 10. lewat `run()` dengan sandbox palsu: statusnya, indeksnya, dan batas ukuran 4.000 byte; 11. tiga blok `bucket` dan blok
`human_list` yang nyata (salinan issue batch 2) menghasilkan contoh yang bisa dijalankan; 12. `line()` dan `label()` memperlakukan hasilnya seperti hasil skrip.
Mutants: sesi `>>>` tetap dilewati; keluaran yang diharapkan dijalankan sebagai kode; mode `exec` bukan `single`; `+SKIP` diabaikan; namespace baru per contoh; sumber disambung tanpa `repr`; `...` sendirian
membuat blok doctest dilewati; pemeriksaan `$ ` dibuang; pemeriksaan `...` dibuang untuk blok non-doctest; batas ukuran dibuang; `ValueError` parser naik ke job.
