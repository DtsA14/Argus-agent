# Spek: contoh di issue dijalankan di commit dasar (`repro`), sebelum drafter dan sebelum approve

Status: **draf Claude 2026-11-12, belum dikerjakan** (Atha: "fase 3 dengan tambahan di depan", sesudah eksperimen repo luar; `pilots/outside_v0/RESULT.md`). Jalur ketat:
menjalankan kode di sandbox dan menambah masukan drafter. Berlaku AGENTS.md: tes yang gagal di kode lama → kode → review → mutants → `verify_at` → "merge".
Tanpa model dan tanpa uang di bagian R1; R2 menyentuh prompt drafter (model) dan menunggu hasil ukur R1.

## 1. Masalah (bukti)

Eksperimen repo luar: dari 10 issue, 3 sudah beres di commit dasar (boltons #480, #343, #261). Pada #480 Argus tidak bisa mereproduksi bug, tidak berhenti, menulis
perubahan lain (cek tipe `str`), disetujui menurut aturan protokol, dan judge memberi PASS. Contoh di issue itu (`fp.group = ''` lalu `int(fp)`) mencetak `0o600` di commit
dasar, sedangkan issue menulis `0o644`: seorang manusia atau model yang melihat keluarannya akan tahu issue sudah beres. Tidak ada tahap yang menunjukkan keluaran itu.
Biaya satu job itu $0,24, kecil; masalahnya patch yang tampak sah untuk bug yang tidak ada.

## 2. Usul

**R1. Jalankan, tampilkan (tanpa model, tanpa penolakan).** Di `argus code`, sesudah intake dan sebelum drafter: ambil blok kode berpagar ```` ```python ```` (dan ```` ```py ````) dari
teks issue, paling banyak 3 blok, tiap blok ≤ 4.000 byte; jalankan masing-masing di sandbox pada pohon commit dasar (`tools/sandbox.run_python`, `--network none`, baca-saja,
batas waktu 20 s, keluaran dipotong 2.000 byte). Blok yang tampak bukan skrip (mulai dengan `>>>`, atau berisi `...` sebagai baris sendiri, atau berisi `$ `) dilewati
dengan alasan. Hasil per blok: `{index, status: "ok"|"raised"|"timeout"|"skipped", exit_code, stdout, stderr_last_line, reason}`; disimpan di `check_report.json` (`report["repro"]`,
selalu ada, mungkin `[]`) dan **ditampilkan**: bagian `## Issue example run at the base commit` di `DRAFT_REVIEW.md` (tiap blok: status, keluaran) dengan satu kalimat
"A clean run does not prove the bug is gone (output may differ from what the issue says); read it against the issue", dan satu baris di layar approve dan `argus status`
(`issue example at base: ran clean / raised <TipeError> / not run`). Dihitung ulang dari issue dan commit dasar saat approve, bukan dibaca dari laporan drafter.
Tidak menolak, tidak mengubah draf, apa pun hasilnya. Galat apa pun dalam R1 (sandbox mati, ekstraksi gagal) → `[]` dan satu baris "not run".

**R2. Drafter diberi keluaran itu, dan boleh berhenti (keputusan Atha sesudah R1 diukur).** Keluaran `repro` masuk konteks drafter (teks tetap, dipotong), dan drafter
mendapat jalan keluar `ReportNoRepro(reason)` yang mengakhiri draf dengan status `NO_REPRO` (bukan `DRAFT_FAILED`; tanpa `redraft` biasa; uang yang terpakai dicatat).
Ini serumpun dengan `ReportConflict` (RC) dan memakai pola gerbangnya; spek terpisah setelah R1 diukur di job nyata. Tidak termasuk R1.

## 3. Di luar cakupan

Membandingkan keluaran dengan komentar `# ...` di issue (rapuh; itu kerja model, R2), bahasa selain Python, blok yang butuh paket yang tidak ada di environment, menjalankan di
komit perbaikan, menolak issue otomatis.

## 4. Kenapa R1 dulu dan kenapa strict

R1 tidak menolak, tetapi menjalankan kode dari issue (masukan tak tepercaya) di sandbox dan menambah satu tahap sebelum drafter: kegagalan sandbox atau waktu tak boleh
menahan job (`[]`, lanjut). Itu cukup untuk jalur ketat. Ukur dulu: berapa persen issue punya blok yang bisa dijalankan, berapa yang "ran clean" pada issue yang memang
terbuka (false positive peringatan). Pada data kita: #480, #261 dan #343 bersih di dasar (benar), 7 lain mestinya `raised` atau berbeda keluaran; angka itu bagian ukuran.

## 5. Tes (gagal di kode lama)

1. issue dengan satu blok ```` ```python ```` yang `raise ValueError` → `status "raised"`, `stderr_last_line` memuat `ValueError`; blok bersih → `"ok"`; `while True: pass` → `"timeout"`, job lanjut.
2. blok `>>>` atau berisi `$ ` → `"skipped"` dengan alasan; lebih dari 3 blok → hanya 3 pertama; blok > 4.000 byte → `"skipped"`.
3. sandbox tak tersedia (`SandboxUnavailable`) atau ekstraksi melempar → `report["repro"] == []`, draf tetap dihasilkan; hasil apa pun **tidak** mengubah status draf atau keputusan.
4. `DRAFT_REVIEW.md` memuat bagian dan kalimat peringatan; tanpa blok, satu baris "No runnable example in the issue".
5. layar approve dan `status`: baris dihitung ulang (issue/dasar di disk diubah → baris ikut berubah); bukan dibaca dari `check_report.json`.
6. kode issue tak bisa menulis ke pohon atau jaringan (bendera sandbox yang sama dengan tes lain); keluaran dipotong 2.000 byte.
Mutants: batas 3 blok dan 4.000 byte, batas waktu, `[]` pada galat, penolakan tak boleh muncul (status draf sama), pemotongan keluaran, baris approve dihitung ulang.

## 6. Ukuran sesudah merge

Di 10 job berikutnya (atau pada 10 issue eksperimen, dijalankan ulang tanpa model): berapa blok jalan, berapa `raised`, berapa `ok`; dari yang `ok`, berapa memang sudah beres. Baru
dari angka itu R2 diputuskan.
