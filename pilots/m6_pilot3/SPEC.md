# M6 pilot 3 (kandidat A): spesifikasi acceptance, bagian inventaris, kontrak, dan kriteria

> **Update 2026-10-21:** Pilot 3 was split by decision of the reviewer into **3a** (shared reader + the two inspectors; `pilots/m6_pilot3/3a/`) and **3b** (the aggregator, which starts only after the 3a patch is applied and verified on `main`). This file is the original combined specification; the sections on `pilot_report.py` belong to 3b. The combined task did not fit one attempt (`TOKEN_SIMULATION.md`).

Status 2026-10-21: **spesifikasi untuk review. Belum ada draf, tes final, patch referensi, atau coder.** Dasar: kandidat A di
`docs/Reconciliation.md` dan arahan GPT (batas Pilot 3, satu catatan tentang dua pekerjaan berbeda). Basis: `main` pada `a0075a9`.
Pertanyaan eksperimen: seberapa baik coder merapikan kode lintas berkas **sambil mempertahankan perilaku lama**, dan menambah
satu keluaran baru dengan definisi eksplisit, dengan acceptance deterministik.

## 1. Inventaris enam skrip (dibaca dari kode; dua dijalankan di VM)

| Skrip | Untuk apa | Input | Keluaran | Cara baca `events.jsonl` | Data rusak atau tidak lengkap | Bisa diuji di sandbox `argus`? |
|---|---|---|---|---|---|---|
| `audit_run.py` (83 baris) | audit satu run code task: bangun ulang tiap panggilan dari memo, cocokkan `prompt_hash`, daftar panggilan, tool, penolakan | satu direktori run (`contract.json`, `result.json`, `memo.sqlite`, `events.jsonl`, `verdict_<i>.json`) | teks bebas: tools efektif, sha prompt, hitungan `llm_call`, per langkah `hash ok/MISMATCH`, tool call, event penting, ringkasan `result` | `json.loads` per baris, tanpa `try` | **baris putus: `JSONDecodeError`. Run tanpa panggilan model (misal `BLOCKED` di setup): `TypeError` di `offered(result["tools"])` karena `tools` bernilai `None` (diverifikasi di VM); `calls[0]` akan menjadi kegagalan berikutnya** | ya (membaca berkas; perlu `PYTHONPATH`) |
| `failure_trace.py` (33 baris) | per attempt dan langkah: token masuk, tool call, teks model | satu atau lebih direktori run (mencari `result.json` di dalamnya) | teks: `##### <nama>` lalu satu baris per panggilan | `json.loads` per baris | baris putus: `JSONDecodeError`; direktori tanpa `result.json`: `StopIteration`; run tanpa panggilan: header saja (benar) | ya |
| `analyze_series.py` (118 baris) | analisis seri eksperimen: biaya, tool, diff terhadap fixture, klaim, validasi ulang | `series.json` dan direktori run per entri; **`fixtures/repos/ledger` ditulis keras** | satu baris JSON per run | `json.loads` per baris | tidak ditangani | **tidak**: memakai `run_validation` di Docker dan fixture `ledger` |
| `sim_admission.py` (60 baris) | simulasi admission attempt 2 dan 3 pada cap $1,00 | tidak ada argumen; **membaca `verification/search-live-2/0*` (data historis)** | teks | `json.loads` per baris (`open(...)`) | tidak ditangani | **sebagian**: bagian sintetis ya; bagian data historis tidak (`verification/` tidak ada di snapshot) |
| `dry_feedback.py` (75 baris) | uji kering jalur umpan balik pada fixture `ledger` dengan model palsu | satu direktori keluaran | teks | `json.loads` per baris, atas log yang baru saja dibuatnya | tidak ditangani | **tidak**: sandbox Docker sungguhan |
| `measure_context.py` (463 baris) | eksperimen B: tumbuhnya token terhadap jumlah berkas yang dibaca; banyak sub-perintah | sub-perintah (`calibrate`, `simulate`, `shop`, ...); sebagian membaca run live historis | teks dan JSON | `json.loads` per baris, atas log buatannya sendiri atau run historis | tidak ditangani | sebagian |

## 2. Temuan: "enam skrip" bukan satu pekerjaan

- **Hanya dua** (`audit_run.py`, `failure_trace.py`) adalah pemeriksa generik atas run nyata. Hanya merekalah yang berhadapan dengan
  log run yang crash, jadi hanya merekalah yang benar-benar butuh pembaca toleran.
- Empat sisanya adalah alat eksperimen yang sudah selesai: terikat fixture tertentu (`ledger`), memakai Docker, atau membaca data
  historis yang **tidak ada di snapshot task**; tiga membaca log yang baru mereka buat sendiri (tidak mungkin terpotong). Merapikannya
  tidak memberi manfaat, dan **perilakunya tidak bisa diverifikasi** di acceptance (Docker atau data historis), jadi refactor-nya
  akan tidak teruji. Itu persis risiko "scope yang kabur" yang GPT khawatirkan.
- **Hubungan agregator dengan skrip:** agregator **tidak** mengonsumsi format keluaran skrip mana pun (keluaran skrip adalah teks
  bebas; satu-satunya keluaran mesin-terbaca, JSON per baris di `analyze_series.py`, khusus seri). Keduanya hanya **berbagi data
  mentah**: direktori run (`result.json`, `events.jsonl`, ...). Hubungan nyata satu-satunya adalah **satu pembaca direktori run**
  yang dipakai bersama.

**Usulan scope Pilot 3 (dipersempit):** satu pembaca direktori run bersama, dua pemeriksa (`audit_run.py`, `failure_trace.py`)
dipindah ke sana dengan perilaku lama dipertahankan, ditambah satu agregator baru (`pilot_report.py`) sebagai pemakai ketiga.
Keempat skrip eksperimen **tidak disentuh** (dicatat sebagai arsip; butir tindak lanjut di `PENDING.md` dipersempit menjadi dua
skrip itu). Dua validasi dilaporkan **terpisah** (inspektor, agregator) supaya hasilnya bisa ditafsirkan: refactor dengan perilaku
dipertahankan versus fitur baru dengan definisi eksplisit. Kalau GPT lebih suka, pilihan lain: pecah menjadi 3a (pembaca plus dua
pemeriksa) dan 3b (agregator).

## 3. Keluaran lama yang tetap menjadi kontrak (refactor harus menjaganya byte demi byte)

Untuk run yang selesai normal (fixture F1, F2, F3, F5 di bagian 4), keluaran standar `audit_run.py` dan `failure_trace.py` **sama persis**
dengan keluaran skrip lama pada commit dasar (tes keluaran emas, bagian 6). Itu termasuk urutan baris, spasi, pemotongan teks
(`[:160]`, `[:150]`), baris `hash ok/MISMATCH`, ringkasan `result`, dan header `##### <nama>`.

**Perilaku yang sengaja berubah** (hanya ini; semuanya hari ini berupa crash):

1. Baris `events.jsonl` yang tidak bisa di-decode dilewati di mana pun posisinya (aturan `parse_lines`). Keluaran untuk log yang sama
   dengan satu baris putus tambahan **identik** dengan keluaran log tanpa baris itu, ditambah satu baris `events skipped: N` hanya
   bila N > 0 (baris itu tidak muncul bila N = 0, supaya keluaran lama tidak berubah).
2. `audit_run.py` pada run tanpa panggilan model dan/atau `tools: None`: tidak crash. Cetak `effective tools None`, hitungan
   `llm_call_started 0, llm_call 0 (ok 0, refused 0)`, `prompt_hash checked 0, mismatches 0`, event penting, dan `result`; exit 0.
3. `failure_trace.py` pada direktori tanpa `result.json`: pesan satu baris `##### <nama>: no result.json` (bukan `StopIteration`),
   lalu lanjut ke argumen berikutnya.

## 4. Fixture sintetis (dibuat saat tes berjalan dengan `run_code_task` dan model palsu terskrip; tanpa biaya, tanpa Docker)

| Fixture | Cara membuat | Mengunci |
|---|---|---|
| **F1** sukses di attempt pertama | skrip: tulis, finish | keluaran emas inspektor; baris agregator `DONE`, 1 attempt |
| **F2** sukses di attempt kedua | `Finish` malas lalu perbaikan (pola `test_feedback_leads_to_a_fix_in_the_next_attempt`) | keluaran emas dengan umpan balik; 2 attempt |
| **F3** gagal `FAILED_ACCEPTANCE` (stagnan) | dua `Finish` malas | keluaran emas; baris agregator bukan `DONE` |
| **F4** `BLOCKED` sebelum panggilan model | `preflight=lambda: (False, "...")` | kasus nol panggilan (perilaku 3.2); agregator: `BLOCKED`, `llm_calls` 0 |
| **F5** run yang di-resume setelah crash | crash di langkah agen (pola `crash_after_setup`), lalu resume | keluaran emas pada run yang punya event `resume`; **F5c** = F5 dengan satu baris putus disisipkan di tengah log (perilaku 3.1) |
| **F6** biaya tak diketahui | `result.json` F1 diubah: `usd_complete: false` dengan `usd_billed` 0.05 (parsial); varian tanpa `usd_billed`; varian tanpa kunci `usd_complete` | agregator: biaya tak diketahui, tidak pernah 0 |
| **F7** tanpa `result.json` | hapus `result.json` dari salinan F1 | agregator: `NO_RESULT`; `failure_trace` baris `no result.json` |
| **S** data supervisi | berkas samping `supervision.json` `{run_id: menit}`: lengkap, sebagian, tidak ada, dan tidak valid (negatif, bukan angka) | agregator: menit hilang bukan 0; berkas tidak valid ditolak |

**Prasyarat sebelum kriteria dibekukan (gue periksa, belum dikerjakan):** keluaran `audit_run.py` dan `failure_trace.py` pada F1–F5
harus **identik** antara host VM dan sandbox `argus` (tidak ada jalur, waktu, atau id acak di keluaran). Kalau tidak, keluaran emas
tidak bisa menjadi kriteria dan harus dinormalkan lebih dulu.

## 5. Kontrak agregator `scripts/pilot_report.py`

`python scripts/pilot_report.py RUN_DIR [RUN_DIR ...] [--supervision FILE.json]` mencetak **satu objek JSON** (kunci berurutan tetap,
`indent=2`) ke stdout. Exit 0; exit 2 dengan pesan di stderr bila argumen bukan direktori run (tanpa `events.jsonl`) atau berkas
supervisi tidak valid.

**Per run** (urut seperti argumen): `run_id` (nama direktori), `status` (`result.json.status`, atau `"NO_RESULT"` tanpa `result.json`),
`done` (`status == "DONE"`), `attempts`, `llm_calls`, `usd_billed` (angka dari `result.json`, atau `null`), `cost_known`
(`evals.score.cost_is_known` atas `result.json`; `NO_RESULT` selalu `false`), `events_skipped` (dari `result.json` bila ada, kalau tidak
dihitung dari log dengan aturan `parse_lines`), `supervision_minutes` (dari berkas samping; `null` bila tidak ada, **tidak pernah 0**).

**Agregat:**

| Kunci | Definisi tepat |
|---|---|
| `runs` | jumlah direktori run |
| `done` | jumlah run dengan `status == "DONE"` |
| `no_result` | jumlah run `NO_RESULT` |
| `success_rate` | `done / (runs - no_result)`; `null` bila penyebutnya 0. Run `NO_RESULT` tidak dihitung gagal maupun sukses |
| `usd_known_total` | jumlah `usd_billed` **hanya** atas run dengan `cost_known` (semua status, gagal ikut) |
| `usd_unknown_runs` | jumlah run dengan `cost_known == false` (termasuk `NO_RESULT`) |
| `cost_per_success` | `usd_known_total / (jumlah run DONE di antara run dengan cost_known)`; `null` bila pembaginya 0. Biaya run yang gagal ikut menjadi pembilang (sama dengan "biaya per sukses" di eksperimen budget). Tidak pernah 0 atau tak hingga |
| `cost_complete` | `true` hanya bila `usd_unknown_runs == 0`; kalau `false`, `usd_known_total` dan `cost_per_success` hanya atas run yang diketahui |
| `attempts` | `{"mean", "median"}` atas run **DONE**; `null` bila tidak ada; `distribution`: `{jumlah attempt: jumlah run}` atas semua run yang punya `result.json` |
| `supervision_minutes` | `{"runs_with_data": n, "total": jumlah, "mean": rata-rata}` hanya atas run yang punya nilai; `n == 0` berarti `total` dan `mean` bernilai `null`, **tidak 0** |
| `events_skipped` | jumlah semua `events_skipped` per run |

`agent-completed` / `human-assisted` / `failed` (status pilot) **bukan** keluaran agregator: itu keputusan reviewer, tidak dihitung dari data.

## 6. Kriteria yang membuktikan refactor mempertahankan perilaku lama (bukan sekadar tampak masuk akal)

1. **Keluaran emas, byte demi byte:** teks standar `audit_run.py` dan `failure_trace.py` atas F1, F2, F3, F5 sama dengan yang dihasilkan
   skrip **lama** pada commit dasar. Golden dicatat dari skrip lama dan ditanam di tes; refactor yang mengubah satu spasi gagal.
2. **Perilaku baru, ditetapkan eksplisit:** F4, F5c, F7 (bagian 3) dengan keluaran persis yang ditulis di tes.
3. **Agregator:** keluaran JSON persis (string emas) untuk satu himpunan F1–F7 dengan dan tanpa berkas supervisi, plus kasus tepi:
   tidak ada run DONE (`cost_per_success: null`, `attempts: null`), semua biaya tak diketahui, supervisi sebagian, berkas supervisi
   tidak valid (exit 2), argumen bukan run.
4. **Tidak disentuh:** keempat skrip eksperimen dan semua yang dilindungi (bagian 7) tidak berubah (dijaga lingkup tulis acceptance).
5. **Mutan** (dijalankan atas patch referensi sebelum dibekukan): pembaca kembali `json.loads` per baris; hanya baris terakhir
   yang ditoleransi; `events skipped` dicetak walau 0; pemotongan teks diubah; urutan baris diubah; nol panggilan memanggil
   `calls[0]` lagi; biaya tak diketahui dihitung 0 di agregator; `cost_per_success` memakai semua run (bukan hanya yang diketahui);
   `success_rate` menghitung `NO_RESULT` sebagai gagal; menit hilang dihitung 0; `done` memakai `status != "FAILED..."`; berkas
   supervisi tidak valid diterima.

**Tes yang gagal di baseline (wajib merah karena assertion):** perilaku baru (3.1, 3.2, 3.3) dan seluruh agregator (skrip belum ada,
jadi gagal karena exit code dan keluaran, bukan error impor). **Penjaga yang lulus di baseline:** keluaran emas F1, F2, F3, F5 atas
skrip lama (tidak masuk `must_pass`, aturan baseline merah W2a, tetapi dijalankan di file target).

## 7. Batas perubahan

- **Writable:** `scripts/audit_run.py`, `scripts/failure_trace.py`, `scripts/pilot_report.py` (baru), dan **satu modul pembaca bersama
  baru di `evals/runlog.py`** (nama dan lokasi ditetapkan supaya lingkup tulis bisa dikunci; isinya keputusan coder).
- **Protected:** `tests/**`, `conftest.py`, `evals/score.py`, `evals/runner.py`, `evals/__init__.py`, `harness/**`, `acceptance/**`,
  `codetask/**`, `tools/**`, `models/**`, `nodes/**`, `runner.py`, `graph.py`, `config.yaml`, dan **keempat skrip eksperimen**
  (`analyze_series.py`, `sim_admission.py`, `dry_feedback.py`, `measure_context.py`).
- **Di luar scope (eksplisit, sesuai arahan GPT):** acceptance inti, `reconcile_ledger`, sistem approval, pembukaan PR otomatis,
  arsitektur multi-agent, perubahan format `result.json`, dan skrip eksperimen.
- Agregator memakai `cost_is_known` dari `evals/score.py` yang sudah ada (tidak mendefinisikan ulang "diketahui").

## 8. Metrik yang dicatat saat dijalankan

Kebenaran keluaran (tes emas), file yang berubah (harus hanya empat yang writable), hasil regresi, biaya aktual, jumlah attempt,
waktu supervisi. Seperti pilot sebelumnya, `agent-completed` hanya bila patch diterapkan tanpa perubahan dan `verify.sh` lulus.

## 9. Ukuran dan profil budget (perkiraan, keputusan ditunda)

Agen perlu membaca `audit_run.py`, `failure_trace.py`, `evals/score.py`, `harness/events.py` dan bagian `codetask/agent.py` (kira-kira
20–30 ribu karakter) lalu menulis satu modul, satu skrip, dan dua refactor, jadi banyak langkah. Pilot 2 (tiga berkas dibaca, tiga
penyuntingan) sudah menabrak reservasi 30.000 token pada langkah ke-4. Task ini lebih besar, jadi attempt pertama hampir pasti
menabrak lagi. Sebelum preflight gue hitung angkanya dengan simulasi harness sendiri (`scripts/measure_context.py simulate`, tanpa
biaya) untuk menilai apakah `default` cukup; **profil `large` dan cap $1 belum disetujui**, ditetapkan setelah angkanya ada.

## 10. Keputusan yang diminta dari review

1. Setuju dipersempit (pembaca bersama + dua pemeriksa + agregator; keempat skrip eksperimen tidak disentuh), dengan dua validasi
   dilaporkan terpisah? Atau dipecah jadi 3a dan 3b?
2. Definisi agregator di bagian 5 (khususnya: sukses = `DONE`; biaya per sukses = total biaya yang diketahui dibagi `DONE` di antara
   run yang biayanya diketahui; `NO_RESULT` = biaya tak diketahui dan bukan gagal; menit hilang `null`).
3. Perubahan perilaku yang disengaja di bagian 3 (hanya tiga, semuanya crash hari ini), termasuk baris `events skipped: N` hanya bila N > 0.
4. Keluaran emas byte demi byte sebagai kriteria utama refactor, dengan prasyarat kesamaan host-sandbox.
5. Modul bersama dikunci di `evals/runlog.py` (hanya lokasi, bukan isi).
