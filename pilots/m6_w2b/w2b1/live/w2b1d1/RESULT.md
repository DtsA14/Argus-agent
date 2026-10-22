# Pilot W2b-1, run `w2b1d1`: hasil

2026-10-22. Drafter (`scripts/draft_task.py`), intake `argus_p6`, issue 3b, config `w2b1/config_w2b1.yaml`, Argus `8e1041b`
(checkout bersih), Sonnet 5.5. Kriteria ditulis sebelum run (`w2b1/PREFLIGHT.md` bagian 4).

## Ringkasan

| | |
|---|---|
| Status | **`NO_DRAFT`** (`output_truncated`): **gagal** menurut kriteria 1 |
| Panggilan model | 4, 0 ditolak; langkah 3 dari 16; **0 submit** dicek |
| Biaya | **$0,1596** (`usd_complete` true); cache read 31.769, write 27.385, penghematan ±$0,047 |
| Salinan intake | tidak berubah (`source_unchanged` true) |
| Waktu terminal | gerbang lolos 15:59:06Z, kunci 15:59:14Z, selesai 16:00:29Z (**1 menit 23 detik**) |

## Jalur (`events.jsonl`)

| Langkah | Masukan | Read | Write | Keluaran (thinking) | USD | Apa |
|---|---|---|---|---|---|---|
| s0 | 2.858 | 0 | 2.854 | 28 | 0,0074 | ListFiles |
| s1 | 10.461 | 2.854 | 7.605 | 215 | 0,0215 | baca `evals/runlog.py`, `evals/score.py`, `scripts/analyze_series.py`, `AGENTS.md` |
| s2 | 18.458 | 10.459 | 7.997 | 364 | 0,0247 | baca `tests/test_run_series.py`, `harness/events.py`, `fixtures/audit/pilot3a4/result.json`, `conftest.py`, `scripts/audit_run.py` |
| s3 | 27.387 | 18.456 | 8.929 | **8.192 (6.108)** | 0,1061 | `SubmitDraft` **terpotong** di `max_tokens` |

## Penyebab

Balasan `SubmitDraft` mencapai batas output 8.192 token. **6.108 di antaranya thinking** (Sonnet 5.5 berpikir secara
bawaan; Argus tidak mengaturnya untuk role mana pun). Sisa 2.084 token hanya cukup untuk `plan`, `scope`, dan sebagian
`validation`. `new_tests`, yaitu isi tesnya, belum sempat ditulis (`submit_cut_off_args.json`). Ini pola yang sama dengan
`argus_self_3` (thinking memakai seluruh output, pilot 2026-10-17).

Harness berperilaku seperti dirancang: balasan terpotong tidak dieksekusi, run berakhir tanpa draf, biaya tercatat
lengkap, dan tidak ada yang ditulis ke intake.

Asumsi di spec K6 ("tes 9,4 KB ≈ 3.000 token dalam satu SubmitDraft, output 8.192 cukup") **salah**, karena tidak
menghitung thinking. Satu balasan harus memuat thinking, rencana, kontrak, dan seluruh isi tes sekaligus.

## Yang terlihat dari draf yang terpotong (dicatat, bukan kriteria)

- **Scope:** writable hanya `scripts/pilot_report.py`, sama dengan draf manusia. Protected luas, memuat `tests/**`,
  `evals/**`, `harness/**`, dan seterusnya.
- **Rencana dan risiko** tepat sasaran: biaya tak diketahui tidak boleh jadi 0, menit 0 tetap data, bool ditolak, urutan
  numerik distribusi, penjumlahan nano-dollar, dan satu baris stderr tanpa traceback.
- **Validasi `target`** menyebut 29 node wajib (manusia: 17). Perilaku yang diuji manusia hampir semuanya muncul di nama
  node: laporan penuh dengan dan tanpa menit supervisi, semua run tanpa hasil, tanpa argumen, argumen bukan direktori
  run, berkas supervisi tidak valid (missing, empty, invalid JSON, list, bool, string, null, negative, nan, …), dan
  supervisi tanpa run. Tes yang tidak ada di draf manusia: urutan kunci, JSON kanonik, run id non-ASCII, dan run buruk
  setelah run yang baik. Isi tesnya tidak ada, jadi **cakupan tidak bisa dinilai** lebih jauh dari nama.
- Bacaan yang kurang perlu: `AGENTS.md`, `scripts/analyze_series.py`, dan `tests/test_run_series.py` dipakai sebagai contoh
  gaya. Puncak input 27.387, masih di bawah batas 40.000.

## Status pilot

**Gagal** (kriteria 2): berhenti. Tidak ada run ulang, kenaikan batas, atau perubahan config tanpa persetujuan baru.
Pilihan perbaikan ada di PR hasil ini.
