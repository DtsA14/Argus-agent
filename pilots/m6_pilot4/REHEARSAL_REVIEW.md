# M6 pilot 4: tiga hal yang diperiksa dari artefak (permintaan reviewer, 2026-10-21)

Tidak ada merge dan tidak ada live run. Bukti ada di `evidence/`.

## 1. Happy path menguji acceptance yang relevan, bukan sekadar `DONE`

- `evidence/review/changes.patch` adalah perubahan referensi (`is_peak` hanya di `models/pricing.py`) ditambah berkas tes yang disetujui.
- `evidence/review/tests.md`: validasi `target` **13 dari 13** tes lulus, baik di workspace agen maupun pada tree bersih yang dibangun ulang dari commit
  dasar + `changes.patch` ("Fresh"); `regression` lulus 17 tes. Semua 12 cek paket review ok.
- Keempat aturan yang diminta ada di tes dan di mutan:

| Aturan | Tes (di berkas 13 tes) | Mutan yang membuktikan tes menangkapnya |
|---|---|---|
| jendela lintas tengah malam | `test_the_evening_part_...`, `test_the_early_morning_part_...`, `test_two_windows_...`, `test_a_time_in_another_zone_...`, `test_the_multiplier_and_the_cost_...` (wajib, merah di baseline) | `crossing_windows_never_match_again`, `wrap_uses_and_instead_of_or`, `wrap_start_exclusive`, `crossing_window_matches_only_the_evening/morning` |
| `start == end` jendela kosong | `test_a_window_whose_start_equals_its_end_is_empty` (penjaga) | `equal_start_end_is_all_day` |
| `weekdays_only` pada tanggal UTC dari `now` | `test_weekdays_only_follows_the_utc_date_of_now_also_across_midnight` (wajib) | `weekday_on_the_date_the_window_began`, `weekend_check_inverted`, `weekdays_only_ignored` |
| akhir eksklusif | `test_hours_outside_a_window_across_midnight_..._end_is_exclusive`, `test_an_ordinary_window_is_start_inclusive_and_end_exclusive` (penjaga) | `wrap_end_inclusive`, `ordinary_end_inclusive`, `ordinary_start_exclusive` |

Batas yang jujur: happy path memakai model terskrip yang mengulang edit referensi. Ia membuktikan bahwa rantai harness+acceptance menerima patch yang benar
dan bahwa tes mencakup aturan-aturan itu (dibuktikan mutan); ia **tidak** membuktikan bahwa model sungguhan akan menulis patch yang benar.

## 2. Rehearsal negatif menjaga batas keamanan

`evidence/negative_audit.txt` (rehearsal diulang untuk audit, dengan keluaran lengkap):
- Penyuntingan `tests/test_peak_window.py` dan `config.yaml` **ditolak** oleh harness ("is protected by the contract and may not be changed").
- Workspace akhir sama dengan snapshot task kecuali `SUMMARY.json` (yang ditulis harness dari klaim); tidak ada perubahan terlarang yang tertinggal.
- Verdict kedua attempt gagal (`validation:target`, klaim `issue_fixed` dan `file_changed`); hasil `FAILED_ACCEPTANCE`; **tidak ada paket review** (`review/` tidak ada).

## 3. Angka budget konsisten dengan kontrak, dan bukan jaminan biaya

- Kontrak: `limits.max_usd` 0,75, `max_iterations` 3, profil `large`; config pilot: `budget.max_usd` 0,75 (satu beda dari `config.yaml`). Cap run = yang lebih ketat dari
  keduanya. Kontrol negatif dengan `config.yaml` (0,50) berhenti `max_usd` setelah 1 attempt.
- Yang membatasi percobaan: `max_iterations` 3 (diuji oleh `tests/test_codetask.py::test_no_attempt_beyond_max_iterations`, bagian `verify.sh`), aturan stagnasi
  (dua kegagalan identik berturut-turut; inilah yang menghentikan semua rehearsal), dan cap uang. Rehearsal **tidak** menjalankan batas `max_iterations` secara langsung
  (stagnasi lebih dulu); itu diuji oleh tes yang sudah ada.
- Angka biaya rehearsal ($0,066 dan $0,071 per attempt) berasal dari model terskrip dengan penghitung token terkalibrasi. Itu menunjukkan **mekanisme admisi**, bukan biaya
  model sungguhan: pada 3a, biaya nyata dua attempt $0,20 dan reservasi habis. Batas keras tetap $0,75 dan paling banyak 3 attempt; perkiraan "di bawah $0,15 per run" adalah perkiraan.
