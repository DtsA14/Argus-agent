# Pilot 3a v2, run `pilot3a4`: hasil

2026-10-22. Task `fix_run_inspectors_v2` (kontrak `ca8a521eb8b7`), config `pilots/m6_pilot3/3a/v2/config_pilot3a_v2.yaml`, Argus `7b2708c`
(checkout bersih), Sonnet 5.5, D1 + D2 + D3; D4 dan D5 tidak ikut. Kriteria dan ekspektasi ditulis sebelum run (`v2/PREFLIGHT.md`).

## Ringkasan

| | |
|---|---|
| Status | **`FAILED_ACCEPTANCE`**, alasan `max_usd` (attempt kedua tidak diterima) |
| Kriteria (`PREFLIGHT.md` bagian 3) | **2, berhasil sebagian**: pesan validasi otomatis pertama memuat error, dan sesudahnya agen memperbaiki dua dari tiga tes wajib yang gagal |
| Attempt | 1 (attempt 0 berakhir `reservation_exhausted` di langkah 8) |
| Biaya | **$0,394736** (8 panggilan ok, 1 ditolak sebelum dikirim; `usd_complete` true) dari cap $0,75 |
| Tes wajib akhir | 4 dari 5 lulus; gagal: `test_a_run_blocked_before_any_model_call_is_audited` |
| Waktu | 159 detik dari setup sampai verdict |

Percobaan sebelumnya, `pilot3a3`, mati sebelum panggilan model pertama: kunci ter-paste dua kali di prompt `go_live.sh`. Tidak ada
`llm_call_started` dan biayanya $0. Dicatat di sini dan tidak dihitung sebagai run. Celah yang ditemukan: kegagalan penghitungan token
mematikan proses, padahal seharusnya berakhir `BLOCKED provider_failed` (bagian 5).

## Jalur (`timeline.txt`, `failure_trace.txt`)

| Langkah | Masukan | Keluaran | USD | Kumulatif | Apa |
|---|---|---|---|---|---|
| s0 | 3.097 | 139 | 0,0076 | 0,0076 | ListFiles, baca `audit_run.py` dan `failure_trace.py` |
| s1 | 12.657 | 172 | 0,0270 | 0,0346 | baca dua tes baru dan `harness/events.py` |
| s2 | 23.840 | 195 | 0,0496 | 0,0842 | SearchFiles |
| s3 | 24.065 | 59 | 0,0487 | 0,1330 | baca `tests/test_run_stats.py` |
| s4 | 25.371 | 76 | 0,0515 | 0,1845 | SearchFiles |
| s5 | 25.472 | 101 | 0,0520 | 0,2364 | baca `evals/score.py`, `RunValidation(regression)` (lulus) |
| s6 | 30.424 | 1.335 | 0,0742 | 0,3106 | tulis `evals/runlog.py` → **validasi otomatis 1**: inspectors 3 gagal (3 tes wajib), error `StopIteration` di `failure_trace.py` |
| s7 | 32.617 | 1.888 | 0,0841 | 0,3947 | tulis `failure_trace.py`, 5× EditFile `audit_run.py` → **validasi otomatis 2**: inspectors 1 gagal (1 tes wajib), error pydantic `result["tools"]` = `None` |
| s8 | 35.763 (taksiran) | | ditolak | | sisa $0,0553 < masukan saja ($0,0715): `reservation_exhausted` |

Sesudahnya acceptance (verdict gagal: satu tes wajib, tanpa `SUMMARY.json`), lalu admission menolak attempt kedua: $0,3947 + $0,45 > $0,75.

## Kriteria dan yang dicatat (`PREFLIGHT.md` bagian 3)

- **Putaran perbaikan:** satu (tulisan s6 → validasi → perbaikan s7 → validasi). Tes wajib gagal turun **3 → 1**; error pertama berganti dari
  `StopIteration` ke error berikutnya (`result["tools"]` = `None`, cacat yang sama dengan yang diperkirakan di `CONTEXT_DESIGN.md` bagian 7).
- **Cacat `NameError` impor dari `pilot3a`/`pilot3a2` tidak muncul:** patch kali ini mengimpor `read_events, read_memo, read_result, skipped_line`
  dari awal.
- **`RunValidation` setelah validasi otomatis:** tidak pernah dipanggil. Satu-satunya `RunValidation` ada di s5, sebelum tulisan pertama.
- **Puncak masukan:** 35.763 (taksiran s8), di bawah batas 40.000; `context_limit` tidak terjadi.
- **Durasi sandbox per `origin`:** `auto` inspectors 33,3 / 34,6 detik, regression 4,5 / 4,5; `tool` regression 4,5; `acceptance` inspectors 34,9,
  regression 4,5.
- **Ekspektasi terhadap kenyataan:** satu attempt, sesuai ekspektasi. Biaya $0,39, dalam rentang perkiraan $0,25–0,45. Bedanya: agen menjelajah
  6 langkah sebelum menulis (di `pilot3a` 2 langkah), sehingga $0,31 sudah terpakai sebelum validasi otomatis pertama dan hanya ada ruang untuk
  satu putaran perbaikan. Simulasi D3 mengandaikan trajektori `pilot3a` (tulisan di langkah 2).
- **Patch akhir:** bukan patch referensi; satu tes wajib masih gagal (`agent_changes.diff`). Tidak diterapkan ke mana pun.

## Audit

`scripts/audit_run.py`: 8 hash prompt diperiksa, **1 mismatch di s7**. Penyebabnya bukan run, tetapi audit yang belum mengenal pesan D3: ia
membangun ulang setiap langkah dari memo dan tidak menyisipkan pesan `after_step`. Spesifikasi D3 keliru menulis bahwa audit tidak terpengaruh
(ia hanya menimbang prompt pertama). `prompt_hashes_with_d3_messages.py` membangun ulang semua permintaan dengan pesan itu disisipkan: **9 dari 9
cocok**, termasuk s8 yang ditolak (`prompt_hashes_with_d3_messages.txt`).

## 5. Tindak lanjut (tidak dikerjakan di sini)

1. `audit_run.py` menyisipkan pesan `after_step` (D3) saat membangun ulang langkah; tes dengan run sintetis ber-D3.
2. Kegagalan penghitungan token di `LLMCaller.call` (sebelum `llm_call_started`) berakhir `BLOCKED provider_failed`, bukan proses mati
   (`pilot3a3`). Tanpa uang, tetapi jalur kegagalan provider harus seragam.
3. Keputusan berikutnya untuk 3a (Atha/GPT): data run ini menunjukkan penjelajahan sebelum menulis memakan ±80% anggaran attempt. Kandidatnya
   D4 (batas ListFiles) dan petunjuk berkas di issue (H2), D5 (caching), atau cap yang memberi dua attempt penuh. Tidak ada run ulang tanpa
   persetujuan baru.
