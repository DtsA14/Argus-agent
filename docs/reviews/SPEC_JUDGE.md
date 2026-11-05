# Spek: `argus judge`, penilai draf + patch (Reviewer Argus, tahap 2)

Status: **usulan, menunggu Atha.** Model dipilih Atha 2026-11-05: GLM-5.3 lewat OpenRouter, provider Baidu (fp8, diskon).
Jalur ketat (panggilan model berbayar baru: ledger, cap, crash-resume). Satu PR. Lanjutan `PENDING.md` tahap 2 dan
`docs/Reconciliation.md` bagian 7 ("Diputuskan 2026-11-05").

## 1. Masalah

Setiap job `argus code` sampai sekarang dibaca Claude: draf (tes dan kontrak) dan patch, lalu Claude menulis vonis di log
shadow sebelum `argus applied`. Itu supervisi yang ingin dikurangi tahap 2. Bukti dari dua batch shadow (12 job,
`~/argus-viewer-issues/SHADOW.md`):

- 3 blok asli: `097d` (agen memecah teks `<option>` ke `<span>` agar tes lama hijau; HTML tidak valid), `0e27` (validasi
  draf meninggalkan satu berkas tes lama; patch merusaknya), `1808` (setiap sel tabel total jadi `<th scope="row">` agar
  tes lama hijau).
- 8 job bersih yang di-apply; 1 job (`3f45`) berhenti di gerbang konflik tanpa patch.
- Kelas `0e27` dan konflik tes lama sekarang dicegat harness (#273, #275). Yang tersisa dan belum bisa dicek mekanis:
  **patch yang mengakali tes** (semantik salah tetapi hijau) dan tes draf yang tidak menguji yang diminta issue.

Pertanyaan yang dijawab spek ini: apakah model murah dari keluarga lain (bukan DeepSeek, yang dipakai drafter dan agen)
bisa menandai blok seperti itu, sehingga Claude cukup membaca vonis BLOCK ditambah sampel?

## 2. Usul

**J1. Perintah dan tempat.** `argus judge <job>` menjalankan satu stage model `j1` (kind `judge`) pada job kode yang punya
stage agen terakhir berstatus DONE dengan paket review `valid`. State job yang diterima: REVIEW_READY, APPLIED, REJECTED
(dua terakhir untuk replay, J8). State lain ditolak sebelum apa pun. `j1` **tidak pernah mengubah state job**, `approval`,
atau perilaku `approve`/`retry`/`applied`/`reject`; ia hanya menambah `stages.j1` dan berkas `JUDGE.md` di direktori job.

**J2. Yang dibaca model (dan hanya itu).** Prompt dibangun harness dari:
1. teks issue (`job_issue(job)`, yang juga diterima drafter);
2. draf yang di-approve: rencana, kontrak (validasi, kriteria, `unverifiable`) dan isi setiap tes baru/diubah, dari
   `draft.json` stage draf yang sha-nya ada di `approval`;
3. paket review agen terakhir: `changes.patch`, `tests.md`, `claims.md`.

Tidak pernah: `job.json` (berisi alasan `reject` dan log keputusan manusia), `SHADOW.md`, `PR.md`, `provenance.json`, isi
repo di luar patch, atau vonis judge lain. Batas ukuran: bila prompt melebihi `judge.max_input_chars` (default 120.000),
stage berakhir `NOT_JUDGED` ("input too large") **sebelum** ada request.

**J3. Keluaran.** Satu tool `SubmitJudgement`:
- `verdict`: `PASS` atau `BLOCK`;
- `findings`: 0-8 entri `{where, problem}`; `where` adalah path berkas yang ada di `changes.patch` atau path tes di draf
  (boleh diikuti `:baris` atau `::nama tes`), `problem` paling banyak 300 karakter;
- `summary`: paling banyak 600 karakter.

Gerbang harness (ditolak dengan umpan balik, `max_submits` 3): `BLOCK` tanpa finding; `where` yang path-nya tidak ada di
patch maupun di tes draf; teks kepanjangan (pada submit terakhir dipotong di batas kata, seperti e1 #309); verdict lain.
`PASS` boleh membawa finding (catatan yang tidak memblok).

**J4. Hasil stage.** `JUDGED` (dengan verdict) atau `NOT_JUDGED` (gerbang gagal di semua submit, model gagal, cap habis,
input kebesaran). `stages.j1` menyimpan `status`, `verdict`, jumlah finding, `usd`, dan sha256 dari tiga berkas paket review
yang dibaca. `JUDGE.md` berisi verdict, summary, finding, model + provider, biaya, dan sha tadi.

**J5. Sekali saja.** Hasil `j1` yang sudah tercatat tidak pernah dibeli ulang: `argus judge` kedua menampilkan vonis yang ada
dan tidak mengirim apa pun. Stage yang terputus dilanjutkan oleh `argus resume <job>` atau `argus judge <job>` lagi (memo
langkah seperti e1). Retry agen yang menghasilkan paket baru (stage `a2`) membuat `j1` lama basi: `status` menandainya
`stale` (sha paket berbeda) dan `argus judge` menjalankan `j2`. Tidak ada `--again`.

**J6. Uang.** Cap stage = `min(router.judge_max_usd` (default 0,10), sisa cap job). Lebih kecil dari satu percobaan
(`judge.attempt_usd`) ditolak sebelum mengirim, **tanpa** memindah job ke BLOCKED (judge hanya saran). Semua panggilan
lewat `LLMCaller.call`, ledger di run `j1`, `reservation_from_ledger` untuk resume, checkpoint `durability="sync"`, semua
dipakai ulang dari stage riset (`run_stage`, `tool_loop`, `with_fallbacks`). Konfirmasi seperti stage lain (`live()`):
model, provider, cap, dan **data yang keluar** (issue, draf, patch, hasil tes dikirim ke OpenRouter lalu ke Baidu).

**J7. Model.** Role baru `judge` → `openrouter:z-ai/glm-5.3`, `gateway_models` upstream `[baidu/fp8]` (pin tanpa fallback,
SPEC_GATEWAY_PROVIDER), harga di `prices` = harga diskon sekarang (input 0,28, output 0,88 USD per juta token).
Konsekuensi (Atha 2026-11-05): ledger tetap jujur karena tagihan = yang lebih besar dari hitungan kita dan `usage.cost`
OpenRouter; tetapi reservasi dihitung dengan harga config, jadi bila diskon berakhir satu stage bisa melewati capnya. Cap
$0,10 membatasi selisih itu. `max_output_tokens` 16.000, `timeout_s` 300. Tidak ada model cadangan: Baidu gagal =
`NOT_JUDGED`, dijalankan lagi nanti.

**J8. Replay (sesudah merge, perlu "go live").** Salin 11 job shadow yang punya paket review (`~/pilot3a_live/jobs`, batch 1
dan 2 kecuali `3f45`) ke `~/judge_replay/jobs/` (salinan; job asli tidak disentuh), jalankan `argus judge` pada setiap job.
Perkiraan $0,015 per job, sekitar $0,20 total; berhenti bila satu job > $0,05 atau total > $0,40.
- Prompt dan config **dibekukan sebelum replay** (commit dicatat); prompt ditulis generik, tanpa menyebut kasus `097d`/`1808`.
- **Lolos bila:** `097d` dan `1808` BLOCK dengan finding yang menunjuk berkas patch yang mengakali tes; paling banyak 1
  dari 8 job bersih BLOCK. `0e27` dicatat tetapi bukan syarat (kelasnya sudah dicegat #273). n kecil: hasilnya indikasi.
- Gagal: satu ganti model (`openai/gpt-5.6-luna`, prompt sama), lalu berhenti dan lapor.

**J9. Shadow batch 3 (sesudah replay lolos, "go live" sendiri).** Issue ditulis Claude (keputusan Atha 2026-11-05), dibuat
singkat (1-3 kalimat) agar tidak menjelaskan cara mengerjakannya; risiko issue terlalu bersih tetap dicatat. Per job: Claude
menulis vonisnya di log shadow dan commit log itu **sebelum** menjalankan `argus judge`; menit kerja Atha dicatat. Ukuran:
blok asli yang lolos dari judge (harus 0), BLOCK yang salah, biaya. Keputusan sesudahnya (Atha): review Claude hanya untuk
vonis BLOCK + sampel acak.

**Tidak dikerjakan:** judge memblok `approve`/`applied` (selalu saran); judge membaca repo atau menjalankan tes sendiri;
judge pada draf sebelum approve (bisa jadi langkah berikutnya bila batch 3 menunjukkan blok yang sumbernya draf); model
cadangan; perubahan pada `argus research`.

## 3. Jaminan dan tes (`tests/test_judge.py`, tanpa sandbox, model `fake:scripted`)

- **G1.** State selain REVIEW_READY/APPLIED/REJECTED, atau paket review tidak valid/tidak ada: ditolak, tidak ada stage, tidak
  ada `llm_call_started`.
- **G2.** Prompt berisi issue, draf yang di-approve, `changes.patch`, `tests.md`, `claims.md`; tidak berisi alasan reject,
  log keputusan, atau isi berkas lain di direktori job (tes menaruh teks penanda di `job.json`, `PR.md`, `provenance.json`
  dan mencarinya di prompt).
- **G3.** Input di atas `max_input_chars`: `NOT_JUDGED` tanpa request.
- **G4.** Gerbang: BLOCK tanpa finding ditolak; `where` di luar patch dan tes draf ditolak; path yang ada (dengan `:baris`
  dan `::tes`) diterima; teks kepanjangan dipotong hanya di submit terakhir.
- **G5.** State, `approval`, dan hasil `approve`/`applied`/`reject` sama persis dengan dan tanpa `j1` (job yang sama
  dijalankan dua kali, dibandingkan).
- **G6.** `argus judge` kedua sesudah JUDGED: tidak ada request baru, vonis yang sama ditampilkan, ledger tidak bertambah.
- **G7.** Crash sesudah balasan model sebelum stage selesai: resume tidak membeli ulang langkah yang sudah di-memo; total
  ledger = satu kali.
- **G8.** Cap: sisa cap job lebih kecil dari satu percobaan ditolak sebelum mengirim, state job tidak berubah (bukan BLOCKED).
- **G9.** Paket baru dari `a2` sesudah `j1`: `status` menandai `j1` `stale`; `argus judge` menjalankan `j2`, `j1` tidak
  dibeli ulang.
- **G10.** Role `judge` hanya bisa memakai model yang ada di `gateway_models` dengan pin (tes gateway yang ada mencakup
  model baru; request membawa `provider.only = [baidu/fp8]`).

Mutants (`verification/judge_mutants.py`): cek state dihapus; `job.json` ikut ke prompt; cek ukuran sesudah request;
gerbang `where` dihapus; judge memindah state job; vonis tercatat dibeli ulang; cek cap dihapus; sha paket tidak
dibandingkan. Lalu `/code-review medium`, verify.sh, "merge" Atha.

## 4. Keputusan untuk Atha

- **K1.** State yang diterima termasuk APPLIED/REJECTED (untuk replay)? Usul: ya.
- **K2.** Harga config = harga diskon Baidu (cap bisa sedikit terlewati bila diskon berakhir), bukan harga resmi Z.AI
  (ledger mencatat lebih mahal dari yang dibayar)? Usul: diskon, cap $0,10.
- **K3.** Ambang replay J8 (2 dari 2 akal-akalan tertangkap, paling banyak 1 dari 8 salah blok)? Usul: ya.
