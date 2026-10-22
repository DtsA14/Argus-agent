# Spec W2b: drafter model (dari issue ke draf task)

Status: **spec, belum dikoding.** 2026-10-22. Ditulis Claude untuk review Atha/GPT. **Keputusan yang diminta: bagian 9.**
Dasar: `docs/reviews/M6_PLAN.md` W2, `docs/reviews/REVIEW_M6_W2A.md`, `acceptance/draft.py`, draf manusia pilot 3b
(`pilots/m6_pilot3/3b/draft.json`).

## 0. Kenapa sekarang, dan apa yang tidak berubah

Hari ini setiap pilot butuh manusia (dulu Claude di chat) untuk menulis rencana, scope, validasi, tes baru, **dan patch
referensi**. Agen sendiri murah (pilot 3b: $0,11, 4 panggilan). Yang mahal adalah persiapannya. W2b memindahkan penulisan
draf ke model, sehingga alurnya menjadi:

```
issue (manusia) ─▶ drafter (model, read-only) ─▶ draft.json ─▶ cek W2a ─▶ approve (manusia) ─▶ agen (Alur B) ─▶ review (manusia)
```

Titik sentuh manusia per task turun dari sekitar 6 menjadi 3: menulis issue, menyetujui draf, dan me-review hasil.

**Tidak berubah:**
- Format draf dan semua cek W2a (`acceptance/draft.py`): kontrak valid, tes baru protected dan tidak writable, serta
  **baseline merah karena assertion**. Drafter hanya menulis file draf yang sama, dan file itu tetap lewat `check()`.
- Draf tidak pernah menjadi kontrak tanpa `--approve` dari manusia. Issue, cap biaya, batas attempt, dan nama task tetap
  dari manusia.
- Acceptance run agen sama persis. `DONE` tetap berarti tes beku lulus di sandbox.
- Aturan uang dan crash-resume di AGENTS.md berlaku penuh untuk drafter (bagian 4).

## 1. Masalah inti: patch referensi

W2a mewajibkan **patch referensi hijau**, yaitu solusi tulisan manusia yang membuktikan kriterianya bisa dipenuhi.
Selama itu wajib, drafter hanya menghemat bagian yang paling ringan, karena manusia tetap harus menyelesaikan task-nya
sendiri dulu. Itulah sebabnya W2b dulu diberi prioritas rendah (PENDING).

Ada tiga pilihan:

| | Pilihan | Untung | Rugi |
|---|---|---|---|
| A | Tetap wajib (seperti sekarang) | Kriteria terbukti bisa dipenuhi sebelum biaya agen keluar | Manusia tetap menyelesaikan task-nya sendiri; drafter hampir tidak menghemat apa pun |
| B | **Opsional.** `approve_draft.py --no-reference`, dan record mencatat `feasibility: "unproven"` | Manusia cukup membaca draf | Kriteria yang mustahil baru ketahuan saat agen gagal. Biayanya paling banyak cap run, dan gagalnya jujur (`FAILED_ACCEPTANCE`, workspace tidak dipakai) |
| C | Drafter juga menulis patch referensi | Otomatis penuh | **Ditolak.** Model yang sama menulis tes dan solusinya, sehingga tes disesuaikan dengan solusi sendiri. Selain itu, task-nya praktis sudah dikerjakan sebelum agen jalan |

**Usul: B.** Yang hilang hanya bukti bahwa kriterianya bisa dipenuhi. Kejujuran hasil tetap terjaga, karena baseline merah
dan acceptance tidak berubah. Risiko yang tersisa dan bertambah dengan B (dicatat jujur di bagian 8): **tes yang salah**,
yaitu tes yang mengunci perilaku yang keliru. Dengan A, manusia setidaknya pernah memikirkan solusinya. Dengan B,
pertahanannya adalah membaca tes saat approve (dibantu `DRAFT_REVIEW.md`, bagian 5) dan me-review patch agen.

## 2. Masukan dan keluaran

**Masukan** (`scripts/draft_task.py`):
- `--intake <nama>`: intake yang sudah ada di `fixtures/repos/` dan lolos `intake.check`;
- `--issue-file`: teks issue dari manusia, maksimal 2.000 karakter (batas yang sama dengan W2a);
- `--run-id`, `--max-usd` (wajib, cap run drafter), `--config`, dan `--resume`.

**Keluaran** di `runs/<run_id>/`:
- `draft.json`: draf W2a yang lolos cek statis dan baseline merah;
- `check_report.json`: laporan `check()` tanpa langkah referensi (bagian 3);
- `DRAFT_REVIEW.md`: ringkasan deterministik untuk manusia (bagian 5);
- `events.jsonl` (ledger) dan `result.json` (status, biaya, `usd_complete`, total cache, jumlah submit, dan langkah).

Status akhir: `DRAFTED` (ada draf yang lolos), `NO_DRAFT` (langkah, submit, atau anggaran habis tanpa draf yang lolos),
atau `BLOCKED` (`invalid_input`, `provider_failed`, dan sebagainya), memakai pola `codetask/status.py`.

Setelah itu, manusia menjalankan `approve_draft.py --draft runs/<id>/draft.json ... [--reference-patch P | --no-reference]
[--approve]` seperti sekarang. Drafter tidak pernah memanggil `approve()`.

## 3. Loop drafter

**Tool:**
- `ListFiles`, `SearchFiles`, dan `ReadFile` di atas salinan snapshot intake. Ketiganya read-only, dan root-nya hanya
  salinan itu.
- `SubmitDraft(plan, contract, new_tests, unverifiable)`. Field `base` dan `draft_version` **diisi harness**, bukan model
  (K5).

Tidak ada `WriteFile` dan tidak ada `RunValidation` bebas. Satu-satunya jalan menjalankan kode adalah lewat `SubmitDraft`,
di sandbox.

**`SubmitDraft` menjalankan cek W2a sampai baseline merah** (K2):
1. `validate_draft`, lalu `build_contract` (dengan isian manusia: nama sementara, issue, cap), lalu `static_problems`;
2. bila lolos, `materialize` dan `baseline_problems` di sandbox;
3. bila ada masalah, daftar masalah plus **potongan output pytest** (helper D2 `error_excerpt`) dikembalikan sebagai hasil
   tool, dan loop berlanjut;
4. bila lolos, draf dan laporannya di-commit ke memo dan loop selesai (`finished`).

`max_submits` (bawaan 3) membatasi berapa kali cek sandbox dijalankan per run. Submit keempat ditolak tanpa menjalankan
apa pun, dan run berakhir `NO_DRAFT`.

Cek referensi **tidak** dijalankan di loop, karena drafter tidak menulis patch. Cek itu tetap milik
`approve_draft.py`.

**Bentuk kode** (K3): loop terpisah `codetask/drafter.py` (sekitar 150 baris) yang memakai ulang helper murni dari
`codetask/agent.py` dan `harness/` (`llm_step_key`, `tool_step_key`, `message_to_json`, `is_truncated`,
`invalid_call_errors`, `reservation_from_ledger`). `make_attempt` milik agen tidak diubah, karena loop itu sudah
di-mutation-check dan dipakai semua pilot.

**Prompt sistem** (ringkas, tidak memuat contoh draf manusia):
- tugasnya menyusun task, bukan memperbaiki kode;
- tes baru harus gagal **karena assertion** di kode sekarang, dan hanya menguji perilaku yang diminta issue;
- scope writable sesempit mungkin;
- yang tidak bisa diuji ditulis di `unverifiable`.

## 4. Jaminan harness (sama dengan Alur B)

- Setiap panggilan model lewat `LLMCaller.call` dengan role baru `drafter` (bawaan Sonnet 5.5). Reservasi diambil dari
  ledger (`reservation_from_ledger`), dan panggilan yang tidak muat ditolak sebelum dikirim. Ledger mencatat
  `llm_call_started` lalu `llm_call`, dalam nano-dollar.
- Profil budget seperti D1: `attempt_usd`, `max_input_tokens`, dan `max_output_tokens` 8.192. Tes 3b berukuran 9,4 KB,
  sekitar 3.000 token output dalam satu `SubmitDraft`. Prompt caching (D5) mengikuti config.
- Cap run: `min(budget.max_usd, --max-usd)`. Cap tidak pernah dinaikkan otomatis.
- Graf LangGraph dengan `durability="sync"`: `setup` (cek intake dan issue, membekukan policy), `draft` (loop), dan
  `finalize` (menulis keluaran). Setiap balasan model dan hasil tool di-commit sebelum loop berlanjut. Kunci memo memuat
  identitas masukan, dan kunci `SubmitDraft` memuat sha argumennya serta versi tool. Run yang di-resume tidak membeli
  ulang dan tidak menjalankan ulang cek sandbox yang sudah di-commit.
- Allowlist tool per role di config: `tools.drafter: [list_files, search_files, read_file, submit_draft]`, ditegakkan
  harness.

**Batas validasi drafter** (K4): untuk v1, validasi yang diusulkan drafter hanya boleh `python -m pytest <path ...>`
dengan `environment` dari config, tanpa executable lain. Validasi tetap jalan di sandbox. Batas ini hanya mempersempit
apa yang bisa diusulkan model.

## 5. `DRAFT_REVIEW.md`: yang dibaca manusia saat approve

Dibuat deterministik dari draf dan laporan, tanpa LLM:
1. issue, lalu rencana (file, langkah, risiko);
2. scope: writable dan protected. **Peringatan** bila writable memuat glob (`*`), path di bawah `tests/`, atau file yang
   tidak disebut di `plan.files`;
3. validasi dan node wajibnya, dengan tes lama dipisahkan dari tes baru;
4. **untuk setiap tes baru:** isi lengkapnya, lalu **pesan assertion-nya di baseline**. Inilah penilaian manusia yang
   diminta M6_PLAN: apakah kegagalannya memang perilaku yang ingin diperbaiki. Saat ini `baseline_problems` hanya
   menyimpan status dan jumlah. W2b menambahkan potongan `output_tail` per validasi (lewat `error_excerpt` D2) ke
   bukti itu. Tambahannya hanya data laporan, bukan kriteria;
5. `unverifiable`;
6. biaya drafter, jumlah submit, dan perintah `approve_draft.py` yang siap disalin, dengan `--no-reference`
   ditampilkan jelas bila K1 = B.

## 6. Tes (fake model; setiap tes harus gagal di kode lama, lalu dicek mutan)

1. **Jalur bahagia:** fake model membaca 2 file, submit draf yang valid, lalu `DRAFTED`. `draft.json` lolos `dr.check`
   ulang di luar loop, dengan baseline merah yang sama.
2. **Submit bermasalah lalu diperbaiki:** submit pertama memuat tes yang hijau di base, sehingga hasil tool berisi
   masalah dan potongan output; submit kedua lolos.
3. Tes yang ERROR (import gagal) ditolak dan tidak dihitung sebagai merah. Ini sudah dicek W2a; di sini yang dites adalah
   sampainya penolakan itu ke model.
4. `max_submits`: submit keempat tidak menjalankan sandbox, lalu `NO_DRAFT`.
5. **Read-only:** snapshot intake identik sebelum dan sesudah run, termasuk saat model mencoba tool tulis (ditolak
   `tool_denied`).
6. `base`, `draft_version`, `limits`, dan `inputs` tidak bisa diisi model: argumen ekstra ditolak skema, dan `base`
   selalu intake yang diminta.
7. Validasi selain `python -m pytest` ditolak (K4).
8. **Uang:** panggilan yang tidak muat ditolak sebelum dikirim, ledger lengkap, dan biaya tidak diketahui tercatat
   `null`.
9. **Crash-resume** di setiap titik (`after_llm`, `after_tool:SubmitDraft`, `finalize`): tidak ada panggilan model yang
   dibeli ulang dan tidak ada cek sandbox yang dijalankan dua kali untuk kunci yang sudah di-commit.
10. Balasan terpotong, tool call tidak valid, atau balasan tanpa tool berakhir atau di-nudge seperti loop agen.
11. `DRAFT_REVIEW.md` memuat pesan assertion setiap tes baru dan peringatan scope. Teksnya dikunci dengan golden file.
12. `approve_draft.py --no-reference`: cek referensi dilewati, record memuat `"feasibility": "unproven"`, dan
    `codetask/review.py` menulis kalimat yang sama di `PR.md`. Tanpa flag dan tanpa patch, perintah ditolak (exit 2),
    seperti sekarang.

Tes sandbox ikut grup xdist `sandbox`. Satu `verify.sh` penuh dijalankan per PR, setelah kode final.

## 7. Rencana pilot (hanya dengan "go live" dari Atha)

Prinsipnya eksperimen terkecil dulu.

1. **W2b-1, mengulang task yang jawabannya sudah ada:** issue 3b (`pilot_report`) di intake `argus_p6`. Draf manusia (17
   node wajib) menjadi pembanding. Di preflight, dicek dulu bahwa snapshot `argus_p6` tidak memuat
   `pilots/m6_pilot3/3b/` atau `tests/test_pilot_report.py`, untuk memastikan tidak ada bocoran. Kriteria ditulis sebelum
   run:
   - `DRAFTED` dalam ≤ 3 submit;
   - tes drafter merah karena assertion;
   - dicatat (bukan kriteria lulus): cakupan dibanding draf manusia, yaitu berapa perilaku issue yang diuji.

   Taksiran biayanya $0,10–0,35.
2. **W2b-2, end-to-end di task baru:** Atha hanya menulis issue, lalu drafter, approve (`--no-reference`), agen, dan
   review. Ukuran suksesnya: titik keputusan manusia (ukuran supervisi ringan), biaya total, dan apakah patch agen
   diterapkan tanpa perubahan. Bila memungkinkan, di repo selain Argus (gap #2 di Reconciliation).

## 8. Risiko dan batas yang diterima

- **Tes yang salah atau terlalu longgar.** Baseline merah hanya membuktikan bahwa tesnya gagal sekarang, bukan bahwa
  tesnya benar. Tes seperti "fungsi X ada" lolos cek tapi lemah. Pertahanannya: membaca `DRAFT_REVIEW.md` saat approve
  dan review patch. Tidak ada cek otomatis untuk ini di v1.
- **Kriteria mustahil** (K1 = B): agen gagal jujur dan biayanya paling banyak cap run. `feasibility: unproven` terlihat
  di record dan `PR.md`.
- Drafter bisa mengusulkan writable yang terlalu lebar. Itu diberi peringatan di review, bukan ditolak, karena tidak ada
  aturan objektif "terlalu lebar".
- Hanya pytest; tes unittest belum didukung (batas W2a yang sama).
- Draf hanya sebagus issue-nya. Issue yang ambigu menghasilkan tes yang menebak.
- Di luar W2b: satu perintah `argus "..."` yang merangkai intake, drafter, approve, dan agen, serta notifikasi. Itu
  langkah berikutnya bila W2b-2 berhasil.

## 9. Keputusan yang diminta

| | Pertanyaan | Usul |
|---|---|---|
| K1 | Kebijakan patch referensi | **B:** opsional lewat `--no-reference`, dicatat `feasibility: unproven` di record dan `PR.md`. A tetap tersedia bila ada patch |
| K2 | `SubmitDraft` menjalankan baseline merah di sandbox dan mengembalikan masalahnya ke model? | **Ya**, `max_submits` 3 |
| K3 | Loop terpisah atau `make_attempt` diberi parameter? | **Terpisah** (`codetask/drafter.py`), helper dipakai ulang, loop agen tidak disentuh |
| K4 | Validasi drafter hanya `python -m pytest <path>`? | **Ya** untuk v1 |
| K5 | `base` dan `draft_version` diisi harness? | **Ya** |
| K6 | Model dan profil | Role `drafter` = Sonnet 5.5, profil seperti `large_usd` (attempt $0,45, input 40k, output 8.192), cache D5 menyala di config pilot |
| K7 | Pilot pertama | **W2b-1** (ulang task 3b dengan cek bocoran), baru W2b-2 |

Taksiran pekerjaan: satu PR kode (drafter, skrip, review, tes, dan mutan) setelah K1–K7 dijawab, lalu preflight W2b-1.
