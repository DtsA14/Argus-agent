# Investigasi: biaya yang tidak diketahui di jalur eval (`evals/runner.py:126`)

Status 2026-10-21: **temuan untuk review; tidak ada perubahan kode.** Basis: `main` pada `d60fdf9`. Yang dikerjakan: kontrak data
biaya, semua pemakai, jalur datanya, dan apakah `null` didukung di seluruh jalur. Semua yang tertulis dibaca dari kode;
tidak ada run baru.

## 1. Kontrak data biaya, seperti yang didefinisikan kode hari ini

| Tingkat | Bentuk | Sumber |
|---|---|---|
| Per panggilan (ledger `llm_call`) | `usd` dan `usd_nano` **`null`** bila model tidak punya harga | `harness/llm.py` (`cost_usd` mengembalikan `None`); tes `tests/test_llm_audit_2a.py:46` ("unknown, not $0") |
| Per run (`reconcile_ledger`) | `usd` adalah **float** = jumlah panggilan **yang berharga**; `usd_complete` = `len(priced) == len(records)` | `harness/llm.py:224-236` |
| `result.json` | `usd_billed` (float, jumlah parsial) dan `usd_complete` (bool), selalu ditulis oleh `run_code_task` dan `runner.py` | `codetask/run.py:379`, `runner.py:122-123` |
| `run_stats` | menyalin `result.get("usd_billed")` dan `result.get("usd_complete")`; **`None` bila kunci hilang** | `evals/score.py:104` |

**Temuan kontrak:** di tingkat run, biaya yang tidak diketahui **tidak** berbentuk `null`. Ia berbentuk jumlah parsial
ditambah bendera `usd_complete: false`. `null` hanya ada di tingkat panggilan, dan di tingkat run hanya muncul bila kunci
hilang dari `result.json`. `README.md:37-38` menulis "recorded as unknown (`null`), never as $0, and `result.json` shows
`usd_complete: false`", yang benar untuk panggilan tetapi menyesatkan untuk total run.

## 2. Bisakah biaya tidak diketahui muncul di jalur eval hari ini?

**Tidak, dalam kondisi normal (cacat laten, bukan aktif).**
- `codetask/run.py:113` menolak (`ContractError`) model coder yang tidak punya harga, sebelum panggilan model apa pun.
- `max_usd` di config berhingga ($0.50), jadi `LLMCaller` juga menolak model tanpa harga (aturan `AGENTS.md`).
- Mode `reference` dan `wrong` memakai `fake:scripted` yang berharga.
- `run_code_task` selalu menulis `usd_billed` (float) dan `usd_complete`.

Jadi `usd_billed` bernilai `None` hanya bila `result.json` hilang kunci itu (file buatan tangan, versi lama, atau rusak), dan
`usd_complete: false` hanya bila salah satu penjaga di atas dilonggarkan. Kodenya sendiri **tidak gagal tertutup** terhadap
kedua kejadian itu, dan itu yang menjadi masalah: ia melindungi uang tetapi default-nya adalah nol.

## 3. Semua pemakai, dan bagaimana tiap pemakai memperlakukan biaya tak diketahui

| Pemakai | Perilaku sekarang | Menyentuh keputusan uang? | Penilaian |
|---|---|---|---|
| `evals/runner.py:126` `spent += usd_billed or 0.0` | `None` dihitung **0**; `usd_complete: false` (jumlah parsial) dihitung seolah lengkap | **Ya**: `spent` menentukan apakah task berikutnya masuk di bawah `max_total_usd` (baris 107) | **cacat fail-open** |
| `evals/runner.py:133` `usd_spent` di laporan | angka dari baris di atas, tanpa penanda | laporan | ikut sumbernya |
| `evals/score.py:141-148` `aggregate` | membuang baris `usd_billed is None` dari `usd_total`, `usd_median`, `usd_p95` tanpa penanda; mengabaikan `usd_complete` | tidak (laporan) | **menyembunyikan**: total dan median tampak lengkap padahal tidak |
| `scripts/run_eval.py:59` | `${usd_billed or 0:.4f}` mencetak `$0.0000` untuk tak diketahui | tidak (tampilan) | menyesatkan |
| `scripts/run_series.py:101` | berhenti bila `usd_billed is None` **atau** `usd_complete is not True`; `spent()` memakai `or 0` tetapi hanya setelah baris itu menghentikan seri | **Ya** | **sudah fail-closed**; ini pola acuan. Tes: `tests/test_run_series.py:140` (`(None, True)`, `(0.05, False)`, `(0.05, None)`) |
| `codetask/review.py:483` | mencetak "(incomplete: unpriced calls)" bila `usd_complete` salah | tidak (paket review) | benar |
| `scripts/analyze_series.py`, `measure_context.py`, `audit_run.py`, `dry_feedback.py`, `smoke_live.py` | memakai `usd_billed` langsung; analisis offline atau cetak | tidak | di luar scope |
| `harness/llm.py` `reconcile_ledger`, `runner.py`, `codetask/run.py` | sumber data (jumlah parsial plus bendera) | inti | **tidak diubah** |

## 4. Fakta yang membatasi pilihan perbaikan

1. Mengubah `reconcile_ledger` menjadi `None` bila tidak lengkap akan merembet ke banyak pemakai dan tes (semuanya
   mengasumsikan float) dan menyentuh ledger, komponen inti. **Tidak disarankan**; kontrak "jumlah parsial plus
   `usd_complete`" sudah ada dan cukup bila dikonsumsi dengan benar.
2. `tests/test_eval.py:189` (tes cap total live) menulis `result.json` **tanpa kunci `usd_complete`**. Aturan ketat seperti
   `run_series` (`usd_billed is None or usd_complete is not True` berarti tak diketahui) akan menghentikan eval itu setelah task
   pertama. Fixture tes itu harus diperbarui (`"usd_complete": true`); itu memang cerminan `result.json` asli.
3. `run_series` sudah punya definisi "tak diketahui" yang teruji dan dipakai di jalur uang. Memakai definisi yang sama di
   `evals/runner.py` menghindari dua definisi.

## 5. Usulan perbaikan (untuk disetujui sebelum implementasi)

**Definisi tunggal:** biaya sebuah run **diketahui** hanya bila `usd_billed is not None` **dan** `usd_complete is True`
(sama dengan `run_series.py:101`). Selain itu **tak diketahui**.

1. `evals/runner.py`
   - Biaya tak diketahui **tidak pernah** ditambahkan sebagai 0. Hentikan eval dengan alasan "the run's cost is unknown",
     sama dengan `STOP_ON`/`run_series`: cap total tidak bisa ditegakkan tanpa biaya yang diketahui, jadi task berikutnya
     tidak dimulai (`not_run`).
   - `usd_spent` di laporan: tetap angka (batas bawah, seperti `usd` di tingkat run) **plus** `usd_complete: false` (usulan),
     atau `null`. **Keputusan untuk GPT, bagian 6.**
2. `evals/score.py` `aggregate`: hitung `usd_total`, `usd_median`, `usd_p95` hanya dari run yang diketahui dan tambahkan
   `usd_unknown_runs` (jumlah) sehingga total yang tidak lengkap tidak tampak lengkap.
3. `scripts/run_eval.py`: cetak `n/a` (bukan `$0.0000`) untuk biaya tak diketahui.
4. `README.md:37-38`: sebut dengan tepat bahwa tak diketahui di tingkat panggilan adalah `null`, dan di tingkat run adalah
   jumlah parsial plus `usd_complete: false`.
5. `PENDING.md`: perbarui butir "biaya tak diketahui".

Tidak diubah: `harness/llm.py`, `runner.py`, `codetask/run.py`, `scripts/run_series.py`.

## 6. Keputusan yang dibutuhkan dari GPT

1. **Definisi "diketahui"** (usulan: `usd_billed is not None and usd_complete is True`, sama dengan `run_series`). Kunci
   `usd_complete` yang hilang berarti tak diketahui.
2. **Perilaku eval live saat satu run tak diketahui:** berhenti (usulan) atau lanjut dengan penanda? Gue sarankan berhenti,
   karena cap total tidak bisa ditegakkan.
3. **Bentuk `usd_spent` saat tak lengkap:** angka batas bawah plus `usd_complete: false` (usulan; konsisten dengan kontrak
   ledger) atau `null` (lebih tegas, tetapi mengubah tipe bidang yang dikonsumsi `run_eval.py` dan tes).
4. **`aggregate`:** total atas run yang diketahui plus `usd_unknown_runs` (usulan) atau `null` bila ada satu pun yang tak
   diketahui.
5. Setuju bahwa `reconcile_ledger` dan `run_series` tidak diubah?

## 7. Rencana tes dan mutan (setelah keputusan)

**Tes yang gagal di kode lama** (`tests/test_eval.py`, file hanya boleh ditambah di sisi tes):
- run dengan `usd_billed: null` di tengah eval live: eval berhenti, task berikutnya `not_run`, `spent` tidak bertambah 0;
- run dengan `usd_billed: 0.05, usd_complete: false`: sama;
- run dengan `usd_complete` hilang: sama;
- `aggregate` dengan satu baris tak diketahui: `usd_total` hanya atas yang diketahui dan `usd_unknown_runs == 1`;
- `run_eval.py` mencetak `n/a`.

**Regresi:** `test_the_live_total_cap_is_checked_against_cumulative_spend` (fixture diperbarui `usd_complete: true`; angka
`usd_spent == 0.60` tetap), tes `aggregate` yang ada, `tests/test_run_series.py`, dan `tests/test_eval_sandbox.py` (run
sungguhan: `usd_spent == usd_billed > 0`).

**Mutan:** kembali ke `or 0.0`; hanya memeriksa `None` tanpa `usd_complete`; hanya memeriksa `usd_complete` tanpa `None`;
menghitung `usd_complete` yang hilang sebagai lengkap; tidak berhenti (lanjut dengan penanda); `aggregate` menghitung baris
tak diketahui sebagai 0; `aggregate` tanpa `usd_unknown_runs`; cetakan `$0.0000`.

**Gerbang merge:** tes yang gagal di kode lama, mutan semua tertangkap, `verify.sh` penuh (0 skip sandbox).
