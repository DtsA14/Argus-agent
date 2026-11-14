# Bukti SANDBOX-SPLIT (2026-11-14)

Tiga `verify_at` penuh berturut-turut pada commit kode `2d55d76bec4c9777d39162e05c2f72e4cb78b4c2` (`VERIFY_SANDBOX_GROUPS` bawaan = 2), tanpa job live dan tanpa `verify_at` kedua di mesin, dengan pengamat: `docker events` (start, die, oom), tekanan CPU/memori tiap 5 detik (`verification/sandbox_split_sample.sh`), dan cap waktu tiap fase tes (`ARGUS_TEST_TIMES`); analisis: `verification/sandbox_split_analyze.py`. Dasar: `verification/verify-20261113T201900Z-aarch64.log` (7175b91, satu grup).

| | dasar (1 grup) | run 1 | run 2 | run 3 |
|---|---|---|---|---|
| log | verify-20261113T201900Z | verify-20261114T015029Z | verify-20261114T020445Z | verify-20261114T021836Z |
| hasil | 4139 lolos, 1 xfailed, PASS | 4171 lolos, 1 xfailed, PASS | 4171, 1 xfailed, PASS | 4171, 1 xfailed, PASS |
| tes sandbox dilewati | 0 | 0 | 0 | 0 |
| waktu pytest | 1158,0 s | 740,4 s | 747,5 s | 738,3 s |
| sandbox_a (test_draft) wall | - | 598,7 s (149 tes) | 602,3 s | 599,4 s |
| sandbox_b wall | - | 729,8 s (595 tes) | 737,5 s | 728,3 s |
| kedua grup mulai | - | +0,0 / +0,0 | +0,0 / +0,0 | +0,0 / +0,0 |
| kematian 137 / oom | 28 / 1 | 28 / 1 | 28 / 1 | 28 / 1 |
| 137 atau oom di luar jendela tes sandbox | - | 0 | 0 | 0 |
| oom di jendela `test_memory_limit_kills_the_code` | ya (20:36:20) | ya | ya | ya |
| rincian per image (python / staging) | 8 / 16+3+1 | 8 / 16+3+1 | 8 / 16+3+1 | 8 / 16+3+1 |
| puncak tekanan CPU `some avg10` | 18,9 | 21,2 | 23,1 | 21,2 |
| puncak tekanan memori | 0 | 0 | 3,07 | 0 |
| memori tersedia minimum | 17,3 GB | 17,3 GB | 17,2 GB | 17,2 GB |
| kontainer hidup sekaligus (maks) | 4 | 4 | 4 | 4 |

Waktu dinding turun dari 1158,0 s menjadi 738 sampai 748 s (sekitar 7 menit lebih cepat, 36 persen). Total detik-CPU grup sandbox naik (1146,8 s menjadi sekitar 1327 s, sekitar 16 persen) karena dua grup berebut CPU; itu harga pembagiannya.

Margin waktu tes berbatas ketat (dasar, run 1, 2, 3; detik): `test_cleanup_is_bounded_and_reported_when_the_daemon_hangs` 5,23 / 5,35 / 5,34 / 5,35 terhadap batas `< 9`; `test_a_validation_that_hangs_is_killed_at_its_timeout` 3,35 / 3,42 / 3,37 / 3,46; `test_timeout_kills_and_removes_the_container` 3,25 / 3,34 / 3,42 / 3,38.

**Yang tidak bersih / catatan jujur**
- Aturan awal "tiap 137 jatuh di jendela satu tes pembunuh" diganti setelah run 1 (lihat spec 3.3): dengan dua grup bersamaan tiap kejadian punya 1 sampai 55 tes kandidat. Pengganti: jumlah per peran image sama dengan dasar, tidak ada di luar jendela, `oom` hanya di jendela tes batas memori.
- Tes terlama naik dari 43,3 s (dasar) menjadi 72 sampai 78 s (`test_eval_sandbox.py::test_search_value_references_pass_with_search_only_where_the_contract_adds_it`); batas luar tesnya 900 s, tetapi seberapa dekat satu run kontainer di dalamnya dengan `timeout_s` 60 belum diperiksa.
- Pengamat run 1 dan 2 sempat tidak berhenti (PID pembungkus `setsid` keliru) dan merekam run berikutnya; analisis memotong log di waktu tes terakhir tiap run.
- n = 3 pada satu mesin, satu repositori; kegagalan 137 yang jarang tidak akan terlihat dalam tiga run.
