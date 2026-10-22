# Pilot 3a D5, run `pilot3a5`: hasil

2026-10-22. Task `fix_run_inspectors_v2` (kontrak `ca8a521eb8b7`), config `pilots/m6_pilot3/3a/d5/config_pilot3a_d5.yaml`, Argus `ea05e98`
(checkout bersih), Sonnet 5.5, D1 + D2 + D3 + **D5 (prompt caching)**. Sama dengan `pilot3a4` kecuali caching. Kriteria ditulis sebelum run
(`d5/PREFLIGHT.md` bagian 4).

## Ringkasan

| | `pilot3a4` (tanpa cache) | **`pilot3a5` (D5)** |
|---|---|---|
| Status | `FAILED_ACCEPTANCE` (`max_usd`) | **`DONE`** (all criteria passed) |
| Attempt | 1, berakhir `reservation_exhausted` di langkah 8 | 1, berakhir `finished` (Finish di langkah 7) |
| Panggilan model | 8 ok + 1 ditolak | 8 ok, 0 ditolak |
| Biaya | $0,3947 | **$0,1501** (`usd_complete` true) |
| Biaya tanpa cache untuk panggilan yang sama (estimasi) | | $0,4208 (hemat $0,2707, **64%**) |
| Eksplorasi sebelum tulisan pertama | 6 panggilan, $0,2364 | 5 panggilan, **$0,0770** (tanpa cache: ±$0,186) |
| Tes wajib gagal sesudah validasi otomatis | 3 → 1 | 3 → **0** |
| Paket review (`build_review.py`) | | **valid**, 0 masalah, validasi segar: inspectors pass, regression pass |

## Jalur (`timeline.txt`, `failure_trace.txt`)

| Langkah | Masukan | Read | Write | Keluaran | USD | Kumulatif | Apa |
|---|---|---|---|---|---|---|---|
| s0 | 3.097 | 0 | 3.093 | 139 | 0,0091 | 0,0091 | ListFiles, baca `audit_run.py` dan `failure_trace.py` |
| s1 | 12.657 | 3.093 | 9.562 | 172 | 0,0259 | 0,0351 | baca dua tes baru dan `harness/events.py` |
| s2 | 23.840 | 12.655 | 11.183 | 198 | 0,0312 | 0,0663 | SearchFiles |
| s3 | 24.131 | 23.838 | 291 | 340 | 0,0065 | 0,0728 | SearchFiles |
| s4 | 24.526 | 24.129 | 395 | 78 | 0,0042 | 0,0770 | baca `codetask/tools.py` |
| s5 | 30.887 | 24.524 | 6.361 | 1.078 | 0,0291 | 0,1061 | tulis `evals/runlog.py` → **validasi otomatis 1**: inspectors gagal (exit 1, 34,1 detik) |
| s6 | 32.822 | 30.885 | 1.933 | 2.125 | 0,0292 | 0,1353 | tulis `failure_trace.py`, 6× EditFile `audit_run.py` → **validasi otomatis 2**: inspectors **lulus**, regression lulus |
| s7 | 36.070 | 32.818 | 3.248 | 344 | 0,0148 | 0,1501 | Finish (klaim: tests_pass ×2, issue_fixed, file_changed ×3) |

Acceptance: inspectors lulus (34,9 detik), regression lulus (4,7 detik), verdict `pass`, `DONE`.

## Kriteria (`d5/PREFLIGHT.md` bagian 4)

**A. Caching bekerja: terpenuhi.**
1. `cache_read > 0` di setiap panggilan sejak panggilan kedua (s1–s7); `cache_creation` tercatat di setiap panggilan; tidak ada `cache_ttl_unexpected`.
   Pola loop yang sehat: tiap panggilan membaca seluruh prefix sebelumnya dan menulis hanya bagian barunya (mis. s3: read 23.838, write 291).
2. Penghematan: `usd_saved_estimate` $0,2707 dari $0,4208 = **64%** (syarat ≥ 50%).
3. Aturan uang dan audit: tidak ada `budget_violation`, `estimate_overrun`, `llm_count_failed`, atau `tool_denied`; `usd_complete` true;
   `audit_run.py`: **8 hash diperiksa, 0 mismatch** (hash dan memo tanpa penanda cache, seperti dirancang).

**B. Apakah ≥ 2 putaran perbaikan muat di attempt 0:** **tidak diuji oleh run ini, karena tidak dibutuhkan.** Satu putaran perbaikan (s6)
membuat semua tes lulus. Anggaran yang tersisa di attempt saat Finish: $0,45 − $0,1501 = ±$0,30, sementara satu putaran (tulis + validasi
otomatis + panggilan berikutnya) di run ini ±$0,03–0,04. Jadi ruang untuk beberapa putaran lagi ada, tetapi run ini tidak membuktikannya.

**C. Dicatat:**
- Eksplorasi sebelum tulisan pertama: 5 langkah (`pilot3a4`: 6), jalurnya mirip: tiga langkah pertama sama alatnya (ListFiles, baca dua
  skrip; baca dua tes dan `harness/events.py`; SearchFiles), lalu menyimpang (s3–s4 di sini mencari `def offered` dan membaca
  `codetask/tools.py`). Agen tidak deterministik; perilaku tidak bisa dibandingkan lebih dari satu sampel.
- Puncak masukan 36.070 (taksiran) di bawah batas 40.000.
- `RunValidation` tidak pernah dipanggil (sebelum maupun sesudah validasi otomatis).
- Durasi sandbox: `auto` inspectors 34,1 / 34,5 detik, regression 4,4 / 4,5; `acceptance` inspectors 34,9, regression 4,7. Total run 157 detik.
- Patch agen (`agent_changes.diff`, 188 baris; patch referensi 146) bukan patch referensi, tetapi lulus semua validasi kontrak, termasuk saat
  dijalankan ulang segar oleh `build_review.py` (`review/`).

## Catatan

- **Satu sampel.** `DONE` di sini tidak berarti D5 selalu cukup; yang ditunjukkan run ini adalah biaya per panggilan dengan cache dan bahwa
  semua jaminan uang tetap utuh. Jalur agen kali ini juga lebih pendek dari `pilot3a4` (menulis di s5, bukan s6; satu putaran perbaikan cukup).
- Bentuk usage nyata dari Anthropic (dengan rincian TTL) cocok dengan yang diuji di D5 dari dokumentasi: `cache_creation` = write 5m, tidak ada
  write 1 jam.
- Patch agen belum diterapkan ke mana pun. Menerapkannya ke `main` (pilot 3a menjadi `agent-completed`) adalah keputusan terpisah: review diff,
  terapkan, `verify.sh` penuh.
