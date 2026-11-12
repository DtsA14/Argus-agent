# Spek v3: `ReportConflict`, amandemen atas v2

Status: **draf Claude 2026-11-12, belum disetujui sebagai teks.** Atha menyetujui arahnya di sesi 2026-11-12 (lima lubang
di bawah, dan `retry` dengan flag eksplisit). Jalur ketat (AGENTS.md): tes yang gagal di kode lama → kode → review → mutan →
`verify_at` → "merge". Tanpa model, tanpa uang.

Dasar: [`FABLE_SPEC_REPORT_CONFLICT_v1.md`](FABLE_SPEC_REPORT_CONFLICT_v1.md) dan
[`FABLE_SPEC_REPORT_CONFLICT_v2.md`](FABLE_SPEC_REPORT_CONFLICT_v2.md). v3 **mengganti**: v2 B1 (sumber himpunan merah), v2 B2
(syarat `path`), v2 §2 baris R2.8 (arti `(None, why)`), v2 §4 butir `retry` dan baris `status`, v1 R1 (argumen `reason`).
v3 **menambah**: sumber `files`, urutan keputusan di node acceptance, kunci memo tool. Sisanya dari v1 dan v2 tetap.

Dibaca di `7e2e129` (`main`): `codetask/run.py:312-389`, `codetask/tools.py:125`, `harness/steps.py:31-42`,
`codetask/status.py:29`, `acceptance/validation.py:334-350`, `388-394`, `453-456`, `617-626`, `644-672`,
`router/job.py:1176-1200`. Tidak ada yang dijalankan. Nomor baris v2 merujuk `3d3b078`; yang bergeser sejak itu:
`GATED` ada di `codetask/tools.py:125`, dan kunci langkah ada di `harness/steps.py`, bukan `codetask/steps.py`.

## 1. Amandemen

**C1. Syarat merah: `path` di berkas terkunci yang tidak berubah (ganti v2 B2).**
`path` di record `red_check` adalah frame terdalam di dalam repositori, bukan frame tes
(`acceptance/validation.py:453-456`, `624`). "`path` = berkas tes itu sendiri" menolak tes lama yang gagal di dalam helper
atau `conftest.py`. Syarat baru, untuk setiap node merah: `outcome == "failed"`, `path` tidak `None`, dan berkas `path`
(a) ada di intake dengan digest yang sama, (b) cocok glob protected (kontrak atau `repo_protected` yang dibekukan di
setup), (c) bukan berkas `new_tests`/`changed_tests` draf. `type` tetap ditampilkan ke manusia.

Yang tetap ditolak, dengan sengaja: tes lama yang merah karena exception dilempar **di kode produksi** (`path` di berkas
writable). Dari bukti harness itu tidak bisa dibedakan dari bug agen. Laporan seperti itu tak terkonfirmasi dan terlihat
lewat baris B3; jumlahnya dicatat (§5).

**C2. `files` dibaca dari hasil node agen yang di-commit, bukan dari `SUMMARY.json`.**
Sandbox me-mount workspace bisa-tulis, jadi kode agen yang jalan saat validasi bisa menimpa `SUMMARY.json`. Hasil tool
adalah `{content, finished: true, conflict: {files}}`, di-commit dengan `tool_step_key`; node agen mengembalikan
`attempt.conflict = {files}` (di-commit `guard`). Node acceptance hanya membaca `state["attempt"]["conflict"]`.
`SUMMARY.json` tetap ditulis dengan `claims: []` supaya `evaluate` berjalan, dan tidak pernah dibaca untuk `files`.

**C3. Urutan keputusan di node acceptance** (`codetask/run.py:347-389`), sesudah `evaluate` dan penulisan `verdict_<i>.json`:

1. `outcome == "pass"` → `DONE`, seperti sekarang. Tidak ada tes merah, jadi laporan tidak diverifikasi; `verdict.conflict`
   mencatat `{files, unconfirmed: ["nothing is red"]}`.
2. `outcome == "blocked"` → `BLOCKED/sandbox_unavailable`, seperti sekarang.
3. `attempt.end == "llm_failed"` → `BLOCKED/provider_failed`, seperti sekarang.
4. **Baru:** `attempt.end == "conflict_reported"` → verifikasi (`acceptance/conflict.py`):
   - sandbox tidak tersedia saat verifikasi → `BLOCKED/sandbox_unavailable` (C4);
   - terkonfirmasi → `BLOCKED/test_conflict`, `verdict.conflict = {files, nodes, checks}`. Ini **mendahului**
     `max_iterations`, stagnasi dan `admission`;
   - tak terkonfirmasi → lanjut ke butir 5, dengan `conflict = {files, unconfirmed: [...]}` ikut di kedua `move`
     (`FAILED_ACCEPTANCE` dan `RUNNING`) dan butir yang gagal masuk umpan balik.
5. `max_iterations`, stagnasi, `admission`: seperti sekarang.

**C4. Gangguan sandbox bukan "tak terkonfirmasi" (ganti v2 §2 baris R2.8).**
`red_check` mengembalikan `(None, why)` untuk dua hal yang berbeda (`validation.py:655-672`): sandbox tidak tersedia, dan
run yang tidak terbaca (timeout, keluaran terpotong, tanpa record). Yang pertama → `BLOCKED/sandbox_unavailable`, state
`conflict` tidak ditulis. Yang kedua bisa disebabkan kode agen → tak terkonfirmasi, jatah terpakai. Keduanya harus bisa
dibedakan **tanpa mencocokkan teks `why`** (nilai kembali terpisah atau exception).

**C5. Himpunan node merah berasal dari evidence validasi di verdict (ganti v2 B1 bagian sumber).**
Agen tetap menyebut 1-5 berkas. Himpunan merah = gabungan `failed_nodes` semua validasi di verdict attempt itu. Aturan:

- Validasi dengan `failures + errors != len(failed_nodes)` (daftar dipotong di `MAX_NODES`, `validation.py:350`, `394`) →
  tak terkonfirmasi: "too many red tests to enumerate". Ini menggantikan "lebih dari 50 node" di v2, yang tidak bisa
  dibedakan dari tepat 50.
- Himpunan kosong → tak terkonfirmasi.
- Setiap node merah harus berada di salah satu berkas yang disebut; berkas yang disebut tanpa node merah → tak terkonfirmasi.
- `red_check` dijalankan pada node-node itu saja (dua kali di workspace, satu kali di input, seperti v2). Tidak perlu
  koleksi berkas. Untuk vitest `red_check` menjalankan seluruh berkas; hanya record node merah yang dipakai. Apakah
  `red_records` mengembalikan record untuk node di luar daftar harus dicek saat implementasi.

**C6. `retry --not-a-conflict` dan kalimat di `status` (ganti v2 §4 butir `retry` dan baris `status`).**
Regresi biasa buatan agen bentuknya sama dengan konflik: tes lama merah, tes baru hijau. Harness hanya membuktikan bentuk
itu, jadi manusia perlu jalan untuk berkata "bukan konflik" tanpa membeli draf lagi.

- `argus retry <job>` tanpa flag, bila run terakhir `BLOCKED/test_conflict`: ditolak, pesannya menyebut dua pilihan.
- `argus retry <job> --not-a-conflict`: hanya sah bila run terakhir `BLOCKED/test_conflict`; semua syarat `retry` yang
  ada tetap berlaku (`job.py:1180-1195`, termasuk `_conflict_refusal` dan cap job). Run baru mendapat:
  - `initial_feedback` **buatan harness** (node dan `type`, tanpa teks agen): tes lama itu benar, buat mereka lulus;
  - state awal `conflict = {files, unconfirmed: ["a human judged this is not a conflict"]}`, sehingga `ReportConflict`
    ditolak di balasan tool sepanjang run itu (A2).
  - Log job: `retry` dengan `not_a_conflict: true`.
- Baris `status` untuk laporan terkonfirmasi:
  `old tests fail with the agent's change, new tests pass (checked by the harness; which side is wrong is your call):`
  lalu `<berkas>: <node> (<type>)` per node, lalu
  `next: argus abandon <job> and a new job that names the file(s) | argus retry <job> --not-a-conflict`.
  Kata "conflict" tidak dipakai sebagai fakta.

**C7. Kecil.**
- **Tanpa `reason`.** Tool = `ReportConflict(files)`. v2 mengganti v1 R1 tanpa menyebut `reason`; v3 membuangnya: teks
  bebas agen tidak dibutuhkan verifikasi dan satu permukaan injeksi hilang (A11). Baris `agent's reason` di v1 R5 gugur.
- **Kunci memo.** Balasan tool bergantung pada state `conflict`. Supaya identitas masukan ada di kunci:
  `versions["ReportConflict"] = "1:" + sha256(json state conflict)[:12]`, seperti `RunValidation` membawa versi image
  (`run.py:331`). Run tanpa state `conflict` memakai `"1:"` ditambah hash dari `null`.
- **Baseline satu kali** (v2) tetap. Risiko yang diterima: tes lama yang flaky sesekali terkonfirmasi salah; akibatnya
  berhenti ke manusia, bukan pass.

## 2. Tes tambahan (gagal di kode lama), di samping v1 §5

1. Tes lama gagal di dalam helper pada berkas terkunci yang tidak berubah → terkonfirmasi (C1).
2. Tes lama merah karena exception dilempar di berkas writable → tak terkonfirmasi, baris B3 menyebut butirnya (C1).
3. `path` di berkas terkunci yang digest-nya berubah, atau di berkas `changed_tests` draf → tak terkonfirmasi (C1).
4. Kode di sandbox menimpa `SUMMARY.json` dengan berkas lain → verifikasi memakai `files` dari hasil yang di-commit (C2).
5. Laporan terkonfirmasi pada iterasi terakhir → `BLOCKED/test_conflict`, bukan `FAILED_ACCEPTANCE/max_iterations`; sama
   untuk stagnasi (C3).
6. Laporan tak terkonfirmasi pada iterasi terakhir → `FAILED_ACCEPTANCE`, state `conflict` ada, baris B3 ada (C3).
7. Laporan, tetapi semua kriteria lulus → `DONE`, `verdict.conflict.unconfirmed` terisi (C3).
8. Sandbox tidak tersedia saat verifikasi → `BLOCKED/sandbox_unavailable`, state `conflict` tidak ditulis (C4).
9. `red_check` timeout → tak terkonfirmasi, jatah terpakai (C4).
10. Daftar `failed_nodes` terpotong; himpunan kosong; node merah di luar berkas yang disebut; berkas yang disebut tanpa
    node merah → tak terkonfirmasi, satu kasus masing-masing (C5).
11. `retry` tanpa flag sesudah `test_conflict` ditolak; dengan flag jalan, `initial_feedback` tidak memuat teks agen,
    `ReportConflict` di run baru ditolak di balasan tool; flag pada job yang run terakhirnya bukan `test_conflict`
    ditolak (C6).
12. `status` memuat kalimat C6 dan tidak memuat "conflict (checked by the harness)".
13. Crash di attempt `i+1` sesudah penolakan kedua: resume memberi balasan tool yang sama tanpa panggilan model; kunci
    memo tool berbeda antara run dengan dan tanpa state `conflict` (C7).
14. Skema tool tidak punya `reason` (C7).

Mutan tambahan: tiap syarat (a), (b), (c) di C1 dibuang; `files` dibaca dari `SUMMARY.json`; cabang terkonfirmasi
dipindah ke bawah `max_iterations`; sandbox tidak tersedia dijadikan tak terkonfirmasi; cek terpotong dibuang; `⊆` berkas
dibuang; `retry` tanpa flag diizinkan; flag diterima untuk run non-konflik; state `conflict` tidak dibawa ke run retry;
hash state dibuang dari versi tool.

## 3. Yang tidak berubah dari v2

A1-A5 (gerbang, selalu ditawarkan, state di graf, crash, satu laporan per run), B3, isi MVP selain `retry` dan baris
`status`, dan batas klaim: MVP memberi jalan keluar, tidak memaksa agen memakainya. Tetap di luar MVP: state job
`CONFLICT`, `redraft --from-conflict`, gerbang approve.

## 4. Perkiraan

Di atas angka v2 (±230 baris kode, ±350 tes): `retry --not-a-conflict` dan state awal `conflict` ±40 baris di
`router/job.py`, `codetask/run.py` dan `scripts/argus.py`; pembeda C4 ±10 baris di `acceptance/validation.py`. Tes ±150
baris. Perkiraan, belum diukur.

## 5. Ukuran sesudah merge

Per laporan, dari log run: terkonfirmasi atau tidak, butir yang gagal, dan untuk yang tak terkonfirmasi apakah `path`
ada di berkas writable (kasus yang sengaja ditolak di C1). Per laporan terkonfirmasi: `abandon` atau
`retry --not-a-conflict`. Kalau kasus C1 yang ditolak sering ternyata konflik nyata, syaratnya ditinjau lagi.

## 6. Urutan

Sesudah REPRO R1 (#468) di-merge. GATE (gerbang deteksi jadi terminal) tetap sesudah RC, PR tersendiri.
